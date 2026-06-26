"""
Report Pre-Computations — deterministic values for report generator LLM prompts.
Used by: ReportGenerator._generate_budget_estimate(), _generate_first_30_days_playbook(),
         _generate_pain_solution_mappings()
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.pain_point import PainPoint


# All 8 PricingStrategyResult.pricing_model Literal values covered
BUDGET_RANGES: dict[str, tuple[int, int]] = {
    "Ad-Supported-Free": (50, 300),
    "Affiliate-Only": (100, 400),
    "Freemium-Lite": (200, 800),
    "Freemium": (400, 1500),
    "Subscription": (800, 2500),
    "Usage-Based": (2000, 8000),
    "One-time": (200, 800),
    "Hybrid": (400, 1500),
}


def compute_budget_range(pricing_model: str, channel_count: int) -> str:
    """Pre-compute suggested budget range from pricing model and channel count.

    Returns formatted string like "$400-$1,500/month".
    """
    base_min, base_max = BUDGET_RANGES.get(pricing_model, (400, 1500))

    # More channels = higher budget (complexity multiplier)
    if channel_count >= 4:
        base_min = int(base_min * 1.5)
        base_max = int(base_max * 1.5)

    return f"${base_min:,}-${base_max:,}/month"


def compute_metric_calibration(
    total_keyword_count: int, tier1_keyword_count: int
) -> str:
    """Calibrate 30-day visitor targets to actual keyword volume.

    New site Month 1 ~ 5-10% of steady-state organic.
    Floor values: 50 low-end, 200 high-end.
    """
    if total_keyword_count > 0 and tier1_keyword_count > 0:
        month1_organic = int(tier1_keyword_count * 50 * 0.02)
        visitor_low = max(50, month1_organic)
        visitor_high = max(200, month1_organic * 3)
        return (
            f"Keyword-Calibrated 30-Day Target: {visitor_low}-{visitor_high} visitors "
            f"(based on {tier1_keyword_count} Tier 1 keywords achievable in Month 1)"
        )
    return "No keyword data for metric calibration -- use conservative defaults (300-500 visitors)"


def format_pain_point_with_scores(pp: PainPoint) -> str:
    """Format a single pain point with severity, WTP, and mention count.

    Uses X.Y/10 display convention to match existing pipeline displays
    in prompt_formatters.py and state_accessors.py.
    Metadata placed in brackets AFTER description to preserve title extraction.
    """
    desc = pp.description[:200] + "..." if len(pp.description) > 200 else pp.description
    return (
        f"- {pp.title}: {desc} "
        f"[Severity: {pp.severity_score * 10:.1f}/10, "
        f"WTP: {pp.commercial_intent * 10:.1f}/10, "
        f"Mentions: {pp.mention_count}]"
    )
