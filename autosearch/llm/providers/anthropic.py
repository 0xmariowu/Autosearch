# Self-written, plan v2.3 § 1 decision 15
import json
import os

import httpx
from pydantic import BaseModel


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider.")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.http_client = http_client

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [
                {
                    "name": "output",
                    "description": "Return the final structured JSON response.",
                    "input_schema": response_model.model_json_schema(),
                }
            ],
            "tool_choice": {"type": "tool", "name": "output"},
        }
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key,
        }

        if self.http_client is not None:
            response = await self.http_client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                )

        response.raise_for_status()
        data = response.json()
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "output":
                return json.dumps(block.get("input", {}))

        raise ValueError("Anthropic response did not contain a matching tool_use block.")
