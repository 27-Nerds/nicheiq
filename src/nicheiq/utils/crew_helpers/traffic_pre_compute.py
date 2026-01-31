"""
Traffic Monetization Pre-Computations — deterministic values for TrafficMonetizationCrew.
Used by: TrafficMonetizationCrew.analyze()
"""
from __future__ import annotations
import re


def compute_traffic_projection(total_volume: int) -> tuple[str, int, int]:
    """Pre-compute traffic projection range from keyword volume.

    Returns: (formatted_string, total_low_pageviews, total_high_pageviews)
    """
    if total_volume <= 0:
        return ("Insufficient keyword data for traffic projection -- use qualitative assessment", 0, 0)

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
