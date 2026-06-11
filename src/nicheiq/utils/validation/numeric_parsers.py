"""Range-aware numeric parsing for guardrail validation.

Shared by the market-sizing guardrail (TAM/SAM/SOM hierarchy + 3-2-1 rule) and
the pricing guardrail (ARPU/LTV/CAC recomputation). The previous parser grabbed
only the first number, so "$50-80M" parsed as 50 (and dropped the M when the
suffix trailed the second number) — enabling both false passes and spurious
guardrail failures on range-formatted estimates.
"""

from __future__ import annotations

import re

_MULTIPLIERS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}

_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([KMBT])?\s*-\s*\$?\s*(\d+(?:\.\d+)?)\s*([KMBT])?",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([KMBT])?", re.IGNORECASE)
_RATIO_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?::\s*1|x\b)", re.IGNORECASE)


def _normalize(text: str) -> str:
    cleaned = text.replace(",", "")
    # Unicode dashes → ASCII
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    # Word multipliers → letter suffixes
    for word, letter in (
        ("trillion", "T"),
        ("billion", "B"),
        ("million", "M"),
        ("thousand", "K"),
    ):
        cleaned = re.sub(word, letter, cleaned, flags=re.IGNORECASE)
    return cleaned


def _apply(value: float, suffix: str | None) -> float:
    return value * _MULTIPLIERS.get((suffix or "").upper(), 1.0)


def parse_dollar_amount(text: str | None) -> float | None:
    """Parse a dollar amount or range into ABSOLUTE dollars.

    Handles: "$2.5B", "$500K", "USD 50M", "$50M+", "$300", and ranges —
    "$50-80M" (a suffix on either end applies to the suffix-less end, so this
    is 50M-80M, not 50-80M), "$50M-$80M", "$300 - $750", "$5-10".
    Ranges return the midpoint. Returns None when no number is present.
    """
    if not text:
        return None
    cleaned = _normalize(str(text))

    range_match = _RANGE_RE.search(cleaned)
    if range_match:
        low_raw, low_suf, high_raw, high_suf = range_match.groups()
        # A suffix present on only one end applies to both ("$50-80M", "$50M-80")
        low_suf = low_suf or high_suf
        high_suf = high_suf or low_suf
        low = _apply(float(low_raw), low_suf)
        high = _apply(float(high_raw), high_suf)
        return (low + high) / 2

    single_match = _SINGLE_RE.search(cleaned)
    if single_match:
        value_raw, suffix = single_match.groups()
        return _apply(float(value_raw), suffix)

    return None


def parse_ratio(text: str | None) -> float | None:
    """Parse a ratio like "3:1", "2.5 : 1", or "3x" into a float (3.0, 2.5, 3.0).

    Ratio ranges ("12:1 to 48:1") return the midpoint. Falls back to the first
    bare number ("ratio of 3.5") when no ratio syntax is present. Returns None
    when no number is found.
    """
    if not text:
        return None
    cleaned = _normalize(str(text))
    ratio_matches = _RATIO_RE.findall(cleaned)
    if ratio_matches:
        values = [float(m) for m in ratio_matches]
        return (values[0] + values[-1]) / 2 if len(values) > 1 else values[0]
    single_match = _SINGLE_RE.search(cleaned)
    if single_match:
        return float(single_match.group(1))
    return None
