# Hearing Assist Live Audio Streaming

## Overview

Live audio from the mixer board is streamed to mobile clients over local WiFi via WebSocket + Web Audio API. Users connect at `/listen`, tap play, and hear the service audio through earphones or hearing devices.

This feature is integrated into the existing audio services app — no separate server or external dependencies.

## Signal Chain

```
Mixer (XLR out) → USB audio interface → Computer (sounddevice capture @ 48kHz)
    ├── Whisper pipeline → text captions → WebSocket /ws
    └── Opus encoder (PyAV) → Ogg segments → WebSocket /ws/audio → Browser Web Audio API
```

## Implementation Details

### Encoding (server side)

- **Module**: `audio_services/audio_broadcast.py`
- **Encoder**: PyAV (libopus) — already a project dependency, no external binary needed
- **Audio tap**: `AudioInputHandler._audio_callback` passes a copy of every raw PCM buffer to the broadcaster before any Whisper preprocessing
- **Encoding runs off the audio thread** — raw PCM is buffered, encoding happens in `asyncio.to_thread` to avoid sounddevice input overflows
- **Segment format**: Self-contained Ogg/Opus files (500ms / 25 frames × 20ms each)
- **Overlap warmup**: 3 frames (60ms) from the previous segment are prepended to give the encoder context, eliminating cold-start clicks at segment boundaries
- **Gain**: +12dB boost applied before encoding (×4 linear, hard-clipped at ±1.0)
- **Bitrate**: 128kbps (configurable via `audio_stream_bitrate`)

### Playback (client side)

- **Page**: `/listen` → `audio_services/static/listen.html`
- **API**: WebSocket receives binary Ogg segments, decoded with `AudioContext.decodeAudioData()`
- **Jitter buffer**: 80ms lookahead scheduling to smooth network variance
- **Overlap trimming**: Client strips the first 60ms (3 × 960 samples) from each decoded segment to avoid double-playing the warmup frames
- **Controls**: Play/Stop toggle button, auto-reconnect on disconnect
- **Level meter**: Peak-based with square root scaling (typical speech reads ~50%)
- **iOS compatibility**: Audio starts on user tap (satisfies autoplay policy)

### Routing

| Endpoint | Purpose |
|----------|---------|
| `/listen` | Player page (HTML) |
| `/ws/audio` | WebSocket — binary Ogg/Opus segments |

### Configuration

In `config.json`:

```json
{
  "audio_stream_enabled": true,
  "audio_stream_bitrate": 128000,
  "max_audio_clients": 50
}
```

- `audio_stream_enabled`: Toggle the feature on/off
- `audio_stream_bitrate`: Opus bitrate in bps
- `max_audio_clients`: Independent limit for audio WebSocket connections

## Latency Budget

| Stage | Time |
|-------|------|
| sounddevice callback buffer | ~5-10ms |
| PCM accumulation (segment) | ~500ms |
| Opus encoding (in thread) | ~20ms |
| WebSocket send (LAN) | ~1-5ms |
| Client jitter buffer | ~80ms |
| **Total end-to-end** | **~600-700ms** |

## Architecture Decisions

### Why WebSocket + Web Audio API (not Icecast)

| Factor | Icecast | WebSocket (implemented) |
|--------|---------|------------------------|
| Latency | 2-4s minimum | ~600-700ms |
| External deps | FFmpeg + Icecast binaries | None (PyAV via pip) |
| Deployment | Separate service | Integrated in existing app |
| Client | `<audio>` tag | Web Audio API + JS |

### Why PyAV (not FFmpeg subprocess)

- Already a project dependency — zero deployment friction
- No subprocess lifecycle management (zombie processes, pipe buffering)
- Direct access to raw Opus packets and frame timing
- ~10 more lines of code buys a significantly simpler system

### Why 500ms segments (not smaller)

- Opus encoder needs context to produce good quality — very short segments (60ms) caused audible quality degradation and background noise
- 500ms gives the encoder 24 frames of context after the first cold-start frame
- Overlap warmup (60ms prepended from previous segment) further smooths the boundary
- Still well under 1 second total latency

## Bandwidth

- 128kbps × 50 clients = ~6.4 Mbps — easily handled by any modern WiFi AP
- Each Ogg segment is ~8-9KB (500ms audio + container overhead)

## Scalability

- Current design: direct broadcast to each WebSocket client
- Fine for <50 simultaneous listeners (current `max_audio_clients` default)
- For 50-200: consider worker threads or pub/sub
- For 200+: add an Icecast relay behind the app (encode once, Icecast distributes)

## Files

- `audio_services/audio_broadcast.py` — AudioBroadcaster class (encoder + WebSocket handler)
- `audio_services/audio.py` — Audio tap (`set_audio_tap` + callback integration)
- `audio_services/server.py` — `/ws/audio` and `/listen` routes
- `audio_services/main.py` — Broadcaster lifecycle wiring
- `audio_services/config.py` — `audio_stream_enabled`, `audio_stream_bitrate`, `max_audio_clients`
- `audio_services/static/listen.html` — Client player page

## Known Limitations / TODO

- First segment ever has no overlap warmup (empty previous tail) — minor quality blip on first 20ms
- No volume control on listen page yet
- Needs testing on iOS Safari, Android Chrome, various Bluetooth devices
- Segment size tuning: 300ms may be viable if click issue is fully resolved
- No captions on listen page (intentionally omitted — audio latency differs from caption latency)
