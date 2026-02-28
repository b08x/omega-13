"""
Baseline measurements for AudioProcessor operations.

Tests all AudioProcessor operations with known test audio files,
measures processing times, and documents expected outputs.

Test audio files are generated synthetically (no large binaries in git):
- mono_44100_1s.wav: 1ch, 44100Hz, 1.0s
- stereo_48000_2s.wav: 2ch, 48000Hz, 2.0s
- mono_16000_3s.wav: 1ch, 16000Hz, 3.0s
- mono_44100_with_silence.wav: 1ch, 44100Hz, 2.0s (with silence)
- stereo_48000_with_silence.wav: 2ch, 48000Hz, 2.0s (with silence)
- mono_44100_short.wav: 1ch, 44100Hz, 0.5s
- mono_16000_long.wav: 1ch, 16000Hz, 5.0s
"""

import sys
import os
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

# Add src to path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import soundfile as sf
import numpy as np
from omega13.audio_processor import (
    AudioProcessor,
    check_ffmpeg_available,
    check_sox_available,
)


@dataclass
class AudioMetrics:
    """Metrics for audio file properties."""

    filename: str
    channels: int
    sample_rate: int
    duration: float
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OperationMetrics:
    """Metrics for an AudioProcessor operation."""

    operation: str
    input_file: str
    output_file: str
    input_metrics: Dict[str, Any]
    output_metrics: Dict[str, Any]
    processing_time_ms: float
    success: bool
    error: str = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaselineMeasurementRunner:
    """Run baseline measurements for AudioProcessor operations."""

    def __init__(self, fixtures_dir: Path = None):
        """Initialize the measurement runner."""
        if fixtures_dir is None:
            fixtures_dir = Path(__file__).parent / "fixtures" / "audio"

        self.fixtures_dir = fixtures_dir
        self.processor = None
        self.measurements: List[OperationMetrics] = []
        self.temp_dir = None

        # Ensure test audio files exist
        if not self.fixtures_dir.exists():
            raise FileNotFoundError(
                f"Test audio fixtures directory not found: {self.fixtures_dir}"
            )

        test_files = list(self.fixtures_dir.glob("*.wav"))
        if not test_files:
            raise FileNotFoundError(f"No test audio files found in {self.fixtures_dir}")

    def setup(self):
        """Setup processor and temp directory."""
        self.processor = AudioProcessor()
        self.temp_dir = tempfile.TemporaryDirectory()

    def teardown(self):
        """Cleanup temp directory."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    def get_audio_metrics(self, file_path: Path) -> AudioMetrics:
        """Get metrics for an audio file."""
        data, sr = sf.read(file_path)

        if len(data.shape) == 1:
            channels = 1
        else:
            channels = data.shape[1]

        duration = len(data) / sr
        size_bytes = file_path.stat().st_size

        return AudioMetrics(
            filename=file_path.name,
            channels=channels,
            sample_rate=sr,
            duration=duration,
            size_bytes=size_bytes,
        )

    def measure_operation(
        self, operation_name: str, input_file: Path, operation_func, *args, **kwargs
    ) -> OperationMetrics:
        """Measure an AudioProcessor operation."""
        input_metrics = self.get_audio_metrics(input_file).to_dict()

        start_time = time.time()
        try:
            output_file = operation_func(input_file, *args, **kwargs)
            processing_time_ms = (time.time() - start_time) * 1000

            output_metrics = self.get_audio_metrics(output_file).to_dict()

            return OperationMetrics(
                operation=operation_name,
                input_file=input_file.name,
                output_file=output_file.name,
                input_metrics=input_metrics,
                output_metrics=output_metrics,
                processing_time_ms=processing_time_ms,
                success=True,
            )
        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            return OperationMetrics(
                operation=operation_name,
                input_file=input_file.name,
                output_file="",
                input_metrics=input_metrics,
                output_metrics={},
                processing_time_ms=processing_time_ms,
                success=False,
                error=str(e),
            )

    def run_trim_silence_tests(self):
        """Test trim_silence operation."""
        print("\n=== Testing trim_silence ===")

        # Test with silence file
        input_file = self.fixtures_dir / "mono_44100_with_silence.wav"
        if input_file.exists():
            output_path = Path(self.temp_dir.name) / "trimmed.wav"
            metrics = self.measure_operation(
                "trim_silence",
                input_file,
                self.processor.trim_silence,
                output_path=output_path,
                threshold_db=-50.0,
                min_silence_duration=0.5,
            )
            self.measurements.append(metrics)
            self._print_metrics(metrics)

        # Test with stereo silence file
        input_file = self.fixtures_dir / "stereo_48000_with_silence.wav"
        if input_file.exists():
            output_path = Path(self.temp_dir.name) / "trimmed_stereo.wav"
            metrics = self.measure_operation(
                "trim_silence_stereo",
                input_file,
                self.processor.trim_silence,
                output_path=output_path,
                threshold_db=-50.0,
                min_silence_duration=0.5,
            )
            self.measurements.append(metrics)
            self._print_metrics(metrics)

    def run_downsample_tests(self):
        """Test downsample operation."""
        print("\n=== Testing downsample ===")

        # Test downsampling 44100Hz to 16000Hz
        input_file = self.fixtures_dir / "mono_44100_1s.wav"
        if input_file.exists():
            output_path = Path(self.temp_dir.name) / "downsampled_16k.wav"
            metrics = self.measure_operation(
                "downsample_44100_to_16000",
                input_file,
                self.processor.downsample,
                output_path=output_path,
                target_rate=16000,
                filter_type="high_quality",
                channels=1,
            )
            self.measurements.append(metrics)
            self._print_metrics(metrics)

        # Test downsampling 48000Hz to 16000Hz (stereo to mono)
        input_file = self.fixtures_dir / "stereo_48000_2s.wav"
        if input_file.exists():
            output_path = Path(self.temp_dir.name) / "downsampled_stereo_16k.wav"
            metrics = self.measure_operation(
                "downsample_48000_to_16000_stereo_to_mono",
                input_file,
                self.processor.downsample,
                output_path=output_path,
                target_rate=16000,
                filter_type="high_quality",
                channels=1,
            )
            self.measurements.append(metrics)
            self._print_metrics(metrics)

    def run_encode_mp3_tests(self):
        """Test encode_mp3 operation."""
        print("\n=== Testing encode_mp3 ===")

        # Test MP3 encoding
        input_file = self.fixtures_dir / "mono_44100_1s.wav"
        if input_file.exists():
            output_path = Path(self.temp_dir.name) / "encoded.mp3"
            metrics = self.measure_operation(
                "encode_mp3",
                input_file,
                self.processor.encode_mp3,
                output_path=output_path,
                bitrate="128k",
            )
            self.measurements.append(metrics)
            self._print_metrics(metrics)

    def run_get_audio_info_tests(self):
        """Test get_audio_info operation."""
        print("\n=== Testing get_audio_info ===")

        test_files = [
            "mono_44100_1s.wav",
            "stereo_48000_2s.wav",
            "mono_16000_3s.wav",
        ]

        for filename in test_files:
            input_file = self.fixtures_dir / filename
            if input_file.exists():
                start_time = time.time()
                try:
                    info = self.processor.get_audio_info(input_file)
                    processing_time_ms = (time.time() - start_time) * 1000

                    input_metrics = self.get_audio_metrics(input_file).to_dict()

                    metrics = OperationMetrics(
                        operation="get_audio_info",
                        input_file=filename,
                        output_file="",
                        input_metrics=input_metrics,
                        output_metrics=info,
                        processing_time_ms=processing_time_ms,
                        success=True,
                    )
                    self.measurements.append(metrics)
                    self._print_metrics(metrics)
                except Exception as e:
                    processing_time_ms = (time.time() - start_time) * 1000
                    input_metrics = self.get_audio_metrics(input_file).to_dict()
                    metrics = OperationMetrics(
                        operation="get_audio_info",
                        input_file=filename,
                        output_file="",
                        input_metrics=input_metrics,
                        output_metrics={},
                        processing_time_ms=processing_time_ms,
                        success=False,
                        error=str(e),
                    )
                    self.measurements.append(metrics)
                    self._print_metrics(metrics)

    def run_preprocess_for_transcription_tests(self):
        """Test preprocess_for_transcription operation."""
        print("\n=== Testing preprocess_for_transcription ===")

        # Test preprocessing for transcription
        input_file = self.fixtures_dir / "mono_44100_1s.wav"
        if input_file.exists():
            output_path = Path(self.temp_dir.name) / "preprocessed.wav"
            metrics = self.measure_operation(
                "preprocess_for_transcription",
                input_file,
                self.processor.preprocess_for_transcription,
                output_path=output_path,
                target_sample_rate=16000,
            )
            self.measurements.append(metrics)
            self._print_metrics(metrics)

    def run_all_tests(self):
        """Run all baseline measurement tests."""
        print("=" * 70)
        print("AudioProcessor Baseline Measurements")
        print("=" * 70)

        self.setup()
        try:
            self.run_get_audio_info_tests()
            self.run_trim_silence_tests()
            self.run_downsample_tests()
            self.run_encode_mp3_tests()
            self.run_preprocess_for_transcription_tests()

            self._print_summary()
            return True
        except Exception as e:
            print(f"\nError during measurements: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            self.teardown()

    def _print_metrics(self, metrics: OperationMetrics):
        """Print metrics for an operation."""
        if metrics.success:
            print(f"\n✓ {metrics.operation}")
            print(
                f"  Input:  {metrics.input_file} ({metrics.input_metrics['channels']}ch, "
                f"{metrics.input_metrics['sample_rate']}Hz, "
                f"{metrics.input_metrics['duration']:.2f}s, "
                f"{metrics.input_metrics['size_bytes']} bytes)"
            )
            print(
                f"  Output: {metrics.output_file} ({metrics.output_metrics['channels']}ch, "
                f"{metrics.output_metrics['sample_rate']}Hz, "
                f"{metrics.output_metrics['duration']:.2f}s, "
                f"{metrics.output_metrics['size_bytes']} bytes)"
            )
            print(f"  Time:   {metrics.processing_time_ms:.2f}ms")
        else:
            print(f"\n✗ {metrics.operation}")
            print(f"  Input:  {metrics.input_file}")
            print(f"  Error:  {metrics.error}")
            print(f"  Time:   {metrics.processing_time_ms:.2f}ms")

    def _print_summary(self):
        """Print summary of all measurements."""
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)

        successful = [m for m in self.measurements if m.success]
        failed = [m for m in self.measurements if not m.success]

        print(f"\nTotal operations: {len(self.measurements)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")

        if successful:
            print("\nOperation timings:")
            for metrics in successful:
                print(f"  {metrics.operation:40s}: {metrics.processing_time_ms:8.2f}ms")

        if failed:
            print("\nFailed operations:")
            for metrics in failed:
                print(f"  {metrics.operation:40s}: {metrics.error}")

    def save_measurements(self, output_file: Path):
        """Save measurements to JSON file."""
        data = {
            "ffmpeg_available": check_ffmpeg_available(),
            "sox_available": check_sox_available(),
            "measurements": [m.to_dict() for m in self.measurements],
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\nMeasurements saved to {output_file}")


def main():
    """Run baseline measurements."""
    runner = BaselineMeasurementRunner()
    success = runner.run_all_tests()

    # Save measurements
    evidence_dir = Path(__file__).parent.parent / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    runner.save_measurements(evidence_dir / "task-4-baseline-measurements.json")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
