from pathlib import Path
import unittest


class PackagingTests(unittest.TestCase):
    def test_required_decky_files_exist(self):
        root = Path(__file__).resolve().parents[2]
        for relative in ("main.py", "plugin.json", "package.json", "LICENSE", "scripts/package_plugin.py"):
            self.assertTrue((root / relative).is_file(), relative)
        self.assertTrue((root / "py_modules/signalbar/backend/engine.py").is_file())
        self.assertTrue((root / "assets/readme-gifs/controller-battery.gif").is_file())
        from scripts.package_plugin import iter_files
        # CI tests run before the build creates dist/index.js.
        packaged = {str(path.relative_to(root)) for path in iter_files(require_build=False)}
        self.assertIn("assets/readme-gifs/controller-battery.gif", packaged)

    def test_panel_order_and_lifecycle_guards(self):
        root = Path(__file__).resolve().parents[2]
        panel = (root / "src/index.tsx").read_text(encoding="utf-8")
        content = panel.index("function Content")
        artwork = panel.index('<PanelSection title="Artwork">', content)
        performance = panel.index('<PanelSection title="Performance">', content)
        countdown = panel.index("<CountdownPanel status=", content)
        weather = panel.index('<PanelSection title="Local weather">')
        debug = panel.index('<PanelSection title="Advanced / debug">', content)
        self.assertLess(artwork, performance)
        self.assertLess(performance, countdown)
        self.assertLess(countdown, debug)
        self.assertLess(weather, debug)
        self.assertIn('routerHook.addRoute("/signalbar/settings", SignalBarSettings)', panel)
        self.assertIn('routerHook.removeRoute("/signalbar/settings")', panel)
        self.assertIn('<SidebarNavigation title="SignalBar settings"', panel)
        self.assertIn('title: "Compatibility"', panel)
        self.assertIn('label="Coordinate LED ownership"', panel)
        self.assertIn('stripmine_priority_light_events', panel)
        self.assertIn('page === "quick" ? <PanelSection title="Now showing">', panel)
        self.assertIn('Game artwork{currentArtwork?.source_label', panel)
        self.assertIn('<ArtworkImage artwork={currentArtwork} title={status.game.title || "current game"} compact />', panel)
        self.assertIn('objectFit: "contain"', panel)
        self.assertNotIn('objectFit: "cover"', panel)
        self.assertIn('heroRequestKey === `${status.game.appid}:${status.artwork_source}`', panel)
        self.assertIn('if (request !== artworkRequest.current) return;', panel)

        runtime = (root / "src/runtime.ts").read_text(encoding="utf-8")
        self.assertIn('this.observeRunningApp("startup");', runtime)
        self.assertIn('window.setInterval(() => this.observeRunningApp("poll fallback")', runtime)
        self.assertIn("RegisterForAppLifetimeNotifications", runtime)
        self.assertIn("RegisterForOnResumeFromSuspend", runtime)
        self.assertIn("RegisterForDownloadOverview", runtime)
        self.assertIn("RegisterForParentalPlaytimeWarnings", runtime)
        self.assertIn("suppressedStaleAppId", runtime)
        self.assertIn("background game sync failed; retrying", runtime)
        self.assertIn("syncArtwork", runtime)
        game_sync = runtime.index("const status = await gameChanged")
        parental_registration = runtime.index("this.registerParentalSignal(current.appid)", game_sync)
        self.assertLess(game_sync, parental_registration)

        initializer = panel.index("export default definePlugin")
        runtime_start = panel.index("const runtime = startSignalBarRuntime()", initializer)
        weather_topbar_start = panel.index("const weatherTopBar = startWeatherTopBar()", initializer)
        returned_plugin = panel.index("return {", runtime_start)
        self.assertLess(runtime_start, returned_plugin)
        self.assertLess(weather_topbar_start, returned_plugin)
        self.assertIn("weatherTopBar.stop()", panel)
        self.assertNotIn("useSteamState", panel)
        self.assertNotIn("useCountdownSignals", panel)
        self.assertIn('label="Extra dark LEDs"', panel)
        self.assertIn('setSetting("countdown_dark_edge_compensation", value)', panel)
        self.assertIn("Countdown and Performance only", panel)
        self.assertIn('label="Full bar scale"', panel)
        self.assertIn('setSetting("countdown_full_bar_minutes", Number(option.data))', panel)
        self.assertIn("Steam Families callback:", panel)
        self.assertIn("Game detection:", panel)
        self.assertIn('label="Meter response"', panel)
        self.assertIn('setSetting("performance_smoothing", String(option.data))', panel)
        self.assertIn('status.mode === "performance"', panel)
        self.assertIn('label="Export configuration JSON"', panel)
        self.assertIn('label="Import configuration JSON"', panel)
        self.assertIn('label="Reset to defaults"', panel)
        self.assertIn('openFilePicker(0, "/home/deck/Documents"', panel)
        self.assertIn('strTitle="Import SignalBar configuration?"', panel)
        self.assertIn('strTitle="Reset SignalBar settings?"', panel)
        self.assertIn("setConfigurationExportPath(result.path)", panel)
        self.assertIn('<PerformanceReadout status={status} />', panel)
        readout = panel[panel.index("function PerformanceReadout"):panel.index("function ColorChoice")]
        self.assertNotIn("PalettePreview", readout)
        self.assertIn('status.provider.startsWith("artwork") && status.game.appid > 0', panel)
        self.assertIn('sampleLine={status.artwork_mode === "manual"', panel)
        self.assertIn('label="Always show Performance"', panel)
        self.assertIn('setSetting("performance_always", value)', panel)
        self.assertIn('{ data: "custom", label: "Custom colours" }', panel)
        self.assertIn("ColorPickerModal", panel)
        self.assertIn("icon: <TbCubeSpark />", panel)
        self.assertIn('<PanelSection title="Active countdown">', panel)
        self.assertIn('label="Isolate recording marker"', panel)
        events_panel = panel[panel.index("function EventsPanel"):panel.index("function ControllersPanel")]
        self.assertNotIn("<PalettePreview", events_panel)
        self.assertIn('<EventPreviewStrip status={status} kinds={[kind]} />', events_panel)
        self.assertIn('setSetting("recording_marker_isolation", value)', panel)
        self.assertIn('label="Country (full name, optional)"', panel)
        self.assertIn('Two-letter codes do not work here.', panel)
        self.assertIn('label="Top-bar temperature unit"', panel)
        self.assertIn('<EventPreviewStrip status={status}', panel)

        engine = (root / "py_modules/signalbar/backend/engine.py").read_text(encoding="utf-8")
        self.assertIn(
            'dark_edge_compensation=values["countdown_dark_edge_compensation"]',
            engine,
        )


if __name__ == "__main__":
    unittest.main()
