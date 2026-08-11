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


def content_tokens(text: str) -> set[str]:
    """Distinctive stemmed tokens of `text` (public: report layer + crew share it)."""
    from .text_stemmer import stem_tokens
    from .validation.dedup import STOPWORDS, normalize_text

    return stem_tokens({
        token
        for token in normalize_text(text or "").split()
        if len(token) > 2 and token not in STOPWORDS
    })


_content_tokens = content_tokens


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


# ── per-clause drift detection for "Check my idea" seeds (quality pass Q4/Q6) ──

_DRIFT_CLAUSES = ("mechanism", "audience", "problem", "delivery")

_DRIFT_AXIS_BY_CLAUSE = {
    "mechanism": "mechanism",
    "audience": "buyer",  # the buyer axis is what pulls in target_personas
    "problem": "job",
    "delivery": "channel",
}

# Contrast cues that repudiate a term occurring later in the SAME sentence. Token
# overlap alone is negation-blind: a seed can argue AGAINST the pitch using the
# pitch's own vocabulary ("instead of ... another AI reply writer") and still pass
# a shared-token check.
_REPUDIATION_CUES = (
    "instead of", "rather than", "unlike", "avoid", "is not", "are not",
    "do not", "does not", "isn't", "aren't", "don't", "doesn't", "without",
    "never", "no longer", "versus", "not just", "not another",
)


def _sentence_segments(value: Any) -> list[str]:
    """Sentence-scoped segments of one identity field. List items are their own
    segments — concatenating fields (or items) lets a cue at the end of one text
    poison a term at the start of the next."""
    import re

    if value is None:
        return []
    if isinstance(value, str):
        parts = value
    elif isinstance(value, dict):
        return [seg for item in value.items()
                for seg in _sentence_segments(f"{item[0]} {item[1]}")]
    elif isinstance(value, Iterable):
        return [seg for item in value for seg in _sentence_segments(item)]
    else:
        parts = str(value)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", parts) if s.strip()]


def _stem_occurrences(stem: str, sentence: str) -> tuple[int, int]:
    """(clean, repudiated) occurrence counts of `stem` in one sentence.

    A sentence-INITIAL cue ("Rather than X, the product does Y") introduces the
    rejected alternative and then asserts — its scope ends at the first comma, so
    the asserted half stays clean. Mid-sentence cues scope to the end of the
    sentence ("... an escalation request rather than a draft").
    """
    import re

    from .text_stemmer import stem_word

    lower = sentence.lower()
    cue_scopes: list[tuple[int, int]] = []
    for cue in _REPUDIATION_CUES:
        for pos in _find_all(lower, cue):
            if pos == 0:
                comma = lower.find(",", pos)
                end = comma if comma != -1 else len(lower)
            else:
                end = len(lower)
            cue_scopes.append((pos, end))
    clean = repudiated = 0
    for match in re.finditer(r"\w+", lower):
        if stem_word(match.group()) != stem:
            continue
        if any(start < match.start() < end for start, end in cue_scopes):
            repudiated += 1
        else:
            clean += 1
    return clean, repudiated


def _find_all(haystack: str, needle: str) -> list[int]:
    positions = []
    start = 0
    while (pos := haystack.find(needle, start)) != -1:
        positions.append(pos)
        start = pos + 1
    return positions


def seed_clause_drift(
    identity_terms: dict | None,
    candidate: Any,
    inferred_fields: list[str] | None = None,
) -> list[str]:
    """Clauses of the user's pitch the evaluated seed no longer embodies.

    Per STATED clause (inferred or term-less clauses are skipped), the clause
    drifted when:
      (a) at least one clause term appears ONLY in repudiated positions (a
          contrast cue earlier in the same sentence of an axis-scoped identity
          field), or
      (b) no clause term appears in the axis-scoped identity fields at all.

    Deliberately NOT "≥1 shared token" (passes a seed that repositioned against
    the pitched mechanism while reusing its vocabulary) and NOT "all terms must
    survive" (a merely-absent term is not repudiation). Warning-only telemetry —
    consumers disclose, they never reject.
    """
    inferred = set(inferred_fields or [])
    drifted: list[str] = []
    for clause in _DRIFT_CLAUSES:
        if clause in inferred:
            continue
        terms = (identity_terms or {}).get(clause) or []
        stems = content_tokens(" ".join(t for t in terms if isinstance(t, str)))
        if not stems:
            continue
        segments = [
            segment
            for field in _AXIS_IDENTITY_FIELDS[_DRIFT_AXIS_BY_CLAUSE[clause]]
            for segment in _sentence_segments(getattr(candidate, field, None))
        ]
        any_present = False
        fully_repudiated = False
        for stem in stems:
            clean = repudiated = 0
            for segment in segments:
                c, r = _stem_occurrences(stem, segment)
                clean += c
                repudiated += r
            if clean or repudiated:
                any_present = True
            if repudiated and not clean:
                fully_repudiated = True
        if fully_repudiated or not any_present:
            drifted.append(clause)
    return drifted
