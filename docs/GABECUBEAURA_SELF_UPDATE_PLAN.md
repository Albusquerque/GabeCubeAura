# GabeCubeAura direct update plan

Date: 2026-09-29

Status: implemented for GabeCubeAura 1.1.0 and validated locally.

Base: GabeCubeAura `1.0.0`, commit `8b767ef66251f3a4e999d4864b29d6998e896bee`.

## Purpose

Give direct GitHub installations of GabeCubeAura a safe update path without
depending on Decky Plugin Store acceptance.

The plugin should:

- check the official `Alyenax/GabeCubeAura` releases in the background;
- show one Decky notification when a newer stable version is available;
- expose a dedicated Updates page with a manual check and install button;
- never install an update without explicit user confirmation;
- keep settings and artwork caches outside the replaced plugin directory;
- restore the previous plugin automatically if the new version does not start;
- remain easy to disable if Decky manages updates in the future.

This is a plugin update mechanism, not firmware OTA. User-facing wording should
use **Software updates** and **Updates**.

## Fixed product decisions

The first implementation should use these defaults:

- update source: official GitHub Releases for `Alyenax/GabeCubeAura`;
- release channel: stable only;
- automatic checks: enabled;
- check interval: once every 24 hours;
- startup delay: 120 seconds, with small random jitter;
- notifications: enabled;
- notification frequency: once per newly discovered version;
- installation: manual confirmation only;
- automatic background installation: not supported;
- downgrades: not offered by the normal interface;
- preview and prerelease builds: out of scope for the first version;
- dedicated external update server: not required;
- Store coexistence: supported through an isolated provider switch.

The first release containing this code is a bootstrap release. Users already on
1.0.0 must install that release once through Decky Developer settings. Later
versions can then be installed from inside GabeCubeAura.

## Source and trust boundary

### Canonical source

Only this repository is trusted:

`https://github.com/Alyenax/GabeCubeAura`

Release discovery uses:

`https://api.github.com/repos/Alyenax/GabeCubeAura/releases/latest`

The updater must not accept a repository, organization or arbitrary URL from a
saved setting, imported configuration or release response.

### Required release assets

Each future release should contain:

- `GabeCubeAura-vVERSION.zip`, the versioned runtime package;
- `GabeCubeAura.zip`, an identical fixed-name runtime package for recovery and
  Install Plugin from URL;
- `SHA256SUMS`, containing both archive hashes;
- release notes on the GitHub release page.

The fixed recovery URL becomes:

`https://github.com/Alyenax/GabeCubeAura/releases/latest/download/GabeCubeAura.zip`

The updater selects the versioned archive. It must find the exact expected
asset name derived from the validated release tag. It must never select the
first release asset blindly.

### Package size

The update archive must contain runtime files only. Repository screenshots,
GIFs, source mockups and documentation media remain in GitHub but not in the
installable ZIP.

Targets:

- normal compressed size below 1 MiB;
- updater download limit 5 MiB;
- uncompressed limit 20 MiB;
- at most 512 archive entries.

The public 1.0.0 archive is larger because it predates the lean packaging fix.
Future update archives must use the current runtime-only packaging script.

## Security model

GabeCubeAura runs with Decky's root flag. A failed or malicious update therefore
has a larger impact than an ordinary user application update. The updater must
fail closed.

### Network rules

- use `ssl.create_default_context()`;
- retain certificate and hostname verification;
- reuse the existing verified system CA recovery when Decky's embedded Python
  cannot locate a trusted issuer;
- never use `ssl.SSLContext()` without verification;
- never offer a disable-TLS-verification setting;
- use explicit connect and read timeouts;
- send a stable GabeCubeAura user agent;
- limit metadata responses to 1 MiB;
- accept downloads only from `github.com` and GitHub's documented release asset
  hosts after an HTTPS redirect;
- reject redirects to HTTP or an unrelated host;
- use GitHub ETag and `If-None-Match` support;
- respect GitHub rate-limit and retry headers;
- apply bounded exponential backoff after network failures.

### Release metadata rules

The release is eligible only when all of the following are true:

- `draft` is false;
- `prerelease` is false;
- the tag is an exact stable semantic version such as `v1.1.0`;
- the parsed version is newer than the installed version;
- the archive name is exactly `GabeCubeAura-vVERSION.zip`;
- the archive reports a positive size within the configured limit;
- a SHA-256 digest is present in GitHub metadata or in `SHA256SUMS`;
- the release and asset belong to `Alyenax/GabeCubeAura`.

Version comparison must implement full semantic version rules. It must not use
a simple split-and-parse comparison that treats prerelease identifiers as
ordinary zeroes.

### Download validation

Before any installed file changes:

1. download into `DECKY_PLUGIN_RUNTIME_DIR/updates/downloads`;
2. stream to disk while computing SHA-256;
3. abort when the compressed size exceeds 5 MiB;
4. compare the result with the expected digest;
5. open the ZIP without extracting it;
6. reject absolute paths, parent traversal, duplicate paths and symbolic links;
7. reject entries outside the single `GabeCubeAura/` top-level directory;
8. enforce file-count and uncompressed-size limits;
9. require `main.py`, `plugin.json`, `package.json`, `dist/index.js`, `LICENSE`
   and the `py_modules/signalbar` package;
10. parse the staged `plugin.json` and require the name `GabeCubeAura`;
11. parse the staged `package.json` and require the exact release version;
12. extract to a new staging directory;
13. validate the extracted tree a second time.

A failed check deletes the download and staging directory. The active plugin is
left untouched.

### Publisher signature extension

The release schema should reserve an optional detached signature field from the
first implementation. SHA-256 and GitHub HTTPS protect integrity in the first
version. A later release can require an offline publisher signature without
changing the update status model.

The interface must say **checksum verified** until a publisher signature is
actually implemented. It must not claim that the publisher identity was
cryptographically verified.

## Architecture

The updater remains independent from LED ownership and feature providers.

```text
GitHub Releases
      |
      v
UpdateManager in the Python backend
      |
      +-- persistent update-state.json
      +-- Decky event: update_status_changed
      +-- validated staging directory
      |
      v
Updates page and Decky notification
      |
      v
Explicit user confirmation
      |
      v
Independent update helper
      |
      +-- stop Decky Loader
      +-- atomic directory swap
      +-- start Decky Loader
      +-- wait for health acknowledgement
      +-- keep new version or roll back
```

The Engine, Providers, Arbiter and Renderer must not know how updates work.
Stopping Decky normally invokes `_unload`, which releases LED ownership before
the directory swap.

## Backend components

### `py_modules/signalbar/updates.py`

Owns release discovery and package preparation.

Responsibilities:

- semantic version parsing and comparison;
- GitHub metadata fetch with ETag caching;
- scheduled checks and manual checks;
- update state transitions;
- release-note URL validation;
- archive download and checksum validation;
- safe ZIP inspection and extraction;
- staging directory creation;
- launch of the independent helper;
- cleanup of expired downloads and staging directories.

Suggested classes:

- `UpdateManager`
- `GitHubReleaseSource`
- `ReleaseInfo`
- `UpdateStatus`
- `PackageValidator`

Network and filesystem dependencies should be injectable so that tests never
need GitHub, root privileges or the real plugin directory.

### `py_modules/signalbar/update_helper.py`

A small command-line helper copied into the runtime update directory before it
starts. It must not execute from the plugin directory that it replaces.

Responsibilities:

- acquire a single installation lock;
- verify the staged and active paths again;
- stop `plugin_loader.service`;
- move the active directory to a rollback directory;
- atomically move the staged directory into place;
- start `plugin_loader.service`;
- wait for the expected health token;
- delete the rollback directory after success;
- restore the previous directory and restart Decky after failure;
- write a bounded log and final result into the runtime directory.

It should run as an independent transient systemd unit when available. This is
safer than relying only on a child process of PluginLoader. A tested detached
fallback may be used only if the active Decky service uses a process-only kill
mode.

All process execution uses argument arrays. Do not use `shell=True`.

### `main.py`

`Plugin._main` should:

- create the UpdateManager after settings load;
- process a pending update health token;
- report successful plugin initialization only after Engine startup succeeds;
- start the background update schedule;
- expose update methods to the frontend.

`Plugin._unload` should stop the update schedule before stopping the Engine.

Suggested backend calls:

- `get_update_status()`
- `check_for_updates()`
- `prepare_update(version)`
- `install_prepared_update(version, confirmation_token)`
- `set_update_preferences(auto_check, notifications)`
- `acknowledge_update_notification(version)`
- `dismiss_update_error()`

Downloading and installation are separate calls. The install call must require
a short-lived confirmation token produced only after a complete validated
download.

## Persistent data

### User preferences in `config.json`

Add only:

- `updates_auto_check: true`
- `updates_notifications: true`

These fields are user choices and may be included in configuration export.

### Runtime state in `update-state.json`

Store under `DECKY_PLUGIN_RUNTIME_DIR`, not in exported configuration:

- schema version;
- latest known release version;
- release URL and notes URL;
- last successful check time;
- last check error category;
- cached ETag;
- next eligible automatic check time;
- last notified version;
- prepared version and digest;
- pending health token;
- last installation result;
- rollback result, if any.

Write this file atomically with a temporary file, flush and replace. Do not put
GitHub responses, archive content, access tokens, device identifiers or user
paths in it.

### Runtime directories

Use only subdirectories of `DECKY_PLUGIN_RUNTIME_DIR/updates`:

- `downloads/`
- `staging/`
- `rollback/`
- `helper/`

Keep at most one prepared update and one rollback copy. Cleanup must never
follow links or delete a path that has not first been resolved inside the
expected update root.

## Update state model

The status returned to the frontend should use explicit phases:

- `idle`
- `checking`
- `up_to_date`
- `available`
- `downloading`
- `verifying`
- `ready`
- `installing`
- `restart_pending`
- `updated`
- `rolled_back`
- `error`
- `managed_by_decky`

Suggested status fields:

- installed version;
- latest version;
- phase;
- release notes URL;
- release title;
- published time;
- last checked time;
- progress from 0 to 100 when known;
- human-readable error category;
- whether a prepared update is ready;
- whether a restart is pending;
- whether the last attempt rolled back;
- provider: `github` or `decky`.

Frontend text should be derived from these fields. The backend should not send
arbitrary GitHub release HTML for rendering.

## Background scheduling

The backend performs checks even when the detailed settings page is closed.

Schedule:

1. wait 120 seconds after plugin startup;
2. add up to 60 seconds of random jitter;
3. check only if automatic checks are enabled;
4. after success, schedule the next check 24 hours later;
5. after failure, retry after 1 hour, then 6 hours, then return to 24 hours;
6. reset backoff after a successful response;
7. manual checks ignore the normal interval but share any request already in
   progress.

Only one check or download may run at a time. Suspend, resume and multiple open
panels must not create duplicate workers.

A network error never affects lighting, normal settings or plugin startup.

## Notification behavior

The Python backend emits `update_status_changed` through `decky.emit` after a
new version is persisted. The frontend registers through the public
`@decky/api` event listener.

Because GabeCubeAura already uses `alwaysRender: true`, the listener can remain
available while the quick panel is closed. The frontend must also query status
on initialization so an event emitted before listener registration is not
lost.

Notification rules:

- show only when notifications are enabled;
- show only once per version;
- prefer to wait until no game is active;
- show immediately after a manual check;
- do not play a GabeCubeAura Light Event for its own update notification;
- clicking the notification closes side menus and opens
  `/gabecubeaura/settings/updates`;
- acknowledging the displayed notification persists the version;
- dismissing the toast does not hide the update from the Updates page;
- update errors are shown in the Updates page, not as repeated background
  toasts.

Proposed notification:

Title:

> GabeCubeAura 1.1.0 is available

Body:

> Open Updates to see what changed and install it.

The version is dynamic. No notification claims that installation has started.

## Interface hierarchy

Add **Updates** as a simple left-side settings page immediately before the
separator and **Advanced / debug**.

The quick panel may show one compact row only when an update is available:

- `Update available: VERSION`
- button: `Review update`

The quick panel must not expose a one-press installation button.

### Updates page

#### Software updates

Display:

- Installed version
- Latest stable version
- Current status
- Last checked

Controls:

- `Check for updates`
- `View release notes`
- `Download update`

After verification, replace the last button with:

- `Update and restart Decky`

#### Automatic checks

Toggle:

> Automatically check for updates

Description:

> Checks the official Alyenax/GabeCubeAura GitHub releases once a day. Nothing
> is installed without your confirmation.

Toggle:

> Notify me when an update is available

Description:

> Shows one Decky notification for each new stable version.

#### Installation safety

Static explanation:

> Updates are downloaded from the official GabeCubeAura repository and checked
> before installation. Settings and artwork caches are kept. Decky restarts
> briefly after an update.

Show the last installation or rollback result when present.

Keep a real focusable button at the bottom of the page so Steam controller
navigation can reveal every status line.

### Confirmation modal

Title:

> Update GabeCubeAura?

Body:

> Update from INSTALLED to AVAILABLE? The downloaded package passed its
> checksum and package checks. Your settings and artwork cache will be kept.
> Decky will restart briefly.

Buttons:

- `Cancel`
- `Update and restart Decky`

The modal must show the exact installed and target versions. It must not close
and install merely because the user opened the release notes.

### Status wording

- `Checking for updates...`
- `GabeCubeAura is up to date.`
- `Version VERSION is available.`
- `Downloading VERSION...`
- `Checking the downloaded package...`
- `Ready to install VERSION.`
- `Restarting Decky to finish the update...`
- `Updated successfully to VERSION.`
- `The update could not start. Your current version was kept.`
- `The new version did not start correctly. GabeCubeAura restored VERSION.`
- `Could not check for updates. Try again later.`
- `Updates are managed by Decky.`

## Transaction and rollback

### Preparation

The plugin remains fully operational while metadata and the archive are being
downloaded and checked. The LED Engine is not stopped during preparation.

### Installation

After explicit confirmation:

1. create a random installation token;
2. write the expected target version, digest and health token to runtime state;
3. copy the helper into the persistent runtime directory;
4. launch it independently;
5. return an accepted response to the frontend;
6. let the helper stop Decky Loader normally;
7. confirm the Loader process has stopped;
8. atomically exchange the current and staged plugin directories with Linux
   `renameat2(RENAME_EXCHANGE)`;
9. move the exchanged previous version from staging to rollback storage;
10. set bounded root-owned permissions;
11. start Decky Loader;
12. wait up to 45 seconds for the new backend health acknowledgement.

The health acknowledgement is written only after:

- settings load succeeds;
- the Engine starts;
- required modules import;
- the running plugin version matches the pending target version.

### Success

On success:

- mark the installation complete;
- keep the previous version for one additional successful plugin startup or a
  maximum of seven days;
- clear the pending token;
- remove download and staging leftovers;
- show `Updated successfully to VERSION` on the Updates page.

### Failure

If Decky does not start, GabeCubeAura does not acknowledge health, the version
does not match or the helper encounters an invalid path:

1. stop Decky Loader if it is running;
2. atomically exchange the failed version with the previous version;
3. quarantine the failed directory inside the bounded runtime update root;
4. restart Decky Loader;
5. record `rolled_back` with a short error category;
6. never delete user settings or artwork caches.

The helper should attempt rollback once. It must not enter a restart loop.

## Store compatibility

The update provider must be isolated behind one mode:

- `github`: direct release checks and installation are active;
- `decky`: the page reports `Updates are managed by Decky` and performs no
  GitHub checks or writes.

The initial direct release uses `github`. If GabeCubeAura is accepted into the
Store later, a Store package can select `decky` without removing the page or
changing the rest of the plugin.

No current code should call Decky's private `utilities/install_plugin` route or
its private `DeckyBackend` object. Those interfaces are not part of the public
plugin API and may change without compatibility guarantees.

## Canonical metadata cleanup

Before the bootstrap release:

- set the `package.json` repository, bug and homepage URLs to
  `Alyenax/GabeCubeAura`;
- change the `plugin.json` image URL to the Alyenax repository;
- update README, release documentation and install links;
- update the local publication remote before any authorized push;
- search the complete release tree for obsolete public account URLs;
- keep the author as `Albus Querque`.

This cleanup must be a normal part of the release change. It must not be
described publicly as a correction of an earlier mistake.

## File-level implementation map

New files:

- `py_modules/signalbar/updates.py`
- `py_modules/signalbar/update_helper.py`
- `src/update_notifications.ts`
- `tests/backend/test_updates.py`
- `tests/backend/test_update_helper.py`
- `tests/frontend/update_notifications.test.ts`

Modified files:

- `main.py`: lifecycle, health acknowledgement and backend calls;
- `py_modules/signalbar/settings/store.py`: two preference fields;
- `src/api.ts`: update call wrappers;
- `src/types.ts`: update status types;
- `src/index.tsx`: Updates page, confirmation modal and compact quick row;
- `src/runtime.ts`: background notification listener and Home deferral;
- `src/settings_snapshot.ts`: update preferences only, not runtime state;
- `scripts/package_plugin.py`: fixed-name archive option and lean package
  assertions;
- `tests/backend/test_packaging.py`: updater files and archive limits;
- `README.md`: direct update behavior and recovery URL;
- `CHANGELOG.md`: bootstrap release notes;
- `package.json` and `plugin.json`: canonical Alyenax metadata;
- `THIRD_PARTY_NOTICES.md`: only if a signature verifier is later bundled.

Do not add GitHub Actions.

## Implementation phases

### Phase 0: freeze and baseline

- implement from the released 1.0.0 worktree, not the experimental SignalBar
  checkout;
- record the current Git state and preserve unrelated untracked documents;
- run backend tests, frontend tests, type check, build and package;
- inspect the existing ZIP allowlist and baseline size;
- choose a local prerelease version for physical testing;
- make no GitHub publication.

### Phase 1: release discovery

- add semantic version parsing;
- implement the fixed GitHub source with verified TLS;
- implement ETag, response limits and backoff;
- add runtime state persistence;
- add manual and scheduled checks;
- expose read-only status through `main.py`;
- test every response and failure category with local fixtures.

No installation code is enabled in this phase.

### Phase 2: Updates interface and notification

- add status types and API calls;
- add the Updates page before Advanced / debug;
- add automatic-check and notification preferences;
- register the Decky event listener;
- deduplicate one notification per version;
- defer background notifications while a game is active;
- add the quick-panel review row;
- verify controller navigation and full-page scrolling.

No installation code is enabled in this phase.

### Phase 3: safe package preparation

- stream downloads with size and checksum enforcement;
- validate GitHub and `SHA256SUMS` digests;
- inspect ZIP paths and limits;
- validate staged manifests and version;
- produce a short-lived confirmation token;
- show download and validation progress;
- retain the current installation after every injected failure.

### Phase 4: transactional helper and rollback

- implement the independent helper;
- implement service stop and start without a shell;
- implement directory swap and permissions;
- implement health acknowledgement;
- implement one-attempt rollback;
- persist bounded logs and results;
- prove recovery with isolated fake plugin directories and a fake service
  controller before touching Decky.

### Phase 5: local integration package

- choose a local prerelease version;
- build a lean bootstrap ZIP;
- generate SHA256SUMS and a fixed-name recovery copy;
- install through Decky Developer settings on the official Steam Machine;
- point discovery at a local fixture or unpublished test release;
- execute the physical matrix below;
- keep the release local until rollback has been demonstrated.

### Phase 6: bootstrap release

- update every Alyenax URL and version field consistently;
- write concise release notes explaining the one-time manual bootstrap;
- run the complete release validation;
- publish manually in the author's name only after explicit authorization;
- upload the versioned ZIP, fixed-name ZIP and SHA256SUMS;
- download every asset again and compare checksums;
- verify the fixed latest-download URL;
- do not add GitHub Actions.

## Testability built into the updater

The updater must be designed so that success and recovery can be proved before
the stable release is visible to normal users. Testing must not depend on
editing production settings or typing temporary URLs on the Steam Machine.

### Three separate test environments

#### 1. Isolated update harness

Run the complete updater against temporary directories and a fake service
controller on the development machine. The harness provides deterministic
release metadata, ZIP files, checksums and service outcomes.

It must be able to stop after every transaction step and then restart, proving
that the journal either completes the update or restores the old version. It
must never use the real Decky service or real plugin directory.

The harness produces one machine-readable report containing:

- scenario name;
- starting and target versions;
- downloaded and calculated digests;
- transaction steps reached;
- final active version;
- rollback result;
- settings and artwork cache hashes before and after;
- bounded error category when the scenario fails.

#### 2. Steam Machine update lab

Test packages may expose an **Update lab** subsection in **Advanced / debug**.
This subsection is compiled out of stable packages. It must show a permanent
`TEST BUILD` label and must not accept an arbitrary URL.

Available fixtures are fixed at build time:

- valid update;
- checksum mismatch;
- invalid ZIP layout;
- plugin that fails its health acknowledgement;
- simulated Decky stop failure;
- simulated Decky start failure;
- interrupted transaction recovery.

The page provides only these actions:

- `Run validation only`, which downloads or opens the fixture and performs all
  checks without changing the installed plugin;
- `Rehearse installation`, which uses isolated fake plugin directories;
- `Install test candidate`, enabled only for the approved candidate fixture;
- `Export test report`.

The lab must explain whether a result came from simulation, real package
validation, a real Decky restart or a physical observation. A green simulated
result must never be presented as proof of a real installation.

#### 3. Real release rehearsal

The last rehearsal uses the exact production ZIP intended for the stable
release. Do not rebuild the archive after this test.

Recommended sequence:

1. build the production `v1.1.0` ZIP once;
2. record its SHA256 digest locally;
3. create a GitHub prerelease with the final `v1.1.0` tag and final assets;
4. install a local bootstrap test build such as `1.0.99-test.1` manually;
5. allow only that visibly marked test build to discover the fixed prerelease;
6. update from the test build to the production `v1.1.0` archive;
7. verify restart, health acknowledgement, settings, artwork caches and LED
   recovery on the official Steam Machine;
8. download the release asset again and compare its digest with the tested
   local archive;
9. change the existing release from prerelease to stable without replacing its
   tag or assets;
10. confirm the stable API now reports the same asset name, size and digest.

GitHub permits changing whether an existing release is a prerelease, including
for immutable releases. If release immutability is enabled, the assets and tag
remain protected while this flag is changed. This makes it possible to publish
the exact tested bytes rather than a later rebuild.

No release, prerelease or asset upload should occur without explicit
authorization from the author.

### Deliberate rollback proof

A successful update is not sufficient acceptance evidence. Before stable
publication, perform one real rollback rehearsal on the Steam Machine:

1. export or hash the current settings and artwork cache;
2. install a test fixture whose backend never writes the expected health token;
3. confirm Decky restarts the fixture only once;
4. wait for the 45-second health timeout;
5. confirm the helper restores the previous healthy version;
6. confirm Decky restarts once more and remains stable;
7. confirm the interface reports the rollback and its reason;
8. confirm settings and artwork caches are byte-for-byte unchanged;
9. reboot the Steam Machine and confirm the failed update is not retried.

The deliberately broken fixture must never be the production candidate and
must never be exposed through the stable update feed.

### Visible evidence before publication

The Updates page in test builds should expose a compact diagnostics block:

- installed version;
- candidate version;
- release source category, without secrets or local paths;
- expected and calculated checksum prefixes;
- package validation result;
- last transaction result;
- rollback version when applicable;
- health acknowledgement time;
- last check and next scheduled check;
- notification deduplication state.

The final test report should be saved beside the release artifacts. Publication
is blocked unless it records all of the following as passed:

- automated discovery and validation suite;
- isolated successful installation;
- every isolated injected failure;
- real Steam Machine update using the final archive;
- real Steam Machine rollback using a separate broken fixture;
- reboot after success;
- reboot after rollback;
- unchanged settings and artwork cache hashes;
- final archive checksum equal to the tested checksum.

This report is private release evidence. It is not included in the plugin ZIP
and does not contain usernames, absolute paths, tokens or device identifiers.

## Automated test plan

### Release discovery

- stable release newer than installed;
- same version;
- installed version newer than latest;
- draft release;
- prerelease release;
- malformed or missing tag;
- malformed semantic version;
- missing expected archive;
- wrong repository or host;
- response over size limit;
- timeout, DNS failure, TLS failure and HTTP errors;
- GitHub rate limit with retry time;
- ETag 304 response;
- concurrent manual and scheduled checks collapse into one request;
- failed checks preserve the last known available version.

### Notification

- one toast per version;
- no toast when notifications are disabled;
- no duplicate after frontend remount or Decky restart;
- pending toast survives an event emitted before listener registration;
- background toast waits while a game is active;
- manual check may notify immediately;
- clicking opens the Updates route;
- the plugin does not trigger its own LED notification effect.

### Package validation

- correct versioned archive and digest;
- checksum mismatch;
- archive over compressed limit;
- archive over uncompressed limit;
- too many entries;
- absolute path;
- `../` traversal;
- symbolic link;
- duplicate path;
- multiple top-level directories;
- missing required file;
- wrong plugin name;
- wrong package version;
- corrupt JSON;
- corrupt ZIP;
- cleanup after every failure.

### Transaction helper

- successful swap and health acknowledgement;
- existing rollback data cleanup within scope;
- Decky stop failure before swap;
- active directory rename failure;
- staged directory rename failure;
- Decky start failure;
- health timeout;
- version mismatch after restart;
- successful rollback;
- rollback start failure recorded without a loop;
- second update rejected while one is active;
- interrupted helper resumes or rolls back from its journal;
- settings and artwork caches remain byte-for-byte unchanged.

### Regression

- GabeCubeAura starts with no network;
- lighting remains active during checks and downloads;
- normal unload still restores LED ownership;
- configuration export contains preferences but no runtime updater state;
- no update files enter the installable ZIP except runtime modules;
- no repository media enters the ZIP;
- full backend and frontend suites pass;
- TypeScript checking, production build, ZIP integrity and checksum validation
  pass.

## Official Steam Machine validation

Use an unpublished or local test feed first.

1. Start offline and confirm GabeCubeAura loads normally.
2. Restore the network and run a manual check.
3. Confirm an automatic check occurs after the startup delay.
4. Leave the detailed page closed and confirm the notification still appears.
5. Launch a game before discovery and confirm the notification waits for Home.
6. Open the notification and confirm the Updates page receives focus.
7. Download and verify a valid lean package.
8. Cancel the confirmation and confirm nothing changes.
9. Install the test update and confirm Decky restarts once.
10. Confirm Home, per-game settings, artwork caches and Customization+ choices
    are preserved.
11. Confirm the light bar is released during Loader restart and resumes after
    healthy startup.
12. Simulate a checksum mismatch and confirm the current version remains.
13. Simulate a broken new plugin and confirm automatic rollback.
14. Reboot after a successful update and confirm there is no repeated toast or
    pending update.
15. Check update logs for tokens, paths or other unnecessary private data.
16. Confirm the fixed latest-download URL installs through the available Decky
    Developer flow.

Each result must distinguish local tests, package checks, Decky behavior and
physically observed Steam Machine behavior.

## Release acceptance criteria

The bootstrap release is ready only when:

- all canonical public URLs use `Alyenax/GabeCubeAura`;
- the updater never changes files before complete validation;
- automatic checks never install automatically;
- one notification is shown at most once per version;
- settings and caches survive update and rollback;
- a broken update rolls back without user terminal commands;
- a restart failure does not create a restart loop;
- no TLS bypass or arbitrary update URL exists;
- the runtime archive remains lean;
- all automated checks pass;
- update success and rollback are both demonstrated on the official Steam
  Machine;
- no GitHub publication occurs without explicit authorization.

## References reviewed

- Decky public frontend API and toaster:
  `https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/plugin-loader.tsx`
- Decky internal install and confirmation flow:
  `https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py`
- Decky plugin distribution format:
  `https://github.com/SteamDeckHomebrew/decky-plugin-template#distribution`
- DeckyZone updater structure:
  `https://github.com/DeckFilter/DeckyZone/blob/main/py_modules/plugin_update.py`
- HueSync updater structure:
  `https://github.com/honjow/HueSync/blob/main/py_modules/update.py`

The external updater implementations demonstrate feasibility only. Their TLS,
validation and rollback choices are not the security baseline for GabeCubeAura.

## Decisions still open

No decision blocks implementation planning. Before coding starts, choose only:

1. the bootstrap version number;
2. whether publisher signatures are mandatory in that first bootstrap or
   reserved for the following stable release.

Recommended defaults are a new minor stable version and checksum validation in
the bootstrap, with the signature field reserved but not advertised until it
is fully implemented and tested.
