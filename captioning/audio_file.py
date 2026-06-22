"""File-based audio source for testing - reads MP3/WAV/etc via PyAV."""

import logging
import time

import av
import numpy as np

from .config import AudioConfig

logger = logging.getLogger(__name__)


class FileAudioSource:
    """Reads an audio file and yields chunks as if it were live input."""

    def __init__(self, file_path: str, config: AudioConfig, realtime: bool = True):
        self._config = config
        self._sample_rate = 16000  # Always decode to 16kHz for Whisper
        self._realtime = realtime
        self._audio = self._load_file(file_path)
        self._position = 0
        self._capturing = True
        self._last_chunk_time = 0.0
        logger.info(
            f"Loaded audio file: {file_path} "
            f"({len(self._audio) / self._sample_rate:.1f}s)"
        )

    def _load_file(self, path: str) -> np.ndarray:
        """Decode any audio format to 16kHz mono float32 via PyAV."""
        container = av.open(path)
        resampler = av.AudioResampler(
            format="s16", layout="mono", rate=16000
        )

        frames = []
        for frame in container.decode(audio=0):
            resampled = resampler.resample(frame)
            for r in resampled:
                array = r.to_ndarray().flatten()
                frames.append(array)

        container.close()

        if not frames:
            raise RuntimeError(f"No audio data decoded from {path}")

        # Convert int16 to float32 [-1.0, 1.0]
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        return audio

    def get_chunk(self) -> np.ndarray | None:
        """Get a chunk split on natural pauses when possible."""
        min_samples = int(self._sample_rate * self._config.min_chunk_seconds)
        max_samples = int(self._sample_rate * self._config.max_chunk_seconds)
        pause_samples = int(self._sample_rate * 0.3)  # 300ms silence = pause

        if self._position >= len(self._audio):
            self._capturing = False
            return None

        remaining = len(self._audio) - self._position
        search_end = min(remaining, max_samples)

        if search_end < min_samples:
            # Last bit of audio — just return it
            chunk = self._audio[self._position:]
            self._position = len(self._audio)
        else:
            # Look for a silence gap after minimum length
            cut_point = None
            for pos in range(min_samples, search_end - pause_samples, pause_samples // 2):
                window = self._audio[self._position + pos:self._position + pos + pause_samples]
                peak = np.max(np.abs(window))
                level_db = 20 * np.log10(peak + 1e-10)
                if level_db < self._config.silence_threshold_db + 10:
                    cut_point = pos
                    break

            if cut_point is None:
                if remaining >= max_samples:
                    cut_point = max_samples
                else:
                    cut_point = remaining

            chunk = self._audio[self._position:self._position + cut_point]
            self._position += cut_point

        # Simulate real-time pacing
        if self._realtime and self._last_chunk_time > 0:
            chunk_duration = len(chunk) / self._sample_rate
            elapsed = time.time() - self._last_chunk_time
            wait = chunk_duration - elapsed
            if wait > 0:
                time.sleep(wait)

        self._last_chunk_time = time.time()

        # Normalize
        peak = np.max(np.abs(chunk))
        if peak > 1e-10:
            target_peak = 10 ** (-3.0 / 20)
            chunk = chunk * (target_peak / peak)

        return chunk

    def is_capturing(self) -> bool:
        return self._capturing

    def is_connected(self) -> bool:
        return True

    def is_silent(self, audio: np.ndarray) -> bool:
        peak = np.max(np.abs(audio))
        level_db = 20 * np.log10(peak + 1e-10)
        return level_db < self._config.silence_threshold_db

    def get_input_level(self) -> float:
        if self._position == 0 or self._position >= len(self._audio):
            return -100.0
        # Report level of most recent chunk
        samples = int(self._sample_rate * 0.1)
        start = max(0, self._position - samples)
        segment = self._audio[start:self._position]
        peak = np.max(np.abs(segment))
        return 20 * np.log10(peak + 1e-10)

    def stop_capture(self) -> None:
        self._capturing = False

    def start_capture(self) -> None:
        """No-op for file source, capture starts on init."""
        pass
