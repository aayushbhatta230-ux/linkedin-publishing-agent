"""
Unit tests for SQLite database management, schema creation, audit logging, and duplicate prevention.
"""
from pathlib import Path

import pytest

from core.db import DatabaseManager, compute_content_hash, normalize_content


@pytest.fixture
def temp_db(tmp_path):
    """Provides an isolated DatabaseManager instance backed by a temporary file."""
    db_file = tmp_path / "test_linkedin_agent.db"
    return DatabaseManager(db_path=db_file)


def test_schema_initialization(temp_db):
    """Verify table and indexes are created properly."""
    with temp_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
        assert cursor.fetchone() is not None

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_posts_hash'")
        assert cursor.fetchone() is not None


def test_save_and_retrieve_draft(temp_db):
    """Test saving a draft post and retrieving it by ID."""
    draft_id = temp_db.save_draft(
        project_title="OpenJarvis Assistant",
        source_type="github",
        source_url="https://github.com/aayushbhatta/OpenJarvis",
        raw_input="Autonomous developer assistant using local LLMs",
        post_text="Shipped OpenJarvis v1.0 today. Built 100% locally.",
        media_path="/path/to/diagram.png",
    )

    assert draft_id == 1
    post = temp_db.get_post(draft_id)
    assert post is not None
    assert post["project_title"] == "OpenJarvis Assistant"
    assert post["status"] == "draft"
    assert post["media_path"] == "/path/to/diagram.png"


def test_update_status_published(temp_db):
    """Test updating post status to published with LinkedIn URN."""
    draft_id = temp_db.save_draft(
        project_title="HandChord",
        source_type="photo",
        source_url="",
        raw_input="Computer vision MIDI synthesizer",
        post_text="Turning camera frames into MIDI sounds in real time.",
    )

    temp_db.update_status(
        post_id=draft_id,
        status="published",
        linkedin_post_urn="urn:li:share:123456789",
    )

    post = temp_db.get_post(draft_id)
    assert post["status"] == "published"
    assert post["linkedin_post_urn"] == "urn:li:share:123456789"
    assert post["published_at"] is not None


def test_duplicate_submission_detection(temp_db):
    """Test duplicate detection catches identical posts and ignores distinct ones."""
    sample_text = "Exciting milestone on RoadDNA: edge defect detection running at 45 FPS."

    # Save and publish first post
    draft_id = temp_db.save_draft(
        project_title="RoadDNA",
        source_type="text",
        source_url="",
        raw_input="",
        post_text=sample_text,
    )
    temp_db.update_status(draft_id, status="published", linkedin_post_urn="urn:li:share:999")

    # Check duplicate on same content (with minor whitespace differences)
    duplicate_candidate = "  Exciting milestone on RoadDNA: edge defect detection running at 45 FPS. \n\n"
    dup = temp_db.check_duplicate(duplicate_candidate)
    assert dup is not None
    assert dup["id"] == draft_id
    assert dup["linkedin_post_urn"] == "urn:li:share:999"

    # Check non-duplicate
    non_dup = temp_db.check_duplicate("Completely different post content here.")
    assert non_dup is None


def test_history_ordering_and_deletion(temp_db):
    """Test history ordering and deletion."""
    temp_db.save_draft("Project A", "text", "", "", "Post A")
    id_b = temp_db.save_draft("Project B", "text", "", "", "Post B")

    history = temp_db.get_history()
    assert len(history) == 2
    assert history[0]["project_title"] == "Project B"  # most recent first

    # Delete project B
    deleted = temp_db.delete_post(id_b)
    assert deleted is True
    assert len(temp_db.get_history()) == 1

