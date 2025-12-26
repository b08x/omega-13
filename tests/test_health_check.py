import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from omega13.transcription import TranscriptionService
import requests

def test_health_check_success():
    service = TranscriptionService(server_url="http://localhost:8080")
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        alive, error = service.check_health()
        
        assert alive is True
        assert error is None
        mock_get.assert_called_once_with("http://localhost:8080", timeout=5)

def test_health_check_connection_error():
    service = TranscriptionService(server_url="http://localhost:8080")
    
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        alive, error = service.check_health()
        
        assert alive is False
        assert "Connection Refused" in error

def test_health_check_timeout():
    service = TranscriptionService(server_url="http://localhost:8080")
    
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        
        alive, error = service.check_health()
        
        assert alive is False
        assert "timed out" in error

def test_health_check_generic_error():
    service = TranscriptionService(server_url="http://localhost:8080")
    
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Generic error")
        
        alive, error = service.check_health()
        
        assert alive is False
        assert "Generic error" in error
