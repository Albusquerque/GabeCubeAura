# GabeCubeAura 1.1.3

GabeCubeAura 1.1.3 completes the direct updater recovery. It does **not** include
Screen Sync, the new Weather animations, 4-controller support, or any of the
other changes currently in the 1.2.0 beta.

## Fixed

**Check now** previously reused the ETag saved by an earlier automatic request.
If the local update state had been cleared while that ETag remained, GitHub
could correctly answer `304 Not Modified` but the plugin had no available
release left to display. Changing between Stable and Beta cleared the cached
request and made the release appear, which explained the inconsistent result.

A manual check now always requests the complete current release. Automatic
checks still use conditional ETag requests to avoid unnecessary downloads.
Changing channel continues to check immediately, but is no longer required to
find a newly published release.

This new version also ensures that installations which received the original
1.1.2 package can discover and install the correction through the normal OTA
flow.

## Included updater safeguards

- Stable and Beta channels with immediate checks when the channel changes.
- Automatic intervals of 15 minutes, 1, 3, 6, 12 or 24 hours.
- HTTPS, metadata, checksum, archive path and package version verification.
- An independent helper that starts outside Decky's bundled runtime libraries.
- Healthy-start acknowledgement and automatic rollback when a replacement does
  not start correctly.
- Recovery from completed or superseded `restart_pending` transactions.

## Installation

Users already running 1.1.2 can install 1.1.3 from **Settings > Updates**.

Versions 1.0.0, 1.1.0 and 1.1.1 need one manual installation because their
currently running updater cannot reliably start the independent helper:

1. Install [Decky Loader](https://decky.xyz/) if needed.
2. Download `GabeCubeAura-v1.1.3.zip` from this release.
3. In **Decky > Settings > General**, enable **Developer mode** if the
   **Developer** page is not visible.
4. Open **Decky > Settings > Developer** and choose
   **Install Plugin from ZIP File** under **Third-Party Plugins**.
5. Select the ZIP without extracting it.

Settings and artwork caches remain in Decky's settings directory.

## Validation

The correction was verified on the Steam Machine with a local package reporting
version 1.1.0. While staying on Stable, **Check now** detected the public 1.1.2
release directly, without the previous channel-change workaround.

Automated validation covers forced manual refresh, conditional automatic
checks, channel selection, release discovery, checksum enforcement, package
validation, helper launch, restart-state recovery, healthy startup
acknowledgement and rollback.
