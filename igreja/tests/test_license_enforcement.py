import unittest
from unittest.mock import patch

from app.licensing import LicenseConnectionError, LicenseValidationError
from app.ui import license_dialog


SETTINGS = {
    "enforced": True,
    "api_url": "https://example.test/api/v1",
}
LOCAL_STATE = {
    "username": "igreja",
    "status": "active",
    "activation_token": "token",
}


class FakeActivationWindow:
    result = False

    def __init__(self, settings, initial_message=""):
        self.settings = settings
        self.initial_message = initial_message

    def mainloop(self):
        return None


class LicenseEnforcementTests(unittest.TestCase):
    @patch.object(license_dialog, "LicenseActivationWindow", FakeActivationWindow)
    @patch.object(license_dialog, "device_has_bypass", return_value=False)
    @patch.object(license_dialog, "license_is_enforced", return_value=True)
    @patch.object(license_dialog, "load_license_settings", return_value=SETTINGS)
    @patch.object(license_dialog, "load_local_license_state", return_value=LOCAL_STATE)
    @patch.object(license_dialog, "local_license_is_usable_offline", return_value=True)
    @patch.object(license_dialog, "clear_local_license_state")
    @patch.object(license_dialog, "validate_with_server")
    def test_server_rejection_clears_local_state_and_blocks_app(
        self,
        validate,
        clear_state,
        _offline,
        _local_state,
        _settings,
        _enforced,
        _bypass,
    ):
        validate.side_effect = LicenseValidationError("Login ou senha invalidos.")

        self.assertFalse(license_dialog.ensure_application_license())
        clear_state.assert_called_once_with()

    @patch.object(license_dialog, "LicenseActivationWindow", FakeActivationWindow)
    @patch.object(license_dialog, "device_has_bypass", return_value=False)
    @patch.object(license_dialog, "license_is_enforced", return_value=True)
    @patch.object(license_dialog, "load_license_settings", return_value=SETTINGS)
    @patch.object(license_dialog, "load_local_license_state", return_value=LOCAL_STATE)
    @patch.object(license_dialog, "local_license_is_usable_offline", return_value=True)
    @patch.object(license_dialog, "clear_local_license_state")
    @patch.object(license_dialog, "validate_with_server")
    def test_connection_failure_keeps_usable_offline_license(
        self,
        validate,
        clear_state,
        _offline,
        _local_state,
        _settings,
        _enforced,
        _bypass,
    ):
        validate.side_effect = LicenseConnectionError("Sem conexao.")

        self.assertTrue(license_dialog.ensure_application_license())
        clear_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
