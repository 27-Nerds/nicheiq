"""Deterministic identity guard for user-submitted product ideas."""

from __future__ import annotations

from collections.abc import Iterable
from math import ceil
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

_AXIS_IDENTITY_FIELDS = {
    "buyer": _IDENTITY_FIELDS + ("target_personas",),
    "job": _IDENTITY_FIELDS,
    "mechanism": _IDENTITY_FIELDS + (
        "data_sources",
        "data_source",
        "data_source_tag",
        "data_access_model",
        "data_acquisition_notes",
    ),
    "channel": _IDENTITY_FIELDS + (
        "distribution_channel",
        "programmatic_seo_opportunity",
        "content_generation_model",
        "organic_discovery_queries",
        "estimated_cac_organic",
        "estimated_cac_paid",
    ),
    "scope": _IDENTITY_FIELDS,
    "business_model": _IDENTITY_FIELDS + ("pricing_strategy", "tags"),
}


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


def structured_synthesis_fidelity_failures(
    proposal: dict, candidate: Any,
) -> list[str]:
    """Return exact Concept Forge identity clauses missing from candidate copy.

    This deliberately reads only product identity fields, never the attached
    `synthesis_evaluation` provenance. Otherwise a drifted candidate would pass
    simply because the original brief was serialized beside it.
    """
    identity_text = " ".join(
        _flatten(getattr(candidate, field, None))
        for field in _IDENTITY_FIELDS
    )
    identity_tokens = _content_tokens(identity_text)
    failures: list[str] = []

    def require(
        label: str, text: str, fraction: float, floor: int,
        candidate_tokens: set[str],
    ) -> None:
        tokens = _content_tokens(text)
        if not tokens:
            return
        required = min(len(tokens), max(floor, ceil(len(tokens) * fraction)))
        if len(tokens & candidate_tokens) < required:
            failures.append(label)

    require(
        "proposedTitle",
        str(proposal.get("proposedTitle") or ""),
        0.5,
        1,
        identity_tokens,
    )
    # An exact Concept Forge option may be refined, but its core product copy
    # must retain most of the selected workflow. A lower threshold let a title,
    # persona, and recycled domain nouns conceal a different mechanism.
    require(
        "proposedBrief",
        str(proposal.get("proposedBrief") or ""),
        0.6,
        3,
        identity_tokens,
    )

    exact = proposal.get("evaluation")
    axes = exact.get("changedAxes") if isinstance(exact, dict) else None
    if isinstance(axes, list):
        for index, axis in enumerate(axes):
            if not isinstance(axis, dict):
                failures.append(f"changedAxes[{index}]")
                continue
            label = str(axis.get("axis") or index)
            axis_fields = _AXIS_IDENTITY_FIELDS.get(label, _IDENTITY_FIELDS)
            axis_tokens = _content_tokens(" ".join(
                _flatten(getattr(candidate, field, None))
                for field in axis_fields
            ))
            require(
                f"changedAxes.{label}.to",
                str(axis.get("to") or ""),
                0.6,
                1,
                axis_tokens,
            )
    return failures
