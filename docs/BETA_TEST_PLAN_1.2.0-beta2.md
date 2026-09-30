# GabeCubeAura 1.2.0-beta2 validation plan

This plan separates software checks from physical Steam Machine results. A
passing preview or archive test is not proof of controller detection or light
bar appearance.

## Before installation

1. Keep the beta1 or v1.1.0 ZIP available for manual rollback.
2. Export the current GabeCubeAura configuration from Advanced settings.
3. Disable every other plugin build that can write to the light bar.
4. Compare the beta2 ZIP checksum with `out/SHA256SUMS`.
5. Install the ZIP through Decky Developer settings without extracting it.

## Basic smoke test

1. Confirm the plugin opens and reports version `1.2.0-beta2`.
2. Confirm Home, in-game and per-game choices survived the upgrade.
3. Preview Artwork, Customization+, Weather, Screen Sync and one Light Event.
4. Confirm the Controllers page reaches its last Preview button with a gamepad.
5. Confirm no Decky restart loop, frozen page or permanent wrong LED owner.

## Controller preview campaign

Run all three Multiple controllers styles with 2, 3 and 4 selected sample
controllers.

- Two controllers must use mirrored 8-LED halves and a dark centre.
- Three controllers must use 5 LEDs, a dark separator, 5 LEDs, another dark
  separator and 5 LEDs. Every zone must fill left to right.
- Four controllers must use four 4-LED seats and a dark centre. P1 and P2 must
  oppose each other on the left; P3 and P4 must oppose each other on the right.
- After each introduction, every non-empty seat must have one white endpoint.
- Switching between Battery level and Player seats must update the permanent
  gauge and multiplayer previews immediately.
- Editing P1 to P4 must affect only the matching fixed seat.
- Low-battery and charging previews must retain their warning colours in Player
  seats mode.
- Connection, low-battery and charging previews must use the selected preview
  controller without changing Steam's live roster.
- Repeat Current, Breathing current and Spark with P1, P2, P3 and P4 selected.
  Motion must remain inside the selected seat.
- Repeat the same campaign with four live controllers and briefly start charging
  each one. The active seat must follow the physical controller.
- On a fresh configuration, every P1 to P4 colour picker must report 55 percent
  Lightness. A previously customised colour must survive the upgrade.

## Live controller campaign

Connect controllers one at a time up to four, then disconnect them in a
different order.

1. Confirm each Steam identity keeps its seat when Steam reorders a later poll.
2. Confirm the second, third and fourth connection uses the selected Multiple
   controllers pattern.
3. Confirm a disconnected controller disappears without swapping the remaining
   controller identities during the same update.
4. Test one charging controller in every seat with Continuous on Home and
   Continuous everywhere.
5. Reach 100% if practical and confirm the completion cue stays inside that
   controller's seat before the normal gauge returns.
6. Repeat with one controller that reports only a coarse Steam battery level.
   The UI must not invent an exact percentage.

## Regression campaign

Repeat the Screen Sync, Steam Families, Weather and coexistence sections from
the beta1 validation plan. In particular, verify recording fallback, the red
centre recording marker, Steam startup and download priority, overlay recovery
and playtime continuity after suspend.

## Update channel campaign

1. Keep Stable selected and confirm a GitHub prerelease is not offered.
2. Select Beta and confirm a newer published beta is offered.
3. Confirm the Beta channel prefers a later stable release when one exists.
4. Test 15 minutes, 1, 3, 6, 12 and 24 hours. Confirm the selected interval
   survives a Decky restart.
5. Confirm Check now works with automatic checks disabled.
6. Download a beta ZIP and confirm checksum and package validation complete
   before the install button becomes available. Do not publish a test release
   solely for this step without a matching SHA256SUMS asset.

The expected publication fixture is a published GitHub prerelease tagged
`v1.2.0-beta2` with `GabeCubeAura-v1.2.0-beta2.zip` and `SHA256SUMS`. A draft,
a bare Git tag or an archive with another filename must not be offered.

## Pass criteria

- every frame remains exactly 17 LEDs;
- no controller index error with zero to four connected controllers;
- two and four use the approved mirrored layouts;
- three always fills every seat left to right;
- existing one-controller and two-controller patterns keep their timing;
- higher-priority Steam activity and countdowns still win;
- configuration export, reinstall and rollback preserve all prior settings.

Record controller model, connection type, reported battery data, chosen colour
mode and any physical diffuser observations for each live test.
