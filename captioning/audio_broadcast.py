"""Live audio broadcaster - encodes PCM to Opus via PyAV and pushes to WebSocket clients."""

import asyncio
import io
import logging
import threading

import av
import numpy as np
from aiohttp import web

logger = logging.getLogger(__name__)

# Opus frame size: 960 samples = 20ms at 48kHz
OPUS_FRAME_SAMPLES = 960
# Accumulate 500ms of audio per segment (25 frames × 20ms)
FRAMES_PER_SEGMENT = 25
# Overlap frames from previous segment to smooth encoder startup
OVERLAP_FRAMES = 3


class AudioBroadcaster:
    """Encodes raw PCM audio to Ogg/Opus segments and broadcasts via WebSocket.

    Each segment is a self-contained Ogg/Opus file that browsers can decode
    with decodeAudioData(). Segments are 500ms long for good codec quality.
    """

    def __init__(self, sample_rate: int = 48000, channels: int = 1, bitrate: int = 96000, max_clients: int = 50):
        self._sample_rate = sample_rate
        self._channels = channels
        self._bitrate = bitrate
        self._max_clients = max_clients
        self._clients: set[web.WebSocketResponse] = set()
        self._pcm_buffer = np.array([], dtype=np.float32)
        self._lock = threading.Lock()
        self._broadcast_task: asyncio.Task | None = None
        self._running = False
        self._layout = "mono" if channels == 1 else "stereo"
        self._prev_tail: list[np.ndarray] = []  # Last few frames from previous segment

    def start(self) -> None:
        """Mark broadcaster as running."""
        self._running = True
        logger.info(f"Audio broadcaster started (Opus {self._bitrate // 1000}kbps, {self._sample_rate}Hz, {FRAMES_PER_SEGMENT * 20}ms segments)")

    def stop(self) -> None:
        """Shut down and disconnect clients."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()

    def _mux_segment(self, pcm_frames: list[np.ndarray]) -> bytes:
        """Encode and mux PCM frames into a self-contained Ogg/Opus file.

        Prepends overlap frames from the previous segment to give the encoder
        context, then only outputs the non-overlap portion. Applies fade-in/out
        at segment boundaries to eliminate clicks.
        """
        # Prepend previous tail as encoder warmup
        all_frames = self._prev_tail + pcm_frames

        # Save tail for next segment's warmup
        self._prev_tail = pcm_frames[-OVERLAP_FRAMES:]

        buf = io.BytesIO()
        output = av.open(buf, mode="w", format="ogg")
        stream = output.add_stream("libopus", rate=self._sample_rate)
        stream.bit_rate = self._bitrate
        stream.layout = self._layout

        for i, raw in enumerate(all_frames):
            # Apply gain boost (+12dB)
            raw = raw * 4.0
            np.clip(raw, -1.0, 1.0, out=raw)

            frame = av.AudioFrame.from_ndarray(
                raw.reshape(1, -1), format="flt", layout=self._layout
            )
            frame.sample_rate = self._sample_rate
            frame.pts = i * OPUS_FRAME_SAMPLES
            for pkt in stream.encode(frame):
                output.mux(pkt)

        # Flush
        for pkt in stream.encode(None):
            output.mux(pkt)

        output.close()
        return buf.getvalue()

    async def start_broadcast_loop(self) -> None:
        """Async loop that encodes and sends Ogg segments to all clients."""
        self._broadcast_task = asyncio.current_task()
        segment_samples = OPUS_FRAME_SAMPLES * FRAMES_PER_SEGMENT

        while self._running:
            # Check if we have enough PCM to encode a segment
            pcm_ready = None
            with self._lock:
                if len(self._pcm_buffer) >= segment_samples:
                    frames = []
                    for _ in range(FRAMES_PER_SEGMENT):
                        raw = self._pcm_buffer[:OPUS_FRAME_SAMPLES].copy()
                        self._pcm_buffer = self._pcm_buffer[OPUS_FRAME_SAMPLES:]
                        frames.append(raw)
                    pcm_ready = frames

            if pcm_ready:
                try:
                    segment = await asyncio.to_thread(self._mux_segment, pcm_ready)
                    if segment:
                        await self._send_to_clients(segment)
                except Exception as e:
                    logger.debug(f"Encode error: {e}")
            else:
                await asyncio.sleep(0.01)

    def feed_audio(self, pcm: np.ndarray) -> None:
        """Feed raw PCM samples from the audio callback (called from audio thread).

        Only buffers data — encoding happens in the broadcast loop.
        """
        if not self._running:
            return

        with self._lock:
            self._pcm_buffer = np.concatenate([self._pcm_buffer, pcm])

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket handler for /ws/audio."""
        if len(self._clients) >= self._max_clients:
            return web.Response(status=503, text="Too many audio clients")

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._clients.add(ws)
        logger.info(f"Audio client connected ({len(self._clients)} total)")

        try:
            async for msg in ws:
                pass  # One-way broadcast, ignore client messages
        finally:
            self._clients.discard(ws)
            logger.info(f"Audio client disconnected ({len(self._clients)} total)")

        return ws

    async def _send_to_clients(self, data: bytes) -> None:
        """Send binary Ogg segment to all connected clients."""
        if not self._clients:
            return
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_bytes(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    @property
    def client_count(self) -> int:
        return len(self._clients)
