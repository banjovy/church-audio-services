# Audio Troubleshooting Guide

This guide covers diagnosing and resolving USB audio device issues on Fedora Linux.

---

## 1. Verify USB Device Detection

```bash
lsusb
```

Look for your device (e.g., `Generalplus Technology Inc. Usb Audio Device`). If it doesn't appear, try a different USB port or cable.

---

## 2. Load the Kernel Audio Driver

Check if the USB audio kernel module is loaded:

```bash
lsmod | grep snd_usb_audio
```

If not listed, load it manually:

```bash
sudo modprobe snd-usb-audio
```

To make it persist across reboots:

```bash
echo "snd-usb-audio" | sudo tee /etc/modules-load.d/snd-usb-audio.conf
```

---

## 3. Verify the System Sees the Audio Device

```bash
cat /proc/asound/cards
```

You should see your USB device listed (e.g., card 1). If not, check `dmesg` for errors:

```bash
dmesg | grep -i audio
dmesg | grep snd
```

---

## 4. List Capture Devices

```bash
arecord -l
```

This requires `alsa-utils`:

```bash
sudo dnf install alsa-utils
```

If `arecord -l` shows "no soundcards found" but `/proc/asound/cards` lists the device, it's a permissions issue (see step 5).

---

## 5. Fix Permissions

Add your user to the `audio` group:

```bash
sudo usermod -aG audio $USER
```

Log out and back in for this to take effect. Verify with:

```bash
groups
```

---

## 6. Check Supported Sample Rates

USB audio devices (especially cheap ones) often only support 44100 or 48000 Hz — not 16000 Hz.

```bash
cat /proc/asound/Device/stream0
```

Look for the "Rates:" line under the Capture section.

### Fix

Update `config.json` to use a supported rate:

```json
"audio": {
  "sample_rate": 48000
}
```

The system automatically resamples to 16kHz for Whisper.

---

## 7. Test Recording

Record a 5-second test clip. Replace `hw:1,0` with your card and device number from `arecord -l`:

```bash
arecord -D hw:1,0 -f S16_LE -r 48000 -c 1 -d 5 test.wav
```

If you get "Invalid sample rate", try other rates:

```bash
arecord -D hw:1,0 -f S16_LE -r 44100 -c 1 -d 5 test.wav
```

Play it back:

```bash
aplay test.wav
```

### Common arecord errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Device or resource busy` | Another process has the device open | Stop PipeWire/PulseAudio: `systemctl --user stop pipewire` |
| `Invalid sample rate` | Device doesn't support that rate | Check supported rates (step 6) |
| `No such device` | Wrong card/device number | Re-check `arecord -l` |
| `Permission denied` | Not in audio group | See step 5 |

### Bypassing PipeWire/PulseAudio

If `hw:1,0` gives "device busy", PipeWire may have exclusive access. Either stop it temporarily:

```bash
systemctl --user stop pipewire.socket pipewire.service
```

Or use the PipeWire/PulseAudio device name instead:

```bash
pactl list sources short
parecord --device=<source_name> --rate=48000 --channels=1 --format=s16le test.raw
```

---

## 8. Adjust Microphone Gain

Open the ALSA mixer for your USB device (card 1):

```bash
alsamixer -c 1
```

- Press F4 to switch to Capture controls
- Use arrow keys to adjust the mic gain
- Press Space to toggle capture on/off if muted

Alternatively, set gain via command line:

```bash
amixer -c 1 sset 'Mic' 80%
```

List available controls:

```bash
amixer -c 1 contents
```

---

## 9. Install PortAudio

`sounddevice` depends on PortAudio.

```bash
sudo dnf install portaudio-devel
```

If you have issues with PortAudio not finding devices that ALSA sees:

```bash
sudo dnf reinstall portaudio portaudio-devel
```

---

## 10. Test with the Application

### Using a known-good audio file

```bash
python -m captioning.main --file test.wav --no-realtime
```

If this produces valid captions, live capture quality is the issue.

### Using live capture

```bash
python -m captioning.main --model tiny
```

Watch the logs for:
- Audio level (dB) — should be above -40 dB when speaking
- `[...]` means audio was detected but transcription failed or had low confidence

---

## 11. Debug Transcription Confidence

If you're getting `[...]` consistently, Whisper is detecting speech but can't decode it. Possible causes:

- Audio too quiet — boost gain (see step 8)
- Audio too noisy — electrical interference from USB, try a different port
- Resampling issues — verify scipy is installed: `pip install scipy`
- Wrong channel count — some USB devices are stereo even with a mono mic

---

## 12. Verify the Full Audio Pipeline

Quick Python test to confirm sounddevice sees the device and can capture:

```python
import sounddevice as sd
import numpy as np

print(sd.query_devices())

# Record 3 seconds from default device at 48kHz
audio = sd.rec(int(3 * 48000), samplerate=48000, channels=1, dtype='float32')
sd.wait()

peak_db = 20 * np.log10(np.max(np.abs(audio)) + 1e-10)
print(f"Peak level: {peak_db:.1f} dB")

if peak_db < -50:
    print("WARNING: Signal is very weak. Check mic gain.")
elif peak_db > -5:
    print("WARNING: Signal may be clipping. Reduce gain.")
else:
    print("Level looks reasonable.")
```

---

## 13. Specifying the Device in config.json

If the system default input isn't your USB device, specify it explicitly:

```json
"audio": {
  "input_device": "Usb Audio Device"
}
```

`sounddevice` accepts a substring match on the device name. Find the exact name with:

```python
import sounddevice as sd
print(sd.query_devices())
```

Set `input_device` to `null` to use the system default.

---

## Summary Checklist

1. [ ] USB device visible (`lsusb`)
2. [ ] Audio driver loaded (`snd-usb-audio`)
3. [ ] Device listed as audio card (`/proc/asound/cards`)
4. [ ] Permissions correct (`audio` group)
5. [ ] Capture device listed (`arecord -l` / `sounddevice.query_devices()`)
6. [ ] Sample rate matches device capabilities
7. [ ] Test recording produces audible audio
8. [ ] Mic gain set appropriately
9. [ ] PortAudio installed
10. [ ] `sounddevice.query_devices()` lists the device
11. [ ] `captioning --file test.wav` produces captions
12. [ ] Live capture produces captions
