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

from .clipboard import copy_to_clipboard

logger = logging.getLogger(__name__)

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

class TranscriptionService:
    def __init__(
        self,
        server_url: str = "http://localhost:8080",
        inference_path: str = "/inference",
        timeout: int = 600,
        notifier: Optional[Any] = None
    ):
        self.server_url = server_url.rstrip('/')
        self.inference_path = inference_path
        self.timeout = timeout
        self.notifier = notifier
        self.endpoint = f"{self.server_url}{self.inference_path}"
        self.active_threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()  # Cooperative shutdown signal

    def _check_server_health(self) -> tuple[bool, Optional[str]]:
        try:
            requests.get(self.server_url, timeout=5)
            return True, None
        except Exception as e:
            return False, str(e)

    def _transcribe_file(self, audio_path: Path) -> tuple[str, Optional[str]]:
        # Use reduced timeout during shutdown to fail fast
        timeout = 3.0 if self._shutdown_event.is_set() else self.timeout
        logger.info(f"Sending transcription request to {self.endpoint} (timeout={timeout}s)")
        with open(audio_path, 'rb') as audio_file:
            files = {'file': (audio_path.name, audio_file, 'audio/wav')}
            data = {'response_format': 'json', 'temperature': '0.0'}
            response = requests.post(
                self.endpoint, files=files, data=data, timeout=timeout
            )
        
        response.raise_for_status()
        result = response.json()
        
        if 'text' in result:
            return result['text'].strip(), result.get('language')
        raise RuntimeError(f"Missing 'text' in response: {result}")

    def transcribe_async(
        self,
        audio_path: Path,
        callback: Callable[[TranscriptionResult], None],
        progress_callback: Optional[Callable[[float], None]] = None,
        copy_to_clipboard_enabled: bool = False,
        clipboard_error_callback: Optional[Callable[[str], None]] = None
    ) -> threading.Thread:
        """
        Start async transcription with proper cleanup support.

        Args:
            audio_path: Path to audio file to transcribe
            callback: Callback function for transcription result
            progress_callback: Optional callback for progress updates (0.0 to 1.0)
            copy_to_clipboard_enabled: Whether to copy result to clipboard
            clipboard_error_callback: Optional callback for clipboard errors (receives error message)

        Returns:
            Thread object running the transcription
        """
        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(audio_path, callback, progress_callback, copy_to_clipboard_enabled, clipboard_error_callback),
            daemon=False,  # Changed from True
            name=f"transcription-{audio_path.stem}"  # Added name for debugging
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
        clipboard_error_callback: Optional[Callable[[str], None]] = None
    ):
        try:
            # Check cancellation before expensive operations
            if self._shutdown_event.is_set():
                logger.info(f"Transcription cancelled during shutdown: {audio_path.name}")
                callback(TranscriptionResult(
                    text="",
                    status=TranscriptionStatus.ERROR,
                    error="Cancelled during shutdown"
                ))
                return

            if progress_callback: progress_callback(0.0)

            if not audio_path.exists():
                raise FileNotFoundError(f"File not found: {audio_path}")

            if progress_callback: progress_callback(0.1)

            try:
                transcribed_text, language = self._transcribe_file(audio_path)
            except requests.exceptions.Timeout:
                # If timeout during shutdown, it's expected behavior
                if self._shutdown_event.is_set():
                    logger.info("Transcription timeout during shutdown (expected)")
                    callback(TranscriptionResult(
                        text="",
                        status=TranscriptionStatus.ERROR,
                        error="Timeout during shutdown"
                    ))
                    return
                else:
                    # Re-raise if not during shutdown
                    raise

            if progress_callback: progress_callback(0.9)

            output_path = audio_path.with_suffix('.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(transcribed_text)

            # Copy to clipboard if enabled
            if copy_to_clipboard_enabled and transcribed_text:
                success, error_msg = copy_to_clipboard(transcribed_text)
                if not success and clipboard_error_callback:
                    # Invoke error callback if clipboard copy failed
                    clipboard_error_callback(error_msg)

            if progress_callback: progress_callback(1.0)

            callback(TranscriptionResult(
                text=transcribed_text,
                status=TranscriptionStatus.COMPLETED,
                language=language
            ))

            if self.notifier:
                self.notifier.notify("Transcription Complete", "Audio successfully transcribed.")

        except Exception as e:
            logger.exception("Transcription failed")
            if self.notifier:
                self.notifier.notify("Transcription Failed", str(e), urgency="critical")

            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=str(e)
            ))

    def shutdown(self, timeout: float = 10.0) -> None:
        """Shutdown service and wait for active transcriptions."""
        logger.info("=== Transcription Shutdown Starting ===")

        # Signal shutdown to all workers
        self._shutdown_event.set()

        with self._lock:
            threads_to_wait = list(self.active_threads)

        logger.info(f"Waiting for {len(threads_to_wait)} threads (timeout={timeout}s)")

        for i, thread in enumerate(threads_to_wait):
            thread_timeout = timeout / len(threads_to_wait) if threads_to_wait else timeout
            logger.info(f"Joining thread {i+1}/{len(threads_to_wait)}: {thread.name}")

            thread.join(timeout=thread_timeout)

            if thread.is_alive():
                logger.warning(f"Thread {thread.name} still alive after {thread_timeout:.1f}s timeout")

        logger.info("=== Transcription Shutdown Complete ===")

    def cleanup(self):
        logger.info("Transcription service cleanup")