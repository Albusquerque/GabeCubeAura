# WARNING: Witcher Remastered telemetry compatibility audit

Date: 2026-09-30

This note records the current physical result and the evidence required before
changing the experimental Witcher bridge. It is not proof of a root cause and
must not be used to weaken Valve LED ownership or the normal GabeCubeAura
arbiter.

## Confirmed on the Steam Machine

- Steam AppID `292030` is detected and the Witcher laboratory can physically
  drive the 17-LED bar.
- Manual laboratory controls therefore reach the backend, arbiter, renderer and
  physical hardware.
- The installed mod is enabled in the game's interface.
- Live HUD values still do not reach the laboratory; it remains on manual
  fallback.
- Screen Sync recovered after recreating Gaming Mode, but the failure was later
  reproduced after a Witcher/game-session transition as a GStreamer PAUSED
  preroll error. Beta3 now force-stops that process at every AppID transition;
  target-hardware validation of the restart remains required.

## Confirmed Remastered compatibility boundary

CD Projekt RED's support page for the newly released cross-platform mod system
states that existing mods containing script files are not immediately
compatible with the update and must be updated using REDkit:

https://support.cdprojektred.com/fr/witcher-3/pc/gameplay/issue/3001/prise-en-charge-des-mods-multiplateforme-guide-pratique

The current GabeCubeAura installer copies a raw WitcherScript file to:

`mods/modGabeCubeAuraTelemetry/content/scripts/local/gca_telemetry.ws`

The Remastered modding guide is more explicit: legacy text assets changed from
UTF-16 to UTF-8, so existing script mods require an update. The current
GabeCubeAura source is already UTF-8/ASCII and uses script annotations. The
guide recommends cooking scripts with REDkit into `precompiled.rsblob`, but it
also states that loose `.ws` scripts remain supported on PC. A precompiled blob
is strictly required on consoles, not for every PC loose-script mod. Metadata
and lower-case archive paths apply to packages submitted to the integrated Mod
Hub:

https://mod.io/g/the-witcher-3/r/what-does-the-remaster-mean-for-modding

GabeCubeAura currently installs only the loose `.ws` file and does not ship a
`precompiled.rsblob`. That is not, by itself, proof that the PC bridge is
invalid. It does mean the installed checksum proves only that GabeCubeAura
copied its expected source; it does not prove that Remastered compiled or ran
it. Runtime compatibility remains unconfirmed until the game emits a fresh
`GCA1|` record or provides a concrete compilation error.

## Static source audit

The bridge was compared both with the public CDPR Modding Documentation script
tree at commit `5310d1980ad60ae4b901a73613a54ee71514ce49` and with the Remastered
4.04b-to-5.00 script changelog commit
`e026f253c8790ebcfe545188eb0ae77978dc1178` linked by the Remastered guide:

- `W3PlayerWitcher.OnPlayerTickTimer(deltaTime : float)` exists as an event;
  REDkit wrappers intentionally declare wrapped events as `function` methods.
- `W3PlayerWitcher.OnSignCastPerformed(signType : ESignType,
  isAlternate : bool)` exists with the expected parameters.
- `GetStat`, `GetStatMax`, `NoTrailZeros`, `SignEnumToString`, and the vitality,
  stamina, toxicity and focus enum values used by the bridge all exist.
- Remastered 5.00 exposes
  `CInGameConfigWrapper.WriteIniFile(iniFileName, key, newValue)`. The repaired
  bridge uses it to overwrite a bounded `GabeCubeAuraTelemetry.ini` state
  channel in Documents while retaining `LogChannel` as a fallback.
- The annotation forms `@addField`, `@addMethod` and `@wrapMethod` match the
  REDkit script-override documentation.
- In the 5.00 `playerWitcher.ws` diff, both wrapped methods retain those same
  signatures; the nearby changes shown for them are formatting or unrelated
  body changes.

This finds no obvious encoding, spelling or changed-signature mistake in the
raw source. It still does not replace compilation and runtime evidence from the
actual game build.

## Automatic ownership rule

The plugin must not interpret `Installed and verified` as live compatibility.
That status means only that the target file matches the packaged checksum.
Automatic Lab session management starts when AppID `292030` launches with the
checksum-verified file and stops when the game exits. Physical Witcher output
is allowed only after a fresh namespaced `GCA1|` record in that session. A
silent or broken bridge therefore leaves Valve/the selected display in control
instead of showing automatic simulated HUD values.

Even after runtime verification, Steam hard priority remains above the lab.
Native download animations, explicit Steam activity and fixed red critical
thermal/system warnings must temporarily retain the physical bar. When the
lease ends, the verified Witcher session may resume; the safety guard itself
must never be bypassed.

## Optional device evidence before a correction

1. Use **Repair telemetry mod** and verify that the displayed target contains
   lower-case `/mods/`. The former installer used upper-case `/Mods/`; on
   SteamOS that can produce a checksum-valid file the game never compiles.
2. Keep the complete `-net -debugscripts` pair in the AppID 292030 Steam
   launch options for the independent `LogChannel` diagnostic fallback.
3. Start the game from a fully stopped state and record any **Script Compilation
   Errors** screen.
4. Load a save, change vitality or stamina, and cast a Sign.
5. Capture the Witcher Lab rows for `Source`, transport and `Telemetry read error`.
6. Use **Export Witcher + Screen Sync diagnostics** and preserve
   `/home/deck/Documents/GabeCubeAura-Witcher3-diagnostics.json` unchanged.
7. If needed after closing the game, locate both possible log names:

   ```bash
   find /home/deck/.local/share/Steam/steamapps /run/media/deck \
     -type f \( -iname 'scriptlog.txt' -o -iname 'scriptslog.txt' \) \
     -path '*292030*' \
     -printf '%TY-%Tm-%Td %TH:%TM:%TS  %s bytes  %p\n' 2>/dev/null
   ```

8. Search the newest log for `GCA1|` or attach that log unchanged.

## Decision boundary

- Fresh direct state file: the game-side bridge compiled and ran even if the
  optional script log is absent.
- No direct state file and no script log: inspect the exported JSON, exact
  lower-case install path and compilation evidence before changing the reader.
- Script log without `GCA1|`: capture any compilation message and validate the
  bridge with current REDkit; do not infer the cause from the missing
  `precompiled.rsblob` alone.
- Fresh `GCA1|` records present while the panel stays on manual fallback: the
  game-side bridge works and GabeCubeAura's discovery/tailing path must be
  corrected.

Do not delete the Proton prefix, game installation, saves, or generated script
cache as part of this audit. Preserve the failing log and exact compilation
message first.
