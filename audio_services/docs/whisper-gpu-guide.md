# Whisper GPU Transcription

This document explains how the audio services system uses a GPU to run the Whisper speech-to-text model via the `faster-whisper` library.

## Overview

The project uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), a CTranslate2-based reimplementation of OpenAI's Whisper model. CTranslate2 provides optimized inference on both CPU and NVIDIA GPUs via CUDA.

## Configuration

GPU usage is controlled by two settings in `config.json`:

```json
{
  "whisper_device": "cuda",
  "whisper_compute_type": "int8"
}
```

| Setting | Values | Description |
|---------|--------|-------------|
| `whisper_device` | `cuda`, `cpu` | Selects GPU or CPU inference |
| `whisper_compute_type` | `float16`, `int8_float16`, `int8`, `float32` | Quantization level for model weights |

For CUDA devices, recommended compute types are `float16` or `int8_float16` for best performance. The `int8` type also works on GPU but `float16` typically gives the best speed/quality balance on modern NVIDIA hardware.

## How the Code Loads the Model on GPU

The GPU path flows through these components:

### 1. Configuration Loading (`config.py`)

`AppConfig` reads `whisper_device` and `whisper_compute_type` from `config.json`:

```python
@dataclass
class AppConfig:
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
```

### 2. Engine Initialization (`main.py`)

At startup, `main.py` passes the device and compute type to the engine:

```python
engine = WhisperTranscriptionEngine()
engine.initialize(
    config.whisper_model,
    config.language,
    device=config.whisper_device,        # "cuda"
    compute_type=config.whisper_compute_type  # "int8"
)
```

### 3. Model Loading (`whisper_engine.py`)

`WhisperTranscriptionEngine.initialize()` passes these values directly to `faster-whisper`'s `WhisperModel`:

```python
self._model = WhisperModel(
    model_id,
    device=device,           # "cuda" → loads model onto GPU
    compute_type=compute_type  # quantization precision
)
```

When `device="cuda"`:
- CTranslate2 loads model weights into GPU VRAM
- All inference (encoding, decoding, beam search) runs on the GPU
- Audio data is transferred to the GPU for processing

When `device="cpu"`, the engine additionally sets `cpu_threads=6` for multi-threaded CPU inference.

### 4. Fallback Mechanism

If loading a model fails (e.g., out of VRAM), the engine tries progressively smaller models:

```python
MODEL_ORDER = ["medium", "small", "base", "tiny"]
```

It starts at the configured size and falls through smaller models until one loads successfully. This handles cases where a GPU doesn't have enough VRAM for larger models.

### 5. Async Transcription (`main.py`)

Transcription runs in a thread pool so GPU inference doesn't block the async event loop:

```python
result = await asyncio.to_thread(engine.transcribe, chunk)
```

The `transcribe()` method calls `self._model.transcribe()` with parameters like `beam_size=3`, `vad_filter=True`, etc. All of this computation happens on whatever device the model was loaded onto.

## CUDA Requirements

To run on GPU, the system needs:

1. An NVIDIA GPU with CUDA support
2. NVIDIA drivers installed (included in Fedora RPM Fusion `akmod-nvidia`)
3. cuBLAS and cuDNN libraries — these ship bundled with `faster-whisper` / CTranslate2's Python wheels via `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` pip packages

No separate CUDA toolkit installation is required. The `faster-whisper` pip package pulls in the necessary CUDA runtime libraries automatically.

## Performance Characteristics

| Model | VRAM Usage (approx) | Realtime Factor (GPU) |
|-------|---------------------|----------------------|
| tiny  | ~1 GB               | ~10-15x              |
| base  | ~1 GB               | ~8-12x               |
| small | ~2 GB               | ~5-8x                |
| medium| ~5 GB               | ~3-5x                |

Realtime factor means how much faster than real-time the model transcribes (e.g., 5x = 1 second of audio processed in 0.2 seconds). Actual numbers depend on GPU model, compute type, and beam size.

## Switching Between CPU and GPU

To switch to CPU (e.g., for a machine without a GPU):

```json
{
  "whisper_device": "cpu",
  "whisper_compute_type": "int8"
}
```

To switch to GPU:

```json
{
  "whisper_device": "cuda",
  "whisper_compute_type": "float16"
}
```

No code changes are required — just update `config.json` and restart the service.
