"""Google Gemini implementations of the provider protocols."""
from typing import List, Sequence

import httpx

from app.ai.base import LLMResponse, ProviderError

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class GeminiEmbeddingProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, dimension: int):
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini.")
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def _embed(self, client: httpx.AsyncClient, text: str) -> List[float]:
        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self.dimension,
        }
        response = await client.post(
            f"{_API_BASE}/models/{self.model}:embedContent",
            headers={"x-goog-api-key": self.api_key},
            json=payload,
        )
        if response.status_code != 200:
            raise ProviderError(f"Gemini embedding request failed with status {response.status_code}.")
        try:
            values = response.json()["embedding"]["values"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Gemini embedding response was malformed.") from exc
        if len(values) != self.dimension:
            raise ProviderError(
                f"Gemini returned {len(values)}-dimension embeddings but {self.dimension} were configured."
            )
        return values

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                return [await self._embed(client, text) for text in texts]
        except httpx.HTTPError as exc:
            raise ProviderError("Gemini embedding request failed (network error).") from exc

    async def embed_query(self, text: str) -> List[float]:
        embeddings = await self.embed_documents([text])
        return embeddings[0]


class GeminiLLMProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    f"{_API_BASE}/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self.api_key},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("Gemini chat request failed (network error).") from exc

        if response.status_code != 200:
            raise ProviderError(f"Gemini chat request failed with status {response.status_code}.")

        try:
            body = response.json()
            parts = body["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts)
            usage = body.get("usageMetadata") or {}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Gemini chat response was malformed.") from exc

        return LLMResponse(
            content=content.strip(),
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
        )
