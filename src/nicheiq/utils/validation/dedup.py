"""Hybrid near-duplicate detection using n-gram and token Jaccard similarity.

Borrowed from last30days skill's dedupe.py pattern. Used to deduplicate
social content across sources before pain point analysis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nicheiq.models.social_content import SocialPost

STOPWORDS = frozenset({
    "the", "a", "an", "to", "for", "how", "is", "in", "of", "on",
    "and", "with", "from", "by", "at", "this", "that", "it", "what",
    "are", "do", "can", "i", "my", "we", "you", "your", "me",
})


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def get_ngrams(text: str, n: int = 3) -> set[str]:
    """Extract character n-grams from normalized text."""
    text = normalize_text(text)
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def token_jaccard(text_a: str, text_b: str) -> float:
    """Token-level Jaccard with stopword removal and Snowball stemming."""
    from ..text_stemmer import stem_tokens

    tokens_a = stem_tokens({
        t for t in normalize_text(text_a).split()
        if len(t) > 1 and t not in STOPWORDS
    })
    tokens_b = stem_tokens({
        t for t in normalize_text(text_b).split()
        if len(t) > 1 and t not in STOPWORDS
    })
    return jaccard_similarity(tokens_a, tokens_b)


def hybrid_similarity(text_a: str, text_b: str) -> float:
    """Max of character n-gram and token Jaccard similarity."""
    return max(
        jaccard_similarity(get_ngrams(text_a), get_ngrams(text_b)),
        token_jaccard(text_a, text_b),
    )


def _post_text(post: SocialPost) -> str:
    """Extract comparable text from a SocialPost."""
    parts = [post.title, post.body, post.author]
    return " ".join(p for p in parts if p).strip()


def deduplicate_posts(
    posts: list[SocialPost],
    threshold: float = 0.6,
) -> list[SocialPost]:
    """Remove near-duplicate posts, keeping the higher-engagement version.

    O(n^2) pairwise comparison — acceptable for typical batch sizes (<100 posts).
    """
    if len(posts) <= 1:
        return list(posts)

    kept: list[SocialPost] = []
    for post in posts:
        text = _post_text(post)
        if not text:
            kept.append(post)
            continue
        is_dup = False
        for i, existing in enumerate(kept):
            if hybrid_similarity(text, _post_text(existing)) >= threshold:
                # Keep whichever has higher engagement
                if post.score > existing.score:
                    kept[i] = post
                is_dup = True
                break
        if not is_dup:
            kept.append(post)
    return kept
