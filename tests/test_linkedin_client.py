"""
Unit tests for official LinkedIn REST API client (Posts API and Media Uploads).
All external API calls are mocked; zero credentials or network dependencies.
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.linkedin_client import (
    LinkedInAPIError,
    LinkedInAuthError,
    LinkedInClient,
    LinkedInPermissionError,
    LinkedInRateLimitError,
)


@pytest.fixture
def client():
    return LinkedInClient(timeout=5)


@patch("requests.get")
def test_get_member_profile_userinfo(mock_get, client):
    """Test retrieving member profile via modern OpenID userinfo endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "sub": "abc_person_123",
        "name": "Aayush Bhatta",
        "email": "aayush@example.com",
    }
    mock_get.return_value = mock_resp

    profile = client.get_member_profile("mock_token")

    assert profile["person_urn"] == "urn:li:person:abc_person_123"
    assert profile["name"] == "Aayush Bhatta"
    assert profile["email"] == "aayush@example.com"


@patch("requests.post")
def test_initialize_image_upload_success(mock_post, client):
    """Test initializing image upload with /rest/images endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "value": {
            "uploadUrl": "https://www.linkedin.com/mediaUpload/upload_target_123",
            "image": "urn:li:image:D4E10AQFxyz789",
        }
    }
    mock_post.return_value = mock_resp

    upload_url, image_urn = client.initialize_image_upload(
        access_token="mock_token",
        owner_urn="urn:li:person:abc_123",
    )

    assert upload_url == "https://www.linkedin.com/mediaUpload/upload_target_123"
    assert image_urn == "urn:li:image:D4E10AQFxyz789"
    mock_post.assert_called_once()


@patch("requests.put")
def test_upload_image_binary(mock_put, client):
    """Test uploading binary image data to presigned uploadUrl."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_put.return_value = mock_resp

    success = client.upload_image_binary(
        upload_url="https://www.linkedin.com/upload",
        image_bytes=b"\xff\xd8\xff\xe0...fake_jpeg",
        content_type="image/jpeg",
    )
    assert success is True


@patch("requests.post")
def test_create_text_post_success(mock_post, client):
    """Test creating a text-only post via /rest/posts."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.headers = {"x-restli-id": "urn:li:share:123456789"}
    mock_resp.json.return_value = {}
    mock_post.return_value = mock_resp

    result = client.create_post(
        access_token="mock_token",
        author_urn="urn:li:person:author_123",
        commentary="Shipped an autonomous agent today. Complete offline execution.",
    )

    assert result["success"] is True
    assert result["post_urn"] == "urn:li:share:123456789"


@patch("requests.post")
def test_create_post_with_media_success(mock_post, client):
    """Test creating a post with attached image URN."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.headers = {"x-restli-id": "urn:li:share:987654321"}
    mock_post.return_value = mock_resp

    result = client.create_post(
        access_token="mock_token",
        author_urn="urn:li:person:author_123",
        commentary="Check out this system architecture diagram.",
        image_urn="urn:li:image:D4E10AQFxyz789",
        alt_text="Architecture diagram",
    )

    assert result["success"] is True
    assert result["post_urn"] == "urn:li:share:987654321"

    # Verify media payload structure
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["content"]["media"]["id"] == "urn:li:image:D4E10AQFxyz789"
    assert sent_payload["content"]["media"]["altText"] == "Architecture diagram"


@patch("requests.post")
def test_linkedin_error_status_mapping(mock_post, client):
    """Test HTTP error status codes are mapped to specific domain exceptions."""
    # 401 Unauthorized -> LinkedInAuthError
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.json.return_value = {"message": "Invalid access token"}
    mock_post.return_value = mock_401

    with pytest.raises(LinkedInAuthError, match="LinkedIn authorization has expired"):
        client.create_post("bad_token", "urn:li:person:1", "Commentary")

    # 403 Forbidden -> LinkedInPermissionError
    mock_403 = MagicMock()
    mock_403.status_code = 403
    mock_403.json.return_value = {"message": "Not enough permissions to create post"}
    mock_post.return_value = mock_403

    with pytest.raises(LinkedInPermissionError, match="Missing required LinkedIn permissions"):
        client.create_post("valid_token", "urn:li:person:1", "Commentary")

    # 429 Rate Limit -> LinkedInRateLimitError
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.json.return_value = {"message": "Too many requests"}
    mock_post.return_value = mock_429

    with pytest.raises(LinkedInRateLimitError, match="rate limit exceeded"):
        client.create_post("valid_token", "urn:li:person:1", "Commentary")
