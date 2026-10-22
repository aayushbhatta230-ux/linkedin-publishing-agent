"""
SQLite database persistence for Local LinkedIn Publishing Agent.
Tracks draft generation, publication history, media paths, status, and duplicate submission prevention.
"""
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import config


def normalize_content(text: str) -> str:
    """Normalizes post text for consistent cryptographic hashing."""
    return " ".join(text.strip().lower().split())


def compute_content_hash(text: str) -> str:
    """Returns SHA-256 digest of normalized text for idempotency / duplicate detection."""
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


class DatabaseManager:
    """Manages SQLite connections, schema initialization, and transactional queries."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initializes database schema and indexes."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT,
                    raw_input TEXT,
                    post_text TEXT NOT NULL,
                    media_path TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    linkedin_post_urn TEXT,
                    error_message TEXT,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_hash ON posts(content_hash);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
                """
            )
            conn.commit()

    def save_draft(
        self,
        project_title: str,
        source_type: str,
        source_url: str,
        raw_input: str,
        post_text: str,
        media_path: Optional[str] = None,
    ) -> int:
        """Saves a newly generated or edited draft into history."""
        content_hash = compute_content_hash(post_text)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO posts (
                    project_title, source_type, source_url, raw_input,
                    post_text, media_path, status, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, CURRENT_TIMESTAMP)
                """,
                (
                    project_title.strip() or "Untitled Project",
                    source_type.strip(),
                    source_url.strip(),
                    raw_input.strip(),
                    post_text.strip(),
                    str(media_path) if media_path else None,
                    content_hash,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_status(
        self,
        post_id: int,
        status: str,
        linkedin_post_urn: str = "",
        error_message: str = "",
        updated_text: Optional[str] = None,
    ) -> None:
        """Updates publication status, LinkedIn URN, error details, and optional text changes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            published_at = datetime.now(timezone.utc).isoformat() if status == "published" else None

            if updated_text:
                new_hash = compute_content_hash(updated_text)
                cursor.execute(
                    """
                    UPDATE posts SET
                        status = ?,
                        linkedin_post_urn = ?,
                        error_message = ?,
                        post_text = ?,
                        content_hash = ?,
                        published_at = COALESCE(?, published_at)
                    WHERE id = ?
                    """,
                    (status, linkedin_post_urn, error_message, updated_text, new_hash, published_at, post_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE posts SET
                        status = ?,
                        linkedin_post_urn = ?,
                        error_message = ?,
                        published_at = COALESCE(?, published_at)
                    WHERE id = ?
                    """,
                    (status, linkedin_post_urn, error_message, published_at, post_id),
                )
            conn.commit()

    def check_duplicate(self, post_text: str, days_threshold: int = 7) -> Optional[Dict[str, Any]]:
        """
        Checks if an identical post was already published or saved recently.
        Returns the existing row dict if found, else None.
        """
        content_hash = compute_content_hash(post_text)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_threshold)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM posts
                WHERE content_hash = ? AND status = 'published' AND created_at >= ?
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                (content_hash, cutoff_date),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns ordered publication and draft history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM posts
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single post by id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_post(self, post_id: int) -> bool:
        """Deletes a post record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            conn.commit()
            return cursor.rowcount > 0


db = DatabaseManager()
