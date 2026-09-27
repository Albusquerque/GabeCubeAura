# GabeCubeAura 1.0.0

GabeCubeAura is the new name of SignalBar. This release keeps existing settings
and artwork caches while introducing independent Home and in-game displays,
Customization+ and artwork-driven game launch animations.

## Highlights

- Separate permanent displays for Steam Home and games, plus per-game overrides.
- Customization+ with 61 patterns, one to three exact RGB colours, brightness,
  direction and speed.
- Game Launches with local Hero, Header or Capsule colour extraction, two or
  three dominant colours, ten patterns and a 3 to 45 second timer.
- Temporary launch, playtime, controller and Steam-event layers that return to
  the selected permanent display.
- Standard Decky left-side settings navigation.
- Full configuration export, import and reset.
- Coordinated ownership with StripMine, developed by the same author.

## Upgrade from SignalBar

Install `GabeCubeAura-v1.0.0.zip` through Decky Developer settings. On first
launch, GabeCubeAura imports existing SignalBar settings and artwork caches. The
source configuration is copied once and is not deleted.

The Python `signalbar` namespace, saved setting keys and the StripMine handoff
identity remain unchanged for compatibility.

## Verification

Version 1.0.0 passed the complete backend and frontend suites, TypeScript
checking, bundle creation, ZIP integrity checks and target Steam Machine tests.
The packaged ZIP is accompanied by `SHA256SUMS`.

## Install

1. Download `GabeCubeAura-v1.0.0.zip` from this release.
2. Open **Decky > Settings > General** and enable **Developer mode** if the
   **Developer** page is not already visible.
3. Open **Decky > Settings > Developer**. Under **Third-Party Plugins**, choose
   **Install Plugin from ZIP File**, then select **Browse**.
4. Select the downloaded archive without extracting it and confirm the
   installation.
5. Restart Decky Loader if GabeCubeAura does not appear immediately.
