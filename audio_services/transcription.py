"""Transcription engine interface and Whisper implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import numpy as np


class ModelStatus(Enum):
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    PROCESSING = "processing"


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float
    processing_time_ms: float


class TranscriptionEngine(ABC):
    """Abstract interface for transcription backends."""

    @abstractmethod
    def initialize(self, model_size: str, language: str) -> None: ...

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> TranscriptionResult | None: ...

    @abstractmethod
    def set_language(self, language: str) -> None: ...

    @abstractmethod
    def get_status(self) -> ModelStatus: ...

    @abstractmethod
    def get_model_name(self) -> str: ...
