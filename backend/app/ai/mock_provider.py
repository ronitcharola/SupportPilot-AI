"""Deterministic, offline providers used by default in demo mode and tests.

The mock embedding model is a compact lexical sketch: stop-word filtered, stemmed
terms are hashed into a fixed-dimension vector, capped to the 24 most salient
features and L2-normalized. That keeps cosine similarity meaningful for demo
retrieval without downloading a model or calling any API.

The mock LLM is deliberately **extractive**: it only reproduces sentences found
in the supplied context and attaches citation markers. It never invents facts,
which makes the offline demo behave like a grounded RAG answerer.
"""
import hashlib
import math
import re
from typing import List, Sequence, Tuple

from app.ai.base import LLMResponse
from app.ai.text_utils import split_sentences, stem, term_counts, tokenize, top_features

_MAX_FEATURES = 24
_BLOCK_RE = re.compile(
    r"\[(\d+)\] Source: ([^\n]+)\n<customer_input>\n(.*?)\n</customer_input>",
    re.DOTALL,
)
_QUESTION_RE = re.compile(r"<customer_input>\n?(.*?)\n?</customer_input>", re.DOTALL)


class MockEmbeddingProvider:
    name = "mock"

    def __init__(self, dimension: int = 1536):
        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive.")
        self.dimension = dimension
        self.model = f"mock-lexical-{dimension}"

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        features = top_features(term_counts(text), _MAX_FEATURES)
        for term, weight in features.items():
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = -1.0 if digest[4] & 1 else 1.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    async def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def _is_substantive(sentence: str) -> bool:
    """Filters headings and list fragments out of extractive answers."""
    stripped = sentence.strip()
    if len(stripped) < 30:
        return False
    if stripped[-1] not in ".!?;:" and len(stripped) < 60:
        return False
    # Reject mid-sentence fragments left by chunk overlap (e.g. "2.0 application ...").
    starts_with_number = stripped[0].isdigit()
    if starts_with_number:
        if not re.match(r"^\d+\.\s", stripped):
            return False
    elif not (stripped[0].isalpha() or stripped[0] in "\"'("):
        return False
    return True


def _parse_context_blocks(user_prompt: str) -> List[Tuple[int, str, str]]:
    return [
        (int(number), title.strip(), content.strip())
        for number, title, content in _BLOCK_RE.findall(user_prompt)
    ]


def _parse_question(user_prompt: str) -> str:
    # Only the trailing block after </context> is the customer's question; the
    # context blocks above it also use <customer_input> wrappers.
    _before, separator, tail = user_prompt.rpartition("</context>")
    matches = _QUESTION_RE.findall(tail if separator else user_prompt)
    return matches[-1].strip() if matches else ""


class MockLLMProvider:
    name = "mock"
    model = "mock-extractive-v1"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> LLMResponse:
        blocks = _parse_context_blocks(user_prompt)
        question_terms = {stem(term) for term in tokenize(_parse_question(user_prompt))}

        selected: List[Tuple[int, str]] = []
        for block_position, (number, _title, content) in enumerate(blocks[:2]):
            sentences = split_sentences(content)
            if not sentences:
                continue

            candidates = [sentence for sentence in sentences if _is_substantive(sentence)]
            if not candidates:
                candidates = sentences

            best_overlap = 0
            best_sentence = candidates[0]
            for sentence in candidates:
                overlap = len(question_terms & {stem(t) for t in tokenize(sentence)})
                # Prefer more overlap, then the longer (more complete) sentence.
                if (overlap, len(sentence)) > (best_overlap, len(best_sentence)):
                    best_overlap = overlap
                    best_sentence = sentence

            # The top block always contributes; a second block only when it shares
            # at least two terms with the question, so answers stay on topic.
            if block_position > 0 and best_overlap < 2:
                continue
            if len(best_sentence) > 420:
                best_sentence = best_sentence[:417].rstrip() + "..."
            selected.append((number, best_sentence))

        answer = " ".join(f"{sentence} [{number}]" for number, sentence in selected).strip()
        if answer and answer[-1] not in ".!?]":
            answer += "."
        if len(answer) > max_tokens * 4:
            answer = answer[: max_tokens * 4].rsplit(" ", 1)[0] + "..."

        return LLMResponse(
            content=answer,
            provider=self.name,
            model=self.model,
            prompt_tokens=len(user_prompt.split()),
            completion_tokens=len(answer.split()),
        )
