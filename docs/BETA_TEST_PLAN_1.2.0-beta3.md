# GabeCubeAura 1.2.0-beta3 validation plan

> **Ownership warning:** preserve and review
> [`IMPORTANT_LED_OWNERSHIP_REGRESSION.md`](../IMPORTANT_LED_OWNERSHIP_REGRESSION.md).
> Do not validate the test from the Decky preview alone.

This plan separates software verification from physical Steam Machine results.

## Before installation

1. Keep the beta2 or stable ZIP and export the current GabeCubeAura settings.
2. Compare the beta3 archive checksum with `out/SHA256SUMS`.
3. Disable unknown light-bar writers; StripMine may remain enabled for the
   explicit handoff tests.
4. Install the ZIP through Decky Developer settings without extracting it.

## Basic regression

1. Confirm the plugin reports `1.2.0-beta3` and the beta2 settings survived.
2. Preview Customization+, Artwork, Weather, Screen Sync, Controllers and one
   Light Event.
3. Repeat the beta2 controller, update-channel, screensaver, recording and
   Steam Families campaigns.

## Screen Sync discovery

1. Press **Preview Screen Sync**, wait five seconds and confirm the page reports
   `render loop live` with a fresh decision instead of retaining the preceding
   Artwork or Performance provider.
2. Select Screen Sync for the current game and confirm the status shows both a
   Gamescope source, the user PipeWire session selected by the backend and
   `Selector: gamescope name`. Confirm `PipeWire identity` names the owner of
   that session, normally `deck (uid 1000)`, rather than root.
3. Repeat from the Steam screensaver. It must use the same live capture path
   without changing the saved Home display.
4. Confirm Decky's root session does not win discovery merely because its
   PipeWire socket is encountered before the Gaming Mode user session.
5. If discovery fails, record the `Runtime`, `Last runtime fault`, `PipeWire
   session`, `Selector` and `Discovery` lines shown on the Screen Sync page
   before restarting Steam or Decky.
6. Confirm Customization+ is used only as the documented safety fallback while
   capture is unavailable, and Screen Sync resumes when Gamescope is found.
7. If the installed PipeWire plugin rejects the modern selector, confirm the
   page briefly reports a retry and then shows `Selector: legacy node ...`.

## Game exit and Home routing

1. Start a game, wait for its title and AppID to appear in the quick panel,
   then exit normally.
2. Confirm a Steam lifetime-stop event returns the panel to Home immediately.
3. Repeat on a build where the lifetime stop is missed. A stale
   `MainRunningApp` must be rejected once it is absent from `RunningApps`, and
   Home must return after no more than five two-second confirmation polls.
4. Change the Home display after exit and confirm the quick panel, current
   display and physical bar all follow the new selection.
5. Toggle `Enable GabeCubeAura outputs` off and on. A closed game's AppID and
   per-game override must not return.

## Screen Sync to Game Launches transition

1. Select Screen Sync for games and enable a Game Launches animation.
2. Start a game and watch the physical strip from the native Steam launch
   state until the configured launch animation begins.
3. Confirm the orange Customization+ fallback never flashes during the
   one-second safety handoff. Valve or a live Screen Sync frame may remain
   visible before the Game Launches animation.

## The Witcher 3 laboratory

1. At the top of the Witcher page, confirm the telemetry mod reports **Not
   installed**, then use **Install telemetry mod**. Confirm it changes to
   **Installed and verified** and displays a target inside the detected AppID
   292030 game directory under lower-case `mods`. If an older upper-case
   `Mods` copy exists, confirm Repair migrates or preserves it explicitly. The
   companion archive in `out/` remains the manual fallback.
2. Add `-net -debugscripts` to Steam launch options, and set
   `DebugScriptsForceFlush=true` under `[Scripts]` in the prefix's
   `user.settings`. Confirm the page detects both launch flags and reports the
   script flush as configured. If either row says it cannot be detected, verify
   the Steam setting manually and retain that exact diagnostic in the report.
3. On Steam Home, confirm the page explains that AppID `292030` is required and
   cannot enable hardware output.
4. Launch The Witcher 3: Wild Hunt - Complete Edition and confirm the quick
   panel offers the experimental page. The checksum-verified Lab must already
   report automatic session management, while no `GCA1` record means it must
   not yet claim the physical bar or display simulated HUD values.
5. Load a save and confirm the source changes to `live WitcherScript telemetry`
   with transport `direct state file`, a recent age and the AppID 292030 Proton
   `GabeCubeAuraTelemetry.ini` path. The first fresh `GCA1` record must arm the
   lab automatically. The namespaced `scriptlog.txt` path is a fallback.
6. Confirm the page reports **Physical bar: GabeCubeAura owns it ·
   witcher-lab…** once Valve is not holding a higher-priority lease, then
   confirm left vitality, centre adrenaline and right stamina are visually
   distinct on the real strip.
7. Take damage, regenerate stamina, drink a potion and gain adrenaline. Confirm
   the displayed values move without touching the manual controls.
8. Raise toxicity and confirm green enters from both outer edges without
   turning the whole diffuser pale.
9. Enter combat below 25 percent vitality and assess whether the red pulse is
   visible but not distracting.
10. Trigger Aard, Axii, Igni, Quen and Yrden. Record colour legibility, direction
   and perceived latency for each.
11. Trigger a Light Event and a countdown. Both must temporarily replace the
   lab and return to the current live state afterward.
12. Cause known Steam activity. The lab must yield without fighting the native
    writer.
    Repeat with a native download animation and verify it remains uninterrupted.
    If a safe thermal-warning test fixture is available, a fixed full red Valve
    signal must also remain above the lab; never induce real overheating for
    this test. After the Steam lease ends, the already verified Witcher session
    must resume without another manual toggle.
13. Exit the game. The lab must turn off and release the bar automatically.
    Confirm Valve's previous hardware effect returns. If Steam's lifetime stop
    callback is absent, the bounded Router fallback must still clear the stale
    game session after 5 consecutive two-second polls.
14. Remove `-net -debugscripts` for one launch and confirm the direct state-file
    transport still updates. The script-log fallback may become unavailable,
    but stale values must never be reused.
15. Before live telemetry has verified the session, enable the manual fallback,
    then select Performance or Artwork in Display Routing. Confirm that manual
    fallback stops. Once live telemetry has enabled automatic session
    management, routing changes must not silently disable it; temporary
    higher-priority Steam/system layers may still replace it.
16. Quit the game, use **Reset / remove gca_telemetry.ws**, and confirm the
    target `gca_telemetry.ws` is no longer the GabeCubeAura file. If installation
    created a backup, confirm it was restored; if the active file was modified,
    confirm the page reports the preserved path. Restarting the game must no
    longer auto-arm the lab.
17. Press **Export Witcher + Screen Sync diagnostics** and retrieve
    `/home/deck/Documents/GabeCubeAura-Witcher3-diagnostics.json`. Confirm it
    contains the lower-case script path, its checksum, the state-file snapshot,
    relevant `GCA1`/compile log lines, physical owner and `stderr_tail` from
    Screen Sync. Attach this JSON unchanged if any physical step fails.

## StripMine coexistence

1. With StripMine active, leave the default Witcher priority on GabeCubeAura
   and confirm the acknowledged handoff completes before the first lab frame.
2. Change the Witcher priority to StripMine and confirm enabling the lab does
   not take the bar.
3. Change it back and confirm ownership returns without a false third-party
   conflict or stale-frame restoration.

## Pass criteria

- every frame contains exactly 17 bounded RGB pixels;
- no output is possible for an AppID other than `292030`;
- live values expire within 1.5 seconds when the game-side stream stops;
- higher-priority Steam and GabeCubeAura layers remain intact;
- leaving the game always disables the transient lab state;
- beta2 settings, routing, Screen Sync and controller behavior regressions pass;
- physical observations remain recorded separately from software test results.
