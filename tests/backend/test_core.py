from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signalbar.arbiter import Arbiter
from signalbar.arbiter.guard import ManualClock, VanillaGuard
from signalbar.backend import Engine
from signalbar.hardware import ValveLedHardware
from signalbar.models import GameState, PerformanceSample, ProviderOutput, normalize_frame
from signalbar.providers import (
    ArtworkProvider,
    CountdownProvider,
    PerformanceProvider,
    countdown_final_alert_frame,
    countdown_frame,
    mixed_performance_frame,
    performance_frame,
    temperature_color,
)
from signalbar.renderer import Renderer
from signalbar.settings import SettingsStore
from signalbar.steam import find_library_artwork, get_library_artwork


BLACK = normalize_frame([(0, 0, 0)] * 17)
RED = normalize_frame([(255, 0, 0)] * 17)
BLUE = normalize_frame([(0, 0, 255)] * 17)


class FakeHardware:
    device_path = "/fake/valve-leds"

    def __init__(self):
        self.frame = BLACK
        self.write_calls = []

    def read_frame(self):
        return self.frame

    def read_signature(self):
        return tuple((f"{r} {g} {b}", "255") for r, g, b in self.frame)

    def write_frame(self, frame):
        self.frame = normalize_frame(frame)
        self.write_calls.append(self.frame)

    def try_restore(self, frame):
        self.write_frame(frame)


class CoreTests(unittest.TestCase):
    def test_stripmine_priority_maps_every_configurable_provider_family(self):
        values = {
            "stripmine_priority_artwork": "stripmine",
            "stripmine_priority_performance": "signalbar",
            "stripmine_priority_weather": "stripmine",
            "stripmine_priority_controller": "signalbar",
            "stripmine_priority_light_events": "signalbar",
        }
        self.assertEqual(Engine._stripmine_priority("artwork:hero", values), "stripmine")
        self.assertEqual(Engine._stripmine_priority("performance", values), "signalbar")
        self.assertEqual(Engine._stripmine_priority("weather:cloud", values), "stripmine")
        self.assertEqual(Engine._stripmine_priority("controller:persistent", values), "signalbar")
        self.assertEqual(Engine._stripmine_priority("event:achievement", values), "signalbar")
        self.assertEqual(Engine._stripmine_priority("countdown", values), "signalbar")
        self.assertEqual(Engine._stripmine_priority("none", values), "stripmine")
        self.assertEqual(Engine._stripmine_priority("valve", values), "stripmine")

    def test_performance_mapping_zero_to_seventeen(self):
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in performance_frame(0, 60)), 0)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in performance_frame(70, 60)), 12)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in performance_frame(100, 60)), 17)

        compensated = performance_frame(
            70, 60, dark_edge_compensation=3,
        )
        compensated_full = performance_frame(
            100, 60, dark_edge_compensation=3,
        )
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in compensated), 9)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in compensated_full), 14)

        barely_visible = performance_frame(
            6, 60, dark_edge_compensation=3,
        )
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in barely_visible), 1)

    def test_mixed_performance_uses_eight_plus_separator_plus_eight(self):
        sample = PerformanceSample(
            gpu_load=50, gpu_temp_c=70, cpu_load=25, cpu_temp_c=60, sampled_at=1,
        )
        frame = mixed_performance_frame(sample)
        self.assertEqual(len(frame), 17)
        self.assertEqual(frame[8], (0, 0, 0))
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in frame[:8]), 2)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in frame[9:]), 4)
        self.assertNotEqual(frame[0], (0, 0, 0))
        self.assertNotEqual(frame[-1], (0, 0, 0))

        same_direction = mixed_performance_frame(sample, direction="same")
        self.assertNotEqual(same_direction[9], (0, 0, 0))
        self.assertEqual(same_direction[-1], (0, 0, 0))

        compensated = mixed_performance_frame(
            sample, direction="mirrored", dark_edge_compensation=3,
        )
        self.assertEqual(compensated[8], (0, 0, 0))
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in compensated), 3)
        self.assertNotEqual(compensated[0], (0, 0, 0))
        self.assertNotEqual(compensated[-1], (0, 0, 0))

    def test_performance_provider_applies_physical_compensation_only_to_output(self):
        provider = PerformanceProvider(clock=ManualClock(1))
        provider._last = PerformanceSample(
            gpu_load=70, gpu_temp_c=60, cpu_load=50, cpu_temp_c=60,
            sampled_at=1,
        )
        provider._next_sample_at = float("inf")

        logical = provider.frame(metric="gpu", dark_edge_compensation=0)
        physical = provider.output(
            metric="gpu", dark_edge_compensation=3,
        ).frame
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in logical), 12)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in physical), 9)

    def test_balanced_performance_smoothing_limits_jumps_and_confirms_falls(self):
        class SequenceMetrics:
            def __init__(self, loads):
                self.loads = iter(loads)

            def sample(self):
                load = next(self.loads)
                return PerformanceSample(
                    gpu_load=load, gpu_temp_c=60,
                    cpu_load=load, cpu_temp_c=60,
                    sampled_at=1,
                )

        clock = ManualClock(0)
        provider = PerformanceProvider(
            metrics=SequenceMetrics([20, 90, 90, 10, 10]),
            clock=clock,
        )

        provider.output(metric="gpu", smoothing="balanced")
        self.assertEqual(provider.sample.gpu_load, 20)
        clock.advance(0.5)
        provider.output(metric="gpu", smoothing="balanced")
        self.assertEqual(provider.sample.gpu_load, 32.5)
        clock.advance(0.5)
        provider.output(metric="gpu", smoothing="balanced")
        self.assertEqual(provider.sample.gpu_load, 45.0)

        # One low sample is ignored; a confirmed fall then decays gradually.
        clock.advance(0.5)
        provider.output(metric="gpu", smoothing="balanced")
        self.assertEqual(provider.sample.gpu_load, 45.0)
        clock.advance(0.5)
        provider.output(metric="gpu", smoothing="balanced")
        self.assertEqual(provider.sample.gpu_load, 38.0)
        self.assertEqual(provider.sample.cpu_load, 38.0)

    def test_responsive_performance_smoothing_accepts_a_fall_immediately(self):
        class SequenceMetrics:
            def __init__(self):
                self.loads = iter([80, 20])

            def sample(self):
                load = next(self.loads)
                return PerformanceSample(
                    gpu_load=load, gpu_temp_c=60, sampled_at=1,
                )

        clock = ManualClock(0)
        provider = PerformanceProvider(metrics=SequenceMetrics(), clock=clock)
        provider.output(metric="gpu", smoothing="responsive")
        clock.advance(0.5)
        provider.output(metric="gpu", smoothing="responsive")
        self.assertLess(provider.sample.gpu_load, 80)

    def test_temperature_thresholds_and_palette_are_explicit(self):
        self.assertEqual(temperature_color(50, 50, 90, "classic"), (35, 205, 95))
        self.assertEqual(temperature_color(90, 50, 90, "classic"), (235, 45, 55))
        custom = ((12, 34, 56), (78, 90, 123), (210, 220, 230))
        self.assertEqual(temperature_color(50, 50, 90, "custom", custom), custom[0])
        self.assertEqual(temperature_color(90, 50, 90, "custom", custom), custom[2])

    def test_countdown_shrinks_and_comet_moves_right_to_left(self):
        first = countdown_frame(50, 100, "cyan", elapsed_seconds=0)
        second = countdown_frame(50, 100, "cyan", elapsed_seconds=0.2)
        smaller = countdown_frame(40, 100, "cyan", elapsed_seconds=0)

        brightest_first = max(range(17), key=lambda index: sum(first[index]))
        brightest_second = max(range(17), key=lambda index: sum(second[index]))
        self.assertEqual(brightest_first, 5)
        self.assertEqual(brightest_second, 4)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in first), 6)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in smaller), 4)
        self.assertTrue(all(pixel == (0, 0, 0) for pixel in smaller[4:]))

        full = countdown_frame(100, 100, "cyan", elapsed_seconds=0)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in full), 17)
        four_nominally_empty = countdown_frame(13, 17, "cyan", elapsed_seconds=0)
        self.assertEqual(
            sum(pixel == (0, 0, 0) for pixel in four_nominally_empty),
            7,
        )

        logical_twelve = countdown_frame(
            12, 17, "cyan", elapsed_seconds=0, dark_edge_compensation=0,
        )
        physical_ten = countdown_frame(
            12, 17, "cyan", elapsed_seconds=0, dark_edge_compensation=2,
        )
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in logical_twelve), 12)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in physical_ten), 10)

    def test_countdown_preview_stays_logical_while_output_is_compensated(self):
        clock = ManualClock(100)
        provider = CountdownProvider(clock=clock)
        provider.start("free", 12, total_seconds=17, label="Free timer")

        status = provider.status(dark_edge_compensation=2)
        output = provider.output(dark_edge_compensation=2)
        self.assertEqual(status["logical_lit"], 12)
        self.assertEqual(status["physical_lit"], 10)
        self.assertEqual(sum(pixel != [0, 0, 0] for pixel in status["colors"]), 12)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in output.frame), 10)

    def test_countdown_can_use_a_fixed_full_bar_time_scale(self):
        clock = ManualClock(100)
        provider = CountdownProvider(clock=clock)
        provider.start("free", 7200, total_seconds=7200, label="Free timer")

        full = provider.status(full_bar_seconds=3600, dark_edge_compensation=0)
        self.assertEqual(full["scale_seconds"], 3600)
        self.assertEqual(full["logical_lit"], 17)

        clock.advance(5400)
        half = provider.status(full_bar_seconds=3600, dark_edge_compensation=0)
        self.assertEqual(half["remaining_seconds"], 1800)
        self.assertEqual(half["logical_lit"], 9)

        provider.start("preview", 15, total_seconds=15, label="Preview")
        preview = provider.status(full_bar_seconds=14400)
        self.assertEqual(preview["scale_seconds"], 15)
        self.assertEqual(preview["logical_lit"], 17)

    def test_countdown_keeps_constant_red_brightness_during_last_five_minutes(self):
        first = countdown_frame(240, 3600, "violet", elapsed_seconds=0)
        later = countdown_frame(240, 3600, "violet", elapsed_seconds=1.6)
        self.assertEqual(first, later)
        self.assertEqual(max(first, key=sum), (255, 0, 0))

    def test_countdown_changes_to_amber_then_red_without_pulsing(self):
        normal = countdown_frame(1000, 1800, "violet", elapsed_seconds=0)
        warning = countdown_frame(600, 1800, "violet", elapsed_seconds=0)
        urgent = countdown_frame(240, 1800, "violet", elapsed_seconds=0)

        self.assertEqual(max(normal, key=sum), (165, 85, 235))
        self.assertEqual(max(warning, key=sum), (245, 165, 35))
        self.assertEqual(max(urgent, key=sum), (255, 0, 0))
        self.assertTrue(all(pixel[1:] == (0, 0) for pixel in urgent))

        final_minute_first = countdown_frame(45, 1800, "violet", elapsed_seconds=0)
        final_minute_later = countdown_frame(45, 1800, "violet", elapsed_seconds=0.8)
        self.assertEqual(final_minute_first, final_minute_later)

    def test_countdown_provider_keeps_independent_deadlines(self):
        clock = ManualClock(100)
        provider = CountdownProvider(clock=clock)
        provider.start("free", 300, label="Free timer")
        provider.start("parental", 1800, label="Steam Families")
        self.assertEqual(provider.status()["source"], "parental")

        provider.start("preview", 15, label="Preview")
        self.assertEqual(provider.status()["source"], "preview")
        clock.advance(16)
        self.assertEqual(provider.status()["source"], "parental")
        clock.advance(1777)
        self.assertTrue(provider.status()["alerting"])
        self.assertFalse(provider.status(allow_parental=False)["active"])

    def test_countdown_final_eight_seconds_repeat_three_white_flashes_then_stop(self):
        white = normalize_frame([(255, 255, 255)] * 17)
        self.assertEqual(countdown_final_alert_frame(0.00), white)
        self.assertEqual(countdown_final_alert_frame(0.16), BLACK)
        self.assertEqual(countdown_final_alert_frame(0.30), white)
        self.assertEqual(countdown_final_alert_frame(0.46), BLACK)
        self.assertEqual(countdown_final_alert_frame(0.60), white)
        self.assertEqual(countdown_final_alert_frame(0.76), BLACK)
        self.assertEqual(countdown_final_alert_frame(1.80), white)

        clock = ManualClock(100)
        provider = CountdownProvider(clock=clock)
        provider.start("free", 10, label="Free timer")
        self.assertFalse(provider.status()["alerting"])
        clock.advance(2)
        self.assertTrue(provider.status()["alerting"])
        self.assertTrue(provider.status()["active"])
        clock.advance(7.9)
        self.assertTrue(provider.status()["active"])
        clock.advance(0.2)
        self.assertFalse(provider.status()["active"])

    def test_renderer_coalesces_and_rate_limits(self):
        clock = ManualClock(100)
        hardware = FakeHardware()
        renderer = Renderer(hardware, min_interval_s=0.05, clock=clock)
        self.assertTrue(renderer.render(RED))
        self.assertFalse(renderer.render(RED))
        self.assertFalse(renderer.render(BLUE))
        self.assertEqual(len(hardware.write_calls), 1)
        clock.advance(0.051)
        self.assertTrue(renderer.render(BLUE))
        self.assertEqual(len(hardware.write_calls), 2)

    def test_renderer_restores_only_while_still_owner(self):
        clock = ManualClock(100)
        hardware = FakeHardware()
        renderer = Renderer(hardware, clock=clock)
        renderer.render(RED)
        self.assertTrue(renderer.relinquish(True))
        self.assertEqual(hardware.frame, BLACK)

        renderer.render(RED)
        last_successful_write = renderer.last_successful_write_at
        hardware.frame = BLUE  # Valve/external actor changed the bar.
        self.assertFalse(renderer.relinquish(True))
        self.assertEqual(hardware.frame, BLUE)
        self.assertEqual(renderer.last_successful_write_at, last_successful_write)

    def test_guard_external_takeover_and_cooldown(self):
        clock = ManualClock()
        guard = VanillaGuard(cooldown_s=5, stable_s=2, clock=clock)
        guard.observe("native-a")
        self.assertFalse(guard.debug_status()["ready"])
        self.assertEqual(guard.debug_status()["stable_remaining"], 2)
        clock.advance(2.1)
        self.assertTrue(guard.observe("native-a"))
        self.assertTrue(guard.debug_status()["ready"])
        self.assertFalse(guard.observe("native-b", expected_signature="signalbar"))
        self.assertEqual(guard.reason, "external LED change detected")
        self.assertGreater(guard.debug_status()["cooldown_remaining"], 0)
        clock.advance(4.9)
        self.assertFalse(guard.observe("native-b"))
        clock.advance(0.2)
        self.assertTrue(guard.observe("native-b"))

    def test_arbiter_transitions(self):
        arbiter = Arbiter()
        game = GameState(10, "Test")
        performance = ProviderOutput("performance", RED, "metrics")
        artwork = ProviderOutput("artwork", BLUE, "hero")
        idle = ProviderOutput("idle", None, "Vanilla")
        self.assertEqual(arbiter.choose(mode="artwork", guard_allows=False, game=game, performance=performance, artwork=artwork, idle=idle).provider, "valve")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True, game=game, performance=performance, artwork=artwork, idle=idle).provider, "performance")
        no_game = GameState()
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True, game=no_game, performance=performance, artwork=artwork, idle=idle).provider, "none")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True, game=no_game, performance=performance, artwork=artwork, idle=idle, performance_always=True).provider, "performance")
        self.assertEqual(arbiter.choose(mode="artwork", guard_allows=True, game=game, performance=performance, artwork=artwork, idle=idle, signal=ProviderOutput("countdown", RED, "timer")).provider, "countdown")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True, game=game, performance=performance, artwork=artwork, idle=idle, signal=ProviderOutput("countdown", RED, "timer")).provider, "countdown")
        self.assertEqual(arbiter.choose(mode="disabled", guard_allows=True, game=game, performance=performance, artwork=artwork, idle=idle, signal=ProviderOutput("countdown", RED, "timer")).provider, "none")
        unavailable = ProviderOutput("performance", None, "missing")
        self.assertEqual(arbiter.choose(mode="artwork", guard_allows=True, game=game, performance=unavailable, artwork=artwork, idle=idle).provider, "artwork")
        self.assertIsNone(arbiter.choose(mode="disabled", guard_allows=True, game=game, performance=performance, artwork=artwork, idle=idle).frame)


class PersistenceTests(unittest.TestCase):
    def test_fresh_install_defaults_match_approved_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "config.json")
            store = SettingsStore(path)
            expected = {
                "mode": "performance", "performance_metric": "mixed",
                "performance_smoothing": "responsive", "performance_always": True,
                "mixed_direction": "mirrored", "temperature_palette": "classic",
                "cool_temp_c": 45.0, "hot_temp_c": 78.0,
                "artwork_source": "hero", "artwork_mode": "auto", "artwork_manual_y": .34,
                "parental_countdown_enabled": True, "countdown_colour": "white",
                "countdown_full_bar_minutes": 0, "free_timer_minutes": 60,
                "events_enabled": True, "event_notifications_enabled": True,
                "event_achievements_enabled": True, "event_screenshots_enabled": True,
                "event_recording_enabled": True, "recording_marker_isolation": True,
                "event_notification_variant": "notification-beacon",
                "event_achievement_variant": "achievement-constellation",
                "event_screenshot_variant": "screenshot-bloom",
                "controller_battery_display": "home", "controller_alerts_enabled": True,
                "controller_alert_context": "both", "controller_charging_mode": "continuous-home",
                "controller_low_threshold": 20, "controller_connect_enabled": True,
                "controller_low_enabled": True, "controller_connect_variant": "welcome",
                "controller_persistent_variant": "tip", "controller_low_variant": "beacon",
                "controller_charging_variant": "breath", "controller_duo_variant": "double-welcome",
                "controller_gauge_brightness": 65,
                "reverse_led_order": True, "countdown_dark_edge_compensation": 2,
                "weather_topbar_enabled": False, "weather_temperature_unit": "celsius",
                "weather_brightness": 100, "weather_shadow_cutoff": 0,
                "weather_cloud_variant": 3, "weather_snow_variant": 1,
            }
            for key, value in expected.items():
                self.assertEqual(store.all()[key], value, key)
            for key, color in {
                "temperature_custom_cool": [30, 180, 230],
                "temperature_custom_middle": [245, 180, 45],
                "temperature_custom_hot": [235, 45, 55],
                "controller_colour_normal": [0, 180, 45],
                "controller_colour_medium": [230, 110, 0],
                "controller_colour_low": [220, 12, 24],
                "controller_colour_charging": [0, 145, 220],
            }.items():
                self.assertEqual(store.all()[key], color, key)
            store.update({"mode": "artwork", "controller_battery_display": "off"})
            upgraded = SettingsStore(path).all()
            self.assertEqual(upgraded["mode"], "artwork")
            self.assertEqual(upgraded["controller_battery_display"], "off")

    def test_engine_accepts_parental_and_free_countdowns(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = ManualClock(100)
            store = SettingsStore(str(Path(directory) / "config.json"))
            engine = Engine(store, str(Path(directory) / "art.json"))
            engine.countdown = CountdownProvider(clock=clock)

            engine.report_parental_minutes(10)
            self.assertFalse(engine.status()["countdown"]["active"])
            engine.set_game(42, "Test")
            engine.report_parental_minutes(10)
            self.assertEqual(engine.status()["countdown"]["source"], "parental")
            self.assertEqual(engine.status()["countdown"]["total_seconds"], 600)

            engine.update_settings({"parental_countdown_enabled": False})
            self.assertFalse(engine.status()["countdown"]["active"])
            engine.report_parental_minutes(9)
            self.assertFalse(engine.status()["countdown"]["active"])

            engine.update_settings({"parental_countdown_enabled": True})
            engine.report_parental_minutes(9)
            self.assertEqual(engine.status()["countdown"]["source"], "parental")
            engine.report_parental_minutes(0)
            self.assertFalse(engine.status()["countdown"]["active"])

            engine.update_settings({"parental_countdown_enabled": False})
            self.assertFalse(engine.status()["countdown"]["active"])
            engine.update_settings({"parental_countdown_enabled": True})
            engine.report_parental_minutes(9)
            clock.advance(532)
            self.assertTrue(engine.status()["countdown"]["alerting"])
            engine.update_settings({"parental_countdown_enabled": False})
            self.assertFalse(engine.status()["countdown"]["active"])

            engine.update_settings({"parental_countdown_enabled": True})
            engine.report_parental_minutes(9)
            clock.advance(532)
            self.assertTrue(engine.status()["countdown"]["alerting"])
            engine.set_game(0, "")
            self.assertFalse(engine.status()["countdown"]["active"])

            engine.set_game(43, "Other test")
            engine.report_parental_minutes(10)
            self.assertTrue(engine.status()["countdown"]["active"])
            engine.set_game(44, "Next test")
            self.assertFalse(engine.status()["countdown"]["active"])

            engine.report_parental_minutes(10)
            engine.report_parental_minutes(1441)
            self.assertFalse(engine.status()["countdown"]["active"])

            engine.start_free_timer(35)
            status = engine.status()
            self.assertEqual(status["countdown"]["source"], "free")
            self.assertEqual(status["free_timer_minutes"], 35)
            self.assertEqual(status["countdown"]["remaining_seconds"], 2100)

    def test_artwork_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "art.json")
            provider = ArtworkProvider(path)
            provider.submit(42, "fingerprint", "auto", 0.72, RED, 0.65, "library_hero.jpg")
            reloaded = ArtworkProvider(path)
            self.assertTrue(reloaded.activate_cached(42, "fingerprint", "auto", 0.72))
            self.assertEqual(reloaded.output(42).frame, RED)
            self.assertFalse(reloaded.activate_cached(42, "changed", "auto", 0.72))

    def test_settings_persist_and_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "config.json")
            store = SettingsStore(path)
            store.update({"mode": "artwork", "artwork_manual_y": 5})
            loaded = SettingsStore(path).all()
            self.assertEqual(loaded["mode"], "artwork")
            self.assertEqual(loaded["artwork_manual_y"], 0.90)
            self.assertEqual(loaded["performance_smoothing"], "responsive")
            self.assertTrue(loaded["performance_always"])
            self.assertEqual(json.loads(Path(path).read_text())["mode"], "artwork")

            store.update({"performance_smoothing": "invalid"})
            self.assertEqual(store.all()["performance_smoothing"], "responsive")
            store.update({
                "temperature_palette": "custom",
                "temperature_custom_cool": [-8, 64.4, 999],
                "temperature_custom_middle": "invalid",
            })
            self.assertEqual(store.all()["temperature_palette"], "custom")
            self.assertEqual(store.all()["temperature_custom_cool"], [0, 64, 255])
            self.assertEqual(store.all()["temperature_custom_middle"], [245, 180, 45])

    def test_countdown_settings_persist_and_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "config.json")
            store = SettingsStore(path)
            self.assertEqual(store.all()["countdown_dark_edge_compensation"], 2)
            self.assertTrue(store.all()["recording_marker_isolation"])
            store.update({
                "parental_countdown_enabled": False,
                "countdown_colour": "violet",
                "countdown_full_bar_minutes": 180,
                "countdown_dark_edge_compensation": 99,
                "free_timer_minutes": 999,
            })
            loaded = SettingsStore(path).all()
            self.assertFalse(loaded["parental_countdown_enabled"])
            self.assertEqual(loaded["countdown_colour"], "violet")
            self.assertEqual(loaded["countdown_full_bar_minutes"], 180)
            self.assertEqual(loaded["countdown_dark_edge_compensation"], 6)
            self.assertEqual(loaded["free_timer_minutes"], 240)
            store.update({"countdown_full_bar_minutes": 90})
            self.assertEqual(store.all()["countdown_full_bar_minutes"], 0)

    def test_runtime_diagnostics_expose_family_callback_delay(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(str(Path(directory) / "config.json"))
            engine = Engine(store, str(Path(directory) / "art.json"))
            engine.set_game(42, "Test")
            engine.report_runtime_diagnostic(
                "game_synced", 42, "Steam lifetime event", 37,
            )
            waiting = engine.status()["debug"]
            self.assertEqual(waiting["game_detection_source"], "Steam lifetime event")
            self.assertEqual(waiting["game_sync_ms"], 37)
            self.assertEqual(waiting["parental_callback_state"], "waiting")
            self.assertIsNotNone(waiting["parental_wait_s"])

            engine.report_runtime_diagnostic(
                "parental_received", 42, "Steam callback", 1250,
            )
            received = engine.status()["debug"]
            self.assertEqual(received["parental_callback_state"], "received")
            self.assertEqual(received["parental_callback_delay_ms"], 1250)
            self.assertIsNone(received["parental_wait_s"])

    def test_artwork_settings_are_persisted_per_game(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "config.json")
            store = SettingsStore(path)
            store.update_artwork(2379780, {"mode": "manual", "manual_y": 0.83, "source": "header"})
            self.assertEqual(store.artwork_for(2379780)["manual_y"], 0.83)
            self.assertTrue(store.artwork_for(2379780)["custom"])
            self.assertEqual(store.artwork_for(2379780)["source"], "header")
            self.assertEqual(store.artwork_for(620)["mode"], "auto")
            self.assertFalse(store.artwork_for(620)["custom"])

            reloaded = SettingsStore(path)
            self.assertEqual(reloaded.artwork_for(2379780)["mode"], "manual")
            self.assertEqual(reloaded.artwork_for(2379780)["manual_y"], 0.83)

    def test_automatic_settings_migrate_to_an_explicit_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"mode": "automatic", "performance_enabled": False}))
            self.assertEqual(SettingsStore(str(path)).all()["mode"], "artwork")
            path.write_text(json.dumps({"mode": "automatic", "performance_enabled": True}))
            self.assertEqual(SettingsStore(str(path)).all()["mode"], "performance")

    def test_discovers_hero_header_and_capsule_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Steam"
            cache = root / "appcache/librarycache/42"
            cache.mkdir(parents=True)
            (cache / "library_hero.jpg").write_bytes(b"hero")
            (cache / "header.jpg").write_bytes(b"header")
            (cache / "library_600x900.jpg").write_bytes(b"capsule")
            with patch.dict("os.environ", {"SIGNALBAR_STEAM_ROOT": str(root)}):
                self.assertEqual(find_library_artwork(42, "hero").name, "library_hero.jpg")
                self.assertEqual(find_library_artwork(42, "header").name, "header.jpg")
                self.assertEqual(find_library_artwork(42, "capsule").name, "library_600x900.jpg")
                payload = get_library_artwork(42, "header")
                self.assertEqual(payload["source_label"], "Library Header")

    def test_custom_grid_artwork_overrides_official_cache_for_active_account(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Steam"
            cache = root / "appcache/librarycache/42"
            cache.mkdir(parents=True)
            (cache / "library_hero.jpg").write_bytes(b"official")
            active_grid = root / "userdata/1234/config/grid"
            active_grid.mkdir(parents=True)
            (active_grid / "42_hero.png").write_bytes(b"custom")
            other_grid = root / "userdata/5678/config/grid"
            other_grid.mkdir(parents=True)
            (other_grid / "42_hero.png").write_bytes(b"other account")
            config = root / "config"
            config.mkdir()
            (config / "loginusers.vdf").write_text(
                '"users"\n{\n'
                '"76561197960266962"\n{\n"MostRecent" "1"\n}\n'
                '"76561197960271406"\n{\n"MostRecent" "0"\n}\n}\n'
            )
            with patch.dict("os.environ", {"SIGNALBAR_STEAM_ROOT": str(root)}):
                payload = get_library_artwork(42, "hero")
                self.assertEqual(payload["filename"], "42_hero.png")
                self.assertEqual(payload["source_label"], "Custom Library Hero")
                self.assertIn("Y3VzdG9t", payload["data_uri"])
                (active_grid / "42_hero.png").unlink()
                self.assertEqual(find_library_artwork(42, "hero"), cache / "library_hero.jpg")

    def test_non_steam_shortcut_uses_custom_grid_and_falls_back_to_available_role(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Steam"
            grid = root / "userdata/1234/config/grid"
            grid.mkdir(parents=True)
            appid = 0xF1234567
            (grid / f"{appid}_hero.png").write_bytes(b"hero")
            (grid / f"{appid}.png").write_bytes(b"header")
            (grid / f"{appid}p.png").write_bytes(b"capsule")
            with patch.dict("os.environ", {"SIGNALBAR_STEAM_ROOT": str(root)}):
                self.assertEqual(get_library_artwork(appid, "hero")["filename"], f"{appid}_hero.png")
                self.assertEqual(get_library_artwork(appid, "header")["filename"], f"{appid}.png")
                self.assertEqual(get_library_artwork(appid, "capsule")["filename"], f"{appid}p.png")
                (grid / f"{appid}_hero.png").unlink()
                payload = get_library_artwork(appid, "hero")
                self.assertEqual(payload["source"], "header")
                self.assertEqual(payload["source_label"], "Custom Library Header")

    def test_active_account_does_not_fall_back_to_another_accounts_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Steam"
            other_grid = root / "userdata/5678/config/grid"
            other_grid.mkdir(parents=True)
            (other_grid / "42_hero.png").write_bytes(b"other account")
            config = root / "config"
            config.mkdir()
            (config / "loginusers.vdf").write_text(
                '"users"\n{\n"76561197960266962"\n{\n"MostRecent" "1"\n}\n}\n'
            )
            with patch.dict("os.environ", {"SIGNALBAR_STEAM_ROOT": str(root)}):
                self.assertFalse(get_library_artwork(42, "hero")["found"])

    def test_hardware_reverse_maps_logical_left_to_physical_right(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(17):
                path = Path(directory) / f"valve-leds[{index}]"
                path.mkdir()
                (path / "multi_intensity").write_text("0 0 0")
                (path / "brightness").write_text("255")
                paths.append(str(path))
            hardware = ValveLedHardware(paths)
            hardware.set_reverse(True)
            frame = normalize_frame([(index, 0, 0) for index in range(17)])
            hardware.write_frame(frame)
            self.assertEqual((Path(paths[0]) / "multi_intensity").read_text(), "16 0 0")
            self.assertEqual((Path(paths[-1]) / "multi_intensity").read_text(), "0 0 0")
            self.assertEqual(hardware.read_frame(), frame)


if __name__ == "__main__":
    unittest.main()
