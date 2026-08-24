import unittest

from app.frames.baixar_videos import BaixarFrame


class BaixarVideosQualityTests(unittest.TestCase):
    def test_requested_quality_is_an_upper_limit(self):
        frame = BaixarFrame.__new__(BaixarFrame)

        attempts = frame._build_best_quality_attempts("144p")

        self.assertTrue(attempts)
        self.assertTrue(all("height<=144" in attempt for attempt in attempts))
        self.assertFalse(any("height=144" in attempt for attempt in attempts))


if __name__ == "__main__":
    unittest.main()
