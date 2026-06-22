# Church Captioning

Real-time live captioning system for church services. Captures audio from a mixer board, transcribes with Whisper, and broadcasts captions to phones/TVs via WebSocket.

## How It Works

Audio from a lapel mic goes through the mixer board into a USB audio interface connected to a dedicated mini PC. The system captures audio, splits it into chunks on silence boundaries, transcribes each chunk using faster-whisper, applies a profanity filter, and pushes the text to all connected clients in real time.

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
captioning

# From an audio file (for testing)
captioning --file path/to/audio.mp3

# Override model or language
captioning --model base --language es
```

## Deployment

An install script sets up a systemd service for auto-start on boot:

```bash
sudo ./captioning/scripts/install-service.sh [username]
```

## Display Modes

- `/` — home page with mode selection
- `/scroll` — scrolling transcript (phones)
- `/tv` — large text, auto-scroll (TVs/projectors)
- `/current` — shows only the latest caption
- `/qr` — QR code page (mDNS hostname)
- `/qr-ip` — QR code page (LAN IP fallback)

## Tech Stack

Python, faster-whisper, sounddevice, aiohttp, PyAV, better-profanity
