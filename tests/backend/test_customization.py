import tempfile
from pathlib import Path
import unittest

from signalbar.arbiter import Arbiter
from signalbar.models import GameState, ProviderOutput
from signalbar.providers.customization import CUSTOMIZATION_PATTERNS, customization_frame
from signalbar.settings import SettingsStore


BLACK = (0, 0, 0)
PALETTE = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


def belongs_to_palette(pixel):
    if pixel == BLACK:
        return True
    for colour in PALETTE:
        scale = max(pixel) / max(colour)
        if all(abs(channel - round(source * scale)) <= 1
               for channel, source in zip(pixel, colour)):
            return True
    return False


class CustomizationTests(unittest.TestCase):
    def test_all_grouped_patterns_render_bounded_palette_locked_frames(self):
        self.assertEqual(len(CUSTOMIZATION_PATTERNS), 61)
        for pattern in CUSTOMIZATION_PATTERNS:
            with self.subTest(pattern=pattern):
                frames = [customization_frame(pattern, PALETTE, tick * .13, 173, 50, "forward")
                          for tick in range(80)]
                self.assertTrue(any(pixel != BLACK for frame in frames for pixel in frame))
                self.assertTrue(all(len(frame) == 17 for frame in frames))
                self.assertTrue(all(0 <= channel <= 173 for frame in frames
                                    for pixel in frame for channel in pixel))
                self.assertTrue(all(belongs_to_palette(pixel) for frame in frames for pixel in frame))

    def test_steady_supports_true_minimum_and_direction_reverses_frames(self):
        minimum = customization_frame("steady", [[255, 255, 255]], 0, 1, 50, "forward")
        self.assertEqual(minimum, ((1, 1, 1),) * 17)
        forward = customization_frame("scanner", PALETTE, .8, 255, 50, "forward")
        reverse = customization_frame("scanner", PALETTE, .8, 255, 50, "reverse")
        self.assertEqual(reverse, tuple(reversed(forward)))

    def test_speed_changes_animated_customization_phase(self):
        slow = customization_frame("scanner", PALETTE, 1.0, 173, 1, "forward")
        fast = customization_frame("scanner", PALETTE, 1.0, 173, 100, "forward")
        self.assertNotEqual(slow, fast)

    def test_settings_validate_customization_and_routing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(str(Path(directory) / "config.json"))
            values = store.update({
                "home_display": "customization",
                "game_display": "customization",
                "customization_pattern": "not-real",
                "customization_brightness": 999,
                "customization_speed": 0,
                "customization_direction": "sideways",
            })
            self.assertEqual(values["home_display"], "customization")
            self.assertEqual(values["game_display"], "customization")
            self.assertEqual(values["customization_pattern"], "steady")
            self.assertEqual(values["customization_brightness"], 255)
            self.assertEqual(values["customization_speed"], 1)
            self.assertEqual(values["customization_direction"], "forward")
            values = store.update({"customization_brightness": 0})
            self.assertEqual(values["customization_brightness"], 34)

    def test_arbiter_selects_customization_as_a_permanent_base(self):
        arbiter = Arbiter()
        empty = ProviderOutput("none", None, "")
        custom = ProviderOutput("customization:steady", ((1, 2, 3),) * 17, "custom")
        result = arbiter.choose(
            mode="customization", guard_allows=True, game=GameState(),
            performance=empty, artwork=empty, idle=empty,
            customization_base=custom,
        )
        self.assertEqual(result.provider, "customization:steady")


if __name__ == "__main__":
    unittest.main()
