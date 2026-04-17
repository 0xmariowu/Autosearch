# Self-written, plan v2.3 § 13.5
import pytest
from pydantic import BaseModel

from autosearch.llm.client import LLMClient


class DemoResponse(BaseModel):
    answer: str


class FailingProvider:
    name = "failing"

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        _ = response_model
        self.calls += 1
        raise self.error


async def test_llm_client_surfaces_provider_exception_without_retrying_provider_calls() -> None:
    provider = FailingProvider(RuntimeError("provider exploded"))
    client = LLMClient(provider_name="failing", providers={"failing": provider})

    with pytest.raises(RuntimeError, match="provider exploded"):
        await client.complete("test prompt", DemoResponse)

    assert client.max_parse_retries == 3
    assert provider.calls == 1
