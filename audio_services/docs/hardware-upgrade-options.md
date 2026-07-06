# Hardware Upgrade Options for Lower Latency

Goal: 1-3s end-to-end latency with `small` or `medium` model for high accuracy.

Current baseline: i5-8500T with `small` model = 1.8x realtime (~2.2s transcription per 4s chunk, ~6s end-to-end).

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
