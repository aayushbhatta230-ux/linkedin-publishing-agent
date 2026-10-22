"""
Unit tests for Ollama client, prompt engineering, RAM safeguards, and offline fallback.
"""
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from core.ollama_client import OllamaClient
from core.persona import (
    BANNED_PHRASES,
    build_system_prompt,
    format_user_prompt,
    generate_deterministic_offline_post,
)


def test_persona_system_prompt_rules():
    """Verify system prompt contains author persona and bans corporate clichés."""
    prompt = build_system_prompt("Aayush Bhatta", "Technical Builder")
    assert "Aayush Bhatta" in prompt
    assert "Zero Corporate Sludge" in prompt
    for banned in BANNED_PHRASES[:3]:
        assert banned in prompt


def test_deterministic_offline_generator():
    """Verify fallback generator produces high-signal posts across all 4 modes."""
    modes = ["launch", "lesson", "progress", "architecture"]
    for mode in modes:
        post = generate_deterministic_offline_post(
            mode=mode,
            title="OpenJarvis",
            context="Local developer automation agent",
            user_notes="Reduced latency by 40% with caching.",
            image_analysis="Visible pipeline architecture",
            source_url="https://github.com/aayushbhatta/OpenJarvis",
        )
        assert len(post) > 100
        assert "OpenJarvis" in post
        assert "https://github.com/aayushbhatta/OpenJarvis" in post
        # Verify no banned corporate phrases
        for banned in BANNED_PHRASES:
            assert banned not in post.lower()


def test_image_resizing_safeguard():
    """Verify images exceeding 1024px are downsized to protect RAM."""
    client = OllamaClient()
    # Create large 3000x2000 in-memory image
    large_img = Image.new("RGB", (3000, 2000), color="blue")
    b64_res = client.resize_image_for_inference(large_img, max_dim=1024)

    assert isinstance(b64_res, str)
    assert len(b64_res) > 0


@patch("requests.get")
def test_ollama_health_online(mock_get):
    """Test health check when Ollama is running and has models."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "qwen2.5:3b"}, {"name": "moondream:latest"}]
    }
    mock_get.return_value = mock_resp

    client = OllamaClient(writing_model="qwen2.5:3b", vision_model="moondream")
    health = client.check_health()

    assert health["available"] is True
    assert health["has_writer"] is True
    assert health["has_vision"] is True


@patch("requests.get")
def test_ollama_health_offline(mock_get):
    """Test health check when Ollama is offline."""
    import requests
    mock_get.side_effect = requests.RequestException("Connection refused")

    client = OllamaClient()
    health = client.check_health()

    assert health["available"] is False
    assert health["has_writer"] is False


@patch("core.ollama_client.OllamaClient.check_health")
@patch("requests.post")
def test_generate_draft_online(mock_post, mock_health):
    """Test drafting when Ollama is online."""
    mock_health.return_value = {"available": True, "has_writer": True}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "Shipped a new lightweight local agent today. Runs on 8 GB RAM."
    }
    mock_post.return_value = mock_resp

    client = OllamaClient()
    res = client.generate_draft(
        mode="launch",
        title="TestProject",
        summary_context="Context",
        user_notes="Notes",
    )

    assert res["success"] is True
    assert res["is_fallback"] is False
    assert "8 GB RAM" in res["text"]


@patch("core.ollama_client.OllamaClient.check_health")
def test_generate_draft_offline_fallback(mock_health):
    """Test automatic fallback to deterministic templates when Ollama is offline."""
    mock_health.return_value = {"available": False}

    client = OllamaClient()
    res = client.generate_draft(
        mode="lesson",
        title="OfflinePay ESP32",
        summary_context="",
        user_notes="Fixed BLE buffer overflow",
    )

    assert res["success"] is True
    assert res["is_fallback"] is True
    assert "OfflinePay ESP32" in res["text"]
    assert "Deterministic Offline Engine" in res["model_used"]
