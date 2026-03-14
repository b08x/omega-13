#!/usr/bin/env python3
"""
Example: AudioEngine with Automatic Transcription

This demonstrates how to use the enhanced AudioEngine with automatic
transcription after audio processing completes.
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, 'src')

from omega13.audio import AudioEngine
from omega13.transcription import TranscriptionService, TranscriptionProvider


class MockTranscriptionProvider(TranscriptionProvider):
    """Mock transcription provider for demonstration."""

    def check_health(self):
        return True, None

    def transcribe(self, audio_path: Path, timeout: int = 60):
        """Mock transcription - returns dummy text."""
        time.sleep(0.5)  # Simulate processing time
        return f"Mock transcription of {audio_path.name}", "en"


def main():
    """Demonstrate automatic transcription workflow."""
    print("AudioEngine with Automatic Transcription Demo")
    print("=" * 50)

    # Setup transcription service
    provider = MockTranscriptionProvider()
    transcription_service = TranscriptionService(provider=provider)

    # Create AudioEngine
    engine = AudioEngine()

    # Configure transcription
    engine.set_transcription_service(transcription_service)
    engine.set_auto_transcription(True)  # Enable automatic transcription

    # Set up callbacks
    def on_processing_done(path, success, error):
        if success:
            print(f"✅ Audio processing completed: {path}")
        else:
            print(f"❌ Audio processing failed: {error}")

    def on_transcription_done(text, success, error):
        if success:
            print(f"📝 Transcription completed: '{text}'")
            # Here you could save to session, copy to clipboard, etc.
        else:
            print(f"❌ Transcription failed: {error}")

    engine.set_processing_callback(on_processing_done)
    engine.set_transcription_callback(on_transcription_done)

    print("Configuration complete!")
    print(f"Auto-transcription: {engine.enable_auto_transcription}")
    print(f"Processing queue: {engine.processing_queue.is_running()}")

    # In real usage, you would now:
    # 1. engine.start()  # Start JACK client and processing queue
    # 2. engine.start_recording(output_path)  # Record audio
    # 3. engine.stop_recording()  # Stop recording
    #
    # The workflow would be:
    # Raw audio saved → Audio processing queued → Processing completes →
    # Transcription starts automatically → Transcription completes →
    # Both callbacks invoked

    print("\nWorkflow:")
    print("1. Record audio → Raw file saved immediately")
    print("2. Audio processing → Background queue (trim, downsample)")
    print("3. Transcription → Automatic after processing completes")
    print("4. Callbacks → Notify when each step completes")
    print("\nNo blocking, no manual steps! 🎉")


if __name__ == "__main__":
    main()