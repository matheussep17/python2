import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from app import licensing, updater, utils
from app.licensing import LicenseConnectionError, LicenseValidationError


class UpdaterAndLicensingTests(unittest.TestCase):
    """Cobertura de update e validação de licenças em cenários reais."""

    @patch.object(updater.requests, "head")
    @patch.object(updater.requests, "get")
    def test_github_redirect_fallback_builds_manifest_with_digest(self, get_mock, head_mock):
        latest_response = Mock()
        latest_response.raise_for_status.return_value = None
        latest_response.url = "https://github.com/org/repo/releases/tag/v2.1.0"
        latest_response.headers = {}

        asset_head = Mock()
        asset_head.raise_for_status.return_value = None
        asset_head.headers = {"content-length": "1200"}

        digest_response = Mock()
        digest_response.ok = True
        digest_response.text = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789  Igreja.exe\n"

        get_mock.side_effect = [latest_response, digest_response]
        head_mock.return_value = asset_head

        manifest = updater._fetch_manifest_from_github_latest_redirect("org/repo", "Igreja.exe", 10)

        self.assertEqual(manifest["version"], "2.1.0")
        self.assertEqual(manifest["url"], "https://github.com/org/repo/releases/download/v2.1.0/Igreja.exe")
        self.assertEqual(manifest["digest"], "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789")
        self.assertEqual(manifest["size"], 1200)

    @patch.object(updater.requests, "get")
    def test_download_update_package_raises_when_file_is_incomplete(self, get_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.headers = {"content-length": "10"}
        response.iter_content.return_value = [b"12345"]

        get_mock.return_value = response

        with self.assertRaises(updater.UpdateError):
            updater.download_update_package({"version": "1.2.3", "url": "https://example.test/Igreja.exe", "size": 10, "digest": ""})

    @patch.object(licensing.requests, "post")
    def test_request_json_raises_license_validation_error_on_server_rejection(self, post_mock):
        response = Mock()
        response.ok = False
        response.json.return_value = {"detail": "Login ou senha invalidos."}
        post_mock.return_value = response

        with self.assertRaises(LicenseValidationError) as exc:
            licensing._request_json("https://example.test/api/v1/validate", {"username": "user"}, 5)

        self.assertIn("Login ou senha invalidos.", str(exc.exception))

    @patch.object(licensing.requests, "post")
    def test_request_json_raises_license_connection_error_on_network_failure(self, post_mock):
        post_mock.side_effect = requests.ConnectionError("sem internet")

        with self.assertRaises(LicenseConnectionError) as exc:
            licensing._request_json("https://example.test/api/v1/activate", {"username": "user"}, 5)

        self.assertIn("sem internet", str(exc.exception))

    def test_runtime_requirement_message_mentions_ffmpeg_path_when_missing(self):
        message = utils.runtime_requirement_message(["ffmpeg", "ffprobe"], {"ffmpeg_bin": "C:/apps/ffmpeg/bin"})

        self.assertIn("FFmpeg localizado em", message)
        self.assertIn("C:/apps/ffmpeg/bin", message)

    @patch.object(utils, "configure_runtime_environment", return_value={"ffmpeg": None, "ffprobe": None, "ffmpeg_bin": None})
    @patch.object(utils, "is_tool_usable", return_value=False)
    @patch.object(utils, "_has_module", return_value=False)
    def test_missing_runtime_requirements_flags_ffmpeg_and_python_dependencies(self, _module_mock, _tool_mock, _runtime_mock):
        missing, runtime = utils.missing_runtime_requirements()

        self.assertIn("ffmpeg", missing)
        self.assertIn("ffprobe", missing)
        self.assertIn("ttkbootstrap", missing)
        self.assertEqual(runtime["ffmpeg_bin"], None)


if __name__ == "__main__":
    unittest.main()
