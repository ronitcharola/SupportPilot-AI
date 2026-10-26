"""Small, dependency-free text helpers shared by the mock providers and chunker."""
import math
import re
from collections import Counter
from typing import Dict, List

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'_-]*")

STOPWORDS = frozenset(
    """
    a an and are as at be been being but by can could did do does for from had has have
    how i if in into is it its me my no not of on or our out over so than that the their
    them then there these they this to too us was we were what when where which who why
    will with would you your
    """.split()
)



def normalize_whitespace(text: str) -> str:
    """Collapses trailing spaces, normalizes newlines, and caps blank-line runs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str, *, keep_stopwords: bool = False) -> List[str]:
    tokens = _WORD_RE.findall(text.lower())
    if keep_stopwords:
        return tokens
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


def stem(token: str) -> str:
    """Light, deterministic stemmer so 'charges', 'charged' and 'charge' match."""
    if len(token) <= 3:
        return token

    word = token
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("es") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]

    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break

    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    return word


def term_counts(text: str) -> Counter:
    """Stemmed, stop-word-filtered term frequencies."""
    return Counter(stem(t) for t in tokenize(text))


def split_sentences(text: str) -> List[str]:
    """Splits prose into sentences while keeping list items intact."""
    text = normalize_whitespace(text)
    if not text:
        return []
    # Split after sentence punctuation that follows a letter/bracket. Digits are
    # excluded so numbered list markers ("6. Assign...") never split.
    parts = re.split(r"(?<=[A-Za-z\)\]][.!?])\s+(?=[A-Z0-9(\"'])", text)
    sentences: List[str] = []
    for part in parts:
        for line in part.split("\n"):
            cleaned = line.strip()
            if cleaned:
                sentences.append(cleaned)
    return sentences


def sublinear_weight(count: int) -> float:
    return 1.0 + math.log(count) if count > 0 else 0.0


def top_features(counts: Dict[str, int], limit: int) -> Dict[str, float]:
    weighted = {term: sublinear_weight(count) for term, count in counts.items()}
    ranked = sorted(weighted.items(), key=lambda item: (-item[1], item[0]))
    return dict(ranked[:limit])
