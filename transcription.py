"""
Audio transcription module using faster-whisper.

Provides thread-safe, asynchronous transcription of audio files with
progress callbacks and error handling. Designed for integration with
Textual TUI applications.
"""

from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)


class TranscriptionStatus(Enum):
    """Enumeration of transcription states."""
    IDLE = "idle"
    LOADING_MODEL = "loading_model"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class TranscriptionResult:
    """Container for transcription output."""
    text: str
    status: TranscriptionStatus
    error: Optional[str] = None
    segments: Optional[list[dict]] = None
    language: Optional[str] = None
    duration: Optional[float] = None


class TranscriptionService:
    """
    Thread-safe audio transcription service using faster-whisper.

    Handles model loading, caching, and asynchronous transcription with
    progress callbacks. Designed for integration with Textual TUI apps.

    Example:
        service = TranscriptionService(model_size="base")

        def on_complete(result):
            print(f"Transcription: {result.text}")

        service.transcribe_async(
            Path("audio.wav"),
            callback=on_complete,
            progress_callback=lambda p: print(f"Progress: {p:.0%}")
        )
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        """
        Initialize transcription service.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large, large-v3-turbo)
            device: Target device ("cpu", "cuda", "auto")
            compute_type: Precision ("int8", "float16", "float32", "auto")
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._model_lock = threading.Lock()
        self._is_loading = False

    def _check_cuda_available(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def load_model(self) -> tuple[bool, Optional[str]]:
        """
        Load Whisper model into memory (thread-safe).

        Returns:
            (success: bool, error_message: Optional[str])
        """
        with self._model_lock:
            if self.model is not None:
                return True, None

            if self._is_loading:
                return False, "Model already loading"

            self._is_loading = True

        try:
            # Check if faster-whisper is available
            from faster_whisper import WhisperModel

            # Auto-detect device if requested
            device = self.device
            compute = self.compute_type

            if device == "auto":
                device = "cuda" if self._check_cuda_available() else "cpu"

            if compute == "auto":
                compute = "int8" if device == "cpu" else "float16"

            # Load model with error handling
            logger.info(f"Loading Whisper model: {self.model_size} on {device} with {compute}")
            self.model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute
            )

            logger.info(f"Model loaded successfully: {self.model_size}")
            return True, None

        except ImportError:
            error = "faster-whisper not installed. Install with: pip install faster-whisper"
            logger.error(error)
            return False, error

        except Exception as e:
            error = f"Failed to load model: {str(e)}"
            logger.error(error)
            return False, error

        finally:
            self._is_loading = False

    def transcribe_async(
        self,
        audio_path: Path,
        callback: Callable[[TranscriptionResult], None],
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> threading.Thread:
        """
        Transcribe audio file asynchronously in background thread.

        Args:
            audio_path: Path to WAV file
            callback: Function to call with final result
            progress_callback: Optional function for progress updates (0.0-1.0)

        Returns:
            Thread object (already started)
        """
        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(audio_path, callback, progress_callback),
            daemon=True
        )
        thread.start()
        return thread

    def _transcribe_worker(
        self,
        audio_path: Path,
        callback: Callable[[TranscriptionResult], None],
        progress_callback: Optional[Callable[[float], None]]
    ):
        """Internal worker function for transcription thread."""
        try:
            # Ensure model is loaded
            if self.model is None:
                if progress_callback:
                    progress_callback(0.0)

                success, error = self.load_model()
                if not success:
                    callback(TranscriptionResult(
                        text="",
                        status=TranscriptionStatus.ERROR,
                        error=error
                    ))
                    return

            # Update progress: model loaded
            if progress_callback:
                progress_callback(0.1)

            # Validate audio file
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            if audio_path.stat().st_size == 0:
                raise ValueError("Audio file is empty")

            # Perform transcription with segments for progress tracking
            logger.info(f"Starting transcription of {audio_path}")
            segments, info = self.model.transcribe(
                str(audio_path),
                beam_size=5,
                word_timestamps=False
            )

            # Build full text and track progress
            full_text = []
            segment_list = []
            total_duration = info.duration if hasattr(info, 'duration') else None

            for i, segment in enumerate(segments):
                full_text.append(segment.text)
                segment_list.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text
                })

                # Update progress based on time coverage
                if progress_callback and total_duration:
                    progress = 0.1 + (segment.end / total_duration) * 0.9
                    progress_callback(min(progress, 1.0))

            # Build result
            transcribed_text = " ".join(full_text).strip()
            result = TranscriptionResult(
                text=transcribed_text,
                status=TranscriptionStatus.COMPLETED,
                segments=segment_list,
                language=info.language if hasattr(info, 'language') else None,
                duration=total_duration
            )

            logger.info(f"Transcription complete. Language: {result.language}, Duration: {result.duration:.2f}s")
            callback(result)

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=str(e)
            ))

        except ValueError as e:
            logger.error(f"Invalid audio file: {e}")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=str(e)
            ))

        except Exception as e:
            logger.exception("Transcription failed")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=f"Transcription error: {str(e)}"
            ))

    def cleanup(self):
        """Release model resources."""
        with self._model_lock:
            if self.model is not None:
                logger.info("Cleaning up transcription model")
                del self.model
                self.model = None
