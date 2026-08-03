"""Off-niche detection for competitive landscapes (downgrade-only).

The competitor researcher can return a landscape from a DIFFERENT industry whenever the
idea's invented name is domain-ambiguous and the agent answers from its prior instead of
searching (live-caught 2026-08-03: "HouseNutIndex" — a live-music venue's fixed operating
cost — produced Mint and YNAB with zero web searches, and the resulting "the personal
finance space is saturated" text flowed into competitor_count, market saturation and
market_gaps_identified for a live-music niche).

The check is deterministic and mirrors the red-team off-category guard
(`utils/red_team_review.py`): build word-boundary/stem matchers from the niche's OWN
vocabulary and require the landscape's competitor + gap text to share at least one term
with it. Zero shared vocabulary is a retrieval/hallucination failure, not market evidence.

Downgrade-only: callers get a caveat string to stamp, never a rewritten landscape.
Fails OPEN — below ``MIN_ANCHORS_ACTIVE`` anchor entities the guard is a no-op.
"""

from __future__ import annotations

import re

from ..jargon_glossary import build_jargon_glossary
from .niche_anchor import Matcher, anchor_coverage, build_anchor_matchers

# Anchor grounding is meaningful only with enough named entities; below this the
# guard is a no-op (mirrors QueryGenerator.MIN_ANCHORS_ACTIVE — see query_generator.py).
MIN_ANCHORS_ACTIVE = 3

# Parentheticals/quoted asides inside a jargon entry ("cottage food operation (CFO)") are
# noise for stem-set matching: the aside's tokens are required too, so the whole term stops
# matching text that uses the plain phrase. Stripped before building matchers.
_ASIDE_RE = re.compile(r"[\(\[“\"][^\)\]”\"]*[\)\]”\"]?")
# Function words carry no niche signal, so a bigram containing one is not distinctive.
_STOPWORDS = frozenset(
    "a an and are as at be by for from in into is its of on or the their to under with "
    "who whose that this these those they while when who's your our".split()
)


def _split_terms(raw: str) -> list[str]:
    """Normalize one vocabulary entry into matchable phrases (asides stripped, / split)."""
    cleaned = _ASIDE_RE.sub(" ", raw or "")
    return [part.strip(" -–—,;:") for part in re.split(r"[/,;]", cleaned) if part.strip()]


def _niche_identity_bigrams(niche_context) -> list[str]:
    """Distinctive adjacent word pairs from the niche's own identity strings.

    A niche's defining phrase ("cottage food", "live music venues") often appears in NO
    structured vocabulary field, so a landscape can be plainly on-niche and still share
    zero anchor terms. Bigrams of adjacent content words recover that identity without
    dropping to single-token matching (which generic words like "food" would defeat).
    """
    out: list[str] = []
    for attr in ("niche_input", "resolved_primary_audience", "user_target_audience"):
        text = getattr(niche_context, attr, None)
        if not isinstance(text, str) or not text.strip():
            continue
        words = re.findall(r"[a-z][a-z0-9-]+", text.lower())
        for first, second in zip(words, words[1:]):
            if first in _STOPWORDS or second in _STOPWORDS:
                continue
            out.append(f"{first} {second}")
    return out


def build_niche_vocab_matchers(niche_context) -> list[Matcher]:
    """Matchers for "does this text belong to the niche at all?".

    Vocabulary = brands (``anchor_entities``) + MULTI-WORD community terms and audience
    jargon + jargon-glossary expansions + niche-identity bigrams. Single-word jargon is
    deliberately excluded: generic tokens ("settlement", "split") stem-match foreign
    evidence and would silently disable the guard. Returns [] when anchors are inactive
    (caller treats as a no-op).
    """
    if niche_context is None:
        return []
    entities = list(getattr(niche_context, "anchor_entities", None) or [])
    if len(entities) < MIN_ANCHORS_ACTIVE:
        return []

    terms: list[str] = []
    for entity in entities:
        terms.extend(_split_terms(entity))
    for attr in ("community_search_terms", "audience_jargon"):
        for term in getattr(niche_context, attr, None) or []:
            if not isinstance(term, str):
                continue
            terms.extend(part for part in _split_terms(term) if len(part.split()) >= 2)
    terms.extend(build_jargon_glossary(niche_context).values())
    terms.extend(_niche_identity_bigrams(niche_context))

    return build_anchor_matchers(terms)


def landscape_evidence_texts(landscape) -> list[str]:
    """The landscape's factual claims, as separate texts to test for niche vocabulary.

    The solution's own name is EXCLUDED — it is the drift source, not evidence.
    """
    texts: list[str] = []
    for comp in getattr(landscape, "competitors", None) or []:
        parts = [
            getattr(comp, "name", "") or "",
            getattr(comp, "description", "") or "",
            " ".join(getattr(comp, "key_features", None) or []),
            getattr(comp, "pricing_model", "") or "",
            " ".join(getattr(comp, "strengths", None) or []),
            " ".join(getattr(comp, "weaknesses", None) or []),
        ]
        texts.append(" ".join(p for p in parts if p))
    texts.extend(t for t in (getattr(landscape, "market_gaps", None) or []) if t)
    texts.extend(
        t for t in (getattr(landscape, "differentiation_opportunities", None) or []) if t
    )
    for attr in ("competitive_intensity", "recommended_positioning", "pricing_insights"):
        value = getattr(landscape, attr, None)
        if value:
            texts.append(value)
    return texts


def assess_landscape_relevance(landscape, niche_context) -> dict:
    """Deterministic on-niche check for one CompetitiveLandscape.

    Returns a dict with:
      active   — whether the guard ran (False = fail-open no-op)
      coverage — fraction of landscape texts carrying >=1 niche term
      off_niche— True only when the guard is active, there is text to judge, and
                 coverage is exactly 0.0 (nothing in the landscape mentions the niche)
      caveat   — caveat string to stamp when off_niche, else None
    """
    matchers = build_niche_vocab_matchers(niche_context)
    texts = landscape_evidence_texts(landscape)
    # A landscape with no competitors is the HONEST-abstain case ("no competitors found
    # via search"), not a drifted one — never caveat it as off-niche.
    if not matchers or not texts or not (getattr(landscape, "competitors", None) or []):
        return {"active": False, "coverage": 0.0, "off_niche": False, "caveat": None}

    coverage = anchor_coverage(texts, matchers)
    if coverage > 0.0:
        return {"active": True, "coverage": coverage, "off_niche": False, "caveat": None}

    niche = (getattr(niche_context, "niche_input", "") or "").strip()
    caveat = (
        "Competitive landscape off-niche: none of the returned competitors, gaps or "
        "positioning share any vocabulary with this niche"
        + (f" ({niche})" if niche else "")
        + " — the competitor research returned a different industry. Competitor count, "
        "market saturation and market-gap claims from this landscape are UNVERIFIED "
        "and must not be read as evidence that the space is uncrowded."
    )
    return {"active": True, "coverage": 0.0, "off_niche": True, "caveat": caveat}
