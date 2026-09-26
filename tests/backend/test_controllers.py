from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from signalbar.arbiter import Arbiter
from signalbar.backend import Engine
from signalbar.models import GameState, ProviderOutput, normalize_frame
from signalbar.providers.controller import ControllerProvider, DURATIONS, VARIANTS, controller_frame
from signalbar.settings import SettingsStore


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def controller(percent=74, identifier="one", charging=False):
    return {"id": identifier, "name": identifier, "percent": percent, "level": None, "charging": charging}


class ControllerTests(unittest.TestCase):
    def test_engine_controller_events_reach_renderer_on_home_and_in_game(self):
        class Hardware:
            device_path = "/fake/valve-leds"
            reverse = False
            frame = normalize_frame([(0, 0, 40)] * 17)

            def set_reverse(self, reverse):
                self.reverse = bool(reverse)

            def read_frame(self):
                return self.frame

            def read_signature(self):
                return self.frame

            def write_frame(self, frame):
                self.frame = normalize_frame(frame)

            def try_restore(self, frame):
                self.write_frame(frame)

        with tempfile.TemporaryDirectory() as folder:
            settings = SettingsStore(str(Path(folder) / "settings.json"))
            hardware = Hardware()
            engine = Engine(settings, str(Path(folder) / "artwork.json"), hardware_factory=lambda: hardware)
            engine.start()
            try:
                for appid in (0, 42):
                    with self.subTest(appid=appid):
                        engine.set_game(appid, "Test" if appid else "")
                        engine.reset_controllers()
                        engine.update_controllers([], "SteamInputManager list")
                        engine.update_controllers([controller()], "SteamInputManager list")
                        deadline = time.monotonic() + 2
                        while time.monotonic() < deadline and engine.status()["provider"] != "controller:connect":
                            time.sleep(.01)
                        self.assertEqual(engine.status()["provider"], "controller:connect")
                        self.assertNotEqual(hardware.frame, normalize_frame([(0, 0, 40)] * 17))
                        engine.update_controllers([controller(10)], "SteamInputManager battery")
                        deadline = time.monotonic() + 2
                        while time.monotonic() < deadline and engine.status()["provider"] != "controller:low":
                            time.sleep(.01)
                        self.assertEqual(engine.status()["provider"], "controller:low")
                        engine.update_controllers([], "SteamInputManager disconnect")
                        self.assertEqual(engine.status()["controllers"]["controllers"], [])
                        self.assertFalse(engine.status()["controllers"]["active"])
                engine.report_controller_telemetry({"phase": "error", "error": "No transport", "hooks": 2,
                                                    "query_ms": float("nan")})
                telemetry = engine.status()["debug"]["controller_telemetry"]
                self.assertEqual(telemetry["phase"], "error")
                self.assertEqual(telemetry["hooks"], 2)
                self.assertIsNone(telemetry["query_ms"])
            finally:
                engine.stop()

    def test_critical_countdown_does_not_consume_pending_low_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = SettingsStore(str(Path(folder) / "settings.json"))
            engine = Engine(settings, str(Path(folder) / "artwork.json"))
            engine.start_free_timer(1)
            engine.update_controllers([controller(10)])
            self.assertFalse(engine.status()["controllers"]["active"])
            engine.countdown.stop("free")
            engine.update_controllers([controller(10)])
            self.assertEqual(engine.status()["controllers"]["kind"], "low")

    def test_zero_and_unknown_battery_never_crash_tip_style(self):
        for percent in (0, None):
            self.assertEqual(controller_frame("persistent", "tip", 1, percent),
                             normalize_frame([(0, 0, 0)] * 17))

    def test_already_connected_low_battery_warns_once_without_fake_connect(self):
        provider = ControllerProvider(clock=Clock())
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        self.assertEqual(provider.update([controller(10)], values), "low")
        provider.clear_transients()
        self.assertIsNone(provider.update([controller(9)], values))
        self.assertIsNone(provider.event_output().frame)

    def test_disabled_or_wrong_context_low_alert_is_not_consumed(self):
        for setting, disabled in (("controller_alerts_enabled", False),
                                  ("controller_alert_context", "game"),
                                  ("controller_low_enabled", False), ("mode", "disabled")):
            with self.subTest(setting=setting):
                provider = ControllerProvider(clock=Clock())
                values = SettingsStore("/nonexistent/signalbar-settings.json").all()
                original = values[setting]
                values[setting] = disabled
                provider.update([controller(30)], values)
                provider.update([controller(10)], values)
                self.assertIsNone(provider.event_output().frame)
                values[setting] = original
                self.assertEqual(provider.update([controller(9)], values), "low")

    def test_charge_can_become_known_and_live_animation_uses_latest_battery(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_charging_mode"] = "brief"
        values["controller_charging_enabled"] = True
        values["controller_charging_display"] = "off"
        provider.update([], values)
        provider.update([controller(None, charging=None)], values)
        clock.advance(2)
        provider.update([controller(75, charging=None)], values)
        self.assertTrue(any(pixel != (0, 0, 0) for pixel in provider.event_output().frame))
        self.assertEqual(provider.update([controller(75, charging=True)], values), "charging")

    def test_collector_lease_expires_and_recovers_without_ghost_connections(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "everywhere"
        provider.update([controller()], values)
        clock.advance(9)
        self.assertIsNotNone(provider.persistent_output(values).frame)
        provider.update([controller()], values)
        clock.advance(9)
        self.assertIsNotNone(provider.persistent_output(values).frame)
        clock.advance(2)
        self.assertIsNone(provider.persistent_output(values).frame)
        self.assertEqual(provider.status(values)["controllers"], [])
        self.assertIsNone(provider.update([controller()], values))
        self.assertIsNotNone(provider.persistent_output(values).frame)

    def test_fifteen_mockup_variants_render_bounded_frames(self):
        for kind, variants in VARIANTS.items():
            for variant in variants:
                with self.subTest(kind=kind, variant=variant):
                    for step in range(1, 12):
                        elapsed = DURATIONS.get(kind, 3) * step / 12
                        frame = controller_frame(kind, variant, elapsed, 74, 25, intro_age=elapsed)
                        self.assertEqual(len(frame), 17)
                        self.assertTrue(all(0 <= channel <= 255 for pixel in frame for channel in pixel))
                    if kind in {"connect", "low", "charging"}:
                        self.assertEqual(controller_frame(kind, variant, DURATIONS[kind]),
                                         normalize_frame([(0, 0, 0)] * 17))
                    if kind == "duo":
                        self.assertEqual(controller_frame(kind, variant, 2.5, 74, 25)[8], (0, 0, 0))

    def test_settings_persist_validate_and_default_to_home_gauge(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "settings.json")
            store = SettingsStore(path)
            self.assertEqual(store.all()["controller_battery_display"], "home")
            self.assertEqual(store.all()["controller_charging_mode"], "continuous-home")
            self.assertEqual(store.all()["controller_charging_display"], "home")
            self.assertEqual(store.all()["controller_alert_context"], "both")
            store.update({"controller_battery_display": "home", "controller_charging_mode": "continuous-home",
                          "controller_connect_variant": "orbit"})
            restored = SettingsStore(path)
            self.assertEqual(restored.all()["controller_connect_variant"], "orbit")
            self.assertEqual(restored.all()["controller_battery_display"], "home")
            self.assertEqual(restored.all()["controller_charging_mode"], "continuous-home")
            self.assertEqual(restored.all()["controller_charging_display"], "home")
            restored.update({"controller_connect_variant": "invalid", "controller_alert_context": [],
                             "controller_charging_mode": "invalid", "controller_low_threshold": 999})
            self.assertEqual(restored.all()["controller_connect_variant"], "welcome")
            self.assertEqual(restored.all()["controller_alert_context"], "both")
            self.assertEqual(restored.all()["controller_low_threshold"], 30)
            self.assertEqual(restored.all()["controller_charging_mode"], "continuous-home")
            self.assertEqual(restored.all()["controller_charging_display"], "home")

    def test_charging_choices_are_exclusive_and_old_settings_migrate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "settings.json")
            store = SettingsStore(path)
            for mode, display, brief in (
                ("off", "off", False), ("brief", "off", True),
                ("continuous-home", "home", False),
                ("continuous-everywhere", "everywhere", False),
            ):
                with self.subTest(mode=mode):
                    store.update({"controller_charging_mode": mode})
                    restored = SettingsStore(path).all()
                    self.assertEqual(restored["controller_charging_mode"], mode)
                    self.assertEqual(restored["controller_charging_display"], display)
                    self.assertEqual(restored["controller_charging_enabled"], brief)
            for legacy, mode in (
                ({"controller_charging_display": "everywhere", "controller_charging_enabled": True}, "continuous-everywhere"),
                ({"controller_charging_display": "home", "controller_charging_enabled": False}, "continuous-home"),
                ({"controller_charging_display": "off", "controller_charging_enabled": True}, "brief"),
                ({"controller_charging_display": "off", "controller_charging_enabled": False}, "off"),
                ({"controller_charging_enabled": True}, "brief"),
                ({"controller_charging_enabled": False}, "off"),
            ):
                with self.subTest(legacy=legacy):
                    Path(path).write_text(json.dumps(legacy), encoding="utf-8")
                    self.assertEqual(SettingsStore(path).all()["controller_charging_mode"], mode)

    def test_brief_charging_plays_once_and_continuous_charging_does_not_play_brief(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        with tempfile.TemporaryDirectory() as folder:
            store = SettingsStore(str(Path(folder) / "settings.json"))
            brief = store.update({"controller_charging_mode": "brief", "controller_battery_display": "off"})
            provider.update([controller(41)], brief)
            self.assertEqual(provider.update([controller(41, charging=True)], brief), "charging")
            self.assertEqual(provider.event_output().provider, "controller:charging")
            self.assertIsNone(provider.persistent_output(brief).frame)
            base = ProviderOutput("artwork", normalize_frame([(10, 20, 30)] * 17), "")
            kwargs = dict(mode="artwork", guard_allows=True, game=GameState(appid=42),
                          performance=base, artwork=base, idle=ProviderOutput("idle", None, ""),
                          signal=ProviderOutput("countdown", None, ""),
                          controller_base=provider.persistent_output(brief))
            self.assertEqual(Arbiter().choose(**{**kwargs, "controller_event": provider.event_output()}).provider,
                             "controller:charging")
            clock.advance(DURATIONS["charging"] + .1)
            self.assertIsNone(provider.event_output().frame)
            self.assertIsNone(provider.persistent_output(brief).frame)
            self.assertEqual(Arbiter().choose(**{**kwargs, "controller_event": provider.event_output()}).provider,
                             "artwork")
            continuous = store.update({"controller_charging_mode": "continuous-everywhere"})
            self.assertEqual(provider.persistent_output(continuous).provider, "controller-charging")
            provider.update([controller(41, charging=False)], continuous)
            self.assertIsNone(provider.update([controller(41, charging=True)], continuous))
            self.assertIsNone(provider.event_output().frame)
            self.assertEqual(provider.persistent_output(continuous).provider, "controller-charging")
            off = store.update({"controller_charging_mode": "off"})
            self.assertIsNone(provider.persistent_output(off).frame)

    def test_brief_charging_needs_known_level_and_allowed_alert_context(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values.update(controller_charging_mode="brief", controller_charging_display="off",
                      controller_charging_enabled=True, controller_alert_context="home")
        provider.update([controller(None)], values, game_running=False)
        self.assertIsNone(provider.update([controller(None, charging=True)], values, game_running=False))
        self.assertIsNone(provider.event_output().frame)
        provider.update([controller(41, charging=False)], values, game_running=True)
        self.assertIsNone(provider.update([controller(41, charging=True)], values, game_running=True))
        self.assertIsNone(provider.event_output().frame)
        provider.update([controller(41, charging=False)], values, game_running=False)
        self.assertEqual(provider.update([controller(41, charging=True)], values, game_running=False), "charging")

    def test_alerts_do_not_require_persistent_gauge_and_context_is_enforced(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "off"
        provider.update([], values, False)
        provider.update([controller()], values, False)
        self.assertEqual(provider.event_output().provider, "controller:connect")
        self.assertIsNone(provider.persistent_output(values, False).frame)
        provider.clear_transients()
        provider.update([], values, False)
        values["controller_alert_context"] = "game"
        provider.update([controller(identifier="two")], values, False)
        self.assertIsNone(provider.event_output().frame)
        provider.update([], values, True)
        provider.update([controller(identifier="three")], values, True)
        self.assertEqual(provider.event_output().provider, "controller:connect")
        values["controller_alert_context"] = "home"
        provider.cancel_for_settings(values, game_running=True)
        self.assertIsNone(provider.event_output().frame)

    def test_low_battery_fires_once_on_crossing_and_rearms_after_recharge(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        provider.update([controller(30)], values)
        provider.update([controller(19)], values)
        self.assertEqual(provider.event_output().provider, "controller:low")
        provider.clear_transients()
        provider.update([controller(18)], values)
        self.assertIsNone(provider.event_output().frame)
        provider.update([controller(26)], values)
        provider.update([controller(20)], values)
        self.assertEqual(provider.event_output().provider, "controller:low")
        provider.clear_transients()
        provider.update([controller(None)], values)
        self.assertIsNone(provider.event_output().frame)

    def test_home_gauge_replaces_base_but_never_countdown_or_critical_warning(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        provider.update([controller()], values)
        values["controller_battery_display"] = "home"
        gauge = provider.persistent_output(values, False)
        self.assertEqual(gauge.provider, "controller-battery")
        self.assertIsNotNone(gauge.frame)
        self.assertIsNone(provider.persistent_output(values, True).frame)
        arbiter = Arbiter()
        base = ProviderOutput("performance", normalize_frame([(10, 20, 30)] * 17), "")
        timer = ProviderOutput("countdown", normalize_frame([(30, 20, 10)] * 17), "")
        kwargs = dict(mode="performance", guard_allows=True, game=GameState(),
                      performance=base, artwork=base, idle=ProviderOutput("idle", None, ""),
                      signal=ProviderOutput("countdown", None, ""), controller_base=gauge)
        self.assertEqual(arbiter.choose(**kwargs).provider, "controller-battery")
        self.assertEqual(arbiter.choose(**{**kwargs, "signal": timer}).provider, "countdown")
        self.assertEqual(arbiter.choose(**{**kwargs, "signal": timer, "signal_critical": True}).provider,
                         "countdown")
        self.assertEqual(arbiter.choose(**{**kwargs, "mode": "disabled"}).provider, "none")

    def test_signals_only_keeps_controller_status_and_alerts_without_ambient_base(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["mode"] = "events"
        values["controller_battery_display"] = "everywhere"
        provider.update([], values)
        provider.update([controller(74)], values)
        gauge = provider.persistent_output(values, False)
        alert = provider.event_output()
        ambient = ProviderOutput("artwork", normalize_frame([(10, 20, 30)] * 17), "")
        weather = ProviderOutput("weather", normalize_frame([(4, 5, 6)] * 17), "")
        empty = ProviderOutput("none", None, "")
        kwargs = dict(mode="events", guard_allows=True, game=GameState(),
                      performance=ambient, artwork=ambient, idle=ambient,
                      signal=empty, event=empty, weather_base=weather,
                      controller_base=gauge)
        self.assertEqual(Arbiter().choose(**{**kwargs, "controller_event": alert}).provider,
                         "controller:connect")
        provider.clear_transients()
        self.assertEqual(Arbiter().choose(
            **{**kwargs, "controller_event": provider.event_output()}).provider,
            "controller-battery")
        self.assertEqual(Arbiter().choose(
            **{**kwargs, "controller_event": provider.event_output(), "controller_base": empty}).provider,
            "none")

    def test_signals_only_accepts_controller_alerts_and_disabled_cancels_them(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = SettingsStore(str(Path(folder) / "settings.json"))
            engine = Engine(settings, str(Path(folder) / "artwork.json"))
            engine.update_settings({"mode": "events"})
            engine.update_controllers([], "baseline")
            engine.update_controllers([controller(74)], "connected")
            self.assertTrue(engine.status()["controllers"]["active"])
            engine.update_settings({"mode": "disabled"})
            self.assertFalse(engine.status()["controllers"]["active"])

    def test_two_controller_gauge_has_dark_centre_and_unknown_is_not_fake_percent(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "everywhere"
        provider.update([controller(74), controller(25, "two")], values)
        clock.advance(2)
        frame = provider.persistent_output(values, True).frame
        self.assertEqual(frame[8], (0, 0, 0))
        self.assertGreater(sum(pixel != (0, 0, 0) for pixel in frame[:8]),
                           sum(pixel != (0, 0, 0) for pixel in frame[9:]))
        provider.update([controller(None)], values)
        self.assertIsNone(provider.persistent_output(values, True).frame)

    def test_duo_intro_delays_white_tips_and_settles_as_mirrored_gauges(self):
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        brightness = values["controller_gauge_brightness"] / 100
        white = tuple(round(channel * brightness) for channel in (246, 249, 255))
        for variant, finish_at in (("twin", 1.45), ("focus", 3.3), ("double-welcome", 3.4)):
            with self.subTest(variant=variant):
                before = controller_frame("duo", variant, finish_at - .01, 96, 41,
                                          intro_age=finish_at - .01, values=values)
                after = controller_frame("duo", variant, finish_at + .01, 96, 41,
                                         intro_age=finish_at + .01, values=values)
                self.assertEqual(before[8], (0, 0, 0))
                self.assertNotEqual(before[7], white)
                self.assertNotEqual(before[14], white)
                self.assertEqual(after[8], (0, 0, 0))
                self.assertEqual(after[7], white)
                self.assertEqual(after[14], white)
                self.assertEqual(after[16], tuple(round(channel * brightness) for channel in values["controller_colour_normal"]))

    def test_duo_moving_points_are_white_and_final_white_tips_remain_visible(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_duo_variant"] = "focus"
        brightness = values["controller_gauge_brightness"] / 100
        white = tuple(round(channel * brightness) for channel in (246, 249, 255))
        provider.update([controller(96)], values)
        provider.update([controller(96), controller(41, "two")], values)
        clock.advance(.6)
        left_intro = provider.event_output().frame
        self.assertIn(white, left_intro[:8])
        self.assertNotEqual(left_intro[7], white)
        clock.advance(1.6)
        right_intro = provider.event_output().frame
        self.assertIn(white, right_intro[9:])
        self.assertNotEqual(right_intro[14], white)
        clock.advance(2.4)
        settled = provider.event_output().frame
        self.assertEqual(settled[7], white)
        self.assertEqual(settled[14], white)
        clock.advance(1.2)
        self.assertEqual(provider.event_output().frame, settled)
        clock.advance(.3)
        self.assertIsNone(provider.event_output().frame)

    def test_steam_list_reordering_does_not_swap_controller_sides(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "everywhere"
        provider.update([controller(96), controller(41, "two")], values)
        clock.advance(4)
        before = provider.persistent_output(values).frame
        provider.update([controller(41, "two"), controller(96)], values)
        after = provider.persistent_output(values).frame
        self.assertEqual(before, after)
        self.assertEqual(after[8], (0, 0, 0))

    def test_charging_continues_without_gauge_and_stops_at_full_charge(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_alerts_enabled"] = False
        values["controller_battery_display"] = "off"
        values["controller_charging_mode"] = "continuous-everywhere"
        values["controller_charging_display"] = "everywhere"
        provider.update([controller(41, charging=True)], values)
        first = provider.persistent_output(values, True)
        self.assertEqual(first.provider, "controller-charging")
        clock.advance(1)
        second = provider.persistent_output(values, True)
        self.assertNotEqual(first.frame, second.frame)
        clock.advance(4)
        self.assertEqual(provider.persistent_output(values, True).provider, "controller-charging")
        provider.update([controller(100, charging=True)], values)
        self.assertEqual(provider.persistent_output(values, True).provider, "controller-charge-complete")
        clock.advance(1)
        self.assertIsNone(provider.persistent_output(values, True).frame)
        values["controller_charging_display"] = "off"
        provider.update([controller(41, charging=True)], values)
        self.assertIsNone(provider.persistent_output(values, True).frame)

    def test_charging_context_and_two_controller_centre(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "off"
        values["controller_charging_display"] = "home"
        provider.update([controller(96), controller(41, "two", True)], values)
        clock.advance(2)
        self.assertIsNone(provider.persistent_output(values, True).frame)
        frame = provider.persistent_output(values, False).frame
        self.assertEqual(frame[8], (0, 0, 0))
        self.assertEqual(provider.persistent_output(values, False).provider, "controller-charging")
        provider.update([controller(96), controller(41, "two", False)], values)
        self.assertIsNone(provider.persistent_output(values, False).frame)

    def test_duo_charging_side_is_blue_white_without_recolouring_other_controller(self):
        for style in ("current", "breath", "spark"):
            for side in ("left", "right", "both"):
                with self.subTest(style=style, side=side):
                    clock = Clock()
                    provider = ControllerProvider(clock=clock)
                    values = SettingsStore("/nonexistent/signalbar-settings.json").all()
                    values["controller_charging_variant"] = style
                    values["controller_colour_charging"] = [23, 93, 180]
                    left_charging = side in ("left", "both")
                    right_charging = side in ("right", "both")
                    provider.update([controller(41, charging=left_charging),
                                     controller(96, "two", charging=right_charging)], values)
                    clock.advance(4)
                    output = provider.persistent_output(values)
                    self.assertEqual(output.provider, "controller-charging")
                    frame = output.frame
                    brightness = values["controller_gauge_brightness"] / 100
                    blue = tuple(round(channel * brightness) for channel in values["controller_colour_charging"])
                    white = tuple(round(channel * brightness) for channel in (246, 249, 255))
                    normal = tuple(round(channel * brightness) for channel in values["controller_colour_normal"])
                    self.assertEqual(frame[8], (0, 0, 0))
                    for pixels, is_charging in ((frame[:8], left_charging), (frame[9:], right_charging)):
                        lit = [pixel for pixel in pixels if pixel != (0, 0, 0)]
                        self.assertTrue(lit)
                        if is_charging:
                            self.assertTrue(all(pixel in (blue, white) for pixel in lit))
                            self.assertIn(blue, lit)
                            self.assertNotIn(normal, lit)
                        else:
                            self.assertIn(normal, lit)

    def test_second_controller_intro_keeps_charging_half_blue(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_duo_variant"] = "focus"
        provider.update([controller(96)], values)
        provider.update([controller(96), controller(41, "two", True)], values)
        clock.advance(4)
        output = provider.event_output()
        self.assertEqual(output.provider, "controller:duo")
        frame = output.frame
        brightness = values["controller_gauge_brightness"] / 100
        blue = tuple(round(channel * brightness) for channel in values["controller_colour_charging"])
        white = tuple(round(channel * brightness) for channel in (246, 249, 255))
        normal = tuple(round(channel * brightness) for channel in values["controller_colour_normal"])
        self.assertEqual(frame[8], (0, 0, 0))
        self.assertIn(normal, frame[:8])
        self.assertIn(blue, frame[9:])
        self.assertEqual(frame[14], white)
        self.assertNotIn(normal, frame[9:])

    def test_full_charge_interrupts_brief_charging_intro_and_restores_base(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "off"
        values["controller_charging_mode"] = "brief"
        values["controller_charging_enabled"] = True
        values["controller_charging_display"] = "off"
        provider.update([controller(41)], values)
        self.assertEqual(provider.update([controller(41, charging=True)], values), "charging")
        self.assertEqual(provider.event_output().provider, "controller:charging")
        provider.update([controller(100, charging=False)], values)
        self.assertIsNone(provider.event_output().frame)
        self.assertIsNone(provider.persistent_output(values).frame)

    def test_ongoing_charge_yields_to_countdown_and_native_owner(self):
        clock = Clock()
        provider = ControllerProvider(clock=clock)
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        provider.update([controller(41, charging=True)], values)
        charge = provider.persistent_output(values)
        base = ProviderOutput("artwork", normalize_frame([(10, 20, 30)] * 17), "")
        timer = ProviderOutput("countdown", normalize_frame([(30, 20, 10)] * 17), "")
        kwargs = dict(mode="artwork", guard_allows=True, game=GameState(),
                      performance=base, artwork=base, idle=ProviderOutput("idle", None, ""),
                      signal=ProviderOutput("countdown", None, ""), controller_base=charge)
        arbiter = Arbiter()
        self.assertEqual(arbiter.choose(**kwargs).provider, "controller-charging")
        self.assertEqual(arbiter.choose(**{**kwargs, "signal": timer}).provider, "countdown")
        self.assertNotEqual(arbiter.choose(**{**kwargs, "guard_allows": False}).provider, "controller-charging")

    def test_second_connection_uses_selected_duo_alert(self):
        provider = ControllerProvider(clock=Clock())
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_duo_variant"] = "double-welcome"
        provider.update([controller()], values)
        provider.update([controller(), controller(25, "two")], values)
        active = provider.status(values)
        self.assertEqual(active["kind"], "duo")
        self.assertEqual(active["variant"], "double-welcome")
        self.assertEqual(active["colors"][8], [0, 0, 0])

    def test_coarse_battery_level_can_render_and_warn_without_claiming_percent(self):
        provider = ControllerProvider(clock=Clock())
        values = SettingsStore("/nonexistent/signalbar-settings.json").all()
        values["controller_battery_display"] = "everywhere"
        first = {**controller(None), "level": 2}
        provider.update([first], values)
        self.assertEqual(provider.status(values)["controllers"][0]["percent"], None)
        self.assertIsNotNone(provider.persistent_output(values).frame)
        provider.update([{**first, "level": 1}], values)
        self.assertEqual(provider.event_output().provider, "controller:low")


if __name__ == "__main__":
    unittest.main()
