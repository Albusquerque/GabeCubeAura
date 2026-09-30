from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from signalbar.arbiter import Arbiter
from signalbar.backend import Engine
from signalbar.models import GameState, ProviderOutput, normalize_frame
from signalbar.providers.witcher import (
    SIGN_COLOURS,
    WITCHER3_APP_ID,
    WitcherLabProvider,
    WitcherTelemetryReader,
    parse_telemetry_line,
    parse_telemetry_state_file,
    sign_frame,
    vitals_frame,
    witcher_log_candidates,
    witcher_state_candidates,
)
from signalbar.settings import SettingsStore


BLACK = normalize_frame([(0, 0, 0)] * 17)
BASE = normalize_frame([(12, 14, 16)] * 17)
NATIVE = normalize_frame([(0, 0, 24)] * 17)


class LoopHardware:
    device_path = "/fake/valve-leds"

    def __init__(self):
        self.frame = NATIVE
        self.reverse = False
        self.restores = 0

    def set_reverse(self, reverse):
        self.reverse = bool(reverse)

    def read_frame(self):
        return self.frame

    def read_signature(self):
        return self.frame

    def write_frame(self, frame):
        self.frame = normalize_frame(frame)

    def try_restore(self, frame):
        self.restores += 1
        self.write_frame(frame)


class ReadyScreenSync:
    def __init__(self):
        self.active = False
        self.stops = 0

    def set_active(self, active):
        self.active = bool(active)

    def output(self, _settings):
        return ProviderOutput("screen-sync", BASE if self.active else None, "test capture")

    def status(self):
        return {
            "revision": "test", "active": self.active,
            "phase": "capturing" if self.active else "off",
            "error": "", "node_id": 7, "node_name": "gamescope",
            "runtime_dir": "/run/user/1000", "capture_identity": "deck (uid 1000)",
            "discovery_detail": "test",
            "capture_selector": "target-object=gamescope",
            "conflicting_consumers": 0, "frame_age_s": 0.0 if self.active else None,
            "frames_per_second": 10.0 if self.active else 0.0,
            "crop_top": 0, "crop_bottom": 0,
            "colors": list(BASE if self.active else BLACK),
        }

    def stop(self):
        self.active = False
        self.stops += 1


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class BridgeInstaller:
    def __init__(self, installed=True):
        self.installed = installed

    def status(self):
        return {
            "state": "installed" if self.installed else "not_installed",
            "installed": self.installed,
            "game_found": True,
            "source_found": True,
            "game_path": "/game",
            "target_path": "/game/mods/modgabecubeauratelemetry/content/scripts/local/gca_telemetry.ws",
            "backup_path": "",
            "error": "",
        }

    def install(self):
        self.installed = True
        return self.status()

    def remove(self):
        self.installed = False
        return self.status()


class SessionTelemetry:
    def __init__(self):
        self.next_state = None
        self.connected = False

    def emit(self, health=75):
        self.next_state = {
            "kind": "state", "health": health, "stamina": 80,
            "toxicity": 0, "adrenaline": 1, "combat": False,
        }

    def poll(self, _appid):
        state = self.next_state
        self.next_state = None
        if state:
            self.connected = True
        return state, ""

    def status(self):
        return {
            "connected": self.connected, "age_s": 0.0 if self.connected else None,
            "path": "/prefix/Documents/The Witcher 3/scriptlog.txt" if self.connected else "",
            "error": "",
        }


class WitcherLabTests(unittest.TestCase):
    def test_log_discovery_uses_witcherscript_singular_filename(self):
        candidates = [str(path) for path in witcher_log_candidates("/tmp/gca-home")]
        singular = [path for path in candidates if path.endswith("/scriptlog.txt")]
        self.assertTrue(singular)
        self.assertLess(candidates.index(singular[0]), next(
            index for index, path in enumerate(candidates) if path.endswith("/scriptslog.txt")
        ))
        reader = WitcherTelemetryReader(candidates=[Path(path) for path in candidates[:3]])
        diagnostic = reader.status()
        self.assertEqual(diagnostic["candidate_count"], 3)
        self.assertEqual(diagnostic["expected_path"], candidates[0])

    def test_game_log_records_are_strictly_parsed_and_normalized(self):
        state = parse_telemetry_line(
            "[GabeCubeAura] GCA1|kind=state|health=250|health_max=500|"
            "stamina=75|stamina_max=100|toxicity=20|toxicity_max=80|"
            "adrenaline=2.9|combat=1"
        )
        self.assertEqual(state, {
            "kind": "state", "health": 50.0, "stamina": 75.0,
            "toxicity": 25.0, "adrenaline": 2, "combat": True,
        })
        self.assertEqual(
            parse_telemetry_line("[GabeCubeAura] GCA1|kind=sign|sign=Igni"),
            {"kind": "sign", "sign": "igni"},
        )
        self.assertIsNone(parse_telemetry_line("[Other] health=100"))
        self.assertIsNone(parse_telemetry_line("GCA1|kind=sign|sign=heliotrope"))

    def test_direct_state_file_transport_does_not_need_scriptlog(self):
        clock = Clock(100.0)
        with tempfile.TemporaryDirectory() as folder:
            state_file = Path(folder) / "GabeCubeAuraTelemetry.ini"
            state_file.write_text(
                'state="GCA1|kind=state|health=25|health_max=100|stamina=30|'
                'stamina_max=60|toxicity=10|toxicity_max=100|adrenaline=2|combat=1"\n'
                'state_stamp="1000"\n'
                'sign="GCA1|kind=sign|sign=Igni"\n'
                'sign_stamp="1001"\n',
                encoding="utf-8",
            )
            os.utime(state_file, (clock.now, clock.now))
            parsed = parse_telemetry_state_file(state_file.read_text(encoding="utf-8"))
            self.assertEqual(parsed["state"]["health"], 25)
            self.assertEqual(parsed["sign"], "igni")

            reader = WitcherTelemetryReader(
                candidates=[], state_candidates=[state_file], clock=clock, wall_clock=clock,
            )
            state, sign = reader.poll(WITCHER3_APP_ID)
            self.assertEqual(state["stamina"], 50)
            self.assertEqual(sign, "igni")
            self.assertEqual(reader.status()["transport"], "state-file")
            self.assertEqual(reader.status()["path"], str(state_file))

            _state, repeated_sign = reader.poll(WITCHER3_APP_ID)
            self.assertEqual(repeated_sign, "")
            state_file.write_text(
                state_file.read_text(encoding="utf-8").replace('sign_stamp="1001"', 'sign_stamp="1002"'),
                encoding="utf-8",
            )
            os.utime(state_file, (clock.now, clock.now))
            _state, new_sign = reader.poll(WITCHER3_APP_ID)
            self.assertEqual(new_sign, "igni")

    def test_state_discovery_uses_documents_in_appid_292030_prefix(self):
        candidates = [str(path) for path in witcher_state_candidates("/tmp/gca-home")]
        self.assertTrue(candidates)
        self.assertTrue(all("compatdata/292030" in path for path in candidates))
        self.assertTrue(candidates[0].endswith("/Documents/The Witcher 3/GabeCubeAuraTelemetry.ini"))

    def test_discovery_prefers_freshest_prefix_over_stale_first_candidate(self):
        clock = Clock(100.0)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stale = root / "old-library/GabeCubeAuraTelemetry.ini"
            live = root / "current-library/GabeCubeAuraTelemetry.ini"
            stale.parent.mkdir(parents=True)
            live.parent.mkdir(parents=True)
            stale.write_text(
                "state=GCA1|kind=state|health=1|health_max=100|stamina=1|"
                "stamina_max=100|toxicity=0|toxicity_max=100|adrenaline=0|combat=0\n",
                encoding="utf-8",
            )
            live.write_text(
                "state=GCA1|kind=state|health=73|health_max=100|stamina=50|"
                "stamina_max=100|toxicity=0|toxicity_max=100|adrenaline=0|combat=0\n",
                encoding="utf-8",
            )
            os.utime(stale, (90.0, 90.0))
            os.utime(live, (100.0, 100.0))

            reader = WitcherTelemetryReader(
                candidates=[], state_candidates=[stale, live],
                clock=clock, wall_clock=clock,
            )
            state, _sign = reader.poll(WITCHER3_APP_ID)

            self.assertEqual(state["health"], 73)
            self.assertEqual(reader.status()["path"], str(live))

    def test_direct_state_survives_an_independent_script_log_read_error(self):
        class FaultyLogReader(WitcherTelemetryReader):
            def _poll_log(self, path, now):
                raise OSError("diagnostic log temporarily unavailable")

        clock = Clock(100.0)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state_file = root / "GabeCubeAuraTelemetry.ini"
            script_log = root / "scriptlog.txt"
            state_file.write_text(
                "state=GCA1|kind=state|health=61|health_max=100|stamina=50|"
                "stamina_max=100|toxicity=0|toxicity_max=100|adrenaline=0|combat=0\n",
                encoding="utf-8",
            )
            script_log.write_text("diagnostic fallback\n", encoding="utf-8")
            os.utime(state_file, (100.0, 100.0))
            os.utime(script_log, (100.0, 100.0))
            reader = FaultyLogReader(
                candidates=[script_log], state_candidates=[state_file],
                clock=clock, wall_clock=clock,
            )

            state, _sign = reader.poll(WITCHER3_APP_ID)

            self.assertEqual(state["health"], 61)
            self.assertEqual(reader.status()["transport"], "state-file")
            self.assertIn("script log: diagnostic log temporarily unavailable",
                          reader.status()["error"])

    def test_live_log_updates_provider_and_expires_when_stream_stops(self):
        clock = Clock(100.0)
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "scriptlog.txt"
            log.write_text(
                "[GabeCubeAura] GCA1|kind=state|health=40|health_max=100|"
                "stamina=30|stamina_max=60|toxicity=25|toxicity_max=100|"
                "adrenaline=3|combat=1\n"
                "[GabeCubeAura] GCA1|kind=sign|sign=Quen\n",
                encoding="utf-8",
            )
            os.utime(log, (clock.now, clock.now))
            reader = WitcherTelemetryReader(
                candidates=[log], clock=clock, wall_clock=clock,
            )
            provider = WitcherLabProvider(clock=clock, telemetry_reader=reader)
            provider.update({"enabled": True})
            self.assertTrue(provider.refresh_telemetry(WITCHER3_APP_ID))
            status = provider.status(WITCHER3_APP_ID)
            self.assertTrue(status["telemetry_connected"])
            self.assertEqual(status["source"], "live")
            self.assertEqual(status["health"], 40)
            self.assertEqual(status["stamina"], 50)
            self.assertEqual(status["toxicity"], 25)
            self.assertEqual(status["adrenaline"], 3)
            self.assertTrue(status["combat"])
            self.assertEqual(provider.output(WITCHER3_APP_ID).provider, "witcher-lab:sign")
            clock.advance(1.6)
            self.assertFalse(provider.status(WITCHER3_APP_ID)["telemetry_connected"])
            self.assertEqual(provider.status(WITCHER3_APP_ID)["source"], "manual")

    def test_old_log_is_not_replayed_as_live_telemetry(self):
        clock = Clock(200.0)
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "scriptlog.txt"
            log.write_text(
                "GCA1|kind=state|health=1|health_max=100|stamina=1|"
                "stamina_max=100|toxicity=1|toxicity_max=100|adrenaline=1|combat=1\n",
                encoding="utf-8",
            )
            os.utime(log, (100.0, 100.0))
            reader = WitcherTelemetryReader(
                candidates=[log], clock=clock, wall_clock=clock,
            )
            state, sign = reader.poll(WITCHER3_APP_ID)
            self.assertIsNone(state)
            self.assertEqual(sign, "")
            self.assertFalse(reader.status()["connected"])

    def test_vitals_frame_is_bounded_and_separates_hud_regions(self):
        frame = vitals_frame(50, 25, 100, 3, combat=True, elapsed_seconds=.2)
        self.assertEqual(len(frame), 17)
        self.assertTrue(all(0 <= channel <= 255 for pixel in frame for channel in pixel))
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in frame[:8]), 4)
        self.assertEqual(sum(pixel != (0, 0, 0) for pixel in frame[9:]), 4)
        self.assertGreater(frame[8][0], frame[8][1])
        self.assertGreater(frame[0][1], frame[0][0])
        self.assertGreater(frame[16][1], frame[16][0])

    def test_sign_colours_make_a_short_centre_out_wave(self):
        for sign, colour in SIGN_COLOURS.items():
            with self.subTest(sign=sign):
                self.assertEqual(sign_frame(sign, 0)[8], colour)
                self.assertNotEqual(sign_frame(sign, .45), BLACK)
                self.assertIsNone(sign_frame(sign, .9))

    def test_provider_requires_explicit_enable_and_complete_edition_appid(self):
        provider = WitcherLabProvider(clock=Clock())
        self.assertIsNone(provider.output(WITCHER3_APP_ID).frame)
        provider.update({"enabled": True, "health": 40, "stamina": 60})
        self.assertIsNone(provider.output(10).frame)
        output = provider.output(WITCHER3_APP_ID)
        self.assertEqual(output.provider, "witcher-lab")
        self.assertEqual(len(output.frame), 17)

    def test_sign_returns_to_current_vitals(self):
        clock = Clock()
        provider = WitcherLabProvider(clock=clock)
        provider.update({"enabled": True, "health": 35, "stamina": 70})
        base = provider.output(WITCHER3_APP_ID).frame
        self.assertTrue(provider.trigger_sign("igni"))
        self.assertEqual(provider.output(WITCHER3_APP_ID).provider, "witcher-lab:sign")
        clock.advance(.91)
        restored = provider.output(WITCHER3_APP_ID)
        self.assertEqual(restored.provider, "witcher-lab")
        self.assertEqual(restored.frame, base)

    def test_arbiter_keeps_steam_alerts_launches_and_countdowns_above_lab(self):
        arbiter = Arbiter()
        game = GameState(WITCHER3_APP_ID, "The Witcher 3")
        lab = ProviderOutput("witcher-lab", BASE, "manual")
        timer = ProviderOutput("countdown", BASE, "timer")
        event = ProviderOutput("event:notification", BASE, "alert")
        launch = ProviderOutput("launch-artwork:ripple", BASE, "launch")
        empty = ProviderOutput("none", None, "")
        kwargs = dict(game=game, performance=empty, artwork=empty, idle=empty, witcher=lab)
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True, **kwargs).provider,
                         "witcher-lab")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=False, **kwargs).provider,
                         "valve")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True,
                                        signal=timer, **kwargs).provider, "countdown")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True,
                                        event=event, **kwargs).provider, "event:notification")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True,
                                        launch_artwork=launch, **kwargs).provider,
                         "launch-artwork:ripple")
        self.assertEqual(arbiter.choose(mode="performance", guard_allows=True,
                                        steam_priority=True, **kwargs).provider, "valve")

    def test_engine_requires_witcher_and_stops_lab_when_game_exits(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
            )
            with self.assertRaisesRegex(ValueError, "Complete Edition"):
                engine.update_witcher_lab({"enabled": True})
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3: Wild Hunt - Complete Edition")
            status = engine.update_witcher_lab({"enabled": True, "health": 45})
            self.assertTrue(status["witcher"]["armed"])
            self.assertFalse(status["witcher"]["active"])
            self.assertEqual(status["witcher"]["health"], 45)
            engine.set_game(0, "")
            self.assertFalse(engine.status()["witcher"]["enabled"])

    def test_game_transition_fully_restarts_screen_sync_capture_session(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
            )
            capture = ReadyScreenSync()
            capture.set_active(True)
            engine.screen_sync = capture

            engine.set_game(WITCHER3_APP_ID, "The Witcher 3 Remastered", launch=True)
            self.assertEqual(capture.stops, 1)
            self.assertFalse(capture.active)
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3 Remastered", launch=False)
            self.assertEqual(capture.stops, 1)
            engine.set_game(0, "")
            self.assertEqual(capture.stops, 2)

    def test_live_verified_bridge_automatically_follows_game_lifetime(self):
        with tempfile.TemporaryDirectory() as folder:
            telemetry = SessionTelemetry()
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
                witcher_installer=BridgeInstaller(installed=True),
            )
            engine.witcher.telemetry = telemetry
            self.assertFalse(engine.status()["witcher"]["enabled"])

            engine.set_game(WITCHER3_APP_ID, "The Witcher 3 Remastered")
            # A matching file checksum is not runtime proof. A broken script
            # arms the game-scoped Lab but must not take the bar with static
            # fallback values.
            waiting = engine.status()["witcher"]
            self.assertTrue(waiting["enabled"])
            self.assertTrue(waiting["auto_managed"])
            self.assertFalse(waiting["runtime_verified_session"])
            self.assertIsNone(engine.witcher.output(WITCHER3_APP_ID).frame)

            telemetry.emit()
            self.assertTrue(engine.witcher.refresh_telemetry(WITCHER3_APP_ID))
            running = engine.status()["witcher"]
            self.assertTrue(running["enabled"])
            self.assertTrue(running["auto_managed"])
            self.assertTrue(running["runtime_verified_session"])
            self.assertTrue(running["armed"])
            self.assertIsNotNone(engine.witcher.output(WITCHER3_APP_ID).frame)

            # Neither a stale UI toggle nor a display-routing change may leave
            # the verified game-scoped bridge off while AppID 292030 runs.
            engine.update_witcher_lab({"enabled": False})
            engine.update_display(WITCHER3_APP_ID, "artwork")
            self.assertTrue(engine.status()["witcher"]["enabled"])
            self.assertTrue(engine.status()["witcher"]["auto_managed"])

            engine.set_game(0, "")
            stopped = engine.status()["witcher"]
            self.assertFalse(stopped["enabled"])
            self.assertFalse(stopped["auto_managed"])
            self.assertFalse(stopped["runtime_verified_session"])

    def test_poll_inferred_stop_resumes_verified_hud_without_new_packet(self):
        with tempfile.TemporaryDirectory() as folder:
            telemetry = SessionTelemetry()
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
                witcher_installer=BridgeInstaller(installed=True),
            )
            engine.witcher.telemetry = telemetry
            engine.set_game(
                WITCHER3_APP_ID, "The Witcher 3 Remastered",
                source="poll fallback",
            )
            telemetry.emit(health=15)
            engine.witcher.refresh_telemetry(WITCHER3_APP_ID)
            self.assertTrue(engine.status()["witcher"]["runtime_verified_session"])

            engine.set_game(
                0, "", source="poll confirmed missing lifetime stop",
            )
            paused = engine.status()["witcher"]
            self.assertFalse(paused["runtime_verified_session"])
            self.assertTrue(paused["runtime_resume_pending"])

            engine.set_game(
                WITCHER3_APP_ID, "The Witcher 3 Remastered",
                source="poll fallback",
            )
            resumed = engine.status()["witcher"]
            self.assertTrue(resumed["runtime_verified_session"])
            self.assertFalse(resumed["runtime_resume_pending"])
            self.assertEqual(resumed["health"], 15)
            self.assertIsNotNone(engine.witcher.output(WITCHER3_APP_ID).frame)

    def test_authoritative_stop_does_not_resume_stale_witcher_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            telemetry = SessionTelemetry()
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
                witcher_installer=BridgeInstaller(installed=True),
            )
            engine.witcher.telemetry = telemetry
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3 Remastered")
            telemetry.emit()
            engine.witcher.refresh_telemetry(WITCHER3_APP_ID)

            engine.set_game(0, "", source="Steam lifetime stop")
            stopped = engine.status()["witcher"]
            self.assertFalse(stopped["runtime_verified_session"])
            self.assertFalse(stopped["runtime_resume_pending"])

            engine.set_game(
                WITCHER3_APP_ID, "The Witcher 3 Remastered",
                source="Steam lifetime start",
            )
            restarted = engine.status()["witcher"]
            self.assertFalse(restarted["runtime_verified_session"])
            self.assertIsNone(engine.witcher.output(WITCHER3_APP_ID).frame)

    def test_install_during_game_waits_for_live_runtime_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            installer = BridgeInstaller(installed=False)
            telemetry = SessionTelemetry()
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
                witcher_installer=installer,
            )
            engine.witcher.telemetry = telemetry
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3 Remastered")
            self.assertFalse(engine.status()["witcher"]["enabled"])
            self.assertFalse(engine.status()["witcher"]["auto_managed"])

            status = engine.install_witcher_telemetry_mod()["witcher"]
            self.assertTrue(status["enabled"])
            self.assertTrue(status["auto_managed"])
            self.assertFalse(status["runtime_verified_session"])
            self.assertIsNone(engine.witcher.output(WITCHER3_APP_ID).frame)
            telemetry.emit()
            engine.witcher.refresh_telemetry(WITCHER3_APP_ID)
            status = engine.status()["witcher"]
            self.assertTrue(status["enabled"])
            self.assertTrue(status["auto_managed"])

    def test_lifecycle_releases_if_verified_bridge_is_removed_mid_game(self):
        installer = BridgeInstaller(installed=True)
        telemetry = SessionTelemetry()
        provider = WitcherLabProvider(
            clock=Clock(), installer=installer, telemetry_reader=telemetry,
        )
        self.assertTrue(provider.sync_game_lifecycle(WITCHER3_APP_ID))
        self.assertIsNone(provider.output(WITCHER3_APP_ID).frame)
        telemetry.emit()
        self.assertTrue(provider.refresh_telemetry(WITCHER3_APP_ID))
        self.assertTrue(provider.status(WITCHER3_APP_ID)["enabled"])
        installer.installed = False
        self.assertFalse(provider.sync_game_lifecycle(WITCHER3_APP_ID))
        self.assertFalse(provider.status(WITCHER3_APP_ID)["enabled"])

    def test_remove_button_backend_releases_automatic_lab_immediately(self):
        with tempfile.TemporaryDirectory() as folder:
            installer = BridgeInstaller(installed=True)
            telemetry = SessionTelemetry()
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
                witcher_installer=installer,
            )
            engine.witcher.telemetry = telemetry
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3 Remastered")
            telemetry.emit()
            engine.witcher.refresh_telemetry(WITCHER3_APP_ID)
            self.assertTrue(engine.status()["witcher"]["auto_managed"])

            removed = engine.remove_witcher_telemetry_mod()["witcher"]
            self.assertFalse(installer.installed)
            self.assertFalse(removed["enabled"])
            self.assertFalse(removed["auto_managed"])
            self.assertFalse(removed["runtime_verified_session"])

    def test_running_engine_selects_armed_lab_on_the_physical_output(self):
        with tempfile.TemporaryDirectory() as folder:
            hardware = LoopHardware()
            settings = SettingsStore(str(Path(folder) / "settings.json"))
            settings.update({"guard_stable_s": .5})
            engine = Engine(
                settings, str(Path(folder) / "artwork.json"),
                hardware_factory=lambda: hardware,
            )
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3")
            engine.update_witcher_lab({"enabled": True})
            engine.start()
            try:
                self.assertTrue(self._wait_until(
                    lambda: engine.status()["provider"].startswith("witcher-lab"),
                    timeout=3.0,
                ), engine.status())
                status = engine.status()
                self.assertTrue(status["witcher"]["armed"])
                self.assertTrue(status["witcher"]["selected"])
                self.assertTrue(status["debug"]["engine_running"])
                self.assertLess(status["debug"]["decision_age_s"], .5)
                self.assertNotEqual(hardware.frame, NATIVE)
            finally:
                engine.stop()

    def test_screen_sync_preview_temporarily_replaces_lab_without_disarming_it(self):
        with tempfile.TemporaryDirectory() as folder:
            hardware = LoopHardware()
            settings = SettingsStore(str(Path(folder) / "settings.json"))
            settings.update({"guard_stable_s": .5})
            engine = Engine(
                settings, str(Path(folder) / "artwork.json"),
                hardware_factory=lambda: hardware,
            )
            engine.screen_sync = ReadyScreenSync()
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3")
            engine.update_witcher_lab({"enabled": True})
            engine.start()
            try:
                self.assertTrue(self._wait_until(
                    lambda: engine.status()["provider"].startswith("witcher-lab"),
                    timeout=3.0,
                ), engine.status())
                self.assertTrue(engine.preview_screen_sync(15))
                self.assertTrue(self._wait_until(
                    lambda: engine.status()["provider"] == "screen-sync",
                ))
                status = engine.status()
                self.assertTrue(status["witcher"]["armed"])
                self.assertFalse(status["witcher"]["selected"])
                self.assertTrue(status["screen_sync"]["active"])
            finally:
                engine.stop()

    def test_render_loop_restores_valve_and_recovers_after_one_runtime_fault(self):
        with tempfile.TemporaryDirectory() as folder:
            hardware = LoopHardware()
            settings = SettingsStore(str(Path(folder) / "settings.json"))
            settings.update({"guard_stable_s": .5})
            engine = Engine(
                settings, str(Path(folder) / "artwork.json"),
                hardware_factory=lambda: hardware,
            )
            calls = {"count": 0}

            def choose(**_kwargs):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise RuntimeError("one-shot provider fault")
                return ProviderOutput("performance", BASE, "test")

            engine.arbiter.choose = choose
            engine.start()
            try:
                self.assertTrue(self._wait_until(
                    lambda: engine.status()["provider"] == "performance",
                    timeout=3.0,
                ))
                self.assertTrue(self._wait_until(
                    lambda: bool(engine.status()["debug"]["last_runtime_error"]),
                    timeout=2.0,
                ))
                self.assertTrue(self._wait_until(
                    lambda: engine.status()["provider"] == "performance"
                    and engine.status()["debug"]["engine_running"],
                    timeout=3.0,
                ))
                self.assertGreaterEqual(hardware.restores, 1)
                self.assertEqual(
                    engine.status()["debug"]["last_runtime_error"],
                    "one-shot provider fault",
                )
            finally:
                engine.stop()

    def test_explicit_display_routing_stops_the_experimental_override(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(
                SettingsStore(str(Path(folder) / "settings.json")),
                str(Path(folder) / "artwork.json"),
            )
            engine.set_game(WITCHER3_APP_ID, "The Witcher 3")
            engine.update_witcher_lab({"enabled": True})
            engine.update_display(WITCHER3_APP_ID, "performance")
            self.assertFalse(engine.status()["witcher"]["enabled"])

            engine.update_witcher_lab({"enabled": True})
            engine.update_settings({"game_display": "artwork"})
            self.assertFalse(engine.status()["witcher"]["enabled"])

    def test_witcher_has_explicit_stripmine_priority(self):
        values = {"stripmine_priority_witcher": "signalbar"}
        self.assertEqual(Engine._stripmine_priority("witcher-lab", values), "signalbar")
        self.assertEqual(Engine._stripmine_priority("witcher-lab:sign", values), "signalbar")

    @staticmethod
    def _wait_until(predicate, timeout=1.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(.01)
        return False


if __name__ == "__main__":
    unittest.main()
