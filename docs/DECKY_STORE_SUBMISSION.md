# Decky Store submission

Prepared on 2026-09-27 by Alyenax for GabeCubeAura 1.0.0.

## Public listing

- Name: GabeCubeAura
- Author: Alyenax
- Repository: `https://github.com/Alyenax/GabeCubeAura`
- Version: `1.0.0`
- License: BSD 3-Clause
- Description: Artwork, custom effects, weather and live status lighting for the Steam Machine light bar.
- Image: `https://raw.githubusercontent.com/Alyenax/GabeCubeAura/main/docs/media/gabecubeaura-product-hero.png`

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

## Maintainer question

Send this question in the official Decky Discord before opening the pull request:

> Hi, I am preparing GabeCubeAura for the Decky Plugin Store. It is designed for
> the official Steam Machine's 17-pixel `valve-leds` light bar. The React and
> Python interface remains safe when that hardware is absent, but physical light
> output requires a Steam Machine. Is a hardware-specific plugin like this
> eligible for the Store, and which hardware should be used for the required
> third-party test?

## Remaining validation and review steps

1. Obtain the maintainers' answer about Steam Machine eligibility and testing.
2. Complete every personal declaration in Decky's current Plugin addition
   template before submission.
3. Open the Store pull request with the third-party testing box left unchecked.
4. Have another person install the submitted build from the Testing Store on
   SteamOS Stable or Beta and leave a report on the pull request.
5. Confirm that the tester can open every settings page and run local previews
   without errors when `valve-leds` is absent.
6. If requested by the maintainers, obtain a separate test on an official Steam
   Machine to confirm physical output and restoration.

Community testing of two other plugin pull requests is optional, but completing
it can improve review priority.

## Database pull request procedure

Fork `SteamDeckHomebrew/decky-plugin-database`, create a submission branch and
add this repository as a submodule at the exact reviewed commit:

```bash
git clone https://github.com/Alyenax/decky-plugin-database.git
cd decky-plugin-database
git remote add upstream https://github.com/SteamDeckHomebrew/decky-plugin-database.git
git fetch upstream
git switch -c add/gabecubeaura upstream/main
git submodule add https://github.com/Alyenax/GabeCubeAura.git plugins/GabeCubeAura
git -C plugins/GabeCubeAura checkout <reviewed-commit>
git add .gitmodules plugins/GabeCubeAura
git commit -m "Add GabeCubeAura"
git push -u origin add/gabecubeaura
```

Open the pull request with Decky's `Plugin addition` template. Paste the summary
above, answer every checklist item personally, remove the Preview testing line,
and leave the third-party testing box unchecked until a tester posts a report.

No workflow file is required in the GabeCubeAura repository.
