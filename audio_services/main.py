"""Main entry point - orchestrates audio capture, transcription, and serving."""

import argparse
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path

from better_profanity import profanity

from .audio import AudioInputHandler, validate_audio_device
from .audio_broadcast import AudioBroadcaster
from .audio_file import FileAudioSource
from .config import AppConfig
from .server import CaptionServer
from .whisper_engine import WhisperTranscriptionEngine

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def caption_loop(
    audio: AudioInputHandler,
    engine: WhisperTranscriptionEngine,
    server: CaptionServer,
    config: AppConfig,
):
    """Main loop: grab audio chunks, transcribe, broadcast."""
    poll_interval = config.audio.chunk_duration_ms / 1000.0 / 2
    last_speech_time = time.time()
    no_speech_sent = False
    no_speech_timeout = config.no_speech_timeout

    while audio.is_capturing():
        chunk = audio.get_chunk()

        # Update status
        server.set_status(
            language=engine._language,
            model_name=engine.get_model_name(),
            audio_level=audio.get_input_level(),
        )

        if chunk is None:
            # Check for extended silence
            if not no_speech_sent and (time.time() - last_speech_time) > no_speech_timeout:
                await server.broadcast("[no speech detected. waiting...]", engine._language)
                no_speech_sent = True
            await asyncio.sleep(poll_interval)
            continue

        if audio.is_silent(chunk):
            if not no_speech_sent and (time.time() - last_speech_time) > no_speech_timeout:
                await server.broadcast("[no speech detected. waiting...]", engine._language)
                no_speech_sent = True
            await asyncio.sleep(0.1)
            continue

        # Run transcription in a thread to not block the event loop
        chunk_duration = len(chunk) / 16000
        result = await asyncio.to_thread(engine.transcribe, chunk)

        if result and result.text.strip():
            last_speech_time = time.time()
            no_speech_sent = False
            ratio = chunk_duration / (result.processing_time_ms / 1000) if result.processing_time_ms > 0 else 0
            logger.debug(
                f"{chunk_duration:.1f}s audio in {result.processing_time_ms:.0f}ms "
                f"({ratio:.1f}x realtime)"
            )
            clean_text = profanity.censor(result.text)
            if clean_text != result.text:
                logger.info(f"Profanity filtered: {result.text}")
            await server.broadcast(clean_text, result.language)
            logger.debug(
                f"Caption: {result.text} "
                f"[{result.processing_time_ms:.0f}ms, conf={result.confidence:.2f}]"
            )
        else:
            # Audio present but no usable transcription — skip silently
            logger.debug("Chunk had audio but no usable transcription — skipped")

        await asyncio.sleep(0.05)


async def run(config: AppConfig, audio_file: str | None = None, no_realtime: bool = False):
    # Initialize profanity filter
    profanity.load_censor_words(whitelist_words=config.profanity_whitelist)

    # Initialize transcription engine
    engine = WhisperTranscriptionEngine()
    try:
        engine.initialize(config.whisper_model, config.language,
                          device=config.whisper_device,
                          compute_type=config.whisper_compute_type)
    except RuntimeError as e:
        logger.error(f"Failed to initialize transcription engine: {e}")
        sys.exit(1)

    # Start caption server
    server = CaptionServer(
        port=config.server_port,
        max_history=config.max_caption_history,
        max_clients=config.max_clients,
        admin_pin=config.admin_pin,
        reconnect_timeout=config.reconnect_timeout,
        site_title=config.site_title,
        secondary_title=config.secondary_title,
    )
    server.set_language_callback(engine.set_language)

    # Set up audio broadcaster if enabled
    broadcaster = None
    if config.audio_stream_enabled:
        broadcaster = AudioBroadcaster(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            bitrate=config.audio_stream_bitrate,
            gain_db=config.audio_stream_gain_db,
            max_clients=config.max_audio_clients,
        )
        broadcaster.start()
        server.set_audio_broadcaster(broadcaster)

    await server.start()

    # Start audio source (file or live)
    if audio_file:
        audio = FileAudioSource(
            audio_file, config.audio, realtime=not no_realtime
        )
        logger.info(f"Using audio file: {audio_file}")
    else:
        try:
            resolved_device = validate_audio_device(config.audio.input_device)
            config.audio.input_device = resolved_device
        except RuntimeError as e:
            logger.error(f"Audio device validation failed: {e}")
            sys.exit(1)
        audio = AudioInputHandler(config.audio)
        try:
            audio.start_capture()
        except Exception as e:
            logger.error(f"Audio capture failed: {e}")
            logger.error("Check that an audio input device is connected.")
            sys.exit(1)

    # Connect audio tap to broadcaster
    if broadcaster and not audio_file:
        audio.set_audio_tap(broadcaster.feed_audio)

    logger.info("=== Caption system ready ===")
    logger.info(f"  Model: {engine.get_model_name()}")
    logger.info(f"  Language: {config.language}")
    logger.info(f"  Server: http://0.0.0.0:{config.server_port}")
    if broadcaster:
        logger.info(f"  Audio stream: /listen (Opus {config.audio_stream_bitrate // 1000}kbps)")
    if audio_file:
        logger.info(f"  Source: {audio_file} (realtime={'yes' if not no_realtime else 'no'})")

    # Start broadcast loop as a background task
    broadcast_task = None
    if broadcaster:
        broadcast_task = asyncio.create_task(broadcaster.start_broadcast_loop())

    try:
        await caption_loop(audio, engine, server, config)
    finally:
        if broadcaster:
            broadcaster.stop()
        if broadcast_task:
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass
        audio.stop_capture()
        await server.stop()
    
    if audio_file:
        logger.info("Audio file finished.")


def main():
    parser = argparse.ArgumentParser(description="Church Audio Services")
    parser.add_argument(
        "--file", "-f",
        help="Path to an audio file (MP3, WAV, etc.) to use instead of live input"
    )
    parser.add_argument(
        "--no-realtime",
        action="store_true",
        help="Process file as fast as possible (no pacing). Only applies with --file"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config.json (default: auto-detect)"
    )
    parser.add_argument(
        "--model", "-m",
        choices=["tiny", "base", "small", "medium"],
        help="Override Whisper model size"
    )
    parser.add_argument(
        "--language", "-l",
        choices=["en", "es", "auto"],
        help="Override transcription language"
    )
    parser.add_argument(
        "--level-test",
        action="store_true",
        help="Run audio input level test (shows live meter and gain recommendations)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Duration in seconds for --level-test (default: 10)"
    )
    parser.add_argument(
        "--device",
        help="Override audio input device for --level-test (index, ALSA id, or name)"
    )
    args = parser.parse_args()

    # Load config
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = Path(__file__).resolve().parent.parent / "config.json"

    if config_path.exists():
        config = AppConfig.from_file(config_path)
    else:
        logger.warning("No config.json found, using defaults")
        config = AppConfig()

    # Handle --level-test before full startup
    if args.level_test:
        from .level_test import run_level_test
        device_override = None
        if args.device:
            # Try to interpret as int index, else pass as string
            try:
                device_override = int(args.device)
            except ValueError:
                device_override = args.device
        run_level_test(config, duration=args.duration, device_override=device_override)
        return

    # Apply log level from config
    level = getattr(logging, config.log_level.upper(), logging.WARNING)
    logging.getLogger().setLevel(level)

    # Silence noisy third-party loggers
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # CLI overrides
    if args.model:
        config.whisper_model = args.model
    if args.language:
        config.language = args.language

    loop = asyncio.new_event_loop()

    def shutdown():
        logger.info("Shutting down...")
        loop.stop()

    signal.signal(signal.SIGINT, lambda *_: shutdown())
    signal.signal(signal.SIGTERM, lambda *_: shutdown())

    try:
        loop.run_until_complete(run(config, audio_file=args.file, no_realtime=args.no_realtime))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
