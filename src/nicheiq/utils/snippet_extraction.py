"""Sliding-window best-evidence snippet extraction.

Borrowed from last30days skill's snippet.py pattern. Finds the most
query-relevant window within a long text body.
"""

from __future__ import annotations

import re

_STOPWORDS = frozenset({
    "the", "a", "an", "to", "for", "how", "is", "in", "of", "on",
    "and", "with", "from", "by", "at", "this", "that", "it", "what",
    "are", "do", "can",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase tokens with stopword removal and Snowball stemming."""
    from .text_stemmer import stem_tokens
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return stem_tokens({w for w in words if w not in _STOPWORDS and len(w) > 1})


def _truncate_words(text: str, max_words: int) -> str:
    """Truncate text to max_words, adding ellipsis if truncated."""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip() + "..."


def _windows(words: list[str], size: int, overlap: int) -> list[str]:
    """Generate overlapping windows of text."""
    if not words:
        return []
    if len(words) <= size:
        return [" ".join(words)]
    step = max(1, size - overlap)
    return [
        " ".join(words[start : start + size])
        for start in range(0, len(words), step)
    ]


def _token_overlap_score(query_tokens: set[str], window_text: str) -> float:
    """Score a window by query token coverage."""
    if not query_tokens:
        return 0.0
    window_tokens = _tokenize(window_text)
    if not window_tokens:
        return 0.0
    overlap = len(query_tokens & window_tokens)
    return overlap / len(query_tokens)


def best_evidence_window(
    text: str,
    query_terms: list[str],
    window_words: int = 80,
) -> str:
    """Find the window of text with highest overlap with query terms.

    Args:
        text: Full text to search within.
        query_terms: Keywords to match against (e.g., pain point anchor keywords).
        window_words: Maximum words in the returned window.

    Returns:
        The best-matching substring, or the full text if shorter than window.
    """
    if not text:
        return ""
    if not query_terms:
        return _truncate_words(text, window_words)

    words = text.split()
    if len(words) <= window_words:
        return text.strip()

    query_tokens = set()
    for term in query_terms:
        query_tokens.update(_tokenize(term))
    if not query_tokens:
        return _truncate_words(text, window_words)

    candidates = _windows(words, size=min(window_words, len(words)), overlap=20)
    if not candidates:
        return _truncate_words(text, window_words)

    best = max(candidates, key=lambda w: _token_overlap_score(query_tokens, w))
    return _truncate_words(best, window_words)
