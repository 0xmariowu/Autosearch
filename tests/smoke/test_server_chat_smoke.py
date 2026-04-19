# Self-written, plan v2.3 § W2 smoke server chat
import httpx
import pytest


@pytest.mark.slow
@pytest.mark.smoke
def test_server_chat_smoke(live_server_base_url: str) -> None:
    with httpx.Client(base_url=live_server_base_url, timeout=30.0) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "smoke"}]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"].strip()
