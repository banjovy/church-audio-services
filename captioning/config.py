"""Configuration management for the captioning system."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level above this package)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass
class AudioConfig:
    input_device: str | int | None = None
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 3000
    silence_threshold_db: float = -40.0
    min_chunk_seconds: float = 3.0
    max_chunk_seconds: float = 8.0


def _require_admin_pin() -> str:
    pin = os.getenv("ADMIN_PIN", "")
    if not pin:
        raise RuntimeError(
            "ADMIN_PIN environment variable is not set. "
            "Set it in your .env file or export it before running."
        )
    return pin


@dataclass
class AppConfig:
    site_title: str = "Live Captions"
    whisper_model: str = "small"
    language: str = "en"
    log_level: str = "warning"
    server_port: int = 8080
    admin_pin: str = field(default_factory=_require_admin_pin)
    max_caption_history: int = 50
    max_clients: int = 50
    no_speech_timeout: int = 30
    reconnect_timeout: int = 600
    profanity_whitelist: list[str] = field(default_factory=list)
    audio: AudioConfig = field(default_factory=AudioConfig)

    @classmethod
    def from_file(cls, path: Path) -> "AppConfig":
        with open(path) as f:
            data = json.load(f)
        audio_data = data.pop("audio", {})
        audio = AudioConfig(**audio_data)
        # Remove null admin_pin from file data so env var is used
        if data.get("admin_pin") is None:
            data.pop("admin_pin", None)
        return cls(audio=audio, **data)
