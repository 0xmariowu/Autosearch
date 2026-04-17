# Self-written, plan v2.3 § 13.5
from fastapi.testclient import TestClient

import autosearch.server.main as server_main


def test_chat_completions_rejects_empty_messages() -> None:
    client = TestClient(server_main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "autosearch", "messages": []},
    )

    payload = response.json()

    assert response.status_code == 400
    assert payload["error"]["type"] == "invalid_request_error"
    assert payload["error"]["code"] == "invalid_messages"
    assert "message" in payload["error"]["message"].lower()
