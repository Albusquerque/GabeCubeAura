"""Atomic, schema-limited JSON settings persistence."""

from __future__ import annotations

import json
import math
import os
import threading
from copy import deepcopy

DEFAULTS = {
    "mode": "performance",
    "display_profiles": {},
    # Retained only to migrate v0.1/v0.2 Automatic configurations.
    "performance_enabled": True,
    "performance_metric": "mixed",
    "performance_smoothing": "responsive",
    "performance_always": True,
    "mixed_direction": "mirrored",
    "temperature_palette": "classic",
    "temperature_custom_cool": [30, 180, 230],
    "temperature_custom_middle": [245, 180, 45],
    "temperature_custom_hot": [235, 45, 55],
    "artwork_mode": "auto",
    "artwork_manual_y": 0.34,
    "artwork_source": "hero",
    "artwork_profiles": {},
    "cool_temp_c": 45.0,
    "hot_temp_c": 78.0,
    "reverse_led_order": True,
    "parental_countdown_enabled": True,
    "countdown_colour": "white",
    # 0 follows the timer's initial duration; otherwise this is fixed minutes.
    "countdown_full_bar_minutes": 0,
    "countdown_dark_edge_compensation": 2,
    "free_timer_minutes": 60,
    "events_enabled": True,
    "event_notifications_enabled": True,
    "event_achievements_enabled": True,
    "event_screenshots_enabled": True,
    "event_recording_enabled": True,
    # Optional optical separation for the persistent red recording marker.
    "recording_marker_isolation": True,
    "event_notification_variant": "notification-beacon",
    "event_achievement_variant": "achievement-constellation",
    "event_screenshot_variant": "screenshot-bloom",
    "controller_battery_display": "home",
    # Charging choices are exclusive; legacy display/enabled keys are derived
    # for compatibility with older local beta settings.
    "controller_charging_mode": "continuous-home",
    "controller_charging_display": "home",
    "controller_alert_context": "both",
    "controller_alerts_enabled": True,
    "controller_connect_enabled": True,
    "controller_low_enabled": True,
    "controller_charging_enabled": False,
    "controller_low_threshold": 20,
    "controller_connect_variant": "welcome",
    "controller_persistent_variant": "tip",
    "controller_low_variant": "beacon",
    "controller_charging_variant": "breath",
    "controller_duo_variant": "double-welcome",
    "controller_colour_normal": [0, 180, 45],
    "controller_colour_medium": [230, 110, 0],
    "controller_colour_low": [220, 12, 24],
    "controller_colour_charging": [0, 145, 220],
    "controller_gauge_brightness": 65,
    "weather_display": "off",
    "weather_location": None,
    "weather_topbar_enabled": False,
    "weather_temperature_unit": "celsius",
    "weather_brightness": 100,
    "weather_shadow_cutoff": 0,
    "weather_sequence_revision": 11,
    "weather_clear_day_variant": 0,
    "weather_clear_night_variant": 0,
    "weather_rain_variant": 0,
    "weather_cloud_variant": 3,
    "weather_breaks_variant": 0,
    "weather_breaks_night_variant": 0,
    "weather_snow_variant": 1,
    "weather_storm_variant": 0,
    "stripmine_integration_enabled": True,
    "stripmine_priority_artwork": "stripmine",
    "stripmine_priority_performance": "stripmine",
    "stripmine_priority_weather": "stripmine",
    "stripmine_priority_controller": "stripmine",
    "stripmine_priority_light_events": "signalbar",
    "guard_cooldown_s": 5.0,
    "guard_stable_s": 2.0,
}

VALID_MODES = {"artwork", "performance", "events", "disabled"}
VALID_ARTWORK_MODES = {"auto", "center", "lower", "manual"}
VALID_ARTWORK_SOURCES = {"hero", "header", "capsule"}
VALID_PERFORMANCE_METRICS = {"cpu", "gpu", "mixed"}
VALID_PERFORMANCE_SMOOTHING = {"responsive", "balanced", "smooth"}
VALID_MIXED_DIRECTIONS = {"same", "mirrored"}
VALID_TEMPERATURE_PALETTES = {"thermal", "classic", "icefire", "custom"}
VALID_COUNTDOWN_COLOURS = {"cyan", "green", "amber", "violet", "white"}
VALID_COMPANION_PRIORITIES = {"stripmine", "signalbar"}
EVENT_VARIANTS = {
    "event_notification_variant": {
        "notification-original", "notification-return", "notification-echo",
        "notification-ample", "notification-double", "notification-beacon",
    },
    "event_achievement_variant": {
        "achievement-original", "achievement-confetti", "achievement-rebound",
        "achievement-constellation", "achievement-twoway", "achievement-supernova",
    },
    "event_screenshot_variant": {
        "screenshot-original", "screenshot-double", "screenshot-scan",
        "screenshot-bloom", "screenshot-ripple",
    },
}
CONTROLLER_VARIANTS = {
    "controller_connect_variant": {"welcome", "orbit", "handshake"},
    "controller_persistent_variant": {"clean", "tip", "horizon"},
    "controller_low_variant": {"beacon", "drain", "heartbeat"},
    "controller_charging_variant": {"current", "breath", "spark"},
    "controller_duo_variant": {"twin", "focus", "double-welcome"},
}
WEATHER_VARIANT_KEYS = tuple(key for key in DEFAULTS if key.startswith("weather_") and key.endswith("_variant"))
WEATHER_VARIANT_COUNTS = {"clear_day": 2, "clear_night": 2, "rain": 2, "cloud": 4,
                          "breaks": 2, "breaks_night": 2, "snow": 2, "storm": 2}


def _valid_weather_location(value):
    if not isinstance(value, dict):
        return None
    try:
        latitude = float(value["latitude"])
        longitude = float(value["longitude"])
        name = str(value["name"]).strip()[:80]
        country = str(value.get("country", "")).strip()[:80]
        if (not name or not math.isfinite(latitude) or not math.isfinite(longitude)
                or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
            return None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return {"name": name, "country": country, "latitude": latitude, "longitude": longitude}


class SettingsStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        with self._lock:
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = json.load(handle)
                if isinstance(raw, dict):
                    for key in DEFAULTS:
                        if key in raw:
                            self._data[key] = raw[key]
                    if raw.get("weather_sequence_revision") not in (10, 11):
                        migration = {
                            "clear_night": {0: 0, 3: 1},
                            "rain": {2: 0, 3: 1},
                            "storm": {3: 0, 4: 1},
                        }
                        for condition, variants in migration.items():
                            key = f"weather_{condition}_variant"
                            self._data[key] = variants.get(raw.get(key), 0)
                        self._data["weather_sequence_revision"] = 11
                    if "controller_charging_mode" not in raw:
                        display = raw.get("controller_charging_display")
                        if display == "home":
                            self._data["controller_charging_mode"] = "continuous-home"
                        elif display == "everywhere":
                            self._data["controller_charging_mode"] = "continuous-everywhere"
                        else:
                            self._data["controller_charging_mode"] = (
                                "brief" if raw.get("controller_charging_enabled", True) else "off"
                            )
            except (OSError, ValueError, TypeError):
                pass
            self._validate()
            return dict(self._data)

    def _validate(self):
        self._data["stripmine_integration_enabled"] = bool(self._data["stripmine_integration_enabled"])
        for key in (
            "stripmine_priority_artwork", "stripmine_priority_performance",
            "stripmine_priority_weather", "stripmine_priority_controller",
            "stripmine_priority_light_events",
        ):
            if self._data[key] not in VALID_COMPANION_PRIORITIES:
                self._data[key] = DEFAULTS[key]
        self._data["performance_enabled"] = bool(self._data["performance_enabled"])
        self._data["performance_always"] = bool(self._data["performance_always"])
        if self._data["mode"] == "automatic":
            self._data["mode"] = "performance" if self._data["performance_enabled"] else "artwork"
        elif self._data["mode"] not in VALID_MODES:
            self._data["mode"] = DEFAULTS["mode"]
        if self._data["artwork_mode"] not in VALID_ARTWORK_MODES:
            self._data["artwork_mode"] = DEFAULTS["artwork_mode"]
        if self._data["artwork_source"] not in VALID_ARTWORK_SOURCES:
            self._data["artwork_source"] = DEFAULTS["artwork_source"]
        if self._data["performance_metric"] not in VALID_PERFORMANCE_METRICS:
            self._data["performance_metric"] = DEFAULTS["performance_metric"]
        if self._data["performance_smoothing"] not in VALID_PERFORMANCE_SMOOTHING:
            self._data["performance_smoothing"] = DEFAULTS["performance_smoothing"]
        if self._data["mixed_direction"] not in VALID_MIXED_DIRECTIONS:
            self._data["mixed_direction"] = DEFAULTS["mixed_direction"]
        if self._data["temperature_palette"] not in VALID_TEMPERATURE_PALETTES:
            self._data["temperature_palette"] = DEFAULTS["temperature_palette"]
        for key in (
            "temperature_custom_cool", "temperature_custom_middle", "temperature_custom_hot",
            "controller_colour_normal", "controller_colour_medium", "controller_colour_low", "controller_colour_charging",
        ):
            value = self._data.get(key)
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                self._data[key] = list(DEFAULTS[key])
                continue
            try:
                self._data[key] = [max(0, min(255, int(round(float(channel))))) for channel in value]
            except (TypeError, ValueError, OverflowError):
                self._data[key] = list(DEFAULTS[key])
        try:
            self._data["controller_gauge_brightness"] = max(10, min(100, int(self._data["controller_gauge_brightness"])))
        except (TypeError, ValueError, OverflowError):
            self._data["controller_gauge_brightness"] = DEFAULTS["controller_gauge_brightness"]
        raw_display = self._data.get("display_profiles")
        display = {}
        if isinstance(raw_display, dict):
            for raw_id, mode in list(raw_display.items())[:512]:
                try:
                    appid = int(raw_id)
                except (TypeError, ValueError, OverflowError):
                    continue
                if 0 < appid <= 0xffffffff and isinstance(mode, str) and mode in {"artwork", "performance"}:
                    display[str(appid)] = mode
        self._data["display_profiles"] = display
        self._data["reverse_led_order"] = bool(self._data["reverse_led_order"])
        self._data["parental_countdown_enabled"] = bool(self._data["parental_countdown_enabled"])
        for key in (
            "events_enabled", "event_notifications_enabled", "event_achievements_enabled",
            "event_screenshots_enabled", "event_recording_enabled", "recording_marker_isolation",
            "controller_alerts_enabled", "controller_connect_enabled", "controller_low_enabled",
            "controller_charging_enabled",
        ):
            self._data[key] = bool(self._data[key])
        for key, choices in EVENT_VARIANTS.items():
            if not isinstance(self._data[key], str) or self._data[key] not in choices:
                self._data[key] = DEFAULTS[key]
        if (not isinstance(self._data["controller_battery_display"], str)
                or self._data["controller_battery_display"] not in {"off", "home", "game", "everywhere"}):
            self._data["controller_battery_display"] = DEFAULTS["controller_battery_display"]
        if self._data["weather_display"] not in {"off", "home", "game", "everywhere"}:
            self._data["weather_display"] = DEFAULTS["weather_display"]
        if not isinstance(self._data["weather_topbar_enabled"], bool):
            self._data["weather_topbar_enabled"] = False
        if self._data["weather_temperature_unit"] not in {"celsius", "fahrenheit"}:
            self._data["weather_temperature_unit"] = DEFAULTS["weather_temperature_unit"]
        self._data["weather_location"] = _valid_weather_location(self._data["weather_location"])
        if self._data["weather_location"] is None:
            self._data["weather_display"] = "off"
            self._data["weather_topbar_enabled"] = False
        for key, lower, upper in (("weather_brightness", 10, 100), ("weather_shadow_cutoff", 0, 60)):
            try:
                self._data[key] = max(lower, min(upper, int(round(float(self._data[key])))))
            except (TypeError, ValueError, OverflowError):
                self._data[key] = DEFAULTS[key]
        self._data["weather_sequence_revision"] = 11
        for key in WEATHER_VARIANT_KEYS:
            try:
                value = int(self._data[key])
                condition = key.removeprefix("weather_").removesuffix("_variant")
                count = WEATHER_VARIANT_COUNTS[condition]
                self._data[key] = value if 0 <= value < count else DEFAULTS[key]
            except (TypeError, ValueError, OverflowError):
                self._data[key] = DEFAULTS[key]
        # Corrupt or hand-edited configurations keep the older controller default.
        if self._data["weather_display"] != "off" and self._data["controller_battery_display"] != "off":
            self._data["weather_display"] = "off"
        charging_mode = self._data["controller_charging_mode"]
        if not isinstance(charging_mode, str) or charging_mode not in {
            "off", "brief", "continuous-home", "continuous-everywhere"
        }:
            charging_mode = DEFAULTS["controller_charging_mode"]
        self._data["controller_charging_mode"] = charging_mode
        self._data["controller_charging_enabled"] = charging_mode == "brief"
        self._data["controller_charging_display"] = {
            "off": "off", "brief": "off", "continuous-home": "home",
            "continuous-everywhere": "everywhere",
        }[charging_mode]
        if (not isinstance(self._data["controller_alert_context"], str)
                or self._data["controller_alert_context"] not in {"off", "home", "game", "both"}):
            self._data["controller_alert_context"] = DEFAULTS["controller_alert_context"]
        for key, choices in CONTROLLER_VARIANTS.items():
            if not isinstance(self._data[key], str) or self._data[key] not in choices:
                self._data[key] = DEFAULTS[key]
        try:
            threshold = int(round(float(self._data["controller_low_threshold"])))
            self._data["controller_low_threshold"] = max(5, min(30, threshold))
        except (TypeError, ValueError):
            self._data["controller_low_threshold"] = DEFAULTS["controller_low_threshold"]
        if self._data["countdown_colour"] not in VALID_COUNTDOWN_COLOURS:
            self._data["countdown_colour"] = DEFAULTS["countdown_colour"]
        try:
            full_bar_minutes = int(round(float(self._data["countdown_full_bar_minutes"])))
            self._data["countdown_full_bar_minutes"] = (
                full_bar_minutes if full_bar_minutes in {0, 60, 120, 180, 240} else 0
            )
        except (TypeError, ValueError):
            self._data["countdown_full_bar_minutes"] = DEFAULTS["countdown_full_bar_minutes"]
        try:
            self._data["countdown_dark_edge_compensation"] = max(
                0, min(6, int(round(float(self._data["countdown_dark_edge_compensation"]))))
            )
        except (TypeError, ValueError):
            self._data["countdown_dark_edge_compensation"] = DEFAULTS["countdown_dark_edge_compensation"]
        try:
            self._data["free_timer_minutes"] = max(5, min(240, int(round(float(self._data["free_timer_minutes"])))))
        except (TypeError, ValueError):
            self._data["free_timer_minutes"] = DEFAULTS["free_timer_minutes"]
        self._data["artwork_manual_y"] = max(0.15, min(0.90, float(self._data["artwork_manual_y"])))
        self._data["cool_temp_c"] = max(20.0, min(100.0, float(self._data["cool_temp_c"])))
        self._data["hot_temp_c"] = max(self._data["cool_temp_c"] + 1.0, min(120.0, float(self._data["hot_temp_c"])))
        self._data["guard_cooldown_s"] = max(1.0, min(30.0, float(self._data["guard_cooldown_s"])))
        self._data["guard_stable_s"] = max(0.5, min(10.0, float(self._data["guard_stable_s"])))
        raw_profiles = self._data.get("artwork_profiles")
        profiles = {}
        if isinstance(raw_profiles, dict):
            for raw_appid, raw_profile in list(raw_profiles.items())[:512]:
                try:
                    appid = str(int(raw_appid))
                except (TypeError, ValueError):
                    continue
                if int(appid) <= 0 or not isinstance(raw_profile, dict):
                    continue
                mode = raw_profile.get("mode", DEFAULTS["artwork_mode"])
                if mode not in VALID_ARTWORK_MODES:
                    mode = DEFAULTS["artwork_mode"]
                source = raw_profile.get("source", DEFAULTS["artwork_source"])
                if source not in VALID_ARTWORK_SOURCES:
                    source = DEFAULTS["artwork_source"]
                try:
                    manual_y = max(0.15, min(0.90, float(raw_profile.get("manual_y", DEFAULTS["artwork_manual_y"]))))
                except (TypeError, ValueError):
                    manual_y = DEFAULTS["artwork_manual_y"]
                profiles[appid] = {"mode": mode, "manual_y": manual_y, "source": source}
        self._data["artwork_profiles"] = profiles

    def all(self):
        with self._lock:
            return dict(self._data)

    def update(self, changes: dict):
        with self._lock:
            if ((changes.get("weather_display") not in (None, "off") or changes.get("weather_topbar_enabled") is True)
                    and _valid_weather_location(changes.get("weather_location", self._data["weather_location"])) is None):
                raise ValueError("Choose a weather city before enabling weather")
            for key, value in changes.items():
                if key in DEFAULTS:
                    self._data[key] = value
            if changes.get("weather_display") in {"home", "game", "everywhere"}:
                self._data["controller_battery_display"] = "off"
            elif changes.get("controller_battery_display") in {"home", "game", "everywhere"}:
                self._data["weather_display"] = "off"
            self._validate()
            self.save()
            return dict(self._data)

    def replace_configuration(self, global_values: dict, display_profiles: dict,
                              artwork_profiles: dict):
        """Atomically replace saved choices; malformed imports leave them intact."""
        if not isinstance(global_values, dict) or not isinstance(display_profiles, dict) \
                or not isinstance(artwork_profiles, dict):
            raise ValueError("Configuration sections must be objects")
        unsupported = set(global_values) - set(DEFAULTS) - {"display_profiles", "artwork_profiles"}
        if unsupported or "display_profiles" in global_values or "artwork_profiles" in global_values:
            raise ValueError("Configuration contains unsupported settings")
        imported = deepcopy(global_values)
        imported["display_profiles"] = deepcopy(display_profiles)
        imported["artwork_profiles"] = deepcopy(artwork_profiles)
        with self._lock:
            previous = self._data
            try:
                self._data = deepcopy(DEFAULTS)
                self._data.update(imported)
                self._validate()
                # Reject invalid values rather than silently changing a user
                # selected import. Derived compatibility fields are expected
                # to be normalized from controller_charging_mode.
                derived = {"controller_charging_enabled", "controller_charging_display",
                           "weather_sequence_revision"}
                for key, value in imported.items():
                    if key not in derived and self._data[key] != value:
                        raise ValueError(f"Invalid configuration setting: {key}")
                self.save()
            except Exception:
                self._data = previous
                raise
            return dict(self._data)

    def reset_configuration(self):
        return self.replace_configuration({}, {}, {})

    def artwork_for(self, appid=0):
        with self._lock:
            appid = int(appid or 0)
            profile = self._data["artwork_profiles"].get(str(appid), {}) if appid > 0 else {}
            return {
                "mode": profile.get("mode", self._data["artwork_mode"]),
                "manual_y": profile.get("manual_y", self._data["artwork_manual_y"]),
                "source": profile.get("source", self._data["artwork_source"]),
                "custom": bool(profile),
            }

    def display_for(self, appid=0):
        with self._lock:
            override = self._data["display_profiles"].get(str(int(appid or 0)), "inherit")
            default = self._data["mode"]
            return {"default": default, "override": override,
                    "mode": default if default in {"disabled", "events"} or override == "inherit" else override}

    def update_display(self, appid, mode):
        appid = int(appid)
        if not 0 < appid <= 0xffffffff or not isinstance(mode, str) or mode not in {"inherit", "artwork", "performance"}:
            raise ValueError("A game AppID and Artwork, Performance or Inherit are required")
        with self._lock:
            profiles = dict(self._data["display_profiles"])
            if mode == "inherit":
                profiles.pop(str(appid), None)
            else:
                if str(appid) not in profiles and len(profiles) >= 512:
                    raise ValueError("Display profile limit reached (512)")
                profiles[str(appid)] = mode
            self._data["display_profiles"] = profiles
            self._validate()
            self.save()
            return self.display_for(appid)

    def update_artwork(self, appid, changes):
        with self._lock:
            appid = int(appid or 0)
            if appid <= 0:
                mapped = {}
                if "mode" in changes:
                    mapped["artwork_mode"] = changes["mode"]
                if "manual_y" in changes:
                    mapped["artwork_manual_y"] = changes["manual_y"]
                if "source" in changes:
                    mapped["artwork_source"] = changes["source"]
                return self.update(mapped)

            profiles = dict(self._data["artwork_profiles"])
            profile = dict(profiles.get(str(appid), self.artwork_for(0)))
            profile.pop("custom", None)
            if "mode" in changes:
                profile["mode"] = changes["mode"]
            if "manual_y" in changes:
                profile["manual_y"] = changes["manual_y"]
            if "source" in changes:
                profile["source"] = changes["source"]
            profiles[str(appid)] = profile
            self._data["artwork_profiles"] = profiles
            self._validate()
            self.save()
            return self.artwork_for(appid)

    def save(self):
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, self.path)
