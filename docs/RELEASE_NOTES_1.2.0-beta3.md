# GabeCubeAura 1.2.0-beta3

This public prerelease carries every beta2 controller, Screen Sync, Weather and
update-channel change into a dedicated The Witcher 3 physical-light experiment.

## Beta update channel and documentation

- Publish `v1.2.0-beta3` as a GitHub prerelease with the exact versioned ZIP and
  `SHA256SUMS`; Stable remains the default channel.
- Start a fresh check immediately when Beta is selected, bypass stale ETags on
  manual checks, and preserve the verified confirmation and rollback flow.
- Keep the updater's helper isolated from Decky's bundled runtime libraries and
  recover completed or superseded transactions after restart.
- Accept both historical `-beta.3` and package-style `-beta3` tags while
  requiring every beta tag to be marked as a GitHub prerelease.
- Add target-hardware GIFs for Screen Sync and the experimental Witcher Lab,
  plus a four-controller animation generated from the updated Concept Lab.

## Screen Sync and session fixes

- Keep an already-verified Witcher HUD session through a false stop inferred
  only from Steam's temporarily empty running-app collection. The bar is
  released during the gap, but the same poll-discovered AppID resumes its HUD
  instead of exposing the underlying Customization+ display. A real Steam
  lifetime stop still clears the session proof.
- Export the master output switch and current Home, in-game and per-game
  display routing with the Witcher diagnostics.
- Do not let an armed Witcher laboratory prevent the Screen Sync capture worker
  from starting. A selected Screen Sync game route or manual preview is now the
  authoritative display request while its lease is active.
- Do not flash the orange Customization+ fallback during the one-second native
  Game Launches handoff. Keep Valve's verified frame, or a real Screen Sync
  frame if already ready, until the launch animation begins.
- Show whether the shared render loop is live, how fresh its decision is and
  the last retained runtime fault so a frozen provider can be diagnosed without
  a terminal.
- Restore the verified Valve state and retry after an isolated runtime failure
  instead of leaving the last plugin frame frozen and terminating the loop.
- Search every local PipeWire runtime instead of stopping at the first valid
  socket, which may belong to Decky rather than the Gaming Mode session.
- Accept a node named exactly `gamescope` even when optional video metadata is
  absent, and expose the selected PipeWire session plus bounded discovery
  details in the settings page.
- Try the stable `target-object=gamescope` source directly when the PipeWire
  session is reachable but `pw-dump` does not enumerate a Gamescope node. This
  removes registry discovery as an unnecessary prerequisite for capture.
- Although the plugin needs Decky's root flag for LED sysfs access, launch its
  PipeWire clients as the owner of `/run/user/1000`. This prevents the root
  backend from seeing a restricted registry while Steam and Gamescope run as
  the Gaming Mode user.
- Use PipeWire's current stable-name selector for Gamescope, with an automatic
  retry through the legacy numeric node selector when required.
- Treat Steam's live `RunningApps` collection as confirmation for
  `MainRunningApp`. This prevents a closed game and its per-game display from
  returning when GabeCubeAura outputs are re-enabled.
- Keep the bounded five-poll grace period so brief Router gaps in menus and
  overlays do not cause a false game exit.
- Terminate the active GStreamer process on every real AppID transition and
  start a fresh capture session when Screen Sync remains requested. An
  idempotent liveness check also recreates the supervisor if the old process
  finishes just after the transition.

## The Witcher 3 experimental HUD lab

- Detect The Witcher 3: Wild Hunt - Complete Edition through Steam AppID
  `292030`.
- Accept live vitality, stamina, toxicity, adrenaline, combat and Sign events
  from the optional WitcherScript companion mod through a bounded direct state
  file, with Proton's script log retained as a diagnostic fallback.
- Show whether the active source is live telemetry or the manual fallback, its
  transport, age and discovered file path.
- Install or repair the bundled telemetry script directly from the top of the
  Witcher page, with exact AppID discovery, checksum verification and a backup
  before replacing different existing content.
- Keep an always-visible **Reset / remove gca_telemetry.ws** button on the same
  page. It checks both lower-case `mods` and the former upper-case `Mods` path,
  restores a previous backup and preserves unknown modified content rather
  than deleting user content.
- Install new and repaired copies in lower-case `mods`; safely migrate the
  incorrect upper-case path that SteamOS may not compile.
- Export a recoverable `GabeCubeAura-Witcher3-diagnostics.json` to Documents
  with exact script/state/log evidence and recent Screen Sync GStreamer errors.
- Expose a dedicated in-game settings page only when that AppID is running.
- Manually simulate vitality, stamina, toxicity, three adrenaline points and
  combat state through GabeCubeAura's real 17-LED renderer.
- Play bounded centre-out Aard, Axii, Igni, Quen and Yrden reactions using the
  game's existing controller-light RGB meanings.
- Stop and release the experimental output automatically when the game exits.
- Automatically arm the Lab when AppID 292030 launches with the matching
  installed bridge and disarm it on game exit. A matching checksum alone does
  not claim the physical bar or pretend that Remastered telemetry works: the
  first fresh `GCA1` record enables the real HUD frame.
- Read WitcherScript's `scriptlog.txt` and the `scriptslog.txt` spelling
  observed in the returned Steam Machine diagnostics. Only namespaced `GCA1`
  records are accepted from either bounded log.
- Require `-net -debugscripts` in Steam launch options. The earlier
  `-debugscripts`-only instruction did not enable the complete WitcherScript
  debug/logging configuration expected by the `LogChannel` bridge.
- Show whether both launch flags and `DebugScriptsForceFlush=true` were found,
  plus the number of bounded Proton log locations checked and the first
  expected path when no log exists.
- Let a deliberate Display Routing change stop the experimental override so
  the selected Performance or Artwork display takes effect immediately.
- Recover from a missing Steam lifetime-stop callback after a bounded empty
  running-app grace period instead of retaining The Witcher 3 forever.
- Keep Steam activity, game-launch effects, brief events and playtime
  countdowns above the lab.
- Preserve hard Valve priority for native download animations and fixed red
  critical thermal/system warnings. These temporarily replace the lab and the
  verified game session resumes only after Steam releases its lease.
- Coordinate the lab with StripMine through an explicit compatibility priority;
  GabeCubeAura is the default because activating the lab is a deliberate test.
- Claim the Valve controller's real `manual` hardware mode for direct RGB
  frames, then restore its prior effect and enabled state when the lab or any
  other GabeCubeAura output releases the bar.
- Display the actual physical owner in the Witcher page so an active simulation
  can no longer be confused with a frame that reached the LED controller.
- Label the laboratory as physically active only when the arbiter really chose
  a `witcher-lab` provider; otherwise show it as armed with the selected provider.

## Current boundary

The bridge is implemented, software-tested and has produced live `GCA1`
telemetry through the script-log fallback on the physical Steam Machine. The
direct `GabeCubeAuraTelemetry.ini` transport was not present in that diagnostic,
so it remains an attempted primary path rather than a physically confirmed one.
The lack of `precompiled.rsblob` is not by itself a PC incompatibility: loose
`.ws` scripts remain supported on PC, while a first live `GCA1` record is still
the plugin's runtime proof for automatic activation.
It does not read process memory, inject a native DLL or change gameplay. Manual
controls remain available when live telemetry is absent or older than 1.5 seconds.

## Installation

Install `GabeCubeAura-v1.2.0-beta3.zip` through Decky Developer settings without
extracting it. Keep the beta2 or stable ZIP and a configuration export available
for rollback.

For the Witcher bridge, put `-net -debugscripts` in Steam's Launch Options and
set `DebugScriptsForceFlush=true` under `[Scripts]` in `dx12user.settings` or
`user.settings` inside the AppID 292030 Proton prefix. The plugin reports the
exact detected path and whether each requirement is present.

Software tests cannot confirm physical direction, diffuser appearance, Steam
ownership or felt reaction latency on the official Steam Machine. Use the
[beta3 validation plan](BETA_TEST_PLAN_1.2.0-beta3.md).
