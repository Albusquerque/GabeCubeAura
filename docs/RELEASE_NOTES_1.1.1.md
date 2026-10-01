# GabeCubeAura 1.1.1

## Update notice

The updater in this release can download and verify a new package, but may fail
with `Could not start the independent update helper` when installation begins.
Install [GabeCubeAura 1.1.2](https://github.com/Alyenax/GabeCubeAura/releases/tag/v1.1.2)
once through Decky Developer settings. Updates after 1.1.2 can use the repaired
in-plugin flow.

GabeCubeAura 1.1.1 is a deliberately small maintenance release built directly
from 1.1.0. Its purpose is to validate the public stable OTA path before the
larger 1.2.0 beta is offered. It does not include Screen Sync, new Weather
animations, support for three or four controllers, or any other 1.2.0 feature.

## Update scheduling

- Choose automatic checks every 15 minutes, 1, 3, 6, 12 or 24 hours.
- Keep 24 hours as the default interval.
- Run one automatic check when Steam loads GabeCubeAura if automatic checks are
  enabled, even when the previous periodic deadline has not yet expired.
- Keep one notification per newly discovered version.

## Stable and Beta channels

Stable remains the default and accepts only normal GitHub releases. Beta is
opt-in and accepts published GabeCubeAura beta prereleases as well as later
stable releases.

Changing channel starts a release check immediately. When a newer beta is
available, GabeCubeAura uses the same Decky notification, verified download and
explicit installation confirmation as a stable update.

An installed beta can also return to the current stable release. GabeCubeAura
labels this action as a return to Stable instead of a normal update, downloads
and verifies the stable package, preserves settings and artwork caches, and
requires confirmation before restarting Decky. If the target build does not
acknowledge a healthy startup, the updater restores the previously working
build.

## Installation

The 1.1.0 to 1.1.1 update path was used to validate the corrected helper locally.
Public 1.1.0 and 1.1.1 installations should install 1.1.2 manually once.

For a manual installation:

1. Install [Decky Loader](https://decky.xyz/) if needed.
2. Download `GabeCubeAura-v1.1.1.zip` from this release.
3. In **Decky > Settings > General**, enable **Developer mode** if the
   **Developer** page is not visible.
4. Open **Decky > Settings > Developer** and choose
   **Install Plugin from ZIP File** under **Third-Party Plugins**.
5. Select the ZIP without extracting it.

The release also provides `GabeCubeAura.zip` as a fixed-name recovery download
and `SHA256SUMS` for both archives.

## Validation result

The complete 1.1.0 to public 1.1.1 update succeeded on the Steam Machine with
the corrected helper launcher. Version 1.1.2 carries that correction for future
updates.

## Coming very soon on the Beta channel

- Support for up to four controllers.
- Responsive real-time Screen Sync inspired by Hue Ambilight.
- Improved night Weather patterns built around a proper night-blue background.
- The Witcher 3 Lab, an experimental mod for visualising HUD elements on the
  light bar in real time.

These features are not part of 1.1.1. Users can opt into the Beta channel when
the first public 1.2.0 beta is ready.
