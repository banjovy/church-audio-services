# Church Audio Services

Real-time captioning and live audio streaming for church services. Captures audio from a mixer board, transcribes with Whisper, and broadcasts captions and audio to phones/TVs via WebSocket.

## How It Works

Audio from mics or other audio sources goes through the mixer board into a USB audio interface connected to a dedicated mini PC. The system:

- Captures audio, splits it into chunks on silence boundaries, transcribes each chunk using faster-whisper, applies a profanity filter, and pushes captions to all connected clients in real time.
- Simultaneously encodes the live audio to Opus and streams it over WebSocket for hearing-assist listening — users connect at `/listen` and hear the service through earphones or hearing devices.

Clients connect via a simple web page — no app install required. A QR code is displayed for easy access.

## Requirements

- Python 3.12 (required for GPU path with ctranslate2 3.24)
- Linux — tested on:
  - **Fedora 41** (Dell OptiPlex 3050 Tower, GTX 1050 Ti)
  - **Ubuntu 22.04 LTS** (same hardware)
- USB audio interface connected to mixer board
- For GPU: NVIDIA GTX 1050 Ti (or other Pascal/newer) with 470xx driver

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| Fedora 41 | Tested, production | Requires RPM Fusion for NVIDIA driver |
| Ubuntu 22.04 LTS | Tested | NVIDIA driver in official repos, simpler setup |

See the platform-specific install guides:
- [Fedora install guide](audio_services/docs/fedora/install.md)
- [Ubuntu install guide](audio_services/docs/ubuntu/install.md)

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env — set ADMIN_PIN at minimum
```

For GPU support, additional version-pinned packages are required. See the install guide for your platform.

## Configuration

- `.env` — environment variables (ADMIN_PIN required)
- `config.json` — application settings (model, audio device, GPU settings, server port, profanity whitelist)

## Running

```bash
# Live audio (default)
audio-services

# From an audio file (for testing)
audio-services --file path/to/audio.mp3

# Override model or language
audio-services --model base --language es
```

## Deployment

An install script sets up a systemd service for auto-start on boot:

```bash
# Fedora
sudo ./audio_services/scripts/fedora/install-service.sh [username]

# Ubuntu
sudo ./audio_services/scripts/ubuntu/install-service.sh [username]
```

## Display Modes

- `/` — home page with mode selection
- `/scroll` — scrolling transcript (phones)
- `/tv` — large text, auto-scroll (TVs/projectors)
- `/current` — shows only the latest caption
- `/listen` — live audio stream (hearing assist)
- `/qr` — QR code page (mDNS hostname)
- `/qr-ip` — QR code page (LAN IP fallback)

## Tech Stack

Python, faster-whisper, sounddevice, aiohttp, PyAV (Opus encoding), better-profanity

## Documentation

```
audio_services/docs/
├── fedora/
│   ├── install.md          # Full Fedora install guide
│   └── networking.md       # nmcli / NetworkManager reference
├── ubuntu/
│   ├── install.md          # Full Ubuntu install guide
│   └── networking.md       # Netplan / systemd-networkd reference
├── audio-troubleshooting.md
├── design-principles.md
├── display-guide.md
├── hardware-upgrade-options.md
├── hearing-assist-stream.md
├── https-options.md
├── viewer-guide.md
└── whisper-gpu-guide.md
```
