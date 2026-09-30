# GabeCubeAura 1.2.0-beta1

This local beta combines GabeCubeAura 1.1.0 with real-time Screen Sync and the
night-weather work prepared in the weather transposition mockup.

## What is new

- Screen Sync maps the current Gamescope picture to the 17 LEDs in real time.
  Panorama uses 17 horizontal zones. Ambient uses one calmer screen colour.
- Screen Sync can be the in-game default, a per-game choice, a 15-second manual
  preview, or an independent Steam screensaver effect.
- Steam Game Recording and another active Gamescope capture consumer pause
  Screen Sync. The saved Customization+ effect takes over, with the permanent
  red centre recording marker when that Light Event is enabled.
- A Steam-lifetime session latch keeps the game AppID through temporary menu,
  overlay and idle gaps. Restoring the selected display no longer depends on
  moving a controller.
- Steam Families registration now retries when the service is not ready during
  plugin startup, and is rebuilt after resume instead of silently remaining
  inactive for the whole game session.
- Upgrading a v0.7.x Signals only or Disabled configuration no longer
  reactivates dormant per-game Artwork or Performance displays. Per-game
  artwork sampling choices are preserved.
- Steam startup, download activity and repeated native LED writes retain hard
  priority. GabeCubeAura resumes only after that activity settles.
- Weather now has 22 selectable loops. The beta adds 8 night transpositions:
  Breathing moon, Lunar bloom, four night-cloud patterns, Moon through clouds
  and Moon, fading clouds.
- Customization+ exposes 65 effects grouped as Calm & ambient, Flowing and
  Energetic.
- The direct updater, rollback protection and stable notification channel from
  v1.1.0 remain included.

## Installation

1. Install [Decky Loader](https://decky.xyz/) if it is not already installed.
2. Open Decky Settings, General, then enable Developer mode.
3. Open Decky Settings, Developer, then choose Install Plugin from ZIP File.
4. Select `GabeCubeAura-v1.2.0-beta1.zip` without extracting it.
5. Restart Decky Loader if the plugin does not appear immediately.

Disable any second plugin build that controls the same light bar before testing
this beta.

## Update channel

The built-in updater intentionally reads stable GitHub releases only. It does
not download prereleases. The installed beta has a 1.2.0 version core, so the
current v1.1.0 stable release is not offered as a downgrade.

## Validation status

The backend, frontend, TypeScript, production build and package checks pass on
the development machine. Those checks validate processing, arbitration,
settings, migration, archive safety and recovery logic. They do not prove the
Gamescope stream, performance cost or physical LED result on an official Steam
Machine.

Use the [beta validation plan](BETA_TEST_PLAN_1.2.0-beta1.md) for the target
hardware campaign. Report failures with the Screen Sync capture phase, source,
measured frame rate, session state and ownership diagnostics shown in Advanced
settings.
