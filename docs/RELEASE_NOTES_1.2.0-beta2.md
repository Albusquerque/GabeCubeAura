# GabeCubeAura 1.2.0-beta2

This local beta builds on 1.2.0-beta1 and adds the approved one-to-four
controller system from the GabeCubeAura concept mockup.

## Controllers

- Render one to four reported controllers in stable player seats.
- Keep the existing mirrored 8 + centre + 8 layout for two controllers.
- Use three ordinary left-to-right 5-LED zones with two dark separators for
  three controllers.
- Use four 4-LED seats around a dark centre for four controllers. The two seats
  on each side use opposing directions, matching the approved mirrored layout.
- Keep the three existing multiplayer patterns and their public names: Twin
  reveal, Two signatures and Mirror greeting. The two-controller timing and
  pixel rules remain unchanged.
- Reuse those three patterns when a third or fourth controller joins instead of
  falling back to the single-controller connection signal.
- Add a Colour meaning choice. Battery level keeps the existing Healthy,
  Medium, Low and Charge palette. Player seats adds editable P1, P2, P3 and P4
  colours.
- Keep low-battery and charging signals semantic in both colour modes. White
  motion and endpoint pixels remain white.
- Add a local preview setup for one to four sample controllers and a target
  controller. Preview choices never replace Steam's detected controller list.
- Draw all three brief charging signals inside the actual or previewed P1, P2,
  P3 or P4 seat.
- Show 55 percent Lightness in the colour picker for every default Player seats
  colour. Existing custom colours are preserved during migration.
- Limit the rendered and reported roster to the first four stable Steam
  controller identities.

## Updates

- Choose an automatic check interval of 15 minutes, 1, 3, 6, 12 or 24 hours.
- Keep Stable as the default channel, or opt into Beta releases from the
  Updates page.
- Let the Beta channel discover both published beta releases and later stable
  releases. Both channels retain the existing SHA256, package validation,
  confirmation and rollback protections.

The channel selector does not publish or upload a build. To feed the Beta
channel, publish a GitHub release such as `v1.2.0-beta2`, mark it as a
prerelease, and attach both `GabeCubeAura-v1.2.0-beta2.zip` and `SHA256SUMS`.
Draft releases and tags without a published release are ignored.

## Continuity fixes carried into beta2

- Detect Steam's screensaver through its read-only state capability, use state
  notifications when available and keep polling as a fallback.
- Let screensaver Screen Sync replace every permanent Home display, including
  Weather and Controllers, while preserving temporary alerts and Steam system
  priority.
- Retry Steam Families registration when Steam's service is unavailable during
  plugin startup, and rebuild it after resume.
- Preserve the confirmed game session through temporary overlay, menu and idle
  gaps so the playtime bar does not restart without a real game transition.
- Keep old SignalBar Signals only and Disabled configurations from reviving
  dormant per-game Artwork or Performance overrides during migration.

## Existing beta features

Screen Sync, Steam screensaver activation, recording fallback, Steam ownership
guards and richer night Weather scenes remain based on 1.2.0-beta1.

Night passing shadow and Night passing shadows now keep the sky night blue and
move low-white RGB 35 clouds across it. The previous beta had those foreground
and background colours reversed.

## Installation

1. Install [Decky Loader](https://decky.xyz/) if it is not already installed.
2. Open Decky Settings, General, then enable Developer mode.
3. Open Decky Settings, Developer, then choose Install Plugin from ZIP File.
4. Select `GabeCubeAura-v1.2.0-beta2.zip` without extracting it.
5. Restart Decky Loader if the plugin does not appear immediately.

The updater starts on Stable. Beta is an explicit choice and no channel installs
anything without confirmation.

## Validation status

Backend, frontend, TypeScript, production build and archive tests can validate
the data flow and exact 17-pixel frames on the development machine. Physical
appearance, Steam controller ordering and charging reports still require an
official Steam Machine and the relevant controllers.

Use the [beta2 validation plan](BETA_TEST_PLAN_1.2.0-beta2.md) before replacing
a daily-use build.
