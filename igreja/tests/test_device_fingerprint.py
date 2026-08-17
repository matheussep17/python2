import unittest
from unittest.mock import patch

from app import licensing


class DeviceFingerprintTests(unittest.TestCase):
    def test_windows_fingerprint_does_not_depend_on_random_mac(self):
        patches = [
            patch.object(licensing.sys, "platform", "win32"),
            patch.object(licensing.platform, "system", return_value="Windows"),
            patch.object(licensing.platform, "machine", return_value="AMD64"),
            patch.object(licensing, "_read_windows_machine_guid", return_value="stable-guid"),
            patch.object(licensing, "_read_windows_bios_uuid", return_value="stable-bios"),
        ]
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

        with patch.object(licensing.uuid, "getnode", return_value=111):
            first = licensing.device_fingerprint()
        with patch.object(licensing.uuid, "getnode", return_value=999):
            second = licensing.device_fingerprint()

        self.assertEqual(first, second)

    def test_validation_sends_saved_fingerprint_for_v2_migration(self):
        state = {
            "username": "igreja",
            "activation_token": "token",
            "device_fingerprint": "a" * 64,
        }
        settings = {
            "api_url": "https://example.test/api/v1",
            "timeout_seconds": 3,
            "send_device_name": False,
        }
        response = {
            "username": "igreja",
            "status": "active",
            "device_fingerprint": "b" * 64,
        }

        with patch.object(licensing, "device_fingerprint", return_value="b" * 64), \
                patch.object(licensing, "acceptable_device_fingerprints", return_value={"b" * 64}), \
                patch.object(licensing, "_request_json", return_value=response) as request, \
                patch.object(licensing, "save_local_license_state"):
            licensing.validate_with_server(settings, state)

        payload = request.call_args.args[1]
        self.assertIn("a" * 64, payload["legacy_device_fingerprints"])


if __name__ == "__main__":
    unittest.main()
