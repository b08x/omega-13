"""Tests for MP3 encoding functionality."""

import tempfile
import unittest
from pathlib import Path

from src.omega13.audio_processor import AudioProcessor, CommandExecutionError


class TestMP3Encoding(unittest.TestCase):
    """Test cases for MP3 encoding."""

    def setUp(self):
        """Set up test fixtures."""
        self.processor = AudioProcessor()
        self.test_audio_dir = Path(__file__).parent / "fixtures" / "audio"

        # Test files
        self.mono_16k = self.test_audio_dir / "mono_16000_3s.wav"
        self.stereo_48k = self.test_audio_dir / "stereo_48000_2s.wav"

        # Verify test files exist
        for file_path in [self.mono_16k, self.stereo_48k]:
            if not file_path.exists():
                raise FileNotFoundError(f"Test audio file not found: {file_path}")

    def test_encode_mp3_default_bitrate(self):
        """Test MP3 encoding with default bitrate."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output_default.mp3"
            result_path = self.processor.encode_mp3(self.stereo_48k, output_path)

            # Verify output file exists
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path, output_path)

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "mp3")
            self.assertEqual(info["channels"], 1)  # Mono output
            self.assertEqual(info["sample_rate"], 16000)  # Resampled to 16kHz

    def test_encode_mp3_custom_bitrate(self):
        """Test MP3 encoding with custom bitrate."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output_192k.mp3"
            result_path = self.processor.encode_mp3(
                self.mono_16k, output_path, bitrate="192k"
            )

            # Verify output file exists
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path, output_path)

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "mp3")
            self.assertEqual(info["channels"], 1)  # Mono output
            self.assertEqual(info["sample_rate"], 16000)  # Resampled to 16kHz

    def test_encode_mp3_auto_output_path(self):
        """Test MP3 encoding with auto-generated output path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.wav"
            # Copy test file to temp directory
            import shutil

            shutil.copy2(self.mono_16k, input_path)

            # Encode without specifying output path
            result_path = self.processor.encode_mp3(input_path)

            # Verify output file exists and has expected naming pattern
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path.suffix, ".mp3")

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "mp3")
            self.assertEqual(info["channels"], 1)  # Mono output
            self.assertEqual(info["sample_rate"], 16000)  # Resampled to 16kHz

    def test_encode_mp3_invalid_bitrate_type(self):
        """Test MP3 encoding with invalid bitrate type raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.mp3"
            with self.assertRaises(ValueError) as context:
                self.processor.encode_mp3(
                    self.mono_16k,
                    output_path,
                    bitrate=128,  # Invalid - should be string
                )
            self.assertIn("bitrate must be a string", str(context.exception))

    def test_encode_mp3_nonexistent_input(self):
        """Test MP3 encoding with nonexistent input file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "nonexistent.wav"
            output_path = Path(tmp_dir) / "output.mp3"
            with self.assertRaises(FileNotFoundError) as context:
                self.processor.encode_mp3(input_path, output_path)
            self.assertIn("Input file not found", str(context.exception))


if __name__ == "__main__":
    unittest.main()
