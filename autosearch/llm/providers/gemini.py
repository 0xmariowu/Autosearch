# Self-written, plan v2.3 § 1 decision 15
import os

import httpx
from pydantic import BaseModel


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is required for the Gemini provider.")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self.http_client = http_client

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_model.model_json_schema(),
            },
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        headers = {
            "content-type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        if self.http_client is not None:
            response = await self.http_client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
