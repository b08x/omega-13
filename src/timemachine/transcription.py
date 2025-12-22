"""
Audio transcription module using whisper-server HTTP API.
Refactored to be part of the timemachine package.
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
        timeout: int = 600
    ):
        self.server_url = server_url.rstrip('/')
        self.inference_path = inference_path
        self.timeout = timeout
        self.endpoint = f"{self.server_url}{self.inference_path}"

    def _check_server_health(self) -> tuple[bool, Optional[str]]:
        try:
            requests.get(self.server_url, timeout=5)
            return True, None
        except Exception as e:
            return False, str(e)

    def _transcribe_file(self, audio_path: Path) -> tuple[str, Optional[str]]:
        logger.info(f"Sending transcription request to {self.endpoint}")
        with open(audio_path, 'rb') as audio_file:
            files = {'file': (audio_path.name, audio_file, 'audio/wav')}
            data = {'response_format': 'json', 'temperature': '0.0'}
            response = requests.post(
                self.endpoint, files=files, data=data, timeout=self.timeout
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
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> threading.Thread:
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
        try:
            if progress_callback: progress_callback(0.0)
            
            if not audio_path.exists():
                raise FileNotFoundError(f"File not found: {audio_path}")

            if progress_callback: progress_callback(0.1)
            
            transcribed_text, language = self._transcribe_file(audio_path)
            
            if progress_callback: progress_callback(0.9)

            output_path = audio_path.with_suffix('.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(transcribed_text)

            if progress_callback: progress_callback(1.0)

            callback(TranscriptionResult(
                text=transcribed_text,
                status=TranscriptionStatus.COMPLETED,
                language=language
            ))

        except Exception as e:
            logger.exception("Transcription failed")
            callback(TranscriptionResult(
                text="",
                status=TranscriptionStatus.ERROR,
                error=str(e)
            ))

    def cleanup(self):
        logger.info("Transcription service cleanup")