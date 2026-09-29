from __future__ import annotations

import unittest

from signalbar.activation import ScreenSyncActivation
from signalbar.arbiter.guard import ManualClock


class ScreenSyncActivationTests(unittest.TestCase):
    def test_contexts_do_not_change_routing_and_expire(self):
        clock = ManualClock(10)
        activation = ScreenSyncActivation(clock=clock, lease_seconds=5)
        self.assertEqual(activation.resolve(game_route=True, enabled=True), "game-route")
        activation.set_screensaver(True)
        self.assertEqual(
            activation.resolve(game_route=False, screensaver_enabled=True, enabled=True),
            "steam-screensaver",
        )
        activation.preview(15)
        self.assertEqual(
            activation.resolve(game_route=False, screensaver_enabled=True, enabled=True),
            "manual-preview",
        )
        clock.advance(16)
        self.assertEqual(
            activation.resolve(game_route=False, screensaver_enabled=True, enabled=True),
            "",
        )

    def test_screensaver_detection_and_disabled_master_are_reported(self):
        clock = ManualClock(4)
        activation = ScreenSyncActivation(clock=clock)
        activation.set_screensaver(False, "unavailable", "service missing")
        status = activation.status(
            game_route=False, screensaver_enabled=True, enabled=False,
        )
        self.assertFalse(status["requested"])
        self.assertEqual(status["screensaver_detection"], "unavailable")
        self.assertEqual(status["screensaver_detail"], "service missing")


if __name__ == "__main__":
    unittest.main()
