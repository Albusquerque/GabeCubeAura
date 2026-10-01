# GabeCubeAura 1.2.1

GabeCubeAura 1.2.1 brings real-time Screen Sync, fixed layouts for up to four
controllers, richer night Weather scenes and safer recovery across Steam,
Gamescope and Decky session changes.

## Highlights

- Screen Sync maps the running game's Gamescope picture across the 17 LEDs in
  Panorama mode, or uses one calmer colour in Ambient mode.
- Steam's screensaver can temporarily use Screen Sync, then the selected Home
  or in-game display returns automatically.
- Failed or PAUSED capture sessions are closed before retry. Gamescope and
  PipeWire rediscovery is rate-limited after Desktop Mode, Gaming Mode,
  suspend and screensaver transitions.
- Controller status supports one to four fixed seats. The Automatic colour
  preset uses battery colours for one controller and distinct player colours
  from two controllers onward.
- Weather adds eight night scenes and Customization+ exposes the four new
  night-cloud patterns.
- Steam activity, downloads, native hardware effects and thermal warnings keep
  priority over plugin output.
- The standalone [TW3 SteamRGB](https://github.com/Alyenax/TW3-SteamRGB)
  companion can replace only the permanent display while its live Witcher HUD
  claim is active. Alerts, Game launches and playtime countdowns stay above it.

The experimental Witcher telemetry Lab is not bundled with GabeCubeAura. It is
distributed separately through TW3 SteamRGB.

## Installation

Download `GabeCubeAura-v1.2.1.zip` and install the archive through Decky Loader
without extracting it. The archive and `SHA256SUMS` file are attached to this
release.

Software tests cover rendering, routing, capture recovery, ownership and
packaging. Physical direction, diffuser appearance and reaction latency still
depend on the SteamOS build and target Steam Machine hardware.
