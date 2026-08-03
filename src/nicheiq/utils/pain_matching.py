"""Deterministic helpers for scoping validated pains to a solution."""

from __future__ import annotations

from collections.abc import Iterable

from .segment_matching import _tokens


def scope_pains_to_addressed(pains: Iterable, addressed: Iterable[str]) -> list:
    """Return validated pains referenced by a solution's addressed-pain text.

    Exact normalized title matches win naturally. Token overlap covers the common case where
    an idea paraphrases a validated title. No niche-wide fallback is allowed: an empty result
    means the relationship is unproven and downstream solution copy must not invent one.
    """
    addressed_tokens = [_tokens(value) for value in addressed if value]
    addressed_tokens = [tokens for tokens in addressed_tokens if tokens]
    if not addressed_tokens:
        return []

    matched = []
    for pain in pains:
        pain_tokens = _tokens(
            getattr(pain, "title", "") or "",
            " ".join(getattr(pain, "categories", None) or []),
            getattr(pain, "description", "") or "",
        )
        if not pain_tokens:
            continue
        if any(
            shared and len(shared) >= 0.5 * min(len(pain_tokens), len(target_tokens))
            for target_tokens in addressed_tokens
            if (shared := pain_tokens & target_tokens)
        ):
            matched.append(pain)
    return matched


def resolve_solution_pain_points(pains: Iterable, solution) -> list:
    """Resolve and priority-sort only the validated pains a solution claims to address."""
    if solution is None:
        return []

    addressed = list(getattr(solution, "pain_points_addressed", None) or [])
    source_pain = getattr(solution, "source_pain", None)
    if source_pain:
        addressed.append(source_pain)

    matched = scope_pains_to_addressed(pains, addressed)
    return sorted(
        matched,
        key=lambda pain: (
            (getattr(pain, "severity_score", None) or 0)
            + (getattr(pain, "commercial_intent", None) or 0)
        ) / 2,
        reverse=True,
    )
