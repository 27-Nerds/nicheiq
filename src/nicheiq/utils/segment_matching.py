"""Deterministic pain-point -> audience-segment matching (Stage 4 enrichment).

Populates ``PainPoint.affected_segments`` by token overlap between a pain's text and each
segment's vocabulary. The earlier matcher only compared pain title/category words to a
segment's ``pain_point_alignment`` under EXACT token equality and left a pain null on any
miss -- so ~half the pains came out unmapped (``anti-cheat`` never matched ``cheaters``,
``performance`` lived only in ``motivation_drivers`` which was ignored). That starves the
downstream (pain x segment) cell builder, which then falls back to arbitrary round-robin.

This matcher widens the signal on both sides (segment_name + alignment + motivation_drivers ;
pain title + categories + description), hyphen-splits and light-stems so ``anti-cheat`` /
``cheaters`` collapse to ``cheat``, and assigns the strongest segment(s) -- but still leaves a
pain null when NOTHING overlaps (e.g. a harassment pain against finance/spectator segments),
because a wrong assignment is worse than the round-robin fallback.
"""
from __future__ import annotations

import re

# Generic words that would otherwise let any pain match any segment. Kept deliberately small;
# "player"/"game" are dropped because in gaming niches they appear in every pain AND every
# segment, collapsing all affinity.
_STOP = {
    "with", "from", "this", "that", "their", "your", "have", "into", "over", "more",
    "what", "when", "which", "while", "where", "they", "them", "than", "then", "also",
    "lack", "high", "risk", "issue", "issues", "problem", "problems", "difficulty",
    "game", "games", "gaming", "player", "players",
}

# Order matters: try longer suffixes first so "organization" -> "organiz", not "organizatio".
_SUFFIXES = ("ization", "isation", "ations", "ation", "ings", "ies", "ers", "ing", "ed", "es", "s")


def _stem(t: str) -> str:
    for suf in _SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    return t


def _tokens(*parts: str) -> set[str]:
    text = " ".join(p for p in parts if p).lower()
    out: set[str] = set()
    for raw in re.split(r"[^a-z0-9]+", text):
        if len(raw) < 4 or raw in _STOP:
            continue
        out.add(_stem(raw))
    return out


def _seg_vocab(segment) -> set[str]:
    return _tokens(
        getattr(segment, "segment_name", "") or "",
        " ".join(getattr(segment, "pain_point_alignment", None) or []),
        " ".join(getattr(segment, "motivation_drivers", None) or []),
    )


def match_pain_to_segments(pain, segments, *, max_segments: int = 2) -> list[str]:
    """Return the segment_name(s) most likely to experience ``pain`` (affinity order), or []
    when there is no real overlap. Caps at ``max_segments`` so a pain doesn't smear across the
    whole audience; ties within one hit of the best score are kept (a genuine multi-segment pain)."""
    if not segments:
        return []
    pv = _tokens(
        getattr(pain, "title", "") or "",
        " ".join(getattr(pain, "categories", None) or []),
        getattr(pain, "description", "") or "",
    )
    if not pv:
        return []
    scored = [(len(pv & _seg_vocab(s)), getattr(s, "segment_name", "") or "") for s in segments]
    best = max((sc for sc, _ in scored), default=0)
    if best <= 0:
        return []
    keep = sorted((sc for sc in scored if sc[0] >= max(1, best - 1) and sc[1]), reverse=True)
    return [name for _, name in keep[:max_segments]]


def normalize_hub_name(name) -> str:
    """Strip a leading 'r/' (case-insensitive) and lowercase, so 'r/OwnerOperators' (from a
    segment's discovery_channels/community_hubs) and the bare 'OwnerOperators' (from a collected
    RedditPost.subreddit) collapse to the same key. Shared between ``match_pain_by_provenance``
    and the hub-validation step that builds ``validated_hubs_by_segment``."""
    if not name:
        return ""
    n = str(name).strip().lower()
    if n.startswith("r/"):
        n = n[2:]
    return n


def match_pain_by_provenance(
    pain, segments, post_to_subreddit, validated_hubs_by_segment, *, max_segments: int = 2
) -> list[str]:
    """Provenance-grounded counterpart to ``match_pain_to_segments``: instead of comparing pain
    vocabulary to segment vocabulary, checks which segment's VALIDATED community hubs the pain's
    ACTUAL source posts came from.

    ``post_to_subreddit`` maps post_id -> raw subreddit/platform label (built once per run from
    the collected corpus). ``validated_hubs_by_segment`` maps segment_name -> a set of normalized
    (see ``normalize_hub_name``) hub names that survived validation for that segment. Returns []
    when the pain has no source-post evidence, or none of it overlaps a validated hub -- a wrong
    provenance claim is worse than leaving the field None (lexical ``affected_segments`` stays as
    fallback either way). Caps at ``max_segments``, mirroring ``match_pain_to_segments``'s
    within-one-hit tie-keep so a genuinely multi-segment pain isn't arbitrarily narrowed to one.
    """
    if not segments or not validated_hubs_by_segment:
        return []
    post_ids = list(getattr(pain, "source_post_ids", None) or []) + list(
        getattr(pain, "matched_post_ids", None) or []
    )
    source_subs = {
        normalize_hub_name(post_to_subreddit.get(pid))
        for pid in post_ids if pid
    }
    source_subs.discard("")
    if not source_subs:
        return []
    scored = []
    for s in segments:
        name = getattr(s, "segment_name", "") or ""
        if not name:
            continue
        hubs = validated_hubs_by_segment.get(name) or set()
        overlap = len(source_subs & hubs)
        if overlap > 0:
            scored.append((overlap, name))
    if not scored:
        return []
    best = max(sc for sc, _ in scored)
    keep = sorted((sc for sc in scored if sc[0] >= max(1, best - 1)), reverse=True)
    return [name for _, name in keep[:max_segments]]
