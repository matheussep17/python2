import unittest

from app.frames.baixar_videos import BaixarFrame


class BaixarVideosFormatTests(unittest.TestCase):
    def setUp(self):
        self.frame = BaixarFrame.__new__(BaixarFrame)

    def test_youtube_clients_are_not_pinned(self):
        self.assertEqual(self.frame._build_youtube_extractor_args(), {})

    def test_hd_quality_attempts_include_adaptive_video_and_audio(self):
        attempts = self.frame._build_best_quality_attempts("1080p")

        self.assertIn("height=1080", attempts[0])
        self.assertIn("+bestaudio", attempts[0])
        self.assertTrue(all("height=1080" in attempt for attempt in attempts))

    def test_pytubefix_can_select_adaptive_hd_stream(self):
        class Stream:
            includes_video_track = True
            is_progressive = False
            fps = 30
            abr = None

            def __init__(self, resolution):
                self.resolution = resolution

        hd = Stream("1080p")
        selected = self.frame._pick_pytubefix_video_stream(
            [Stream("360p"), hd, Stream("720p")],
            "1080p",
        )

        self.assertIs(selected, hd)

    def test_cut_input_seeks_after_opening_stream(self):
        args = self.frame._ffmpeg_url_input_args(
            {"url": "https://cdn.example/video"},
            {},
            12,
            8,
        )

        self.assertLess(args.index("-i"), args.index("-ss"))
        self.assertLess(args.index("-ss"), args.index("-t"))

    def test_cut_audio_and_video_are_timestamp_normalized(self):
        source = BaixarFrame._download_cut_with_ffmpeg.__code__.co_consts
        constants = {value for value in source if isinstance(value, str)}

        self.assertIn("setpts=PTS-STARTPTS", constants)
        self.assertIn("aresample=async=1:first_pts=0,asetpts=PTS-STARTPTS", constants)


if __name__ == "__main__":
    unittest.main()
