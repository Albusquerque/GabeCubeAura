from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signalbar.witcher_diagnostics import (
    diagnostic_export_path,
    write_witcher_diagnostics,
)


class WitcherDiagnosticsTests(unittest.TestCase):
    def test_export_path_is_the_gaming_users_documents_folder(self):
        self.assertEqual(
            diagnostic_export_path(
                "/home/deck/homebrew/settings/GabeCubeAura",
                "/home/deck",
            ),
            Path("/home/deck/Documents/GabeCubeAura-Witcher3-diagnostics.json"),
        )
        self.assertEqual(
            diagnostic_export_path(
                "/home/deck/homebrew/settings/GabeCubeAura",
            ),
            Path("/home/deck/Documents/GabeCubeAura-Witcher3-diagnostics.json"),
        )

    def test_export_is_recoverable_json_with_filtered_game_and_gstreamer_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "mods/modGabeCubeAuraTelemetry/content/scripts/local/gca_telemetry.ws"
            script.parent.mkdir(parents=True)
            script.write_text("// bridge\n", encoding="utf-8")
            state_file = root / "Documents/The Witcher 3/GabeCubeAuraTelemetry.ini"
            state_file.parent.mkdir(parents=True)
            state_file.write_text("state=GCA1|kind=state|health=10\n", encoding="utf-8")
            script_log = state_file.with_name("scriptlog.txt")
            script_log.write_text(
                "unrelated private game text\n"
                "[GabeCubeAura] GCA1|kind=state|health=10\n"
                "Error [modgabecubeauratelemetry] compile failed\n",
                encoding="utf-8",
            )
            status = {
                "version": "1.2.0-beta.3",
                "game": {"appid": 292030, "title": "The Witcher 3"},
                "owner": "Valve", "provider": "none",
                "suspension_reason": "test", "error": "",
                "signalbar_enabled": True,
                "home_display": "controller", "game_display": "customization",
                "display_override": "inherit", "current_display": "customization",
                "witcher": {
                    "installation": {
                        "target_path": str(script), "legacy_target_path": "",
                    },
                    "telemetry_state_candidates": [str(state_file)],
                    "telemetry_log_candidates": [str(script_log)],
                },
                "screen_sync": {
                    "phase": "error", "error": "Failed to set pipeline to PAUSED",
                    "stderr_tail": ["Failed to set pipeline to PAUSED"],
                },
                "debug": {"engine_running": True},
            }
            destination = root / "Documents/GabeCubeAura-Witcher3-diagnostics.json"
            result = write_witcher_diagnostics(destination, status)
            payload = json.loads(destination.read_text(encoding="utf-8"))

            self.assertEqual(result["path"], str(destination))
            self.assertEqual(payload["game"]["appid"], 292030)
            self.assertTrue(payload["display_routing"]["outputs_enabled"])
            self.assertEqual(payload["display_routing"]["current_display"],
                             "customization")
            self.assertEqual(payload["screen_sync"]["stderr_tail"][0],
                             "Failed to set pipeline to PAUSED")
            snapshots = {entry["kind"]: entry for entry in payload["files"]}
            self.assertIn("sha256", snapshots["script"])
            self.assertIn("GCA1|kind=state", snapshots["state-file"]["contents"])
            self.assertEqual(len(snapshots["script-log"]["relevant_tail"]), 2)
            self.assertNotIn("unrelated private game text",
                             "\n".join(snapshots["script-log"]["relevant_tail"]))


if __name__ == "__main__":
    unittest.main()
