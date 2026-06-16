"""Niche-anchor matching helpers.

Shared, niche-agnostic utilities for deciding whether a piece of text contains a
niche's "anchor" vocabulary (specific named entities / disambiguation-exclusion
terms). Used by query generation, thread relevance validation, pain-point
evidence ranking, idea-coverage matching, and the drift caveat.

Matching is WORD-BOUNDARY + STEM based, never naive substring — so an anchor term
like "pro" cannot match inside "protein", and "weight" cannot match inside
"weightlifting". A term matches if EITHER:
  - its lowercased phrase appears as a whole-word/phrase span in the text, OR
  - all of its stemmed tokens are present in the text's stemmed token set.

All functions are fail-open friendly: an empty matcher list means "no anchors
configured", and callers should treat that as a no-op (never drop content).
"""

from __future__ import annotations

import re

from ..text_stemmer import stem_tokens

# A "word" is a run of letters/digits (length >= 2 to skip noise like single chars).
_WORD_RE = re.compile(r"[a-z0-9]{2,}")

# Matcher tuple: (lowercased phrase, frozenset of stemmed tokens for that phrase).
Matcher = tuple[str, frozenset]


def _tokens(text: str) -> set[str]:
    """Lowercase word tokens (>=2 chars) from arbitrary text."""
    return set(_WORD_RE.findall(text.lower()))


def build_anchor_matchers(terms: list[str]) -> list[Matcher]:
    """Build (phrase, stem_set) matchers from raw anchor/exclusion terms.

    Empty/blank terms are skipped. The returned list is empty when no usable
    terms are provided, which callers should treat as "anchors inactive".
    """
    matchers: list[Matcher] = []
    for term in terms or []:
        phrase = (term or "").strip().lower()
        if not phrase:
            continue
        toks = _tokens(phrase)
        if not toks:
            continue
        matchers.append((phrase, frozenset(stem_tokens(toks))))
    return matchers


def _phrase_in_text(phrase: str, text_lower: str) -> bool:
    """True if `phrase` occurs in `text_lower` at word boundaries.

    Avoids substring false positives ("pro" in "protein"). For multi-word
    phrases this checks the phrase as a contiguous word-boundary span; if the
    phrase contains punctuation/spacing the boundary check still keys on the
    alphanumeric edges.
    """
    pat = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return re.search(pat, text_lower) is not None


def text_has_anchor(text: str, matchers: list[Matcher]) -> bool:
    """True if `text` contains at least one anchor (phrase span OR full stem set)."""
    if not matchers or not text:
        return False
    text_lower = text.lower()
    stems = stem_tokens(_tokens(text_lower))
    for phrase, phrase_stems in matchers:
        if _phrase_in_text(phrase, text_lower):
            return True
        if phrase_stems and phrase_stems <= stems:
            return True
    return False


def anchor_coverage(texts: list[str], matchers: list[Matcher]) -> float:
    """Fraction of `texts` containing >=1 anchor term (0.0 when no texts)."""
    if not texts:
        return 0.0
    if not matchers:
        return 0.0
    hits = sum(1 for t in texts if text_has_anchor(t, matchers))
    return hits / len(texts)


def format_anchor_block(niche_context, max_entities: int = 20, max_exclusions: int = 12) -> str:
    """Render the niche's anchor vocabulary as a prompt block.

    Shared by query generation (Reddit/HN/YouTube) and thread-relevance
    validation so every LLM that touches the niche sees the same disambiguating
    entities. Returns "" when no anchor entities are configured, so callers can
    append it unconditionally and it becomes a no-op for generic niches.
    """
    if niche_context is None:
        return ""
    entities = list(getattr(niche_context, "anchor_entities", []) or [])[:max_entities]
    if not entities:
        return ""
    exclusions = list(getattr(niche_context, "disambiguation_exclusions", []) or [])[:max_exclusions]
    communities = list(getattr(niche_context, "anchor_communities", []) or [])[:8]

    parts = [
        "\n**ANCHOR ENTITIES** (specific named items that identify this niche — "
        "favor these to stay on-topic and avoid adjacent topics):",
        ", ".join(entities),
    ]
    if exclusions:
        parts.append(
            "\n**OUT-OF-SCOPE — DO NOT TARGET** (adjacent senses that share this "
            "niche's words but are a DIFFERENT topic; never write queries/judge "
            "threads about these):"
        )
        parts.append(", ".join(exclusions))
    if communities:
        parts.append("\n**TARGET COMMUNITIES**: " + ", ".join(communities))
    return "\n".join(parts) + "\n"
