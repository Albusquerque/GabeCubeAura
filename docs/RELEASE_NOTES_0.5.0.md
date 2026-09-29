# SignalBar 0.5.0

This release adds controller battery signals, per-game display choices, and a
fresh-install setup based on real Steam Machine testing. Existing saved settings
are preserved when upgrading.

## Controller battery

- Read controllers already connected when SignalBar starts, listen for Steam
  connection and battery notifications, and use a background recovery poll.
- Keep live battery readings ahead of older snapshots. A genuine 41% reading
  should no longer be replaced by a stale 100% list value. Unknown battery
  levels are not presented as exact percentages.
- Choose a battery gauge on Home, everywhere, or off. With two controllers, the
  17 LEDs become eight mirrored LEDs per player plus an unlit centre pixel.
  White tips appear after the introduction to mark each charge level.
- Choose separate brief connection and low-battery alerts, their Home/in-game
  visibility, and the low-battery threshold. Alerts play on a real change,
  not on every status poll.
- Choose one charging behavior: Off, Brief, Continuous on Home, or Continuous
  everywhere. Continuous charging moves while Steam reports charging below
  100%, then stops. At 100%, a short completion cue plays.
- Pick from three visual styles for each controller situation, four controller
  colours, and controller-only brightness. Preview buttons use sample data and
  work without a controller connected.

![Two mirrored controller gauges followed by continuous charging](https://raw.githubusercontent.com/Alyenax/GabeCubeAura/main/docs/media/animations/controller-battery.gif)

[Explore the interactive controller mockup](https://alyenax.github.io/signalbar-controller-battery/)

## Other improvements

- Save Artwork or Performance as the display choice for each game. Returning
  Home uses the global default; Disabled still overrides per-game choices.
- CPU/GPU sensors now update in every display mode. Performance settings show
  fresh readings immediately, with stale or failed readings cleared.
- Advanced / debug includes a concise snapshot of saved choices across all
  tabs, including global and per-game Artwork settings. It omits device paths
  and controller identifiers.
- Light events keep their individual animation previews without the duplicate
  preview at the top of the page.

## New-install defaults

Performance starts in mirrored CPU + GPU mode with Balanced response, the
green/yellow/red temperature palette, 45°C and 78°C thresholds, and Home
display enabled. Artwork uses Library Hero and automatic sampling, with the
saved manual row at 34%. Steam Families countdown is enabled, starts white,
and the personal timer preset is 60 minutes.

Light events are enabled with Return beacon notifications, Chromatic rebound
achievements, Expanding echoes screenshots, and an isolated red recording LED.
The controller gauge and continuous charging run on Home; brief alerts run on
Home and in games. The defaults include Bright tip for one controller, Last
ember for low battery, Tidal fill for charging, Mirror greeting for two
controllers, and 65% controller brightness. Physical LED reversal remains on
and Extra dark LEDs remains at two.

These are defaults for a fresh installation. Upgrading does not reset your
existing choices.

## Install

Download **SignalBar-v0.5.0.zip** below. In Decky Loader, open **Settings >
Developer > Install Plugin from ZIP** and choose the archive without extracting
it. Restart Decky Loader if SignalBar does not appear immediately.

## Compatibility note

Controller information comes from private SteamInputManager interfaces and
depends on the controller and connection type. Automated tests cover startup,
live updates, stale snapshots, disconnects, charging and priority rules, but
there is not yet a verified compatibility list for every controller.

For implementation and feature details, see the [README](https://github.com/Alyenax/SignalBar#readme)
and [full changelog](https://github.com/Alyenax/SignalBar/blob/v0.5.0/CHANGELOG.md).
