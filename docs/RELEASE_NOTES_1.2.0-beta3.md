# GabeCubeAura 1.2.0-beta3

This opt-in public preview adds real-time Screen Sync, fixed layouts for up to
four controllers, richer night Weather scenes and an experimental live HUD
bridge for The Witcher 3: Wild Hunt: Complete Edition / Remastered.

## Highlights

- Screen Sync maps the live Gamescope picture to 17 LEDs in Panorama or
  Ambient mode and restarts cleanly when the running game changes.
- Controller display supports one to four fixed battery seats, with automatic
  mirrored layouts for two and four players and editable P1-P4 colours.
- The experimental Witcher 3 Lab reacts to vitality, stamina, toxicity,
  adrenaline, combat and Sign casts from the optional WitcherScript bridge.
- The Witcher page can install, verify, repair or safely remove the bundled
  script and export a focused diagnostic JSON to Documents.
- Selecting the Beta update channel checks immediately. Downloads still require
  confirmation and are verified against package metadata and `SHA256SUMS`.

## The Witcher 3 experimental Lab

The Lab targets Steam AppID `292030`. A checksum-valid script only arms the
feature: the bar is not claimed until a fresh `GCA1` telemetry record proves
that the current game session is live. When telemetry stops or the game exits,
GabeCubeAura releases the experimental output instead of replaying stale data.

The direct `GabeCubeAuraTelemetry.ini` transport remains experimental. Live
telemetry has been observed on the target Steam Machine through namespaced
records in the script-log fallback.

### Required setup

1. Install or repair the bridge from the top of the Witcher page, then restart
   the game so WitcherScript recompiles.
2. In Steam Launch Options, enter exactly `-net -debugscripts`.
3. Reopen the Witcher page and check the reported script, telemetry and
   physical-owner states. No manual settings-file edit is required.

## Safety and coexistence

Steam downloads, repeated native Valve writes and the fixed red critical
thermal/system warning remain above every GabeCubeAura display. Launch effects,
brief alerts and playtime countdowns also temporarily replace the Witcher HUD
or Screen Sync, then the selected display resumes. Changing Display Routing or
leaving The Witcher 3 releases the experimental Lab.

Screen Sync now discovers the active Gaming Mode PipeWire session more
reliably, recovers after an isolated capture/runtime failure and avoids showing
the saved Customization+ fallback during the native game-launch handoff.

## Install and rollback

Install `GabeCubeAura-v1.2.0-beta3.zip` through Decky Developer settings without
extracting it, or select Beta from GabeCubeAura's Updates page. Keep the stable
v1.1.3 ZIP and a configuration export available for rollback.
