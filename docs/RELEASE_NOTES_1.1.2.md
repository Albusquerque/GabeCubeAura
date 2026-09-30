# GabeCubeAura 1.1.2

GabeCubeAura 1.1.2 is a focused recovery release for direct updates. It contains
no Screen Sync, Weather, controller or other 1.2.0 feature changes.

## Fixed

Decky Loader can expose bundled runtime libraries to commands started by a
plugin. The updater previously passed that environment unchanged to the SteamOS
`systemd-run` binary. On the Steam Machine, the package downloaded and verified
correctly, but installation stopped with `Could not start the independent
update helper`.

Version 1.1.2 removes Decky's library and Python runtime overrides before
starting the helper. If helper startup still fails, the original system detail
is retained in the Decky backend log for diagnosis.

After Decky restarts, the running backend now reloads the terminal transaction
state written by the helper instead of retaining an in-memory
`restart_pending` snapshot. A healthy replacement backend can also recover that
state after a short grace period, which re-enables update checks and Stable or
Beta channel selection. A newer manual installation also closes an older
`restart_pending` transaction automatically instead of inheriting its lock.

## One-time manual installation

Versions 1.0.0, 1.1.0 and 1.1.1 must install 1.1.2 manually. The correction has
to be present in the currently running plugin before it can launch an update.
After 1.1.2 is installed, future stable or beta releases can use the normal
in-plugin notification, download, verification and confirmation flow.

1. Install [Decky Loader](https://decky.xyz/) if needed.
2. Download `GabeCubeAura-v1.1.2.zip` from this release.
3. In **Decky > Settings > General**, enable **Developer mode** if the
   **Developer** page is not visible.
4. Open **Decky > Settings > Developer** and choose
   **Install Plugin from ZIP File** under **Third-Party Plugins**.
5. Select the ZIP without extracting it.

Settings and artwork caches remain in Decky's settings directory and are kept
during this installation.

## Validation

The corrected launcher was tested on the Steam Machine by installing a local
1.1.0 test build and updating it to the unmodified public 1.1.1 release. Decky
restarted and GabeCubeAura completed the update successfully.

Automated validation covers the contaminated Decky environment, release
discovery, checksum enforcement, package validation, directory exchange,
healthy startup acknowledgement and rollback. The release package is also
checked for its root directory, required files, version and SHA256 value.
