"""Whisper-based transcription engine using faster-whisper."""

import logging
import time

import numpy as np
from faster_whisper import WhisperModel

from .transcription import ModelStatus, TranscriptionEngine, TranscriptionResult

logger = logging.getLogger(__name__)

MODEL_ORDER = ["medium", "small", "base", "tiny"]


class WhisperTranscriptionEngine(TranscriptionEngine):
    def __init__(self):
        self._model: WhisperModel | None = None
        self._status = ModelStatus.LOADING
        self._language = "en"
        self._model_name = ""

    def initialize(self, model_size: str, language: str) -> None:
        self._language = language
        self._status = ModelStatus.LOADING

        # Try requested model, fall back to smaller if OOM
        sizes_to_try = MODEL_ORDER[MODEL_ORDER.index(model_size):]

        for size in sizes_to_try:
            # Use English-specific model when language is 'en'
            model_id = f"{size}.en" if language == "en" else size
            try:
                logger.info(f"Loading Whisper model: {model_id}")
                self._model = WhisperModel(
                    model_id, device="cpu", compute_type="int8",
                    cpu_threads=6,
                )
                self._model_name = model_id
                self._status = ModelStatus.READY
                logger.info(f"Model '{size}' loaded successfully")
                return
            except Exception as e:
                logger.warning(f"Failed to load model '{model_id}': {e}")
                continue

        self._status = ModelStatus.ERROR
        raise RuntimeError("Failed to load any Whisper model")

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult | None:
        if self._model is None or self._status != ModelStatus.READY:
            return None

        self._status = ModelStatus.PROCESSING
        start = time.time()

        try:
            lang = None if self._language == "auto" else self._language
            segments, info = self._model.transcribe(
                audio,
                language=lang,
                beam_size=3,
                best_of=2,
                vad_filter=True,
                without_timestamps=True,
                condition_on_previous_text=True,
            )

            texts = []
            total_confidence = 0.0
            count = 0
            for segment in segments:
                texts.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                count += 1

            elapsed_ms = (time.time() - start) * 1000
            self._status = ModelStatus.READY

            if not texts or count == 0:
                return None

            avg_confidence = total_confidence / count
            # Convert log prob to a 0-1 scale (rough approximation)
            confidence = min(1.0, max(0.0, 1.0 + avg_confidence))

            if confidence <= 0.3:
                return None

            return TranscriptionResult(
                text=" ".join(texts),
                language=info.language if self._language == "auto" else self._language,
                confidence=confidence,
                processing_time_ms=elapsed_ms,
            )

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            self._status = ModelStatus.READY
            return None

    def set_language(self, language: str) -> None:
        self._language = language

    def get_status(self) -> ModelStatus:
        return self._status

    def get_model_name(self) -> str:
        return self._model_name
