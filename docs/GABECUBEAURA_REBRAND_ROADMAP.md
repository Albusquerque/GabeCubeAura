# GabeCubeAura rebrand publication record

Completed on 2026-09-27 by Albus Querque for the GabeCubeAura 1.0.0 public
release.

## Result

- The primary repository is `Albusquerque/GabeCubeAura` and retains the full
  SignalBar history.
- The former `Albusquerque/SignalBar` repository URL redirects to the renamed
  repository.
- The product is a final `1.0.0` release, not a beta.
- GitHub Actions is not used for the release. The ZIP and checksum are built,
  verified and published manually.
- Current public copy and release materials contain no automated-authoring
  attribution.

## Compatibility retained intentionally

The public product name is GabeCubeAura. These older identifiers remain only
where changing them would break existing installations or historical records:

- Python import namespace `signalbar`;
- saved `signalbar_*` keys and the configuration schema;
- legacy settings probes for CubeGlow and SignalBar;
- the `SignalBar` and `signalbar` StripMine ownership protocol;
- historical release notes, tags, links and changelog entries;
- stable legacy media filenames already referenced by earlier releases.

GabeCubeAura copies an existing CubeGlow test configuration first, then a
SignalBar configuration and artwork cache. It does not delete the source.

## Acceptance and verification

- The project owner confirmed the Steam Machine checks, including the left-hand
  settings tabs, Game Launch scrolling, both Preview controls, brightness 34,
  Customization+ speed, representative pattern families, two- and three-colour
  launch palettes, timers, interruption handling, migration and StripMine
  handoff.
- Backend suite: 132 passed.
- Frontend suite: 38 passed and 1 environment-specific test skipped.
- TypeScript check, Rollup build, package tests and ZIP integrity passed.
- The installable archive has one `GabeCubeAura/` root and includes the final
  documentation and README media.
- Final archive: `GabeCubeAura-v1.0.0.zip`.
- SHA-256: `67840338fb33f3f43b3e177c677874b4771e073e34d8c94d217869053526baa3`.

## Public sites

### Concept Lab

- Canonical repository: `Albusquerque/gabecubeaura-concept`.
- Canonical page: `https://albusquerque.github.io/gabecubeaura-concept/`.
- Published commit: `41e7490`.
- Legacy repository: `Albusquerque/signalbar-concept`.
- Legacy page: `https://albusquerque.github.io/signalbar-concept/`.
- Legacy redirect commit: `4eb58f8`.
- Browser audit passed over HTTP and direct file opening, including every major
  simulator tab, per-game and per-source palettes, all sampled datasets,
  desktop layout and 390 px layout.

### Controller battery annex

- Canonical repository: `Albusquerque/gabecubeaura-controller-battery`.
- Canonical page:
  `https://albusquerque.github.io/gabecubeaura-controller-battery/`.
- Published commit: `99a7fb4`.
- Legacy repository: `Albusquerque/signalbar-controller-battery`.
- Legacy page:
  `https://albusquerque.github.io/signalbar-controller-battery/`.
- Legacy redirect commit: `62cbd5c`.
- Browser audit passed for five controller scenes, three variants per scene,
  17 logical LEDs, keyboard controls, desktop layout and 390 px layout.

### Light-variant annex

The local `signalbar-light-variants-site` artifact had no identified public
repository or live link and overlaps the complete Concept Lab. It is superseded
by the Concept Lab and remains unpublished. The broad parent Xplorarr checkout
was not modified.

## Release media

The final Concept Lab regenerated these README animations with
`npm run media:release`:

- `customization-plus.gif`;
- `game-launch-palettes.gif`;
- `game-launch-patterns.gif`.

The captures remain explicitly described as browser simulations. Hardware
validation is recorded separately as a physical observation by the project
owner.

## Publication policy

- All commits and releases use the identity Albus Querque
  `<guyalbuquerque@gmx.fr>`.
- No GitHub Actions workflow is present in the primary repository.
- GitHub Actions is disabled for the primary repository and the four Pages
  repositories.
- The release is created manually with the ZIP, `SHA256SUMS` and the maintained
  release notes.
- The published ZIP is downloaded again and checked against `SHA256SUMS` after
  release creation.

## Rollback points

- Primary repository history before the rebrand: commit `6a66fce`.
- Concept Lab before the rebrand: commit `2e60b97`.
- Controller annex before the rebrand: commit `bb53e01`.
- The legacy redirect repositories are separate and can be removed without
  rewriting the canonical histories.
