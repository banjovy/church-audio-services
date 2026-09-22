# Audio Level Setup Guide

Set optimal input gain and stream volume using the built-in level test.

## Run the Level Test

```bash
audio-services --level-test --duration 20
```

Speak at normal volume into the mic for the full duration. The first half-second measures the noise floor (stay quiet), then speak naturally.

Override the input device if needed:

```bash
audio-services --level-test --duration 20 --device 0
audio-services --level-test --duration 20 --device "plughw:CARD=Device,DEV=0"
```

## Reading the Results

The test reports four values:

| Metric | What it means |
|--------|--------------|
| Peak level | Loudest moment during the test |
| Avg speech RMS | Average loudness while speaking |
| Noise floor | Background level when silent |
| SNR estimate | Speech level minus noise floor |

## Target Levels

| Metric | Target | Action if outside |
|--------|--------|-------------------|
| Avg speech RMS | -24 to -12 dBFS | Adjust input gain at source |
| Peak level | Below -3 dBFS | Reduce gain if peaks exceed this |
| Noise floor | Below -50 dBFS | Check cables, source gain staging |
| SNR | 20+ dB | Increase source gain or reduce noise |

## Adjusting Input Gain

The goal is to raise speech level without raising the noise floor. Always adjust gain at the earliest point in the signal chain:

1. Increase the source output level (mixer send, interface gain knob)
2. Re-run `--level-test` and check that speech RMS lands between -24 and -12 dBFS
3. Confirm peak stays below -3 dBFS (no clipping)
4. Confirm noise floor drops below -50 dBFS relative to the new speech level

If the source is already maxed and speech is still below -24 dBFS, the hardware preamp is too weak for the mic. Use a device with more gain.

## Adjusting Stream Gain (config.json)

The `audio_stream_gain_db` setting in `config.json` applies digital gain to the audio stream before encoding:

```json
{
  "audio_stream_gain_db": 12.0
}
```

This value is in decibels. The signal is multiplied by `10^(dB/20)` then clipped to prevent distortion.

| Input speech level | Recommended `audio_stream_gain_db` |
|---|---|
| -12 dBFS (hot) | 0 to 6 |
| -18 dBFS (normal) | 6 to 12 |
| -24 dBFS (quiet) | 12 to 18 |
| -30+ dBFS (very quiet) | Fix at source first |

### How to set it

1. Run `--level-test` and note the avg speech RMS
2. Choose a gain value that brings speech to approximately -6 dBFS after boost:
   - Formula: `gain_db = -6 - (speech_rms_db)`
   - Example: speech at -18 dBFS → gain = -6 - (-18) = 12 dB
3. Set `"audio_stream_gain_db"` in `config.json`
4. Restart the service

### Clipping

If `speech_rms + audio_stream_gain_db` exceeds 0 dBFS, peaks will clip. The encoder hard-clips at 0 dBFS. Keep the sum below -3 dBFS for headroom:

```
speech_peak + audio_stream_gain_db < -3
```

## Quick Reference

```
Too quiet on phone → increase audio_stream_gain_db (or better: increase source gain)
Distortion/clipping → decrease audio_stream_gain_db
Hiss/noise audible → increase source gain (improves SNR), don't boost digitally
```
