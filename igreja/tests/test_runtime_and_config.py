import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import licensing, utils


class RuntimeAndConfigTests(unittest.TestCase):
    """Cobertura de runtime e configuração do aplicativo."""

    def test_load_app_config_merges_bundled_and_user_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bundled = temp_path / "bundled.json"
            user = temp_path / "user.json"
            bundled.write_text('{"output_folder": "C:/tmp/bundle", "ffmpeg_download_url": "https://bundle.test/ffmpeg.zip"}', encoding="utf-8")
            user.write_text('{"output_folder": "C:/tmp/user", "license_api_url": "https://example.test/api/v1"}', encoding="utf-8")

            with patch.object(utils, "bundled_app_config_path", return_value=bundled), patch.object(utils, "app_config_path", return_value=user):
                config = utils.load_app_config()

            self.assertEqual(config["output_folder"], "C:/tmp/user")
            self.assertEqual(config["ffmpeg_download_url"], "https://bundle.test/ffmpeg.zip")
            self.assertEqual(config["license_api_url"], "https://example.test/api/v1")

    def test_save_output_folder_normalizes_and_persists_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_base = Path(temp_dir)
            target_path = temp_base / "videos" / "saida"
            config_path = temp_base / "config.json"

            with patch.object(utils, "app_config_path", return_value=config_path):
                with patch.object(utils, "load_app_config", return_value={}):
                    saved = utils.save_output_folder(str(target_path))

            self.assertEqual(saved, str(target_path.resolve()))
            self.assertTrue(config_path.exists())
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["output_folder"], str(target_path.resolve()))

    def test_resolve_tool_path_prefers_local_app_binary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ffmpeg_dir = temp_path / "ffmpeg"
            ffmpeg_dir.mkdir()
            ffmpeg_bin = ffmpeg_dir / "ffmpeg.exe"
            ffmpeg_bin.write_bytes(b"tool")

            with patch.object(utils, "_runtime_bundle_dir", return_value=temp_path), patch.object(utils, "app_base_dir", return_value=temp_path):
                found = utils.resolve_tool_path("ffmpeg")

            self.assertEqual(found, str(ffmpeg_bin))

    def test_get_available_js_runtimes_returns_detected_tools(self):
        with patch.object(utils, "resolve_tool_path", side_effect=lambda name: {
            "node": "C:/Program Files/node.exe",
            "deno": "C:/Program Files/deno.exe",
        }.get(name)):
            runtimes = utils.get_available_js_runtimes()

        self.assertEqual(runtimes["node"]["path"], "C:/Program Files/node.exe")
        self.assertEqual(runtimes["deno"]["path"], "C:/Program Files/deno.exe")

    def test_device_has_bypass_matches_configured_machine_name(self):
        with patch.object(licensing, "acceptable_device_fingerprints", return_value={"abc"}), patch.object(licensing, "machine_name", return_value="DESKTOP-OK"):
            settings = {"bypass_machine_names": ["desktop-ok"], "bypass_device_fingerprints": []}
            self.assertTrue(licensing.device_has_bypass(settings))

    def test_local_license_is_usable_offline_requires_valid_active_state(self):
        future = licensing.utcnow() + licensing.timedelta(days=2)
        valid_state = {
            "device_fingerprint": "abc",
            "status": "active",
            "expires_at": licensing.to_iso_datetime(licensing.utcnow() + licensing.timedelta(days=30)),
            "offline_valid_until": licensing.to_iso_datetime(future),
        }

        with patch.object(licensing, "acceptable_device_fingerprints", return_value={"abc"}):
            self.assertTrue(licensing.local_license_is_usable_offline(valid_state))

        expired_state = dict(valid_state)
        expired_state["offline_valid_until"] = licensing.to_iso_datetime(licensing.utcnow() - licensing.timedelta(hours=1))
        with patch.object(licensing, "acceptable_device_fingerprints", return_value={"abc"}):
            self.assertFalse(licensing.local_license_is_usable_offline(expired_state))


if __name__ == "__main__":
    unittest.main()
