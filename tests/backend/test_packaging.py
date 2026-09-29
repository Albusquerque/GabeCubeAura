from pathlib import Path
import unittest


class PackagingTests(unittest.TestCase):
    def test_required_decky_files_exist_and_runtime_package_stays_lean(self):
        root = Path(__file__).resolve().parents[2]
        for relative in (
            "main.py", "plugin.json", "package.json", "LICENSE",
            "THIRD_PARTY_NOTICES.md", "scripts/package_plugin.py",
            "docs/SCREEN_SYNC.md", "docs/SCREEN_SYNC_INTEGRATION_PLAN.md",
            "docs/BETA_TEST_PLAN_1.2.0-beta1.md",
            "docs/RELEASE_NOTES_1.2.0-beta1.md",
        ):
            self.assertTrue((root / relative).is_file(), relative)
        self.assertTrue((root / "py_modules/signalbar/backend/engine.py").is_file())
        from scripts.package_plugin import iter_files
        packaged = {str(path.relative_to(root)) for path in iter_files(require_build=False)}
        self.assertIn("THIRD_PARTY_NOTICES.md", packaged)
        self.assertIn("py_modules/signalbar/backend/engine.py", packaged)
        self.assertIn("py_modules/signalbar/updates.py", packaged)
        self.assertIn("py_modules/signalbar/update_helper.py", packaged)
        self.assertFalse(any(path.startswith("assets/") for path in packaged))
        self.assertFalse(any(path.startswith("docs/") for path in packaged))

    def test_gabecubeaura_settings_screen_sync_updates_and_lifecycle_guards(self):
        root = Path(__file__).resolve().parents[2]
        panel = (root / "src/index.tsx").read_text(encoding="utf-8")
        customization_catalog = (root / "src/customization_catalog.ts").read_text(encoding="utf-8")
        manifest = (root / "plugin.json").read_text(encoding="utf-8")
        package = (root / "package.json").read_text(encoding="utf-8")
        self.assertIn('"name": "GabeCubeAura"', manifest)
        self.assertIn('"version": "1.2.0-beta1"', package)
        self.assertIn('"url": "git+https://github.com/Alyenax/GabeCubeAura.git"', package)
        self.assertNotIn("Albusquerque/GabeCubeAura", package)
        self.assertIn('routerHook.addRoute("/gabecubeaura/settings", GabeCubeAuraSettings)', panel)
        self.assertIn('routerHook.removeRoute("/gabecubeaura/settings")', panel)
        self.assertIn('return <SidebarNavigation title="GabeCubeAura settings"', panel)
        self.assertIn('route: "/gabecubeaura/settings/customization"', panel)
        self.assertIn('route: "/gabecubeaura/settings/screen-sync"', panel)
        self.assertIn('route: "/gabecubeaura/settings/launches"', panel)
        self.assertNotIn('Content page="settings"', panel)
        self.assertIn('{ data: "steam", label: "GabeCubeAura Off" }', panel)
        self.assertIn('{ data: "customization", label: "Customization+" }', panel)
        self.assertIn('<CustomizationPanel status={status}', panel)
        self.assertIn('label="Brightness"', panel)
        self.assertIn('min={34} max={255} step={1}', panel)
        self.assertIn('label="Speed"', panel)
        self.assertIn('setSetting("customization_speed", value)', panel)
        self.assertIn('label="Hex"', panel)
        self.assertIn('label="Red"', panel)
        self.assertIn('label="Green"', panel)
        self.assertIn('label="Blue"', panel)
        self.assertIn('OpaqueColorPickerModal', panel)
        self.assertNotIn('ColorPickerModal', panel.replace('OpaqueColorPickerModal', ''))
        self.assertNotIn('label="Alpha"', panel)
        self.assertIn('Light Events / ${kind}', customization_catalog)
        self.assertIn('Controllers / ${kind}', customization_catalog)
        self.assertIn('Weather / ${condition', customization_catalog)
        self.assertIn('Game Launches · ${pattern.label}', customization_catalog)
        self.assertIn('"Calm & ambient"', customization_catalog)
        self.assertIn('"Flowing"', customization_catalog)
        self.assertIn('"Energetic"', customization_catalog)
        self.assertNotIn('{ data: "patrol", label: "Patrol" }', panel)
        self.assertNotIn('{ data: "breathe", label: "Breathe" }', panel)
        self.assertNotIn('{ data: "rainbow", label: "Rainbow" }', panel)
        self.assertNotIn('{ data: "solid", label: "Solid" }', panel)

        preview = panel.index('label="Preview launch animation"')
        live = panel.index("Live 17-LED launch preview", preview)
        artwork = panel.index('<ArtworkImage artwork={currentLaunchArtwork}', live)
        second_preview = panel.index('label="Preview launch animation"', artwork)
        self.assertLess(preview, live)
        self.assertLess(live, artwork)
        self.assertLess(artwork, second_preview)
        self.assertNotIn('label="Replay launch animation"', panel)
        self.assertEqual(panel.count('label="Preview launch animation"'), 2)
        self.assertEqual(panel.count("void runLaunchPreview()"), 2)
        self.assertNotIn('<PalettePreview colors={status.launch_artwork.dominant_colors ?? []} />', panel)
        self.assertNotIn("Live 17-LED launch preview", panel[artwork:second_preview])
        self.assertIn('page === "compatibility" || page === "launches" ? 100', panel)
        self.assertIn('page === "screen-sync" ? 250 : 1000', panel)
        self.assertIn('<Focusable style={{ width: "100%", paddingBottom: 28, scrollMarginBottom: 24 }} aria-label="Launch artwork preview">', panel)
        self.assertIn('label="Palette source"', panel)
        self.assertIn('label="Number of colours"', panel)
        self.assertIn('setLaunchArtworkSetting', panel)
        self.assertIn('stripmine_priority_customization', panel)
        self.assertIn('route: "/gabecubeaura/settings/updates"', panel)
        self.assertIn('label="Check for updates"', panel)
        self.assertIn('label="Automatically check for updates"', panel)
        self.assertIn('label="Notify me when an update is available"', panel)
        self.assertIn('Update lab · TEST BUILD', panel)
        self.assertIn('stripmine_priority_screen_sync', panel)
        self.assertIn('{ data: "screen_sync", label: "Screen Sync" }', panel)
        self.assertIn('<ScreenSyncPanel status={status}', panel)
        self.assertIn('label="Refresh capture status"', panel)
        self.assertIn('label="Use during Steam screensaver"', panel)
        self.assertIn('label="Preview Screen Sync"', panel)
        self.assertIn('<PanelSection title="Capture fallback">', panel)
        self.assertIn('function SettingsPageEnd', panel)
        self.assertIn('page !== "quick" ? <SettingsPageEnd page={page} setStatus={setStatus} />', panel)
        self.assertIn('label={`End of ${PAGE_END_LABELS[page]} settings`}', panel)

        runtime = (root / "src/runtime.ts").read_text(encoding="utf-8")
        self.assertIn('this.session.seed(runningApp())', runtime)
        self.assertIn('this.session.observePoll(runningApp())', runtime)
        self.assertIn('this.session.observeLifetime(', runtime)
        self.assertIn("RegisterForAppLifetimeNotifications", runtime)
        self.assertIn("RegisterForOnResumeFromSuspend", runtime)
        self.assertIn("RegisterForParentalPlaytimeWarnings", runtime)
        self.assertIn("isSteamScreensaverService", runtime)
        self.assertIn('setScreenSyncContext("steam-screensaver"', runtime)
        self.assertIn("const runtime = startGabeCubeAuraRuntime()", panel)
        self.assertIn("weatherTopBar.stop()", panel)

        packager = (root / "scripts/package_plugin.py").read_text(encoding="utf-8")
        self.assertIn('f"GabeCubeAura-v{PACKAGE[\'version\']}.zip"', packager)
        self.assertIn('Path("GabeCubeAura") / relative', packager)
        self.assertIn('FIXED_OUTPUT = ROOT / "out" / "GabeCubeAura.zip"', packager)
        self.assertIn('CHECKSUMS = ROOT / "out" / "SHA256SUMS"', packager)

        updates = (root / "py_modules/signalbar/updates.py").read_text(encoding="utf-8")
        helper = (root / "py_modules/signalbar/update_helper.py").read_text(encoding="utf-8")
        self.assertIn('OWNER = "Alyenax"', updates)
        self.assertIn('ssl.create_default_context()', updates)
        self.assertNotIn("CERT_NONE", updates)
        self.assertIn("RENAME_EXCHANGE", helper)
        self.assertIn('"plugin_loader.service"', helper)


if __name__ == "__main__":
    unittest.main()
