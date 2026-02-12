"""
Crew Helpers - Utility functions for CrewAI crew implementations.
"""

from .content_preparers import (
    prepare_competitor_intelligence,
    prepare_pain_point_content,
)
from .knowledge_helpers import create_knowledge
from .market_sizing_pre_compute import (
    compute_strive_pre_check,
    compute_saturation_level,
    compute_tam_seed,
    compute_wtp_stats,
    compute_seo_market_enrichment,
)
from .pricing_pre_compute import (
    compute_wtp_summary,
    compute_cac_range,
    format_market_sizing_summary,
    format_audience_budget_sensitivity,
    format_solution_rank_context,
)
from .traffic_pre_compute import (
    collect_all_tiered_keywords,
    compute_ad_revenue_estimate,
    compute_affiliate_revenue_estimate,
    compute_commercial_intent_ratio,
    compute_difficulty_weighted_traffic,
    compute_intent_breakdown,
    compute_seo_traffic_enrichment,
    compute_total_revenue_estimate,
    compute_traffic_projection,
    match_niche_to_cpm,
)

__all__ = [
    "create_knowledge",
    "prepare_competitor_intelligence",
    "prepare_pain_point_content",
    "compute_strive_pre_check",
    "compute_saturation_level",
    "compute_tam_seed",
    "compute_wtp_stats",
    "compute_wtp_summary",
    "compute_cac_range",
    "format_market_sizing_summary",
    "format_audience_budget_sensitivity",
    "format_solution_rank_context",
    "collect_all_tiered_keywords",
    "compute_ad_revenue_estimate",
    "compute_affiliate_revenue_estimate",
    "compute_commercial_intent_ratio",
    "compute_difficulty_weighted_traffic",
    "compute_intent_breakdown",
    "compute_seo_market_enrichment",
    "compute_seo_traffic_enrichment",
    "compute_total_revenue_estimate",
    "compute_traffic_projection",
    "match_niche_to_cpm",
]
