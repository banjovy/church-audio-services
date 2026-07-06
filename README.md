# Church Audio Services

Real-time captioning and live audio streaming for church services. Captures audio from a mixer board, transcribes with Whisper, and broadcasts captions and audio to phones/TVs via WebSocket.

## How It Works

Audio from mics or other audio sources goes through the mixer board into a USB audio interface connected to a dedicated mini PC. The system:

- Captures audio, splits it into chunks on silence boundaries, transcribes each chunk using faster-whisper, applies a profanity filter, and pushes captions to all connected clients in real time.
- Simultaneously encodes the live audio to Opus and streams it over WebSocket for hearing-assist listening — users connect at `/listen` and hear the service through earphones or hearing devices.

Clients connect via a simple web page — no app install required. A QR code is displayed for easy access.

## Requirements

- Python 3.10+
- Linux (Fedora, tested on HP EliteDesk 800 G4 Mini)
- System packages: `gcc gcc-c++ python3-devel portaudio-devel libjpeg-turbo-devel`
- USB audio interface connected to mixer board

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env — set ADMIN_PIN at minimum
```

## Configuration

- `.env` — environment variables (ADMIN_PIN required)
- `config.json` — application settings (model, audio, server port, profanity whitelist)

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
sudo ./audio_services/scripts/install-service.sh [username]
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
