"""
Configuration management for Local LinkedIn Publishing Agent.
Loads environment variables from .env if present, otherwise provides sensible local defaults.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
SHARED_CLIENT_FILE = BASE_DIR / "shared_client.json"
PLACEHOLDER_VALUES = {"", "your_linkedin_client_id_here", "your_linkedin_client_secret_here"}


def load_shared_client(path: Path = SHARED_CLIENT_FILE) -> dict:
    """
    Loads the app owner's bundled LinkedIn Developer App credentials.
    Lets friends click "Connect with LinkedIn" without creating their own developer app.
    Returns an empty dict if the file is missing or malformed.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: str(data.get(k, "")).strip() for k in ("client_id", "client_secret", "redirect_uri")}
    except (OSError, ValueError, AttributeError):
        return {}


def _env_or_shared(env_key: str, shared_key: str, default: str = "") -> str:
    """Prefers a real .env value; falls back to shared_client.json, then the default."""
    value = os.getenv(env_key, "").strip()
    if value not in PLACEHOLDER_VALUES:
        return value
    return load_shared_client().get(shared_key) or default

@dataclass
class AppConfig:
    # LinkedIn OAuth 2.0
    client_id: str = field(default_factory=lambda: _env_or_shared("LINKEDIN_CLIENT_ID", "client_id"))
    client_secret: str = field(default_factory=lambda: _env_or_shared("LINKEDIN_CLIENT_SECRET", "client_secret"))
    redirect_uri: str = field(default_factory=lambda: _env_or_shared("LINKEDIN_REDIRECT_URI", "redirect_uri", "http://localhost:8501"))
    scopes: List[str] = field(default_factory=lambda: os.getenv(
        "LINKEDIN_SCOPES", "openid profile w_member_social"
    ).strip().split())

    # Ollama Local Configuration
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip())
    ollama_writing_model: str = field(default_factory=lambda: os.getenv("OLLAMA_WRITING_MODEL", "qwen2.5:3b").strip())
    ollama_vision_model: str = field(default_factory=lambda: os.getenv("OLLAMA_VISION_MODEL", "moondream").strip())
    ollama_timeout: int = field(default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")))
    ollama_max_context_tokens: int = field(default_factory=lambda: int(os.getenv("OLLAMA_MAX_CONTEXT_TOKENS", "2048")))
    max_image_dimension: int = field(default_factory=lambda: int(os.getenv("MAX_IMAGE_DIMENSION", "1024")))

    # Persona Defaults
    author_name: str = field(default_factory=lambda: os.getenv("DEFAULT_AUTHOR_NAME", "Aayush Bhatta").strip())
    author_role: str = field(default_factory=lambda: os.getenv("DEFAULT_AUTHOR_ROLE", "Technical Builder & Engineer").strip())

    # SQLite Database
    db_path: Path = field(default_factory=lambda: BASE_DIR / "linkedin_agent.db")
    media_upload_dir: Path = field(default_factory=lambda: BASE_DIR / "uploads")

    def is_linkedin_configured(self) -> bool:
        """Returns True if client_id and client_secret are provided."""
        return self.client_id not in PLACEHOLDER_VALUES and self.client_secret not in PLACEHOLDER_VALUES

    def uses_shared_client(self) -> bool:
        """True when credentials come from the bundled shared_client.json rather than the user's .env."""
        shared = load_shared_client()
        return bool(shared.get("client_id")) and shared.get("client_id") == self.client_id

# Singleton configuration instance
config = AppConfig()
config.media_upload_dir.mkdir(exist_ok=True, parents=True)

