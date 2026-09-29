"""Screen Sync activation reasons, independent from display routing."""

from __future__ import annotations

import threading
import time


class ScreenSyncActivation:
    """Retain bounded frontend contexts and resolve one effective reason."""

    def __init__(self, clock=time.monotonic, lease_seconds=5.0):
        self._clock = clock
        self._lease_seconds = max(2.0, float(lease_seconds))
        self._lock = threading.RLock()
        self._screensaver_until = 0.0
        self._screensaver_detection = "waiting"
        self._screensaver_detail = ""
        self._preview_until = 0.0

    def set_screensaver(self, active, detection="available", detail=""):
        detection = str(detection or "available")[:32]
        if detection not in {"waiting", "available", "unavailable", "error"}:
            detection = "error"
        with self._lock:
            self._screensaver_detection = detection
            self._screensaver_detail = str(detail or "")[:180]
            self._screensaver_until = (
                self._clock() + self._lease_seconds if bool(active) else 0.0
            )

    def preview(self, seconds=15.0):
        with self._lock:
            self._preview_until = self._clock() + max(3.0, min(30.0, float(seconds)))
        return True

    def stop_preview(self):
        with self._lock:
            self._preview_until = 0.0

    def resolve(self, *, game_route=False, screensaver_enabled=False, enabled=True):
        if not enabled:
            return ""
        now = self._clock()
        with self._lock:
            if now < self._preview_until:
                return "manual-preview"
            if screensaver_enabled and now < self._screensaver_until:
                return "steam-screensaver"
        return "game-route" if game_route else ""

    def status(self, *, game_route=False, screensaver_enabled=False, enabled=True):
        now = self._clock()
        with self._lock:
            preview_remaining = max(0.0, self._preview_until - now)
            screensaver_remaining = max(0.0, self._screensaver_until - now)
            detection = self._screensaver_detection
            detail = self._screensaver_detail
        reason = self.resolve(
            game_route=game_route,
            screensaver_enabled=screensaver_enabled,
            enabled=enabled,
        )
        return {
            "requested": bool(reason),
            "reason": reason,
            "preview_remaining_s": preview_remaining,
            "screensaver_active": screensaver_remaining > 0,
            "screensaver_lease_remaining_s": screensaver_remaining,
            "screensaver_detection": detection,
            "screensaver_detail": detail,
        }
