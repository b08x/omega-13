"""Tests for PCM format conversion functionality."""

import tempfile
import unittest
from pathlib import Path

from src.omega13.audio_processor import AudioProcessor, CommandExecutionError


class TestFormatConversion(unittest.TestCase):
    """Test cases for PCM format conversion."""

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

    def test_convert_to_pcm_s16le_mono(self):
        """Test converting to pcm_s16le mono format."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output_s16le_mono.wav"
            result_path = self.processor.convert_to_pcm(
                self.stereo_48k, output_path, codec="pcm_s16le", channels=1
            )

            # Verify output file exists
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path, output_path)

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "pcm_s16le")
            self.assertEqual(info["channels"], 1)
            self.assertEqual(info["sample_rate"], 48000)  # Preserved from input

    def test_convert_to_pcm_s24le_stereo(self):
        """Test converting to pcm_s24le stereo format."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output_s24le_stereo.wav"
            result_path = self.processor.convert_to_pcm(
                self.mono_16k, output_path, codec="pcm_s24le", channels=2
            )

            # Verify output file exists
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path, output_path)

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "pcm_s24le")
            self.assertEqual(info["channels"], 2)
            self.assertEqual(info["sample_rate"], 16000)  # Preserved from input

    def test_convert_to_pcm_f32le_with_resampling(self):
        """Test converting to pcm_f32le with sample rate conversion."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output_f32le_resampled.wav"
            result_path = self.processor.convert_to_pcm(
                self.stereo_48k,
                output_path,
                codec="pcm_f32le",
                channels=1,
                sample_rate=16000,
            )

            # Verify output file exists
            self.assertTrue(result_path.exists())
            self.assertEqual(result_path, output_path)

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "pcm_f32le")
            self.assertEqual(info["channels"], 1)
            self.assertEqual(info["sample_rate"], 16000)  # Resampled

    def test_convert_to_pcm_auto_output_path(self):
        """Test PCM conversion with auto-generated output path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "input.wav"
            # Copy test file to temp directory
            import shutil

            shutil.copy2(self.mono_16k, input_path)

            # Convert without specifying output path
            result_path = self.processor.convert_to_pcm(
                input_path, codec="pcm_s16le", channels=1
            )

            # Verify output file exists and has expected naming pattern
            self.assertTrue(result_path.exists())
            self.assertIn("pcm_s16le_1ch", str(result_path))

            # Verify audio properties
            info = self.processor.get_audio_info(result_path)
            self.assertEqual(info["codec"], "pcm_s16le")
            self.assertEqual(info["channels"], 1)

    def test_convert_to_pcm_invalid_codec(self):
        """Test PCM conversion with invalid codec raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.wav"
            with self.assertRaises(ValueError) as context:
                self.processor.convert_to_pcm(
                    self.mono_16k, output_path, codec="invalid_codec", channels=1
                )
            self.assertIn("Unsupported codec", str(context.exception))

    def test_convert_to_pcm_invalid_channels(self):
        """Test PCM conversion with invalid channels raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.wav"
            with self.assertRaises(ValueError) as context:
                self.processor.convert_to_pcm(
                    self.mono_16k,
                    output_path,
                    codec="pcm_s16le",
                    channels=0,  # Invalid - must be positive
                )
            self.assertIn("channels must be a positive integer", str(context.exception))

    def test_convert_to_pcm_invalid_sample_rate(self):
        """Test PCM conversion with invalid sample rate raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.wav"
            with self.assertRaises(ValueError) as context:
                self.processor.convert_to_pcm(
                    self.mono_16k,
                    output_path,
                    codec="pcm_s16le",
                    channels=1,
                    sample_rate=-1,  # Invalid - must be positive
                )
            self.assertIn(
                "sample_rate must be a positive integer", str(context.exception)
            )

    def test_convert_to_pcm_nonexistent_input(self):
        """Test PCM conversion with nonexistent input file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "nonexistent.wav"
            output_path = Path(tmp_dir) / "output.wav"
            with self.assertRaises(FileNotFoundError) as context:
                self.processor.convert_to_pcm(
                    input_path, output_path, codec="pcm_s16le", channels=1
                )
            self.assertIn("Input file not found", str(context.exception))


if __name__ == "__main__":
    unittest.main()
