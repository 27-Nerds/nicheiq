"""
Market Sizing Pre-Computations — deterministic values for MarketSizingCrew.
Used by: MarketSizingCrew.analyze()
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.pain_point import PainPointAnalysisResult


def compute_strive_pre_check(
    keyword_volume: int,
    total_mentions: int,
    competitor_count: int,
) -> str:
    """Pre-evaluate 3 of 6 deterministic STRIVE criteria.

    Returns formatted summary string. Income/Velocity/Enterable left for LLM.
    """
    searchable = keyword_volume >= 100_000
    talked_about = total_mentions >= 50
    rivalry = 5 <= competitor_count <= 15
    met = sum([searchable, talked_about, rivalry])
    return (
        f"STRIVE Pre-Check ({met}/3 deterministic criteria met):\n"
        f"- Searchable (100K+ volume): {'YES' if searchable else 'NO'} ({keyword_volume:,} searches)\n"
        f"- Talked About (50+ mentions): {'YES' if talked_about else 'NO'} ({total_mentions} mentions)\n"
        f"- Rivalry (5-15 competitors): {'YES' if rivalry else 'NO'} ({competitor_count} competitors)\n"
        f"- Income (SAM >$50M): LLM to evaluate after TAM/SAM calculation\n"
        f"- Velocity (10%+ growth): LLM to evaluate from trend data\n"
        f"- Enterable (clear channels): LLM to evaluate from competitive landscape"
    )


def compute_saturation_level(competitor_count: int) -> str:
    """Deterministic saturation level from competitor count.

    Returns: "Low", "Medium", or "High"
    """
    if competitor_count < 5:
        return "Low"
    elif competitor_count <= 15:
        return "Medium"
    else:
        return "High"


def compute_tam_seed(total_volume: int) -> str:
    """Keyword-based TAM seed anchor for the LLM to adjust.

    Formula: monthly_volume x $50 avg LTV x 12 months.
    """
    if total_volume > 0:
        baseline = total_volume * 50 * 12
        return (
            f"Keyword-based TAM seed: ${baseline:,.0f}/year "
            f"(based on {total_volume:,} monthly searches x $50 avg LTV x 12 months "
            f"-- adjust LTV based on niche)"
        )
    return "No keyword data for TAM seed calculation"


def compute_wtp_stats(
    pain_point_analysis: PainPointAnalysisResult | None,
) -> dict[str, str | int]:
    """Pre-compute WTP aggregate statistics from pain points.

    Returns dict with keys: high_severity_count, high_wtp_count, avg_wtp (pre-formatted string).
    """
    if not pain_point_analysis or not pain_point_analysis.pain_points:
        return {"high_severity_count": 0, "high_wtp_count": 0, "avg_wtp": "0.00"}

    pain_points = pain_point_analysis.pain_points
    high_severity = len([pp for pp in pain_points if pp.severity_score >= 0.7])
    high_wtp = len([pp for pp in pain_points if pp.willingness_to_pay >= 0.5])
    avg = sum(pp.willingness_to_pay for pp in pain_points) / len(pain_points)

    return {
        "high_severity_count": high_severity,
        "high_wtp_count": high_wtp,
        "avg_wtp": f"{avg:.2f}",
    }
