"""Provider factory: resolves configuration into concrete provider instances."""
from typing import Optional

from app.ai.base import EmbeddingProvider, LLMProvider, ProviderError
from app.ai.gemini_provider import GeminiEmbeddingProvider, GeminiLLMProvider
from app.ai.mock_provider import MockEmbeddingProvider, MockLLMProvider
from app.ai.openai_provider import OpenAIEmbeddingProvider, OpenAILLMProvider
from app.config import settings

SUPPORTED_EMBEDDING_PROVIDERS = ("mock", "openai", "gemini")
SUPPORTED_LLM_PROVIDERS = ("mock", "openai", "gemini")


def get_embedding_provider(
    provider: Optional[str] = None,
    dimension: Optional[int] = None,
) -> EmbeddingProvider:
    """Builds the embedding provider selected by workspace/app configuration."""
    name = (provider or settings.EMBEDDING_PROVIDER or "mock").strip().lower()
    dimension = dimension or settings.EMBEDDING_DIMENSION

    if name == "mock":
        return MockEmbeddingProvider(dimension)
    if name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_EMBEDDING_MODEL,
            dimension=dimension,
        )
    if name == "gemini":
        return GeminiEmbeddingProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_EMBEDDING_MODEL,
            dimension=dimension,
        )
    raise ProviderError(
        f"Unsupported embedding provider '{name}'. "
        f"Expected one of: {', '.join(SUPPORTED_EMBEDDING_PROVIDERS)}."
    )


def get_llm_provider(provider: Optional[str] = None, model: Optional[str] = None) -> LLMProvider:
    """Builds the LLM provider selected by workspace/app configuration."""
    name = (provider or settings.LLM_PROVIDER or "mock").strip().lower()
    configured_model = (model or settings.LLM_MODEL or "").strip()

    if name == "mock":
        return MockLLMProvider()
    if name == "openai":
        resolved_model = (
            configured_model
            if configured_model and not configured_model.startswith("mock")
            else "gpt-4o-mini"
        )
        return OpenAILLMProvider(api_key=settings.OPENAI_API_KEY, model=resolved_model)
    if name == "gemini":
        resolved_model = (
            configured_model
            if configured_model and not configured_model.startswith("mock")
            else settings.GEMINI_LLM_MODEL
        )
        return GeminiLLMProvider(api_key=settings.GEMINI_API_KEY, model=resolved_model)
    raise ProviderError(
        f"Unsupported LLM provider '{name}'. Expected one of: {', '.join(SUPPORTED_LLM_PROVIDERS)}."
    )


def mock_similarity_threshold() -> float:
    """Mock embeddings are lexical, so they use their own calibrated cutoff."""
    return settings.MOCK_SIMILARITY_THRESHOLD


def resolve_similarity_threshold(provider_name: str, workspace_threshold: Optional[float]) -> float:
    if (provider_name or "").lower() == "mock":
        return settings.MOCK_SIMILARITY_THRESHOLD
    if workspace_threshold is None:
        return settings.SIMILARITY_THRESHOLD
    return workspace_threshold
