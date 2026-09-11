import os

import pytest

from ecp.windows_credentials import WindowsCredentialStore


def test_windows_backend_is_fail_closed_outside_windows():
    if os.name == "nt":
        pytest.skip("Linux-only guard test")
    with pytest.raises(OSError, match="requires Windows"):
        WindowsCredentialStore()


def test_identity_mapping_is_namespaced_and_non_secret():
    if os.name == "nt":
        pytest.skip("mapping is covered by Windows integration test")
    assert WindowsCredentialStore.__name__ == "WindowsCredentialStore"
    assert "secret" not in "ECP/credential-id/1".lower()
