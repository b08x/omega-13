#!/usr/bin/env python3
"""
Debug test script for containerized transcription.
Enables detailed logging to diagnose podman/whisper-cli issues.
"""
import sys
import logging
from pathlib import Path

# Enable DEBUG level logging with detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

try:
    from transcription import TranscriptionService, TranscriptionStatus, TranscriptionResult

    print("=" * 70)
    print("CONTAINERIZED TRANSCRIPTION DEBUG TEST")
    print("=" * 70)

    # Initialize service
    service = TranscriptionService(
        model_size="large-v3-turbo-q5_0",
        container_image="localhost/whisper-cuda:2025-12-21",
        whisper_binary="~/LLMOS/whisper.cpp/build/bin/whisper-cli"
    )

    print(f"\n✓ Service initialized:")
    print(f"  Model: {service.model_size}")
    print(f"  Image: {service.container_image}")
    print(f"  Binary: {service.whisper_binary}")

    # Find a test audio file
    test_audio = Path("/var/home/b08x/Notebooks/tm-2025-12-20T21-40-47.wav")

    if not test_audio.exists():
        print(f"\n✗ Test audio file not found: {test_audio}")
        print("Please specify a valid WAV file to test with.")
        sys.exit(1)

    print(f"\n✓ Test audio file: {test_audio}")
    print(f"  Size: {test_audio.stat().st_size:,} bytes")

    # Define callbacks
    def on_complete(result: TranscriptionResult):
        print("\n" + "=" * 70)
        print("TRANSCRIPTION COMPLETE")
        print("=" * 70)
        print(f"Status: {result.status}")
        print(f"Language: {result.language}")
        print(f"Text length: {len(result.text)} chars")
        print(f"\nTranscription:\n{result.text[:500]}")
        if result.error:
            print(f"\n✗ Error: {result.error}")

    def on_progress(progress: float):
        pct = int(progress * 100)
        print(f"Progress: {pct}%")

    # Start transcription
    print("\n" + "=" * 70)
    print("STARTING TRANSCRIPTION")
    print("=" * 70)

    thread = service.transcribe_async(
        test_audio,
        callback=on_complete,
        progress_callback=on_progress
    )

    # Wait for completion
    print("\nWaiting for transcription to complete...")
    thread.join()

    print("\n✓ Test complete!")

except ImportError as e:
    print(f"✗ Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
