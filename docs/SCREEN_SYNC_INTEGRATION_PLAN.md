# Screen Sync integration and ownership plan

Date: 2026-09-29

Status: merged into GabeCubeAura `1.2.0-beta1` for local testing. The complete
local
test, type-check, build and package campaign passed on 2026-09-29. Physical
Steam Machine validation remains mandatory.

## Implementation status

- Phase 1: implemented with frontend heartbeat, capture age, LED write age,
  external-write, Steam-lease and recovery diagnostics.
- Phase 2: implemented with authoritative lifetime events and a conservative
  polling fallback.
- Phase 3: implemented with Customization+ capture fallback and the recording
  marker.
- Phase 4: implemented with startup and download leases, launch settle time,
  one automatic recovery and repeated-write escalation.
- Phase 5: implemented with feature-detected Steam screensaver monitoring and
  an independent renewable activation lease.
- Phase 6: implemented in the Screen Sync and Advanced pages and documented in
  `docs/SCREEN_SYNC.md`.

The physical checklist and completion criteria at the end of this document are
still open until the beta is tested on the official Steam Machine.

This file preserves the design history from the separate local prototype.
It does not describe a second plugin that must be installed with GabeCubeAura.
Current product-facing documentation is in `docs/SCREEN_SYNC.md`.

## Purpose

Screen Sync began as a separate local prototype derived from GabeCubeAura. Its
goal is a Hue-like, real-time experience on the official Steam Machine's
17-pixel light bar. Direct Philips Hue lamp support is outside the current
scope.

The next integration must make Screen Sync easy to enable, modular enough to
serve several contexts and resilient when Steam temporarily changes the light
bar or the visible application state.

The stable GabeCubeAura checkout must remain untouched while this work is being
validated. GabeCubeAura must continue to use the shared provider, arbiter and renderer
pipeline rather than creating another direct LED writer.

## Product goals

The integration should provide all of the following:

- real-time Screen Sync while a game is running, when selected for that game;
- optional Screen Sync only while Steam's screensaver is active;
- a short manual preview that does not change permanent display routing;
- an automatic Customization+ fallback when screen capture cannot be used;
- a persistent red centre LED while Steam Game Recording is active;
- automatic recovery from harmless Steam light-bar takeovers;
- complete yielding to Steam for startup, downloads, overheating and other
  genuine system states;
- no need to move a controller merely to make GabeCubeAura resume;
- no permanent dependence on the detailed settings page being open.

## Design principles

### Separate the display from its activation context

Screen Sync is the visual engine. It should not contain rules about why it is
running. A separate activation controller decides when it is wanted.

The initial activation contexts are:

1. In-game routing
2. Steam screensaver
3. Manual preview

This separation allows the same processing and appearance settings to be used
without changing the user's Home or per-game display choices.

### Keep one LED writer

Every output must continue through Providers, Arbiter and Renderer. Screen
capture, game-session monitoring, screensaver monitoring and recording state
only provide context. They must never write to the Valve LED interface
themselves.

### Keep state in the backend

Once an activation context has been accepted, the Python backend should retain
the desired state and supervise the output. The Decky frontend reports Steam
events and renews short leases, but UI throttling, panel closure or temporary
loss of focus must not immediately drop the selected display.

### Recover without fighting Steam

GabeCubeAura may recover from a single harmless Steam write after a transition. It
must not repeatedly overwrite a real Steam system animation. Repeated native
writes or a known system event create a Steam priority lease during which
GabeCubeAura writes nothing.

## Activation controller

The activation controller should collect independent reasons and resolve them
without modifying display routing.

Suggested internal reasons:

- `game-route`
- `steam-screensaver`
- `manual-preview`
- `recording-blocked`
- `capture-conflict`
- `steam-system-priority`

Each temporary frontend-owned reason should use a renewable lease. If the
frontend disappears, the lease expires safely. Permanent per-game routing
remains stored in the existing settings model.

The controller should expose the effective reason in status output so that the
interface can explain why Screen Sync is active, paused or replaced.

## Steam screensaver integration

### Intended behaviour

The user may enable **Use during Steam screensaver** independently from Home
and in-game routing.

When Steam's screensaver becomes active:

1. the screensaver context requests Screen Sync;
2. the existing Gamescope capture follows the visible slideshow, screenshots or
   other screensaver content;
3. temporary higher-priority signals may interrupt it;
4. when the screensaver closes, the previous Home or in-game display returns;
5. no Home or per-game selection is rewritten.

The same Screen Mapping, Reactivity, Colour Intensity, Brightness, black-bar and
black-threshold settings should be shared with in-game Screen Sync. A separate
public frame-rate setting is unnecessary for the first version.

### Detection adapter

Steam's current screensaver service is private and may change. The frontend
adapter should therefore:

- locate the service by capability rather than a fixed module name;
- require both `GetActiveState` and `ForceScreensaver` before identifying a
  candidate;
- use `GetActiveState` only for normal monitoring;
- feature-detect every call and use bounded timeouts;
- poll conservatively;
- reset and rediscover the adapter after failures;
- report **Detection unavailable** instead of breaking other displays.

`ForceScreensaver` may be useful for explicit testing later, but automatic
operation must never start the screensaver itself.

### Proposed wording

Setting label:

> Use during Steam screensaver

Description:

> Temporarily follows the colours shown by Steam's screensaver. Your Home and
> in-game displays return when it closes.

Possible states:

- Waiting for Steam screensaver
- Following Steam screensaver
- Detection unavailable on this Steam build

## Game session continuity

### Current weakness

The current frontend checks `Router.MainRunningApp` every two seconds. A
temporary AppID value of zero is immediately reported as no game. Steam menus,
idle transitions or frontend throttling can therefore select the Home route and
restore the vanilla Steam preset. Controller activity can make the AppID
visible again, which explains why touching the controller may appear to repair
the light bar.

### Session latch

Game state should use a confidence hierarchy:

1. Steam game-lifetime start and stop notifications are authoritative.
2. A reliable second Steam session query may confirm the state.
3. `Router.MainRunningApp` polling is a discovery and recovery source, not an
   authoritative stop signal.

Once a lifetime start notification confirms an AppID, a single poll returning
zero must not clear it. Menus, overlays, short idle periods and temporary UI
sleep keep the confirmed game session and its display route.

The session is cleared by:

- the matching lifetime stop notification;
- a separate reliable query confirming that the game no longer runs;
- a conservative fallback only when the lifetime service is unavailable.

Fallback expiry must avoid leaving a game profile active indefinitely after a
missed stop event, but a time-based zero poll alone must not defeat a confirmed
session while the normal lifetime service is healthy.

## Output liveness watchdog

The backend should track:

- expected display and provider;
- active activation reason;
- age of the latest capture frame;
- measured capture rate;
- age of the latest successful LED write;
- expected and observed LED signatures;
- active Steam priority lease and its reason;
- latest automatic recovery and its result.

When GabeCubeAura is expected to own the bar and no higher-priority lease exists:

1. a stale capture triggers the existing bounded capture restart;
2. the fallback display appears while capture is recovering;
3. a single external LED change causes a short settle period;
4. GabeCubeAura restores the desired output once after the settle period;
5. further native changes create a Steam priority lease instead of a writer
   loop.

The watchdog must live in the backend render loop. A controller event may
refresh telemetry, but controller input must never be required for recovery.

## Steam Game Recording and capture conflicts

### Recording start

Screen Sync cannot safely share the Gamescope source with Steam Game Recording
until multi-consumer behaviour is proven on the official machine.

The intended recording sequence is:

1. Steam reports recording start.
2. The existing recording-start Light Event plays.
3. Screen capture stops immediately.
4. Customization+ becomes the permanent fallback.
5. LED 9, the centre pixel, remains red for the complete recording.
6. The existing optional black neighbours remain supported.

The fallback uses the user's current Customization+ effect. It does not create
a new preset and does not return to Steam's vanilla Customization preset.

Temporary GabeCubeAura alerts may briefly replace the fallback according to their
normal priority. When they finish, Customization+ and the red recording marker
return.

### Recording stop

The intended stop sequence is:

1. Steam reports recording stop.
2. The recording-stop Light Event plays.
3. The persistent red centre marker disappears.
4. Customization+ remains active while the capture source is released.
5. Screen Sync retries with bounded backoff.
6. Screen Sync returns only if the original activation reason still exists.

### Other capture consumers

When screen sharing or another Gamescope consumer blocks capture, Customization+
also becomes the fallback, but without the recording marker. The interface must
state which conflict caused the fallback.

### Proposed wording

Section label:

> Capture fallback

Description:

> When Screen Sync pauses for Steam Game Recording or another capture consumer,
> Customization+ takes over automatically. The centre LED remains red while
> recording.

## Steam ownership coordinator

The existing Vanilla Guard already watches LED signatures and applies a
cooldown after external writes. The next version should make its intent
explicit by separating two cases.

### Launch handoff

Game launch commonly produces harmless native writes while Steam changes
state. The coordinator should:

1. detect the new running AppID;
2. let Steam's launch writes settle;
3. reclaim the bar once for the selected launch animation or permanent display;
4. treat another immediate native write as intentional Steam activity and
   yield.

This is one delayed recovery, not several blind retries.

### Runtime recovery

While a confirmed game remains active, an isolated transition to the vanilla
preset should follow the same settle and single-recovery rule. This covers
Steam menus, overlays and idle transitions without needing controller input.

### Steam priority lease

Steam retains complete control for:

- machine startup and initial Steam settle;
- downloads and update activity;
- overheating and other hardware safety states;
- maintenance or other persistent native system animations;
- repeated external LED writes that indicate an active native owner.

During this lease, the arbiter must return Valve ownership before considering
GabeCubeAura Light Events, Game Launches or permanent displays. GabeCubeAura must not
restore, refresh or preview a frame until the lease and its stability cooldown
have ended.

Download activity currently uses a short backend lease. The frontend should
renew that lease while the download remains active and send an explicit release
when it ends. A single callback must not allow the lease to expire during a
long download.

Overheating needs a reliable explicit source if Steam exposes one. Until that
source is confirmed, repeated native signature changes remain the conservative
fallback. Any temperature threshold derived from GabeCubeAura's own telemetry must
be researched and validated before it is treated as equivalent to Steam's
hardware warning.

## Target priority order

The target arbitration order is:

1. Steam hard system priority
2. Critical Steam Families or safety countdown
3. Recording start or stop event, then Customization+ with recording marker
4. Other opted-in Light Events and controller alerts
5. Game Launches
6. Normal timer and temporary GabeCubeAura layers
7. Screen Sync, Artwork, Performance, Weather or Customization+
8. Valve ownership when no GabeCubeAura display is selected

Steam hard system priority is absolute. In particular, GabeCubeAura events must not
write over startup, download, update or overheating signals.

## Detailed settings hierarchy

The Screen Sync page should remain simple and contain:

### Activation

- Use during Steam screensaver
- Current in-game route with a link or explanation pointing to Display routing
- Preview for 15 seconds
- Current activation status

### Screen mapping

- Style
- Reactivity
- Colour Intensity
- Brightness
- Ignore cinematic black bars
- Black threshold

### Capture fallback

- explanation of Customization+ fallback;
- recording marker explanation;
- current capture conflict, if any.

### Capture safety

- local processing and no frame storage;
- measured capture source and rate;
- current consumer conflict;
- Refresh capture status button as a genuine final focusable control.

The manual preview must exercise the real capture and rendering path for a
bounded time. It must not modify Home or per-game routing.

## Diagnostics

Advanced and debug status should expose human-readable states such as:

- Waiting for Steam launch writes
- Game session retained during Steam UI transition
- Reclaiming light bar
- GabeCubeAura ownership confirmed
- Steam system activity, yielding
- Steam download activity, yielding
- Screen Sync stalled, restarting
- Recording active, using Customization+
- Capture consumer detected, using Customization+
- Waiting for Steam screensaver
- Following Steam screensaver

The raw diagnostic data should include timestamps or ages for frontend
heartbeat, game-session update, capture frame, LED write, external LED change
and the latest recovery. This allows physical reports to distinguish a route
failure, capture failure and ownership handoff.

## Implementation sequence

### Phase 1: Observability before policy changes

- Record the source and confidence of every AppID transition.
- Record frontend heartbeat age.
- Expose capture-frame age and last successful LED-write age together.
- Expose external signature changes and Steam lease reasons.
- Reproduce idle, overlay and menu transitions on the official machine.

### Phase 2: Game session latch

- Make lifetime notifications authoritative.
- Prevent a polling zero from clearing a confirmed session.
- Add a safe fallback for Steam builds without lifetime notifications.
- Test launch, menu, idle, overlay, Quick Access, exit, crash, suspend and
  resume.

### Phase 3: Recording and generic capture fallback

- Stop Screen Sync on recording start.
- Render Customization+ even when it is serving as a fallback rather than the
  selected route.
- Preserve the red recording marker over that fallback.
- Keep Customization+ while waiting for capture recovery.
- Resume the original Screen Sync context only when it is still valid.

### Phase 4: Ownership coordinator

- Add launch handoff and one delayed recovery.
- Add runtime recovery for isolated menu or idle takeovers.
- Move Steam hard priority ahead of all GabeCubeAura event selection.
- Renew long-running download leases.
- Add conservative repeated-write detection and cooldown.

### Phase 5: Screensaver activation

- Add the feature-detected Steam screensaver monitor.
- Add the renewable activation lease.
- Add the independent setting and status text.
- Confirm exit restores the previous route without changing settings.

### Phase 6: Interface and documentation

- Add the Activation and Capture fallback sections.
- Keep a focusable control at the bottom of the page.
- Update the implementation document and release notes with only verified
  behaviour.
- Do not describe the feature as complete before physical validation.

## Automated test plan

Add deterministic tests for:

- a temporary poll value of zero during a confirmed game;
- an authoritative lifetime stop event;
- fallback behaviour when lifetime notifications are unavailable;
- recording start, persistent marker and recording stop;
- generic capture conflict without recording marker;
- restoration of the original activation context;
- screensaver lease start, renewal, expiry and unavailable service;
- one launch recovery followed by a repeated-write yield;
- Steam hard priority over every GabeCubeAura event and display;
- long download heartbeat and explicit release;
- watchdog recovery after stale capture;
- no recovery when a Steam system lease is active.

The full backend suite, frontend tests, type check, build and package checks must
pass after every policy phase.

## Official Steam Machine validation

Software tests cannot prove the final ownership behaviour. Use the official
machine to verify:

1. Leave a game untouched long enough for controller and UI inactivity.
2. Open and close the Steam overlay and Quick Access Menu repeatedly.
3. Navigate Steam menus while the game remains alive.
4. Confirm the selected GabeCubeAura display returns without controller input.
5. Exit normally and confirm the Home display returns.
6. Crash or force-close a game and confirm the session latch eventually clears.
7. Start and stop Steam Game Recording and inspect the fallback and red marker.
8. Exercise another Gamescope capture consumer.
9. Start a download and confirm Steam retains the bar for the entire activity.
10. Test startup and resume without opening the Decky panel.
11. Exercise any safe, reproducible thermal-warning path available from Valve.
12. Run the Steam screensaver slideshow and confirm Screen Sync follows it and
    restores the prior display on exit.
13. Leave each context active for an extended period and inspect capture rate,
    CPU load, frame-time impact and LED continuity.

Each result must distinguish:

- frontend event receipt;
- backend state and arbitration;
- successful LED write;
- physically visible behaviour on the 17-pixel bar.

## Out of scope for this plan

- direct control of Philips Hue bridges or lamps;
- cloud processing or remote frame transport;
- automatic installation of PipeWire or GStreamer components;
- simultaneous independent LED writers;
- publication as a stable GabeCubeAura release before hardware validation.

## Completion criteria

This plan is complete only when:

- Screen Sync works in games and during the optional Steam screensaver context;
- menus and inactivity no longer cause a lasting vanilla-preset fallback;
- recovery never requires controller input;
- recording and other capture conflicts use the correct Customization+
  fallback;
- the recording marker remains visible for the complete recording;
- Steam retains control for startup, downloads, overheating and other genuine
  system signals;
- no writer loop or visible ownership flicker occurs;
- all automated checks pass;
- the complete transition matrix is confirmed on the official Steam Machine.
