import unittest
from unittest.mock import patch

from app import licensing


class LicenseSettingsTests(unittest.TestCase):
    @patch.object(
        licensing,
        "load_app_config",
        return_value={
            "license_enforced": True,
            "license_api_url": "https://python2-production-e3ee.up.railway.app/api/v1",
            "license_bypass_machine_names": ["DESKTOP-ANTIGO"],
            "license_bypass_device_fingerprints": ["fingerprint-antigo"],
        },
    )
    def test_legacy_railway_config_is_migrated_and_bypasses_are_ignored(self, _config):
        settings = licensing.load_license_settings()

        self.assertEqual(settings["api_url"], licensing.CURRENT_LICENSE_API_URL)
        self.assertEqual(settings["bypass_machine_names"], [])
        self.assertEqual(settings["bypass_device_fingerprints"], [])

    @patch.object(licensing, "load_app_config", return_value={})
    def test_missing_config_uses_secure_cloudflare_defaults(self, _config):
        settings = licensing.load_license_settings()

        self.assertTrue(settings["enforced"])
        self.assertTrue(settings["send_device_name"])
        self.assertEqual(settings["api_url"], licensing.CURRENT_LICENSE_API_URL)


if __name__ == "__main__":
    unittest.main()
