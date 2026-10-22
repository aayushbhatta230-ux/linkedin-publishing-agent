"""
Unit tests for URL intake (GitHub repos and public web demos).
"""
from unittest.mock import MagicMock, patch

import pytest

from core.url_intake import URLIntakeService


@pytest.fixture
def intake_service():
    return URLIntakeService()


def test_parse_github_repo(intake_service):
    """Test extracting owner and repo name from multiple URL patterns."""
    cases = [
        ("https://github.com/aayushbhatta/OpenJarvis", ("aayushbhatta", "OpenJarvis")),
        ("http://github.com/aayushbhatta/HandChord/", ("aayushbhatta", "HandChord")),
        ("https://github.com/torvalds/linux.git", ("torvalds", "linux")),
    ]
    for url, expected in cases:
        assert intake_service.parse_github_repo(url) == expected

    assert intake_service.parse_github_repo("https://example.com/not/github") is not None  # parses 2 parts
    assert intake_service.is_github_url("https://example.com/not/github") is False
    assert intake_service.is_github_url("https://github.com/user/repo") is True


@patch("requests.Session.get")
def test_fetch_github_info_success(mock_get, intake_service):
    """Test fetching GitHub metadata and README excerpt with mocked API."""
    def get_side_effect(url, timeout):
        resp = MagicMock()
        if "api.github.com/repos" in url:
            resp.status_code = 200
            resp.json.return_value = {
                "description": "Autonomous local agent",
                "language": "Python",
                "topics": ["ai", "agents", "local-llm"],
                "stargazers_count": 42,
            }
        elif "raw.githubusercontent.com" in url:
            resp.status_code = 200
            resp.text = "# OpenJarvis\nRuns on local hardware without paid APIs."
        else:
            resp.status_code = 404
        return resp

    mock_get.side_effect = get_side_effect

    res = intake_service.fetch_github_info("https://github.com/aayushbhatta/OpenJarvis")

    assert res["success"] is True
    assert res["description"] == "Autonomous local agent"
    assert res["language"] == "Python"
    assert "OpenJarvis" in res["formatted_summary"]
    assert "Runs on local hardware" in res["formatted_summary"]


@patch("requests.Session.get")
def test_fetch_webpage_info_success(mock_get, intake_service):
    """Test extracting title and meta description from public webpage."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>KrishiPath AI - Crop Health Diagnostics</title>
        <meta name="description" content="Offline-first crop disease diagnosis for farmers.">
    </head>
    <body>
        <h1>Offline Plant Pathogen Vision</h1>
        <p>Built with lightweight edge models running on modest hardware.</p>
    </body>
    </html>
    """
    mock_get.return_value = mock_resp

    res = intake_service.fetch_webpage_info("https://krishipath.ai")

    assert res["success"] is True
    assert res["title"] == "KrishiPath AI - Crop Health Diagnostics"
    assert "Offline-first" in res["description"]
    assert "Offline Plant Pathogen Vision" in res["formatted_summary"]
