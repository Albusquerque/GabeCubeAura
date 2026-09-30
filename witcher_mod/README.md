# GabeCubeAura telemetry mod for The Witcher 3

This optional game-side mod sends Geralt's current vitality, stamina, toxicity,
adrenaline, combat state and performed Signs to GabeCubeAura through Witcher 3's
own direct state file, with the script log retained as a diagnostic fallback.
It does not open a network socket and does not change gameplay.

## Install on SteamOS

1. Close The Witcher 3.
2. Extract this archive into the game directory so this file exists:
   `mods/modGabeCubeAuraTelemetry/content/scripts/local/gca_telemetry.ws`.
3. Add `-net -debugscripts` to the game's Steam launch options. `-net` enables
   the script debug channel used by `LogChannel`; `-debugscripts` alone is not
   the supported complete launch configuration for this bridge.
4. In the AppID 292030 Proton prefix, edit
   `drive_c/users/steamuser/Documents/The Witcher 3/dx12user.settings` for the
   DX12/Remastered renderer, or `user.settings` for DX11. Under the existing
   `[Scripts]` section, set `DebugScriptsForceFlush=true`. If `[Scripts]` does
   not exist, add it at the end of the file.
5. Start the game, load a save, open GabeCubeAura's
   **The Witcher 3 · experimental** page and enable the light output.

The page should change from **manual fallback** to **live WitcherScript
telemetry**. The primary state file is
`compatdata/292030/pfx/drive_c/users/steamuser/Documents/The Witcher 3/GabeCubeAuraTelemetry.ini`.
The diagnostic fallback accepts namespaced `GCA1` records from
`scriptlog.txt` or `scriptslog.txt` in the same directory; the plural spelling
was observed in a returned Steam Machine diagnostic.

If the game reports a script compilation error, remove the single
`mods/modGabeCubeAuraTelemetry` directory to roll back. Annotation support
requires a current Complete Edition build with the REDkit scripting update.
