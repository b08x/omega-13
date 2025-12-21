import sys
from pathlib import Path
import logging

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

try:
    from transcription import TranscriptionService, TranscriptionStatus, TranscriptionResult
    print("✓ Successfully imported transcription module")

    service = TranscriptionService(
        model_size="base",
        container_image="localhost/whisper-cuda:2025-12-21",
        whisper_binary="~/LLMOS/whisper.cpp/build/bin/whisper-cli"
    )
    print(f"✓ Service initialized with:")
    print(f"  - Model size: {service.model_size}")
    print(f"  - Container image: {service.container_image}")
    print(f"  - Whisper binary: {service.whisper_binary}")

    # Check if the methods exist (containerized approach)
    print(f"\n✓ API methods available:")
    print(f"  - transcribe_async: {hasattr(service, 'transcribe_async')}")
    print(f"  - cleanup: {hasattr(service, 'cleanup')}")

    print(f"\n✓ Containerized approach - no model loading required!")
    print(f"  Transcription runs in ephemeral podman containers")

except ImportError as e:
    print(f"✗ Import Error: {e}")
except Exception as e:
    print(f"✗ Unexpected Error: {e}")
