"""The Witcher 3 HUD provider and bounded WitcherScript telemetry bridge.

The game-side mod overwrites a small state INI in the Proton Documents folder
and also emits prefixed ``scriptlog.txt`` records as a diagnostic fallback.
Both transports feed real HUD values through GabeCubeAura's normal arbiter,
StripMine handoff and renderer. Manual values remain an installation fallback.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import threading
import time

from signalbar.models import ProviderOutput, normalize_frame


WITCHER3_APP_ID = 292030
BLACK = (0, 0, 0)
SIGN_COLOURS = {
    "aard": (158, 214, 255),
    "axii": (255, 255, 255),
    "igni": (255, 79, 10),
    "quen": (255, 205, 68),
    "yrden": (200, 81, 255),
}
SIGN_DURATION_S = 0.9
TELEMETRY_MARKER = "GCA1|"
TELEMETRY_FRESH_S = 1.5
TELEMETRY_STATE_FILE = "GabeCubeAuraTelemetry.ini"


def _unique_paths(paths):
    result = []
    seen = set()
    for path in paths:
        path = Path(path)
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _witcher_steamapps(home=None):
    homes = [Path(home or os.environ.get("HOME") or "/home/deck"), Path("/home/deck")]
    steamapps = []
    for user_home in _unique_paths(homes):
        steamapps.extend((
            user_home / ".local/share/Steam/steamapps",
            user_home / ".steam/steam/steamapps",
        ))
        for vdf in (
            user_home / ".local/share/Steam/steamapps/libraryfolders.vdf",
            user_home / ".steam/steam/steamapps/libraryfolders.vdf",
        ):
            try:
                for line in vdf.read_text(encoding="utf-8", errors="replace").splitlines():
                    if '"path"' not in line:
                        continue
                    parts = line.split('"')
                    if len(parts) >= 4:
                        steamapps.append(Path(parts[3].replace("\\\\", "/")) / "steamapps")
            except OSError:
                pass
    media = Path("/run/media/deck")
    try:
        steamapps.extend(path / "steamapps" for path in media.iterdir() if path.is_dir())
    except OSError:
        pass
    return _unique_paths(steamapps)


def witcher_log_candidates(home=None):
    """Return bounded Steam/Proton log locations without crawling the filesystem."""
    # WitcherScript's LogChannel writes to ``scriptlog.txt`` (singular).
    # Keep the former plural spelling as a last-resort compatibility candidate
    # so a user-created redirect from an earlier beta remains harmless.
    suffixes = tuple(
        Path(f"pfx/drive_c/users/steamuser/{documents}/The Witcher 3/{filename}")
        for filename in ("scriptlog.txt", "scriptslog.txt")
        for documents in ("Documents", "My Documents")
    )
    return _unique_paths(
        root / "compatdata" / str(WITCHER3_APP_ID) / suffix
        for root in _witcher_steamapps(home)
        for suffix in suffixes
    )


def witcher_state_candidates(home=None):
    """Return the direct WitcherScript state-file transport locations."""
    suffixes = tuple(
        Path(f"pfx/drive_c/users/steamuser/{documents}/The Witcher 3/{TELEMETRY_STATE_FILE}")
        for documents in ("Documents", "My Documents")
    )
    return _unique_paths(
        root / "compatdata" / str(WITCHER3_APP_ID) / suffix
        for root in _witcher_steamapps(home)
        for suffix in suffixes
    )


def parse_telemetry_line(line):
    """Parse one namespaced record; unrelated game logging is ignored."""
    if TELEMETRY_MARKER not in str(line):
        return None
    payload = str(line).split(TELEMETRY_MARKER, 1)[1].strip()
    fields = {}
    for item in payload.split("|"):
        if "=" in item:
            key, value = item.split("=", 1)
            fields[key.strip().lower()] = value.strip()
    kind = fields.get("kind")
    if kind == "sign":
        sign = fields.get("sign", "").lower()
        return {"kind": "sign", "sign": sign} if sign in SIGN_COLOURS else None
    if kind != "state":
        return None
    try:
        values = {key: float(fields[key]) for key in (
            "health", "health_max", "stamina", "stamina_max",
            "toxicity", "toxicity_max", "adrenaline",
        )}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in values.values()):
        return None

    def percent(value, maximum):
        return 0.0 if maximum <= 0 else max(0.0, min(100.0, value * 100.0 / maximum))

    return {
        "kind": "state",
        "health": percent(values["health"], values["health_max"]),
        "stamina": percent(values["stamina"], values["stamina_max"]),
        "toxicity": percent(values["toxicity"], values["toxicity_max"]),
        "adrenaline": max(0, min(3, int(math.floor(values["adrenaline"] + 0.001)))),
        "combat": fields.get("combat", "0") == "1",
    }


def parse_telemetry_state_file(text):
    """Parse the bounded overwrite-style INI transport written by the mod."""
    fields = {}
    for raw_line in str(text or "").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("[", ";", "#")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        fields[key.strip().lower()] = value
    state = parse_telemetry_line(fields.get("state", ""))
    sign = parse_telemetry_line(fields.get("sign", ""))
    return {
        "state": state if state and state.get("kind") == "state" else None,
        "state_stamp": fields.get("state_stamp", ""),
        "sign": sign.get("sign", "") if sign and sign.get("kind") == "sign" else "",
        "sign_stamp": fields.get("sign_stamp", ""),
    }


class WitcherTelemetryReader:
    """Incrementally tail telemetry emitted inside the AppID 292030 prefix."""

    def __init__(self, candidates=None, state_candidates=None,
                 clock=time.monotonic, wall_clock=time.time):
        self.candidates = [Path(path) for path in candidates] if candidates is not None else None
        self.state_candidates = (
            [Path(path) for path in state_candidates]
            if state_candidates is not None
            else [] if candidates is not None else None
        )
        self.clock = clock
        self.wall_clock = wall_clock
        self.path = None
        self.transport = ""
        self.log_path = None
        self.state_path = None
        self.offset = 0
        self.identity = None
        self.last_state = None
        self.last_update_at = 0.0
        self.last_sign = ""
        self.error = ""
        self._next_discovery_at = 0.0
        self._last_sign_stamp = ""

    @staticmethod
    def _freshest_existing(paths, current=None):
        """Prefer the live prefix when stale files exist in old Steam libraries."""
        candidates = list(paths or ())
        if current is not None and current not in candidates:
            candidates.append(current)
        existing = []
        for path in candidates:
            path = Path(path)
            try:
                stat = path.stat()
            except OSError:
                continue
            if path.is_file():
                existing.append((stat.st_mtime_ns, path))
        return max(existing, default=(0, None), key=lambda item: item[0])[1]

    def _discover(self, now):
        log_path = self.log_path if self.log_path and self.log_path.is_file() else None
        state_path = self.state_path if self.state_path and self.state_path.is_file() else None
        if now < self._next_discovery_at:
            return log_path, state_path
        self._next_discovery_at = now + 2.0
        discovered_log = self._freshest_existing(
            self.candidates if self.candidates is not None else witcher_log_candidates(),
            log_path,
        )
        if discovered_log != self.log_path:
            self.log_path = discovered_log
            self.offset = 0
            self.identity = None
        log_path = discovered_log
        discovered_state = self._freshest_existing(
            self.state_candidates
            if self.state_candidates is not None else witcher_state_candidates(),
            state_path,
        )
        self.state_path = discovered_state
        state_path = discovered_state
        return log_path, state_path

    def _poll_state_file(self, path, now):
        if path is None:
            return None, ""
        stat = path.stat()
        if stat.st_size > 65536:
            raise OSError("GabeCubeAuraTelemetry.ini exceeds 64 KiB")
        fresh = self.wall_clock() - stat.st_mtime <= TELEMETRY_FRESH_S
        if not fresh:
            return None, ""
        parsed = parse_telemetry_state_file(path.read_text(encoding="utf-8", errors="replace"))
        state = parsed["state"]
        sign = ""
        sign_stamp = parsed["sign_stamp"] or parsed["sign"]
        if parsed["sign"] and sign_stamp and sign_stamp != self._last_sign_stamp:
            sign = parsed["sign"]
            self._last_sign_stamp = sign_stamp
        if state is not None:
            self.last_state = state
            self.last_update_at = now
        return state, sign

    def _poll_log(self, path, now):
        if path is None:
            return None, ""
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity != self.identity or stat.st_size < self.offset:
            self.identity = identity
            self.offset = max(0, stat.st_size - 65536)
        if stat.st_size - self.offset > 131072:
            self.offset = stat.st_size - 131072
        with path.open("rb") as stream:
            stream.seek(self.offset)
            chunk = stream.read(131072)
            self.offset = stream.tell()
        if not chunk:
            return None, ""
        state = None
        sign = ""
        for line in chunk.decode("utf-8", errors="replace").splitlines():
            record = parse_telemetry_line(line)
            if not record:
                continue
            if record["kind"] == "state":
                state = record
            elif record["kind"] == "sign":
                sign = record["sign"]
        fresh = self.wall_clock() - stat.st_mtime <= TELEMETRY_FRESH_S
        if state is not None and fresh:
            self.last_state = state
            self.last_update_at = now
        elif not fresh:
            state = None
            sign = ""
        return state, sign

    def poll(self, appid):
        now = self.clock()
        self.last_sign = ""
        if int(appid or 0) != WITCHER3_APP_ID:
            return None, ""
        log_path, state_path = self._discover(now)
        if log_path is None and state_path is None:
            self.error = ""
            return None, ""

        errors = []
        state = None
        sign = ""
        log_state = None
        log_sign = ""
        try:
            state, sign = self._poll_state_file(state_path, now)
        except OSError as error:
            errors.append(f"state file: {error}")
            if self.state_path and not self.state_path.is_file():
                self.state_path = None
        state_file_state = state
        try:
            log_state, log_sign = self._poll_log(log_path, now)
        except OSError as error:
            errors.append(f"script log: {error}")
            if self.log_path and not self.log_path.is_file():
                self.log_path = None
            self.identity = None
            self.offset = 0

        if state is None and log_state is not None:
            state = log_state
        if not sign and log_sign:
            sign = log_sign
        if sign:
            self.last_sign = sign
        if state_file_state is not None:
            self.path = state_path
            self.transport = "state-file"
        elif log_state is not None:
            self.path = log_path
            self.transport = "script-log"
        self.error = "; ".join(errors)
        return state, sign

    def status(self):
        age = max(0.0, self.clock() - self.last_update_at) if self.last_update_at else None
        log_candidates = self.candidates or witcher_log_candidates()
        state_candidates = (
            self.state_candidates if self.state_candidates is not None else witcher_state_candidates()
        )
        active_path = self.state_path if self.transport == "state-file" else self.path
        return {
            "connected": age is not None and age <= TELEMETRY_FRESH_S,
            "age_s": age,
            "path": str(active_path) if active_path else "",
            "transport": self.transport,
            "candidate_count": len(log_candidates) + len(state_candidates),
            "expected_path": str(state_candidates[0]) if state_candidates else (
                str(log_candidates[0]) if log_candidates else ""
            ),
            "log_candidates": [str(path) for path in log_candidates],
            "state_candidates": [str(path) for path in state_candidates],
            "error": self.error,
        }


def _percentage(value, fallback):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if not math.isfinite(value):
        return fallback
    return max(0.0, min(100.0, value))


def _adrenaline(value, fallback):
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback
    return max(0, min(3, value))


def vitals_frame(health=100, stamina=100, toxicity=0, adrenaline=0,
                 combat=False, elapsed_seconds=0.0):
    """Render two separated eight-pixel gauges and a central adrenaline marker."""
    health = _percentage(health, 100.0)
    stamina = _percentage(stamina, 100.0)
    toxicity = _percentage(toxicity, 0.0)
    adrenaline = _adrenaline(adrenaline, 0)
    pixels = [BLACK] * 17

    health_lit = int(math.ceil(health * 8.0 / 100.0)) if health > 0 else 0
    stamina_lit = int(math.ceil(stamina * 8.0 / 100.0)) if stamina > 0 else 0
    health_brightness = 205 if combat else 155
    if combat and 0 < health <= 25:
        health_brightness = int(round(
            125 + 65 * (0.5 + 0.5 * math.sin(elapsed_seconds * math.pi * 2))
        ))
    for index in range(health_lit):
        pixels[index] = (health_brightness, 10, 8)
    for offset in range(stamina_lit):
        pixels[16 - offset] = (190, 130, 18)

    if adrenaline:
        brightness = (75, 135, 205)[adrenaline - 1]
        pixels[8] = (brightness, int(brightness * 0.48), 8)

    toxic_edges = int(math.ceil(toxicity * 4.0 / 100.0)) if toxicity > 0 else 0
    toxic_green = int(round(85 + toxicity * 1.1))
    for index in range(toxic_edges):
        pixels[index] = (20, toxic_green, 22)
        pixels[16 - index] = (20, toxic_green, 22)
    return normalize_frame(pixels)


def sign_frame(sign, elapsed_seconds):
    """Run a short centre-out wave using the game's controller-light colours."""
    colour = SIGN_COLOURS.get(str(sign or "").lower())
    if colour is None or elapsed_seconds < 0 or elapsed_seconds >= SIGN_DURATION_S:
        return None
    radius = min(8, int(elapsed_seconds / SIGN_DURATION_S * 10))
    pixels = [BLACK] * 17
    for distance, scale in ((radius, 1.0), (radius - 1, 0.42)):
        if distance < 0:
            continue
        for index in {8 - distance, 8 + distance}:
            if 0 <= index < 17:
                pixels[index] = tuple(int(round(channel * scale)) for channel in colour)
    return normalize_frame(pixels)


class WitcherLabProvider:
    name = "witcher-lab"

    def __init__(self, clock=time.monotonic, telemetry_reader=None, installer=None):
        self.clock = clock
        self._lock = threading.RLock()
        self.enabled = False
        self.health = 100.0
        self.stamina = 100.0
        self.toxicity = 0.0
        self.adrenaline = 0
        self.combat = False
        self.sign = ""
        self.sign_started_at = 0.0
        self.auto_managed = False
        self.runtime_verified_session = False
        self._soft_resume_verified = False
        self.telemetry = telemetry_reader or WitcherTelemetryReader(clock=clock)
        self.installer = installer

    @staticmethod
    def _unavailable_installation():
        return {
            "state": "unavailable", "installed": False,
            "game_found": False, "source_found": False,
            "game_path": "", "target_path": "", "legacy_target_path": "", "backup_path": "",
            "preserved_path": "", "last_action": "",
            "logging": {
                "launch_options": {
                    "state": "unknown", "has_net": False,
                    "has_debugscripts": False, "path": "",
                },
                "force_flush": {"state": "unknown", "path": ""},
            },
            "error": "Witcher telemetry installer is unavailable",
        }

    def installation_status(self):
        if self.installer is None:
            return self._unavailable_installation()
        try:
            return self.installer.status()
        except Exception as error:
            status = self._unavailable_installation()
            status.update({"state": "error", "error": str(error)})
            return status

    def sync_game_lifecycle(self, appid, session_transition="steady"):
        """Bind a checksum-verified bridge to the lifetime of AppID 292030.

        Matching the packaged checksum proves only that the expected file was
        copied, so it is sufficient to arm automatic session management but not
        to render HUD values. Physical Witcher output starts only after the
        current session has produced a real namespaced telemetry record. This
        prevents an installed but non-functional Remastered script from silently
        taking the bar with static fallback values.
        """
        eligible = int(appid or 0) == WITCHER3_APP_ID
        installation = self.installation_status()
        file_verified = bool(installation.get("installed"))
        with self._lock:
            transition = str(session_transition or "steady")
            if transition == "soft-stop":
                # Steam's running-app collection can disappear while the game
                # itself is still alive (the QAM/overlay is a common case).
                # Stop writing immediately, but retain the already-proven
                # bridge so a poll fallback can resume the same session.
                self._soft_resume_verified = bool(self.runtime_verified_session)
            elif transition == "soft-resume" and eligible and file_verified:
                if self._soft_resume_verified:
                    self.runtime_verified_session = True
                self._soft_resume_verified = False
            elif transition == "hard-transition":
                self._soft_resume_verified = False

            if not file_verified:
                self._soft_resume_verified = False
                self.runtime_verified_session = False
            elif not eligible:
                self.runtime_verified_session = False
            was_auto_managed = self.auto_managed
            self.auto_managed = bool(eligible and file_verified)
            if self.auto_managed:
                self.enabled = True
            elif not eligible or was_auto_managed:
                self.enabled = False
                self.sign = ""
                self.sign_started_at = 0.0
            return self.auto_managed

    def refresh_telemetry(self, appid):
        state, sign = self.telemetry.poll(appid)
        received = bool(state or sign)
        with self._lock:
            if int(appid or 0) != WITCHER3_APP_ID:
                self.runtime_verified_session = False
            elif received:
                self.runtime_verified_session = True
            if state:
                self.health = _percentage(state["health"], self.health)
                self.stamina = _percentage(state["stamina"], self.stamina)
                self.toxicity = _percentage(state["toxicity"], self.toxicity)
                self.adrenaline = _adrenaline(state["adrenaline"], self.adrenaline)
                self.combat = bool(state["combat"])
            if sign and self.enabled:
                self.sign = sign
                self.sign_started_at = self.clock()
        if received:
            self.sync_game_lifecycle(appid)
        return received

    def update(self, values):
        if not isinstance(values, dict):
            raise ValueError("Witcher lab state must be an object")
        with self._lock:
            if "enabled" in values:
                # A verified bridge follows the game's lifetime. The UI may
                # still update manual values, but it cannot accidentally leave
                # the automatic laboratory switched off while the game runs.
                self.enabled = True if self.auto_managed else bool(values["enabled"])
            if "health" in values:
                self.health = _percentage(values["health"], self.health)
            if "stamina" in values:
                self.stamina = _percentage(values["stamina"], self.stamina)
            if "toxicity" in values:
                self.toxicity = _percentage(values["toxicity"], self.toxicity)
            if "adrenaline" in values:
                self.adrenaline = _adrenaline(values["adrenaline"], self.adrenaline)
            if "combat" in values:
                self.combat = bool(values["combat"])
            if not self.enabled:
                self.sign = ""
                self.sign_started_at = 0.0

    def trigger_sign(self, sign):
        sign = str(sign or "").lower()
        if sign not in SIGN_COLOURS:
            raise ValueError("Unknown Witcher sign")
        with self._lock:
            if not self.enabled:
                return False
            self.sign = sign
            self.sign_started_at = self.clock()
            return True

    def stop(self):
        with self._lock:
            self.enabled = False
            self.auto_managed = False
            self.runtime_verified_session = False
            self._soft_resume_verified = False
            self.sign = ""
            self.sign_started_at = 0.0

    def stop_manual(self):
        with self._lock:
            if self.auto_managed:
                return False
            self.enabled = False
            self.sign = ""
            self.sign_started_at = 0.0
            return True

    def install_telemetry_mod(self):
        if self.installer is None:
            raise RuntimeError("Witcher telemetry installer is unavailable")
        return self.installer.install()

    def remove_telemetry_mod(self):
        if self.installer is None:
            raise RuntimeError("Witcher telemetry installer is unavailable")
        return self.installer.remove()

    def _frames_locked(self, now):
        base = vitals_frame(
            self.health, self.stamina, self.toxicity, self.adrenaline,
            self.combat, now,
        )
        transient = sign_frame(self.sign, now - self.sign_started_at) if self.sign_started_at else None
        if self.sign_started_at and transient is None:
            self.sign = ""
            self.sign_started_at = 0.0
        return base, transient

    def output(self, appid):
        now = self.clock()
        with self._lock:
            base, transient = self._frames_locked(now)
            if not self.enabled:
                return ProviderOutput(self.name, None, "Witcher lab disabled")
            if int(appid or 0) != WITCHER3_APP_ID:
                return ProviderOutput(self.name, None, "The Witcher 3 is not the running game")
            if self.auto_managed and not self.runtime_verified_session:
                return ProviderOutput(
                    self.name, None,
                    "Automatic Witcher session waiting for first live GCA1 telemetry",
                )
            if transient is not None:
                return ProviderOutput(
                    "witcher-lab:sign", transient,
                    f"{'Live' if self.telemetry.status()['connected'] else 'Simulated'} {self.sign.title()} cast",
                )
            description = (
                "Live WitcherScript HUD telemetry"
                if self.telemetry.status()["connected"]
                else "Manual Witcher HUD simulation"
            )
            return ProviderOutput(self.name, base, description)

    def status(self, appid):
        now = self.clock()
        telemetry = self.telemetry.status()
        installation = self.installation_status()
        with self._lock:
            base, transient = self._frames_locked(now)
            eligible = int(appid or 0) == WITCHER3_APP_ID
            remaining = (
                max(0.0, SIGN_DURATION_S - (now - self.sign_started_at))
                if self.sign_started_at else 0.0
            )
            return {
                "enabled": self.enabled,
                "auto_managed": self.auto_managed,
                "runtime_verified_session": self.runtime_verified_session,
                "runtime_resume_pending": self._soft_resume_verified,
                "eligible": eligible,
                "active": self.enabled and eligible,
                "health": self.health,
                "stamina": self.stamina,
                "toxicity": self.toxicity,
                "adrenaline": self.adrenaline,
                "combat": self.combat,
                "sign": self.sign,
                "sign_remaining_s": remaining,
                "colors": [list(pixel) for pixel in (transient or base)],
                "telemetry_connected": telemetry["connected"],
                "telemetry_age_s": telemetry["age_s"],
                "telemetry_path": telemetry["path"],
                "telemetry_transport": telemetry.get("transport", ""),
                "telemetry_candidate_count": telemetry.get("candidate_count", 0),
                "telemetry_expected_path": telemetry.get("expected_path", ""),
                "telemetry_log_candidates": telemetry.get("log_candidates", []),
                "telemetry_state_candidates": telemetry.get("state_candidates", []),
                "telemetry_error": telemetry["error"],
                "source": "live" if telemetry["connected"] else "manual",
                "installation": installation,
                "reason": (
                    "live WitcherScript telemetry" if eligible and telemetry["connected"]
                    else "automatic session armed; waiting for the first live GCA1 telemetry record"
                    if eligible and self.auto_managed
                    else "waiting for mod telemetry; manual controls remain available" if eligible
                    else "Launch The Witcher 3 Complete Edition (AppID 292030)"
                ),
            }
