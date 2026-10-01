# GabeCubeAura 1.2.1-beta.1 local validation plan

This build is local only. Do not expect it to appear in the plugin's Beta
update channel unless it is published later as a GitHub prerelease.

## Package checks

1. Confirm the plugin reports `1.2.1-beta.1`.
2. Compare the archive checksum with `out/SHA256SUMS`.
3. Confirm the archive contains one `GabeCubeAura/` root and no game telemetry
   Lab provider, installer, companion script, route or setting.
4. Install the version through Decky Developer settings and confirm the plugin
   loads without resetting existing settings.

## Regression checks

1. Test Home and in-game routing with GabeCubeAura Off, Customization+,
   Performance, Artwork, Weather, Controller status and Screen Sync.
2. Verify Screen Sync starts for a selected game route, the bounded preview
   and Steam screensaver activation, then releases capture when each request
   ends.
3. Verify Steam Game Recording or another capture consumer activates the saved
   Customization+ fallback instead of competing for the capture stream.
4. Connect one to four controllers and verify each battery seat, charging state
   and enabled alert pattern.
5. Verify Game launches, Light events and the final five minutes of a Playtime
   warning retain their documented priority.
6. Verify Steam startup, downloads, repeated native LED activity and fixed red
   system warnings keep physical ownership above every plugin display.

Software tests can validate routing, packaging and ownership decisions. The
physical light direction, diffuser appearance and reaction latency still need
validation on the target Steam Machine.
