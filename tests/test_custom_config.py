import pytest
from unittest.mock import patch, MagicMock
from omega13.transcription import TranscriptionService, LocalTranscriptionProvider
import requests

def test_custom_inference_path():
    provider = LocalTranscriptionProvider(server_url="http://my-whisper-server", inference_path="/my-custom-path")
    service = TranscriptionService(provider=provider)
    
    assert provider.endpoint == "http://my-whisper-server/my-custom-path"
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        alive, error = service.check_health()
        
        assert alive is True
        # Health check uses server_url, not the endpoint with inference_path
        mock_get.assert_called_once_with("http://my-whisper-server", timeout=5)

def test_inference_path_slash_handling():
    # Test that it adds a leading slash if missing
    provider = LocalTranscriptionProvider(server_url="http://localhost:8080", inference_path="inference")
    assert provider.endpoint == "http://localhost:8080/inference"
    
    # Test that it doesn't double slash
    provider = LocalTranscriptionProvider(server_url="http://localhost:8080", inference_path="/inference")
    assert provider.endpoint == "http://localhost:8080/inference"