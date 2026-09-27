from pathlib import Path
import unittest


class PackagingTests(unittest.TestCase):
    def test_required_decky_files_exist_and_release_documents_are_packaged(self):
        root = Path(__file__).resolve().parents[2]
        for relative in (
            "main.py", "plugin.json", "package.json", "LICENSE",
            "scripts/package_plugin.py", "docs/GABECUBEAURA_1.0.0.md",
        ):
            self.assertTrue((root / relative).is_file(), relative)
        self.assertTrue((root / "py_modules/signalbar/backend/engine.py").is_file())
        from scripts.package_plugin import iter_files
        packaged = {str(path.relative_to(root)) for path in iter_files(require_build=False)}
        self.assertIn("docs/GABECUBEAURA_1.0.0.md", packaged)
        self.assertIn("docs/LAUNCH_ARTWORK_ANIMATIONS.md", packaged)
        self.assertIn("docs/RELEASE_NOTES_1.0.0.md", packaged)
        self.assertIn("assets/readme-gifs/controller-battery.gif", packaged)
        for animation in (
            "customization-plus.gif",
            "game-launch-palettes.gif",
            "game-launch-patterns.gif",
        ):
            self.assertIn(f"assets/readme-gifs/{animation}", packaged)

    def test_rebrand_standard_settings_and_lifecycle_guards(self):
        root = Path(__file__).resolve().parents[2]
        panel = (root / "src/index.tsx").read_text(encoding="utf-8")
        customization_catalog = (root / "src/customization_catalog.ts").read_text(encoding="utf-8")
        manifest = (root / "plugin.json").read_text(encoding="utf-8")
        package = (root / "package.json").read_text(encoding="utf-8")
        self.assertIn('"name": "GabeCubeAura"', manifest)
        self.assertIn('"version": "1.0.0"', package)
        self.assertIn('routerHook.addRoute("/gabecubeaura/settings", GabeCubeAuraSettings)', panel)
        self.assertIn('routerHook.removeRoute("/gabecubeaura/settings")', panel)
        self.assertIn('return <SidebarNavigation title="GabeCubeAura settings"', panel)
        self.assertIn('route: "/gabecubeaura/settings/customization"', panel)
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
        self.assertIn('page === "compatibility" || page === "launches" ? 100 : 1000', panel)
        self.assertIn('<Focusable style={{ width: "100%", paddingBottom: 28, scrollMarginBottom: 24 }} aria-label="Launch artwork preview">', panel)
        self.assertIn('label="Palette source"', panel)
        self.assertIn('label="Number of colours"', panel)
        self.assertIn('setLaunchArtworkSetting', panel)
        self.assertIn('stripmine_priority_customization', panel)

        runtime = (root / "src/runtime.ts").read_text(encoding="utf-8")
        self.assertIn('this.observeRunningApp("startup");', runtime)
        self.assertIn("RegisterForAppLifetimeNotifications", runtime)
        self.assertIn("RegisterForOnResumeFromSuspend", runtime)
        self.assertIn("RegisterForParentalPlaytimeWarnings", runtime)
        self.assertIn("const runtime = startGabeCubeAuraRuntime()", panel)
        self.assertIn("weatherTopBar.stop()", panel)

        packager = (root / "scripts/package_plugin.py").read_text(encoding="utf-8")
        self.assertIn('f"GabeCubeAura-v{PACKAGE[\'version\']}.zip"', packager)
        self.assertIn('Path("GabeCubeAura") / relative', packager)


if __name__ == "__main__":
    unittest.main()
