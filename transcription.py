"""
Audio transcription module using whisper-server HTTP API.

Provides thread-safe, asynchronous transcription of audio files with
progress callbacks and error handling. Designed for integration with
Textual TUI applications.

Uses persistent whisper-server container accessed via HTTP API,
eliminating model loading overhead for each transcription request.
"""

from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import logging
import requests
import json

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
    Thread-safe audio transcription service using whisper-server HTTP API.

    Connects to a persistent whisper-server container via HTTP requests.
    The server keeps the model loaded in memory for fast transcription.
    Designed for integration with Textual TUI apps.

    Example:
        service = TranscriptionService(
            server_url="http://localhost:8080"
        )

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
        server_url: str = "http://localhost:8080",
        inference_path: str = "/inference",
        timeout: int = 600  # 10 minutes default timeout
    ):
        """
        Initialize transcription service.

        Args:
            server_url: Base URL of whisper-server (e.g., http://localhost:8080)
            inference_path: API endpoint path for transcription
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.inference_path = inference_path
        self.timeout = timeout
        self.endpoint = f"{self.server_url}{self.inference_path}"

    def _check_server_health(self) -> tuple[bool, Optional[str]]:
        """
        Check if whisper-server is reachable and healthy.

        Returns:
            (is_healthy: bool, error_message: Optional[str])
        """
        try:
            response = requests.get(self.server_url, timeout=5)
            return True, None
        except requests.ConnectionError:
            return False, f"Cannot connect to whisper-server at {self.server_url}"
        except requests.Timeout:
            return False, f"Timeout connecting to whisper-server at {self.server_url}"
        except Exception as e:
            return False, f"Server health check failed: {str(e)}"

    def _transcribe_file(self, audio_path: Path) -> tuple[str, Optional[str]]:
        """
        Send audio file to whisper-server for transcription.

        Args:
            audio_path: Path to audio file

        Returns:
            (transcribed_text: str, detected_language: Optional[str])

        Raises:
            requests.RequestException: If HTTP request fails
            RuntimeError: If server returns error or invalid response
        """
        logger.info(f"Sending transcription request to {self.endpoint}")

        # Prepare multipart file upload
        with open(audio_path, 'rb') as audio_file:
            files = {'file': (audio_path.name, audio_file, 'audio/wav')}

            # Optional: Add request parameters
            data = {
                'response_format': 'json',  # Request JSON response
                'temperature': '0.0'  # Deterministic output
            }

            # Send POST request
            response = requests.post(
                self.endpoint,
                files=files,
                data=data,
                timeout=self.timeout
            )

        # Check for HTTP errors
        response.raise_for_status()

        # Parse JSON response
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from server: {e}")

        # Extract transcription text
        if 'text' in result:
            transcribed_text = result['text'].strip()
        else:
            raise RuntimeError(f"Server response missing 'text' field: {result}")

        # Extract detected language (if available)
        detected_language = result.get('language')

        return transcribed_text, detected_language

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
        """Internal worker function for transcription thread using HTTP API."""
        try:
            # Initial progress
            if progress_callback:
                progress_callback(0.0)

            # Validate audio file
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            if audio_path.stat().st_size == 0:
                raise ValueError("Audio file is empty")

            # Debug logging
            logger.info("=" * 60)
            logger.info("TRANSCRIPTION DEBUG INFO")
            logger.info("=" * 60)
            logger.info(f"Audio file: {audio_path}")
            logger.info(f"Audio size: {audio_path.stat().st_size:,} bytes")
            logger.info(f"Server endpoint: {self.endpoint}")
            logger.info(f"Request timeout: {self.timeout}s")
            logger.info("=" * 60)

            # Check server health
            logger.info("Checking whisper-server health...")
            healthy, error = self._check_server_health()
            if not healthy:
                raise ConnectionError(error)

            if progress_callback:
                progress_callback(0.1)

            # Send transcription request
            logger.info("Sending audio to whisper-server...")
            transcribed_text, language = self._transcribe_file(audio_path)

            if progress_callback:
                progress_callback(0.9)

            # Save transcription to file (same directory as audio)
            output_path = audio_path.with_suffix('.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(transcribed_text)

            logger.info(f"Transcription saved to {output_path}")

            if progress_callback:
                progress_callback(1.0)

            # Build result
            transcription_result = TranscriptionResult(
                text=transcribed_text,
                status=TranscriptionStatus.COMPLETED,
                language=language,
                duration=None
            )

            logger.info(f"Transcription complete. Language: {language}, Length: {len(transcribed_text)} chars")
            callback(transcription_result)

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

        except ConnectionError as e:
            logger.error(f"Server connection error: {e}")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=f"Cannot connect to whisper-server: {e}"
            ))

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout}s")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=f"Transcription timed out (max {self.timeout}s)"
            ))

        except requests.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=f"Server request failed: {str(e)}"
            ))

        except Exception as e:
            logger.exception("Transcription failed")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=f"Transcription error: {str(e)}"
            ))

    def cleanup(self):
        """
        Cleanup method for consistency with previous API.

        Note: No cleanup needed for containerized approach since
        containers are ephemeral (--rm flag handles cleanup).
        """
        logger.info("Transcription service cleanup (no-op for containerized approach)")
