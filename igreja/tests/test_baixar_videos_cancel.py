import subprocess
import unittest
from unittest.mock import patch

from app.frames.baixar_videos import BaixarFrame


class FakeDownloadCancelled(Exception):
    pass


class FakeYtDlp:
    class utils:
        DownloadCancelled = FakeDownloadCancelled


class FakeProcess:
    def __init__(self):
        self.terminated = False
        self.killed = False
        self.returncode = None

    def wait(self, timeout=None):
        if self.terminated or self.killed:
            self.returncode = 0
            return 0
        raise subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=timeout)

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def poll(self):
        if self.terminated or self.killed:
            return 0
        return None


class BaixarVideosCancelTests(unittest.TestCase):
    def _make_frame(self):
        frame = BaixarFrame.__new__(BaixarFrame)
        frame.cancel_requested = True
        frame._yt_dlp = FakeYtDlp()
        frame._queue_event = lambda *args, **kwargs: None
        frame._get_ffmpeg_executable = lambda: "C:\\fake\\ffmpeg.exe"
        return frame

    @patch("app.frames.baixar_videos.os.path.exists", return_value=True)
    @patch("app.frames.baixar_videos.subprocess.Popen")
    def test_run_ffmpeg_honors_cancel_request(self, popen, _exists):
        process = FakeProcess()
        popen.return_value = process

        frame = self._make_frame()

        with self.assertRaises(FakeDownloadCancelled):
            frame._run_ffmpeg(["-i", "input", "output.mp4"], "falha")

        self.assertTrue(process.terminated)

    @patch.object(BaixarFrame, "_validate_cut_output", autospec=True)
    @patch.object(BaixarFrame, "_select_requested_format", autospec=True)
    @patch.object(BaixarFrame, "_extract_cut_source_info", autospec=True)
    @patch.object(BaixarFrame, "_iter_cut_extract_attempts", autospec=True)
    @patch.object(BaixarFrame, "_run_ffmpeg", autospec=True)
    def test_download_cut_with_ffmpeg_propagates_cancel(
        self,
        run_ffmpeg,
        iter_attempts,
        extract_info,
        select_format,
        _validate,
    ):
        frame = self._make_frame()
        frame.cancel_requested = False
        frame._is_music_mode = lambda _fmt: False
        frame._is_holyrics_profile = lambda: False
        frame._ffmpeg_url_input_args = lambda *args, **kwargs: ["-i", "https://example.test/media"]

        iter_attempts.return_value = iter([{"dummy": True}])
        extract_info.return_value = {"formats": []}
        select_format.side_effect = [
            {"url": "https://example.test/video"},
            {"url": "https://example.test/audio"},
        ]
        run_ffmpeg.side_effect = FakeDownloadCancelled()

        with self.assertRaises(FakeDownloadCancelled):
            frame._download_cut_with_ffmpeg(
                "https://example.test/watch?v=1",
                "Video",
                "1080p",
                "outtmpl",
                "D:\\temp\\output.mkv",
                (0, 10),
            )


if __name__ == "__main__":
    unittest.main()
