# Installation Guide

How to install (or reinstall) the audio services system on a fresh or existing machine.

## Platform

- **GPU system (primary):** Dell OptiPlex 3050 Tower, GTX 1050 Ti, Fedora 41
- **CPU-only fallback:** Any x86_64 Linux with AVX2 support (e.g., HP EliteDesk i5-8500T)

The instructions below cover the GPU path. For CPU-only, skip the NVIDIA/GPU sections and set `whisper_device` to `"cpu"` in config.json.

## Prerequisites

- Fedora 41 Server (or compatible — see note on OS choice below)
- Python 3.12
- User account for the service (default: `lscoc` or `audio`)
- USB audio interface connected to the mixer board's aux bus
- Internet connection (for initial package and model downloads)
- For GPU: NVIDIA GTX 1050 Ti (or other Pascal/newer GPU)

### OS Choice

Fedora 41 is tested and working. Key requirements for GPU support:

- GCC ≤ 14 (for CUDA toolkit compilation if needed)
- Kernel ≤ 6.x (kernel 7.x blocks executable stacks, breaking ctranslate2 3.x)
- `akmod-nvidia-470xx` available from RPM Fusion (for Pascal GPUs)
- Python 3.12 available (ctranslate2 3.24 has prebuilt wheels)

Other viable options: Ubuntu 22.04 LTS, Rocky/Alma Linux 9, Fedora 40.

**Do NOT use Fedora 44+** — kernel 7.1 blocks executable stacks (breaks ctranslate2), and GCC 16 is incompatible with CUDA 11.4's nvcc.

### System Dependencies

```bash
sudo dnf install gcc gcc-c++ python3-devel portaudio-devel libjpeg-turbo-devel alsa-utils
```

For audio stream encoding (PyAV build from source, if needed):

```bash
sudo dnf install ffmpeg-devel
```

### NVIDIA GPU Setup

#### 1. Enable RPM Fusion

```bash
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
```

#### 2. Install the 470xx proprietary driver

The GTX 1050 Ti (Pascal, GP107) requires the **470xx legacy branch**. The newer open kernel modules (595+) only support Turing and newer GPUs.

```bash
sudo dnf install akmod-nvidia-470xx xorg-x11-drv-nvidia-470xx-cuda
```

#### 3. Wait for kernel module to build

```bash
sudo akmods --force --kernels $(uname -r)
```

#### 4. Blacklist nouveau and configure initramfs

```bash
echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nouveau.conf
echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nouveau.conf
echo 'add_drivers+=" nvidia nvidia_modeset nvidia_uvm nvidia_drm "' | sudo tee /etc/dracut.conf.d/nvidia.conf
sudo dracut --force
sudo reboot
```

#### 5. Verify after reboot

```bash
nvidia-smi
```

Should show the GTX 1050 Ti, driver 470.x, CUDA 11.4.

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

**Must use Python 3.12** (ctranslate2 3.24 requires it for CUDA 11 support):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package and GPU dependencies

```bash
# Install the project
pip install -e .

# Downgrade to CUDA 11 compatible versions (required for 470xx driver)
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

The USB audio interface defaults to max capture gain, which clips. Use alsamixer to set the correct level, then persist it.

#### Disable PipeWire/WirePlumber

WirePlumber resets ALSA levels on login, overriding saved state. Disable it for the service user:

```bash
systemctl --user disable --now pipewire pipewire.socket pipewire-pulse.socket wireplumber
```

#### Pin the USB device to a stable card index

Ensure the USB audio device always gets the same card number across reboots:

```bash
sudo tee /etc/modprobe.d/alsa-cards.conf << 'EOF'
# Pin USB audio (capture device) to card 0
options snd_usb_audio index=0
# Pin Intel HDA to card 1, NVidia to card 2
options snd_hda_intel index=1,2
EOF
sudo dracut --force
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

This writes to `/var/lib/alsa/asound.state`. The `alsa-restore.service` (static unit, pulled in by `sound.target`) restores these levels on boot.

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
sudo ./audio_services/scripts/fedora/install-service.sh lscoc
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
sudo ./audio_services/scripts/fedora/install-service.sh lscoc
sudo systemctl restart audio-services
```

## Troubleshooting

### General

- **Service won't start**: Check `journalctl -u audio-services -n 50`
- **"ADMIN_PIN not set"**: Make sure `.env` exists and contains `ADMIN_PIN=...`
- **Audio device not found**: Verify USB interface is plugged in, run `arecord -l`
- **Model download hangs**: First run downloads from HuggingFace — needs internet

### GPU-specific

- **`nvidia-smi` fails**: Check `lspci | grep -i nvidia` — if card isn't visible, check 6-pin PCIe power connector (MSI Gaming cards require it even though card is <75W)
- **"not supported by open nvidia.ko"**: You have the wrong driver. Remove `akmod-nvidia` and install `akmod-nvidia-470xx`
- **"cannot enable executable stack"**: Wrong kernel or OS version. Need kernel ≤ 6.x (Fedora 41 or older)
- **"CUDA driver version is insufficient"**: ctranslate2 version mismatch. Need `ctranslate2==3.24.0` (not 4.x) for the 470 driver
- **"float16 not supported"**: Pascal GPUs don't support float16. Use `compute_type: "int8"`
- **"libcudnn_ops_infer.so.8 not found"**: Install `pip install nvidia-cudnn-cu11==8.9.6.50` and ensure `LD_LIBRARY_PATH` is set
- **nouveau still loading**: Check `lsmod | grep nouveau`. Ensure blacklist is in `/etc/modprobe.d/` and nvidia modules are in initramfs (`dracut --force`)
- **Slow first transcription (~1.4s)**: Normal — CUDA context initialization on first inference. Subsequent calls are ~420ms.

### Audio

- **`arecord -l` shows no devices**: User needs `audio` group membership
- **PipeWire/WirePlumber resetting capture gain to max**: Disable PipeWire for the service user (see step 8)
- **SELinux denials**: Install script sets contexts automatically, check `audit2why` if issues persist

## Key Version Constraints (GPU system)

| Component | Version | Why |
|-----------|---------|-----|
| NVIDIA driver | 470xx | Last branch supporting Pascal (GTX 1050 Ti) |
| CUDA (bundled) | 11.4 | Max supported by 470 driver |
| ctranslate2 | 3.24.0 | Last version with CUDA 11 runtime |
| faster-whisper | 0.10.1 | Last version compatible with ctranslate2 3.x |
| nvidia-cudnn-cu11 | 8.9.6.50 | cuDNN 8 for CUDA 11 |
| Python | 3.12 | ctranslate2 3.24 has cp312 wheels |
| Fedora | 41 | GCC 14 + kernel 6.11 (no execstack blocking) |
| compute_type | int8 | float16 not supported on Pascal |
