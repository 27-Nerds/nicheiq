"""
Pricing Pre-Computations — deterministic values for PricingStrategyCrew.
Used by: PricingStrategyCrew.analyze()
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.pain_point import PainPointAnalysisResult


def compute_wtp_summary(
    pain_point_analysis: PainPointAnalysisResult | None,
) -> tuple[str, str]:
    """Compute WTP aggregate summary and pre-formatted average.

    Returns: (wtp_summary string, avg_wtp pre-formatted string)
    """
    if not pain_point_analysis or not pain_point_analysis.pain_points:
        return ("No WTP data available", "0.00")

    scores = [pp.willingness_to_pay for pp in pain_point_analysis.pain_points]
    avg = sum(scores) / len(scores)
    mn, mx = min(scores), max(scores)
    high_count = sum(1 for s in scores if s >= 0.5)

    if avg >= 0.70:
        tolerance = "Premium (+20-40% vs median)"
    elif avg >= 0.50:
        tolerance = "Market Rate (+-10% of median)"
    elif avg >= 0.30:
        tolerance = "Discount (-20-40% vs median)"
    else:
        tolerance = "Free/Near-Free (ad-supported or data play)"

    summary = (
        f"Average WTP: {avg:.2f} | Range: {mn:.2f}-{mx:.2f} | "
        f"High-WTP pain points (>=0.5): {high_count}/{len(scores)}\n"
        f"Implied Price Tolerance: {tolerance}"
    )
    return (summary, f"{avg:.2f}")


def compute_cac_range(market_fit_score: float | None) -> str:
    """Pre-compute suggested CAC range from market fit score.

    Returns formatted string with CAC range and acquisition strategy hint.
    """
    if market_fit_score is None:
        return "Cannot estimate -- market fit score unavailable"
    if market_fit_score > 0.75:
        return "$15-30 (organic/SEO-focused)"
    elif market_fit_score >= 0.60:
        return "$30-60 (mixed organic + paid)"
    else:
        return "$60-120 (paid-heavy acquisition)"
