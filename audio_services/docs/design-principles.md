# Design Principles

## Accessible to any congregation

Live captioning and hearing-assist streaming shouldn't require a dedicated AV team or a cloud subscription. This project brings those capabilities to any size church — running on hardware you already own or can buy for under $200, with zero ongoing costs.

## No subscriptions, no cloud, no data leaving the building

Everything runs locally. Whisper models run on-device. Audio never leaves the LAN. There are no API keys to manage, no monthly bills, no third-party accounts, and no privacy concerns about sermon audio being processed externally.

## Modest hardware

The system runs well on a used mini PC (e.g., HP EliteDesk 800 G4 Mini, ~$100 used) with no GPU. CPU-only inference with `faster-whisper` and INT8 quantization keeps it fast enough for real-time on a 4-core desktop chip. A $20 USB audio interface completes the setup.

## Turn it on and it works

Once installed, the service starts on boot. No login required, no manual steps on Sunday morning. Plug in the audio interface, power on the machine, and captions are live. Attendees scan a QR code — no app install needed.

## Accuracy over speed

We favor slightly longer transcription chunks (4–7 seconds) with silence-boundary splitting over faster but choppy word-by-word output. This gives Whisper enough context to produce accurate, natural sentences — especially important for sermon content where proper nouns, scripture references, and theological terms are common.

## Self-contained and maintainable

A single Python package, a single systemd service, a single config file. Updates are `git pull && restart`. No Docker, no orchestration, no build step. A volunteer who can follow a terminal guide can maintain it.

## Room to grow

The baseline hardware handles real-time captioning well, but modest upgrades can noticeably reduce latency and improve throughput. Adding a low-end NVIDIA GPU (e.g., GTX 1650 or T400) enables CUDA-accelerated inference — cutting transcription time roughly in half. Faster CPUs with more cores also help, especially for parallel audio encoding. See `hardware-upgrade-options.md` for specific recommendations.
