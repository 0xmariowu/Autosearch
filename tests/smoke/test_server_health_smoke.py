# Self-written, plan v2.3 § W2 smoke server health
import httpx
import pytest


@pytest.mark.slow
@pytest.mark.smoke
def test_server_health_smoke(live_server_base_url: str) -> None:
    with httpx.Client(base_url=live_server_base_url, timeout=5.0) as client:
        health_response = client.get("/health")
        models_response = client.get("/v1/models")

    assert health_response.json() == {"status": "ok"}
    assert models_response.status_code == 200
    assert models_response.json() == {
        "object": "list",
        "data": [{"id": "autosearch", "object": "model", "owned_by": "autosearch"}],
    }
