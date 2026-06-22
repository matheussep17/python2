import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import licensing


class LicenseStorageMigrationTests(TestCase):
    def test_loads_legacy_license_state_from_frozen_exe_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            primary_dir = temp_root / "primary"
            legacy_dir = temp_root / "legacy"
            legacy_dir.mkdir(parents=True, exist_ok=True)

            legacy_state = {
                "username": "igreja",
                "status": "active",
                "device_fingerprint": "legacy-fingerprint-1234567890",
                "offline_valid_until": "2099-01-01T00:00:00+00:00",
            }
            legacy_path = legacy_dir / licensing.LICENSE_STATE_FILE
            legacy_path.write_text(json.dumps(legacy_state), encoding="utf-8")

            fake_executable = legacy_dir / "Igreja.exe"

            with patch.dict(
                "os.environ",
                {
                    "IGREJA_LICENSE_STORAGE_DIR": str(primary_dir),
                    "PROGRAMDATA": str(temp_root / "ProgramData"),
                },
                clear=False,
            ), \
                patch.object(licensing.sys, "platform", "win32"), \
                patch.object(licensing.sys, "frozen", True, create=True), \
                patch.object(licensing.sys, "executable", str(fake_executable), create=True):
                loaded = licensing.load_local_license_state()

            self.assertEqual(loaded["username"], legacy_state["username"])
            self.assertTrue((primary_dir / licensing.LICENSE_STATE_FILE).exists())
            self.assertEqual(
                json.loads((primary_dir / licensing.LICENSE_STATE_FILE).read_text(encoding="utf-8")),
                legacy_state,
            )
