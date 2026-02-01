"""
Pricing Pre-Computations — deterministic values for PricingStrategyCrew.
Used by: PricingStrategyCrew.analyze()
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.pain_point import PainPointAnalysisResult
    from ...models.research_state import AudienceMappingResult, MarketSizingResult
    from ...models.solution_selection import SolutionScores


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


def format_market_sizing_summary(market_sizing: MarketSizingResult | None) -> str:
    """Format market sizing data for pricing context.

    Returns a one-line summary with TAM/SAM/SOM, growth, timing, and viability.
    """
    if market_sizing is None:
        return "Market sizing data not available"

    parts: list[str] = []

    if market_sizing.total_addressable_market:
        parts.append(f"TAM: {market_sizing.total_addressable_market}")
    if market_sizing.serviceable_available_market:
        parts.append(f"SAM: {market_sizing.serviceable_available_market}")
    if market_sizing.serviceable_obtainable_market_y1:
        parts.append(f"SOM Y1: {market_sizing.serviceable_obtainable_market_y1}")

    if market_sizing.market_growth_rate:
        parts.append(f"Growth: {market_sizing.market_growth_rate}")
    if market_sizing.market_timing_assessment:
        parts.append(f"Timing: {market_sizing.market_timing_assessment}")
    if market_sizing.market_viability_verdict:
        parts.append(f"Viability: {market_sizing.market_viability_verdict}")

    return " | ".join(parts) if parts else "Market sizing data incomplete"


def format_audience_budget_sensitivity(
    audience_mapping: AudienceMappingResult | None,
) -> str:
    """Format audience segment budget sensitivity for pricing context.

    Returns primary target segment and per-segment budget sensitivity.
    """
    if audience_mapping is None:
        return "Audience data not available"

    segments = audience_mapping.audience_segments
    if not segments:
        return "No audience segments defined"

    primary = audience_mapping.primary_target_segment or "Not specified"

    segment_parts: list[str] = []
    for seg in segments:
        sensitivity = getattr(seg, "budget_sensitivity", None) or "Unknown"
        segment_parts.append(f"{seg.segment_name} ({sensitivity} sensitivity)")

    segments_str = ", ".join(segment_parts)
    return f"Primary: {primary} | Segments: {segments_str}"


def format_solution_rank_context(
    solution_scores: list[SolutionScores] | None,
    solution_name: str,
) -> str:
    """Format solution ranking and keyword demand for pricing confidence.

    Returns rank, composite score, and keyword demand for the named solution.
    """
    if not solution_scores:
        return "Solution ranking data not available"

    match = None
    for s in solution_scores:
        if s.solution_name == solution_name:
            match = s
            break

    if match is None:
        return f"Solution '{solution_name}' not found in ranking data"

    total = len(solution_scores)
    parts = [f"Rank: #{match.rank} of {total}", f"Composite: {match.composite_score:.2f}"]

    kw = match.keyword_demand_score
    if kw is not None:
        if kw >= 0.7:
            label = "Strong"
        elif kw >= 0.4:
            label = "Moderate"
        else:
            label = "Weak"
        parts.append(f"Keyword Demand: {kw:.2f} ({label})")

    return " | ".join(parts)


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
