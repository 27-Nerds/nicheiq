"""Pain/segment resolver for the user-composed idea seed (chat "propose your own idea").

Tolerantly matches the user's OPTIONAL pain/tool references — and, failing that, the free seed
text itself — against THIS RUN's validated pain titles, then picks an audience segment with real
affinity to whatever pain(s) matched. A genuine match anchors the seed exactly like any other
Multi-Frame focus (reuses `frames.anchor_pains_for_frame_focus`'s >=2-shared-stemmed-token gate,
so a seed is never anchored more loosely than a gap/data-asset/workflow focus is). No genuine
match is a SAFE, HONEST outcome — `anchor_pain_titles=[]`, `segment=None` — never a forced or
fabricated link; the caller grounds on "the niche audience" and evaluates the seed as an
unanchored hypothesis (see `idea_improvement_loop_v4._frame_directive`'s `user_seed` rule).

Pure module: deterministic token overlap only, no I/O, no LLM calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SeedAnchorResult:
    """Resolver outcome. `segment` is the matched `AudienceSegment` object, or None."""

    anchor_pain_titles: list[str]
    segment: object | None


def _exact_title_match(ref: str, pain_points: list) -> Optional[object]:
    """Case/whitespace-insensitive EXACT title match for an explicit `pain_ref` — the
    highest-confidence path (the user picked or typed a specific validated pain by name, not
    just prose). This is the only path that can anchor on ONE pain alone with no corroborating
    token overlap, since the user's own reference IS the evidence."""
    ref_norm = (ref or "").strip().lower()
    if not ref_norm:
        return None
    for p in pain_points or []:
        if (getattr(p, "title", "") or "").strip().lower() == ref_norm:
            return p
    return None


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

    Match order (first genuine hit wins — never both):
      1. `pain_ref` EXACT title match (case/whitespace-insensitive). The user named a specific
         validated pain directly (e.g. picked one from a suggestion list); trust it outright.
      2. Token-overlap match of `seed_text` (+ `tool_ref`, if given) against each pain's
         title/description/representative_quotes, via `frames.anchor_pains_for_frame_focus` —
         the SAME `>=2 shared distinctive stemmed tokens` gate every other Multi-Frame focus
         (gap/data_asset/workflow) is held to. Ranked by shared-token strength, may return
         multiple titles.

    No genuine match at either step -> `([], None)`. This is deliberately NOT an error path: an
    honestly unanchored seed is a normal, expected outcome (the user proposed something this
    run's research doesn't happen to have evidenced) — the caller (`_run_seed_cell`) evaluates it
    as an explicit unanchored hypothesis rather than forcing a link or fabricating one.
    """
    from .frames import FrameFocus, anchor_pains_for_frame_focus

    pain_points = list(pain_points or [])
    segments = list(segments or [])

    exact = _exact_title_match(pain_ref or "", pain_points)
    if exact is not None:
        titles = [getattr(exact, "title", "")]
    else:
        focus = FrameFocus(
            frame="user_seed", key="seed:resolve",
            payload={"seed_text": seed_text or "", "tool_ref": tool_ref or ""},
            anchor_pain_titles=[],
        )
        titles = anchor_pains_for_frame_focus(focus, pain_points)

    if not titles:
        return SeedAnchorResult(anchor_pain_titles=[], segment=None)

    pains_by_title = {(getattr(p, "title", "") or ""): p for p in pain_points}
    anchor_objs = [pains_by_title[t] for t in titles if t in pains_by_title]
    segment = _pick_segment(anchor_objs, segments)
    return SeedAnchorResult(anchor_pain_titles=titles, segment=segment)
