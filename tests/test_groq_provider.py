import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import requests
import time
from omega13.transcription import (
    TranscriptionService,
    LocalTranscriptionProvider,
    GroqTranscriptionProvider,
    TranscriptionError,
    PermanentTranscriptionError,
)


def test_local_provider_transcribe_success():
    provider = LocalTranscriptionProvider(
        server_url="http://localhost:8080", inference_path="/inference"
    )
    audio_path = Path("test.wav")

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"text": "Hello world", "language": "en"}
        mock_post.return_value = mock_response

        with patch("builtins.open", MagicMock()):
            text, lang = provider.transcribe(audio_path, timeout=60)

        assert text == "Hello world"
        assert lang == "en"
        assert mock_post.called


def test_groq_provider_transcribe_success():
    provider = GroqTranscriptionProvider(
        api_key="test_key", model="whisper-large-v3-turbo"
    )
    audio_path = Path("test.wav")

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Hello from Groq"}
        mock_post.return_value = mock_response

        with patch("builtins.open", MagicMock()):
            text, lang = provider.transcribe(audio_path, timeout=60)

        assert text == "Hello from Groq"
        assert lang is None

        # Verify headers
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test_key"
        assert kwargs["data"]["model"] == "whisper-large-v3-turbo"


def test_groq_provider_auth_error():
    provider = GroqTranscriptionProvider(
        api_key="invalid_key", model="whisper-large-v3-turbo"
    )
    audio_path = Path("test.wav")

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        with patch("builtins.open", MagicMock()):
            with pytest.raises(PermanentTranscriptionError) as excinfo:
                provider.transcribe(audio_path, timeout=60)

        assert "Invalid API Key (401)" in str(excinfo.value)
        assert excinfo.value.retryable is False


def test_groq_provider_rate_limit_error():
    provider = GroqTranscriptionProvider(
        api_key="test_key", model="whisper-large-v3-turbo"
    )
    audio_path = Path("test.wav")

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        with patch("builtins.open", MagicMock()):
            with pytest.raises(TranscriptionError) as excinfo:
                provider.transcribe(audio_path, timeout=60)

        assert "Rate limit exceeded (429)" in str(excinfo.value)
        assert excinfo.value.retryable is True


def test_service_retry_on_rate_limit():
    mock_provider = MagicMock(spec=GroqTranscriptionProvider)
    # Fail twice with rate limit, then succeed
    mock_provider.transcribe.side_effect = [
        TranscriptionError("Rate limit", retryable=True),
        TranscriptionError("Rate limit", retryable=True),
        ("Success!", "en"),
    ]

    audio_path = Path("test.wav")
    service = TranscriptionService(provider=mock_provider, timeout=10)

    with patch("time.sleep", return_value=None):  # Skip actual waiting
        with patch("pathlib.Path.exists", return_value=True):
            # We need to use transcribe_async or call _transcribe_worker directly
            # For simplicity, let's call _transcribe_worker directly
            results = []

            def callback(res):
                results.append(res)

            service._transcribe_worker(audio_path, callback, None)

            assert len(results) == 1
            assert results[0].text == "Success!"
            assert mock_provider.transcribe.call_count == 3

            # Verify increasing timeouts
            calls = mock_provider.transcribe.call_args_list
            assert calls[0][0][1] == 10.0  # Initial
            assert calls[1][0][1] == 15.0  # 1.5x
            assert calls[2][0][1] == 20.0  # 2x


def test_service_fail_fast_on_permanent_error():
    mock_provider = MagicMock(spec=GroqTranscriptionProvider)
    mock_provider.transcribe.side_effect = PermanentTranscriptionError("Bad Request")

    audio_path = Path("test.wav")
    service = TranscriptionService(provider=mock_provider)

    with patch("time.sleep", return_value=None):
        with patch("pathlib.Path.exists", return_value=True):
            results = []

            def callback(res):
                results.append(res)

            service._transcribe_worker(audio_path, callback, None)

            assert len(results) == 1
            assert "Bad Request" in results[0].error
            assert mock_provider.transcribe.call_count == 1  # Should NOT retry
