"""SignalBar runtime orchestration.

Data collection stays in providers, ownership policy in Arbiter/VanillaGuard,
and all sysfs writes in Renderer.
"""

from __future__ import annotations

import threading
import time

from signalbar import __version__
from signalbar.arbiter import Arbiter, VanillaGuard
from signalbar.hardware import ValveLedHardware
from signalbar.integration import LightEventLease, StripMineClaimReader
from signalbar.models import GameState
from signalbar.providers import ArtworkProvider, CountdownProvider, EventProvider, IdleProvider, PerformanceProvider
from signalbar.providers.controller import ControllerProvider
from signalbar.providers.weather import WeatherProvider
from signalbar.renderer import Renderer


class Engine:
    def __init__(self, settings, cache_path, logger=None, hardware_factory=ValveLedHardware,
                 event_lease=None, stripmine_claim=None):
        self.settings = settings
        self.log = logger
        self.hardware_factory = hardware_factory
        self.event_lease = event_lease or LightEventLease()
        self.stripmine_claim = stripmine_claim or StripMineClaimReader()
        self._light_event_announced_at = 0.0
        self.artwork = ArtworkProvider(cache_path)
        self.countdown = CountdownProvider()
        self.performance = PerformanceProvider()
        self.events = EventProvider()
        self.events.set_variants(settings.all())
        self.controllers = ControllerProvider()
        self.weather = WeatherProvider()
        initial = settings.all()
        self.weather.configure(initial["weather_location"], initial["weather_display"], initial["weather_topbar_enabled"])
        self.idle = IdleProvider()
        self.arbiter = Arbiter()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._game = GameState()
        self._artwork_identity = None
        self._steam_active_until = 0.0
        self._steam_reason = ""
        self._renderer = None
        self._guard = None
        self._decision = "none"
        self._owner = "Valve"
        self._suspension_reason = "starting"
        self._error = ""
        self._available = False
        self._runtime_debug = {
            "appid": 0,
            "game_detection_source": "startup",
            "game_sync_ms": None,
            "parental_callback_state": "idle",
            "parental_callback_delay_ms": None,
            "parental_wait_started_at": 0.0,
            "controller_callback_source": "waiting",
            "controller_last_update_at": 0.0,
            "controller_telemetry": {"phase": "starting", "hooks": 0, "queries": 0,
                                     "events": 0, "raw_count": 0, "query_ms": None, "error": ""},
        }

    def _info(self, message):
        if self.log:
            self.log.info(f"[SignalBar] {message}")

    def _warn(self, message):
        if self.log:
            self.log.warning(f"[SignalBar] {message}")

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self.weather.start()
            self._thread = threading.Thread(target=self._run, name="signalbar-engine", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        self.weather.stop()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self.events.clear_transients()
            self.events.clear_recording()
            self.controllers.clear()
            if self._renderer:
                self._renderer.relinquish(restore_if_owned=True)
            self.event_lease.release()
            self.stripmine_claim.release()
            self._light_event_announced_at = 0.0
            self._owner = "Valve"
            self._decision = "none"

    def set_game(self, appid=0, title=""):
        try:
            appid = max(0, int(appid or 0))
        except (TypeError, ValueError):
            appid = 0
        with self._lock:
            changed = appid != self._game.appid
            self._game = GameState(appid, str(title or ""))
            if changed:
                # A Steam Families deadline belongs to the game session that
                # produced it. Never leak it into the next game or after exit.
                self.countdown.stop("parental")
                self.events.clear_recording()
            if changed or not self._game.running:
                self.artwork.clear()
                self._artwork_identity = None
            self.controllers.cancel_for_settings(self.settings.all(), self._game.running)

    def prepare_artwork(self, appid, fingerprint, filename="", source="hero"):
        artwork_settings = self.settings.artwork_for(appid)
        identity = (int(appid), str(fingerprint), str(filename or ""), str(source or "hero"))
        with self._lock:
            self._artwork_identity = identity
            return self.artwork.activate_cached(
                identity[0], identity[1], artwork_settings["mode"], artwork_settings["manual_y"]
            )

    def submit_artwork(self, appid, fingerprint, colors, sample_y, filename="", source="hero"):
        artwork_settings = self.settings.artwork_for(appid)
        self.artwork.submit(
            appid, fingerprint, artwork_settings["mode"], artwork_settings["manual_y"],
            colors, sample_y, filename, source,
        )

    def update_artwork_settings(self, appid, changes):
        artwork_settings = self.settings.update_artwork(appid, changes)
        with self._lock:
            if self._artwork_identity and int(appid or 0) == self._artwork_identity[0]:
                identity_appid, fingerprint, _, _ = self._artwork_identity
                self.artwork.activate_cached(
                    identity_appid, fingerprint,
                    artwork_settings["mode"], artwork_settings["manual_y"],
                )
        return artwork_settings

    def set_steam_activity(self, active, reason="Steam event"):
        with self._lock:
            if active:
                # Lease prevents a vanished frontend from suspending forever.
                self._steam_active_until = time.monotonic() + 3.0
                self._steam_reason = str(reason or "Steam event")
            else:
                self._steam_active_until = 0.0
                self._steam_reason = ""

    def report_runtime_diagnostic(self, event, appid=0, source="", duration_ms=-1):
        """Record frontend lifecycle timings without affecting provider policy."""
        try:
            appid = max(0, int(appid or 0))
            duration_ms = max(0.0, float(duration_ms))
        except (TypeError, ValueError):
            return
        event = str(event or "")
        now = time.monotonic()
        with self._lock:
            if event == "game_synced":
                self._runtime_debug.update({
                    "appid": appid,
                    "game_detection_source": str(source or "unknown")[:48],
                    "game_sync_ms": duration_ms,
                    "parental_callback_state": (
                        "waiting" if appid > 0 and self.settings.all()["parental_countdown_enabled"]
                        else "disabled" if appid > 0 else "idle"
                    ),
                    "parental_callback_delay_ms": None,
                    "parental_wait_started_at": now if appid > 0 else 0.0,
                })
            elif event == "parental_received" and appid == self._runtime_debug["appid"]:
                self._runtime_debug.update({
                    "parental_callback_state": "received",
                    "parental_callback_delay_ms": duration_ms,
                    "parental_wait_started_at": 0.0,
                })

    def report_parental_minutes(self, minutes):
        try:
            minutes = float(minutes)
        except (TypeError, ValueError):
            return
        values = self.settings.all()
        with self._lock:
            game_running = self._game.running
        if not values["parental_countdown_enabled"] or not game_running:
            self.countdown.stop("parental")
            return
        # SteamUI uses values above one day as the no-active-limit sentinel.
        if minutes <= 0:
            self.countdown.stop("parental")
            return
        if minutes > 1440:
            self.countdown.stop("parental")
            return
        self.countdown.start(
            "parental", minutes * 60.0,
            label="Steam Families",
        )

    def start_free_timer(self, minutes):
        values = self.settings.update({"free_timer_minutes": minutes})
        duration = values["free_timer_minutes"] * 60.0
        self.countdown.start("free", duration, total_seconds=duration, label="Free timer")

    def stop_free_timer(self):
        self.countdown.stop("free")

    def preview_countdown(self):
        self.countdown.start("preview", 15.0, total_seconds=15.0, label="Preview")

    def trigger_event(self, kind, preview=False, variant=""):
        values = self.settings.all()
        kind = str(kind or "")
        if values["mode"] == "disabled":
            return False
        if self.controllers.event_output().provider == "controller:low":
            return False
        if not preview:
            setting = {
                "notification": "event_notifications_enabled",
                "achievement": "event_achievements_enabled",
                "screenshot": "event_screenshots_enabled",
                "record-start": "event_recording_enabled",
                "record-stop": "event_recording_enabled",
            }.get(kind)
            if not values["events_enabled"] or not setting or not values[setting]:
                return False
        with self._lock:
            game_running = self._game.running
        countdown = self.countdown.status(
            allow_parental=values["parental_countdown_enabled"] and game_running,
        )
        if countdown["active"] and countdown["remaining_seconds"] <= 300:
            # Recording state still follows Steam, but the warning is never
            # visually interrupted, even for a fraction of one render tick.
            if kind in {"record-start", "record-stop"} and not preview:
                self.events.trigger(kind)
                self.events.clear_transients()
            return False
        return self.events.trigger(kind, preview=bool(preview), variant=variant)

    def update_controllers(self, controllers, source="Steam callback"):
        values = self.settings.all()
        with self._lock:
            running = self._game.running
            self._runtime_debug["controller_callback_source"] = str(source or "Steam callback")[:48]
            self._runtime_debug["controller_last_update_at"] = time.monotonic()
        countdown = self.countdown.status(allow_parental=values["parental_countdown_enabled"] and running)
        if countdown["active"] and countdown["remaining_seconds"] <= 300:
            # Keep receiving real state, but don't consume an unseen low warning.
            values = {**values, "controller_alerts_enabled": False}
        if self.controllers.update(controllers, values, running) == "low":
            self.events.clear_transients()

    def reset_controllers(self):
        self.controllers.clear()
        with self._lock:
            self._runtime_debug["controller_callback_source"] = "waiting"
            self._runtime_debug["controller_last_update_at"] = 0.0
            self._runtime_debug["controller_telemetry"]["phase"] = "starting"

    def report_controller_telemetry(self, state):
        if not isinstance(state, dict):
            return
        phase = state.get("phase")
        if phase not in {"starting", "ready", "unavailable", "error"}:
            return
        clean = {"phase": phase, "error": str(state.get("error") or "")[:180]}
        for key in ("hooks", "queries", "events", "raw_count", "query_ms"):
            value = state.get(key)
            clean[key] = min(10000000, max(0, int(value))) if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < float("inf") else (None if key == "query_ms" else 0)
        clean["devices"] = []
        devices = state.get("devices", [])
        if isinstance(devices, list):
            for device in devices[:8]:
                if not isinstance(device, dict):
                    continue
                entry = {"name": str(device.get("name", "Controller"))[:64],
                         "source": str(device.get("source", "unknown"))[:40]}
                for key in ("index", "list_percent", "store_percent", "event_percent", "effective_percent", "event_age_s"):
                    value = device.get(key)
                    maximum = 0xffffffff if key == "index" else 100 if key.endswith("percent") else 10000000
                    entry[key] = value if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= maximum else None
                clean["devices"].append(entry)
        with self._lock:
            self._runtime_debug["controller_telemetry"] = clean

    def preview_controller(self, kind, variant=""):
        values = self.settings.all()
        if values["mode"] == "disabled":
            return False
        with self._lock:
            running = self._game.running
        countdown = self.countdown.status(
            allow_parental=values["parental_countdown_enabled"] and running,
        )
        if countdown["active"] and countdown["remaining_seconds"] <= 300:
            return False
        selected = str(kind or "")
        played = self.controllers.preview(selected, values, str(variant or ""))
        if played and selected == "low":
            self.events.clear_transients()
        return played

    def _weather_preview_allowed(self):
        values = self.settings.all()
        if values["mode"] == "disabled":
            return False
        with self._lock:
            running = self._game.running
        countdown = self.countdown.status(
            allow_parental=values["parental_countdown_enabled"] and running,
        )
        if countdown["active"] and countdown["remaining_seconds"] <= 300:
            return False
        return True

    def preview_weather(self, condition, variant):
        return self._weather_preview_allowed() and self.weather.preview(condition, variant)

    def stop_weather_preview(self):
        self.weather.stop_preview()
        return True

    def update_settings(self, changes):
        values = self.settings.update(changes)
        self._apply_settings(values, changes)
        return values

    def import_configuration(self, global_values, display_profiles, artwork_profiles):
        previous = self.settings.all()
        values = self.settings.replace_configuration(global_values, display_profiles, artwork_profiles)
        changes = {key: value for key, value in values.items() if previous.get(key) != value}
        self._apply_settings(values, changes)
        self.countdown.stop("free")
        self.weather.stop_preview()
        self.controllers.clear_transients()
        self.events.clear_transients()
        with self._lock:
            if self._artwork_identity:
                appid, fingerprint, _, _ = self._artwork_identity
                artwork_settings = self.settings.artwork_for(appid)
                self.artwork.activate_cached(appid, fingerprint,
                                             artwork_settings["mode"], artwork_settings["manual_y"])
        return values

    def reset_configuration(self):
        return self.import_configuration({}, {}, {})

    def _apply_settings(self, values, changes):
        self.weather.configure(values["weather_location"], values["weather_display"], values["weather_topbar_enabled"])
        self.events.set_variants(values)
        with self._lock:
            running = self._game.running
        self.controllers.cancel_for_settings(values, running)
        if not values["events_enabled"] or not values["event_recording_enabled"]:
            self.events.clear_recording()
        if not values["events_enabled"]:
            self.events.clear_transients()
        elif values["mode"] == "disabled":
            self.events.clear_transients()
        else:
            for key, kinds in (
                ("event_notifications_enabled", ("notification",)),
                ("event_achievements_enabled", ("achievement",)),
                ("event_screenshots_enabled", ("screenshot",)),
                ("event_recording_enabled", ("record-start", "record-stop")),
            ):
                if key in changes and not values[key]:
                    self.events.cancel_kinds(kinds)
        if values["mode"] == "disabled":
            self.controllers.clear_transients()
        if "parental_countdown_enabled" in changes and not values["parental_countdown_enabled"]:
            # Turning the feature off is an immediate cancellation, not only
            # a visual filter. Later callbacks are ignored until re-enabled.
            self.countdown.stop("parental")
            with self._lock:
                self._runtime_debug["parental_callback_state"] = "disabled"
                self._runtime_debug["parental_wait_started_at"] = 0.0
        elif "parental_countdown_enabled" in changes:
            with self._lock:
                if self._game.running:
                    self._runtime_debug["parental_callback_state"] = "waiting"
                    self._runtime_debug["parental_callback_delay_ms"] = None
                    self._runtime_debug["parental_wait_started_at"] = time.monotonic()
        with self._lock:
            if self._guard:
                self._guard.cooldown_s = values["guard_cooldown_s"]
                self._guard.stable_s = values["guard_stable_s"]

    @staticmethod
    def _stripmine_family(provider):
        if provider.startswith("artwork"):
            return "artwork"
        if provider.startswith("performance"):
            return "performance"
        if provider.startswith("weather"):
            return "weather"
        if provider.startswith("controller"):
            return "controller"
        if provider.startswith("event:"):
            return "light_events"
        return "system"

    @classmethod
    def _stripmine_priority(cls, provider, values):
        if provider in {"none", "valve", "idle"}:
            return "stripmine"
        family = cls._stripmine_family(provider)
        if family == "system":
            # Countdowns and unknown safety providers keep SignalBar priority.
            return "signalbar"
        return values.get(f"stripmine_priority_{family}", "stripmine")

    def _run(self):
        hardware = None
        renderer = None
        guard = None
        interval = 0.10
        event_was_active = False
        event_preempted_valve = False
        next_hardware_attempt = 0.0
        while not self._stop.is_set():
            # Telemetry must not depend on LED ownership, hardware availability,
            # the chosen display, or whether a Decky panel is open.
            self.performance.refresh(self.settings.all()["performance_smoothing"])
            if hardware is None:
                if time.monotonic() < next_hardware_attempt:
                    self._stop.wait(0.1)
                    continue
                try:
                    hardware = self.hardware_factory()
                    values = self.settings.all()
                    renderer = Renderer(hardware)
                    guard = VanillaGuard(values["guard_cooldown_s"], values["guard_stable_s"])
                    with self._lock:
                        self._renderer, self._guard = renderer, guard
                        self._available = True
                        self._error = ""
                        self._suspension_reason = "startup settle"
                    self._info("17 valve-leds detected; conservative startup settle begun")
                except Exception as error:
                    with self._lock:
                        self._available = False
                        self._error = str(error)
                        self._suspension_reason = "hardware unavailable; retrying"
                    next_hardware_attempt = time.monotonic() + 2.0
                    continue

            if self._stop.wait(interval):
                break
            try:
                now = time.monotonic()
                values = self.settings.all()
                if hardware.reverse != values["reverse_led_order"]:
                    # Restore with the old mapping before changing orientation;
                    # otherwise a later shutdown would restore the snapshot backwards.
                    if renderer.last_frame is not None:
                        renderer.relinquish(restore_if_owned=True)
                    hardware.set_reverse(values["reverse_led_order"])
                with self._lock:
                    game = self._game
                    explicit = now < self._steam_active_until
                    explicit_reason = self._steam_reason
                values["mode"] = self.settings.display_for(game.appid)["mode"]
                signature = hardware.read_signature()
                # A new native write during our animation ends that animation
                # immediately; otherwise the two writers would fight each tick.
                event_interrupted = (
                    event_was_active and renderer.last_signature is not None
                    and signature != renderer.last_signature
                )
                allowed = guard.observe(
                    signature,
                    expected_signature=renderer.last_signature,
                    explicit_active=explicit,
                    explicit_reason=explicit_reason,
                )
                stripmine_active = (
                    values["stripmine_integration_enabled"]
                    and self.stripmine_claim.active()
                )
                performance = self.performance.output(
                    metric=values["performance_metric"],
                    cool_c=values["cool_temp_c"],
                    hot_c=values["hot_temp_c"],
                    palette=values["temperature_palette"],
                    direction=values["mixed_direction"],
                    dark_edge_compensation=values["countdown_dark_edge_compensation"],
                    smoothing=values["performance_smoothing"],
                    enabled=(values["mode"] == "performance"),
                    custom_palette=(
                        values["temperature_custom_cool"],
                        values["temperature_custom_middle"],
                        values["temperature_custom_hot"],
                    ),
                )
                artwork = self.artwork.output(game.appid)
                signal = self.countdown.output(
                    colour=values["countdown_colour"],
                    dark_edge_compensation=values["countdown_dark_edge_compensation"],
                    full_bar_seconds=values["countdown_full_bar_minutes"] * 60.0,
                    allow_parental=(
                        values["parental_countdown_enabled"] and game.running
                    ),
                )
                countdown_state = self.countdown.status(
                    allow_parental=values["parental_countdown_enabled"] and game.running,
                )
                signal_critical = (
                    countdown_state["active"] and countdown_state["remaining_seconds"] <= 300
                )
                if signal_critical:
                    self.events.clear_transients()
                    self.controllers.clear_transients()
                if event_interrupted:
                    self.events.clear_transients()
                    self.controllers.clear_transients()
                event = self.events.output()
                controller_event = self.controllers.event_output()
                controller_base = self.controllers.persistent_output(values, game.running)
                weather_base = self.weather.output(values, game.running, now)
                # Moving event waves need more than ten samples per second to
                # visibly visit all 17 positions. Normal providers stay at
                # the conservative 10 Hz cadence.
                interval = 0.06 if event.frame is not None or controller_event.frame is not None else 0.10
                decision = self.arbiter.choose(
                    mode=values["mode"], guard_allows=allowed or stripmine_active, game=game,
                    performance=performance, artwork=artwork, idle=self.idle.output(),
                    signal=signal, event=event, signal_critical=signal_critical,
                    controller_event=controller_event, controller_base=controller_base,
                    weather_base=weather_base,
                    recording_marker=(
                        self.events.recording and values["events_enabled"]
                        and values["event_recording_enabled"]
                    ),
                    recording_marker_isolation=values["recording_marker_isolation"],
                    performance_always=values["performance_always"],
                )

                stripmine_priority = self._stripmine_priority(decision.provider, values)
                yield_to_stripmine = stripmine_active and stripmine_priority == "stripmine"
                take_from_stripmine = stripmine_active and stripmine_priority == "signalbar"
                if stripmine_active and not yield_to_stripmine:
                    self.stripmine_claim.acknowledge(stripmine_priority, decision.provider)

                is_light_event = decision.provider.startswith("event:")
                needs_handoff = (is_light_event and not yield_to_stripmine) or take_from_stripmine
                if needs_handoff:
                    # Publish before the first LED write so StripMine can yield
                    # without treating this short, intentional takeover as a conflict.
                    self.event_lease.refresh(
                        decision.provider,
                        "light-event" if is_light_event else "priority-output",
                    )
                    if not self._light_event_announced_at:
                        self._light_event_announced_at = now
                    handoff_ready = (
                        self.event_lease.acknowledged()
                        or is_light_event and now - self._light_event_announced_at >= 0.10
                    )
                else:
                    self._light_event_announced_at = 0.0
                    handoff_ready = True
                if yield_to_stripmine:
                    if renderer.last_frame is not None:
                        renderer.relinquish(restore_if_owned=True)
                    # Grant StripMine ownership only after every possible
                    # restore write has completed. On the physical 17-LED
                    # sysfs device a restore is sequential; acknowledging
                    # first lets StripMine resume in the middle of it and
                    # misclassify our remaining writes as a third-party app.
                    self.stripmine_claim.acknowledge(stripmine_priority, decision.provider)
                    event_was_active = False
                    event_preempted_valve = False
                    owner = "Valve"
                    suspension = f"StripMine priority over {self._stripmine_family(decision.provider)}"
                elif needs_handoff and not handoff_ready:
                    # Keep the current frame untouched until StripMine confirms
                    # it has stopped writing. A short timeout preserves normal
                    # events when no compatible companion is installed.
                    event_was_active = False
                    event_preempted_valve = False
                    owner = self._owner
                    suspension = "waiting for companion LED handoff"
                elif decision.frame is not None:
                    is_event = decision.provider.startswith(("event:", "controller:"))
                    if is_event and not allowed:
                        event_preempted_valve = True
                    elif not is_event:
                        event_preempted_valve = False
                    wrote = renderer.render(decision.frame)
                    if wrote:
                        guard.note_own_write(renderer.last_signature)
                    owner = "SignalBar"
                    suspension = ""
                    event_was_active = is_event
                else:
                    externally_blocked = decision.provider == "valve"
                    if renderer.last_frame is not None:
                        # After a short event over a stable Valve frame, put
                        # that exact frame back. Renderer verifies ownership
                        # first, so a concurrent native write is never undone.
                        renderer.relinquish(
                            restore_if_owned=not externally_blocked or event_preempted_valve
                        )
                    event_was_active = False
                    event_preempted_valve = False
                    owner = "Valve"
                    suspension = guard.reason if externally_blocked else decision.reason
                if not needs_handoff or yield_to_stripmine:
                    # Relinquish/restore happens above; only then tell StripMine
                    # that it may safely reclaim its continuously animated bar.
                    self.event_lease.release()

                with self._lock:
                    # Do not report the event as physically active while the
                    # cooperative handoff is still pending. Besides being more
                    # truthful in diagnostics, this prevents callers from
                    # racing a native write against SignalBar's first frame.
                    self._decision = (
                        "companion:handoff"
                        if needs_handoff and not handoff_ready
                        else "companion:stripmine"
                        if yield_to_stripmine
                        else decision.provider
                    )
                    self._owner = owner
                    self._suspension_reason = suspension
                    self._error = ""
            except Exception as error:
                renderer.relinquish(restore_if_owned=False)
                self.event_lease.release()
                self.stripmine_claim.release()
                self._light_event_announced_at = 0.0
                with self._lock:
                    self._owner = "Valve"
                    self._decision = "none"
                    self._suspension_reason = "renderer failure; yielded to Valve"
                    self._error = str(error)
                self._warn(f"render loop stopped after failure: {error}")
                return

        if renderer is not None:
            renderer.relinquish(restore_if_owned=True)
        self.stripmine_claim.release()

    def status(self):
        values = self.settings.all()
        now = time.monotonic()
        stripmine_detected = (
            values["stripmine_integration_enabled"]
            and self.stripmine_claim.active()
        )
        sample = self.performance.sample
        art = self.artwork.status()
        with self._lock:
            display = self.settings.display_for(self._game.appid)
            values["mode"] = display["mode"]
            artwork_settings = self.settings.artwork_for(self._game.appid)
            countdown = self.countdown.status(
                colour=values["countdown_colour"],
                dark_edge_compensation=values["countdown_dark_edge_compensation"],
                full_bar_seconds=values["countdown_full_bar_minutes"] * 60.0,
                allow_parental=(
                    values["parental_countdown_enabled"] and self._game.running
                ),
            )
            renderer = self._renderer
            guard = self._guard
            last_write_at = renderer.last_successful_write_at if renderer else 0.0
            last_external_at = guard.last_external_at if guard else 0.0
            guard_debug = guard.debug_status() if guard else {
                "ready": False,
                "reason": "not initialized",
                "cooldown_remaining": 0.0,
                "stable_remaining": 0.0,
            }
            runtime_debug = dict(self._runtime_debug)
            wait_started = runtime_debug.pop("parental_wait_started_at", 0.0)
            controller_last_update_at = runtime_debug.pop("controller_last_update_at", 0.0)
            runtime_debug["controller_last_update_age_s"] = (
                max(0.0, now - controller_last_update_at) if controller_last_update_at else None
            )
            runtime_debug["parental_wait_s"] = (
                max(0.0, now - wait_started) if wait_started else None
            )
            logical_performance = self.performance.frame(
                metric=values["performance_metric"],
                cool_c=values["cool_temp_c"],
                hot_c=values["hot_temp_c"],
                palette=values["temperature_palette"],
                direction=values["mixed_direction"],
                dark_edge_compensation=0,
                custom_palette=(
                    values["temperature_custom_cool"],
                    values["temperature_custom_middle"],
                    values["temperature_custom_hot"],
                ),
            )
            physical_performance = self.performance.frame(
                metric=values["performance_metric"],
                cool_c=values["cool_temp_c"],
                hot_c=values["hot_temp_c"],
                palette=values["temperature_palette"],
                direction=values["mixed_direction"],
                dark_edge_compensation=values["countdown_dark_edge_compensation"],
                custom_palette=(
                    values["temperature_custom_cool"],
                    values["temperature_custom_middle"],
                    values["temperature_custom_hot"],
                ),
            )
            controller_status = self.controllers.status(values, self._game.running)
            weather_status = self.weather.status(values, self._game.running)
            return {
                "version": __version__,
                "available": self._available,
                "active": self._owner == "SignalBar",
                "owner": self._owner,
                "provider": self._decision,
                "suspension_reason": self._suspension_reason,
                "error": self._error,
                "mode": values["mode"],
                "default_mode": display["default"],
                "display_override": display["override"],
                "performance_metric": values["performance_metric"],
                "performance_smoothing": values["performance_smoothing"],
                "performance_always": values["performance_always"],
                "mixed_direction": values["mixed_direction"],
                "temperature_palette": values["temperature_palette"],
                "temperature_custom_cool": values["temperature_custom_cool"],
                "temperature_custom_middle": values["temperature_custom_middle"],
                "temperature_custom_hot": values["temperature_custom_hot"],
                "artwork_mode": artwork_settings["mode"],
                "artwork_manual_y": artwork_settings["manual_y"],
                "artwork_source": artwork_settings["source"],
                "artwork_custom": artwork_settings["custom"],
                "artwork_default_mode": values["artwork_mode"],
                "artwork_default_manual_y": values["artwork_manual_y"],
                "artwork_default_source": values["artwork_source"],
                "cool_temp_c": values["cool_temp_c"],
                "hot_temp_c": values["hot_temp_c"],
                "reverse_led_order": values["reverse_led_order"],
                "parental_countdown_enabled": values["parental_countdown_enabled"],
                "countdown_colour": values["countdown_colour"],
                "countdown_full_bar_minutes": values["countdown_full_bar_minutes"],
                "countdown_dark_edge_compensation": values["countdown_dark_edge_compensation"],
                "free_timer_minutes": values["free_timer_minutes"],
                "events_enabled": values["events_enabled"],
                "event_notifications_enabled": values["event_notifications_enabled"],
                "event_achievements_enabled": values["event_achievements_enabled"],
                "event_screenshots_enabled": values["event_screenshots_enabled"],
                "event_recording_enabled": values["event_recording_enabled"],
                "recording_marker_isolation": values["recording_marker_isolation"],
                "event_notification_variant": values["event_notification_variant"],
                "event_achievement_variant": values["event_achievement_variant"],
                "event_screenshot_variant": values["event_screenshot_variant"],
                "controller_battery_display": values["controller_battery_display"],
                "controller_charging_mode": values["controller_charging_mode"],
                "controller_charging_display": values["controller_charging_display"],
                "controller_alert_context": values["controller_alert_context"],
                "controller_alerts_enabled": values["controller_alerts_enabled"],
                "controller_connect_enabled": values["controller_connect_enabled"],
                "controller_low_enabled": values["controller_low_enabled"],
                "controller_charging_enabled": values["controller_charging_enabled"],
                "controller_low_threshold": values["controller_low_threshold"],
                "controller_connect_variant": values["controller_connect_variant"],
                "controller_persistent_variant": values["controller_persistent_variant"],
                "controller_low_variant": values["controller_low_variant"],
                "controller_charging_variant": values["controller_charging_variant"],
                "controller_duo_variant": values["controller_duo_variant"],
                "controller_colour_normal": values["controller_colour_normal"],
                "controller_colour_medium": values["controller_colour_medium"],
                "controller_colour_low": values["controller_colour_low"],
                "controller_colour_charging": values["controller_colour_charging"],
                "controller_gauge_brightness": values["controller_gauge_brightness"],
                "weather_display": values["weather_display"],
                "weather_location": values["weather_location"],
                "weather_topbar_enabled": values["weather_topbar_enabled"],
                "weather_temperature_unit": values["weather_temperature_unit"],
                "weather_brightness": values["weather_brightness"],
                "weather_shadow_cutoff": values["weather_shadow_cutoff"],
                "stripmine_integration_enabled": values["stripmine_integration_enabled"],
                "stripmine_detected": stripmine_detected,
                "stripmine_priority_artwork": values["stripmine_priority_artwork"],
                "stripmine_priority_performance": values["stripmine_priority_performance"],
                "stripmine_priority_weather": values["stripmine_priority_weather"],
                "stripmine_priority_controller": values["stripmine_priority_controller"],
                "stripmine_priority_light_events": values["stripmine_priority_light_events"],
                **{key: values[key] for key in values if key.startswith("weather_") and key.endswith("_variant")},
                "weather": weather_status,
                "controllers": controller_status,
                "events": self.events.status(),
                "game": {"appid": self._game.appid, "title": self._game.title},
                "performance": {
                    "sample_age_s": max(0.0, now - sample.sampled_at) if sample.sampled_at else None,
                    "error": self.performance.error,
                    "gpu_load": sample.gpu_load,
                    "gpu_temperature": sample.gpu_temp_c,
                    "cpu_load": sample.cpu_load,
                    "cpu_temperature": sample.cpu_temp_c,
                    "logical_lit": sum(pixel != (0, 0, 0) for pixel in logical_performance),
                    "physical_lit": sum(pixel != (0, 0, 0) for pixel in physical_performance),
                },
                "artwork": art,
                "countdown": countdown,
                "debug": {
                    "led_path": renderer.hardware.device_path if renderer else "/sys/class/leds/valve-leds[*]",
                    "last_write": renderer.last_write_at if renderer else 0.0,
                    "last_write_age_s": max(0.0, now - last_write_at) if last_write_at else None,
                    "writes": renderer.writes if renderer else 0,
                    "last_external": guard.last_external_at if guard else 0.0,
                    "last_external_age_s": max(0.0, now - last_external_at) if last_external_at else None,
                    "cooldown_remaining": guard_debug["cooldown_remaining"],
                    "stable_remaining": guard_debug["stable_remaining"],
                    "guard_state": "ready" if guard_debug["ready"] else "blocked",
                    "guard_reason": guard_debug["reason"],
                    "reverse_led_order": values["reverse_led_order"],
                    **runtime_debug,
                },
            }
