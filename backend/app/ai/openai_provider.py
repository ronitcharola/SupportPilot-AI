"""OpenAI implementations of the provider protocols (embeddings + chat)."""
from typing import List, Sequence

import httpx

from app.ai.base import LLMResponse, ProviderError

_API_BASE = "https://api.openai.com/v1"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, dimension: int):
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def _request(self, texts: Sequence[str]) -> List[List[float]]:
        payload = {
            "model": self.model,
            "input": list(texts),
            "encoding_format": "float",
        }
        # text-embedding-3-* supports shortening the output; older models do not.
        if self.model.startswith("text-embedding-3"):
            payload["dimensions"] = self.dimension

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    f"{_API_BASE}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("OpenAI embedding request failed (network error).") from exc

        if response.status_code != 200:
            raise ProviderError(f"OpenAI embedding request failed with status {response.status_code}.")

        try:
            data = response.json()["data"]
            embeddings = [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("OpenAI embedding response was malformed.") from exc

        if len(embeddings) != len(texts):
            raise ProviderError("OpenAI embedding response count did not match the request.")
        for embedding in embeddings:
            if len(embedding) != self.dimension:
                raise ProviderError(
                    f"OpenAI returned {len(embedding)}-dimension embeddings but {self.dimension} were configured."
                )
        return embeddings

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        return await self._request(texts)

    async def embed_query(self, text: str) -> List[float]:
        embeddings = await self._request([text])
        return embeddings[0]


class OpenAILLMProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
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
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    f"{_API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("OpenAI chat request failed (network error).") from exc

        if response.status_code != 200:
            raise ProviderError(f"OpenAI chat request failed with status {response.status_code}.")

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"] or ""
            usage = body.get("usage") or {}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("OpenAI chat response was malformed.") from exc

        return LLMResponse(
            content=content.strip(),
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
