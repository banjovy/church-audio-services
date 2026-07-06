# Installation Guide

How to install (or reinstall) the audio services system on a fresh or existing machine.

## Prerequisites

- Fedora Linux v44 (tested on HP EliteDesk 800 G4 Mini, i5-8500T)
- User account for the service (default: `audio`) — see below
- USB audio interface connected to the mixer board's aux bus
- Internet connection (for initial package and model downloads)

### System Dependencies

Install these once:

```bash
sudo dnf install gcc gcc-c++ python3-devel portaudio-devel libjpeg-turbo-devel alsa-utils
```

These are needed to compile native extensions for audio capture, Whisper, and image processing. `alsa-utils` provides `arecord`, `aplay`, and `amixer` for audio troubleshooting.

### mDNS (optional but recommended)

Avahi lets devices find the server by hostname (e.g., `audio.local`) without knowing the IP:

```bash
sudo dnf install avahi
sudo systemctl enable --now avahi-daemon
```

To set the hostname to `audio` (so it resolves as `audio.local` on the LAN):

```bash
sudo hostnamectl set-hostname audio
```

### Firewall

Open the server port and mDNS so devices on the LAN can connect:

```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-service=mdns
sudo firewall-cmd --reload
```

### Service User Account

Create a dedicated user to run the service:

```bash
sudo useradd -m -s /bin/bash audio
```

This keeps the service isolated from other accounts on the system. The install script expects a home directory at `/home/audio`.

## Installation

### 1. Clone the repository

```bash
cd /home/audio
git clone <repo-url> church-audio-services
cd church-audio-services
```

Or if reinstalling on a machine that already has the repo:

```bash
cd /home/audio/church-audio-services
git fetch origin
git checkout main
git pull
```

### 2. Create (or reuse) the Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If the `.venv` already exists, just activate it — no need to recreate.

### 3. Install the package

```bash
pip install -e .
```

This installs in "editable" mode so the code runs directly from the repo. Any future `git pull` updates the running code without needing to reinstall (unless dependencies change).

If dependencies have changed since last install:

```bash
pip install -e . --upgrade
```

### 4. Configure environment

Create the `.env` file at the project root with your admin PIN:

```bash
cp .env.example .env
```

Then edit `.env` and set your PIN:

```
ADMIN_PIN=123456
```

Replace `123456` with your actual PIN. This protects the `/status` endpoint and admin controls.

### 5. Configure the audio input device

Identify your USB audio interface's ALSA card name:

```bash
arecord -l
```

Example output:

```
**** List of CAPTURE Hardware Devices ****
card 0: PCH [HDA Intel PCH], device 0: ALC295 Analog [ALC295 Analog]
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
```

The USB interface is card `Device`, subdevice `0`. Use a `plughw:` identifier in `config.json` — this tells ALSA to handle sample rate/format conversion automatically:

```json
"audio": {
  "input_device": "plughw:CARD=Device,DEV=0"
}
```

The `CARD=` value comes from the bracketed name after "card N:" in the `arecord -l` output. If your device shows as `card 2: Audio [Behringer USB Audio]`, you'd use `plughw:CARD=Audio,DEV=0`.

Why `plughw:` instead of `hw:`: The `plughw:` prefix adds ALSA's conversion plugin, so if the device doesn't natively support the requested sample rate (48kHz), ALSA resamples transparently. Raw `hw:` will fail unless the device supports the exact rate.

This identifier is stable across reboots — it's tied to the device name rather than enumeration order. It only breaks if you connect a second device with the same ALSA card name (rare for USB interfaces).

At startup, the service validates the device and logs what it resolved. Check `journalctl -u audio-services` if the device isn't found.

### 6. Configure the application

Edit `config.json` (at the project root) to match your setup. The key settings to check:

- `whisper_model` — `"small"` is the default, good balance of speed and accuracy
- `server_port` — default `8080`
- `site_title` — shown on all display pages, change to reflect your church or service name
- `audio_stream_enabled` — `true` to enable live audio streaming (hearing assist)
- `audio_stream_bitrate` — Opus bitrate in bps (default 128000)

### 7. Install the systemd service

```bash
sudo ./audio_services/scripts/install-service.sh
```

This creates and enables a systemd unit that:
- Starts audio-services automatically on boot
- Reads environment from `.env` at the project root
- Runs as the `audio` user
- Restarts on failure

### 8. Start it up

```bash
sudo systemctl start audio-services
```

Check that it's running:

```bash
sudo systemctl status audio-services
journalctl -u audio-services -f
```

## Verifying the Install

1. Check the service is active: `systemctl status audio-services`
2. Open a browser to `http://audio.local:8080` — you should see the home page
3. Check audio levels at `http://audio.local:8080/status?pin=<your-pin>`
4. Speak into the mic and confirm captions appear on the display pages
5. Open `http://audio.local:8080/listen` and confirm audio playback works

## Updating After a Code Change

When you pull new code:

```bash
cd /home/audio/church-audio-services
git pull

# Only needed if dependencies changed in pyproject.toml:
source .venv/bin/activate
pip install -e . --upgrade

# Restart the service to pick up changes
sudo systemctl restart audio-services
```

## Reinstalling the Service File

If the systemd unit file needs updating (paths changed, hardening added, etc.):

```bash
sudo ./audio_services/scripts/install-service.sh
sudo systemctl restart audio-services
```

The install script is idempotent — safe to re-run anytime.

## Troubleshooting

- **Service won't start**: Check `journalctl -u audio-services -n 50` for errors
- **"ADMIN_PIN not set"**: Make sure `.env` exists at the project root and contains `ADMIN_PIN=...`
- **Audio device not found**: Verify USB interface is plugged in, run `arecord -l` to confirm the card name matches `config.json`. Check `journalctl -u audio-services` for the startup validation message.
- **Model download hangs**: First run downloads the Whisper model from HuggingFace — needs internet
- **SELinux denials**: The install script sets contexts automatically, but check `audit2why` if issues persist
