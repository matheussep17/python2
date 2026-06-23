import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import updater
from app.yt_dlp_runtime import _sha256_file


class UpdateSecurityTests(unittest.TestCase):
    def test_manifest_without_sha256_is_rejected(self):
        response = Mock()
        response.json.return_value = {
            "version": "9.9.9",
            "url": "https://example.test/Igreja.exe",
        }
        response.raise_for_status.return_value = None
        with patch.object(updater.requests, "get", return_value=response):
            with self.assertRaises(updater.UpdateError):
                updater._fetch_manifest_from_url("https://example.test/manifest.json", 1)

    def test_download_hash_helper_matches_sha256(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "package.whl"
            path.write_bytes(b"conteudo-verificado")
            self.assertEqual(
                _sha256_file(path),
                hashlib.sha256(b"conteudo-verificado").hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
