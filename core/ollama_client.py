"""
Ollama client optimized for 8 GB RAM local workstations.
Executes models sequentially (moondream for vision, qwen2.5:3b for drafting).
Applies aggressive image resizing and bounded context window to prevent memory pressure.
Gracefully falls back to deterministic local generation when Ollama service is unavailable.
"""
import base64
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from PIL import Image

from config import config
from core.persona import (
    build_system_prompt,
    format_user_prompt,
    generate_deterministic_offline_post,
)

logger = logging.getLogger("ollama_client")


class OllamaClient:
    """Manages local inference with health checking, image compression, and RAM safeguards."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        writing_model: Optional[str] = None,
        vision_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or config.ollama_base_url).rstrip("/")
        self.writing_model = writing_model or config.ollama_writing_model
        self.vision_model = vision_model or config.ollama_vision_model
        self.timeout = timeout or config.ollama_timeout

    def check_health(self) -> Dict[str, Any]:
        """
        Pings Ollama server and checks installed models.
        Returns:
            Dict containing availability status, model list, and warnings.
        """
        url = f"{self.base_url}/api/tags"
        try:
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                model_names = [m.get("name", "") for m in data.get("models", [])]
                has_writer = any(self.writing_model.split(":")[0] in m for m in model_names)
                has_vision = any(self.vision_model.split(":")[0] in m for m in model_names)

                # Auto-detect best installed writing model if configured default is missing
                if not has_writer and model_names:
                    for candidate in model_names:
                        c_lower = candidate.lower()
                        if "embed" in c_lower:
                            continue
                        if any(w in c_lower for w in ["qwen", "llama", "gemma", "mistral", "phi"]):
                            self.writing_model = candidate
                            has_writer = True
                            logger.info("Auto-selected installed writing model: %s", self.writing_model)
                            break
                    if not has_writer:
                        for candidate in model_names:
                            if "embed" not in candidate.lower():
                                self.writing_model = candidate
                                has_writer = True
                                break

                return {
                    "available": True,
                    "models": model_names,
                    "has_writer": has_writer,
                    "has_vision": has_vision,
                    "writing_model": self.writing_model,
                    "vision_model": self.vision_model,
                    "error": None,
                }
            return {
                "available": False,
                "models": [],
                "has_writer": False,
                "has_vision": False,
                "error": f"Ollama HTTP {resp.status_code}",
            }
        except requests.RequestException as e:
            return {
                "available": False,
                "models": [],
                "has_writer": False,
                "has_vision": False,
                "error": str(e),
            }

    def resize_image_for_inference(self, image_input: Union[str, Path, bytes, Image.Image], max_dim: int = 1024) -> str:
        """
        Resizes an image down to max_dim and encodes to base64 JPEG.
        Keeps RAM usage low during vision model inference.
        """
        if isinstance(image_input, (str, Path)):
            img = Image.open(image_input)
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        # Convert RGBA to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize keeping aspect ratio
        width, height = img.size
        if width > max_dim or height > max_dim:
            if width > height:
                new_w = max_dim
                new_h = int(height * (max_dim / width))
            else:
                new_h = max_dim
                new_w = int(width * (max_dim / height))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def analyze_image(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        custom_prompt: str = "Describe this image technically. Highlight the software UI, hardware components, or architecture diagrams visible.",
    ) -> Dict[str, Any]:
        """
        Sends resized image to local vision model (moondream) for feature extraction.
        Runs sequentially before drafting to avoid concurrent model RAM spikes.
        """
        health = self.check_health()
        if not health["available"]:
            return {
                "success": False,
                "analysis": "Image attached (Ollama vision model offline).",
                "is_fallback": True,
            }

        try:
            b64_image = self.resize_image_for_inference(image_input, max_dim=config.max_image_dimension)
        except Exception as e:
            logger.error("Failed to process image for vision model: %s", e)
            return {"success": False, "analysis": "", "error": str(e)}

        payload = {
            "model": self.vision_model,
            "prompt": custom_prompt,
            "images": [b64_image],
            "stream": False,
            "options": {
                "num_ctx": 1536,
                "temperature": 0.2,
            },
        }

        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                return {"success": True, "analysis": text, "is_fallback": False}
            logger.warning("Vision model returned HTTP %s: %s", resp.status_code, resp.text)
        except requests.RequestException as e:
            logger.warning("Vision inference request failed: %s", e)

        return {
            "success": False,
            "analysis": "Image processed, but local vision inference timed out or model missing.",
            "is_fallback": True,
        }

    def generate_draft(
        self,
        mode: str,
        title: str,
        summary_context: str,
        user_notes: str,
        image_analysis: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates LinkedIn post draft using qwen2.5:3b.
        If Ollama is unreachable, falls back to deterministic offline template engine.
        """
        system_prompt = build_system_prompt(config.author_name, config.author_role)
        user_prompt = format_user_prompt(
            mode=mode,
            title=title,
            summary_context=summary_context,
            user_notes=user_notes,
            image_analysis=image_analysis,
            source_url=source_url,
        )

        health = self.check_health()
        if not health["available"]:
            logger.info("Ollama is offline. Utilizing deterministic offline fallback.")
            offline_text = generate_deterministic_offline_post(
                mode=mode,
                title=title,
                context=summary_context,
                user_notes=user_notes,
                image_analysis=image_analysis,
                source_url=source_url,
            )
            return {
                "success": True,
                "text": offline_text,
                "model_used": "Deterministic Offline Engine",
                "is_fallback": True,
                "note": "Generated via offline engine (Ollama service not running at localhost:11434).",
            }

        payload = {
            "model": self.writing_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "num_ctx": config.ollama_max_context_tokens,
                "temperature": 0.65,
                "top_p": 0.9,
            },
        }

        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                raw_response = resp.json().get("response", "").strip()
                # Clean any outer quotes or accidental leading conversational preambles
                cleaned = raw_response.strip('"`')
                return {
                    "success": True,
                    "text": cleaned,
                    "model_used": self.writing_model,
                    "is_fallback": False,
                    "note": None,
                }
            logger.warning("Writing model returned HTTP %s: %s", resp.status_code, resp.text)
        except requests.RequestException as e:
            logger.warning("Draft generation request failed: %s", e)

        # Graceful fallback on network/inference error
        offline_text = generate_deterministic_offline_post(
            mode=mode,
            title=title,
            context=summary_context,
            user_notes=user_notes,
            image_analysis=image_analysis,
            source_url=source_url,
        )
        return {
            "success": True,
            "text": offline_text,
            "model_used": "Deterministic Offline Engine",
            "is_fallback": True,
            "note": f"Inference with {self.writing_model} failed. Loaded deterministic template.",
        }


ollama_client = OllamaClient()

