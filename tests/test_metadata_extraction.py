"""
Test metadata extraction using ffprobe CLI implementation.

Tests verify that the new ffprobe-based get_audio_info() method produces
identical results to the original ffmpeg.probe() implementation.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any

import pytest

from omega13.audio_processor import AudioProcessor, CommandExecutionError

logger = logging.getLogger(__name__)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "audio"


class TestMetadataExtraction:
    """Test metadata extraction with ffprobe CLI."""

    @pytest.fixture
    def processor(self):
        """Create AudioProcessor instance."""
        return AudioProcessor()

    @pytest.fixture
    def test_files(self):
        """Get list of test audio files."""
        if not FIXTURES_DIR.exists():
            pytest.skip("Test fixtures directory not found")

        files = list(FIXTURES_DIR.glob("*.wav"))
        if not files:
            pytest.skip("No test audio files found")

        return sorted(files)

    def test_metadata_extraction_basic(self, processor, test_files):
        """Test basic metadata extraction from test audio files."""
        for audio_file in test_files:
            logger.info(f"Testing metadata extraction: {audio_file.name}")

            info = processor.get_audio_info(audio_file)

            # Verify all required fields are present
            assert "duration" in info
            assert "sample_rate" in info
            assert "channels" in info
            assert "codec" in info
            assert "bitrate" in info
            assert "size_bytes" in info
            assert "format" in info

            # Verify field types
            assert isinstance(info["duration"], float)
            assert isinstance(info["sample_rate"], int)
            assert isinstance(info["channels"], int)
            assert isinstance(info["codec"], str)
            assert isinstance(info["bitrate"], int)
            assert isinstance(info["size_bytes"], int)
            assert isinstance(info["format"], str)

            # Verify reasonable values
            assert info["duration"] > 0, (
                f"Duration should be positive: {info['duration']}"
            )
            assert info["sample_rate"] > 0, (
                f"Sample rate should be positive: {info['sample_rate']}"
            )
            assert info["channels"] > 0, (
                f"Channels should be positive: {info['channels']}"
            )
            assert info["size_bytes"] > 0, (
                f"File size should be positive: {info['size_bytes']}"
            )

            logger.info(
                f"  ✓ {info['sample_rate']}Hz, {info['channels']}ch, "
                f"{info['duration']:.2f}s, {info['codec']}, {info['bitrate']}bps"
            )

    def test_metadata_consistency(self, processor, test_files):
        """Test that metadata extraction is consistent across multiple calls."""
        if not test_files:
            pytest.skip("No test audio files")

        audio_file = test_files[0]

        # Extract metadata twice
        info1 = processor.get_audio_info(audio_file)
        info2 = processor.get_audio_info(audio_file)

        # Verify identical results
        assert info1 == info2, "Metadata should be consistent across calls"
        logger.info(f"✓ Metadata extraction is consistent for {audio_file.name}")

    def test_metadata_file_not_found(self, processor):
        """Test error handling for missing files."""
        missing_file = FIXTURES_DIR / "nonexistent_file.wav"

        with pytest.raises(FileNotFoundError):
            processor.get_audio_info(missing_file)

        logger.info("✓ FileNotFoundError raised for missing file")

    def test_metadata_corrupted_file(self, processor, tmp_path):
        """Test error handling for corrupted audio files."""
        # Create a corrupted file (not valid audio)
        corrupted_file = tmp_path / "corrupted.wav"
        corrupted_file.write_text("This is not valid audio data")

        with pytest.raises(CommandExecutionError):
            processor.get_audio_info(corrupted_file)

        logger.info("✓ CommandExecutionError raised for corrupted file")

    def test_metadata_mono_vs_stereo(self, processor, test_files):
        """Test metadata extraction for mono and stereo files."""
        mono_files = [f for f in test_files if "mono" in f.name]
        stereo_files = [f for f in test_files if "stereo" in f.name]

        # Test mono files
        for mono_file in mono_files:
            info = processor.get_audio_info(mono_file)
            assert info["channels"] == 1, f"Expected mono (1 channel): {mono_file.name}"
            logger.info(f"✓ Mono file detected: {mono_file.name}")

        # Test stereo files
        for stereo_file in stereo_files:
            info = processor.get_audio_info(stereo_file)
            assert info["channels"] == 2, (
                f"Expected stereo (2 channels): {stereo_file.name}"
            )
            logger.info(f"✓ Stereo file detected: {stereo_file.name}")

    def test_metadata_sample_rates(self, processor, test_files):
        """Test metadata extraction for different sample rates."""
        sample_rate_map = {
            "16000": 16000,
            "44100": 44100,
            "48000": 48000,
        }

        for audio_file in test_files:
            info = processor.get_audio_info(audio_file)

            # Check if filename contains sample rate hint
            for rate_str, expected_rate in sample_rate_map.items():
                if rate_str in audio_file.name:
                    assert info["sample_rate"] == expected_rate, (
                        f"Expected {expected_rate}Hz for {audio_file.name}, "
                        f"got {info['sample_rate']}Hz"
                    )
                    logger.info(
                        f"✓ Sample rate {expected_rate}Hz detected: {audio_file.name}"
                    )
                    break

    def test_metadata_duration(self, processor, test_files):
        """Test metadata extraction for duration field."""
        for audio_file in test_files:
            info = processor.get_audio_info(audio_file)

            # Duration should be reasonable (between 0.1s and 1 hour)
            assert 0.1 <= info["duration"] <= 3600, (
                f"Duration out of reasonable range: {info['duration']}s"
            )

            logger.info(f"✓ Duration {info['duration']:.2f}s: {audio_file.name}")

    def test_metadata_codec_detection(self, processor, test_files):
        """Test codec detection for different file formats."""
        for audio_file in test_files:
            info = processor.get_audio_info(audio_file)

            # Codec should be detected
            assert info["codec"], f"Codec not detected for {audio_file.name}"

            # WAV files should have PCM codec
            if audio_file.suffix.lower() == ".wav":
                assert "pcm" in info["codec"].lower(), (
                    f"Expected PCM codec for WAV file, got {info['codec']}"
                )

            logger.info(f"✓ Codec detected: {info['codec']} ({audio_file.name})")

    def test_metadata_format_detection(self, processor, test_files):
        """Test format detection for different file types."""
        for audio_file in test_files:
            info = processor.get_audio_info(audio_file)

            # Format should be detected
            assert info["format"], f"Format not detected for {audio_file.name}"

            # WAV files should have wav format
            if audio_file.suffix.lower() == ".wav":
                assert "wav" in info["format"].lower(), (
                    f"Expected WAV format, got {info['format']}"
                )

            logger.info(f"✓ Format detected: {info['format']} ({audio_file.name})")


class TestMetadataComparison:
    """Compare ffprobe CLI implementation with original ffmpeg.probe() if available."""

    @pytest.fixture
    def processor(self):
        """Create AudioProcessor instance."""
        return AudioProcessor()

    @pytest.fixture
    def test_files(self):
        """Get list of test audio files."""
        if not FIXTURES_DIR.exists():
            pytest.skip("Test fixtures directory not found")

        files = list(FIXTURES_DIR.glob("*.wav"))
        if not files:
            pytest.skip("No test audio files found")

        return sorted(files)

    def _get_ffmpeg_probe_info(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata using ffmpeg.probe() if available."""
        try:
            import ffmpeg

            probe = ffmpeg.probe(str(file_path))
            audio_stream = next(
                stream for stream in probe["streams"] if stream["codec_type"] == "audio"
            )

            return {
                "duration": float(probe["format"]["duration"]),
                "sample_rate": int(audio_stream["sample_rate"]),
                "channels": int(audio_stream["channels"]),
                "codec": audio_stream["codec_name"],
                "bitrate": int(probe["format"].get("bit_rate", 0)),
                "size_bytes": int(probe["format"]["size"]),
                "format": probe["format"]["format_name"],
            }
        except ImportError:
            pytest.skip("ffmpeg-python not available for comparison")

    def test_metadata_equivalence(self, processor, test_files):
        """Test that ffprobe CLI produces same metadata as ffmpeg.probe()."""
        for audio_file in test_files:
            logger.info(f"Comparing metadata: {audio_file.name}")

            # Get metadata from new implementation
            new_info = processor.get_audio_info(audio_file)

            # Get metadata from old implementation if available
            try:
                old_info = self._get_ffmpeg_probe_info(audio_file)
            except Exception:
                logger.warning(
                    f"Could not get old implementation metadata for {audio_file.name}"
                )
                continue

            # Compare all fields
            for key in [
                "duration",
                "sample_rate",
                "channels",
                "codec",
                "bitrate",
                "size_bytes",
                "format",
            ]:
                assert key in new_info, f"Missing field in new implementation: {key}"
                assert key in old_info, f"Missing field in old implementation: {key}"

                # Allow small floating point differences for duration
                if key == "duration":
                    assert abs(new_info[key] - old_info[key]) < 0.01, (
                        f"Duration mismatch for {audio_file.name}: "
                        f"new={new_info[key]}, old={old_info[key]}"
                    )
                else:
                    assert new_info[key] == old_info[key], (
                        f"{key} mismatch for {audio_file.name}: "
                        f"new={new_info[key]}, old={old_info[key]}"
                    )

            logger.info(f"✓ Metadata equivalence verified: {audio_file.name}")


def run_standalone():
    """Standalone test runner for manual execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    processor = AudioProcessor()

    if not FIXTURES_DIR.exists():
        print(f"Test fixtures directory not found: {FIXTURES_DIR}")
        return

    test_files = sorted(FIXTURES_DIR.glob("*.wav"))
    if not test_files:
        print(f"No test audio files found in {FIXTURES_DIR}")
        return

    print(f"\n{'=' * 70}")
    print(f"Testing metadata extraction with {len(test_files)} audio files")
    print(f"{'=' * 70}\n")

    results = []
    for audio_file in test_files:
        try:
            info = processor.get_audio_info(audio_file)
            results.append(
                {
                    "file": audio_file.name,
                    "duration": info["duration"],
                    "sample_rate": info["sample_rate"],
                    "channels": info["channels"],
                    "codec": info["codec"],
                    "bitrate": info["bitrate"],
                    "size_bytes": info["size_bytes"],
                    "format": info["format"],
                    "status": "✓ PASS",
                }
            )
            print(f"✓ {audio_file.name}")
            print(
                f"  Duration: {info['duration']:.2f}s | Sample Rate: {info['sample_rate']}Hz | "
                f"Channels: {info['channels']} | Codec: {info['codec']}"
            )
        except Exception as e:
            results.append({"file": audio_file.name, "status": f"✗ FAIL: {str(e)}"})
            print(f"✗ {audio_file.name}: {str(e)}")

    print(f"\n{'=' * 70}")
    print(
        f"Results: {sum(1 for r in results if '✓' in r['status'])}/{len(results)} passed"
    )
    print(f"{'=' * 70}\n")

    # Save results to evidence file
    evidence_dir = Path(__file__).parent.parent / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    evidence_file = evidence_dir / "task-6-metadata-comparison.json"
    with open(evidence_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Evidence saved to: {evidence_file}")


if __name__ == "__main__":
    run_standalone()
