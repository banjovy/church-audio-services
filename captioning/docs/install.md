# Captioning — Installation Guide

How to install (or reinstall) the captioning system on a fresh or existing machine.

## Prerequisites

- Fedora Linux v44 (tested on HP EliteDesk 800 G4 Mini, i5-8500T)
- User account for the service (default: `captioning`) — see below
- USB audio interface connected to the mixer board's aux bus
- Internet connection (for initial package and model downloads)

### System Dependencies

Install these once:

```bash
sudo dnf install gcc gcc-c++ python3-devel portaudio-devel libjpeg-turbo-devel alsa-utils
```

These are needed to compile native extensions for audio capture, Whisper, and image processing. `alsa-utils` provides `arecord`, `aplay`, and `amixer` for audio troubleshooting.

### mDNS (optional but recommended)

Avahi lets devices find the server by hostname (e.g. `captions.local`) without knowing the IP:

```bash
sudo dnf install avahi
sudo systemctl enable --now avahi-daemon
```

### Firewall

Open the captioning port and mDNS so devices on the LAN can connect:

```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-service=mdns
sudo firewall-cmd --reload
```

### Service User Account

Create a dedicated user to run the captioning service:

```bash
sudo useradd -m -s /bin/bash captioning
```

This keeps the service isolated from other accounts on the system. The install script expects a home directory at `/home/captioning`.

## Installation

### 1. Clone the repository

```bash
cd /home/captioning
git clone <repo-url> church-captioning
cd church-captioning
```

Or if reinstalling on a machine that already has the repo:

```bash
cd /home/captioning/church-captioning
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

### 3. Install the captioning package

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

### 5. Configure the application

Edit `config.json` (at the project root) to match your setup. The key settings to check:

- `audio.input_device` — set to your USB interface name (run `python -c "import sounddevice; print(sounddevice.query_devices())"` to find it)
- `whisper_model` — `"small"` is the default, good balance of speed and accuracy
- `server_port` — default `8080`
- `site_title` — shown on all display pages, change this to reflect your church or service name

### 6. Install the systemd service

```bash
sudo ./captioning/scripts/install-service.sh
```

This creates and enables a systemd unit that:
- Starts captioning automatically on boot
- Reads environment from `.env` at the project root
- Runs as the `captioning` user
- Restarts on failure

### 7. Start it up

```bash
sudo systemctl start captioning
```

Check that it's running:

```bash
sudo systemctl status captioning
journalctl -u captioning -f
```

## Verifying the Install

1. Check the service is active: `systemctl status captioning`
2. Open a browser to `http://<hostname>.local:8080` — you should see the home page
3. Check audio levels at `http://<hostname>.local:8080/status?pin=<your-pin>`
4. Speak into the mic and confirm captions appear on the display pages

## Updating After a Code Change

When you pull new code:

```bash
cd /home/captioning/church-captioning
git pull

# Only needed if dependencies changed in pyproject.toml:
source .venv/bin/activate
pip install -e . --upgrade

# Restart the service to pick up changes
sudo systemctl restart captioning
```

## Reinstalling the Service File

If the systemd unit file needs updating (paths changed, hardening added, etc.):

```bash
sudo ./captioning/scripts/install-service.sh
sudo systemctl restart captioning
```

The install script is idempotent — safe to re-run anytime.

## Troubleshooting

- **Service won't start**: Check `journalctl -u captioning -n 50` for errors
- **"ADMIN_PIN not set"**: Make sure `.env` exists at the project root and contains `ADMIN_PIN=...`
- **Audio device not found**: Verify USB interface is plugged in, check with `sounddevice.query_devices()`
- **Model download hangs**: First run downloads the Whisper model from HuggingFace — needs internet
- **SELinux denials**: The install script sets contexts automatically, but check `audit2why` if issues persist
