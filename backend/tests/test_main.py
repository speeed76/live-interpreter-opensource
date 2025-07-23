# backend/tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# We need to patch the LocalSpeechProcessor before it's imported by main
mock_processor = MagicMock()
mock_processor.is_ready = True

# Create a mock for the class itself to control its instances
mock_processor_class = MagicMock(return_value=mock_processor)

# Patch the class in the local_client module
patcher = patch('backend.local_client.LocalSpeechProcessor', mock_processor_class)
patcher.start()

# Now we can import the app with the patch in place
from backend.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    mock_processor.reset_mock()
    mock_processor_class.reset_mock()
    mock_processor.is_ready = True
    # Ensure the patch is stopped after tests run
    yield
    patcher.stop()


def test_health_check_when_ready():
    """Test the /health endpoint when the processor is ready."""
    mock_processor.is_ready = True
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Services are ready."}

def test_health_check_when_not_ready():
    """Test the /health endpoint when the processor is not ready."""
    mock_processor.is_ready = False
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Services are not ready. Models may be loading or have failed."}

def test_data_websocket_connection():
    """Test that a client can connect to the /ws/data endpoint."""
    with client.websocket_connect("/ws/data") as websocket:
        # Check for the initial status message
        data = websocket.receive_json()
        assert data["type"] == "status"
        assert "agent_connected" in data

def test_audio_websocket_connection_when_ready():
    """Test that an agent can connect to the /ws/audio endpoint when the processor is ready."""
    mock_processor.is_ready = True
    with client.websocket_connect("/ws/audio") as websocket:
        # Check for the initial status message broadcast to data clients
        # This is a bit tricky to test directly without a more complex setup,
        # but we can assert the connection was successful.
        assert mock_processor.start.called
    assert mock_processor.stop.called

def test_audio_websocket_connection_when_not_ready():
    """Test that an agent is rejected from /ws/audio when the processor is not ready."""
    mock_processor.is_ready = False
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/audio") as websocket:
            # The connection should be closed with an error code
            pass
