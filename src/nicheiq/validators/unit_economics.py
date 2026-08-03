"""Grounding check for the published LTV:CAC ratio.

The pricing crew computes `ltv_to_cac_ratio` from a *suggested* CAC band that is
derived mechanically from `market_fit_score` (`utils/crew_helpers/pricing_pre_compute.py:
compute_cac_range`). That band is a benchmark, not this idea's CAC. The idea's own CAC
lives on the solution (`estimated_cac_organic` / `estimated_cac_paid`) and is deliberately
left blank when a rebuild cannot ground it (`crews/unified_solution_crew.py:
_UNGROUNDABLE_ON_REBUILD`).

When those two diverge the report renders a headline ratio directly above a CAC table
reading "N/A" — a unit-economics claim resting on a number that appears nowhere in the
report (live 2026-08 job 8ef396eb: `7.2:1 to 18:1 (LTV $324 - $810 ÷ CAC $45)` above
Organic N/A / Paid N/A).

This validator is DOWNGRADE-ONLY, matching the convention in `score_validators.py`:

* It can CLEAR a ratio to "not computable" when no CAC was published.
* It can LABEL a ratio as unverified when the CAC it cites is not the published one.
* It never raises a ratio, never coerces one upward past a threshold, and never
  silently rewrites the numeral — an honest ratio that FAILS the 2:1 rule of thumb
  is a real research finding and passes through untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "NOT_COMPUTABLE",
    "LtvCacGroundingResult",
    "apply_ltv_cac_grounding",
    "declares_not_computable",
    "has_numeric_ratio",
    "validate_ltv_cac_grounding",
]

# Prose fields that argue the ratio and so must carry the label when it is downgraded.
# In the 8ef396eb report the "exceeds the mandatory 2:1 threshold" claim sits in
# wtp_validation, not pricing_rationale.
_RATIO_PROSE_FIELDS = ("pricing_rationale", "wtp_validation")

# Rendered in place of a ratio that had no CAC to stand on.
NOT_COMPUTABLE = "Not computable - no CAC estimate established for this idea"

# Values that mean "no CAC", spelled the several ways the pipeline spells them.
_ABSENT_MARKERS = {
    "", "-", "--", "n/a", "na", "n.a.", "none", "null", "unknown", "tbd",
    "not available", "not applicable", "not estimated", "not established",
}

# A real ratio: "3:1", "7.2 : 1", "18x". Deliberately NOT parse_ratio() — that falls
# back to the first bare number, so "N/A - 100% organic traffic" would parse as 100:1.
_RATIO_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?\s*(?::\s*1|x\b)", re.IGNORECASE)

# The CAC the ratio claims to have divided by: "... ÷ CAC $45)", "/ CAC $30-60".
_CITED_CAC_RE = re.compile(
    r"CAC[^0-9]{0,20}\$?\s*(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?:-|to)\s*\$?\s*(\d[\d,]*(?:\.\d+)?))?",
    re.IGNORECASE,
)

# The leading dollar figure(s) of a CAC field: "$15-45 per customer (SEO pages)" -> 15..45.
# Anchored on '$' so the parenthetical prose ("30+ pages") cannot be mistaken for money.
_CAC_BAND_RE = re.compile(
    r"\$\s*(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(?:-|to)\s*\$?\s*(\d[\d,]*(?:\.\d+)?))?",
)

# Range endpoints are rounded by both the model and the report; don't flag rounding.
_BAND_TOLERANCE = 0.10


# A ratio field that declares itself uncomputable rather than asserting a number.
_NOT_COMPUTABLE_RE = re.compile(
    r"\b(n/?a|not\s+computable|not\s+applicable|cannot\s+be\s+computed|"
    r"not\s+established|no\s+cac|unknown|undetermined)\b",
    re.IGNORECASE,
)


def has_numeric_ratio(text: str | None) -> bool:
    """True when the field asserts an actual ratio ("3:1", "18x").

    Deliberately stricter than `parse_ratio`, whose bare-number fallback reads
    "N/A - 100% organic traffic" as 100:1.
    """
    return bool(text and _RATIO_TOKEN_RE.search(str(text)))


def declares_not_computable(text: str | None) -> bool:
    """True when the field states it has no ratio, rather than failing to parse as one."""
    return bool(text and _NOT_COMPUTABLE_RE.search(str(text)))


def _is_absent(value: str | None) -> bool:
    """True when a CAC field carries no usable estimate."""
    if value is None:
        return True
    return str(value).strip().strip(".").lower() in _ABSENT_MARKERS


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def _cac_band(value: str | None) -> tuple[float, float] | None:
    """Dollar band a CAC field publishes, or None when it publishes no number."""
    if _is_absent(value):
        return None
    match = _CAC_BAND_RE.search(str(value))
    if not match:
        return None
    low = _to_float(match.group(1))
    high = _to_float(match.group(2)) if match.group(2) else low
    return (low, high) if low <= high else (high, low)


def _cited_cac_band(ratio_text: str) -> tuple[float, float] | None:
    """The CAC band the ratio string names as its divisor, or None if it names none."""
    match = _CITED_CAC_RE.search(ratio_text)
    if not match:
        return None
    low = _to_float(match.group(1))
    high = _to_float(match.group(2)) if match.group(2) else low
    return (low, high) if low <= high else (high, low)


def _overlaps(cited: tuple[float, float], published: tuple[float, float]) -> bool:
    lo, hi = published
    lo *= 1 - _BAND_TOLERANCE
    hi *= 1 + _BAND_TOLERANCE
    return cited[0] <= hi and cited[1] >= lo


def _fmt(band: tuple[float, float]) -> str:
    def one(v: float) -> str:
        return f"${v:,.0f}" if float(v).is_integer() else f"${v:,.2f}"

    return one(band[0]) if band[0] == band[1] else f"{one(band[0])}-{one(band[1])}"


Status = Literal["ok", "not_applicable", "cleared_ungrounded", "flagged_mismatch"]


@dataclass(frozen=True)
class LtvCacGroundingResult:
    """Outcome of the grounding check.

    `ratio` is what the report should publish: the original string when the check
    passes or does not apply, `NOT_COMPUTABLE` when it was cleared, or the original
    string with a visible "[unverified: ...]" label appended when it was flagged.
    The numeral itself is never altered.
    """

    ratio: str | None
    status: Status
    degradation: str | None = None
    #: Sentence to append to `pricing_rationale`. The rationale argues the ratio
    #: ("...exceeds the mandatory 2:1 threshold"), so clearing the ratio without it would
    #: leave the prose asserting a threshold the number no longer states.
    rationale_note: str | None = None

    @property
    def changed(self) -> bool:
        return self.status in ("cleared_ungrounded", "flagged_mismatch")


def validate_ltv_cac_grounding(
    *,
    solution_name: str,
    ltv_to_cac_ratio: str | None,
    estimated_cac_organic: str | None,
    estimated_cac_paid: str | None,
) -> LtvCacGroundingResult:
    """Check a published LTV:CAC ratio against the CAC the same report publishes.

    Args:
        solution_name: Used only to make the degradation ledger entry identifiable.
        ltv_to_cac_ratio: The ratio as the pricing crew emitted it.
        estimated_cac_organic: The solution's organic CAC field, exactly as rendered
            in the CAC breakdown table (`report/templates/report_templates.py`).
        estimated_cac_paid: The solution's paid CAC field, likewise.

    Returns:
        LtvCacGroundingResult. `status` is one of:

        * ``not_applicable`` - nothing to check (no ratio, or the field already says
          something non-numeric like "N/A - SEO-driven traffic acquisition").
        * ``ok`` - the ratio is grounded, or asserts no divisor to contradict. This
          includes ratios BELOW the 2:1 rule of thumb: a failing ratio is a finding.
        * ``cleared_ungrounded`` - the ratio asserts a number but the report publishes
          no CAC at all. Cleared to ``NOT_COMPUTABLE``.
        * ``flagged_mismatch`` - the ratio names a CAC that is not the published one.
          Preserved verbatim with a visible unverified label.
    """
    text = (ltv_to_cac_ratio or "").strip()
    if not text or not _RATIO_TOKEN_RE.search(text):
        return LtvCacGroundingResult(ratio=ltv_to_cac_ratio, status="not_applicable")

    published = [
        (label, band)
        for label, band in (
            ("organic", _cac_band(estimated_cac_organic)),
            ("paid", _cac_band(estimated_cac_paid)),
        )
        if band is not None
    ]

    if not published:
        return LtvCacGroundingResult(
            ratio=NOT_COMPUTABLE,
            status="cleared_ungrounded",
            degradation=(
                f"{solution_name}: the LTV:CAC ratio '{text}' was computed from a customer "
                "acquisition cost that this report does not establish - both estimated_cac_organic "
                "and estimated_cac_paid are unavailable for this idea. The ratio has been cleared; "
                "unit economics are unverified, and no LTV:CAC threshold has been met or missed."
            ),
            rationale_note=(
                " [LTV:CAC note: no customer acquisition cost was established for this idea, so "
                "any LTV:CAC figure or threshold argued above is unsupported — the ratio has been "
                "cleared to 'not computable'.]"
            ),
        )

    cited = _cited_cac_band(text)
    if cited is None or any(_overlaps(cited, band) for _, band in published):
        return LtvCacGroundingResult(ratio=ltv_to_cac_ratio, status="ok")

    published_desc = " / ".join(f"{_fmt(band)} {label}" for label, band in published)
    label = (
        f" [unverified: divides by CAC {_fmt(cited)}, which is not the CAC this report "
        f"estimates for the idea ({published_desc})]"
    )
    return LtvCacGroundingResult(
        ratio=f"{text}{label}",
        status="flagged_mismatch",
        degradation=(
            f"{solution_name}: the LTV:CAC ratio '{text}' divides by a CAC of {_fmt(cited)}, "
            f"which does not match the acquisition cost this report estimates "
            f"({published_desc}). The ratio is shown as published but is unverified."
        ),
        rationale_note=(
            f" [LTV:CAC note: the ratio above divides by a CAC of {_fmt(cited)}, which is not "
            f"the acquisition cost this report estimates ({published_desc}); treat the ratio "
            "and any threshold argued from it as unverified.]"
        ),
    )


def apply_ltv_cac_grounding(pricing_strategy, selected_solution, solution_name: str):
    """Run the grounding check and return the report's downgraded pricing strategy.

    Returns ``(pricing_strategy, result)``. The first element is a `model_copy` when the
    ratio was downgraded — the report weakens its own rendering, it does not corrupt the
    checkpointed crew output — and the original object otherwise.

    When the ratio is cleared or flagged, the prose that argues it is labelled too:
    clearing the number while the text still asserts "exceeds the mandatory 2:1 threshold"
    would only move the contradiction.
    """
    result = validate_ltv_cac_grounding(
        solution_name=solution_name,
        ltv_to_cac_ratio=getattr(pricing_strategy, "ltv_to_cac_ratio", None),
        estimated_cac_organic=getattr(selected_solution, "estimated_cac_organic", None),
        estimated_cac_paid=getattr(selected_solution, "estimated_cac_paid", None),
    )
    if not result.changed:
        return pricing_strategy, result

    update: dict = {"ltv_to_cac_ratio": result.ratio}
    if result.rationale_note:
        for field in _RATIO_PROSE_FIELDS:
            prose = getattr(pricing_strategy, field, None) or ""
            if "cac" in prose.lower() or "ltv" in prose.lower():
                update[field] = prose + result.rationale_note
    return pricing_strategy.model_copy(update=update), result
