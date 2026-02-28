import json
import logging
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Union
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Union

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class AudioProcessorError(Exception):
    """Base exception for audio processing errors."""
    pass


class CommandExecutionError(AudioProcessorError):
    """Raised when subprocess command execution fails."""
    pass


class CommandTimeoutError(AudioProcessorError):
    """Raised when subprocess command times out."""
    pass


def run_command(
    command: list[str],
    timeout: int = 300,
    description: str = "",
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """
    Execute a subprocess command with timeout and error handling.
    
    Args:
        command: List of command arguments (e.g., ['ffmpeg', '-i', 'input.wav'])
        timeout: Timeout in seconds (default 300s for processing, 30s for probe)
        description: Human-readable description of the command for logging
        check: If True, raise CommandExecutionError on non-zero exit code
        
    Returns:
        subprocess.CompletedProcess with stdout/stderr captured
        
    Raises:
        CommandTimeoutError: If command exceeds timeout
        CommandExecutionError: If command fails and check=True
        ValueError: If command is not a list or is empty
    """
    # Validate input
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty list")
    
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError(f"timeout must be positive integer, got {timeout}")
    
    # Log command execution at debug level
    cmd_str = " ".join(str(arg) for arg in command)
    if description:
        logger.debug(f"Executing: {description}")
    logger.debug(f"Command: {cmd_str}")
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # We handle errors manually for better control
        )
        
        # Log output at debug level
        if result.stdout:
            logger.debug(f"Command stdout: {result.stdout[:500]}")
        if result.stderr:
            logger.debug(f"Command stderr: {result.stderr[:500]}")
        
        # Check return code if requested
        if check and result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else f"Exit code {result.returncode}"
            logger.error(f"Command failed: {cmd_str}")
            logger.error(f"Error: {error_msg}")
            raise CommandExecutionError(f"Command failed: {error_msg}")
        
        logger.debug(f"Command succeeded with exit code {result.returncode}")
        return result
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after {timeout}s: {cmd_str}")
        raise CommandTimeoutError(f"Command timed out after {timeout}s") from e
    except CommandExecutionError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error executing command: {e}")
        raise CommandExecutionError(f"Command execution error: {str(e)}") from e


def build_ffmpeg_command(
    input_file: str,
    output_file: str,
    filters: Optional[list[str]] = None,
    codec_args: Optional[dict[str, Any]] = None,
    extra_args: Optional[list[str]] = None,
) -> list[str]:
    """
    Build an FFmpeg command with proper argument ordering.
    
    Args:
        input_file: Path to input audio file
        output_file: Path to output audio file
        filters: List of filter strings (e.g., ['aresample=16000', 'aformat=mono'])
        codec_args: Dictionary of codec arguments (e.g., {'acodec': 'mp3', 'ab': '128k'})
        extra_args: Additional arguments to append before output file
        
    Returns:
        List of command arguments ready for subprocess.run()
    """
    command = ["ffmpeg", "-i", input_file]
    
    # Add filters if provided
    if filters:
        filter_chain = ",".join(filters)
        command.extend(["-af", filter_chain])
    
    # Add codec arguments
    if codec_args:
        for key, value in codec_args.items():
            command.extend([f"-{key}", str(value)])
    
    # Add extra arguments
    if extra_args:
        command.extend(extra_args)
    
    # Add output file and overwrite flag
    command.extend(["-y", output_file])
    
    return command


def build_sox_command(
    input_file: str,
    output_file: str,
    effects: Optional[list[str]] = None,
    rate: Optional[int] = None,
    channels: Optional[int] = None,
) -> list[str]:
    """
    Build a SoX command with proper argument ordering.
    
    Args:
        input_file: Path to input audio file
        output_file: Path to output audio file
        effects: List of effect strings (e.g., ['silence 1 0.1 1%', 'norm'])
        rate: Target sample rate in Hz
        channels: Target number of channels (1 for mono, 2 for stereo)
        
    Returns:
        List of command arguments ready for subprocess.run()
    """
    command = ["sox", input_file, output_file]
    
    # Add rate conversion if specified
    if rate:
        command.extend(["rate", str(rate)])
    
    # Add channel conversion if specified
    if channels:
        if channels == 1:
            command.append("remix -")
        elif channels == 2:
            command.append("remix 1,2")
    
    # Add effects
    if effects:
        command.extend(effects)
    
    return command

def check_ffmpeg_available() -> bool:
    """
    Check if ffmpeg binary is available in system PATH.
    
    Returns:
        True if ffmpeg is found and executable, False otherwise
    """
    ffmpeg_path = shutil.which("ffmpeg")
    return ffmpeg_path is not None


def check_sox_available() -> bool:
    """
    Check if sox binary is available in system PATH.
    
    Returns:
        True if sox is found and executable, False otherwise
    """
    sox_path = shutil.which("sox")
    return sox_path is not None


def get_ffmpeg_version() -> Optional[str]:
    """
    Get the version string of the ffmpeg binary.
    
    Returns:
        Version string if ffmpeg is available, None otherwise
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return None
    
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            # First line contains version info
            return result.stdout.split("\n")[0]
        return None
    except Exception as e:
        logger.debug(f"Failed to get ffmpeg version: {e}")
        return None


def get_sox_version() -> Optional[str]:
    """
    Get the version string of the sox binary.
    
    Returns:
        Version string if sox is available, None otherwise
    """
    sox_path = shutil.which("sox")
    if not sox_path:
        return None
    
    try:
        result = subprocess.run(
            [sox_path, "-V"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.debug(f"Failed to get sox version: {e}")
        return None


class AudioProcessor:
    """
    Audio preprocessing pipeline using FFmpeg for advanced operations.

    Provides methods for silence trimming, downsampling, and encoding
    to various formats while maintaining audio quality and metadata.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the AudioProcessor.

        Args:
            config: Optional configuration dictionary for processor settings
        """
        self.config = config or {}
        self._validate_cli_tools_availability()

        # Default processing parameters
        self.default_params = {
            "silence_threshold_db": -50.0,  # dB level for silence detection
            "silence_duration": 0.5,  # Minimum silence duration in seconds
            "target_sample_rate": 16000,  # Common for transcription systems
            "mp3_bitrate": "128k",  # Default MP3 encoding bitrate
            "fade_duration": 0.1,  # Crossfade duration for smooth cuts
        }

        # Thread safety
        self._lock = threading.RLock()  # Reentrant: pipeline calls individual methods
        logger.info("AudioProcessor initialized")

    def _validate_cli_tools_availability(self) -> None:
        """Validate that required CLI tools (ffmpeg/sox) are available for processing.
        
        Raises:
            RuntimeError: If required binaries are not found in system PATH
        """
        # Check ffmpeg availability
        if not check_ffmpeg_available():
            raise RuntimeError(
                "FFmpeg binary not found in system PATH. "
                "Please install FFmpeg system package. "
                "On Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                "On Fedora/RHEL: sudo dnf install ffmpeg\n"
                "On macOS: brew install ffmpeg"
            )
        
        # Log ffmpeg version
        ffmpeg_version = get_ffmpeg_version()
        if ffmpeg_version:
            logger.info(f"FFmpeg available: {ffmpeg_version}")
        else:
            logger.warning("FFmpeg found but could not determine version")
        
        # Check sox availability (optional but recommended)
        if not check_sox_available():
            logger.warning(
                "SoX binary not found in system PATH. "
                "Some audio processing features may be unavailable. "
                "Install with: sudo apt-get install sox (Ubuntu/Debian) "
                "or brew install sox (macOS)"
            )
        else:
            sox_version = get_sox_version()
            if sox_version:
                logger.info(f"SoX available: {sox_version}")
        
        logger.debug("CLI tools availability validated")

    def trim_silence(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        threshold_db: Optional[float] = None,
        min_silence_duration: Optional[float] = None,
    ) -> Path:
        """
        Remove silence from the beginning and end of an audio file.

        Uses FFmpeg's silenceremove filter to detect and remove silent
        segments based on RMS energy levels.

        Args:
            input_path: Path to input audio file
            output_path: Optional output path (auto-generated if None)
            threshold_db: Silence detection threshold in dB
            min_silence_duration: Minimum duration of silence to remove

        Returns:
            Path to the processed audio file

        Raises:
            FileNotFoundError: If input file doesn't exist
            ffmpeg.Error: If processing fails
        """
        with self._lock:
            # Parameter defaults
            threshold_db = threshold_db or self.default_params["silence_threshold_db"]
            min_silence_duration = (
                min_silence_duration or self.default_params["silence_duration"]
            )

            # Ensure numeric types
            if not isinstance(threshold_db, (int, float)):
                raise ValueError(f"threshold_db must be numeric, got {type(threshold_db)}")
            if not isinstance(min_silence_duration, (int, float)):
                raise ValueError(f"min_silence_duration must be numeric, got {type(min_silence_duration)}")

            # Validate input
            input_path = Path(input_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # Generate output path if not provided
            if output_path is None:
                output_path = self._generate_output_path(input_path, suffix="_trimmed")
            else:
                output_path = Path(output_path)

            logger.info(f"Trimming silence from {input_path} -> {output_path}")

            # Read audio data for RMS analysis
            try:
                audio_data, original_sample_rate = sf.read(input_path)
                logger.debug(f"Loaded audio: {audio_data.shape}, sample_rate={original_sample_rate}")
            except Exception as e:
                logger.error(f"Failed to read audio file {input_path}: {e}")
                raise

            # Ensure mono for RMS calculation (use first channel if stereo)
            if len(audio_data.shape) > 1:
                audio_mono = audio_data[:, 0]
                logger.debug("Converted stereo to mono for RMS analysis")
            else:
                audio_mono = audio_data

            # Calculate RMS in sliding windows
            window_size = int(min_silence_duration * original_sample_rate)
            if window_size == 0:
                window_size = 1

            # Convert threshold from dB to linear scale
            # RMS threshold = 10^(dB/20)
            linear_threshold = 10 ** (threshold_db / 20.0)
            logger.debug(f"Silence threshold: {threshold_db} dB = {linear_threshold:.6f} linear")

            # Find start point (first window above threshold)
            start_sample = 0
            for i in range(0, len(audio_mono) - window_size, window_size // 4):
                window = audio_mono[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                if rms > linear_threshold:
                    start_sample = i
                    logger.debug(f"Found audio start at sample {start_sample} (RMS: {rms:.6f})")
                    break

            # Find end point (last window above threshold, searching backwards)
            end_sample = len(audio_mono)
            for i in range(len(audio_mono) - window_size, 0, -window_size // 4):
                if i + window_size > len(audio_mono):
                    continue
                window = audio_mono[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                if rms > linear_threshold:
                    end_sample = i + window_size
                    logger.debug(f"Found audio end at sample {end_sample} (RMS: {rms:.6f})")
                    break

            # Trim the audio data
            if start_sample >= end_sample:
                logger.warning("No audio content found above threshold, saving original")
                trimmed_audio = audio_data
            else:
                trimmed_audio = audio_data[start_sample:end_sample]
                duration_removed = ((len(audio_data) - len(trimmed_audio)) / original_sample_rate)
                logger.info(f"Trimmed {duration_removed:.2f}s of silence")

            # Write the trimmed audio
            try:
                sf.write(output_path, trimmed_audio, original_sample_rate)
                logger.info(f"Trimmed audio saved to {output_path}")
            except Exception as e:
                logger.error(f"Failed to write trimmed audio: {e}")
                raise

            return output_path

    def downsample(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        target_rate: Optional[int] = None,
        filter_type: str = "high_quality",
        channels: int = 1,
    ) -> Path:
        """
        Downsample audio to a target sample rate and channel count.

        Uses high-quality resampling algorithms to maintain audio fidelity
        while reducing file size and processing requirements.

        Args:
            input_path: Path to input audio file
            output_path: Optional output path (auto-generated if None)
            target_rate: Target sample rate in Hz
            filter_type: Resampling filter quality ('fast', 'medium', 'high_quality')
            channels: Target number of channels (default 1 for mono)

        Returns:
            Path to the downsampled audio file

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If target_rate is invalid
            ffmpeg.Error: If processing fails
        """
        with self._lock:
            # Parameter defaults
            target_rate = target_rate or self.default_params["target_sample_rate"]

            # Ensure numeric type
            if not isinstance(target_rate, int):
                raise ValueError(f"target_rate must be an integer, got {type(target_rate)}")
            # Validate input
            input_path = Path(input_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            if target_rate <= 0:
                raise ValueError(f"Invalid target sample rate: {target_rate}")

            # Generate output path if not provided
            if output_path is None:
                output_path = self._generate_output_path(
                    input_path, suffix=f"_{target_rate}Hz"
                )
            else:
                output_path = Path(output_path)

            logger.info(
                f"Downsampling {input_path} to {target_rate}Hz ({channels}ch) -> {output_path}"
            )

            # Get current audio info
            try:
                current_info = self.get_audio_info(input_path)
                current_rate = current_info['sample_rate']
                current_channels = current_info['channels']
                logger.debug(f"Current audio: {current_rate}Hz, {current_channels}ch")
            except Exception as e:
                logger.error(f"Failed to get audio info: {e}")
                raise

            # Skip resampling if already at target rate and channels
            if current_rate == target_rate and current_channels == channels:
                logger.info(f"Audio already at target rate {target_rate}Hz and {channels}ch")
                # Copy file to output path if different
                if input_path != output_path:
                    import shutil
                    shutil.copy2(input_path, output_path)
                return output_path

            # Configure resampling filter based on quality
            filter_configs = {
                'fast': ['aresample=resampler=swr:linear_interp=0'],
                'medium': ['aresample=resampler=swr:linear_interp=1'], 
                'high_quality': ['aresample=resampler=swr:linear_interp=1:cutoff=0.98']
            }

            filters = filter_configs.get(filter_type, filter_configs['high_quality'])
            logger.debug(f"Using filters: {filters}")

            try:
                # Build FFmpeg command for resampling using subprocess
                codec_args = {'acodec': 'pcm_s16le', 'ar': target_rate, 'ac': channels}
                command = build_ffmpeg_command(
                    str(input_path),
                    str(output_path),
                    filters=filters,
                    codec_args=codec_args
                )

                # Run resampling using subprocess
                logger.debug(f"Running FFmpeg resampling: {current_rate}Hz -> {target_rate}Hz")
                run_command(command, timeout=300, description="Audio resampling")

                # Verify output
                output_info = self.get_audio_info(output_path)
                actual_rate = output_info['sample_rate']
                if actual_rate != target_rate:
                    logger.warning(f"Output sample rate {actual_rate}Hz != target {target_rate}Hz")

                logger.info(f"Downsampling completed: {current_rate}Hz -> {actual_rate}Hz")
                return output_path

            except CommandExecutionError as e:
                logger.error(f"FFmpeg resampling failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during resampling: {e}")
                raise

    def encode_mp3(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        bitrate: Optional[str] = None,
        quality: str = "standard",
    ) -> Path:
        """
        Encode audio to MP3 format with configurable quality settings.

        Uses FFmpeg's LAME encoder for high-quality MP3 encoding with
        optimized parameters for speech/music content.

        Args:
            input_path: Path to input audio file
            output_path: Optional output path (auto-generated if None)
            bitrate: Target bitrate (e.g., '128k', '192k', '256k')
            quality: Encoding quality preset ('fast', 'standard', 'high')

        Returns:
            Path to the encoded MP3 file

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If bitrate format is invalid
            ffmpeg.Error: If encoding fails
        """
        with self._lock:
            # Parameter defaults
            bitrate = bitrate or self.default_params["mp3_bitrate"]

            # Ensure bitrate is a string
            if not isinstance(bitrate, str):
                raise ValueError(f"bitrate must be a string, got {type(bitrate)}")
            # Validate input
            input_path = Path(input_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # Generate output path if not provided
            if output_path is None:
                output_path = self._generate_output_path(
                    input_path, suffix="", extension=".mp3"
                )
            else:
                output_path = Path(output_path)

            logger.info(f"Encoding {input_path} to MP3 @ {bitrate} -> {output_path}")

            # Build FFmpeg pipeline for MP3 encoding with resampling and mono conversion
            try:
                # Create ffmpeg input stream
                input_stream = ffmpeg.input(str(input_path))
                
                # Get input audio info for proper processing
                probe = ffmpeg.probe(str(input_path))
                audio_stream = next(stream for stream in probe['streams'] if stream['codec_type'] == 'audio')
                input_channels = int(audio_stream['channels'])
                
                # Apply audio processing pipeline:
                # 1. Resample to 16kHz first
                # 2. Convert to mono (sum channels if stereo)
                # 3. Encode as MP3
                stream = input_stream.audio
                
                # Resample to 16kHz
                stream = stream.filter('aresample', 16000)
                
                # Output as MP3 with CBR encoding
                # Use ac=1 output option for mono conversion (avoids filter escaping issues)
                output_args = {
                    'acodec': 'mp3',
                    'audio_bitrate': bitrate,
                    'ac': 1,  # Force mono output
                    'map_metadata': '-1',  # Strip all metadata/ID3 tags
                    'write_id3v2': '0',   # Disable ID3v2 tags
                    'fflags': '+bitexact', # Use bitexact mode to avoid encoder metadata
                }
                output_stream = stream.output(
                    str(output_path),
                    **output_args
                )
                
                # Execute the pipeline
                # Execute the pipeline with verbose output for debugging
                output_stream.overwrite_output().run()
                
                logger.info(f"Successfully encoded MP3: {output_path}")
                return output_path
                
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg encoding failed: {e}")
                raise
            except Exception as e:
                logger.error(f"MP3 encoding error: {e}")
                raise

    def process_pipeline(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        operations: Optional[list] = None,
    ) -> Path:
        """
        Execute a complete processing pipeline with multiple operations.

        Chains together multiple processing steps efficiently using FFmpeg's
        filter graph capabilities for optimal performance.

        Args:
            input_path: Path to input audio file
            output_path: Optional final output path
            operations: List of operation dictionaries to perform

        Returns:
            Path to the final processed audio file

        Example:
            operations = [
                {'op': 'trim_silence', 'threshold_db': -45.0},
                {'op': 'downsample', 'target_rate': 16000},
                {'op': 'encode_mp3', 'bitrate': '128k'}
            ]
        """
        with self._lock:
            operations = operations or []

            if not operations:
                logger.warning("No operations specified for pipeline")
                return Path(input_path)

            logger.info(f"Starting pipeline with {len(operations)} operations")

            current_path = Path(input_path)

            # Process each operation in sequence
            for i, operation in enumerate(operations):
                op_type = operation.get('op')
                logger.debug(f"Processing operation {i+1}/{len(operations)}: {op_type}")

                # Generate intermediate file path if not the last operation
                if i == len(operations) - 1 and output_path:
                    next_path = Path(output_path)
                else:
                    suffix = f"_step{i+1}_{op_type}"
                    next_path = self._generate_output_path(current_path, suffix)

                # Execute the operation
                if op_type == 'trim_silence':
                    kwargs = {k: v for k, v in operation.items() if k != 'op'}
                    current_path = self.trim_silence(current_path, next_path, **kwargs)
                elif op_type == 'downsample':
                    kwargs = {k: v for k, v in operation.items() if k != 'op'}
                    current_path = self.downsample(current_path, next_path, **kwargs)
                elif op_type == 'encode_mp3':
                    kwargs = {k: v for k, v in operation.items() if k != 'op'}
                    current_path = self.encode_mp3(current_path, next_path, **kwargs)
                else:
                    logger.error(f"Unknown operation: {op_type}")
                    raise ValueError(f"Unsupported operation: {op_type}")

                logger.info(f"Completed {op_type}: {current_path}")

            # Clean up intermediate files if we created any
            if len(operations) > 1:
                # Keep only the final output, remove intermediate files
                intermediate_files = []
                for i in range(len(operations) - 1):
                    op_type = operations[i].get('op')
                    suffix = f"_step{i+1}_{op_type}"
                    temp_path = self._generate_output_path(Path(input_path), suffix)
                    if temp_path.exists() and temp_path != current_path:
                        intermediate_files.append(temp_path)

                for temp_file in intermediate_files:
                    try:
                        temp_file.unlink()
                        logger.debug(f"Cleaned up intermediate file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up {temp_file}: {e}")

            logger.info(f"Pipeline completed: {input_path} -> {current_path}")
            return current_path

    def preprocess_for_transcription(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        silence_threshold_db: Optional[float] = None,
        target_sample_rate: Optional[int] = None,
    ) -> Path:
        """
        Complete preprocessing pipeline for transcription optimization.

        Applies silence trimming and downsampling in sequence to prepare
        audio files for transcription systems like Whisper.

        Args:
            input_path: Path to input audio file
            output_path: Optional output path (auto-generated if None)
            silence_threshold_db: Silence detection threshold in dB
            target_sample_rate: Target sample rate in Hz

        Returns:
            Path to the preprocessed audio file
        """
        # Generate output path if not provided
        if output_path is None:
            input_path_obj = Path(input_path)
            output_path = self._generate_output_path(
                input_path_obj, suffix="_preprocessed"
            )

        # Define the processing pipeline
        operations = [
            {
                'op': 'trim_silence',
                'threshold_db': silence_threshold_db,
            },
            {
                'op': 'downsample', 
                'target_rate': target_sample_rate,
                'filter_type': 'high_quality'
            }
        ]

        logger.info(f"Starting transcription preprocessing pipeline")
        return self.process_pipeline(input_path, output_path, operations)
    def _generate_output_path(
        self, input_path: Path, suffix: str = "", extension: Optional[str] = None
    ) -> Path:
        """Generate an output file path based on input path and processing type."""
        if extension is None:
            extension = input_path.suffix

        stem = input_path.stem + suffix
        return input_path.parent / f"{stem}{extension}"

    def get_audio_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get detailed information about an audio file using ffprobe CLI.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary containing audio metadata and properties:
            - duration: float (seconds)
            - sample_rate: int (Hz)
            - channels: int
            - codec: str (codec name)
            - bitrate: int (bits per second)
            - size_bytes: int (file size)
            - format: str (format name)

        Raises:
            FileNotFoundError: If file does not exist
            CommandExecutionError: If ffprobe fails
            CommandTimeoutError: If ffprobe times out
        """
        file_path = Path(file_path)

        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            # Build ffprobe command to extract JSON metadata
            command = [
                "ffprobe",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                str(file_path)
            ]

            # Execute ffprobe with 30s timeout (probe operations are fast)
            result = run_command(
                command,
                timeout=30,
                description=f"Extract metadata from {file_path.name}",
                check=True
            )

            # Parse JSON output
            probe_data = json.loads(result.stdout)

            # Find audio stream
            audio_stream = None
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break

            if audio_stream is None:
                raise CommandExecutionError(f"No audio stream found in {file_path}")

            # Extract format information
            format_info = probe_data.get("format", {})

            # Parse metadata with safe defaults for missing fields
            duration = float(format_info.get("duration", 0.0))
            sample_rate = int(audio_stream.get("sample_rate", 0))
            channels = int(audio_stream.get("channels", 0))
            codec = audio_stream.get("codec_name", "unknown")
            bitrate = int(format_info.get("bit_rate", 0))
            size_bytes = int(format_info.get("size", 0))
            format_name = format_info.get("format_name", "unknown")

            logger.debug(
                f"Audio info: {sample_rate}Hz, {channels}ch, {duration:.2f}s, {codec}, {bitrate}bps"
            )

            return {
                "duration": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "codec": codec,
                "bitrate": bitrate,
                "size_bytes": size_bytes,
                "format": format_name,
            }

        except FileNotFoundError:
            raise
        except CommandExecutionError:
            raise
        except CommandTimeoutError:
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe JSON output: {e}")
            raise CommandExecutionError(f"Invalid ffprobe output: {str(e)}") from e
        except Exception as e:
            logger.error(f"Failed to get audio info for {file_path}: {e}")
            raise CommandExecutionError(f"Failed to extract audio metadata: {str(e)}") from e

    def _get_quality_params(self, quality: str) -> Dict[str, Any]:
        """Get FFmpeg quality parameters based on quality preset."""
        quality_presets = {
            "fast": {
                "q:a": "5",  # Variable bitrate quality
                "compression_level": "1"
            },
            "standard": {
                "q:a": "2",  # Higher quality VBR
                "compression_level": "6"
            },
            "high": {
                "q:a": "0",  # Highest quality VBR
                "compression_level": "9"
            }
        }
        
        return quality_presets.get(quality, quality_presets["standard"])

    def convert_to_pcm(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        codec: str = "pcm_s16le",
        channels: int = 1,
        sample_rate: Optional[int] = None,
    ) -> Path:
        """
        Convert audio to PCM format with specified codec and channel count.

        Uses FFmpeg CLI to convert audio files to PCM format with high fidelity.

        Args:
            input_path: Path to input audio file
            output_path: Optional output path (auto-generated if None)
            codec: PCM codec to use (pcm_s16le, pcm_s24le, pcm_f32le)
            channels: Target number of channels (default 1 for mono)
            sample_rate: Optional target sample rate (preserves original if None)

        Returns:
            Path to the converted PCM audio file

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If codec or channels are invalid
            CommandExecutionError: If conversion fails
        """
        with self._lock:
            # Validate inputs
            input_path = Path(input_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # Validate codec
            supported_codecs = {"pcm_s16le", "pcm_s24le", "pcm_f32le"}
            if codec not in supported_codecs:
                raise ValueError(f"Unsupported codec: {codec}. Supported: {supported_codecs}")

            # Validate channels
            if not isinstance(channels, int) or channels <= 0:
                raise ValueError(f"channels must be a positive integer, got {channels}")

            # Validate sample_rate if provided
            if sample_rate is not None and (not isinstance(sample_rate, int) or sample_rate <= 0):
                raise ValueError(f"sample_rate must be a positive integer, got {sample_rate}")

            # Generate output path if not provided
            if output_path is None:
                output_path = self._generate_output_path(
                    input_path, suffix=f"_{codec}_{channels}ch"
                )
            else:
                output_path = Path(output_path)

            logger.info(f"Converting {input_path} to {codec} ({channels}ch) -> {output_path}")

            try:
                # Build codec arguments
                codec_args = {'acodec': codec, 'ac': channels}
                if sample_rate is not None:
                    codec_args['ar'] = sample_rate

                # Build FFmpeg command for PCM conversion using subprocess
                command = build_ffmpeg_command(
                    str(input_path),
                    str(output_path),
                    codec_args=codec_args
                )

                # Run conversion using subprocess
                logger.debug(f"Running FFmpeg PCM conversion: {codec} ({channels}ch)")
                run_command(command, timeout=300, description="Audio PCM conversion")

                logger.info(f"PCM conversion completed: {input_path} -> {output_path}")
                return output_path

            except CommandExecutionError as e:
                logger.error(f"FFmpeg PCM conversion failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during PCM conversion: {e}")
                raise

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        logger.debug("AudioProcessor context manager cleanup")
