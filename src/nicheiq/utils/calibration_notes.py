"""Parse persisted calibration_notes strings ('market_fit: ... | technical_feasibility: ...').

Shared by the regen scoreboard (unified_solution_crew) and the report's per-idea honest
brief (report_generator) — both surface the critic's verbatim reason for one criterion.

The extracted reason is USER-FACING (the honest brief's "Independent critic's take"), so raw
0-1 decimals the critic cites ("a validated 0.60-severity pain", "(0.45)") are converted to
the shared qualitative bands before display — the internal scale never reaches the user
(band-words convention). The full verbatim notes stay on calibration_notes for audit.
"""

import re

# Bare 0-1 decimals ("0.60", "0.45") not part of a larger number or a dollar amount.
_DECIMAL_RE = re.compile(r"(?<![$\d.])[01]\.\d{1,3}(?!\d)")

# Wallet-class enum tokens the critic echoes from its payability input line ("personal-wallet
# payability (weak)") — swapped for plain English inline. Same band-words convention as the
# decimals: internal vocabulary never reaches the user. "mixed" is a common word, left alone.
_WALLET_TOKEN_RE = re.compile(
    r"\b(corporate-budget|smb-budget|prosumer-wallet|personal-wallet)\b", re.IGNORECASE)
_WALLET_TOKEN_INLINE = {
    "corporate-budget": "corporate budget",
    "smb-budget": "small-business budget",
    "prosumer-wallet": "prosumer out-of-pocket",
    "personal-wallet": "personal out-of-pocket",
}


def humanize_score_mentions(text: str) -> str:
    """Replace bare 0-1 decimals with score_band words ('0.60-severity' -> 'moderate-severity',
    '(0.45)' -> '(limited)') and wallet-class enum tokens with plain English ('personal-wallet
    payability' -> 'personal out-of-pocket payability'). Dollar amounts and out-of-range
    numbers are left alone."""
    from .score_helpers import score_band

    def _sub(m: re.Match) -> str:
        v = float(m.group(0))
        return score_band(v) if 0.0 <= v <= 1.0 else m.group(0)

    text = _DECIMAL_RE.sub(_sub, text)
    return _WALLET_TOKEN_RE.sub(lambda m: _WALLET_TOKEN_INLINE[m.group(0).lower()], text)


#: Longest reason worth persisting per criterion. Matches the largest `max_len` any
#: consumer asks for (report_generator and research_flow both pass 280), so the
#: display cap is the binding one and storage never silently loses text the UI
#: would have shown.
MAX_STORED_REASON_LEN = 280


# Inline markdown the critics occasionally emit ("*structurally* different", `market_fit`).
# Every consumer of these strings is a plain-text UI slot that renders no markdown, so the
# markers would be shown literally. Underscore emphasis is only recognized at word edges so
# snake_case identifiers (market_fit_score) survive intact.
_MD_STAR_RE = re.compile(r"(?<!\w)(\*{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)")
_MD_UNDERSCORE_RE = re.compile(r"(?<!\w)(_{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)")
_MD_CODE_RE = re.compile(r"`([^`]+)`")

#: Function words a cut must never dangle on — "…the", "…and", "…for" reads as a rendering
#: bug rather than an abbreviation, which is exactly how the live audit reported it.
_DANGLING_TAIL_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "of", "to", "for", "with", "in", "on", "at",
    "by", "from", "as", "is", "are", "was", "were", "that", "which", "who", "whose",
    "its", "it", "this", "these", "those", "than", "then", "so", "into", "over",
    "under", "not", "no", "be", "been", "has", "have", "had", "will", "would", "can",
    "could", "may", "might", "also", "per", "their", "there", "if", "when", "while",
    "about", "after", "before", "because", "such", "any", "each", "more", "most",
})

_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")

#: A sentence-boundary cut that keeps less than this fraction of the budget throws away text
#: the reader could have had; below it we prefer a word-boundary cut with an ellipsis.
_SENTENCE_CUT_FLOOR = 0.6


def strip_markdown_emphasis(text: str) -> str:
    """Drop inline markdown emphasis / code fencing, keeping the words themselves."""
    out = text or ""
    for pattern in (_MD_STAR_RE, _MD_UNDERSCORE_RE):
        prev = None
        while prev != out:
            prev = out
            out = pattern.sub(r"\2", out)
    return _MD_CODE_RE.sub(r"\1", out)


def truncate_at_word(text: str, max_len: int) -> str:
    """Cut `text` to at most `max_len` chars on a word boundary, marking the cut with '…'.

    Critic reasons are written as "addresses X, but Y" — the caveat lands last, so a raw
    slice removes the only clause that makes the sentence a concern rather than praise.
    Never slice these by hand; the '…' is also the reader's signal that more existed.

    Trailing function words are dropped after the cut so the result never dangles on a
    bare article or conjunction ("…the"), which reads as truncation damage, not brevity.
    """
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    cut = cut.rstrip(" ,;:.—–-")
    words = cut.split(" ")
    while len(words) > 1 and words[-1].strip("(\"'“‘").casefold() in _DANGLING_TAIL_WORDS:
        words.pop()
    return " ".join(words).rstrip(" ,;:.—–-") + "…"


def truncate_for_display(text: str | None, max_len: int) -> str:
    """User-facing cleanup for a free-text critic string: markdown stripped, whitespace
    collapsed, and capped at `max_len` on the last COMPLETE sentence that fits.

    A sentence-boundary cut needs no ellipsis — it ends a thought — but it only wins when it
    keeps most of the budget; otherwise it discards text that would have fit, so we fall back
    to `truncate_at_word`. Text already within budget is returned whole.
    """
    out = " ".join(strip_markdown_emphasis(text or "").split())
    if len(out) <= max_len:
        return out
    ends = [m.end() for m in _SENTENCE_END_RE.finditer(out) if m.end() <= max_len]
    if ends and ends[-1] >= max_len * _SENTENCE_CUT_FLOOR:
        return out[:ends[-1]].strip()
    return truncate_at_word(out, max_len)


def extract_criterion_reason(notes: str | None, criterion: str = "market_fit",
                             max_len: int = 170) -> str:
    """Extract one criterion's reason from a calibration_notes string. '' when absent.

    Band-words the critic's raw decimals (user-facing), strips inline markdown, then cuts to
    max_len on a sentence boundary where one fits and a word boundary with an ellipsis
    otherwise — an over-long reason must never be handed to the UI ending mid-clause.
    """
    if not notes:
        return ""
    for seg in notes.split("|"):
        seg = seg.strip()
        if seg.lower().startswith(f"{criterion}:"):
            reason = humanize_score_mentions(seg.split(":", 1)[1].strip())
            return truncate_for_display(reason, max_len)
    return ""
