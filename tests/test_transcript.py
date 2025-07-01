import pytest
from unittest.mock import patch

def test_transcript_stream(client):
    with patch("services.transcript_service.get_transcript_from_url") as mock_transcript:
        mock_transcript.return_value = "mocked transcript"
        resp = client.post("/transcript/stream", json={"url": "https://youtube.com/watch?v=abc"})
        assert resp.status_code == 200
        assert "mocked transcript" in resp.text

def test_transcript_upload(client):
    with patch("services.transcript_service.get_transcript_from_file") as mock_file:
        mock_file.return_value = "mocked file transcript"
        resp = client.post("/transcript/upload", files={"file": ("test.txt", b"dummy data")})
        assert resp.status_code == 200
        assert "mocked file transcript" in resp.text 