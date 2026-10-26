"""Provider protocols shared by the LLM, embedding and retrieval layers.

Every AI interaction in SupportPilot goes through these protocols so the app can
always boot with the deterministic offline providers (`MockProvider`) and swap in
OpenAI or Gemini purely through configuration.
"""
from dataclasses import dataclass
from typing import List, Optional, Protocol, Sequence, runtime_checkable


class ProviderError(RuntimeError):
    """Raised when an upstream AI provider fails or is misconfigured.

    Messages must stay safe to surface to logs and API clients: never include
    API keys or raw upstream responses that could echo credentials.
    """


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimension: int

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        """Embeds a batch of document texts, preserving input order."""
        ...

    async def embed_query(self, text: str) -> List[float]:
        """Embeds a single search query."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generates a completion for the given prompts."""
        ...
