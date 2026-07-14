"""Pain/segment resolver for the user-composed idea seed (chat "propose your own idea").

Matches the user's OPTIONAL pain/tool references — and, failing that, the free seed text itself —
against THIS RUN's validated pain titles and descriptions, then picks an audience segment with
real affinity to the ONE best-matched pain. Seed matching is intentionally stricter than general
frame linkage: an advisory pain title is never trusted without product-text corroboration, at
least three distinctive stemmed terms must overlap, and representative quotes are excluded from
matching because broad story context ("game", "player", "fan") creates false product/pain links.
No genuine match is a SAFE, HONEST outcome — `anchor_pain_titles=[]`, `segment=None` — never a
forced or fabricated link; the caller evaluates the seed as an unanchored hypothesis.

Pure module: deterministic token overlap only, no I/O, no LLM calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SeedAnchorResult:
    """Resolver outcome. Match metadata is diagnostic; anchors remain the public contract."""

    anchor_pain_titles: list[str]
    segment: object | None
    match_kind: str = "unanchored"
    rejected_pain_ref: str | None = None
    shared_terms: tuple[str, ...] = ()


def _exact_title_match(ref: str, pain_points: list) -> Optional[object]:
    """Return the canonical pain named by an advisory `pain_ref`, if it exists.

    Exact spelling proves identity, not product compatibility. `resolve_seed_anchors` still
    requires the submitted product text to corroborate this candidate before anchoring it.
    """
    ref_norm = (ref or "").strip().lower()
    if not ref_norm:
        return None
    for p in pain_points or []:
        if (getattr(p, "title", "") or "").strip().lower() == ref_norm:
            return p
    return None


_SEED_MIN_SHARED_TOKENS = 3


def _compatible_pains(seed_text: str, tool_ref: str, pain_points: list) -> list[tuple[object, tuple[str, ...]]]:
    """Rank product-compatible pains using identity text only (title + description).

    Quotes are deliberately evidence-only. Returning at most one primary pain prevents a single
    submitted product from being force-stamped with several loosely related research problems.
    """
    from .frames import _content_tokens

    seed_tokens = _content_tokens(f"{seed_text or ''} {tool_ref or ''}")
    if not seed_tokens:
        return []
    scored: list[tuple[int, str, object, tuple[str, ...]]] = []
    for pain in pain_points or []:
        title = (getattr(pain, "title", "") or "").strip()
        if not title:
            continue
        description = getattr(pain, "description", "") or ""
        shared = tuple(sorted(seed_tokens & _content_tokens(f"{title} {description}")))
        if len(shared) >= _SEED_MIN_SHARED_TOKENS:
            scored.append((len(shared), title.lower(), pain, shared))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(pain, shared) for _, _, pain, shared in scored[:1]]


def _pick_segment(anchor_pains: list, segments: list):
    """Segment with the strongest textual affinity to the matched anchor pain(s), via the same
    deterministic matcher `PainPoint.affected_segments` enrichment uses
    (`segment_matching.match_pain_to_segments`) — which itself returns [] rather than a
    round-robin guess when nothing overlaps. Tries each anchor pain in order (rank order from the
    caller) and returns the first genuine hit; None when nothing overlaps any of them. NEVER an
    arbitrary/round-robin pick — the caller's "the niche audience" fallback is the honest default
    for a no-affinity match."""
    if not segments or not anchor_pains:
        return None
    from .segment_matching import match_pain_to_segments

    seg_by_name = {(getattr(s, "segment_name", "") or ""): s for s in segments}
    for pain in anchor_pains:
        for name in match_pain_to_segments(pain, segments, max_segments=1):
            seg = seg_by_name.get(name)
            if seg is not None:
                return seg
    return None


def resolve_seed_anchors(
    seed_text: str,
    pain_ref: Optional[str],
    tool_ref: Optional[str],
    pain_points: list,
    segments: list,
) -> SeedAnchorResult:
    """Resolve a user idea seed to exact validated pain title(s) + an audience segment.

    Match order:
      1. If `pain_ref` names a canonical pain, test that pain first — but still require product
         compatibility from `seed_text`/`tool_ref`.
      2. Otherwise select the strongest compatible pain using title + description identity text.

    Compatibility requires >=3 shared distinctive stemmed tokens. Quotes do not participate.

    No genuine match at either step -> `([], None)`. This is deliberately NOT an error path: an
    honestly unanchored seed is a normal, expected outcome (the user proposed something this
    run's research doesn't happen to have evidenced) — the caller (`_run_seed_cell`) evaluates it
    as an explicit unanchored hypothesis rather than forcing a link or fabricating one.
    """
    pain_points = list(pain_points or [])
    segments = list(segments or [])

    exact = _exact_title_match(pain_ref or "", pain_points)
    rejected_ref = None
    if exact is not None:
        exact_match = _compatible_pains(seed_text, tool_ref or "", [exact])
        if exact_match:
            pain, shared = exact_match[0]
            title = getattr(pain, "title", "") or ""
            return SeedAnchorResult(
                anchor_pain_titles=[title],
                segment=_pick_segment([pain], segments),
                match_kind="explicit",
                shared_terms=shared,
            )
        rejected_ref = getattr(exact, "title", "") or (pain_ref or "")

    inferred = _compatible_pains(seed_text, tool_ref or "", pain_points)
    if not inferred:
        return SeedAnchorResult(
            anchor_pain_titles=[], segment=None,
            rejected_pain_ref=rejected_ref,
        )

    pain, shared = inferred[0]
    title = getattr(pain, "title", "") or ""
    return SeedAnchorResult(
        anchor_pain_titles=[title],
        segment=_pick_segment([pain], segments),
        match_kind="inferred",
        rejected_pain_ref=rejected_ref,
        shared_terms=shared,
    )
