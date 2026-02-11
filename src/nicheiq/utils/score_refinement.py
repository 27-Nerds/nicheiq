"""
Score refinement utilities for Stage 12 SEO refinement.

Refines solution scores based on keyword data from SEO analysis.
"""

import re
from typing import Any

from ..config.settings import settings


def refine_scalability_score(
    base_score: float,
    project_type: str | None,
    total_volume: int,
    tier1_count: int,
    tier1_keywords: list[Any]
) -> dict[str, Any]:
    """
    Refine SEO scalability score based on keyword data.

    Args:
        base_score: Original seo_scalability_score from Stage 7
        project_type: Project type (directory, aggregator, saas, etc.)
        total_volume: Total monthly search volume
        tier1_count: Number of Tier 1 (quick win) keywords
        tier1_keywords: List of TieredKeyword objects for Tier 1

    Returns:
        dict with 'score' (float) and 'metadata' (dict)
    """
    # Determine baseline volume by project type
    baselines = settings.seo_refinement_volume_baselines
    baseline_volume = baselines.get(project_type, 30_000)

    # Calculate volume multiplier (20% range, capped)
    volume_ratio = total_volume / baseline_volume if baseline_volume > 0 else 1.0
    volume_multiplier = min(settings.seo_refinement_max_volume_boost, max(0.8, volume_ratio))

    # Calculate Tier 1 multiplier (1% per keyword, max 20%)
    tier1_boost = min(settings.seo_refinement_max_tier1_boost, tier1_count * 0.01)
    tier1_multiplier = 1.0 + tier1_boost

    # Calculate competition modifier from Tier 1 keywords
    if tier1_keywords:
        competition_scores = []
        for kw in tier1_keywords:
            # Parse competition string like "LOW (30)" or "MEDIUM (53)"
            comp_str = kw.competition
            if '(' in comp_str:
                try:
                    comp_value = int(comp_str.split('(')[1].replace(')', ''))
                    competition_scores.append(comp_value / 100.0)  # Normalize to 0-1
                except (ValueError, IndexError):
                    pass

        avg_competition = sum(competition_scores) / len(competition_scores) if competition_scores else 0.5
        competition_modifier = 1.0 - avg_competition  # Lower competition = higher score
    else:
        competition_modifier = 0.5  # Neutral if no data

    # Calculate refined score
    refined_score = base_score * volume_multiplier * tier1_multiplier * competition_modifier
    refined_score = min(1.0, refined_score)  # Cap at 1.0

    metadata = {
        'baseline_volume': baseline_volume,
        'volume_multiplier': round(volume_multiplier, 3),
        'tier1_multiplier': round(tier1_multiplier, 3),
        'competition_modifier': round(competition_modifier, 3),
        'change': round(refined_score - base_score, 3)
    }

    return {
        'score': round(refined_score, 2),
        'metadata': metadata
    }

def refine_cac_organic(
    base_cac_str: str | None,
    tier1_keywords: list[Any],
    total_volume: int
) -> dict[str, Any]:
    """
    Refine organic CAC estimate based on keyword difficulty and volume.

    Args:
        base_cac_str: Original CAC string like "$15-30 per customer"
        tier1_keywords: List of TieredKeyword objects for Tier 1
        total_volume: Total monthly search volume

    Returns:
        dict with 'cac_range' (str) and 'metadata' (dict)
    """
    if not base_cac_str:
        return {'cac_range': 'N/A', 'metadata': {'estimated_year1_pages': 0}}

    # Parse base CAC (extract midpoint)
    matches = re.findall(r'\$?(\d+)', base_cac_str)
    if len(matches) >= 2:
        base_cac = (int(matches[0]) + int(matches[1])) / 2
    elif len(matches) == 1:
        base_cac = int(matches[0])
    else:
        base_cac = 100  # Fallback

    # Calculate average Tier 1 difficulty
    if tier1_keywords:
        competition_scores = []
        for kw in tier1_keywords:
            comp_str = kw.competition
            if '(' in comp_str:
                try:
                    comp_value = int(comp_str.split('(')[1].replace(')', ''))
                    competition_scores.append(comp_value)
                except (ValueError, IndexError):
                    pass

        avg_difficulty = sum(competition_scores) / len(competition_scores) if competition_scores else 50
    else:
        avg_difficulty = 50  # Neutral

    difficulty_multiplier = 1.0 + (avg_difficulty / 100)

    # Calculate volume discount (economies of scale)
    volume_discount = max(
        settings.seo_refinement_volume_discount_floor,
        1.0 - (total_volume / 1_000_000)
    )

    # Calculate refined CAC
    refined_cac = base_cac * difficulty_multiplier * volume_discount

    # Create range (±20%)
    cac_low = int(refined_cac * 0.8 / 5) * 5  # Round to nearest $5
    cac_high = int(refined_cac * 1.2 / 5) * 5

    metadata = {
        'base_cac': base_cac,
        'difficulty_multiplier': round(difficulty_multiplier, 3),
        'volume_discount': round(volume_discount, 3),
        'avg_tier1_difficulty': round(avg_difficulty, 1),
        'estimated_year1_pages': 0  # Will be updated by refine_programmatic_opportunity
    }

    return {
        'cac_range': f"${cac_low}-{cac_high}",
        'metadata': metadata
    }

def refine_programmatic_opportunity(
    original_assessment: str | None,
    seo_report: Any,
    tier1_count: int
) -> dict[str, Any]:
    """
    Refine programmatic SEO opportunity with quantitative page count estimates.

    Args:
        original_assessment: Original qualitative assessment from Stage 7
        seo_report: SEOStrategyReport from Stage 9
        tier1_count: Number of Tier 1 keywords

    Returns:
        dict with 'assessment' (str) and 'page_count' (int)
    """
    # Calculate estimated page count
    page_count = 0

    # Tier 1 landing pages
    page_count += tier1_count

    # Geographic/category pages (Tier 3/4)
    if hasattr(seo_report, 'tier_3_geographic_groups') and seo_report.tier_3_geographic_groups:
        page_count += len(seo_report.tier_3_geographic_groups)

    if hasattr(seo_report, 'tier_4_category_groups') and seo_report.tier_4_category_groups:
        page_count += len(seo_report.tier_4_category_groups)

    # Topic cluster pages (pillar + supporting)
    if hasattr(seo_report, 'topic_clusters') and seo_report.topic_clusters:
        posts_per_cluster = 4  # Average pillar + 3 supporting posts
        page_count += len(seo_report.topic_clusters) * posts_per_cluster

    # Keyword-based page types
    if hasattr(seo_report, 'keyword_based_page_types') and seo_report.keyword_based_page_types:
        for page_type in seo_report.keyword_based_page_types:
            if hasattr(page_type, 'estimated_page_count'):
                page_count += page_type.estimated_page_count

    # Build refined assessment
    refined = f"""**Refined Assessment (Based on Keyword Research):**

This solution can generate approximately **{page_count} indexable pages** in Year 1, comprising:

- **{tier1_count} Tier 1 landing pages** targeting quick-win keywords
"""

    if hasattr(seo_report, 'tier_3_geographic_groups') and seo_report.tier_3_geographic_groups:
        geo_count = len(seo_report.tier_3_geographic_groups)
        refined += f"- **{geo_count} geographic pages** for regional targeting\n"

    if hasattr(seo_report, 'tier_4_category_groups') and seo_report.tier_4_category_groups:
        cat_count = len(seo_report.tier_4_category_groups)
        refined += f"- **{cat_count} category pages** for vertical segmentation\n"

    if hasattr(seo_report, 'topic_clusters') and seo_report.topic_clusters:
        cluster_count = len(seo_report.topic_clusters)
        cluster_pages = cluster_count * 4
        refined += f"- **{cluster_pages} content pieces** across {cluster_count} topic clusters\n"

    refined += f"\n**Total Estimated Year 1 SEO Footprint:** {page_count} pages\n\n"
    refined += f"**Original Architectural Analysis:**\n{original_assessment or 'N/A'}"

    return {
        'assessment': refined,
        'page_count': page_count
    }
