"""Audio input handler - captures from USB/system audio interface."""

import logging
import time
from collections import deque

import numpy as np
import sounddevice as sd

from .config import AudioConfig

logger = logging.getLogger(__name__)


def _resolve_alsa_card_name(device_str: str) -> int | None:
    """Resolve an ALSA identifier (plughw:CARD=Name,DEV=0) to a sounddevice index.

    Extracts the CARD name and matches it against sounddevice's device list.
    Returns the matching device index, or None if not found.
    """
    # Extract card name from plughw:CARD=Name,DEV=0 or hw:CARD=Name,DEV=0
    import re
    match = re.search(r"CARD=([^,]+)", device_str)
    if not match:
        return None
    card_name = match.group(1)

    # Search sounddevice's device list for a matching input device
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] < 1:
            continue
        # sounddevice names often include the ALSA card name
        if card_name.lower() in dev["name"].lower():
            return idx
    return None


def validate_audio_device(device: str | int | None) -> int | None:
    """Validate the configured audio device at startup.

    Accepts None (system default), an integer index, or an ALSA device
    string (e.g. 'plughw:CARD=Device,DEV=0').  For ALSA strings, resolves
    to the matching sounddevice index since PortAudio cannot open raw ALSA
    identifiers directly.

    Returns the resolved device value to pass to sd.InputStream(device=...).
    """
    if device is None:
        default = sd.query_devices(kind="input")
        logger.info(f"Audio input: using system default — {default['name']}")
        return device

    if isinstance(device, int):
        info = sd.query_devices(device)
        if info["max_input_channels"] < 1:
            raise RuntimeError(
                f"Audio device index {device} ({info['name']}) has no input channels"
            )
        logger.info(f"Audio input: index {device} — {info['name']}")
        return device

    # String — ALSA identifier like plughw:CARD=Device,DEV=0
    # Resolve to sounddevice index since PortAudio can't open these directly
    if device.startswith(("hw:", "plughw:")):
        idx = _resolve_alsa_card_name(device)
        if idx is not None:
            info = sd.query_devices(idx)
            logger.info(f"Audio input: '{device}' resolved to index {idx} — {info['name']}")
            return idx
        else:
            raise RuntimeError(
                f"Audio device '{device}' — could not find a matching input device. "
                f"Run 'arecord -l' to verify the card name, then check that the CARD= "
                f"value matches a device in 'python -c \"import sounddevice; print(sounddevice.query_devices())\"'"
            )

    # Plain substring match against device names
    try:
        info = sd.query_devices(device)
        if info["max_input_channels"] < 1:
            raise RuntimeError(
                f"Audio device '{device}' ({info['name']}) has no input channels"
            )
        logger.info(f"Audio input: '{device}' — {info['name']}")
        return device
    except ValueError:
        raise RuntimeError(
            f"Audio device '{device}' not found. "
            "Use an ALSA identifier (plughw:CARD=...,DEV=0), "
            "a device index, or null for system default."
        )


class AudioInputHandler:
    def __init__(self, config: AudioConfig):
        self._config = config
        self._buffer: deque[np.ndarray] = deque()
        self._capturing = False
        self._stream: sd.InputStream | None = None
        self._input_level: float = -100.0
        self._connected = True
        self._audio_tap: callable | None = None  # Optional tap for live audio streaming

    def set_audio_tap(self, tap: callable) -> None:
        """Set a callback that receives a copy of every raw PCM buffer (audio thread)."""
        self._audio_tap = tap

    def start_capture(self) -> None:
        """Start capturing audio from configured device."""
        self._capturing = True
        try:
            self._stream = sd.InputStream(
                device=self._config.input_device,
                samplerate=self._config.sample_rate,
                channels=self._config.channels,
                dtype="float32",
                latency="high",
                blocksize=4096,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._connected = True
            logger.info("Audio capture started")
        except Exception as e:
            self._connected = False
            logger.error(f"Failed to start audio capture: {e}")
            raise

    def stop_capture(self) -> None:
        """Stop audio capture."""
        self._capturing = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_chunk(self) -> np.ndarray | None:
        """Get a chunk of audio, splitting on natural pauses when possible."""
        min_samples = int(self._config.sample_rate * self._config.min_chunk_seconds)
        max_samples = int(self._config.sample_rate * self._config.max_chunk_seconds)
        pause_samples = int(self._config.sample_rate * 0.3)  # 300ms silence = pause

        # Drain deque into local list (atomic popleft, no lock needed)
        chunks = []
        while self._buffer:
            try:
                chunks.append(self._buffer.popleft())
            except IndexError:
                break

        if not chunks:
            return None

        concatenated = np.concatenate(chunks)
        if len(concatenated) < min_samples:
            # Not enough audio yet — put it back
            self._buffer.appendleft(concatenated)
            return None

        # Look for a silence gap after the minimum length
        cut_point = None
        search_end = min(len(concatenated), max_samples)

        for pos in range(min_samples, search_end - pause_samples, pause_samples // 2):
            window = concatenated[pos:pos + pause_samples]
            peak = np.max(np.abs(window))
            level_db = 20 * np.log10(peak + 1e-10)
            if level_db < self._config.silence_threshold_db + 10:  # Slightly above silence threshold
                cut_point = pos
                break

        # If no pause found and we've hit max, cut at max
        if cut_point is None:
            if len(concatenated) >= max_samples:
                cut_point = max_samples
            else:
                # Wait for more audio or a pause — put it back
                self._buffer.appendleft(concatenated)
                return None

        chunk = concatenated[:cut_point]
        leftover = concatenated[cut_point:]
        if len(leftover) > 0:
            self._buffer.appendleft(leftover)

        return self._preprocess(chunk)

    def get_input_level(self) -> float:
        """Return current input level in dB."""
        return self._input_level

    def is_capturing(self) -> bool:
        return self._capturing and self._connected

    def is_connected(self) -> bool:
        return self._connected

    def _audio_callback(self, indata: np.ndarray, frames, time_info, status):
        if status:
            logger.warning(f"Audio status: {status}")
            if "input overflow" not in str(status).lower():
                self._connected = False
                return

        audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()

        # Update level meter
        peak = np.max(np.abs(audio))
        self._input_level = 20 * np.log10(peak + 1e-10)

        # Feed raw PCM to audio stream tap (before any resampling)
        if self._audio_tap is not None:
            try:
                self._audio_tap(audio.copy())
            except Exception:
                pass  # Never let the tap break audio capture

        # deque.append is GIL-atomic — no lock needed
        self._buffer.append(audio.copy())

    def _preprocess(self, audio: np.ndarray) -> np.ndarray:
        """Resample if needed and normalize audio to target level."""
        # Resample to 16kHz for Whisper if capture rate differs
        if self._config.sample_rate != 16000:
            ratio = self._config.sample_rate // 16000
            if self._config.sample_rate == 16000 * ratio:
                # Integer ratio — use fast decimation with anti-alias filter
                from scipy.signal import decimate
                audio = decimate(audio, ratio, ftype="fir", zero_phase=False).astype(np.float32)
            else:
                # Non-integer ratio — fall back to FFT resample
                from scipy.signal import resample
                target_length = int(len(audio) * 16000 / self._config.sample_rate)
                audio = resample(audio, target_length).astype(np.float32)

        peak = np.max(np.abs(audio))
        if peak < 1e-10:
            return audio

        # Normalize to -3 dB
        target_peak = 10 ** (-3.0 / 20)
        audio = audio * (target_peak / peak)
        return audio

    def is_silent(self, audio: np.ndarray) -> bool:
        """Check if audio chunk is below silence threshold."""
        peak = np.max(np.abs(audio))
        level_db = 20 * np.log10(peak + 1e-10)
        return level_db < self._config.silence_threshold_db
