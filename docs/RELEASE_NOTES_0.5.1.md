# SignalBar 0.5.1

SignalBar 0.5.1 makes saved settings easier to review and retrieve, while
keeping the README focused on the plugin itself.

## Configuration export

Open **Detailed settings > Advanced / debug**, enable **Show debug details**,
then choose **Export configuration JSON**. On a standard SteamOS installation,
the file is available in Desktop Mode at:

`/home/deck/Documents/SignalBar-configuration.json`

The panel displays the exact path after each successful export. The JSON
contains global settings, saved per-game Display and Artwork profiles, and the
current game's resolved choices. It omits controller device identifiers and
runtime hardware diagnostics. Re-exporting atomically replaces only this file.

## Documentation polish

- The README now moves directly from the short SignalBar introduction and
  download link to Artwork, Performance, Playtime, controllers, and events.
- The controller-battery animation is smaller and uses a softer LED glow.

## Install

Download **SignalBar-v0.5.1.zip** below. In Decky Loader, open **Settings >
Developer > Install Plugin from ZIP** and select the archive without extracting
it. Restart Decky Loader if SignalBar does not appear immediately.

Existing settings are preserved when upgrading from 0.5.0.

For full details, see the [README](https://github.com/Alyenax/SignalBar#readme)
and [changelog](https://github.com/Alyenax/SignalBar/blob/v0.5.1/CHANGELOG.md).
