# GabeCubeAura 1.2.0-beta1 validation plan

This plan separates package checks from real Steam Machine behaviour. A passing
archive test is not proof of capture quality or physical LED output.

## Before installation

1. Keep the v1.1.0 ZIP available for manual rollback.
2. Export the current GabeCubeAura configuration from Advanced settings.
3. Disable any second build that can write to the same light bar.
4. Record the beta ZIP SHA256 and compare it with `SHA256SUMS`.
5. Install the ZIP through Decky Developer settings without extracting it.

## Smoke test

1. Confirm the plugin opens and reports version `1.2.0-beta1`.
2. Check that Home, in-game and per-game display choices survived the upgrade.
3. Preview Artwork, Customization+, Weather and one Light Event.
4. Open Screen Sync and confirm the page can scroll below Capture safety.
5. Run the 15-second preview and record the phase, source and measured frame
   rate shown in the panel.

Stop here and reinstall v1.1.0 if the panel cannot open, settings disappeared,
Decky restarts repeatedly or the light bar remains under the wrong owner.

## Screen Sync campaign

Test Panorama and Ambient in one colourful game, one dark game, one game with
letterboxing and one high-motion game. For each game, keep Screen Sync running
for 30 minutes and note frame rate, stale-frame errors and performance impact.

Then verify:

- open and close the Steam overlay and Quick Access Menu;
- leave the controller untouched in a menu, then return to play;
- switch games, exit to Home, suspend and resume;
- start and stop the Steam screensaver with its option enabled;
- launch Steam Game Recording and confirm immediate Customization+ fallback;
- confirm the red centre LED stays present for the full recording;
- stop recording and confirm Screen Sync returns without controller input;
- start a Steam download and confirm Steam keeps priority until it settles.

## Weather campaign

Preview all 8 new night scenes. Confirm that the logical preview uses only the
deep-blue night field, neutral cloud grey and stepped moon whites. Compare the
preview with the physical bar at low and high Weather brightness. Check that
existing day, rain, snow and storm selections are unchanged.

## Coexistence campaign

Trigger a Game Launch, notification, screenshot, achievement, low-controller
alert and playtime countdown over Screen Sync. Confirm that each temporary
layer restores the expected display. If StripMine is installed, test every
ownership choice and confirm both plugins acknowledge handoffs.

## Steam Families campaign

1. On the restricted account, select GabeCubeAura Off for Home and in-game,
   leave the current game on Use in-game default, and disable Game launches.
2. Confirm Steam's account colour is visible before starting a game.
3. Launch a game with a playtime allowance and confirm Advanced settings moves
   from Steam Families callback waiting to received.
4. Open and close the Steam overlay and Quick Access Menu several times. The
   countdown must keep its progress and must not restart at a full bar.
5. Suspend and resume during the same allowance. Confirm the callback is
   received again without restarting Decky or moving a controller.
6. Change between the unrestricted and restricted Steam accounts, then repeat
   the launch. Confirm the restricted account still starts the countdown and
   Steam's own account colour returns when no countdown is active.
7. Repeat once with a fixed full-bar scale and once with Timer duration. A real
   game exit and relaunch may start full with Timer duration; a temporary menu
   visit must never do so.

## Pass criteria

- no crash, repeated Decky restart or frozen capture process;
- no lost settings or artwork cache;
- no second capture consumer is disrupted;
- Steam system activity keeps priority;
- GabeCubeAura resumes without controller movement when it should;
- every preview and live frame remains exactly 17 LEDs;
- rollback to v1.1.0 remains possible with the saved ZIP and configuration.

Keep a short result table with the game, display mode, capture rate, recording
result, resume result, physical colour notes and any diagnostics copied from
Advanced settings.
