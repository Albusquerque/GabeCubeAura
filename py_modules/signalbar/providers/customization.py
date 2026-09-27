"""Persistent user-authored light-bar display for Customization+."""

from __future__ import annotations

import threading
import time

from signalbar.models import LED_COUNT, ProviderOutput, normalize_frame
from signalbar.providers.controller import DURATIONS as CONTROLLER_DURATIONS
from signalbar.providers.controller import VARIANTS as CONTROLLER_VARIANTS
from signalbar.providers.controller import controller_frame
from signalbar.providers.events import VARIANT_DURATIONS, event_frame
from signalbar.providers.launch_artwork import PATTERNS, pattern_frame
from signalbar.providers.weather_sequences import weather_loop_seconds, weather_sequence


WEATHER_VARIANT_COUNTS = {
    "clear_day": 2, "clear_night": 2, "rain": 2, "cloud": 4,
    "breaks": 2, "breaks_night": 2, "snow": 2, "storm": 2,
}
EVENT_PATTERNS = {f"event:{variant}" for variant in VARIANT_DURATIONS
                  if not variant.startswith("record-")}
CONTROLLER_PATTERNS = {
    f"controller:{kind}:{variant}"
    for kind, variants in CONTROLLER_VARIANTS.items() for variant in variants
}
WEATHER_PATTERNS = {
    f"weather:{condition}:{variant}"
    for condition, count in WEATHER_VARIANT_COUNTS.items() for variant in range(count)
}
CUSTOMIZATION_PATTERNS = {"steady"} | PATTERNS | EVENT_PATTERNS | CONTROLLER_PATTERNS | WEATHER_PATTERNS
BLACK = (0, 0, 0)


def _colour(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("a colour needs three RGB channels")
    return tuple(max(0, min(255, int(round(float(channel))))) for channel in value)


def _scale(colour, level):
    level = max(0, min(255, int(level)))
    return tuple(round(channel * level / 255) for channel in colour)


def _recolour(frame, palette, brightness, phase):
    """Keep an existing animation's light/dark choreography, using user hues."""
    result = []
    for index, pixel in enumerate(frame):
        level = max(pixel)
        if level <= 0:
            result.append(BLACK)
            continue
        selected = palette[(index + int(phase * .7)) % len(palette)]
        result.append(_scale(selected, round(brightness * level / 255)))
    return result


def customization_frame(pattern, colours, elapsed_seconds, brightness=128,
                        speed=50, direction="forward"):
    """Render one logical frame; brightness is the exact 0..255 RGB ceiling."""
    if pattern not in CUSTOMIZATION_PATTERNS:
        raise ValueError(f"unknown customization pattern: {pattern}")
    if not isinstance(colours, (list, tuple)) or not 1 <= len(colours) <= 3:
        raise ValueError("Customization+ needs one, two or three colours")
    palette = tuple(_colour(value) for value in colours)
    brightness = max(0, min(255, int(brightness)))
    speed = max(1, min(100, int(speed)))
    phase = max(0.0, float(elapsed_seconds)) * (.2 + speed * .028)

    if brightness == 0:
        frame = [BLACK] * LED_COUNT
    elif pattern == "steady":
        frame = [_scale(palette[0], brightness)] * LED_COUNT
    elif pattern.startswith("event:"):
        variant = pattern.split(":", 1)[1]
        kind = variant.split("-", 1)[0]
        duration = VARIANT_DURATIONS[variant]
        frame = _recolour(event_frame(kind, phase % duration, variant), palette, brightness, phase)
    elif pattern.startswith("controller:"):
        _, kind, variant = pattern.split(":", 2)
        duration = CONTROLLER_DURATIONS[kind]
        elapsed = phase % duration
        frame = _recolour(controller_frame(
            kind, variant, elapsed, 74, 35,
            intro_age=elapsed if kind == "duo" else None,
            continuous=kind == "charging",
        ), palette, brightness, phase)
    elif pattern.startswith("weather:"):
        _, condition, raw_variant = pattern.split(":", 2)
        variant = int(raw_variant)
        elapsed = phase % weather_loop_seconds(condition, variant)
        frame = _recolour(weather_sequence(condition, variant, elapsed), palette, brightness, phase)
    else:
        shared_palette = palette if len(palette) > 1 else (palette[0], palette[0])
        raw = pattern_frame(pattern, shared_palette, phase)
        frame = [_scale(pixel, brightness) for pixel in raw]

    if direction == "reverse":
        frame.reverse()
    return normalize_frame(frame)


class CustomizationProvider:
    name = "customization"

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._lock = threading.RLock()
        self._preview_until = 0.0

    def preview(self, seconds=8.0):
        with self._lock:
            self._preview_until = self.clock() + max(1.0, min(30.0, float(seconds)))
        return True

    def stop_preview(self):
        with self._lock:
            self._preview_until = 0.0

    def output(self, values, enabled=False):
        with self._lock:
            preview = self.clock() < self._preview_until
        if not enabled and not preview:
            return ProviderOutput(self.name, None, "Customization+ is not selected here")
        count = max(1, min(3, int(values.get("customization_colour_count", 1))))
        colours = [values[f"customization_colour_{index}"] for index in range(1, count + 1)]
        frame = customization_frame(
            values.get("customization_pattern", "steady"), colours, self.clock(),
            values.get("customization_brightness", 128),
            values.get("customization_speed", 50),
            values.get("customization_direction", "forward"),
        )
        provider = "customization:preview" if preview else f"customization:{values.get('customization_pattern', 'steady')}"
        return ProviderOutput(provider, frame, "Customization+ user display")

    def status(self, values):
        with self._lock:
            preview = self.clock() < self._preview_until
        count = max(1, min(3, int(values.get("customization_colour_count", 1))))
        colours = [values[f"customization_colour_{index}"] for index in range(1, count + 1)]
        return {
            "preview_active": preview,
            "colors": [list(pixel) for pixel in customization_frame(
                values.get("customization_pattern", "steady"), colours, self.clock(),
                values.get("customization_brightness", 128),
                values.get("customization_speed", 50),
                values.get("customization_direction", "forward"),
            )],
        }
