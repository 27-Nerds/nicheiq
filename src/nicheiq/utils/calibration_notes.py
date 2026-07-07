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


def extract_criterion_reason(notes: str | None, criterion: str = "market_fit",
                             max_len: int = 170) -> str:
    """Extract one criterion's reason from a calibration_notes string. '' when absent.

    Band-words the critic's raw decimals (user-facing), then truncates at a word boundary
    with an ellipsis when the reason exceeds max_len.
    """
    if not notes:
        return ""
    for seg in notes.split("|"):
        seg = seg.strip()
        if seg.lower().startswith(f"{criterion}:"):
            reason = humanize_score_mentions(seg.split(":", 1)[1].strip())
            if len(reason) <= max_len:
                return reason
            cut = reason[:max_len]
            if " " in cut:
                cut = cut[:cut.rindex(" ")]
            return cut.rstrip(" ,;.") + "…"
    return ""
