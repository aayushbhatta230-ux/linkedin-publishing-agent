"""
LinkedIn OAuth 2.0 Authorization Flow Manager.
Handles URL generation, CSRF state verification, and authorization code exchange.
Adheres to official LinkedIn OAuth 2.0 specifications with zero credentials in logs or source.
"""
import logging
import secrets
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("oauth")

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


class OAuthError(Exception):
    """Base exception for OAuth operations."""
    pass


class StateMismatchError(OAuthError):
    """Raised when the OAuth state parameter fails verification (potential CSRF)."""
    pass


class TokenExchangeError(OAuthError):
    """Raised when token exchange with LinkedIn fails."""
    pass


class LinkedInOAuth:
    """Encapsulates LinkedIn OAuth 2.0 client operations."""

    @staticmethod
    def generate_state() -> str:
        """Generates a cryptographically strong random token for state parameter."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def build_auth_url(
        client_id: str,
        redirect_uri: str,
        scopes: List[str],
        state: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Builds the authorization URL for user consent.
        Returns:
            Tuple of (full_auth_url, state_token)
        """
        if not client_id:
            raise OAuthError("LinkedIn Client ID is missing. Please configure it in .env or settings.")
        if not redirect_uri:
            raise OAuthError("LinkedIn Redirect URI is missing.")

        state_token = state or LinkedInOAuth.generate_state()
        scope_str = " ".join(scopes)

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state_token,
            "scope": scope_str,
        }
        encoded_query = urllib.parse.urlencode(params)
        return f"{AUTH_URL}?{encoded_query}", state_token

    @staticmethod
    def verify_state(received_state: Optional[str], expected_state: Optional[str]) -> bool:
        """
        Validates state using constant-time comparison to prevent timing attacks.
        """
        if not received_state or not expected_state:
            return False
        return secrets.compare_digest(received_state, expected_state)

    @staticmethod
    def exchange_code_for_token(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """
        Exchanges authorization code for an OAuth access token.
        Returns token payload: access_token, expires_in, scope.
        """
        if not code:
            raise TokenExchangeError("Authorization code is empty.")
        if not client_id or not client_secret:
            raise TokenExchangeError("Client ID or Client Secret is missing.")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Connection": "close",
        }

        last_err = None
        response = None
        for attempt in range(3):
            try:
                response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=timeout)
                break
            except requests.RequestException as e:
                last_err = e
                logger.warning("Token exchange attempt %d failed (%s), retrying...", attempt + 1, e)
                import time
                time.sleep(1)

        if response is None:
            logger.error("Network error during token exchange after retries: %s", last_err)
            raise TokenExchangeError(f"Network error communicating with LinkedIn: {last_err}") from last_err

        if response.status_code != 200:
            try:
                err_json = response.json()
                err_desc = err_json.get("error_description") or err_json.get("error") or response.text
            except Exception:
                err_desc = response.text
            logger.error("LinkedIn token exchange returned HTTP %s: %s", response.status_code, err_desc)
            raise TokenExchangeError(f"LinkedIn authentication failed ({response.status_code}): {err_desc}")

        try:
            token_data = response.json()
        except ValueError as e:
            raise TokenExchangeError(f"Invalid JSON response from LinkedIn token endpoint: {e}") from e

        if "access_token" not in token_data:
            raise TokenExchangeError(f"Access token missing in response: {token_data}")

        return token_data

