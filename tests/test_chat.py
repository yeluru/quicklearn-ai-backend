from unittest.mock import patch

def test_chat_on_topic(client):
    with patch("services.chat_service.chat_on_topic") as mock_chat:
        mock_chat.return_value = "mocked chat response"
        resp = client.post("/chat/on-topic", json={"transcript": "test", "chatHistory": []})
        assert resp.status_code == 200
        assert "mocked chat response" in resp.text

def test_suggested_questions(client):
    with patch("services.chat_service.suggested_questions") as mock_suggest:
        mock_suggest.return_value = ["Q1", "Q2"]
        resp = client.post("/chat/suggested-questions", json={"summary": "test summary"})
        assert resp.status_code == 200
        assert "Q1" in resp.text
        assert "Q2" in resp.text 