"""
Unit tests for LinkedIn OAuth 2.0 flow, state validation, and token exchange.
Zero real credentials used; external network calls are mocked.
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.oauth import (
    AUTH_URL,
    LinkedInOAuth,
    OAuthError,
    StateMismatchError,
    TokenExchangeError,
)


def test_build_auth_url_structure():
    """Verify generated OAuth authorization URL includes all required parameters."""
    client_id = "test_client_id_123"
    redirect_uri = "http://localhost:8501"
    scopes = ["openid", "profile", "w_member_social"]

    url, state = LinkedInOAuth.build_auth_url(client_id, redirect_uri, scopes)

    assert AUTH_URL in url
    assert f"client_id={client_id}" in url
    assert "response_type=code" in url
    assert f"state={state}" in url
    assert "openid+profile+w_member_social" in url or "openid%20profile%20w_member_social" in url
    assert len(state) >= 32


def test_build_auth_url_missing_params():
    """Verify validation errors when client_id or redirect_uri are missing."""
    with pytest.raises(OAuthError, match="Client ID is missing"):
        LinkedInOAuth.build_auth_url("", "http://localhost:8501", ["w_member_social"])

    with pytest.raises(OAuthError, match="Redirect URI is missing"):
        LinkedInOAuth.build_auth_url("test_id", "", ["w_member_social"])


def test_state_verification_constant_time():
    """Test cryptographic constant-time state validation."""
    valid_state = LinkedInOAuth.generate_state()

    assert LinkedInOAuth.verify_state(valid_state, valid_state) is True
    assert LinkedInOAuth.verify_state(valid_state, "tampered_state_token") is False
    assert LinkedInOAuth.verify_state("", valid_state) is False
    assert LinkedInOAuth.verify_state(valid_state, None) is False
    assert LinkedInOAuth.verify_state(None, None) is False


@patch("requests.post")
def test_exchange_code_success(mock_post):
    """Test successful token exchange with LinkedIn OAuth endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "AQ_mock_token_abc123",
        "expires_in": 5184000,
        "scope": "openid,profile,w_member_social",
    }
    mock_post.return_value = mock_resp

    result = LinkedInOAuth.exchange_code_for_token(
        code="auth_code_xyz",
        client_id="client_id_123",
        client_secret="client_secret_456",
        redirect_uri="http://localhost:8501",
    )

    assert result["access_token"] == "AQ_mock_token_abc123"
    assert result["expires_in"] == 5184000
    mock_post.assert_called_once()


@patch("requests.post")
def test_exchange_code_error_handling(mock_post):
    """Test error handling when LinkedIn returns 400 or network fails."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "error": "invalid_grant",
        "error_description": "Authorization code expired",
    }
    mock_post.return_value = mock_resp

    with pytest.raises(TokenExchangeError, match="Authorization code expired"):
        LinkedInOAuth.exchange_code_for_token(
            code="expired_code",
            client_id="client_id_123",
            client_secret="client_secret_456",
            redirect_uri="http://localhost:8501",
        )

    # Test network timeout
    mock_post.side_effect = requests.RequestException("Connection timed out")
    with pytest.raises(TokenExchangeError, match="Network error communicating with LinkedIn"):
        LinkedInOAuth.exchange_code_for_token(
            code="code_123",
            client_id="client_id_123",
            client_secret="client_secret_456",
            redirect_uri="http://localhost:8501",
        )

