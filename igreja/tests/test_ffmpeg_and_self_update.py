import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from app import updater, utils


class FfmpegAndSelfUpdateTests(unittest.TestCase):
    """Cobertura do FFmpeg e do fluxo de auto-update no Windows."""

    def test_download_and_install_ffmpeg_requires_windows(self):
        with patch.object(utils.sys, "platform", "linux", create=True):
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                utils.download_and_install_ffmpeg("https://example.test/ffmpeg.zip")

    def test_download_and_install_ffmpeg_requires_configured_download_url(self):
        with patch.object(utils.sys, "platform", "win32", create=True):
            with patch.object(utils, "get_ffmpeg_download_url", return_value=""):
                with self.assertRaisesRegex(RuntimeError, "ffmpeg_download_url"):
                    utils.download_and_install_ffmpeg("")

    def test_download_and_install_ffmpeg_raises_when_archive_is_missing_required_binaries(self):
        with patch.object(utils.sys, "platform", "win32", create=True):
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "fake-package.zip"
                with zipfile.ZipFile(zip_path, "w") as archive:
                    archive.writestr("readme.txt", "arquivo sem ffmpeg")

                response = Mock()
                response.raise_for_status.return_value = None
                response.headers = {"content-length": str(zip_path.stat().st_size)}
                response.iter_content.return_value = [zip_path.read_bytes()]

                with patch.object(utils.tempfile, "mkdtemp", return_value=temp_dir), patch.object(utils.requests, "get", return_value=response):
                    with self.assertRaisesRegex(RuntimeError, "ffmpeg.exe.*ffprobe.exe"):
                        utils.download_and_install_ffmpeg("https://example.test/ffmpeg.zip")

    def test_schedule_windows_self_replace_writes_pending_state_and_starts_powershell(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            current_exe = temp_path / "Igreja.exe"
            current_exe.write_bytes(b"current-app")
            downloaded_exe = temp_path / "Igreja-2.1.0.exe"
            downloaded_exe.write_bytes(b"new-app")
            state_path = temp_path / "igreja-update-state.json"

            with patch.object(updater, "can_self_update", return_value=True), \
                patch.object(updater, "UPDATE_STATE_PATH", state_path), \
                patch.object(updater.tempfile, "gettempdir", return_value=str(temp_path)), \
                patch.object(updater.sys, "executable", str(current_exe), create=True), \
                patch.object(updater.subprocess, "Popen") as popen:
                updater.schedule_windows_self_replace(downloaded_exe, "2.1.0")

            self.assertTrue(state_path.exists())
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pending")
            self.assertEqual(payload["target_version"], "2.1.0")
            self.assertEqual(payload["target_path"], str(current_exe.resolve()))
            self.assertEqual(payload["package_path"], str(downloaded_exe.resolve()))
            popen.assert_called_once()
            self.assertIn("powershell.exe", popen.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
