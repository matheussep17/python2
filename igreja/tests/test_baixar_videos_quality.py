import unittest

from app.frames.baixar_videos import BaixarFrame


class BaixarVideosQualityTests(unittest.TestCase):
    def test_requested_quality_is_exact(self):
        frame = BaixarFrame.__new__(BaixarFrame)

        attempts = frame._build_best_quality_attempts("144p")

        self.assertTrue(attempts)
        self.assertTrue(all("height=144" in attempt for attempt in attempts))
        self.assertFalse(any("height<=" in attempt for attempt in attempts))

    def test_holyrics_quality_is_exact(self):
        frame = BaixarFrame.__new__(BaixarFrame)

        attempts = frame._build_yt_holyrics_relaxed_attempts("1080p")

        self.assertTrue(attempts)
        self.assertTrue(all("height=1080" in attempt for attempt in attempts))
        self.assertFalse(any("height<=" in attempt for attempt in attempts))


if __name__ == "__main__":
    unittest.main()
