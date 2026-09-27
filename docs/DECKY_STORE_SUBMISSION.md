# Decky Store submission

Prepared on 2026-09-27 by Albus Querque for GabeCubeAura 1.0.0.

## Public listing

- Name: GabeCubeAura
- Author: Albus Querque
- Repository: `https://github.com/Albusquerque/GabeCubeAura`
- Version: `1.0.0`
- License: BSD 3-Clause
- Description: Artwork, custom effects, weather and live status lighting for the Steam Machine light bar.
- Image: `https://raw.githubusercontent.com/Albusquerque/GabeCubeAura/main/docs/media/gabecubeaura-product-hero.png`

## Proposed pull request summary

GabeCubeAura gives the official Steam Machine's 17-pixel light bar permanent
and temporary displays through Decky Loader. It can sample local Steam or
SteamGridDB artwork, play per-game launch animations, show CPU and GPU activity,
display controller battery levels and weather, run custom multi-colour effects,
and signal playtime or Steam events.

The plugin uses the standard React frontend and Python backend. It contains no
custom binary. Artwork analysis stays local. Weather is optional and uses
Open-Meteo without an account, API key or automatic location detection.

The `root` flag is required only for the official Steam Machine's root-owned
`valve-leds` sysfs files. GabeCubeAura does not modify SteamOS's read-only
filesystem. Hardware writes are serialized, rate-limited and guarded so the
plugin yields when Steam or another process owns the light bar.

The plugin is specific to Steam Machine hardware. Its interface and previews
remain safe when `valve-leds` is unavailable, but actual lighting requires the
17-pixel Steam Machine light bar.

## Backend answers

- Custom backend other than Python: No
- Third-party FOSS tool with non-static dependencies: No
- Custom binary with statically linked dependencies: No
- Required testing channel: SteamOS Stable or Beta

## Validation still required before opening the pull request

1. Ask the Decky maintainers whether a Steam Machine-specific plugin is eligible
   for the official Store and which hardware they want used for final testing.
2. Have another person test the submitted build on SteamOS Stable or Beta and
   leave the report on the Store pull request.
3. Confirm that the tester can open every settings page and run local previews
   without errors when `valve-leds` is absent.
4. If requested by the maintainers, obtain a separate test on an official Steam
   Machine to confirm physical output and restoration.
5. Complete every personal declaration in Decky's current Plugin addition
   template before submission.

Community testing of two other plugin pull requests is optional, but completing
it can improve review priority.

## Database pull request procedure

Fork `SteamDeckHomebrew/decky-plugin-database`, create a submission branch and
add this repository as a submodule at the exact reviewed commit:

```bash
git clone https://github.com/Albusquerque/decky-plugin-database.git
cd decky-plugin-database
git remote add upstream https://github.com/SteamDeckHomebrew/decky-plugin-database.git
git fetch upstream
git switch -c add/gabecubeaura upstream/main
git submodule add https://github.com/Albusquerque/GabeCubeAura.git plugins/GabeCubeAura
git -C plugins/GabeCubeAura checkout <reviewed-commit>
git add .gitmodules plugins/GabeCubeAura
git commit -m "Add GabeCubeAura"
git push -u origin add/gabecubeaura
```

Open the pull request with Decky's `Plugin addition` template. Paste the summary
above, answer every checklist item personally, remove the Preview testing line,
and leave the third-party testing box unchecked until a tester posts a report.

No workflow file is required in the GabeCubeAura repository.
