"""Safe local installer for GabeCubeAura's optional WitcherScript bridge."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import time


APP_ID = 292030
SOURCE_RELATIVE = Path(
    "witcher_mod/mods/modGabeCubeAuraTelemetry/content/scripts/local/gca_telemetry.ws"
)
TARGET_RELATIVE = Path(
    "modGabeCubeAuraTelemetry/content/scripts/local/gca_telemetry.ws"
)
LEGACY_DIRECTORY = "Mods"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique(paths):
    result = []
    seen = set()
    for path in paths:
        path = Path(path)
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _same_existing_file(first, second):
    try:
        return Path(first).exists() and Path(second).exists() and os.path.samefile(first, second)
    except OSError:
        return False


def _vdf_named_blocks(text, key):
    """Yield balanced VDF blocks for a quoted key without a full VDF parser."""
    pattern = re.compile(r'"' + re.escape(str(key)) + r'"\s*\{', re.IGNORECASE)
    for match in pattern.finditer(str(text)):
        opening = str(text).find("{", match.start())
        depth = 0
        quoted = False
        escaped = False
        for index in range(opening, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    yield text[opening + 1:index]
                    break


def _launch_flag(options, flag):
    return bool(re.search(
        r"(?:^|\s)" + re.escape(flag) + r"(?=\s|$)",
        str(options or ""),
        re.IGNORECASE,
    ))


def steamapps_roots(user_home=None):
    homes = _unique((Path(user_home or os.environ.get("DECKY_USER_HOME") or "/home/deck"), Path("/home/deck")))
    roots = []
    for home in homes:
        roots.extend((home / ".local/share/Steam/steamapps", home / ".steam/steam/steamapps"))
        for vdf in (
            home / ".local/share/Steam/steamapps/libraryfolders.vdf",
            home / ".steam/steam/steamapps/libraryfolders.vdf",
        ):
            try:
                for line in vdf.read_text(encoding="utf-8", errors="replace").splitlines():
                    if '"path"' not in line:
                        continue
                    parts = line.split('"')
                    if len(parts) >= 4:
                        roots.append(Path(parts[3].replace("\\\\", "/")) / "steamapps")
            except OSError:
                pass
    media = Path("/run/media/deck")
    try:
        roots.extend(path / "steamapps" for path in media.iterdir() if path.is_dir())
    except OSError:
        pass
    return _unique(roots)


class WitcherTelemetryInstaller:
    def __init__(self, plugin_dir, roots=None):
        self.plugin_dir = Path(plugin_dir)
        self.source = self.plugin_dir / SOURCE_RELATIVE
        self.roots = [Path(path) for path in roots] if roots is not None else None
        self.last_backup = ""
        self.last_preserved = ""
        self.last_action = ""
        self.error = ""
        self._logging_cache = None
        self._logging_cache_at = 0.0

    def _roots(self):
        return self.roots or steamapps_roots()

    def _game_directory(self):
        for root in self._roots():
            manifest = root / f"appmanifest_{APP_ID}.acf"
            try:
                text = manifest.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not re.search(r'"appid"\s*"292030"', text):
                continue
            match = re.search(r'"installdir"\s*"([^"]+)"', text)
            if not match:
                continue
            common = (root / "common").resolve()
            candidate = (common / match.group(1)).resolve()
            try:
                if os.path.commonpath((str(common), str(candidate))) != str(common):
                    continue
            except ValueError:
                continue
            if candidate.is_dir():
                return candidate
        return None

    def _launch_options_status(self):
        saw_config = False
        best = None
        for root in self._roots():
            userdata = root.parent / "userdata"
            try:
                accounts = sorted(path for path in userdata.iterdir() if path.is_dir())[:64]
            except OSError:
                continue
            for account in accounts:
                path = account / "config/localconfig.vdf"
                try:
                    if path.stat().st_size > 16 * 1024 * 1024:
                        continue
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                saw_config = True
                for block in _vdf_named_blocks(text, str(APP_ID)):
                    match = re.search(
                        r'"LaunchOptions"\s*"((?:\\.|[^"\\])*)"',
                        block,
                        re.IGNORECASE,
                    )
                    if not match:
                        continue
                    options = match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                    has_net = _launch_flag(options, "-net")
                    has_debugscripts = _launch_flag(options, "-debugscripts")
                    current = {
                        "state": "configured" if has_net and has_debugscripts else "partial",
                        "has_net": has_net,
                        "has_debugscripts": has_debugscripts,
                        "path": str(path),
                    }
                    if current["state"] == "configured":
                        return current
                    best = current
        if best:
            return best
        return {
            "state": "not_set" if saw_config else "unknown",
            "has_net": False,
            "has_debugscripts": False,
            "path": "",
        }

    def _script_settings_status(self):
        saw_file = False
        best_path = ""
        suffixes = tuple(
            Path(f"pfx/drive_c/users/steamuser/{documents}/The Witcher 3/{filename}")
            for documents in ("Documents", "My Documents")
            for filename in ("user.settings", "dx12user.settings")
        )
        for root in self._roots():
            for suffix in suffixes:
                path = root / "compatdata" / str(APP_ID) / suffix
                try:
                    if path.stat().st_size > 4 * 1024 * 1024:
                        continue
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                saw_file = True
                best_path = best_path or str(path)
                section = re.search(
                    r"(?ims)^\[Scripts\]\s*(.*?)(?=^\[[^\]]+\]|\Z)", text,
                )
                configured = bool(section and re.search(
                    r"(?im)^\s*DebugScriptsForceFlush\s*=\s*true\s*$",
                    section.group(1),
                ))
                if configured:
                    return {"state": "configured", "path": str(path)}
        return {
            "state": "missing" if saw_file else "unknown",
            "path": best_path,
        }

    def _logging_status(self):
        now = time.monotonic()
        if self._logging_cache is not None and now - self._logging_cache_at < 15.0:
            return dict(self._logging_cache)
        result = {
            "launch_options": self._launch_options_status(),
            "force_flush": self._script_settings_status(),
        }
        self._logging_cache = result
        self._logging_cache_at = now
        return dict(result)

    @staticmethod
    def _target(game):
        # CDPR's documented PC layout is lower-case ``mods``.  SteamOS uses a
        # case-sensitive filesystem, so creating ``Mods`` on a fresh install
        # can produce a checksum-valid file that the game never compiles.
        return game / "mods" / TARGET_RELATIVE

    @staticmethod
    def _legacy_target(game):
        return game / LEGACY_DIRECTORY / TARGET_RELATIVE

    @staticmethod
    def _backup(target):
        return target.with_suffix(target.suffix + ".backup-before-gabecubeaura")

    @staticmethod
    def _preserved(target):
        return target.with_suffix(target.suffix + ".preserved-before-remove")

    @staticmethod
    def _migration_preserved(target):
        return target.with_suffix(target.suffix + ".preserved-before-lowercase-migration")

    def status(self):
        source_found = self.source.is_file()
        game = self._game_directory()
        target = self._target(game) if game else None
        legacy_target = self._legacy_target(game) if game else None
        backup = self._backup(target) if target else None
        state = "game_not_found"
        installed = False
        if not source_found:
            state = "source_missing"
        elif game and target and not target.is_file():
            state = "legacy_path" if legacy_target and legacy_target.is_file() else "not_installed"
        elif game and target:
            try:
                installed = _sha256(target) == _sha256(self.source)
                state = "installed" if installed else "update_required"
            except OSError as error:
                self.error = str(error)
                state = "error"
        return {
            "state": state,
            "installed": installed,
            "game_found": game is not None,
            "source_found": source_found,
            "game_path": str(game) if game else "",
            "target_path": str(target) if target else "",
            "legacy_target_path": (
                str(legacy_target)
                if legacy_target and legacy_target.is_file()
                and not _same_existing_file(legacy_target, target) else ""
            ),
            "backup_path": str(backup) if backup and backup.is_file() else self.last_backup,
            "preserved_path": self.last_preserved,
            "last_action": self.last_action,
            "logging": self._logging_status(),
            "error": self.error,
        }

    def install(self):
        self.error = ""
        self.last_action = ""
        self.last_preserved = ""
        game = self._game_directory()
        if game is None:
            raise RuntimeError("The Witcher 3 AppID 292030 installation was not found")
        if not self.source.is_file():
            raise RuntimeError("The packaged Witcher telemetry source is missing")
        target = self._target(game)
        target.parent.mkdir(parents=True, exist_ok=True)
        game_real = game.resolve()
        parent_real = target.parent.resolve()
        if os.path.commonpath((str(game_real), str(parent_real))) != str(game_real):
            raise RuntimeError("Refusing to install outside The Witcher 3 directory")
        if target.is_symlink():
            raise RuntimeError("Refusing to replace a symbolic-link telemetry script")
        source_bytes = self.source.read_bytes()
        if target.is_file() and target.read_bytes() != source_bytes:
            backup = self._backup(target)
            if backup.is_symlink():
                raise RuntimeError("Refusing to write through a symbolic-link backup")
            if not backup.exists():
                backup.write_bytes(target.read_bytes())
            self.last_backup = str(backup)
        temporary = target.with_name(f".{target.name}.gabecubeaura-{os.getpid()}.tmp")
        try:
            temporary.write_bytes(source_bytes)
            os.replace(temporary, target)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        self.last_action = "installed"
        legacy_target = self._legacy_target(game)
        distinct_legacy = not _same_existing_file(legacy_target, target)
        if distinct_legacy and (legacy_target.exists() or legacy_target.is_symlink()):
            if legacy_target.is_symlink() or not legacy_target.is_file():
                raise RuntimeError("Refusing to migrate a non-regular legacy telemetry script")
            if _sha256(legacy_target) == _sha256(self.source):
                legacy_target.unlink()
            else:
                preserved = self._migration_preserved(legacy_target)
                if preserved.exists() or preserved.is_symlink():
                    raise RuntimeError(
                        "A preserved legacy telemetry file already exists; move it before repairing"
                    )
                os.replace(legacy_target, preserved)
                self.last_preserved = str(preserved)
        result = self.status()
        if not result["installed"]:
            raise RuntimeError("The telemetry script could not be verified after installation")
        return result

    def remove(self):
        """Remove only the active GabeCubeAura script, preserving unknown data."""
        self.error = ""
        self.last_action = ""
        self.last_preserved = ""
        game = self._game_directory()
        if game is None:
            raise RuntimeError("The Witcher 3 AppID 292030 installation was not found")
        target = self._target(game)
        legacy_target = self._legacy_target(game)
        targets = [target]
        if not _same_existing_file(legacy_target, target):
            targets.append(legacy_target)

        existing = [path for path in targets if path.exists() or path.is_symlink()]
        if not existing:
            self.last_action = "already_absent"
            return self.status()
        for candidate in existing:
            if candidate.is_symlink() or not candidate.is_file():
                raise RuntimeError("Refusing to remove a non-regular telemetry script")

        game_real = game.resolve()
        parent_real = target.parent.resolve()
        if os.path.commonpath((str(game_real), str(parent_real))) != str(game_real):
            raise RuntimeError("Refusing to remove outside The Witcher 3 directory")

        matches_packaged = self.source.is_file() and target.is_file() and _sha256(target) == _sha256(self.source)
        backup = self._backup(target)
        if target.is_file() and backup.exists():
            if backup.is_symlink() or not backup.is_file():
                raise RuntimeError("Refusing to restore a non-regular telemetry backup")
            if not matches_packaged:
                preserved = self._preserved(target)
                if preserved.exists() or preserved.is_symlink():
                    raise RuntimeError(
                        "A preserved telemetry file already exists; move it before removing again"
                    )
                os.replace(target, preserved)
                self.last_preserved = str(preserved)
            os.replace(backup, target)
            self.last_backup = ""
            self.last_action = "restored_backup"
        elif target.is_file() and matches_packaged:
            target.unlink()
            self.last_action = "removed"
        elif target.is_file():
            preserved = self._preserved(target)
            if preserved.exists() or preserved.is_symlink():
                raise RuntimeError(
                    "A preserved telemetry file already exists; move it before removing again"
                )
            os.replace(target, preserved)
            self.last_preserved = str(preserved)
            self.last_action = "preserved_unknown"

        if legacy_target in existing:
            matches_packaged = self.source.is_file() and _sha256(legacy_target) == _sha256(self.source)
            if matches_packaged:
                legacy_target.unlink()
                if not self.last_action:
                    self.last_action = "removed"
            else:
                preserved = self._preserved(legacy_target)
                if preserved.exists() or preserved.is_symlink():
                    raise RuntimeError(
                        "A preserved legacy telemetry file already exists; move it before removing again"
                    )
                os.replace(legacy_target, preserved)
                self.last_preserved = str(preserved)
                self.last_action = "preserved_unknown"
        return self.status()
