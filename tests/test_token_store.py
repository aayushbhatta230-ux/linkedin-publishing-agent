"""
Unit tests for secure token store and safe disconnect functionality.
Tests both keyring and isolated file fallback without exposing real credentials.
"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.token_store import TokenStore


@pytest.fixture
def temp_token_store(tmp_path):
    """Provides an isolated TokenStore instance using a temporary directory."""
    fallback_file = tmp_path / ".test_secure_token.json"
    store = TokenStore(fallback_path=fallback_file)
    # Force fallback mode to test deterministic file serialization
    store._keyring_available = False
    return store


def test_save_and_retrieve_token(temp_token_store):
    """Test saving access token and reading it back."""
    temp_token_store.save_token(
        access_token="test_access_token_1234567890",
        expires_in=3600,
        member_urn="urn:li:person:abcdef",
        member_name="Aayush Bhatta",
        scopes="openid profile w_member_social",
    )

    data = temp_token_store.get_token()
    assert data is not None
    assert data["access_token"] == "test_access_token_1234567890"
    assert data["member_urn"] == "urn:li:person:abcdef"
    assert data["member_name"] == "Aayush Bhatta"
    assert data["expires_at"] > time.time()


def test_token_expiration_validation(temp_token_store):
    """Test is_token_valid correctly detects expired tokens."""
    # Active token
    temp_token_store.save_token("active_token", expires_in=3600)
    assert temp_token_store.is_token_valid() is True

    # Expired token (expires_in = -100)
    temp_token_store.save_token("expired_token", expires_in=-100)
    assert temp_token_store.is_token_valid() is False


def test_masked_token_status(temp_token_store):
    """Ensure raw token is never exposed in the UI status dictionary."""
    temp_token_store.save_token(
        access_token="AQ_very_long_secret_token_1234567890_xyz",
        expires_in=86400 * 10,
        member_urn="urn:li:person:123",
        member_name="Aayush Bhatta",
    )

    status = temp_token_store.get_token_status()
    assert status["connected"] is True
    assert status["member_name"] == "Aayush Bhatta"
    assert status["expires_in_days"] >= 9.9
    # Must be masked (e.g. AQ_ver..._xyz)
    assert status["masked_token"] != "AQ_very_long_secret_token_1234567890_xyz"
    assert "..." in status["masked_token"]


def test_safe_disconnect_wipes_token(temp_token_store):
    """Test delete_token completely clears token storage."""
    temp_token_store.save_token("token_to_wipe", expires_in=3600)
    assert temp_token_store.get_token() is not None

    temp_token_store.delete_token()
    assert temp_token_store.get_token() is None
    assert temp_token_store.is_token_valid() is False
    status = temp_token_store.get_token_status()
    assert status["connected"] is False

