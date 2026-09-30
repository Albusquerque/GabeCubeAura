from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signalbar.witcher_install import (
    SOURCE_RELATIVE,
    TARGET_RELATIVE,
    WitcherTelemetryInstaller,
)


class WitcherTelemetryInstallerTests(unittest.TestCase):
    def _layout(self, folder):
        base = Path(folder)
        plugin = base / "plugin"
        source = plugin / SOURCE_RELATIVE
        source.parent.mkdir(parents=True)
        source.write_text("live telemetry v1\n", encoding="utf-8")
        steamapps = base / "library/steamapps"
        game = steamapps / "common/The Witcher 3"
        game.mkdir(parents=True)
        steamapps.mkdir(parents=True, exist_ok=True)
        (steamapps / "appmanifest_292030.acf").write_text(
            '"AppState"\n{\n"appid" "292030"\n"installdir" "The Witcher 3"\n}\n',
            encoding="utf-8",
        )
        return plugin, steamapps, game, source

    def test_status_install_and_verification_use_exact_app_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, game, source = self._layout(folder)
            installer = WitcherTelemetryInstaller(plugin, roots=[steamapps])
            before = installer.status()
            self.assertEqual(before["state"], "not_installed")
            self.assertFalse(before["installed"])
            result = installer.install()
            target = game / "mods" / TARGET_RELATIVE
            self.assertTrue(result["installed"])
            self.assertEqual(result["state"], "installed")
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(Path(result["target_path"]).resolve(), target.resolve())

    def test_status_reports_complete_logging_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, _, _ = self._layout(folder)
            config = steamapps.parent / "userdata/123/config/localconfig.vdf"
            config.parent.mkdir(parents=True)
            config.write_text(
                '"UserLocalConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n'
                '"Steam"\n{\n"apps"\n{\n"292030"\n{\n'
                '"LaunchOptions" "-net -debugscripts"\n}\n}\n}\n}\n}\n}\n',
                encoding="utf-8",
            )
            settings = (
                steamapps / "compatdata/292030/pfx/drive_c/users/steamuser/"
                "Documents/The Witcher 3/user.settings"
            )
            settings.parent.mkdir(parents=True)
            settings.write_text(
                "[Scripts]\nDebugScriptsForceFlush=true\n\n[Input]\nPadVibrationEnabled=true\n",
                encoding="utf-8",
            )

            logging = WitcherTelemetryInstaller(plugin, roots=[steamapps]).status()["logging"]
            self.assertEqual(logging["launch_options"]["state"], "configured")
            self.assertTrue(logging["launch_options"]["has_net"])
            self.assertTrue(logging["launch_options"]["has_debugscripts"])
            self.assertEqual(logging["force_flush"]["state"], "configured")

    def test_status_identifies_partial_launch_options_and_missing_flush(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, _, _ = self._layout(folder)
            config = steamapps.parent / "userdata/123/config/localconfig.vdf"
            config.parent.mkdir(parents=True)
            config.write_text(
                '"apps"\n{\n"292030"\n{\n"LaunchOptions" "-debugscripts"\n}\n}\n',
                encoding="utf-8",
            )
            settings = (
                steamapps / "compatdata/292030/pfx/drive_c/users/steamuser/"
                "Documents/The Witcher 3/user.settings"
            )
            settings.parent.mkdir(parents=True)
            settings.write_text("[Scripts]\nDebugScriptsForceFlush=false\n", encoding="utf-8")

            logging = WitcherTelemetryInstaller(plugin, roots=[steamapps]).status()["logging"]
            self.assertEqual(logging["launch_options"]["state"], "partial")
            self.assertFalse(logging["launch_options"]["has_net"])
            self.assertTrue(logging["launch_options"]["has_debugscripts"])
            self.assertEqual(logging["force_flush"]["state"], "missing")

    def test_repair_backs_up_different_existing_script_once(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, game, _ = self._layout(folder)
            target = game / "mods" / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_text("user modified script\n", encoding="utf-8")
            installer = WitcherTelemetryInstaller(plugin, roots=[steamapps])
            self.assertEqual(installer.status()["state"], "update_required")
            result = installer.install()
            backup = Path(result["backup_path"])
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.read_text(encoding="utf-8"), "user modified script\n")

            removed = installer.remove()
            self.assertEqual(removed["last_action"], "restored_backup")
            self.assertFalse(removed["installed"])
            self.assertEqual(target.read_text(encoding="utf-8"), "user modified script\n")
            self.assertFalse(backup.exists())

    def test_remove_deletes_only_the_checksum_verified_managed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, game, _ = self._layout(folder)
            installer = WitcherTelemetryInstaller(plugin, roots=[steamapps])
            installer.install()
            target = game / "mods" / TARGET_RELATIVE
            self.assertTrue(target.is_file())

            removed = installer.remove()
            self.assertEqual(removed["last_action"], "removed")
            self.assertEqual(removed["state"], "not_installed")
            self.assertFalse(target.exists())

    def test_remove_preserves_an_unknown_modified_file_instead_of_deleting_it(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, game, _ = self._layout(folder)
            installer = WitcherTelemetryInstaller(plugin, roots=[steamapps])
            installer.install()
            target = game / "mods" / TARGET_RELATIVE
            target.write_text("locally modified telemetry\n", encoding="utf-8")

            removed = installer.remove()
            preserved = Path(removed["preserved_path"])
            self.assertEqual(removed["last_action"], "preserved_unknown")
            self.assertEqual(removed["state"], "not_installed")
            self.assertFalse(target.exists())
            self.assertEqual(
                preserved.read_text(encoding="utf-8"), "locally modified telemetry\n",
            )

    def test_repair_migrates_legacy_uppercase_mods_path_without_data_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, game, source = self._layout(folder)
            # Use a distinct directory name so this remains deterministic on
            # the case-insensitive macOS filesystem running the test suite.
            legacy = game / "LegacyMods" / TARGET_RELATIVE
            legacy.parent.mkdir(parents=True)
            legacy.write_text("older GabeCubeAura bridge\n", encoding="utf-8")
            installer = WitcherTelemetryInstaller(plugin, roots=[steamapps])
            with patch.object(installer, "_legacy_target", return_value=legacy):
                before = installer.status()
                self.assertEqual(before["state"], "legacy_path")
                self.assertEqual(before["legacy_target_path"], str(legacy))
                repaired = installer.install()
            target = game / "mods" / TARGET_RELATIVE
            self.assertTrue(repaired["installed"])
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertFalse(legacy.exists())
            self.assertEqual(
                Path(repaired["preserved_path"]).read_text(encoding="utf-8"),
                "older GabeCubeAura bridge\n",
            )

    def test_reset_always_removes_managed_legacy_uppercase_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, game, source = self._layout(folder)
            legacy = game / "Mods" / TARGET_RELATIVE
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(source.read_bytes())
            installer = WitcherTelemetryInstaller(plugin, roots=[steamapps])

            removed = installer.remove()
            self.assertEqual(removed["last_action"], "removed")
            self.assertFalse(legacy.exists())
            self.assertEqual(removed["state"], "not_installed")

    def test_wrong_appid_or_path_traversal_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin, steamapps, _, _ = self._layout(folder)
            manifest = steamapps / "appmanifest_292030.acf"
            manifest.write_text(
                '"AppState"\n{\n"appid" "10"\n"installdir" "../escape"\n}\n',
                encoding="utf-8",
            )
            status = WitcherTelemetryInstaller(plugin, roots=[steamapps]).status()
            self.assertEqual(status["state"], "game_not_found")
            self.assertFalse(status["game_found"])


if __name__ == "__main__":
    unittest.main()
