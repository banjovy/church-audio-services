# Installation Guide — Ubuntu 22.04 LTS

How to install the audio services system on Ubuntu 22.04 LTS.

## Platform

- **GPU system (primary):** Dell OptiPlex 3050 Tower, GTX 1050 Ti, Ubuntu 22.04 LTS
- **CPU-only fallback:** Any x86_64 Linux with AVX2 support (e.g., HP EliteDesk i5-8500T)

The instructions below cover the GPU path. For CPU-only, skip the NVIDIA/GPU sections and set `whisper_device` to `"cpu"` in config.json.

## Why Ubuntu 22.04 LTS

- 5-year support window (through April 2027, ESM through 2032)
- Kernel 5.15 HWE — stable, no execstack issues with ctranslate2
- `nvidia-driver-470` in official Ubuntu repos — no third-party repos needed
- Python 3.12 available via deadsnakes PPA
- No rolling-release breakage from kernel/GCC updates
- NVIDIA Container Toolkit has first-class support (if containers are needed later)

## Prerequisites

- Ubuntu 22.04 LTS Server (minimal install recommended)
- Python 3.12 (via deadsnakes PPA)
- User account for the service (default: `lscoc` or `audio`)
- USB audio interface connected to the mixer board's aux bus
- Internet connection (for initial package and model downloads)
- For GPU: NVIDIA GTX 1050 Ti (or other Pascal/newer GPU)

### System Dependencies

```bash
sudo apt update
sudo apt install -y build-essential python3-dev libportaudio2 portaudio19-dev \
  libjpeg-dev alsa-utils gcc g++
```

For audio stream encoding (PyAV build from source, if needed):

```bash
sudo apt install -y libavformat-dev libavcodec-dev libavutil-dev libswresample-dev
```

### Python 3.12 (deadsnakes PPA)

Ubuntu 22.04 ships Python 3.10. ctranslate2 3.24 needs 3.12:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

### NVIDIA GPU Setup

#### 1. Install the 470 driver

The GTX 1050 Ti (Pascal, GP107) requires the **470 legacy branch**. Ubuntu ships this in the official repos.

```bash
sudo apt install -y nvidia-driver-470
```

This automatically blacklists nouveau and sets up the kernel module (DKMS).

#### 2. Reboot

```bash
sudo reboot
```

#### 3. Verify after reboot

```bash
nvidia-smi
```

Should show the GTX 1050 Ti, driver 470.x, CUDA 11.4.

**Note:** If `nvidia-smi` fails, check that Secure Boot is disabled in BIOS, or enroll the MOK key that DKMS generates during install.

### mDNS (optional but recommended)

Avahi lets devices find the server by hostname (e.g., `audio.local`) without knowing the IP:

```bash
sudo apt install -y avahi-daemon
sudo systemctl enable --now avahi-daemon
```

To set the hostname:

```bash
sudo hostnamectl set-hostname audio
```

### Firewall

Ubuntu uses `ufw` by default:

```bash
sudo ufw allow 8080/tcp
sudo ufw allow 5353/udp  # mDNS
sudo ufw enable
```

If `ufw` is not active and you don't need a firewall on the LAN, skip this.

### Service User Account

If using a dedicated user (not your personal account):

```bash
sudo useradd -m -s /bin/bash audio
sudo usermod -aG audio audio
```

The `audio` group membership is required for non-root access to ALSA sound devices.

## Installation

### 1. Clone the repository

```bash
cd ~
git clone <repo-url> church-audio-services
cd church-audio-services
```

### 2. Create the Python virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package and GPU dependencies

```bash
# Install the project
pip install -e .

# Downgrade to CUDA 11 compatible versions (required for 470 driver)
pip install ctranslate2==3.24.0
pip install faster-whisper==0.10.1 --no-deps
pip install av huggingface-hub tokenizers onnxruntime tqdm

# Install cuDNN (bundled in venv, no system install needed)
pip install nvidia-cudnn-cu11==8.9.6.50
```

**Why the version pinning:**
- `ctranslate2==3.24.0` — last version with CUDA 11 support (bundles CUDA 11 runtime)
- `faster-whisper==0.10.1` — last version compatible with ctranslate2 3.x
- `--no-deps` on faster-whisper avoids it pulling ctranslate2 4.x (which needs CUDA 12)
- `nvidia-cudnn-cu11` — cuDNN 8.x for CUDA 11, needed for inference

#### CPU-only install (no GPU)

```bash
pip install -e .
```

No version pinning needed — the latest faster-whisper + ctranslate2 work fine on CPU.

### 4. Configure cuDNN library path

Add to `~/.bashrc` so the cuDNN libraries are found at runtime:

```bash
echo 'export LD_LIBRARY_PATH=$HOME/church-audio-services/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### 5. Verify GPU inference

```bash
source .venv/bin/activate
python -c "
import faster_whisper
model = faster_whisper.WhisperModel('small.en', device='cuda', compute_type='int8')
print('GPU model loaded successfully')
"
```

**Note:** `float16` compute type does NOT work on Pascal GPUs (GTX 1050 Ti). Use `int8`.

### 6. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your admin PIN:

```
ADMIN_PIN=123456
```

### 7. Configure the audio input device

Identify your USB audio interface:

```bash
arecord -l
```

Set the ALSA identifier in `config.json`:

```json
"audio": {
  "input_device": "plughw:CARD=Device,DEV=0"
}
```

### 8. Set and persist capture gain

The USB audio interface defaults to max capture gain, which clips.

#### Disable PipeWire/PulseAudio (if present)

Ubuntu 22.04 Server minimal does not install PipeWire or PulseAudio. If you installed a desktop environment or they are present, disable them:

```bash
systemctl --user disable --now pipewire pipewire.socket pipewire-pulse.socket wireplumber
```

Or for PulseAudio:

```bash
systemctl --user disable --now pulseaudio pulseaudio.socket
```

On a minimal server install, skip this step.

#### Pin the USB device to a stable card index

```bash
sudo tee /etc/modprobe.d/alsa-cards.conf << 'EOF'
# Pin USB audio (capture device) to card 0
options snd_usb_audio index=0
# Pin Intel HDA to card 1, NVidia to card 2
options snd_hda_intel index=1,2
EOF
sudo update-initramfs -u
```

Reboot and verify with `cat /proc/asound/cards`.

#### Set and store levels

```bash
alsamixer -c 0
```

Set the capture level (typically 60–70% to avoid clipping), then save:

```bash
sudo alsactl store
```

This writes to `/var/lib/alsa/asound.state`. The `alsa-restore.service` restores these levels on boot.

#### Verify after reboot

```bash
amixer -c 0 get Mic
```

Confirm the level matches what you stored, not max.

### 9. Configure GPU settings

In `config.json`, set:

```json
"whisper_device": "cuda",
"whisper_compute_type": "int8"
```

For CPU-only:

```json
"whisper_device": "cpu",
"whisper_compute_type": "int8"
```

### 10. Install the systemd service

```bash
sudo ./audio_services/scripts/ubuntu/install-service.sh lscoc
```

(Replace `lscoc` with your username if different.)

The service unit includes `LD_LIBRARY_PATH` for cuDNN automatically.

### 11. Start it up

```bash
sudo systemctl start audio-services
sudo systemctl status audio-services
journalctl -u audio-services -f
```

## Verifying the Install

1. Check the service is active: `systemctl status audio-services`
2. Open a browser to `http://audio.local:8080` — you should see the home page
3. Check audio levels at `http://audio.local:8080/status?pin=<your-pin>`
4. Speak into the mic and confirm captions appear on the display pages
5. Open `http://audio.local:8080/listen` and confirm audio playback works
6. Check logs for GPU confirmation: `journalctl -u audio-services | grep "loaded successfully on cuda"`

## Updating After a Code Change

```bash
cd ~/church-audio-services
git pull
source .venv/bin/activate
pip install -e . --upgrade
sudo systemctl restart audio-services
```

## Reinstalling the Service File

```bash
sudo ./audio_services/scripts/ubuntu/install-service.sh lscoc
sudo systemctl restart audio-services
```

## Troubleshooting

### General

- **Service won't start**: Check `journalctl -u audio-services -n 50`
- **"ADMIN_PIN not set"**: Make sure `.env` exists and contains `ADMIN_PIN=...`
- **Audio device not found**: Verify USB interface is plugged in, run `arecord -l`
- **Model download hangs**: First run downloads from HuggingFace — needs internet

### GPU-specific

- **`nvidia-smi` fails**: Check Secure Boot status. Either disable it in BIOS or enroll the DKMS MOK key (`sudo mokutil --import /var/lib/shim-signed/mok/MOK.der`)
- **"CUDA driver version is insufficient"**: ctranslate2 version mismatch. Need `ctranslate2==3.24.0` (not 4.x) for the 470 driver
- **"float16 not supported"**: Pascal GPUs don't support float16. Use `compute_type: "int8"`
- **"libcudnn_ops_infer.so.8 not found"**: Install `pip install nvidia-cudnn-cu11==8.9.6.50` and ensure `LD_LIBRARY_PATH` is set
- **nouveau still loading**: `sudo lsmod | grep nouveau` — the nvidia-driver-470 package should blacklist it automatically. If not: `echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nouveau.conf && sudo update-initramfs -u && sudo reboot`
- **Slow first transcription (~1.4s)**: Normal — CUDA context initialization on first inference. Subsequent calls are ~420ms.

### Audio

- **`arecord -l` shows no devices**: User needs `audio` group membership (`sudo usermod -aG audio $USER`, then re-login)
- **PipeWire/PulseAudio resetting capture gain**: Disable for the service user (see step 8)
- **Card index changes between reboots**: Verify `/etc/modprobe.d/alsa-cards.conf` exists and run `sudo update-initramfs -u`

## Key Differences from Fedora Install

| Area | Fedora 41 | Ubuntu 22.04 LTS |
|------|-----------|------------------|
| Package manager | dnf | apt |
| NVIDIA driver source | RPM Fusion (`akmod-nvidia-470xx`) | Official repos (`nvidia-driver-470`) |
| Kernel module build | akmods | DKMS (automatic) |
| Initramfs rebuild | `dracut --force` | `update-initramfs -u` |
| Python 3.12 | System default | deadsnakes PPA |
| Firewall | firewalld (`firewall-cmd`) | ufw |
| Kernel | 6.11 (rolling) | 5.15 HWE (stable) |
| SELinux | Enforcing by default | Not present (AppArmor instead) |
| Audio daemon | PipeWire (default) | None on server minimal |

## Key Version Constraints (GPU system)

| Component | Version | Why |
|-----------|---------|-----|
| NVIDIA driver | 470 | Last branch supporting Pascal (GTX 1050 Ti) |
| CUDA (bundled) | 11.4 | Max supported by 470 driver |
| ctranslate2 | 3.24.0 | Last version with CUDA 11 runtime |
| faster-whisper | 0.10.1 | Last version compatible with ctranslate2 3.x |
| nvidia-cudnn-cu11 | 8.9.6.50 | cuDNN 8 for CUDA 11 |
| Python | 3.12 | ctranslate2 3.24 has cp312 wheels |
| Ubuntu | 22.04 LTS | Kernel 5.15 HWE, stable LTS, driver in repos |
| compute_type | int8 | float16 not supported on Pascal |
