import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import updater


class UpdateSecurityTests(unittest.TestCase):
    def test_manifest_without_sha256_is_accepted(self):
        response = Mock()
        response.json.return_value = {
            "version": "9.9.9",
            "url": "https://example.test/Igreja.exe",
        }
        response.raise_for_status.return_value = None
        with patch.object(updater.requests, "get", return_value=response):
            manifest = updater._fetch_manifest_from_url("https://example.test/manifest.json", 1)

        self.assertEqual(manifest["version"], "9.9.9")
        self.assertEqual(manifest["url"], "https://example.test/Igreja.exe")
        self.assertEqual(manifest["digest"], "")

    def test_download_hash_helper_matches_sha256(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "package.whl"
            path.write_bytes(b"conteudo-verificado")
            self.assertEqual(
                updater._sha256_file(path),
                hashlib.sha256(b"conteudo-verificado").hexdigest(),
            )

    def test_update_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "igreja-update-state.json"
            with patch.object(updater, "UPDATE_STATE_PATH", state_path):
                updater.write_update_state("2.1.9", Path(temp_dir) / "Igreja.exe", Path(temp_dir) / "Igreja-2.1.9.exe")
                payload = updater.read_update_state()

                self.assertEqual(payload.get("status"), "pending")
                self.assertEqual(payload.get("target_version"), "2.1.9")
                self.assertEqual(payload.get("target_path"), str((Path(temp_dir) / "Igreja.exe").resolve()))
                self.assertGreater(float(payload.get("created_at", 0)), 0)

                updater.clear_update_state()
                self.assertFalse(state_path.exists())
                self.assertEqual(updater.read_update_state(), {})


if __name__ == "__main__":
    unittest.main()
