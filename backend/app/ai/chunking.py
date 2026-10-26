"""Deterministic, sentence-aware chunking for knowledge-base documents."""
from dataclasses import dataclass
from typing import List

from app.ai.text_utils import normalize_whitespace, split_sentences

DEFAULT_CHUNK_SIZE = 900
DEFAULT_OVERLAP = 150
MIN_CHUNK_SIZE = 60


@dataclass
class TextChunk:
    index: int
    content: str

    @property
    def char_count(self) -> int:
        return len(self.content)


def _hard_slice(unit: str, size: int) -> List[str]:
    """Splits an oversized paragraph on word boundaries (or characters as a last resort)."""
    pieces: List[str] = []
    remaining = unit
    while len(remaining) > size:
        cut = remaining.rfind(" ", 0, size)
        if cut < size // 2:
            cut = size
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _overlap_tail(text: str, overlap: int) -> str:
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    # Start the overlap at a word boundary so chunks do not begin mid-word.
    first_space = tail.find(" ")
    if first_space != -1 and first_space < len(tail) - 1:
        tail = tail[first_space + 1 :]
    return tail.strip()


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> List[TextChunk]:
    """Splits text into overlapping chunks that mostly end on sentence boundaries."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size.")

    normalized = normalize_whitespace(text)
    if not normalized:
        return []

    # Paragraphs first, then sentences, so headings and lists stay readable.
    units: List[str] = []
    for paragraph in normalized.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue
        sentences = split_sentences(paragraph)
        for sentence in sentences or [paragraph]:
            if len(sentence) > chunk_size:
                units.extend(_hard_slice(sentence, chunk_size))
            else:
                units.append(sentence)

    chunks: List[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n{unit}".strip() if current else unit
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current.strip():
            chunks.append(current.strip())
        carried = _overlap_tail(chunks[-1], overlap) if chunks else ""
        current = f"{carried}\n{unit}".strip() if carried else unit
        if len(current) > chunk_size:
            pieces = _hard_slice(current, chunk_size)
            chunks.extend(pieces[:-1])
            current = pieces[-1]

    if current.strip() and len(current.strip()) >= MIN_CHUNK_SIZE:
        chunks.append(current.strip())
    elif current.strip() and chunks:
        # A tiny trailing fragment reads better appended to the previous chunk.
        chunks[-1] = f"{chunks[-1]}\n{current.strip()}".strip()
    elif current.strip():
        chunks.append(current.strip())

    # Drop accidental duplicates while preserving order.
    deduped: List[str] = []
    seen = set()
    for chunk in chunks:
        if chunk and chunk not in seen:
            seen.add(chunk)
            deduped.append(chunk)

    return [TextChunk(index=i, content=content) for i, content in enumerate(deduped)]
