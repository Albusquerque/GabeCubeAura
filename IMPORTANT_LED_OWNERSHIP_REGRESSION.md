# WARNING: Valve LED ownership regression

Do not treat an on-screen preview or an active provider as proof that a frame
reached the physical Steam Machine light bar.

## Trace found in Git

Two separate changes explain the former failure:

1. Commit `f88072dcc8569c98604c8cc743bf7c94ecb769a7` wrote the 17
   `multi_intensity` values without selecting the Valve controller's global
   `manual` effect or explicitly enabling the strip.
2. Commit `a0470b22336184c5444b12acd57a58e1b2b32943` correctly added hard
   Steam priority for repeated native activity, but initially classified some
   harmless startup or brightness churn as permanent native ownership.

The priority is intentional. Active Steam downloads, native hardware
animations and critical fixed-red thermal or system warnings must remain above
every GabeCubeAura display. The regression exists only when ordinary churn
keeps that priority alive after the genuine native condition has ended.

## Non-regression requirements

- Save the current Valve `effect` and `enabled` state.
- Select `effect=manual` and `enabled=1` before direct RGB writes.
- Include Valve's global controls in the ownership signature.
- Keep explicit Steam activity and native safety signals above every plugin
  output.
- Yield after any full-signature external change.
- Restore Valve's former frame, effect and enabled state only while
  GabeCubeAura still owns the verified hardware signature.
- Expose the physical owner separately from the logical preview.

Do not fix a false positive by removing hard Steam priority. Narrow the false
positive while keeping the native safety guard.

## Validation boundary

Automated tests, type checking and packaging can verify policy and sysfs
transactions. They cannot prove physical ownership on the official Steam
Machine. On target hardware, confirm that the panel reports GabeCubeAura as
owner while the physical strip displays the selected frame, then confirm that
Valve's former effect returns when the plugin releases ownership.
