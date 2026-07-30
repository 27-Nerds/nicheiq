"""Deterministic niche-jargon glossary (2026-07-30 run-quality fixes, §4).

Ambiguous niche acronyms escape Stage 1 unexpanded ("SMS" = shop management system
in the auto-repair niche) and then poison downstream search queries and idea names
(docs/RUN_QUALITY_ROOT_CAUSES.md §2/§4: probe queries for "SMS migration" retrieved
text-messaging and devops content, laundering a retrieval failure into a market
conclusion). Stage 1 already produces the mapping — audience_jargon entries like
"DVI (digital vehicle inspection)" and industry_boundaries prose like "shop
management systems (SMS)" — but nothing parsed it into a substitution table.

Pure text parsing, no LLM call. Fail-soft: empty dict / unchanged text on any
missing or malformed input.
"""

from __future__ import annotations

import re

# ``SHORT (long form)`` — the all-caps 2-6-char side is the acronym.
_SHORT_LONG_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,5})\s*\(([^()]{3,60})\)")
# ``long form (SHORT)`` — expansion first, acronym parenthesized (the
# industry_boundaries prose shape: "shop management systems (SMS)").
_LONG_SHORT_RE = re.compile(r"\b([A-Za-z][\w\s/-]{2,60}?)\s*\(([A-Z][A-Z0-9]{1,5})\)")


def _clean_long(long: str) -> str:
    """Normalize an expansion phrase: collapse whitespace, drop a trailing plural 's'
    on the LAST word only when the singular stays a word (>=4 chars, not 'ss').
    The acronym key is NEVER singularized — stripping 's' from 'SMS' would corrupt it.
    """
    long = " ".join(long.split()).strip(" .,;:")
    words = long.split()
    if words:
        last = words[-1]
        if len(last) >= 5 and last.endswith("s") and not last.endswith("ss"):
            words[-1] = last[:-1]
            long = " ".join(words)
    return long


def _trim_to_initials(long: str, short: str) -> str:
    """For the ``long form (SHORT)`` prose shape the regex capture runs from the
    sentence start ("This market includes shop management systems"). Trim to the
    trailing word-suffix whose initials spell the acronym; '' when no suffix does
    (the pair is then skipped — an initials mismatch means the parenthetical was
    not an acronym definition at all).
    """
    words = long.split()
    n = len(short)
    if len(words) >= n:
        suffix = words[-n:]
        if "".join(w[0] for w in suffix).lower() == short.lower():
            return " ".join(suffix)
    return ""


def build_jargon_glossary(niche_context) -> dict[str, str]:
    """{acronym_lower: expansion} parsed from ``audience_jargon`` entries and
    ``industry_boundaries`` prose. First-wins on duplicate acronyms (jargon entries
    are scanned before boundaries prose — they are the curated source). Skips
    self-referential pairs (expansion == acronym) and expansions that are
    themselves all-caps acronyms.
    """
    if niche_context is None:
        return {}
    texts: list[str] = []
    for item in getattr(niche_context, "audience_jargon", None) or []:
        if isinstance(item, str) and item.strip():
            texts.append(item)
    boundaries = getattr(niche_context, "industry_boundaries", None) or ""
    if isinstance(boundaries, str) and boundaries.strip():
        texts.append(boundaries)

    glossary: dict[str, str] = {}
    for text in texts:
        pairs: list[tuple[str, str]] = []
        for m in _SHORT_LONG_RE.finditer(text):
            pairs.append((m.group(1), m.group(2)))
        for m in _LONG_SHORT_RE.finditer(text):
            trimmed = _trim_to_initials(" ".join(m.group(1).split()), m.group(2))
            if trimmed:
                pairs.append((m.group(2), trimmed))
        for short, long in pairs:
            long = _clean_long(long)
            if not long or long.upper() == short.upper():
                continue
            if long.isupper():  # expansion is itself an acronym — not a real expansion
                continue
            key = short.lower()
            if key not in glossary:
                glossary[key] = long.lower()
    return glossary


def expand_jargon(text: str, glossary: dict[str, str]) -> str:
    """Replace each glossary acronym in ``text`` with its expansion.

    Case-insensitive, word-boundary-safe ("sms" never matches inside "transmission").
    No-op on empty text or glossary.
    """
    if not text or not glossary:
        return text
    for short, long in glossary.items():
        text = re.sub(rf"\b{re.escape(short)}\b", long, text, flags=re.IGNORECASE)
    return text
