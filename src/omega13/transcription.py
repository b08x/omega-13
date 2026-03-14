"""
Audio transcription module using whisper-server HTTP API.
Refactored to be part of the omega13 package.
"""

from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import threading
import logging
import requests
import json
import time
import random

from .clipboard import copy_to_clipboard
from .injection import inject_text
from .obsidian_cli import obsidian_cli

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Base exception for transcription errors."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class PermanentTranscriptionError(TranscriptionError):
    """Exception for errors that should not be retried."""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class TranscriptionStatus(Enum):
    IDLE = "idle"
    LOADING_MODEL = "loading_model"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class TranscriptionResult:
    text: str
    status: TranscriptionStatus
    error: Optional[str] = None
    segments: Optional[list[dict]] = None
    language: Optional[str] = None
    duration: Optional[float] = None


class TranscriptionProvider:
    """Base class for transcription backends."""

    def check_health(self) -> tuple[bool, Optional[str]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Path, timeout: float) -> tuple[str, Optional[str]]:
        raise NotImplementedError


class LocalTranscriptionProvider(TranscriptionProvider):
    """Local whisper-server backend."""

    def __init__(self, server_url: str, inference_path: str):
        self.server_url = server_url.rstrip("/")
        inference_path = (
            inference_path if inference_path.startswith("/") else f"/{inference_path}"
        )
        self.endpoint = f"{self.server_url}{inference_path}"

    def check_health(self) -> tuple[bool, Optional[str]]:
        try:
            response = requests.get(self.server_url, timeout=5)
            response.raise_for_status()
            return True, None
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to server (Connection Refused)"
        except requests.exceptions.Timeout:
            return False, "Server connection timed out"
        except Exception as e:
            return False, str(e)

    def transcribe(self, audio_path: Path, timeout: float) -> tuple[str, Optional[str]]:
        with open(audio_path, "rb") as audio_file:
            # Detect MIME type from file extension
            mime_type = "audio/mpeg" if audio_path.suffix == ".mp3" else "audio/wav"
            files = {"file": (audio_path.name, audio_file, mime_type)}
            data = {"response_format": "json", "temperature": "0.0"}
            response = requests.post(
                self.endpoint, files=files, data=data, timeout=timeout
            )

        response.raise_for_status()
        result = response.json()

        if "text" in result:
            return result["text"].strip(), result.get("language")
        raise PermanentTranscriptionError(f"Missing 'text' in response: {result}")


class GroqTranscriptionProvider(TranscriptionProvider):
    """Groq Cloud Whisper backend."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    def check_health(self) -> tuple[bool, Optional[str]]:
        if not self.api_key:
            return False, "Groq API key is missing"
        # Minimally verify we can reach the API
        try:
            # We don't want to burn tokens, so just a GET to the base URL (if supported) or similar
            # Groq API doesn't have a simple health endpoint that doesn't requires auth.
            return True, None
        except Exception as e:
            return False, str(e)

    def transcribe(self, audio_path: Path, timeout: float) -> tuple[str, Optional[str]]:
        if not self.api_key:
            raise ValueError("Groq API key is missing")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        with open(audio_path, "rb") as audio_file:
            mime_type = "audio/mpeg" if audio_path.suffix == ".mp3" else "audio/wav"
            files = {"file": (audio_path.name, audio_file, mime_type)}
            data = {
                "model": self.model,
                "response_format": "json",
                "temperature": "0.0",
            }
            response = requests.post(
                self.endpoint, headers=headers, files=files, data=data, timeout=timeout
            )

        if response.status_code == 401:
            raise PermanentTranscriptionError("Groq API Error: Invalid API Key (401)")
        elif response.status_code == 429:
            # Rate limits are typically retryable with backoff
            raise TranscriptionError(
                "Groq API Error: Rate limit exceeded (429)", retryable=True
            )
        elif 400 <= response.status_code < 500:
            # Most other 4xx errors are permanent (client errors)
            raise PermanentTranscriptionError(
                f"Groq API Client Error: {response.status_code}"
            )

        response.raise_for_status()
        result = response.json()

        if "text" in result:
            return result["text"].strip(), result.get("language")
        raise PermanentTranscriptionError(f"Missing 'text' in response: {result}")


class TranscriptionService:
    def __init__(
        self,
        provider: TranscriptionProvider,
        timeout: int = 600,
        notifier: Optional[Any] = None,
    ):
        self.provider = provider
        self.timeout = timeout
        self.notifier = notifier
        self.active_threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()  # Cooperative shutdown signal

    def check_health(self) -> tuple[bool, Optional[str]]:
        """Check if the transcription backend is reachable and responding."""
        return self.provider.check_health()

    def _transcribe_file(
        self, audio_path: Path, current_timeout: Optional[float] = None
    ) -> tuple[str, Optional[str]]:
        # Use reduced timeout during shutdown to fail fast
        timeout = (
            3.0 if self._shutdown_event.is_set() else (current_timeout or self.timeout)
        )
        logger.info(
            f"Sending transcription request to provider {type(self.provider).__name__} (timeout={timeout}s)"
        )
        return self.provider.transcribe(audio_path, timeout)

    def transcribe_async(
        self,
        audio_path: Path,
        callback: Callable[[TranscriptionResult], None],
        progress_callback: Optional[Callable[[float], None]] = None,
        copy_to_clipboard_enabled: bool = False,
        clipboard_error_callback: Optional[Callable[[str], None]] = None,
        inject_to_active_window_enabled: bool = False,
        injection_error_callback: Optional[Callable[[str], None]] = None,
        write_to_daily_note_enabled: bool = False,
        daily_note_error_callback: Optional[Callable[[str], None]] = None,
    ) -> threading.Thread:
        """
        Start async transcription with proper cleanup support.

        Args:
            audio_path: Path to audio file to transcribe
            callback: Callback function for transcription result
            progress_callback: Optional callback for progress updates (0.0 to 1.0)
            copy_to_clipboard_enabled: Whether to copy result to clipboard
            clipboard_error_callback: Optional callback for clipboard errors (receives error message)
            inject_to_active_window_enabled: Whether to type result into active window
            injection_error_callback: Optional callback for injection errors (receives error message)
            write_to_daily_note_enabled: Whether to write result to Obsidian daily note
            daily_note_error_callback: Optional callback for daily note errors (receives error message)

        Returns:
            Thread object running the transcription
        """
        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(
                audio_path,
                callback,
                progress_callback,
                copy_to_clipboard_enabled,
                clipboard_error_callback,
                inject_to_active_window_enabled,
                injection_error_callback,
                write_to_daily_note_enabled,
                daily_note_error_callback,
            ),
            daemon=True,  # Daemon thread allows clean shutdown without blocking
            name=f"transcription-{audio_path.stem}",  # Added name for debugging
        )
        thread.start()

        # Track active threads for shutdown
        with self._lock:
            # Clean up completed threads
            self.active_threads = [t for t in self.active_threads if t.is_alive()]
            self.active_threads.append(thread)

        return thread

    def _transcribe_worker(
        self,
        audio_path: Path,
        callback: Callable[[TranscriptionResult], None],
        progress_callback: Optional[Callable[[float], None]],
        copy_to_clipboard_enabled: bool = False,
        clipboard_error_callback: Optional[Callable[[str], None]] = None,
        inject_to_active_window_enabled: bool = False,
        injection_error_callback: Optional[Callable[[str], None]] = None,
        write_to_daily_note_enabled: bool = False,
        daily_note_error_callback: Optional[Callable[[str], None]] = None,
    ):
        try:
            # Check cancellation before expensive operations
            if self._shutdown_event.is_set():
                logger.info(
                    f"Transcription cancelled during shutdown: {audio_path.name}"
                )
                callback(
                    TranscriptionResult(
                        text="",
                        status=TranscriptionStatus.ERROR,
                        error="Cancelled during shutdown",
                    )
                )
                return

            if progress_callback:
                progress_callback(0.0)

            if not audio_path.exists():
                raise FileNotFoundError(f"File not found: {audio_path}")

            if progress_callback:
                progress_callback(0.1)

            max_retries = 3
            retry_count = 0
            transcribed_text = ""
            language = None

            while retry_count < max_retries:
                try:
                    # Gradually increase timeout on retries: baseline -> baseline * 1.5 -> baseline * 2
                    current_timeout = self.timeout * (1 + 0.5 * retry_count)
                    transcribed_text, language = self._transcribe_file(
                        audio_path, current_timeout=current_timeout
                    )
                    break
                except requests.exceptions.Timeout:
                    if self._shutdown_event.is_set():
                        logger.info("Transcription timeout during shutdown (expected)")
                        callback(
                            TranscriptionResult(
                                text="",
                                status=TranscriptionStatus.ERROR,
                                error="Timeout during shutdown",
                            )
                        )
                        return

                    retry_count += 1
                    if retry_count >= max_retries:
                        raise

                    # Exponential backoff with jitter
                    wait_time = (2**retry_count) + random.uniform(0, 1)
                    logger.warning(
                        f"Transcription timeout. Retrying in {wait_time:.1f}s ({retry_count}/{max_retries})..."
                    )
                    time.sleep(wait_time)

                except TranscriptionError as e:
                    if not e.retryable:
                        raise

                    retry_count += 1
                    if retry_count >= max_retries:
                        raise

                    # Longer backoff for explicit transcription errors (like rate limits)
                    wait_time = (4**retry_count) + random.uniform(0, 2)
                    logger.warning(
                        f"Transcription retryable error: {e}. Retrying in {wait_time:.1f}s ({retry_count}/{max_retries})..."
                    )
                    time.sleep(wait_time)

                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise

                    wait_time = (2**retry_count) + random.uniform(0, 1)
                    logger.warning(
                        f"Transcription unexpected error: {e}. Retrying in {wait_time:.1f}s ({retry_count}/{max_retries})..."
                    )
                    time.sleep(wait_time)

            if progress_callback:
                progress_callback(0.9)

            # Determine correct path for transcription text file
            # If part of an omega13 session, put in transcriptions/ folder
            if "recordings" in str(audio_path):
                trans_dir = audio_path.parent.parent / "transcriptions"
                trans_dir.mkdir(parents=True, exist_ok=True)
                output_path = trans_dir / f"{audio_path.stem}.md"
            else:
                output_path = audio_path.with_suffix(".md")

            logger.info(f"Saving transcription to {output_path}")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcribed_text)

            # Copy to clipboard if enabled
            if copy_to_clipboard_enabled and transcribed_text:
                success, error_msg = copy_to_clipboard(transcribed_text)
                if not success and clipboard_error_callback:
                    # Invoke error callback if clipboard copy failed
                    clipboard_error_callback(error_msg)

            # Inject to active window if enabled
            if inject_to_active_window_enabled and transcribed_text:
                success, error_msg = inject_text(transcribed_text)
                if not success and injection_error_callback:
                    # Invoke error callback if injection failed
                    injection_error_callback(error_msg)

            # Write to Obsidian daily note if enabled
            if write_to_daily_note_enabled and transcribed_text:
                result = obsidian_cli.append_to_daily_note(transcribed_text)
                if not result.success and daily_note_error_callback:
                    # Invoke error callback if daily note writing failed
                    daily_note_error_callback(result.message)

            if progress_callback:
                progress_callback(1.0)

            callback(
                TranscriptionResult(
                    text=transcribed_text,
                    status=TranscriptionStatus.COMPLETED,
                    language=language,
                )
            )

            if self.notifier:
                self.notifier.notify(
                    "Transcription Complete", "Audio successfully transcribed."
                )

        except Exception as e:
            logger.exception("Transcription failed")
            if self.notifier:
                self.notifier.notify("Transcription Failed", str(e), urgency="critical")

            callback(
                TranscriptionResult(
                    text="", status=TranscriptionStatus.ERROR, error=str(e)
                )
            )

    def shutdown(self, timeout: float = 10.0) -> None:
        """Shutdown service and wait for active transcriptions."""
        logger.info("=== Transcription Shutdown Starting ===")

        # Signal shutdown to all workers
        self._shutdown_event.set()

        with self._lock:
            threads_to_wait = list(self.active_threads)

        logger.info(f"Waiting for {len(threads_to_wait)} threads (timeout={timeout}s)")

        for i, thread in enumerate(threads_to_wait):
            thread_timeout = (
                timeout / len(threads_to_wait) if threads_to_wait else timeout
            )
            logger.info(f"Joining thread {i+1}/{len(threads_to_wait)}: {thread.name}")

            thread.join(timeout=thread_timeout)

            if thread.is_alive():
                logger.warning(
                    f"Thread {thread.name} still alive after {thread_timeout:.1f}s timeout"
                )

        logger.info("=== Transcription Shutdown Complete ===")

    def cleanup(self):
        logger.info("Transcription service cleanup")
