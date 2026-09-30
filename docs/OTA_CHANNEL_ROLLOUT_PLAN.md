# GabeCubeAura OTA channel rollout plan

Date: 2026-09-30

Status: decision recorded, no implementation or publication performed

## Goal

Validate the updater in two deliberately separate stages:

1. Publish a minimal stable `1.1.1` built strictly from the released `1.1.0`.
2. Only after the `1.1.0` to `1.1.1` OTA path has been validated on the Steam Machine, publish `1.2.0-beta.2` for users who explicitly select the Beta channel.

## Stage 1: minimal stable 1.1.1

`1.1.1` must start from the exact `v1.1.0` source, not from the current 1.2.0 beta work.

The only user-facing additions allowed in `1.1.1` are:

- OTA check intervals of 15 minutes, 1 hour, 3 hours, 6 hours, 12 hours and 24 hours.
- Stable and Beta update channels.
- Stable remains the default channel.
- Beta may offer a newer published prerelease as well as a later stable release.

The existing notification, verified download, explicit installation confirmation, Decky restart, health check and transactional rollback behaviour must remain unchanged except where channel support requires a narrowly scoped adjustment.

The following 1.2.0 work must not be included in `1.1.1`:

- Screen Sync.
- Weather changes.
- Three-controller and four-controller support.
- Controller animation or colour changes.
- Playtime changes.
- Any other feature or fix currently present only in the 1.2.0 beta worktree.

Required stable test:

1. Install the public `1.1.0` package on the Steam Machine.
2. Confirm that Stable is the default channel.
3. Publish `1.1.1` as a normal GitHub release with its verified ZIP and `SHA256SUMS`.
4. Let `1.1.0` discover `1.1.1` through its normal OTA path.
5. Confirm that Decky shows one update notification.
6. Download, verify and install `1.1.1` from the plugin.
7. Confirm that GabeCubeAura restarts as `1.1.1` and preserves settings and artwork caches.
8. Confirm that a second check does not repeat the notification for the same version.

`1.1.1` must not be treated as validated until this complete path succeeds on the Steam Machine.

## Stage 2: public Beta channel

Only after Stage 1 succeeds:

1. Keep `main` for stable releases.
2. Use one permanent `beta` branch for the latest testable work.
3. Publish `1.2.0-beta.2` as a GitHub prerelease with a matching verified ZIP and `SHA256SUMS`.
4. On GabeCubeAura `1.1.1`, explicitly select the Beta channel.
5. The channel change must trigger an immediate release check.
6. Confirm that `1.2.0-beta.2` produces the same Decky notification and the same download, verification and confirmation workflow as a stable update.
7. Install it and verify that the plugin reports `1.2.0-beta.2` after Decky restarts.

Local development builds do not need GitHub prereleases. Only a beta intentionally offered to testers is published.

## Returning from Beta to Stable

Changing from Beta to Stable is not a normal version upgrade. For example, `1.2.0-beta.2` is numerically newer than the current stable `1.1.1`, so a normal newer-version comparison would incorrectly report that no stable update is available.

The updater must therefore implement an explicit channel transition:

1. Selecting Stable triggers an immediate check of the latest published stable release, even when the installed beta has a higher version number.
2. If the installed build does not match the latest stable release, the UI offers `Return to stable 1.1.1` rather than describing it as a newer update.
3. The stable archive is downloaded and verified with the same HTTPS, size, path, identity and SHA256 checks as every other update.
4. Installation still requires explicit confirmation.
5. Settings and artwork caches are preserved.
6. If the stable package fails its post-install health check, the transactional installer restores the previously working beta package.
7. After a successful return, the selected channel remains Stable and ordinary stable update checks resume.

This return-to-stable behaviour must be present in both the minimal updater work prepared for `1.1.1` and the updater shipped inside `1.2.0-beta.2`. Once the beta is installed, its own updater is responsible for the return path.

Required channel test:

1. Start on validated `1.1.1` with the Stable channel selected.
2. Select Beta and confirm that the check begins immediately.
3. Confirm notification, download, verification and installation of `1.2.0-beta.2`.
4. After the beta restarts successfully, select Stable.
5. Confirm that the UI offers a return to `1.1.1` despite its lower version number.
6. Download, verify and install the stable package.
7. Confirm that the plugin restarts as `1.1.1`, keeps its data and remains on Stable.
8. Separately rehearse a failed return installation and confirm that the installer restores the working beta.

## Release gate

Do not publish `1.2.0-beta.2` to the Beta channel until all of the following are true:

- The `1.0.0` to `1.1.0` history has not been altered.
- `1.1.1` contains only the scoped updater changes listed above.
- The `1.1.0` to `1.1.1` OTA path has succeeded on the Steam Machine.
- Stable remains the default channel.
- Selecting Beta triggers an immediate check and does not install anything without confirmation.
- Selecting Stable from a beta offers the current stable release even when it is numerically older.
- Both forward installation and transactional recovery have been tested.
- Release ZIP names, embedded versions and checksums all match exactly.

## Current decision

No code, version, branch, tag, release or GitHub state is changed as part of recording this plan.
