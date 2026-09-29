"""Independent transactional swap helper for GabeCubeAura updates.

This file uses only the Python standard library because it runs after Decky
Loader has stopped. It is copied to the persistent plugin runtime directory
before launch.
"""

from __future__ import annotations

import json
import ctypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


TOKEN = re.compile(r"^[0-9a-f]{32}$")
AT_FDCWD = -100
RENAME_EXCHANGE = 2


class TransactionError(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def _read_json(path: Path):
    if path.stat().st_size > 512 * 1024:
        raise TransactionError("transaction file is too large")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TransactionError("transaction file is invalid")
    return value


def _within(path: Path, parent: Path):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_transaction(raw: dict):
    if raw.get("schema") != 1 or not TOKEN.fullmatch(str(raw.get("token", ""))):
        raise TransactionError("transaction identity is invalid")
    token = raw["token"]
    runtime = Path(raw["runtime_root"]).resolve()
    active = Path(raw["active_dir"]).resolve()
    staged = Path(raw["staged_dir"]).resolve()
    state = Path(raw["state_path"]).resolve()
    health = Path(raw["health_path"]).resolve()
    if active.name != "GabeCubeAura" or active.is_symlink():
        raise TransactionError("active plugin path is invalid")
    if not _within(staged, runtime / "staged") or staged.name != "GabeCubeAura" or staged.is_symlink():
        raise TransactionError("staged plugin path is invalid")
    if not _within(state, runtime) or not _within(health, runtime):
        raise TransactionError("runtime paths are invalid")
    if staged.parent.name != token or health.name != f"{token}.json":
        raise TransactionError("transaction paths do not match the token")
    if not active.is_dir():
        raise TransactionError("active plugin directory is missing")
    for directory in (active, staged) if staged.exists() else (active,):
        if not directory.is_dir() or directory.is_symlink():
            raise TransactionError("required plugin directory is invalid")
        for required in ("main.py", "plugin.json", "package.json", "dist/index.js"):
            if not (directory / required).is_file():
                raise TransactionError("plugin directory is incomplete")
    service = str(raw.get("service", ""))
    if service != "plugin_loader.service":
        raise TransactionError("service name is invalid")
    timeout = int(raw.get("health_timeout", 45))
    if not 15 <= timeout <= 120:
        raise TransactionError("health timeout is invalid")
    return {
        **raw,
        "runtime": runtime,
        "active": active,
        "staged": staged,
        "state": state,
        "health": health,
        "service": service,
        "health_timeout": timeout,
    }


def _plugin_version(directory: Path):
    try:
        package = _read_json(directory / "package.json")
        return str(package.get("version", ""))
    except (OSError, ValueError, TypeError, TransactionError):
        return ""


def _exchange_directories(first: Path, second: Path):
    """Atomically exchange two Linux directory entries on one filesystem."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as error:
        raise TransactionError("atomic directory exchange is unavailable") from error
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        AT_FDCWD, os.fsencode(first), AT_FDCWD, os.fsencode(second), RENAME_EXCHANGE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise TransactionError(f"atomic directory exchange failed with errno {error_number}")


def _merge_state(path: Path, **changes):
    try:
        state = _read_json(path)
    except (OSError, ValueError, TypeError, TransactionError):
        state = {}
    state.update(changes)
    _atomic_json(path, state)


class SystemdService:
    def __init__(self, name: str):
        self.name = name

    def _run(self, action: str, *, check=True):
        return subprocess.run(
            ["systemctl", action, self.name],
            check=check, capture_output=True, text=True, timeout=25,
        )

    def stop(self):
        self._run("stop")

    def start(self):
        self._run("start")

    def active(self):
        result = self._run("is-active", check=False)
        return result.returncode == 0 and result.stdout.strip() == "active"

    def wait_inactive(self, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.active():
                return True
            time.sleep(0.25)
        return False


def _wait_for_health(path: Path, token: str, version: str, timeout: int):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            health = _read_json(path)
            if health.get("token") == token and health.get("version") == version:
                return True
        except (OSError, ValueError, TypeError, TransactionError):
            pass
        time.sleep(0.5)
    return False


def run_transaction(raw: dict, service=None, health_waiter=_wait_for_health,
                    exchanger=_exchange_directories):
    tx = _validate_transaction(raw)
    service = service or SystemdService(tx["service"])
    token = tx["token"]
    rollback_parent = tx["runtime"] / "rollback" / token
    rollback = rollback_parent / "GabeCubeAura"
    quarantine = tx["runtime"] / "failed" / token / "GabeCubeAura"
    existing_state = {}
    try:
        existing_state = _read_json(tx["state"])
    except (OSError, ValueError, TypeError, TransactionError):
        pass
    if (existing_state.get("last_result") == "updated"
            and existing_state.get("installed_version") == tx["to_version"]):
        return {"result": "updated", "version": tx["to_version"]}
    if (existing_state.get("last_result") == "rolled_back"
            and existing_state.get("installed_version") == tx["from_version"]):
        return {"result": "rolled_back", "version": tx["from_version"]}
    tx["health"].unlink(missing_ok=True)
    _merge_state(tx["state"], phase="installing", pending_token=token,
                 pending_version=tx["to_version"], error="", error_category="")
    try:
        service.stop()
        if not service.wait_inactive(20):
            raise TransactionError("Decky Loader did not stop")
        active_version = _plugin_version(tx["active"])
        staged_version = _plugin_version(tx["staged"]) if tx["staged"].exists() else ""
        rollback_version = _plugin_version(rollback) if rollback.exists() else ""
        if active_version == tx["from_version"] and staged_version == tx["to_version"]:
            _merge_state(tx["state"], phase="swap_started")
            exchanger(tx["active"], tx["staged"])
            active_version, staged_version = staged_version, active_version
            _merge_state(tx["state"], phase="swapped")
        if active_version != tx["to_version"]:
            raise TransactionError("active directory does not contain the target version")
        if staged_version == tx["from_version"] and not rollback.exists():
            rollback_parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            os.replace(tx["staged"], rollback)
            rollback_version = tx["from_version"]
        if rollback_version != tx["from_version"]:
            raise TransactionError("rollback directory does not contain the previous version")
        for directory, subdirectories, files in os.walk(tx["active"]):
            os.chmod(directory, 0o755)
            for name in subdirectories:
                os.chmod(Path(directory) / name, 0o755)
            for name in files:
                os.chmod(Path(directory) / name, 0o644)
        _merge_state(tx["state"], phase="restart_pending")
        service.start()
        if not health_waiter(tx["health"], token, tx["to_version"], tx["health_timeout"]):
            raise TransactionError("new plugin did not acknowledge a healthy startup")
        _merge_state(
            tx["state"], phase="updated", installed_version=tx["to_version"],
            pending_token="", pending_version="", confirmation_token="",
            available_version="", release_notes="", release_url="",
            prepared_digest="",
            rollback_version=tx["from_version"], last_result="updated",
            completed_token=token,
            error="", error_category="",
        )
        return {"result": "updated", "version": tx["to_version"]}
    except Exception as error:
        rollback_error = ""
        try:
            if service.active():
                service.stop()
                service.wait_inactive(20)
            previous = rollback if _plugin_version(rollback) == tx["from_version"] else tx["staged"]
            if (_plugin_version(tx["active"]) == tx["to_version"]
                    and _plugin_version(previous) == tx["from_version"]):
                exchanger(tx["active"], previous)
                quarantine.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                if quarantine.exists():
                    shutil.rmtree(quarantine)
                os.replace(previous, quarantine)
            service.start()
        except Exception as caught:
            rollback_error = type(caught).__name__
        message = str(error)[:140] or type(error).__name__
        if rollback_error:
            message = f"{message}; rollback restart failed ({rollback_error})"[:180]
        _merge_state(
            tx["state"], phase="rolled_back", installed_version=tx["from_version"],
            pending_token="", pending_version="", confirmation_token="",
            rollback_version=tx["from_version"], last_result="rolled_back",
            completed_token=token,
            error_category="install", error=message,
        )
        return {"result": "rolled_back", "version": tx["from_version"], "error": message}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        return 2
    path = Path(argv[0]).resolve()
    try:
        raw = _read_json(path)
        result = run_transaction(raw)
        result_path = Path(raw["runtime_root"]).resolve() / "transactions" / f"{raw['token']}.result.json"
        _atomic_json(result_path, result)
        return 0 if result["result"] == "updated" else 1
    except Exception as error:
        try:
            failure = path.with_suffix(".fatal.json")
            _atomic_json(failure, {"result": "fatal", "error": str(error)[:180]})
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
