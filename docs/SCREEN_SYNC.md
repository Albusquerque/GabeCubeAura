# Screen Sync in GabeCubeAura 1.2.0-beta1

Screen Sync is integrated into GabeCubeAura's normal display routing. It uses
the same Providers to Arbiter to Renderer pipeline as Artwork, Performance,
Weather and Customization+. The renderer remains the only production component
that writes to the LED hardware.

## Activation

Screen Sync can run for four reasons:

1. it is the selected in-game display;
2. it is saved for the current Steam AppID;
3. Steam's screensaver is active and the independent option is enabled;
4. the user starts the bounded 15-second preview.

Screensaver and preview activation do not rewrite Home, in-game or per-game
display choices.

## Local capture and processing

The backend discovers the Gamescope video node with `pw-dump`, starts a
GStreamer process without a shell and requests a 34 by 18 BGRx stream at 10
frames per second. Only the newest frame is retained. Captured pixels are not
saved, returned through Decky or sent over the network.

Panorama maps 17 horizontal image zones to 17 LEDs. Ambient calculates one
robust screen colour and repeats it across the bar. Processing includes linear
RGB averaging, bright-HUD reduction, stable cinematic-bar detection, a black
threshold, colour intensity, brightness, spatial blending and asymmetric
temporal smoothing.

## Capture safety

Camera, V4L2 and loopback nodes are rejected. Capture stops when Screen Sync is
no longer requested, the plugin is disabled, a critical countdown wins,
StripMine owns the feature, Steam Game Recording starts, another Gamescope
consumer appears, the stream becomes stale or the plugin unloads.

When capture is unavailable because recording or another consumer is active,
the saved Customization+ effect becomes the fallback. Steam recording can keep
a pure red centre LED over that fallback. Missing capture tools or a missing
Gamescope source produce a visible status error. GabeCubeAura does not install
system packages.

## Steam ownership and continuity

Steam's game-lifetime service confirms the active AppID. Temporary zero values
from `Router.MainRunningApp` during menus, overlays or idle periods do not end
that session. Polling remains a recovery source when lifetime callbacks are
unavailable.

Steam keeps hard priority during startup, active downloads and repeated native
LED writes. One isolated native transition receives a settle period before one
automatic recovery. Genuine system activity can renew the priority lease, so
GabeCubeAura does not fight Steam for the bar.

## Target-hardware checks still required

- Gamescope source discovery in Gaming Mode
- 30 minutes near 10 frames per second without stale frames
- CPU, GPU and frame-time impact in bright, dark and high-motion games
- SDR, HDR, letterboxing, Steam overlay and Quick Access Menu
- launch, exit, switch, suspend and resume continuity
- Steam Game Recording and another capture consumer
- screensaver start and stop without changing saved display routing
- physical left-to-right orientation, diffuser colour and black behaviour
- Steam downloads, Game Launches, Light Events, controllers and countdowns
- StripMine handoff and restoration

Software checks cannot close these hardware items.
