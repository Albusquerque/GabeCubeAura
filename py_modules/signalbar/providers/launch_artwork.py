"""Per-game launch animations driven by artwork dominant colours."""

from __future__ import annotations

import math
import threading
import time

from signalbar.models import LED_COUNT, ProviderOutput, normalize_frame


BLACK = (0, 0, 0)
PATTERNS = {
    "arpege-crossed", "two-hands", "legato", "nocturne", "crescendo",
    "color-wipe", "scanner", "theater-chase", "twinkle", "ripple",
}


def _scale(colour, strength):
    """Dim one source hue towards black without creating a new hue."""
    strength = max(0.0, min(1.0, float(strength)))
    return tuple(round(channel * strength) for channel in colour)


def _add(frame, index, colour, strength=1.0):
    if 0 <= index < LED_COUNT and strength > 0:
        # Several glows may overlap on one LED. Mixing their RGB values would
        # invent a hue outside the selected two/three-colour palette. Keep the
        # strongest single-colour contribution instead.
        candidate = _scale(colour, strength)
        if max(candidate) > max(frame[index]) or (
                max(candidate) == max(frame[index]) and sum(candidate) > sum(frame[index])):
            frame[index] = candidate


def _glow(frame, centre, width, colour, strength=1.0):
    width = max(.1, width)
    for index in range(LED_COUNT):
        weight = max(0.0, 1.0 - abs(index - centre) / width) * strength
        _add(frame, index, colour, weight)


def _palette(values):
    if not isinstance(values, (list, tuple)) or len(values) not in (2, 3):
        raise ValueError("launch palette must contain two or three colours")
    out = []
    for colour in values:
        if not isinstance(colour, (list, tuple)) or len(colour) != 3:
            raise ValueError("each launch colour must contain three channels")
        out.append(tuple(max(0, min(255, int(round(float(channel))))) for channel in colour))
    return tuple(out)


def _envelope(elapsed, duration):
    # A fixed fade keeps the selected timer useful without slowing loop tempo.
    return min(1.0, elapsed / .45, max(0.0, duration - elapsed) / .65)


def pattern_frame(pattern, palette, phase, strength=1.0):
    """Render a palette-locked frame without a launch fade envelope."""
    if pattern not in PATTERNS:
        raise ValueError(f"unknown launch artwork pattern: {pattern}")
    colours = _palette(palette)
    phase = max(0.0, float(phase))
    strength = max(0.0, min(1.0, float(strength)))
    frame = [BLACK] * LED_COUNT

    if pattern == "arpege-crossed":
        travel = (phase * 5.1) % 32
        left = travel if travel <= 16 else 32 - travel
        right = 16 - left
        _glow(frame, left, 3.0, colours[0], strength)
        _glow(frame, right, 3.0, colours[1], strength)
        if len(colours) == 3:
            _glow(frame, 8 + math.sin(phase * 2.2) * 5, 2.1, colours[2], strength * .72)
    elif pattern == "two-hands":
        radius = abs(8 - ((phase * 4.0) % 16))
        _glow(frame, 8 - radius, 2.7, colours[0], strength)
        _glow(frame, 8 + radius, 2.7, colours[1], strength)
        if len(colours) == 3:
            _glow(frame, 8, 2.5, colours[2], strength * (1 - radius / 8) * .85)
    elif pattern == "legato":
        for index in range(LED_COUNT):
            wave = (math.sin(index * .58 - phase * 2.0) + 1) / 2
            first = colours[int(phase / 2) % len(colours)]
            second = colours[(int(phase / 2) + 1) % len(colours)]
            # Alternate palette members instead of interpolating between them.
            colour = second if wave >= .5 else first
            frame[index] = _scale(colour, strength * (.45 + .5 * wave))
    elif pattern == "nocturne":
        breath = .32 + .45 * (math.sin(phase * 1.15 - math.pi / 2) + 1) / 2
        for index in range(LED_COUNT):
            base = colours[index % len(colours)]
            frame[index] = _scale(base, strength * breath * (.55 + .35 * math.cos(index * .42) ** 2))
        spark = int(phase * 2.3) % LED_COUNT
        _glow(frame, spark, 1.4, colours[(spark + 1) % len(colours)], strength * .75)
    elif pattern == "crescendo":
        cycle = (phase % 3.2) / 3.2
        reach = cycle * 8.8
        for index in range(LED_COUNT):
            distance = abs(index - 8)
            if distance <= reach:
                colour = colours[min(len(colours) - 1, int(distance / 8 * len(colours)))]
                _add(frame, index, colour, strength * (.45 + .55 * cycle))
        _glow(frame, 8 - reach, 1.7, colours[0], strength)
        _glow(frame, 8 + reach, 1.7, colours[1], strength)
    elif pattern == "color-wipe":
        head = int((phase * 7.0) % (LED_COUNT + 6)) - 3
        colour_index = int(phase * 7.0 / (LED_COUNT + 6)) % len(colours)
        for index in range(LED_COUNT):
            if index <= head:
                _add(frame, index, colours[colour_index], strength * .82)
        _glow(frame, head, 2.4, colours[(colour_index + 1) % len(colours)], strength)
    elif pattern == "scanner":
        travel = (phase * 6.4) % 32
        position = travel if travel <= 16 else 32 - travel
        _glow(frame, position, 3.2, colours[int(phase / 2.5) % len(colours)], strength)
        _glow(frame, position - (2 if travel <= 16 else -2), 3.8,
              colours[(int(phase / 2.5) + 1) % len(colours)], strength * .32)
    elif pattern == "theater-chase":
        step = int(phase * 7.5)
        for index in range(LED_COUNT):
            if (index + step) % 3 == 0:
                _add(frame, index, colours[(index // 3 + step // 3) % len(colours)], strength)
            elif (index + step) % 3 == 1:
                _add(frame, index, colours[(index + 1) % len(colours)], strength * .18)
    elif pattern == "twinkle":
        tick = int(phase * 8)
        for index in range(LED_COUNT):
            seed = (index * 73 + tick * 47 + (index + tick) * 19) % 101
            if seed < 24:
                level = .4 + .6 * (1 - seed / 24)
                _glow(frame, index, 1.25, colours[(index * 5 + tick) % len(colours)], strength * level)
    elif pattern == "ripple":
        for offset in (0.0, 1.1, 2.2):
            age = (phase - offset) % 3.3
            radius = age / 3.3 * 9.5
            colour = colours[int(offset / 1.1) % len(colours)]
            _glow(frame, 8 - radius, 1.8, colour, strength * (1 - age / 3.3))
            _glow(frame, 8 + radius, 1.8, colour, strength * (1 - age / 3.3))

    return normalize_frame(frame)


def launch_frame(pattern, palette, elapsed_seconds, duration_seconds):
    """Render one deterministic 17-pixel launch frame."""
    duration = max(3.0, min(45.0, float(duration_seconds)))
    elapsed = max(0.0, float(elapsed_seconds))
    if elapsed >= duration:
        return normalize_frame([BLACK] * LED_COUNT)
    return pattern_frame(pattern, palette, elapsed, _envelope(elapsed, duration))


class LaunchArtworkProvider:
    name = "launch-artwork"

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._lock = threading.RLock()
        self._enabled = False
        self._pattern = "arpege-crossed"
        self._colour_count = 2
        self._duration = 8.0
        self._palettes = {}
        self._appid = 0
        self._pending_at = 0.0
        self._started_at = 0.0
        self._last_tick_at = 0.0
        self._elapsed = 0.0
        self._paused = False
        self._preview = False

    def configure(self, enabled, pattern, colour_count, duration):
        with self._lock:
            self._enabled = bool(enabled)
            self._pattern = pattern if pattern in PATTERNS else "arpege-crossed"
            self._colour_count = 3 if int(colour_count) == 3 else 2
            self._duration = max(3.0, min(45.0, float(duration)))
            if not self._enabled and not self._preview:
                self._clear_locked()

    def set_palettes(self, appid, palettes):
        validated = {}
        if isinstance(palettes, dict):
            for count in (2, 3):
                raw = palettes.get(str(count), palettes.get(count))
                try:
                    validated[count] = _palette(raw)
                except (TypeError, ValueError):
                    pass
        with self._lock:
            if validated:
                self._palettes[int(appid)] = validated
                while len(self._palettes) > 64:
                    self._palettes.pop(next(iter(self._palettes)))

    def clear_palettes(self, appid=None):
        with self._lock:
            if appid is None:
                self._palettes.clear()
            else:
                self._palettes.pop(int(appid or 0), None)

    def arm(self, appid, preview=False):
        with self._lock:
            if not preview and not self._enabled:
                return False
            appid = int(appid or 0)
            if appid <= 0 or self._colour_count not in self._palettes.get(appid, {}):
                # A real launch may arm before browser-side sampling completes.
                if not preview and appid > 0:
                    self._appid = appid
                    self._pending_at = self.clock()
                    self._started_at = 0.0
                    self._last_tick_at = 0.0
                    self._elapsed = 0.0
                    self._paused = False
                    self._preview = False
                    return True
                return False
            self._appid = appid
            self._pending_at = self.clock()
            self._started_at = 0.0
            self._last_tick_at = 0.0
            self._elapsed = 0.0
            self._paused = False
            self._preview = bool(preview)
            return True

    def cancel(self):
        with self._lock:
            self._clear_locked()

    def _clear_locked(self):
        self._appid = 0
        self._pending_at = 0.0
        self._started_at = 0.0
        self._last_tick_at = 0.0
        self._elapsed = 0.0
        self._paused = False
        self._preview = False

    @property
    def active(self):
        with self._lock:
            return self._started_at > 0

    @property
    def previewing(self):
        with self._lock:
            return self._preview

    def output(self, appid, allow_start=False, paused=False):
        with self._lock:
            now = self.clock()
            if self._appid <= 0 or int(appid or 0) != self._appid:
                return ProviderOutput(self.name, None, "no launch animation")
            palette = self._palettes.get(self._appid, {}).get(self._colour_count)
            if self._started_at <= 0:
                if now - self._pending_at > 12.0:
                    self._clear_locked()
                    return ProviderOutput(self.name, None, "launch palette wait expired")
                if not palette or not allow_start:
                    return ProviderOutput(self.name, None, "launch animation pending")
                self._started_at = now
                self._last_tick_at = now
                self._elapsed = 0.0
            delta = max(0.0, now - self._last_tick_at)
            self._last_tick_at = now
            self._paused = bool(paused)
            if not self._paused:
                self._elapsed += delta
            if self._elapsed >= self._duration:
                self._clear_locked()
                return ProviderOutput(self.name, None, "launch animation complete")
            if self._paused:
                return ProviderOutput(self.name, None, "launch animation paused by alert")
            frame = launch_frame(self._pattern, palette, self._elapsed, self._duration)
            return ProviderOutput(f"{self.name}:{self._pattern}", frame, "game launch artwork palette")

    def status(self, appid=0):
        with self._lock:
            now = self.clock()
            active = self._started_at > 0 and self._elapsed < self._duration
            pending = self._pending_at > 0 and not active and now - self._pending_at <= 12.0
            palette_appid = self._appid if active or pending else int(appid or 0)
            palette = self._palettes.get(palette_appid, {}).get(self._colour_count, ())
            return {
                "active": active,
                "paused": active and self._paused,
                "pending": pending,
                "pattern": self._pattern,
                "duration_seconds": self._duration,
                "remaining_seconds": max(0.0, self._duration - self._elapsed) if active else 0.0,
                "colour_count": self._colour_count,
                "dominant_colors": [list(colour) for colour in palette],
                "colors": [list(pixel) for pixel in (
                    launch_frame(self._pattern, palette, self._elapsed, self._duration)
                    if active and palette and not self._paused else []
                )],
            }
