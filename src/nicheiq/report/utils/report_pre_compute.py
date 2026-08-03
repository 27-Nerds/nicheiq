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


# Weekly share of the 30-day visitor total. Monotone ramp summing to 1.0 — it replaces the
# hardcoded ladder in report_first_30_days_playbook.yaml, whose weeks summed to ~170% of its
# own stated 30-day total and could not be reconciled with a keyword-calibrated target.
_WEEKLY_VISITOR_SHARE: tuple[float, ...] = (0.05, 0.20, 0.30, 0.45)

# Email subscribers as a share of 30-day visitors. Set so the no-keyword-data path reproduces
# the previous static pairing exactly (500 visitors -> 70 subscribers).
_SUBSCRIBER_CONVERSION = 0.14


def _visitor_band(total_keyword_count: int, tier1_keyword_count: int) -> tuple[int, int]:
    """30-day visitor band: keyword-calibrated, else the no-data conservative default."""
    if total_keyword_count > 0 and tier1_keyword_count > 0:
        month1_organic = int(tier1_keyword_count * 50 * 0.02)
        return (max(50, month1_organic), max(200, month1_organic * 3))
    return (300, 500)


def compute_metric_ceiling(total_keyword_count: int, tier1_keyword_count: int) -> str:
    """Hard metric cap for the playbook prompt, from the same band as the anchor.

    The prompt used to hardcode this cap, so a keyword-calibrated anchor above the cap told
    the model to aim at a number it was simultaneously forbidden to reach.
    """
    _, visitor_high = _visitor_band(total_keyword_count, tier1_keyword_count)
    subscriber_high = max(1, round(visitor_high * _SUBSCRIBER_CONVERSION))
    return f"≤{visitor_high:,} visitors, ≤{subscriber_high:,} email subscribers in 30 days"


def compute_metric_calibration(
    total_keyword_count: int, tier1_keyword_count: int
) -> str:
    """Calibrate 30-day visitor targets to actual keyword volume.

    New site Month 1 ~ 5-10% of steady-state organic.
    Floor values: 50 low-end, 200 high-end.
    Emits the weekly ladder and the subscriber target too, so the prompt carries exactly one
    set of numbers instead of a static ladder competing with this anchor.
    """
    visitor_low, visitor_high = _visitor_band(total_keyword_count, tier1_keyword_count)
    if total_keyword_count > 0 and tier1_keyword_count > 0:
        header = (
            f"Keyword-Calibrated 30-Day Target: {visitor_low}-{visitor_high} visitors "
            f"(based on {tier1_keyword_count} Tier 1 keywords achievable in Month 1)"
        )
    else:
        header = (
            "No keyword data for metric calibration -- use conservative defaults "
            f"({visitor_low}-{visitor_high} visitors)"
        )

    ladder = "\n".join(
        f"- Week {week}: {round(visitor_low * share)}-{round(visitor_high * share)} visitors"
        for week, share in enumerate(_WEEKLY_VISITOR_SHARE, start=1)
    )
    subscriber_low = max(1, round(visitor_low * _SUBSCRIBER_CONVERSION))
    subscriber_high = max(1, round(visitor_high * _SUBSCRIBER_CONVERSION))
    return (
        f"{header}\n\n"
        f"Weekly visitor ramp (derived from that target -- use these figures, not your own):\n"
        f"{ladder}\n\n"
        f"30-Day Email Subscriber Target: {subscriber_low}-{subscriber_high} subscribers"
    )


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
