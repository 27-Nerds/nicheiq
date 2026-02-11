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


def compute_seo_market_enrichment(seo_report) -> str:
    """Extract SEO tier data for market sizing enrichment.

    Uses shared helpers from traffic_pre_compute for difficulty-weighted traffic
    and intent analysis.

    Args:
        seo_report: SEOStrategyReport object with tier keywords and geographic/category groups.

    Returns:
        Formatted string with SEO-enriched market signals for crew context.
    """
    if seo_report is None:
        return ""

    from .traffic_pre_compute import (
        collect_all_tiered_keywords,
        compute_commercial_intent_ratio,
        compute_difficulty_weighted_traffic,
        compute_intent_breakdown,
    )

    t1 = getattr(seo_report, 'tier_1_keywords', None) or []
    t2 = getattr(seo_report, 'tier_2_keywords', None) or []
    t1_volume = sum(getattr(kw, 'search_volume', 0) or 0 for kw in t1)
    t2_volume = sum(getattr(kw, 'search_volume', 0) or 0 for kw in t2)

    # Difficulty-weighted traffic ceilings
    t1_low, t1_high = compute_difficulty_weighted_traffic(t1)
    t2_low, t2_high = compute_difficulty_weighted_traffic(t2)
    y1_low = t1_low + int(t2_low * 0.6)
    y1_high = t1_high + int(t2_high * 0.6)
    y3_low = t1_low + t2_low
    y3_high = t1_high + t2_high

    # Intent analysis
    all_keywords = collect_all_tiered_keywords(seo_report)
    intent = compute_intent_breakdown(all_keywords)
    commercial_pct = compute_commercial_intent_ratio(intent)
    commercial_vol = intent.get("commercial", {}).get("volume", 0)
    informational_vol = intent.get("informational", {}).get("volume", 0)

    # Geographic / category expansion
    geo_groups = getattr(seo_report, 'tier_3_geographic_groups', None) or []
    cat_groups = getattr(seo_report, 'tier_4_category_groups', None) or []

    geo_volume = sum(
        sum(getattr(kw, 'search_volume', 0) or 0 for kw in (getattr(g, 'keywords', None) or []))
        for g in geo_groups
    )
    cat_volume = sum(
        sum(getattr(kw, 'search_volume', 0) or 0 for kw in (getattr(g, 'keywords', None) or []))
        for g in cat_groups
    )

    core_volume = t1_volume + t2_volume
    geo_uplift_pct = (geo_volume / core_volume * 100) if core_volume > 0 else 0
    cat_uplift_pct = (cat_volume / core_volume * 100) if core_volume > 0 else 0

    # Difficulty distribution
    all_kws = list(t1) + list(t2)
    total = len(all_kws) or 1
    easy = sum(1 for kw in all_kws if (getattr(kw, 'keyword_difficulty', None) or 0) < 25)
    medium = sum(1 for kw in all_kws if 25 <= (getattr(kw, 'keyword_difficulty', None) or 0) < 50)
    hard = sum(1 for kw in all_kws if (getattr(kw, 'keyword_difficulty', None) or 0) >= 50)

    # Topic clusters
    topic_clusters = getattr(seo_report, "topic_clusters", None) or []

    lines = [
        "DIFFICULTY-WEIGHTED DEMAND ANALYSIS:",
        f"- Organic Traffic Ceiling Y1: {y1_low:,}-{y1_high:,} visits/mo "
        f"(Tier 1 fully + 60% Tier 2, difficulty-weighted)",
        f"- Organic Traffic Ceiling Y3: {y3_low:,}-{y3_high:,} visits/mo "
        f"(Tier 1+2 fully, difficulty-weighted)",
        f"  Method: sum(volume x CTR_at_expected_position x ranking_probability)",
        "NOTE: The traffic ceiling validates demand signal strength, not SOM revenue ceiling.",
        "SOM represents total market opportunity (product sales, services, partnerships)",
        "while traffic ceiling represents organic content monetization only.",
        "",
        "COMMERCIAL VIABILITY:",
        f"- Commercial Intent Ratio: {commercial_pct:.0f}%",
    ]

    if commercial_pct >= 40:
        lines.append("  (>40% = strong commercial viability)")
    elif commercial_pct >= 20:
        lines.append("  (20-40% = moderate commercial viability)")
    else:
        lines.append("  (<20% = weak direct revenue potential)")

    lines.append(f"- Commercial keyword volume: {commercial_vol:,}/mo (direct revenue potential)")
    lines.append(f"- Informational keyword volume: {informational_vol:,}/mo (content/ad monetization only)")

    lines.append("")
    lines.append("TAM EXPANSION SCENARIOS:")
    lines.append(f"- Core (Tier 1+2): {core_volume:,}/mo search volume")
    if geo_volume > 0:
        lines.append(f"- Geographic expansion: +{geo_volume:,}/mo ({geo_uplift_pct:.0f}% uplift over core)")
    if cat_volume > 0:
        lines.append(f"- Category expansion: +{cat_volume:,}/mo ({cat_uplift_pct:.0f}% uplift over core)")

    if topic_clusters:
        lines.append("")
        lines.append("MARKET SEGMENTATION (from topic clusters):")
        total_cluster_vol = sum(getattr(c, "total_monthly_volume", 0) or 0 for c in topic_clusters)
        lines.append(f"- {len(topic_clusters)} content clusters identified, total addressable: {total_cluster_vol:,}/mo")
        largest = max(topic_clusters, key=lambda c: getattr(c, "total_monthly_volume", 0) or 0, default=None)
        if largest:
            l_name = getattr(largest, "cluster_name", "Unknown")
            l_vol = getattr(largest, "total_monthly_volume", 0) or 0
            l_pct = (l_vol / total_cluster_vol * 100) if total_cluster_vol > 0 else 0
            lines.append(f"- Largest cluster: {l_name} ({l_vol:,}/mo, {l_pct:.0f}% of total)")

    lines.append("")
    lines.append(
        f"Difficulty Distribution: {easy/total*100:.0f}% easy / "
        f"{medium/total*100:.0f}% medium / {hard/total*100:.0f}% hard"
    )

    return "\n".join(lines)
