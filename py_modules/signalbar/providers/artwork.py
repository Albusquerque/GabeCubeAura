"""Artwork palette state and disk cache.

Image decoding happens in Steam's browser canvas; this provider owns validated
17-pixel results and persists them by AppID, artwork fingerprint, and row mode.
"""

from __future__ import annotations

import json
import os
import threading

from signalbar.models import ProviderOutput, normalize_frame


class ArtworkProvider:
    name = "artwork"

    def __init__(self, cache_path):
        self.cache_path = cache_path
        self._lock = threading.RLock()
        self._cache = {}
        self._current = None
        self._load()

    @staticmethod
    def key(appid, fingerprint, mode, manual_y):
        suffix = f"{float(manual_y):.3f}" if mode == "manual" else "-"
        return f"{int(appid)}:{fingerprint}:{mode}:{suffix}"

    def _load(self):
        try:
            with open(self.cache_path, encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                self._cache = raw
        except (OSError, ValueError, TypeError):
            self._cache = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        temporary = self.cache_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self._cache, handle, separators=(",", ":"), sort_keys=True)
        os.replace(temporary, self.cache_path)

    @staticmethod
    def _dominant_palettes(raw):
        if not isinstance(raw, dict):
            return {}
        palettes = {}
        for count in (2, 3):
            values = raw.get(str(count), raw.get(count))
            if not isinstance(values, (list, tuple)) or len(values) != count:
                continue
            try:
                colours = []
                for colour in values:
                    if not isinstance(colour, (list, tuple)) or len(colour) != 3:
                        raise ValueError("invalid dominant colour")
                    colours.append(tuple(max(0, min(255, int(round(float(channel))))) for channel in colour))
                palettes[str(count)] = colours
            except (TypeError, ValueError, OverflowError):
                continue
        return palettes

    def activate_cached(self, appid, fingerprint, mode, manual_y):
        with self._lock:
            entry = self._cache.get(self.key(appid, fingerprint, mode, manual_y))
            if not isinstance(entry, dict):
                self._current = None
                return False
            try:
                frame = normalize_frame(entry.get("colors"))
            except (ValueError, TypeError):
                self._current = None
                return False
            palettes = self._dominant_palettes(entry.get("dominant_palettes"))
            self._current = {**entry, "frame": frame, "appid": int(appid),
                             "dominant_palettes": palettes}
            # v0.7.1 caches remain valid for Artwork, but are resampled once so
            # the launch-animation palette is not guessed from the 17-pixel row.
            return set(palettes) == {"2", "3"}

    def submit(self, appid, fingerprint, mode, manual_y, colors, sample_y,
               filename="", source="hero", dominant_palettes=None):
        frame = normalize_frame(colors)
        palettes = self._dominant_palettes(dominant_palettes)
        if set(palettes) != {"2", "3"}:
            raise ValueError("artwork sampling must include two- and three-colour palettes")
        entry = {
            "colors": [list(pixel) for pixel in frame],
            "dominant_palettes": {
                count: [list(colour) for colour in values]
                for count, values in palettes.items()
            },
            "sample_y": float(sample_y),
            "filename": os.path.basename(str(filename or "")),
            "source": str(source or "hero"),
        }
        with self._lock:
            self._cache[self.key(appid, fingerprint, mode, manual_y)] = entry
            # Bound cache growth without adding a database.
            while len(self._cache) > 256:
                self._cache.pop(next(iter(self._cache)))
            self._save()
            self._current = {**entry, "frame": frame, "appid": int(appid)}

    def clear(self):
        with self._lock:
            self._current = None

    def output(self, appid):
        with self._lock:
            if not self._current or self._current.get("appid") != int(appid or 0):
                return ProviderOutput(self.name, None, "artwork not sampled")
            return ProviderOutput(self.name, self._current["frame"], "Steam Library artwork")

    def dominant_palettes(self, appid=0):
        with self._lock:
            if not self._current or self._current.get("appid") != int(appid or 0):
                return {}
            return {
                count: [list(colour) for colour in values]
                for count, values in self._current.get("dominant_palettes", {}).items()
            }

    def status(self, colour_count=2):
        with self._lock:
            if not self._current:
                return {}
            palettes = self._current.get("dominant_palettes", {})
            selected = palettes.get(str(3 if int(colour_count) == 3 else 2), ())
            return {
                "sample_y": self._current["sample_y"],
                "filename": self._current["filename"],
                "source": self._current.get("source", "hero"),
                "colors": [list(pixel) for pixel in self._current["frame"]],
                "dominant_colors": [list(colour) for colour in selected],
            }
