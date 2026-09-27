# SignalBar v0.7.0

SignalBar v0.7.0 adds **Light Events only**, directly answering the request in
[issue #1](https://github.com/Albusquerque/SignalBar/issues/1). Notifications,
achievements, screenshots, and recording cues can now use the light bar without
keeping Artwork or Performance active between events.

## Light Events only

- Select **Light Events only** as the default display mode.
- Between events, SignalBar leaves the light bar untouched for Steam or another
  compatible application.
- Existing Artwork and Performance profiles stay saved and become active again
  when their display mode is selected.
- Countdown, alert, and native ownership protections retain their priorities.

## StripMine coordination

SignalBar and StripMine, both developed by the same author, can now share the
physical light bar through their coordinated handoff protocol. Before a short
event, SignalBar publishes a renewable handoff request and
briefly waits for StripMine to yield. After the animation, SignalBar restores
the exact previous frame and releases the handoff so StripMine can resume.

The handoff is fail-safe: leases expire after a crash, and StripMine verifies
the restored LED signature before reclaiming the bar. Local lifecycle tests
pass, but the transition still needs confirmation on the physical Steam
Machine.

## Install

Download `SignalBar-v0.7.0.zip` below. In Decky Loader, open **Settings >
General** and enable **Developer mode** if the **Developer** section is not
already visible. Then open **Developer > Install Plugin from ZIP** and select
the archive without extracting it.

Existing settings are preserved when upgrading.

For complete details, see the [README](https://github.com/Albusquerque/SignalBar#readme)
and [changelog](https://github.com/Albusquerque/SignalBar/blob/v0.7.0/CHANGELOG.md).
