"""Deterministic identity guard for user-submitted product ideas."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_IDENTITY_FIELDS = (
    "concept_name",
    "one_liner",
    "solution_name",
    "headline",
    "short_description",
    "description",
    "value_proposition",
    "core_features",
    "project_type",
    "mechanism_tag",
    "why_it_works",
    "innovation_angle",
    "technical_approach",
)


def _content_tokens(text: str) -> set[str]:
    from .text_stemmer import stem_tokens
    from .validation.dedup import STOPWORDS, normalize_text

    return stem_tokens({
        token
        for token in normalize_text(text or "").split()
        if len(token) > 2 and token not in STOPWORDS
    })


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(f"{_flatten(k)} {_flatten(v)}" for k, v in value.items())
    if isinstance(value, Iterable):
        return " ".join(_flatten(item) for item in value)
    return str(value)


def seed_fidelity_score(seed_text: str, candidate: Any) -> float:
    """Return distinctive seed-token coverage across a candidate's identity fields."""
    seed_tokens = _content_tokens(seed_text)
    if not seed_tokens:
        return 1.0
    candidate_text = " ".join(
        _flatten(getattr(candidate, field, None))
        for field in _IDENTITY_FIELDS
    )
    shared = seed_tokens & _content_tokens(candidate_text)
    return len(shared) / len(seed_tokens)


def is_seed_faithful(seed_text: str, candidate: Any) -> bool:
    """Require the candidate to retain up to three distinctive terms from the brief.

    Prompts require those product-identity terms to remain visible in the product copy.
    This is a deterministic backstop against an anchor-derived replacement idea, not a
    semantic judge of product quality.
    """
    seed_tokens = _content_tokens(seed_text)
    if not seed_tokens:
        return True
    candidate_text = " ".join(
        _flatten(getattr(candidate, field, None))
        for field in _IDENTITY_FIELDS
    )
    shared = seed_tokens & _content_tokens(candidate_text)
    return len(shared) >= min(3, len(seed_tokens))
