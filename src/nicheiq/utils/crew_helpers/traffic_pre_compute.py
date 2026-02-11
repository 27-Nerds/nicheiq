"""
Traffic Monetization Pre-Computations — deterministic values for TrafficMonetizationCrew.
Used by: TrafficMonetizationCrew.analyze(), MarketSizingCrew.analyze()
"""
from __future__ import annotations

import re


# ──────────────────────────────────────────────────────────────────────
# Evidence-based KD profiles
# Sources: Backlinko CTR study (874K URLs, 5M queries) + Ahrefs/Animalz model
# ──────────────────────────────────────────────────────────────────────
KD_PROFILES = {
    "easy": {"kd_max": 25, "position": (3, 5), "p_rank": 0.8, "ctr": (0.065, 0.11)},
    "medium": {"kd_max": 50, "position": (5, 8), "p_rank": 0.45, "ctr": (0.030, 0.065)},
    "hard": {"kd_max": 100, "position": (8, 15), "p_rank": 0.12, "ctr": (0.005, 0.030)},
}


def _get_kd_profile(kd: float | int | None) -> dict:
    """Return the KD profile for a given keyword difficulty score."""
    if kd is None:
        return KD_PROFILES["medium"]
    if kd < 25:
        return KD_PROFILES["easy"]
    if kd < 50:
        return KD_PROFILES["medium"]
    return KD_PROFILES["hard"]


# ──────────────────────────────────────────────────────────────────────
# Shared helpers (used by both traffic and market sizing)
# ──────────────────────────────────────────────────────────────────────

def collect_all_tiered_keywords(seo_report) -> list:
    """Gather keywords from tier_0 + tier_1 + tier_2 into a flat list.

    Uses getattr() defensively for each tier.
    Returns empty list if seo_report is None.
    """
    if seo_report is None:
        return []
    t0 = getattr(seo_report, "tier_0_keywords", None) or []
    t1 = getattr(seo_report, "tier_1_keywords", None) or []
    t2 = getattr(seo_report, "tier_2_keywords", None) or []
    return list(t0) + list(t1) + list(t2)


def compute_difficulty_weighted_traffic(keywords) -> tuple[int, int]:
    """Estimate achievable monthly organic traffic using evidence-based CTR model.

    Model basis:
    - CTR by position: Backlinko study (874K URLs, 5M queries)
    - KD -> ranking probability: calibrated estimates for well-optimized new domains (DA < 30)

    Instead of naive volume x flat_CTR, this uses:
      traffic = volume x CTR_at_expected_position x ranking_probability

    Where expected_position and ranking_probability are derived from KD.

    Returns (conservative, optimistic) monthly visitors.
    """
    if not keywords:
        return (0, 0)

    low_total = 0
    high_total = 0
    for kw in keywords:
        volume = getattr(kw, "search_volume", 0) or 0
        if volume <= 0:
            continue
        kd = getattr(kw, "keyword_difficulty", None)
        profile = _get_kd_profile(kd)
        ctr_low, ctr_high = profile["ctr"]
        p_rank = profile["p_rank"]
        low_total += volume * ctr_low * p_rank
        high_total += volume * ctr_high * p_rank

    return (int(low_total), int(high_total))


def compute_intent_breakdown(keywords) -> dict:
    """Bucket keywords by intent using priority-cascade substring matching.

    Commercial is checked first (takes priority when both match).
    Returns {bucket: {"count": int, "volume": int}}.
    """
    if not keywords:
        return {}

    # Priority cascade: commercial checked first, then informational, fallback other
    commercial_patterns = [
        "commercial", "transactional", "conversion", "purchase", "buy",
        "comparison", "vs", "pricing", "alternative", "recommend",
    ]
    informational_patterns = [
        "informational", "research", "learn", "how to", "educational",
        "guide", "what is", "tutorial",
    ]

    buckets: dict[str, dict[str, int]] = {
        "commercial": {"count": 0, "volume": 0},
        "informational": {"count": 0, "volume": 0},
        "other": {"count": 0, "volume": 0},
    }

    for kw in keywords:
        intent = (getattr(kw, "intent", None) or "").lower()
        volume = getattr(kw, "search_volume", 0) or 0

        # Priority cascade: commercial first
        if any(p in intent for p in commercial_patterns):
            bucket = "commercial"
        elif any(p in intent for p in informational_patterns):
            bucket = "informational"
        else:
            bucket = "other"

        buckets[bucket]["count"] += 1
        buckets[bucket]["volume"] += volume

    return buckets


def compute_commercial_intent_ratio(intent_breakdown: dict) -> float:
    """Return commercial_volume / total_volume as a percentage.

    Guards against division by zero.
    """
    if not intent_breakdown:
        return 0.0
    commercial_vol = intent_breakdown.get("commercial", {}).get("volume", 0)
    total_volume = sum(b.get("volume", 0) for b in intent_breakdown.values())
    if total_volume == 0:
        return 0.0
    return (commercial_vol / total_volume) * 100


# ──────────────────────────────────────────────────────────────────────
# Traffic projection (enhanced with optional SEO data)
# ──────────────────────────────────────────────────────────────────────

def compute_traffic_projection(
    total_volume: int,
    seo_strategy_report=None,
) -> tuple[str, int, int]:
    """Pre-compute traffic projection range from keyword volume.

    When seo_strategy_report is provided, uses difficulty-weighted CTR model
    (Backlinko/Ahrefs) for more realistic projections.
    When not provided, falls back to flat 3-5% CTR (backward compat).

    Returns: (formatted_string, total_low_pageviews, total_high_pageviews)
    """
    if total_volume <= 0:
        return ("Insufficient keyword data for traffic projection -- use qualitative assessment", 0, 0)

    if seo_strategy_report is not None:
        tier_1 = getattr(seo_strategy_report, "tier_1_keywords", None) or []
        tier_2 = getattr(seo_strategy_report, "tier_2_keywords", None) or []

        if tier_1 or tier_2:
            # Compute SEPARATELY for correct 60% T2 scaling
            t1_low, t1_high = compute_difficulty_weighted_traffic(tier_1)
            t2_low, t2_high = compute_difficulty_weighted_traffic(tier_2)

            # Year 1: T1 fully + 60% of T2
            y1_organic_low = t1_low + int(t2_low * 0.6)
            y1_organic_high = t1_high + int(t2_high * 0.6)

            # Year 3: T1 + T2 fully
            y3_organic_low = t1_low + t2_low
            y3_organic_high = t1_high + t2_high

            # Apply +25% direct/referral uplift for pageviews
            y1_total_low = int(y1_organic_low * 1.25)
            y1_total_high = int(y1_organic_high * 1.25)
            y3_total_low = int(y3_organic_low * 1.25)
            y3_total_high = int(y3_organic_high * 1.25)

            projection = (
                f"Pre-computed Traffic Estimate (difficulty-weighted, Backlinko/Ahrefs model):\n"
                f"- Year 1 organic visitors: {y1_organic_low:,}-{y1_organic_high:,}/month "
                f"(Tier 1 fully + 60% Tier 2, position-CTR x ranking probability)\n"
                f"- Year 1 total pageviews: {y1_total_low:,}-{y1_total_high:,}/month "
                f"(with 25% direct/referral uplift)\n"
                f"- Year 3 organic visitors: {y3_organic_low:,}-{y3_organic_high:,}/month "
                f"(Tier 1 + Tier 2 fully ramped)\n"
                f"- Year 3 total pageviews: {y3_total_low:,}-{y3_total_high:,}/month\n"
                f"- NOTE: New sites take 6-12 months to reach Year 1 levels. "
                f"Month 1-3 expect 10-20% of steady state."
            )
            return (projection, y1_total_low, y1_total_high)

    # Fallback: flat 3-5% CTR model (no SEO tier data)
    organic_low = int(total_volume * 0.03)
    organic_high = int(total_volume * 0.05)
    total_low = int(organic_low * 1.2)
    total_high = int(organic_high * 1.3)

    projection = (
        f"Pre-computed Traffic Estimate (Year 1 steady state):\n"
        f"- Organic visitors: {organic_low:,}-{organic_high:,}/month "
        f"(3-5% CTR on {total_volume:,} monthly searches)\n"
        f"- Total pageviews: {total_low:,}-{total_high:,}/month "
        f"(with 20-30% direct/referral)\n"
        f"- NOTE: New sites take 6-12 months to reach these levels. "
        f"Month 1-3 expect 10-20% of steady state."
    )
    return (projection, total_low, total_high)


# ──────────────────────────────────────────────────────────────────────
# CPM and ad revenue (unchanged)
# ──────────────────────────────────────────────────────────────────────

def match_niche_to_cpm(niche_description: str) -> tuple[int, int, str]:
    """Match niche description to CPM range via keyword matching.

    Returns: (cpm_low, cpm_high, vertical_name)
    Always returns a valid result (falls back to "General").
    """
    niche_lower = niche_description.lower()

    categories = [
        (['finance', 'insurance', 'invest', 'banking', 'mortgage', 'fintech', 'trading', 'crypto'], 15, 40, "Finance/Insurance"),
        (['legal', 'lawyer', 'attorney', 'law', 'compliance', 'regulation'], 10, 25, "Legal"),
        (['health', 'medical', 'wellness', 'fitness', 'healthcare', 'clinical', 'patient', 'telemedicine'], 8, 20, "Health"),
        (['tech', 'software', 'saas', 'developer', 'coding', 'devops', 'cloud', 'ai', 'machine learning'], 5, 15, "Technology/SaaS"),
        (['beauty', 'fashion', 'lifestyle', 'skincare', 'cosmetic'], 3, 10, "Lifestyle/Beauty"),
        (['entertainment', 'gaming', 'music', 'movie', 'streaming'], 2, 5, "Entertainment"),
    ]

    for keywords, low, high, vertical in categories:
        if any(re.search(rf'\b{re.escape(w)}\b', niche_lower) for w in keywords):
            return (low, high, vertical)

    return (2, 8, "General")


def compute_ad_revenue_estimate(
    total_low: int, total_high: int, cpm_low: int, cpm_high: int
) -> str:
    """Compute ad revenue range from pageview and CPM ranges.

    Returns formatted string with revenue range.
    """
    if total_low <= 0 or total_high <= 0:
        return "Cannot estimate -- no traffic data"

    rev_low = int(total_low * cpm_low / 1000)
    rev_high = int(total_high * cpm_high / 1000)
    return f"${rev_low:,}-${rev_high:,}/month at steady state"


# ──────────────────────────────────────────────────────────────────────
# Affiliate & total revenue estimates
# ──────────────────────────────────────────────────────────────────────

def compute_affiliate_revenue_estimate(
    intent_breakdown: dict,
    pageview_low: int,
    pageview_high: int,
    niche_description: str,
) -> str:
    """Pre-compute affiliate revenue estimate using intent breakdown + benchmarks.

    Benchmark rates (WordStream 2023): 3-5% affiliate click rate, 2-4% CVR.
    Commission adjusted by niche (SaaS = $100-500, general = $20-50).

    Returns formatted string, or "" when intent data not available.
    """
    if not intent_breakdown or pageview_low <= 0 or pageview_high <= 0:
        return ""

    total_volume = sum(b.get("volume", 0) for b in intent_breakdown.values())
    if total_volume == 0:
        return ""

    commercial_vol = intent_breakdown.get("commercial", {}).get("volume", 0)
    commercial_pct = commercial_vol / total_volume

    commercial_pv_low = int(pageview_low * commercial_pct)
    commercial_pv_high = int(pageview_high * commercial_pct)

    if commercial_pv_low <= 0 and commercial_pv_high <= 0:
        return ""

    # Niche-adjusted commission ranges
    niche_lower = niche_description.lower()
    saas_keywords = ["saas", "software", "developer", "devops", "cloud", "tech", "hosting"]
    finance_keywords = ["finance", "insurance", "invest", "banking", "fintech", "crypto"]

    if any(w in niche_lower for w in saas_keywords):
        commission_low, commission_high = 100, 500
    elif any(w in niche_lower for w in finance_keywords):
        commission_low, commission_high = 50, 200
    else:
        commission_low, commission_high = 20, 50

    # WordStream 2023: 3-5% click rate, 2-4% CVR for commercial intent
    aff_rev_low = int(commercial_pv_low * 0.03 * 0.02 * commission_low)
    aff_rev_high = int(commercial_pv_high * 0.05 * 0.04 * commission_high)

    commercial_pct_display = commercial_pct * 100
    return f"${aff_rev_low:,}-${aff_rev_high:,}/month from affiliate (based on {commercial_pct_display:.0f}% commercial intent traffic)"


def compute_total_revenue_estimate(
    ad_rev_low: int, ad_rev_high: int, aff_rev_low: int, aff_rev_high: int
) -> str:
    """Sum of ad + affiliate revenue ranges.

    Returns formatted string.
    """
    total_low = ad_rev_low + aff_rev_low
    total_high = ad_rev_high + aff_rev_high
    if total_low <= 0 and total_high <= 0:
        return ""
    return f"${total_low:,}-${total_high:,}/month total estimated revenue"


# ──────────────────────────────────────────────────────────────────────
# SEO traffic enrichment (Assert-Constrain-Reference format)
# ──────────────────────────────────────────────────────────────────────

def compute_seo_traffic_enrichment(seo_report) -> str:
    """Extract SEO tier data for traffic estimation enrichment.

    Uses the "Assert-Constrain-Reference" prompt pattern:
    - Zone A: HARD CONSTRAINTS (traffic ceilings)
    - Zone B: PHASED RAMP-UP (tier-by-tier)
    - Zone C: REFERENCE DATA (intent, clusters, geographic)

    Args:
        seo_report: SEOStrategyReport object with tier keywords and geographic/category groups.

    Returns:
        Formatted string with SEO-enriched traffic data for crew context.
    """
    if seo_report is None:
        return ""

    tier_0 = getattr(seo_report, "tier_0_keywords", None) or []
    tier_1 = getattr(seo_report, "tier_1_keywords", None) or []
    tier_2 = getattr(seo_report, "tier_2_keywords", None) or []

    # Compute difficulty-weighted traffic per tier
    t1_low, t1_high = compute_difficulty_weighted_traffic(tier_1)
    t2_low, t2_high = compute_difficulty_weighted_traffic(tier_2)

    # Year 1: T1 fully + 60% T2
    y1_low = t1_low + int(t2_low * 0.6)
    y1_high = t1_high + int(t2_high * 0.6)

    # Year 3: T1 + T2 fully
    y3_low = t1_low + t2_low
    y3_high = t1_high + t2_high

    # Intent analysis
    all_keywords = collect_all_tiered_keywords(seo_report)
    intent = compute_intent_breakdown(all_keywords)
    commercial_pct = compute_commercial_intent_ratio(intent)

    # Tier stats
    t0_count = len(tier_0)
    t0_volume = sum(getattr(kw, "search_volume", 0) or 0 for kw in tier_0)
    t1_count = len(tier_1)
    t1_volume = sum(getattr(kw, "search_volume", 0) or 0 for kw in tier_1)
    t2_count = len(tier_2)
    t2_volume = sum(getattr(kw, "search_volume", 0) or 0 for kw in tier_2)

    # Avg KD per tier
    def _avg_kd(keywords):
        diffs = [getattr(kw, "keyword_difficulty", None) for kw in keywords]
        diffs = [d for d in diffs if d is not None]
        return sum(diffs) / len(diffs) if diffs else 0

    t0_avg_kd = _avg_kd(tier_0)
    t1_avg_kd = _avg_kd(tier_1)
    t2_avg_kd = _avg_kd(tier_2)

    # Zone A: HARD CONSTRAINTS
    lines = [
        "TRAFFIC CONSTRAINTS (pre-computed from keyword difficulty data):",
        f"- Traffic Ceiling Y1: {y1_low:,}-{y1_high:,} organic visits/mo "
        f"(difficulty-weighted, Tier 1 fully + 60% Tier 2)",
        f"  Method: sum(search_volume x position_CTR x ranking_probability) per Backlinko/Ahrefs model",
        f"- Traffic Ceiling Y3: {y3_low:,}-{y3_high:,} organic visits/mo "
        f"(Tier 1 + Tier 2 fully ramped)",
        f"- Commercial Intent Ratio: {commercial_pct:.0f}% of keyword volume is commercial/transactional",
    ]
    if commercial_pct >= 40:
        lines.append("  (>40% = strong affiliate/lead-gen potential)")
    elif commercial_pct < 20:
        lines.append("  (<20% = display-ad-primary)")
    else:
        lines.append("  (20-40% = moderate, hybrid monetization)")

    # Zone B: PHASED RAMP-UP
    lines.append("")
    lines.append("PHASED ORGANIC TRAFFIC RAMP-UP:")
    if t1_count > 0:
        lines.append(
            f"- Month 1-3 (Quick Wins): {t1_count} Tier 1 keywords, "
            f"{t1_volume:,} vol, avg KD {t1_avg_kd:.0f}"
        )
        lines.append(
            f"  Achievable: {t1_low:,}-{t1_high:,} visits/mo "
            f"(expected position 3-5, 80% ranking probability)"
        )
    if t2_count > 0:
        lines.append(
            f"- Month 3-9 (Strategic): {t2_count} Tier 2 keywords, "
            f"{t2_volume:,} vol, avg KD {t2_avg_kd:.0f}"
        )
        lines.append(
            f"  Achievable: {t2_low:,}-{t2_high:,} visits/mo "
            f"(expected position 5-8, 45% ranking probability)"
        )
    if t0_count > 0:
        t0_low, t0_high = compute_difficulty_weighted_traffic(tier_0)
        lines.append(
            f"- Month 6-12+ (Premium): {t0_count} Tier 0 keywords, "
            f"{t0_volume:,} vol, avg KD {t0_avg_kd:.0f}"
        )
        lines.append(
            f"  Achievable: {t0_low:,}-{t0_high:,} visits/mo "
            f"(high competition, 12% ranking probability)"
        )

    # Zone C: REFERENCE DATA
    lines.append("")
    lines.append("REFERENCE DATA:")

    # Intent table
    for bucket_name in ("commercial", "informational", "other"):
        bucket = intent.get(bucket_name, {})
        if bucket.get("count", 0) > 0:
            lines.append(
                f"- {bucket_name.title()} intent: {bucket['count']} keywords, "
                f"{bucket.get('volume', 0):,} vol/mo"
            )

    # Topic clusters
    topic_clusters = getattr(seo_report, "topic_clusters", None) or []
    if topic_clusters:
        top_clusters = sorted(
            topic_clusters,
            key=lambda c: getattr(c, "total_monthly_volume", 0) or 0,
            reverse=True,
        )[:3]
        for tc in top_clusters:
            name = getattr(tc, "cluster_name", "Unknown")
            vol = getattr(tc, "total_monthly_volume", 0) or 0
            prio = getattr(tc, "priority", "")
            lines.append(f"- Topic cluster: {name} ({vol:,} vol/mo, priority: {prio})")

    # Geographic groups
    geo_groups = getattr(seo_report, "tier_3_geographic_groups", None) or []
    if geo_groups:
        for g in geo_groups[:3]:
            g_name = getattr(g, "region_name", None) or getattr(g, "group_name", "Unknown")
            g_vol = sum(getattr(kw, "search_volume", 0) or 0 for kw in (getattr(g, "keywords", None) or []))
            g_comp = getattr(g, "competition_level", "")
            lines.append(f"- Geographic: {g_name} ({g_vol:,} vol/mo, competition: {g_comp})")

    # Content production hint
    page_types = getattr(seo_report, "keyword_based_page_types", None) or []
    if page_types:
        lines.append(f"- Content production: {len(page_types)} page types identified")

    return "\n".join(lines)
