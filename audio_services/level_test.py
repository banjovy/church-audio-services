"""Audio input level test utility.

Opens the configured (or specified) audio input device and displays a
real-time level meter with statistics.  Use this to set optimal input
gain before streaming.

Usage:
    audio-services --level-test [--duration 10] [--device <device>]
"""

import sys
import time

import numpy as np
import sounddevice as sd

from .audio import validate_audio_device
from .config import AppConfig, AudioConfig


def _db(peak: float) -> float:
    return 20 * np.log10(peak + 1e-10)


def _meter_bar(db: float, width: int = 50) -> str:
    """Render a horizontal level bar. Range: -60 dB to 0 dB."""
    clamped = max(-60.0, min(0.0, db))
    filled = int((clamped + 60) / 60 * width)
    bar = "█" * filled + "░" * (width - filled)
    # Add markers for key thresholds
    if db > -3:
        return f"\033[91m{bar}\033[0m"  # Red — clipping risk
    elif db > -12:
        return f"\033[93m{bar}\033[0m"  # Yellow — hot
    elif db > -40:
        return f"\033[92m{bar}\033[0m"  # Green — good
    else:
        return f"\033[90m{bar}\033[0m"  # Gray — too quiet


def run_level_test(config: AppConfig, duration: float = 10.0, device_override=None):
    """Run an interactive level test on the audio input."""
    audio_cfg = config.audio

    # Resolve device
    device = device_override if device_override is not None else audio_cfg.input_device
    try:
        resolved = validate_audio_device(device)
    except RuntimeError as e:
        print(f"\033[91mError:\033[0m {e}", file=sys.stderr)
        sys.exit(1)

    # Query device info for display
    if resolved is None:
        info = sd.query_devices(kind="input")
    else:
        info = sd.query_devices(resolved)
    device_name = info["name"]
    sample_rate = int(info["default_samplerate"])

    print(f"\n\033[1mAudio Level Test\033[0m")
    print(f"  Device:      {device_name}")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  Duration:    {duration:.0f}s")
    print(f"\n  Speak normally into the headset mic.")
    print(f"  Target range: \033[92m-24 to -12 dBFS\033[0m (green)")
    print(f"  Legend: \033[90m░ too quiet\033[0m  \033[92m█ good\033[0m  \033[93m█ hot\033[0m  \033[91m█ clip risk\033[0m")
    print()

    # Statistics accumulators
    peaks: list[float] = []
    rms_values: list[float] = []
    noise_samples: list[float] = []  # samples from the first 0.5s (assumed quiet)

    start_time = time.time()
    noise_window = 0.5  # seconds to measure noise floor at start
    noise_collected = False

    def callback(indata, frames, time_info, status):
        nonlocal noise_collected
        if status:
            pass  # Ignore overflow during test
        audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()
        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(audio ** 2)))
        peaks.append(peak)
        rms_values.append(rms)

        elapsed = time.time() - start_time
        if elapsed < noise_window:
            noise_samples.append(rms)

    try:
        stream = sd.InputStream(
            device=resolved,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=2048,
            callback=callback,
        )
        stream.start()
    except Exception as e:
        print(f"\033[91mFailed to open audio device:\033[0m {e}", file=sys.stderr)
        sys.exit(1)

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break

            # Display current level
            if peaks:
                current_peak = peaks[-1]
                current_db = _db(current_peak)
                bar = _meter_bar(current_db)
                remaining = duration - elapsed
                sys.stdout.write(
                    f"\r  {bar} {current_db:+6.1f} dBFS  [{remaining:4.1f}s] "
                )
                sys.stdout.flush()

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        stream.close()

    # Compute summary statistics
    print("\n")
    if not peaks:
        print("  No audio captured.")
        return

    max_peak_db = _db(max(peaks))
    avg_rms_db = _db(np.mean(rms_values))
    noise_floor_db = _db(np.mean(noise_samples)) if noise_samples else -100.0

    # Speech RMS: frames above noise floor + 10 dB
    speech_threshold = noise_floor_db + 10
    speech_rms = [r for r in rms_values if _db(r) > speech_threshold]
    avg_speech_db = _db(np.mean(speech_rms)) if speech_rms else avg_rms_db

    print(f"\033[1m  ── Results ──\033[0m")
    print(f"  Peak level:      {max_peak_db:+.1f} dBFS")
    print(f"  Avg speech RMS:  {avg_speech_db:+.1f} dBFS")
    print(f"  Noise floor:     {noise_floor_db:+.1f} dBFS")
    print(f"  SNR estimate:    {avg_speech_db - noise_floor_db:.0f} dB")
    print()

    # Recommendation
    if max_peak_db > -1:
        print(f"  \033[91m⚠ CLIPPING — reduce gain on mixer/interface\033[0m")
    elif avg_speech_db > -6:
        print(f"  \033[93m⚠ HOT — speech is loud, minor gain reduction recommended\033[0m")
    elif avg_speech_db > -24:
        print(f"  \033[92m✓ GOOD — input level is in the optimal range\033[0m")
    elif avg_speech_db > -36:
        print(f"  \033[93m⚠ LOW — increase gain on mixer/interface\033[0m")
    else:
        print(f"  \033[91m⚠ VERY LOW — significantly increase gain or check mic connection\033[0m")

    if noise_floor_db > -40:
        print(f"  \033[93m⚠ NOISE — floor is high ({noise_floor_db:+.1f} dB). Check for hiss/hum at source.\033[0m")
    elif noise_floor_db > -50:
        print(f"  \033[92m  Noise floor acceptable.\033[0m")
    else:
        print(f"  \033[92m  Noise floor excellent.\033[0m")

    print()
    print(f"  Target: speech RMS between -24 and -12 dBFS,")
    print(f"          peak below -3 dBFS, noise floor below -50 dBFS.")
    print()
