"""
Configuration management for Local LinkedIn Publishing Agent.
Loads environment variables from .env if present, otherwise provides sensible local defaults.
"""
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

@dataclass
class AppConfig:
    # LinkedIn OAuth 2.0
    client_id: str = field(default_factory=lambda: os.getenv("LINKEDIN_CLIENT_ID", "").strip())
    client_secret: str = field(default_factory=lambda: os.getenv("LINKEDIN_CLIENT_SECRET", "").strip())
    redirect_uri: str = field(default_factory=lambda: os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8501").strip())
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
        return bool(self.client_id and self.client_secret and self.client_id != "your_linkedin_client_id_here")

# Singleton configuration instance
config = AppConfig()
config.media_upload_dir.mkdir(exist_ok=True, parents=True)

