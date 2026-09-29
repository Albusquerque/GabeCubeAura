"""Live Gamescope capture and 17-pixel screen colour mapping.

Frames stay in memory. The capture service never creates screenshots, cache
files, or network requests.
"""

from __future__ import annotations

import colorsys
import json
import os
import select
import shutil
import subprocess
import threading
import time
from collections import deque

from signalbar.models import LED_COUNT, ProviderOutput, normalize_frame


CAPTURE_WIDTH = 34
CAPTURE_HEIGHT = 18
BYTES_PER_PIXEL = 4
FRAME_BYTES = CAPTURE_WIDTH * CAPTURE_HEIGHT * BYTES_PER_PIXEL

VALID_STYLES = {"panorama", "ambient"}
VALID_REACTIVITY = {"calm", "balanced", "fast"}
VALID_COLOUR_INTENSITY = {"natural", "vivid"}


def _clamp(value, low=0.0, high=255.0):
    return max(low, min(high, value))


def _srgb_to_linear(channel):
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(channel):
    value = 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055
    return int(round(_clamp(value, 0.0, 1.0) * 255.0))


def _luma(pixel):
    red, green, blue = pixel
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


class ScreenSyncProcessor:
    """Turn a tiny BGRx screen frame into a stable 17-pixel RGB frame."""

    _ALPHAS = {
        "calm": (0.24, 0.14),
        "balanced": (0.46, 0.28),
        "fast": (0.72, 0.52),
    }

    def __init__(self, width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT):
        self.width = int(width)
        self.height = int(height)
        self._previous = None
        self._bar_candidate = (0, 0)
        self._bar_streak = 0
        self._stable_bars = (0, 0)
        self._black_streak = 0

    def reset(self):
        self._previous = None
        self._bar_candidate = (0, 0)
        self._bar_streak = 0
        self._stable_bars = (0, 0)
        self._black_streak = 0

    def _decode(self, raw):
        expected = self.width * self.height * BYTES_PER_PIXEL
        if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != expected:
            raise ValueError(f"screen frame must contain exactly {expected} BGRx bytes")
        pixels = []
        view = memoryview(raw)
        for offset in range(0, expected, 4):
            blue, green, red = view[offset], view[offset + 1], view[offset + 2]
            pixels.append((red, green, blue))
        return pixels

    def _detect_bars(self, pixels, threshold):
        def row_is_black(row):
            start = row * self.width
            values = pixels[start:start + self.width]
            dark = sum(_luma(pixel) <= threshold + 4 for pixel in values)
            return dark >= int(self.width * 0.90)

        limit = max(0, self.height // 3)
        top = 0
        while top < limit and row_is_black(top):
            top += 1
        bottom = 0
        while bottom < limit and row_is_black(self.height - 1 - bottom):
            bottom += 1
        candidate = (top, bottom)
        if candidate == self._bar_candidate:
            self._bar_streak += 1
        else:
            self._bar_candidate = candidate
            self._bar_streak = 1
        if self._bar_streak >= 3:
            self._stable_bars = candidate
        return self._stable_bars

    @staticmethod
    def _mean_colour(pixels):
        if not pixels:
            return (0, 0, 0)
        # Bright HUD elements should not pull an entire LED zone to white.
        ordered = sorted(pixels, key=_luma)
        keep = max(1, int(round(len(ordered) * 0.95)))
        sample = ordered[:keep]
        linear = [sum(_srgb_to_linear(pixel[channel]) for pixel in sample) / len(sample)
                  for channel in range(3)]
        return tuple(_linear_to_srgb(channel) for channel in linear)

    def _zones(self, pixels, top, bottom, style):
        rows = range(top, max(top + 1, self.height - bottom))
        if style == "ambient":
            colour = self._mean_colour([
                pixels[row * self.width + column]
                for row in rows for column in range(self.width)
            ])
            return [colour] * LED_COUNT

        out = []
        for index in range(LED_COUNT):
            left = index * self.width // LED_COUNT
            right = max(left + 1, (index + 1) * self.width // LED_COUNT)
            out.append(self._mean_colour([
                pixels[row * self.width + column]
                for row in rows for column in range(left, right)
            ]))
        return out

    @staticmethod
    def _adjust(colours, brightness, colour_intensity, black_threshold):
        scale = _clamp(float(brightness), 34.0, 255.0) / 255.0
        saturation_scale = 1.30 if colour_intensity == "vivid" else 1.0
        adjusted = []
        for red, green, blue in colours:
            if _luma((red, green, blue)) <= black_threshold:
                adjusted.append((0, 0, 0))
                continue
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
            red_f, green_f, blue_f = colorsys.hsv_to_rgb(
                hue, _clamp(saturation * saturation_scale, 0.0, 1.0), value * scale
            )
            adjusted.append((
                int(round(_clamp(red_f, 0.0, 1.0) * 255)),
                int(round(_clamp(green_f, 0.0, 1.0) * 255)),
                int(round(_clamp(blue_f, 0.0, 1.0) * 255)),
            ))
        return adjusted

    @staticmethod
    def _spatial_blur(colours):
        if len(colours) < 2 or len(set(colours)) == 1:
            return list(colours)
        out = []
        for index, centre in enumerate(colours):
            left = colours[max(0, index - 1)]
            right = colours[min(len(colours) - 1, index + 1)]
            out.append(tuple(int(round(left[channel] * 0.2 + centre[channel] * 0.6
                                       + right[channel] * 0.2)) for channel in range(3)))
        return out

    def process(self, raw, *, style="panorama", brightness=160, reactivity="balanced",
                colour_intensity="natural", black_threshold=8, ignore_black_bars=True):
        if style not in VALID_STYLES:
            style = "panorama"
        if reactivity not in VALID_REACTIVITY:
            reactivity = "balanced"
        if colour_intensity not in VALID_COLOUR_INTENSITY:
            colour_intensity = "natural"
        black_threshold = int(_clamp(float(black_threshold), 0.0, 32.0))
        pixels = self._decode(raw)
        top, bottom = self._detect_bars(pixels, black_threshold) if ignore_black_bars else (0, 0)
        colours = self._zones(pixels, top, bottom, style)
        colours = self._adjust(colours, brightness, colour_intensity, black_threshold)
        colours = self._spatial_blur(colours)

        all_black = all(_luma(colour) <= black_threshold for colour in colours)
        self._black_streak = self._black_streak + 1 if all_black else 0
        if self._black_streak >= 3:
            result = [(0, 0, 0)] * LED_COUNT
        elif self._previous is None:
            result = colours
        else:
            brighten_alpha, darken_alpha = self._ALPHAS[reactivity]
            result = []
            for previous, current in zip(self._previous, colours):
                alpha = brighten_alpha if _luma(current) >= _luma(previous) else darken_alpha
                result.append(tuple(int(round(previous[channel] +
                                              (current[channel] - previous[channel]) * alpha))
                                    for channel in range(3)))
        self._previous = normalize_frame(result)
        return self._previous

    @property
    def crop(self):
        return self._stable_bars


class ScreenCaptureService:
    """Supervise a low-resolution GStreamer consumer of Gamescope PipeWire."""

    def __init__(self, clock=time.monotonic, popen=subprocess.Popen, run=subprocess.run):
        self._clock = clock
        self._popen = popen
        self._run_command = run
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._active = False
        self._frame = None
        self._frame_at = 0.0
        self._sequence = 0
        self._phase = "off"
        self._error = ""
        self._node_id = None
        self._node_name = ""
        self._conflicting_consumers = 0
        self._stderr = deque(maxlen=12)
        self._frames_seen = 0
        self._started_at = 0.0

    @staticmethod
    def _runtime_dir():
        candidates = []
        configured = os.environ.get("XDG_RUNTIME_DIR")
        if configured:
            candidates.append(configured)
        sudo_uid = os.environ.get("SUDO_UID")
        if sudo_uid and sudo_uid.isdigit():
            candidates.append(f"/run/user/{sudo_uid}")
        candidates.append("/run/user/1000")
        try:
            candidates.extend(
                f"/run/user/{entry}" for entry in os.listdir("/run/user") if entry.isdigit()
            )
        except OSError:
            pass
        for candidate in dict.fromkeys(candidates):
            if os.path.exists(os.path.join(candidate, "pipewire-0")):
                return candidate
        return configured or ""

    @staticmethod
    def _node_label(item):
        props = (item.get("info") or {}).get("props") or {}
        return " ".join(str(props.get(key, "")) for key in (
            "node.name", "node.description", "media.name", "application.name"
        )).strip()

    @classmethod
    def find_gamescope_node(cls, dump):
        best = None
        for item in dump if isinstance(dump, list) else []:
            if item.get("type") != "PipeWire:Interface:Node":
                continue
            props = (item.get("info") or {}).get("props") or {}
            label = cls._node_label(item)
            lowered = label.lower()
            media_class = str(props.get("media.class", "")).lower()
            if "video" not in media_class and "video" not in lowered:
                continue
            if any(term in lowered for term in ("camera", "v4l2", "loopback")):
                continue
            score = 0
            if "gamescope" in lowered:
                score += 100
            if "steam" in lowered and "game" in lowered:
                score += 20
            if "source" in media_class:
                score += 10
            if score and (best is None or score > best[0]):
                best = (score, int(item["id"]), label or "Gamescope video")
        return None if best is None else (best[1], best[2])

    @staticmethod
    def count_consumers(dump, node_id):
        count = 0
        for item in dump if isinstance(dump, list) else []:
            if item.get("type") != "PipeWire:Interface:Link":
                continue
            info = item.get("info") or {}
            props = info.get("props") or {}
            output_node = props.get("link.output.node", info.get("output-node-id"))
            state = str(info.get("state", "active")).lower()
            try:
                matches = int(output_node) == int(node_id)
            except (TypeError, ValueError):
                matches = False
            if matches and state not in {"error", "unlinked"}:
                count += 1
        return count

    def _pipewire_dump(self, runtime_dir):
        executable = shutil.which("pw-dump")
        if not executable:
            raise RuntimeError("pw-dump is not installed")
        environment = dict(os.environ)
        if runtime_dir:
            environment["XDG_RUNTIME_DIR"] = runtime_dir
        result = self._run_command(
            [executable], capture_output=True, text=True, timeout=2.0,
            check=False, env=environment,
        )
        if result.returncode:
            raise RuntimeError((result.stderr or "pw-dump failed").strip()[-240:])
        return json.loads(result.stdout)

    def set_active(self, active):
        active = bool(active)
        with self._lock:
            changed = active != self._active
            self._active = active
            if not active:
                self._phase = "off"
                self._error = ""
                self._conflicting_consumers = 0
        if not changed:
            return
        self._wake.set()
        if active and (self._thread is None or not self._thread.is_alive()):
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._supervise, name="gabecubeaura-screen-capture", daemon=True
            )
            self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._active = False
            self._phase = "off"

    def latest(self):
        with self._lock:
            return self._frame, self._sequence, self._frame_at

    def status(self):
        with self._lock:
            age = max(0.0, self._clock() - self._frame_at) if self._frame_at else None
            elapsed = max(0.001, self._clock() - self._started_at) if self._started_at else 0.0
            return {
                "phase": self._phase,
                "error": self._error,
                "node_id": self._node_id,
                "node_name": self._node_name,
                "conflicting_consumers": self._conflicting_consumers,
                "frame_age_s": age,
                "frames_per_second": self._frames_seen / elapsed if elapsed else 0.0,
            }

    def _set_state(self, phase, error="", consumers=0):
        with self._lock:
            self._phase = phase
            self._error = str(error)[:300]
            self._conflicting_consumers = max(0, int(consumers))

    def _wait(self, seconds):
        self._wake.wait(seconds)
        self._wake.clear()

    def _supervise(self):
        backoff = 0.5
        while not self._stop.is_set():
            with self._lock:
                active = self._active
            if not active:
                self._wait(0.25)
                continue
            process = None
            try:
                runtime_dir = self._runtime_dir()
                if not runtime_dir:
                    raise RuntimeError("PipeWire session was not found")
                gst = shutil.which("gst-launch-1.0")
                if not gst:
                    raise RuntimeError("GStreamer is not installed")
                dump = self._pipewire_dump(runtime_dir)
                node = self.find_gamescope_node(dump)
                if node is None:
                    raise RuntimeError("Gamescope video source was not found")
                node_id, node_name = node
                consumers = self.count_consumers(dump, node_id)
                with self._lock:
                    self._node_id, self._node_name = node_id, node_name
                if consumers:
                    self._set_state("conflict", "Another app is already capturing Gamescope", consumers)
                    self._wait(1.0)
                    continue
                environment = dict(os.environ)
                environment["XDG_RUNTIME_DIR"] = runtime_dir
                command = [
                    gst, "-q", "pipewiresrc", f"path={node_id}", "do-timestamp=true",
                    "!", "queue", "max-size-buffers=1", "leaky=downstream",
                    "!", "videoconvert", "!", "videoscale", "method=1",
                    "!", "videorate", "drop-only=true",
                    "!", "video/x-raw,format=BGRx,width=34,height=18,framerate=10/1",
                    "!", "fdsink", "fd=1", "sync=false",
                ]
                process = self._popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL, env=environment, bufsize=0,
                )
                os.set_blocking(process.stdout.fileno(), False)
                os.set_blocking(process.stderr.fileno(), False)
                buffer = bytearray()
                last_frame = self._clock()
                last_conflict_check = last_frame
                with self._lock:
                    self._started_at = last_frame
                    self._frames_seen = 0
                self._set_state("capturing")
                backoff = 0.5
                while not self._stop.is_set():
                    with self._lock:
                        active = self._active
                    if not active or process.poll() is not None:
                        break
                    readable, _, _ = select.select(
                        [process.stdout.fileno(), process.stderr.fileno()], [], [], 0.20
                    )
                    if process.stdout.fileno() in readable:
                        chunk = os.read(process.stdout.fileno(), FRAME_BYTES * 2)
                        if chunk:
                            buffer.extend(chunk)
                            while len(buffer) >= FRAME_BYTES:
                                frame = bytes(buffer[:FRAME_BYTES])
                                del buffer[:FRAME_BYTES]
                                last_frame = self._clock()
                                with self._lock:
                                    self._frame = frame
                                    self._frame_at = last_frame
                                    self._sequence += 1
                                    self._frames_seen += 1
                    if process.stderr.fileno() in readable:
                        message = os.read(process.stderr.fileno(), 2048).decode("utf-8", "replace").strip()
                        if message:
                            self._stderr.append(message[-240:])
                    now = self._clock()
                    if now - last_frame > 1.5:
                        raise RuntimeError("Gamescope capture stopped producing frames")
                    if now - last_conflict_check >= 2.0:
                        current = self._pipewire_dump(runtime_dir)
                        consumers = self.count_consumers(current, node_id)
                        if consumers > 1:
                            self._set_state(
                                "conflict", "Another Gamescope capture consumer appeared",
                                consumers - 1,
                            )
                            break
                        last_conflict_check = now
                if process.poll() not in (None, 0) and active:
                    detail = self._stderr[-1] if self._stderr else "GStreamer capture stopped"
                    raise RuntimeError(detail)
            except Exception as error:
                with self._lock:
                    conflict = self._phase == "conflict"
                if not conflict:
                    self._set_state("error", error)
                self._wait(backoff)
                backoff = min(5.0, backoff * 2.0)
            finally:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1.0)


class ScreenSyncProvider:
    def __init__(self, capture=None, processor=None, clock=time.monotonic):
        self.capture = capture or ScreenCaptureService(clock=clock)
        self.processor = processor or ScreenSyncProcessor()
        self.clock = clock
        self._active = False
        self._sequence = -1
        self._frame = None

    def set_active(self, active):
        active = bool(active)
        if active != self._active:
            self._active = active
            self.capture.set_active(active)
            if not active:
                self.processor.reset()
                self._sequence = -1
                self._frame = None

    def stop(self):
        self._active = False
        self.capture.stop()
        self.processor.reset()
        self._frame = None

    def output(self, values):
        if not self._active:
            return ProviderOutput("screen-sync", None, "Screen Sync is off")
        capture_status = self.capture.status()
        if capture_status.get("phase") != "capturing":
            reason = capture_status.get("error") or "Waiting for Gamescope capture"
            return ProviderOutput("screen-sync", None, reason)
        raw, sequence, sampled_at = self.capture.latest()
        if raw is None or not sampled_at or self.clock() - sampled_at > 1.0:
            return ProviderOutput("screen-sync", None, "Waiting for a fresh Gamescope frame")
        if sequence != self._sequence:
            self._frame = self.processor.process(
                raw,
                style=values["screen_sync_style"],
                brightness=values["screen_sync_brightness"],
                reactivity=values["screen_sync_reactivity"],
                colour_intensity=values["screen_sync_colour_intensity"],
                black_threshold=values["screen_sync_black_threshold"],
                ignore_black_bars=values["screen_sync_ignore_black_bars"],
            )
            self._sequence = sequence
        return ProviderOutput("screen-sync", self._frame, "Live Gamescope colours")

    def status(self):
        status = self.capture.status()
        status.update({
            "active": self._active,
            "colors": [list(pixel) for pixel in self._frame] if self._frame else [],
            "crop_top": self.processor.crop[0],
            "crop_bottom": self.processor.crop[1],
        })
        return status
