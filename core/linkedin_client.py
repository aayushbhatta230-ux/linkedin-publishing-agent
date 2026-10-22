"""
Official LinkedIn REST API Client for Member Posts and Media Uploads.
Complies with official LinkedIn documentation:
- https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
"""
import logging
import os
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger("linkedin_client")

REST_API_BASE = "https://api.linkedin.com"
REST_POSTS_ENDPOINT = f"{REST_API_BASE}/rest/posts"
REST_IMAGES_ENDPOINT = f"{REST_API_BASE}/rest/images?action=initializeUpload"
USERINFO_ENDPOINT = f"{REST_API_BASE}/v2/userinfo"
LEGACY_ME_ENDPOINT = f"{REST_API_BASE}/v2/me"

LINKEDIN_VERSION = os.getenv("LINKEDIN_API_VERSION", "202610")
PROTOCOL_VERSION = "2.0.0"


class LinkedInAPIError(Exception):
    """Base exception for LinkedIn API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, raw_response: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.raw_response = raw_response


class LinkedInAuthError(LinkedInAPIError):
    """Raised on 401 Unauthorized (e.g. expired or revoked access token)."""
    pass


class LinkedInPermissionError(LinkedInAPIError):
    """Raised on 403 Forbidden (e.g. missing w_member_social or unapproved developer app)."""
    pass


class LinkedInRateLimitError(LinkedInAPIError):
    """Raised on 429 Rate Limited."""
    pass


class LinkedInClient:
    """Handles communication with official LinkedIn REST endpoints."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def _default_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token.strip()}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": PROTOCOL_VERSION,
            "LinkedIn-Version": LINKEDIN_VERSION,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Connection": "close",
        }

    def _handle_error_response(self, response: requests.Response, context: str) -> None:
        """Parses error body and raises appropriate typed exception."""
        status = response.status_code
        try:
            err_json = response.json()
            message = err_json.get("message") or err_json.get("error_description") or response.text
        except Exception:
            message = response.text

        detailed_msg = f"{context} failed (HTTP {status}): {message}"
        logger.error(detailed_msg)

        if status == 401:
            raise LinkedInAuthError("Your LinkedIn authorization has expired or is invalid. Please reconnect.", status, response.text)
        elif status == 403:
            raise LinkedInPermissionError(
                f"Missing required LinkedIn permissions or app unapproved ({detailed_msg}). "
                "Ensure your developer app has the 'Share on LinkedIn' (w_member_social) product enabled.",
                status,
                response.text,
            )
        elif status == 429:
            raise LinkedInRateLimitError("LinkedIn API rate limit exceeded. Please wait before retrying.", status, response.text)
        else:
            raise LinkedInAPIError(detailed_msg, status, response.text)

    def get_member_profile(self, access_token: str) -> Dict[str, str]:
        """
        Retrieves the authenticated member's profile and returns:
        {'person_urn': 'urn:li:person:...', 'name': '...', 'email': '...'}
        Tries OpenID userinfo endpoint first, falls back to legacy /v2/me.
        """
        headers = {
            "Authorization": f"Bearer {access_token.strip()}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Connection": "close",
        }

        # Attempt 1: Modern OpenID userinfo
        try:
            resp = requests.get(USERINFO_ENDPOINT, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                sub = data.get("sub", "")
                name = data.get("name") or f"{data.get('given_name', '')} {data.get('family_name', '')}".strip()
                return {
                    "person_urn": f"urn:li:person:{sub}" if sub else "",
                    "name": name or "LinkedIn Member",
                    "email": data.get("email", ""),
                    "picture": data.get("picture", ""),
                }
        except requests.RequestException as e:
            logger.warning("userinfo check failed: %s", e)

        # Attempt 2: Legacy /v2/me
        try:
            resp = requests.get(LEGACY_ME_ENDPOINT, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                member_id = data.get("id", "")
                first = data.get("localizedFirstName", "")
                last = data.get("localizedLastName", "")
                name = f"{first} {last}".strip()
                return {
                    "person_urn": f"urn:li:person:{member_id}" if member_id else "",
                    "name": name or "LinkedIn Member",
                    "email": "",
                    "picture": "",
                }
            self._handle_error_response(resp, "Profile retrieval")
        except requests.RequestException as e:
            raise LinkedInAPIError(f"Network error retrieving profile: {e}") from e

        return {"person_urn": "", "name": "LinkedIn Member", "email": "", "picture": ""}

    def initialize_image_upload(self, access_token: str, owner_urn: str) -> Tuple[str, str]:
        """
        Calls /rest/images?action=initializeUpload.
        Returns:
            Tuple of (uploadUrl, imageUrn)
        """
        headers = self._default_headers(access_token)
        payload = {
            "initializeUploadRequest": {
                "owner": owner_urn
            }
        }

        try:
            resp = requests.post(REST_IMAGES_ENDPOINT, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise LinkedInAPIError(f"Network failure initializing image upload: {e}") from e

        if resp.status_code not in (200, 201):
            self._handle_error_response(resp, "Initialize image upload")

        data = resp.json().get("value", {})
        upload_url = data.get("uploadUrl")
        image_urn = data.get("image")

        if not upload_url or not image_urn:
            raise LinkedInAPIError(f"Unexpected image initialization response: {resp.text}")

        return upload_url, image_urn

    def upload_image_binary(self, upload_url: str, image_bytes: bytes, content_type: str = "image/jpeg") -> bool:
        """Uploads raw binary bytes to the pre-signed LinkedIn uploadUrl."""
        headers = {
            "Content-Type": content_type,
            "User-Agent": "LocalLinkedInAgent/1.0",
        }
        try:
            resp = requests.put(upload_url, data=image_bytes, headers=headers, timeout=self.timeout + 15)
        except requests.RequestException as e:
            raise LinkedInAPIError(f"Network failure uploading image binary: {e}") from e

        if resp.status_code not in (200, 201):
            raise LinkedInAPIError(f"Binary upload failed with HTTP {resp.status_code}: {resp.text}")

        return True

    def create_post(
        self,
        access_token: str,
        author_urn: str,
        commentary: str,
        image_urn: Optional[str] = None,
        article_url: Optional[str] = None,
        alt_text: str = "",
    ) -> Dict[str, Any]:
        """
        Publishes a post via the official LinkedIn Posts API (POST /rest/posts).
        Returns:
            Dict containing 'id' (post URN) and status details.
        """
        if not commentary or not commentary.strip():
            raise LinkedInAPIError("Cannot publish empty post commentary.")
        if not author_urn or not author_urn.startswith("urn:li:"):
            raise LinkedInAPIError("Valid member author URN (urn:li:person:...) is required.")

        headers = self._default_headers(access_token)
        payload: Dict[str, Any] = {
            "author": author_urn,
            "commentary": commentary.strip(),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        if image_urn:
            payload["content"] = {
                "media": {
                    "id": image_urn,
                    "altText": alt_text or "Project preview image",
                }
            }
        elif article_url:
            payload["content"] = {
                "article": {
                    "source": article_url.strip(),
                    "title": "Project Link",
                }
            }

        try:
            resp = requests.post(REST_POSTS_ENDPOINT, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise LinkedInAPIError(f"Network error publishing post to LinkedIn: {e}") from e

        if resp.status_code not in (201, 200):
            self._handle_error_response(resp, "Post publishing")

        post_urn = resp.headers.get("x-restli-id") or ""
        if not post_urn:
            try:
                post_urn = resp.json().get("id", "")
            except Exception:
                pass

        return {
            "success": True,
            "post_urn": post_urn,
            "status_code": resp.status_code,
        }


linkedin_client = LinkedInClient()

