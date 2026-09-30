# WARNING: Valve LED ownership regression

Do not treat an on-screen preview, an active provider, or an active Witcher lab
as proof that a frame reached the physical Steam Machine light bar.

## Trace found in Git

Two separate changes explain the failure:

1. **Latent hardware-control omission (2026-09-20)**
   - Commit: `f88072dcc8569c98604c8cc743bf7c94ecb769a7`
   - Release: SignalBar `v0.2.1`
   - `ValveLedHardware.write_frame()` wrote only the 17 `multi_intensity`
     values. It did not select the Valve controller's global `manual` effect
     and did not explicitly enable the strip.
   - The exact same hardware file/blob (`1a04d973…`) remained in v1.0.0,
     v1.1.0 and the original 1.2.0-beta1 base. Earlier apparent success could
     therefore depend on Valve already being in a compatible hardware state.

2. **Intentional guardrail with an overly broad side effect (2026-09-29 19:14 +02:00)**
   - Commit: `a0470b22336184c5444b12acd57a58e1b2b32943`
   - Release line: GabeCubeAura `1.2.0-beta1`
   - Repeated native changes began escalating to hard Steam priority.
   - `steam_priority = explicit or guard.hard_priority` was then evaluated by
     the arbiter before previews and other GabeCubeAura outputs.
   - The priority itself is required: native download animations, critical
     thermal/system signals and other explicit Valve states must remain above
     every GabeCubeAura provider.
   - The defect was the lack of distinction between those legitimate native
     signals and harmless startup/brightness churn. In the latter case every
     physical output could remain blocked indefinitely.

The Witcher beta3 work did not introduce the original fault. It inherited the
beta1 ownership path and made the distinction between a simulated frame and a
physical write especially visible.

## Non-regression invariant: do not invert the priority

The fact that Valve sometimes keeps the strip is **not by itself a defect**.
It is the intended safety contract whenever the ownership signal is genuine:

1. an active or renewed Steam download animation remains above every
   GabeCubeAura display, including Screen Sync and the Witcher lab;
2. a native Valve hardware animation remains above every plugin output even if
   the private Steam callback is missing;
3. a nearly full fixed-red native bar is treated as a critical thermal/system
   warning and must never be replaced by a game HUD, preview or permanent
   display;
4. once that explicit/native condition ends, its bounded lease must expire and
   normal GabeCubeAura ownership must become eligible again.

The regression is only case 4 failing: ordinary startup or brightness churn
was able to look like repeated critical/native activity and continually keep
the hard-priority path alive. Tests and diagnostics must therefore distinguish
`Steam download activity`, `Valve <effect> hardware effect`, and
`Valve critical red hardware signal` from the generic
`repeated native LED activity` false-positive path.

## Required correction

Any beta3 package or branch derived from the original beta1 base must retain
all of these fixes together:

- save the current Valve `effect` and `enabled` state;
- select `effect=manual` and `enabled=1` before direct RGB writes;
- include the global Valve controls in the ownership signature;
- allow initial settling across brightness-only churn;
- keep Steam's explicit download lease above every plugin output;
- treat active Valve hardware animations as native priority if the private
  Steam callback is unavailable;
- treat a nearly full fixed red Valve bar as a critical thermal/system signal
  that GabeCubeAura must never replace;
- after GabeCubeAura has written, yield on any full-signature external change;
- restore Valve's previous frame, effect and enabled state only while
  GabeCubeAura still owns the verified hardware signature;
- expose the real physical owner separately from the logical/UI preview.

**Do not fix this regression by bypassing or removing hard Steam priority.**
The correction must narrow false positives while preserving native safety
signals.

The corrected implementation is currently in:

- `py_modules/signalbar/hardware/valve_leds.py`
- `py_modules/signalbar/renderer/renderer.py`
- `py_modules/signalbar/arbiter/guard.py`
- `py_modules/signalbar/backend/engine.py`
- `src/index.tsx`

## Validation boundary

Automated tests, type checking and packaging can verify the policy and sysfs
transactions, but they cannot prove physical ownership on the official Steam
Machine. On target hardware, the Witcher page must report
`Physical bar: GabeCubeAura owns it` while the real strip displays the frame.
On release, Valve's former hardware effect must return.

If the page still reports Valve, capture the displayed suspension reason and
the Advanced/debug ownership guard fields before changing more code.
