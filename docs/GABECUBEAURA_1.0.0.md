# GabeCubeAura v1.0.0

## Status

GabeCubeAura replaces the temporary CubeGlow name and the former SignalBar
product identity. Version 1.0.0 is the first public GabeCubeAura release.

The Python namespace, persistent `signalbar_*` keys, and the local StripMine
handoff identity remain unchanged for compatibility. The Decky name, package,
archive root, UI, logs, configuration export, and current documentation use
GabeCubeAura. On first launch, GabeCubeAura first looks for the immediately
preceding CubeGlow test configuration, then for SignalBar, and copies the
configuration and artwork caches when its own settings directory is still empty.

## Product hierarchy

Detailed settings use Decky's documented `SidebarNavigation`, restoring the
simple left-hand tabs used before the rebrand. Each tab owns one page instead of
rendering every settings section in one long column:

1. Display routing
2. Customization+
3. Artwork
4. Performance
5. Game launches
6. Playtime
7. Light events
8. Controllers
9. Weather
10. Compatibility
11. Advanced / debug

Home and In-game routing remain independent. **GabeCubeAura Off** means GabeCubeAura
does not draw a permanent display in that context; Steam keeps the bar between
temporary layers. It does not disable Game Launches, alerts, or countdowns.
The master output toggle is the only control that disables every GabeCubeAura
output.

## Game Launches

Game Launches remains a temporary layer and can therefore run for a configured
duration over Weather on Home, Performance in game, or any other permanent
display. Its page is ordered as follows:

1. enable switch and current AppID;
2. Hero, Header, or Capsule artwork source;
3. artwork palette or a palette saved for the current game;
4. two or three colours;
5. pattern and 3–45 second timer;
6. the first Preview control;
7. live 17-LED frame and remaining time, refreshed every 100 ms while this page
   is open;
8. focusable artwork image;
9. a second Preview control below the image, with no duplicate LED bar beneath
   it, giving Steam gamepad navigation a natural final target for scrolling.

Both the two-colour and three-colour custom palettes are retained per AppID, so
switching palette size does not discard either one. Profiles are included in
GabeCubeAura configuration exports and restored by imports.

Every Game Launch pattern is palette-locked. Black and dimmer values of the
selected hues are allowed for fades, but overlapping glows no longer blend two
source colours into a new hue. Legato switches between palette members rather
than interpolating them.

## Customization+

Customization+ is a permanent display available independently on Home and in
game. Temporary layers keep their existing priority and the chosen permanent
display returns afterward.

Controls:

- one, two, or three precise colours;
- opaque colour picker without a misleading Alpha control, exact hexadecimal
  entry, and RGB 0–255 sliders;
- raw output brightness from 34 to 255 in increments of one; values below 34
  are raised to 34 because they switch the physical bar off;
- speed from 1 to 100 for every animated pattern (hidden for Steady because a
  static colour has no animation phase);
- forward or reverse direction;
- an eight-second preview and live logical 17-LED strip.

The library contains **61 selectable effects**. Their existing names and source
prefixes are unchanged, but the dropdown now groups them by visible dynamism:

- Calm & ambient;
- Flowing;
- Energetic.

The catalogue still contains:

- Steady: one precise static GabeCubeAura colour;
- Game Launches: all ten launch patterns;
- Light Events: all notification, achievement, and screenshot variants;
- Controllers: all connection, gauge, low-battery, charging, and dual-controller
  variants, rendered with representative sample state;
- Weather: every existing weather condition and variant.

Customization+ reuses the real existing event, controller, and weather frame
generators as loops, then maps their light/dark choreography to the selected
palette and brightness. This keeps the proven motion while preventing the
settings page from duplicating dozens of implementations.

### Native Steam effects

Steam currently names four customization choices **Patrol, Breathe, Rainbow,
and Solid**. They are intentionally not duplicated in Customization+. Valve's
public support documentation confirms that Steam owns and customizes the bar,
but does not specify the exact frame timing for those presets or expose a safe
public preset-selection API. A merely similar GabeCubeAura animation would be
confusing. Users keep the authentic Steam effects by selecting **GabeCubeAura Off**
and configuring the bar in Steam.

## Verification boundary

Automated checks cover settings migration and persistence, per-AppID palettes,
every pattern, palette purity, arbitration, frontend types, bundle and ZIP
contents. The 34 floor records the observed hardware cutoff and automated tests
verify that it is enforced. Version 1.0.0 was also checked on the target Steam
Machine for diffuser appearance, native-write interruption, controller focus
and final tab navigation.

## Public concept site

The public GabeCubeAura Concept Lab presents Customization+,
Game Launches, the complete priority model, and the existing non-game display
families. Unrelated embedded games and their assets are excluded.

The canonical page is
`https://albusquerque.github.io/gabecubeaura-concept/`. The former SignalBar
Concept Lab address redirects to it.
