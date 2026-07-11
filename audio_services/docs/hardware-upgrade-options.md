# Hardware Upgrade Options for Lower Latency

Goal: 1-3s end-to-end latency with `small` or `medium` model for high accuracy.

Previous baseline: i5-8500T (CPU) with `small` model = 1.8x realtime (~2.2s transcription per 4s chunk, ~6s end-to-end).

**Current system: Dell OptiPlex 3050 Tower + GTX 1050 Ti = ~420ms per chunk, ~2.5s end-to-end. ✅ ACHIEVED.**

## GPU Path

Best performance per dollar. Whisper is dramatically faster on NVIDIA GPUs.

| GPU | Approx Cost (used) | small model speed | Notes |
|-----|-------------------|-------------------|-------|
| GTX 1050 Ti | $80-120 | 5-10x realtime | Budget option, still great |
| GTX 1650 | $100-150 | 10-15x realtime | Sweet spot for value |
| RTX 3060 | $200-250 | 15-30x realtime | Could run `medium` easily |

- Transcription of a 3s chunk in ~100-200ms with `small` on any of these.
- Could drop `min_chunk_seconds` to 1.5-2s and still get accurate results.
- `medium` model becomes viable for even better accuracy.
- Downside: requires PCIe slot (EliteDesk Mini doesn't have one). Would need a different form factor machine or an eGPU enclosure.
- Requires CUDA drivers and cuBLAS/cuDNN libraries.

## Better CPU Path (staying compact/mini PC)

| CPU | Form Factor | Approx Cost | Expected speed with `small` |
|-----|-------------|-------------|---------------------------|
| Intel i7-12700T | Mini PC | $300-400 | 3-4x realtime |
| Intel i5-13500T | Mini PC | $300-400 | 3-4x realtime |
| AMD Ryzen 7 5700G | Mini PC (Beelink, MinisForum) | $250-350 | 3-4x realtime |
| AMD Ryzen 7 7735HS | Mini PC | $350-450 | 3-5x realtime |

- 2-3x faster than i5-8500T due to more cores + efficiency cores + newer architecture.
- Would allow `small` model with 2s chunks at ~1s transcription = 3s total end-to-end.
- Same form factor as current EliteDesk — compact, low power, silent.
- No GPU driver complexity.

## Recommendation

For a church AV closet setup:

- **Best value**: Mini PC with Ryzen 7 or i7-12th/13th gen ($300-400). Gets you to ~3s latency with `small` on CPU. Clean, simple, low power, silent.
- **Maximum quality**: Machine with PCIe slot + GTX 1650 or RTX 3060 ($400-600 total). Sub-2s latency possible, `medium` model viable. More complex setup (drivers, cooling, larger form factor).
- **Budget GPU option**: Used SFF desktop (Dell OptiPlex, HP ProDesk) with low-profile GTX 1650 ($200-300 total). Good middle ground.

## SFF System Notes for Budget GPU Path

**Good candidate SFF systems (used, $80-150):**

- Dell OptiPlex 3050/5050/7050 SFF (6th/7th gen Intel)
- HP ProDesk 400/600 G3/G4/G6 SFF
- Lenovo ThinkCentre M710s/M720s SFF

**What to verify:**

- Must be SFF chassis (not USFF/Micro/Mini) — SFF has a low-profile PCIe x16 slot.
- GTX 1050 Ti needs a low-profile card (MSI and ZOTAC make LP versions). Check single vs dual slot clearance.
- 1050 Ti draws under 75W, no PCIe power connector needed — works with SFF PSUs (180-240W).
- 8GB RAM is sufficient since Whisper runs on GPU VRAM.
- Watch for BIOS PCIe whitelists (some HP machines). Dell OptiPlex is generally safest for third-party GPUs.

**Specific candidate: HP ProDesk 400 G6 SFF**

- i5-9500 (6-core, higher clocks than current 8500T)
- Low-profile PCIe x16 slot confirmed
- 180W or 310W PSU depending on config (both fine for 75W 1050 Ti)
- 9th gen Intel — no issues with modern Linux
- 400-series ProDesks generally less restrictive on PCIe whitelist than EliteDesk line
- Worth confirming others have used non-HP GPUs without BIOS complaints

## Planned Build

**System:** Dell OptiPlex 3050 Tower Desktop PC, Intel Core i5-7500, 8GB RAM, 256GB SSD, Windows 11 Pro

**GPU:** MSI Gaming GeForce GTX 1050 Ti 4GB GDDR5 128-bit, TORX 2.0 Fan, DirectX 12, HDCP Support

**Why this works:**

- i5-7500 is sufficient — Whisper runs on the GPU, CPU just handles audio capture and the web server
- 8GB RAM is enough since model weights live in 4GB VRAM
- 256GB SSD is more than needed (OS + dependencies + Whisper models < 20GB)
- Tower chassis fits the full-size MSI card with no clearance issues
- 1050 Ti draws 75W, no PCIe power connector needed — works with the OptiPlex 3050's stock PSU
- No PCIe whitelist issues on Dell OptiPlex
- 7th gen Intel has solid Linux support (will wipe Windows for Fedora/Ubuntu)

**Expected performance:**

- `small` model: ~100-200ms per 3s chunk (5-10x realtime)
- `medium` model: viable at ~300-500ms per chunk
- End-to-end latency: ~2-3s with `small`, ~3-4s with `medium`
- Can reduce `min_chunk_seconds` to 1.5-2s for tighter responsiveness

**Setup requirements:**

- Install Linux (Fedora or Ubuntu)
- NVIDIA proprietary driver
- CUDA toolkit
- `pip install openai-whisper` or `faster-whisper` with CUDA support

**Fedora NVIDIA driver setup:**

```bash
# Enable RPM Fusion repos
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

# Install the driver (builds kernel module automatically on kernel updates)
sudo dnf install akmod-nvidia

# Install CUDA runtime (needed for Whisper GPU inference)
sudo dnf install xorg-x11-drv-nvidia-cuda

# Reboot, then verify
nvidia-smi
```

**Notes:**

- `akmod-nvidia` auto-rebuilds the kernel module on updates — avoids black screen after `dnf upgrade`
- GTX 1050 Ti supports CUDA 12.x with current drivers (what PyTorch/Whisper expects)
- Disable Secure Boot in BIOS — `akmod-nvidia` won't load without signing the kernel module, and this is a dedicated box so no need for Secure Boot

**Estimated total cost:** ~$300 (system + GPU)

---

## Full-Size Tower Path (cheapest GPU option)

If size isn't a constraint, a standard tower chassis is easier and cheaper — no low-profile card requirement, more supply of both systems and GPUs.

**Tower systems (used, $50-100):**

- Dell OptiPlex 3050/5050/7050 Tower
- HP ProDesk/EliteDesk Tower
- Lenovo ThinkCentre Tower
- Any 6th gen+ i5 or i7 is fine — CPU barely matters since Whisper runs on the GPU

**What to look for:**

- At least 300W PSU (most Dell/HP towers have this)
- PCIe x16 slot (all of them do)
- 8GB RAM minimum
- Full-size cards fit with no clearance issues

**GPU: full-size GTX 1050 Ti ($60-100 used)**

- MSI, EVGA, Gigabyte, ASUS — all widely available full-size
- Much more common and cheaper than low-profile variants
- Still 75W, no PCIe power connector needed
- Avoid no-name brands (AISURIX, etc.) — risk of fake/rebadged chips

**Estimated total: $110-200**

Tradeoff vs SFF: bigger box in the AV closet, but significantly cheaper and easier to source parts.

---

## Build Progress

**System:** Dell OptiPlex 3050 Tower, i5-7500, 8GB RAM, 256GB NVMe SSD — ✅ working  
**GPU:** MSI GTX 1050 Ti GAMING X 4GB — ✅ working (required SATA-to-6-pin power adapter)  
**OS:** Fedora 41 Server — ✅ working  
**Driver:** akmod-nvidia-470xx (470.256.02) — ✅ working  
**CUDA:** 11.4 (bundled via ctranslate2 3.24.0 pip wheel) — ✅ working  
**Python:** 3.12 — ✅ working  
**Inference:** small.en, device=cuda, compute_type=int8 — ✅ working  
**Performance:** ~420ms per chunk (4.7-9.4x realtime), ~2.5s end-to-end latency

### Benchmarks (steady-state, after warmup)

| Model | Chunk | Avg Time | Realtime Factor | End-to-end Latency |
|-------|-------|----------|-----------------|-------------------|
| small.en | 2s | 422ms | 4.7x | ~2.5s |
| small.en | 3s | 428ms | 7.0x | ~3.4s |
| small.en | 4s | 427ms | 9.4x | ~4.4s |
| medium.en | 3s | 1152ms | 2.6x | ~4.2s |

- small.en processing time is ~constant (~420ms) regardless of chunk length
- medium.en is viable but tighter — use if small.en accuracy is insufficient
- First inference after cold start: ~1.4s (CUDA context init, one-time cost)
- float16 NOT supported on Pascal — must use int8

### Lessons Learned from Fedora 44 Attempt

**Problem 1: MSI Gaming 1050 Ti not detected on PCIe bus**
- Root cause: MSI Gaming variant has a 6-pin PCIe power connector that must be plugged in, even though the card draws <75W. Card won't enumerate without supplementary power.
- Fix: SATA 15-pin to 6-pin PCIe power adapter. NVMe is onboard so SATA power connectors are free.

**Problem 2: NVIDIA 595.x driver (open kernel modules) doesn't support Pascal**
- The `akmod-nvidia` package on Fedora 44 installs driver 595.x which is the **open kernel module** variant.
- Open modules require GSP (GPU System Processor) — only available on Turing (RTX 2000+) and newer.
- GTX 1050 Ti (GP107, Pascal) has no GSP. Error: "not supported by open nvidia.ko because it does not include the required GPU System Processor (GSP)"
- Fix: Use `akmod-nvidia-470xx` — the proprietary (closed-source) legacy branch that supports Pascal.

**Problem 3: ctranslate2 3.x requires executable stack — blocked by kernel 7.1**
- Fedora 44's kernel 7.1.x hardened against executable stacks at the kernel level (not just SELinux).
- ctranslate2 3.24.0 (CUDA 11 compatible) requires execstack → `ImportError: cannot enable executable stack`
- Not fixable with `setenforce 0`, `execstack -c`, or sysctl. Kernel-level block.
- ctranslate2 4.x doesn't need execstack but requires CUDA 12 (needs driver 525+, incompatible with 470xx).

**Problem 4: CUDA 11.4 nvcc incompatible with GCC 16 (Fedora 44)**
- CUDA 11.4 officially supports up to GCC 11.
- GCC 16's C++ headers use features nvcc can't parse (even with `--allow-unsupported-compiler`).
- No older GCC packages available on Fedora 44 (only gcc15 compat, which also fails).
- whisper.cpp CUDA build impossible on F44.

**Problem 5: float16 compute type not supported on Pascal**
- GTX 1050 Ti (compute capability 6.1) doesn't support efficient float16.
- Error: "Requested float16 compute type, but the target device or backend do not support efficient float16 computation"
- Fix: Use `compute_type="int8"` — works great, fast inference, fits in 4GB VRAM.

### Why Fedora 41 (chosen solution)

- GCC 14.2 — compatible with CUDA 11.4 if nvcc is ever needed
- Kernel 6.11 — no execstack blocking (ctranslate2 3.24 loads fine)
- Python 3.12 native — ctranslate2 3.24 has prebuilt wheels
- `akmod-nvidia-470xx` available from RPM Fusion
- Fedora 41 ISO: `https://archives.fedoraproject.org/pub/archive/fedora/linux/releases/41/Server/x86_64/iso/`
- Note: F41 is EOL (Dec 2025) — acceptable for a dedicated appliance

### Final Working Setup (reproducible)

```bash
# 1. Install Fedora 41 Server, expand root LV to 50G+
lvextend -L 50G /dev/<vg>/root
xfs_growfs /

# 2. Update system
sudo dnf update

# 3. Enable RPM Fusion
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

# 4. Install NVIDIA 470xx driver
sudo dnf install akmod-nvidia-470xx xorg-x11-drv-nvidia-470xx-cuda
sudo akmods --force --kernels $(uname -r)

# 5. Blacklist nouveau, add nvidia to initramfs
echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nouveau.conf
echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nouveau.conf
echo 'add_drivers+=" nvidia nvidia_modeset nvidia_uvm nvidia_drm "' | sudo tee /etc/dracut.conf.d/nvidia.conf
sudo dracut --force
sudo reboot

# 6. Verify GPU
nvidia-smi  # Should show GTX 1050 Ti, driver 470.x, CUDA 11.4

# 7. Install system deps
sudo dnf install gcc gcc-c++ python3-devel portaudio-devel libjpeg-turbo-devel alsa-utils ffmpeg-devel avahi

# 8. Clone repo and create venv
cd ~
git clone <repo-url> church-audio-services
cd church-audio-services
python3.12 -m venv .venv
source .venv/bin/activate

# 9. Install Python packages
pip install -e .
pip install ctranslate2==3.24.0
pip install faster-whisper==0.10.1 --no-deps
pip install av huggingface-hub tokenizers onnxruntime tqdm
pip install nvidia-cudnn-cu11==8.9.6.50

# 10. Configure cuDNN library path
echo 'export LD_LIBRARY_PATH=$HOME/church-audio-services/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# 11. Verify GPU inference
python -c "
import faster_whisper
model = faster_whisper.WhisperModel('small.en', device='cuda', compute_type='int8')
print('GPU model loaded successfully')
"

# 12. Configure .env and config.json, install systemd service
cp .env.example .env  # Edit with ADMIN_PIN
sudo ./audio_services/scripts/install-service.sh $(whoami)
sudo systemctl start audio-services
```

### CUDA Toolkit (NOT required for faster-whisper path)

ctranslate2 3.24.0 bundles CUDA 11 runtime libraries. The CUDA toolkit (nvcc) is only needed if building whisper.cpp from source. For the faster-whisper Python path, you only need:
- NVIDIA driver (470xx)
- ctranslate2 3.24.0 (pip wheel includes CUDA runtime)
- nvidia-cudnn-cu11 (pip wheel includes cuDNN)

