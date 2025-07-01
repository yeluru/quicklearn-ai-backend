from unittest.mock import patch

def test_summary_stream(client):
    with patch("services.summary_service.summarize_transcript") as mock_summarize:
        mock_summarize.return_value = "mocked summary"
        resp = client.post("/summary/summarize-stream", json={"transcript": "test transcript"})
        assert resp.status_code == 200
        assert "mocked summary" in resp.text

def test_qna_stream(client):
    with patch("services.summary_service.generate_quiz") as mock_quiz:
        mock_quiz.return_value = "mocked quiz"
        resp = client.post("/summary/qna-stream", json={"transcript": "test transcript"})
        assert resp.status_code == 200
        assert "mocked quiz" in resp.text 