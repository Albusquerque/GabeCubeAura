"""Userspace ownership detection for Valve-first LED coexistence."""

from __future__ import annotations

import time


class VanillaGuard:
    def __init__(self, cooldown_s=5.0, stable_s=2.0, clock=time.monotonic):
        self.cooldown_s = float(cooldown_s)
        self.stable_s = float(stable_s)
        self._clock = clock
        now = self._clock()
        self._last_observed = None
        self._last_stability_observed = None
        self._last_change_at = now
        self._blocked_until = now + self.stable_s
        self._reason = "startup settle"
        self._external_at = 0.0
        self._external_changes = []
        self._hard_until = self._blocked_until
        self._hard_reason = "startup settle"

    @property
    def reason(self):
        return self._reason

    @property
    def last_external_at(self):
        return self._external_at

    @property
    def hard_priority(self):
        return self._clock() < self._hard_until

    @property
    def hard_reason(self):
        return self._hard_reason if self.hard_priority else ""

    def block(self, reason: str, hard=False):
        now = self._clock()
        self._reason = str(reason or "Steam/system activity")
        self._external_at = now
        self._last_change_at = now
        self._blocked_until = max(self._blocked_until, now + self.cooldown_s)
        if hard:
            self._hard_until = max(self._hard_until, now + self.cooldown_s)
            self._hard_reason = self._reason

    def observe(self, signature, expected_signature=None, explicit_active=False, explicit_reason="",
                stability_signature=None):
        now = self._clock()
        if explicit_active:
            self.block(explicit_reason or "Steam/system activity", hard=True)

        changed = self._last_observed is not None and signature != self._last_observed
        self._last_observed = signature
        stable_value = signature if stability_signature is None else stability_signature
        stability_changed = (
            self._last_stability_observed is not None
            and stable_value != self._last_stability_observed
        )
        self._last_stability_observed = stable_value
        if changed:
            external_window = max(8.0, self.cooldown_s * 2.0)
            continuing_external = bool(
                expected_signature is None
                and self._external_changes
                and now - self._external_changes[-1] <= external_window
            )
            if (
                expected_signature is not None and signature != expected_signature
                or continuing_external
            ):
                self._external_changes = [
                    changed_at for changed_at in self._external_changes
                    if now - changed_at <= external_window
                ]
                self._external_changes.append(now)
                repeated = len(self._external_changes) >= 2
                self.block(
                    "repeated native LED activity" if repeated else "external LED change detected",
                    hard=repeated,
                )
        # Before our first write, master-brightness churn is not sufficient to
        # prove another userspace writer owns the RGB targets. After a verified
        # own write or takeover, every part of the full signature matters.
        if (
            expected_signature is not None and changed
            or expected_signature is None and stability_changed
        ):
            self._last_change_at = now

        stable = now - self._last_change_at >= self.stable_s
        if now >= self._blocked_until and stable and not explicit_active:
            self._reason = ""
            return True
        return False

    def note_own_write(self, signature):
        self._last_observed = signature

    def remaining(self):
        return max(0.0, self._blocked_until - self._clock())

    def debug_status(self):
        now = self._clock()
        cooldown_remaining = max(0.0, self._blocked_until - now)
        stable_remaining = max(0.0, self.stable_s - (now - self._last_change_at))
        ready = cooldown_remaining <= 0 and stable_remaining <= 0
        if ready:
            reason = ""
        elif cooldown_remaining > 0:
            reason = self._reason or "cooldown"
        else:
            reason = "waiting for stable LED state"
        return {
            "ready": ready,
            "reason": reason,
            "cooldown_remaining": cooldown_remaining,
            "stable_remaining": stable_remaining,
            "hard_priority": self.hard_priority,
            "hard_reason": self.hard_reason,
        }


class ManualClock:
    """Tiny deterministic clock used by tests."""
    def __init__(self, value=0.0):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)
