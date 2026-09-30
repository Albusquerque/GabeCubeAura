"""Recoverable Witcher/Screen Sync diagnostics for physical SteamOS tests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path


DIAGNOSTIC_FILENAME = "GabeCubeAura-Witcher3-diagnostics.json"
MAX_TAIL_BYTES = 256 * 1024
MAX_EXCERPT_LINES = 160


def diagnostic_export_path(settings_directory: str, user_home: str | None = None) -> Path:
    if user_home:
        home = Path(user_home).expanduser()
        if home.is_absolute():
            return home / "Documents" / DIAGNOSTIC_FILENAME
    settings = Path(settings_directory).expanduser()
    if not settings.is_absolute():
        settings = Path.cwd() / settings
    for parent in (settings, *settings.parents):
        if parent.name == "homebrew" and parent.parent != parent:
            return parent.parent / "Documents" / DIAGNOSTIC_FILENAME
    return settings / DIAGNOSTIC_FILENAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot(path_value, kind):
    path = Path(str(path_value))
    result = {"kind": kind, "path": str(path), "exists": False}
    try:
        stat = path.stat()
        result.update({
            "exists": path.is_file(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(
                stat.st_mtime, timezone.utc,
            ).isoformat().replace("+00:00", "Z"),
        })
        if not path.is_file():
            return result
        if kind == "script":
            result["sha256"] = _sha256(path)
            return result
        with path.open("rb") as stream:
            if stat.st_size > MAX_TAIL_BYTES:
                stream.seek(stat.st_size - MAX_TAIL_BYTES)
            text = stream.read(MAX_TAIL_BYTES).decode("utf-8", errors="replace")
        if kind == "state-file":
            result["contents"] = text[-65536:]
        else:
            needles = ("gca1|", "gabecubeaura", "error", "warning", "compile")
            relevant = [
                line[-1000:] for line in text.splitlines()
                if any(needle in line.lower() for needle in needles)
            ]
            result["relevant_tail"] = relevant[-MAX_EXCERPT_LINES:]
    except OSError as error:
        result["read_error"] = str(error)
    return result


def build_witcher_diagnostics(status):
    witcher = status.get("witcher") or {}
    installation = witcher.get("installation") or {}
    screen_sync = status.get("screen_sync") or {}
    paths = []
    for kind, values in (
        ("script", (installation.get("target_path"), installation.get("legacy_target_path"))),
        ("state-file", witcher.get("telemetry_state_candidates") or ()),
        ("script-log", witcher.get("telemetry_log_candidates") or ()),
    ):
        for value in values:
            if value and str(value) not in {entry[1] for entry in paths}:
                paths.append((kind, str(value)))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gabecubeaura_version": status.get("version", ""),
        "game": status.get("game", {}),
        "physical_output": {
            "owner": status.get("owner", ""),
            "provider": status.get("provider", ""),
            "suspension_reason": status.get("suspension_reason", ""),
            "error": status.get("error", ""),
        },
        "display_routing": {
            "outputs_enabled": status.get("signalbar_enabled"),
            "home_display": status.get("home_display", ""),
            "game_display": status.get("game_display", ""),
            "game_override": status.get("display_override", ""),
            "current_display": status.get("current_display", ""),
        },
        "witcher": witcher,
        "screen_sync": screen_sync,
        "runtime": status.get("debug", {}),
        "files": [_snapshot(path, kind) for kind, path in paths],
    }


def write_witcher_diagnostics(path: Path, status):
    target = Path(path)
    parent_existed = target.parent.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not parent_existed and hasattr(os, "geteuid") and os.geteuid() == 0:
        owner = target.parent.parent.stat()
        os.chown(target.parent, owner.st_uid, owner.st_gid)
    payload = build_witcher_diagnostics(status)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            owner = target.parent.stat()
            os.chown(target, owner.st_uid, owner.st_gid)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return {"path": str(target), "generated_at": payload["generated_at"]}
