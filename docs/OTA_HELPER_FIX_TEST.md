# OTA helper launch fix test

Status: passed on the Steam Machine on 2026-09-30.

The public `1.1.1` release is not modified by this test.

## Failure identified

Decky Loader can expose bundled runtime libraries through `LD_LIBRARY_PATH`.
Passing that environment unchanged to the SteamOS `systemd-run` binary can make
the binary load Decky's libraries instead of the matching system libraries. The
update then stops after verification with `Could not start the independent
update helper`.

The local correction removes Decky's library and Python runtime overrides before
starting `systemd-run`. The original failure detail is also written to the Decky
backend log if helper startup still fails.

## Physical test package

The local test archive deliberately reports version `1.1.0` while containing the
corrected helper launcher. It must discover the existing public `1.1.1` release,
download it, verify it, restart Decky and finish on the real `1.1.1` build.

No tag, release or remote branch is created for this test package.

## Expected result

1. Install the local test archive through Decky Developer settings.
2. Open GabeCubeAura, then Updates.
3. Check for updates and prepare `1.1.1`.
4. Select `Update and restart Decky` and confirm.
5. Decky restarts and GabeCubeAura reports version `1.1.1`.
6. Existing GabeCubeAura settings remain unchanged.
