import unittest
from datetime import timedelta
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
        self.assertEqual(settings["offline_grace_hours"], 24)

    @patch.object(licensing, "acceptable_device_fingerprints", return_value={"device"})
    @patch.object(licensing, "utcnow")
    def test_legacy_long_offline_period_is_capped_locally(self, now_mock, _fingerprints):
        now = licensing.datetime(2026, 6, 23, tzinfo=licensing.timezone.utc)
        now_mock.return_value = now
        state = {
            "status": "active",
            "device_fingerprint": "device",
            "last_validated_at": licensing.to_iso_datetime(now - timedelta(hours=25)),
            "offline_valid_until": licensing.to_iso_datetime(now + timedelta(days=3650)),
        }

        self.assertFalse(
            licensing.local_license_is_usable_offline(
                state,
                {"offline_grace_hours": 24},
            )
        )


if __name__ == "__main__":
    unittest.main()
