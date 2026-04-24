# Self-written, plan v2.3 § 1 decision 15
import os

import httpx
from pydantic import BaseModel


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.completions_url = f"{base}/chat/completions"
        self.http_client = http_client

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                    "strict": True,
                },
            },
        }
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

        if self.http_client is not None:
            response = await self.http_client.post(
                self.completions_url,
                headers=headers,
                json=payload,
            )
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.completions_url,
                    headers=headers,
                    json=payload,
                )

        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content

        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
