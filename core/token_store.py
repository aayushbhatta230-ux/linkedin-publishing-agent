"""
Secure token storage manager for LinkedIn OAuth 2.0 credentials.
Uses Windows Credential Locker (via keyring) as primary storage.
Falls back to a protected local JSON file (.secure_token.json) if keyring is unavailable.
Tokens are NEVER stored in SQLite, committed to Git, or exposed in logs.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("token_store")

SERVICE_NAME = "LinkedInPublishingAgent"
TOKEN_KEY = "oauth_payload"
FALLBACK_FILE = Path(__file__).resolve().parent.parent / ".secure_token.json"


class TokenStore:
    """Manages storage, retrieval, and invalidation of OAuth access tokens."""

    def __init__(self, fallback_path: Optional[Path] = None):
        self.fallback_file = fallback_path or FALLBACK_FILE
        self._keyring_available = self._test_keyring()

    def _test_keyring(self) -> bool:
        """Test if the system keyring backend is functional."""
        try:
            import keyring
            # Try a lightweight get on a dummy or non-existing key
            keyring.get_password(SERVICE_NAME, "__test_probe__")
            return True
        except Exception as e:
            logger.warning("System keyring unavailable (%s). Using local secure file fallback.", e)
            return False

    def save_token(
        self,
        access_token: str,
        expires_in: int = 5184000,  # LinkedIn default is 60 days (5,184,000s)
        member_urn: str = "",
        member_name: str = "",
        scopes: str = "",
    ) -> None:
        """Securely saves the token payload with expiration timestamp."""
        payload = {
            "access_token": access_token.strip(),
            "expires_at": int(time.time()) + int(expires_in),
            "member_urn": member_urn.strip(),
            "member_name": member_name.strip(),
            "scopes": scopes.strip(),
            "saved_at": int(time.time()),
        }
        serialized = json.dumps(payload)

        saved_in_keyring = False
        if self._keyring_available:
            try:
                import keyring
                keyring.set_password(SERVICE_NAME, TOKEN_KEY, serialized)
                saved_in_keyring = True
            except Exception as e:
                logger.error("Failed to write to system keyring: %s", e)

        if not saved_in_keyring:
            # Write to fallback file with restrictive mode
            self.fallback_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.fallback_file, "w", encoding="utf-8") as f:
                f.write(serialized)
            # Ensure permissions on Windows/POSIX
            try:
                os.chmod(self.fallback_file, 0o600)
            except Exception:
                pass

    def get_token(self) -> Optional[Dict[str, Any]]:
        """Retrieves and deserializes token payload. Returns None if absent."""
        serialized = None

        if self._keyring_available:
            try:
                import keyring
                serialized = keyring.get_password(SERVICE_NAME, TOKEN_KEY)
            except Exception as e:
                logger.warning("Keyring read failed: %s", e)

        if not serialized and self.fallback_file.exists():
            try:
                with open(self.fallback_file, "r", encoding="utf-8") as f:
                    serialized = f.read().strip()
            except Exception as e:
                logger.error("Failed to read fallback token file: %s", e)
                return None

        if not serialized:
            return None

        try:
            return json.loads(serialized)
        except Exception as e:
            logger.error("Failed to parse stored token JSON: %s", e)
            return None

    def delete_token(self) -> None:
        """Safe disconnect: wipes token from all storage mechanisms."""
        if self._keyring_available:
            try:
                import keyring
                keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
            except Exception:
                pass

        if self.fallback_file.exists():
            try:
                self.fallback_file.unlink()
            except Exception as e:
                logger.error("Failed to remove fallback token file: %s", e)

    def is_token_valid(self) -> bool:
        """Returns True if a valid token exists and has not expired."""
        token_data = self.get_token()
        if not token_data or "access_token" not in token_data:
            return False
        # Buffer of 60 seconds before actual expiration
        return token_data.get("expires_at", 0) > (time.time() + 60)

    def get_token_status(self) -> Dict[str, Any]:
        """
        Returns a sanitized status dictionary suitable for UI display.
        Never reveals the full raw token.
        """
        data = self.get_token()
        if not data:
            return {
                "connected": False,
                "status": "Disconnected",
                "member_name": "",
                "member_urn": "",
                "masked_token": "",
                "expires_in_days": 0,
                "expired": True,
            }

        raw = data.get("access_token", "")
        masked = f"{raw[:6]}...{raw[-4:]}" if len(raw) > 12 else "***"
        expires_at = data.get("expires_at", 0)
        remaining_seconds = expires_at - int(time.time())
        is_expired = remaining_seconds <= 0
        remaining_days = round(remaining_seconds / 86400, 1) if not is_expired else 0

        return {
            "connected": not is_expired,
            "status": "Connected" if not is_expired else "Expired",
            "member_name": data.get("member_name", "Authorized Member"),
            "member_urn": data.get("member_urn", ""),
            "masked_token": masked,
            "expires_in_days": remaining_days,
            "expired": is_expired,
            "scopes": data.get("scopes", ""),
        }


# Default singleton instance
token_store = TokenStore()

