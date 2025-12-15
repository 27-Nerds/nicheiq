"""
Keyword filtering and relevance validation utilities.

Used for Stage 8.8 keyword quality checks.
"""

import re
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..config.settings import settings

if TYPE_CHECKING:
    from ..models.research_state import NicheContext
    from ..models.solution_idea import SolutionIdea

def filter_single_word_keywords(
    keywords: list[dict[str, Any]],
    label: str
) -> list[dict[str, Any]]:
    """
    Filter out single-word keywords from enriched keyword list.

    Single-word keywords can be used as seeds for DataForSEO expansion,
    but should be removed from final analysis to avoid over-generic results.

    Args:
        keywords: List of keyword dictionaries with 'keyword' field
        label: Label for logging (e.g., "Solution XYZ")

    Returns:
        Filtered list with only multi-word keywords
    """
    if not keywords:
        return keywords

    original_count = len(keywords)

    # Filter: keep only keywords with 2+ words (split by whitespace, hyphens, slashes)
    # This handles: "co-working" (2 words), "B2B/B2C" (2 words), "keyword phrase" (2 words)
    filtered = [
        kw for kw in keywords
        if len(re.split(r'[\s\-/]+', kw.get('keyword', '').strip())) >= 2
    ]

    filtered_count = len(filtered)
    removed_count = original_count - filtered_count

    if removed_count > 0:
        # Log some examples of removed single-word keywords
        removed_keywords = [
            kw.get('keyword', '') for kw in keywords
            if len(re.split(r'[\s\-/]+', kw.get('keyword', '').strip())) < 2
        ]
        examples = removed_keywords[:5]  # Show first 5
        examples_str = ", ".join(f"'{kw}'" for kw in examples)

        logger.info(
            f"[Stage 8.8] {label}: Filtered {removed_count} single-word keywords "
            f"(kept {filtered_count} multi-word). Examples removed: {examples_str}"
        )
    else:
        logger.debug(f"[Stage 8.8] {label}: No single-word keywords to filter")

    return filtered

def check_keyword_relevance(
    expanded_keywords: list[dict],
    solution: "SolutionIdea",
    niche_context: "NicheContext | None" = None,
    validation_cache: dict[str, tuple | None] = None,
    audience_vocabulary: list[str] | None = None
) -> tuple[float, list[dict], list[str]]:
    """
    Check if expanded keywords are relevant using 4 criteria.

    Evaluates keyword quality based on:
    1. Search volume distribution (reject if >80% have volume < 10/month)
    2. DataForSEO validation success rate
    3. Semantic relevance using KeywordRelevanceValidator
    4. Audience vocabulary alignment (checks if keywords contain terms from Stage 6.5)

    Args:
        expanded_keywords: List of keyword dicts from DataForSEO expansion
        solution: SolutionIdea object for semantic comparison
        niche_context: Optional NicheContext for semantic validation
        validation_cache: Optional cache dict for validation results
        audience_vocabulary: Optional list of audience terms from Stage 6.5

    Returns:
        Tuple of (relevance_score, good_keywords, issues):
        - relevance_score: 0.0-1.0 overall quality score
        - good_keywords: List of relevant keyword dicts
        - issues: List of problem descriptions
    """
    if not expanded_keywords:
        return (0.0, [], ["no_keywords_generated"])

    issues = []
    total_keywords = len(expanded_keywords)

    # Criterion 1: Search volume distribution
    low_volume_threshold = getattr(settings, 'keyword_min_volume_threshold', 10)
    low_volume_keywords = [
        kw for kw in expanded_keywords
        if (kw.get('search_volume') or 0) < low_volume_threshold
    ]
    low_volume_ratio = len(low_volume_keywords) / total_keywords if total_keywords > 0 else 1.0

    if low_volume_ratio > 0.8:
        issues.append(f"low_search_volume_ratio_{low_volume_ratio:.2f}")
        logger.debug(
            f"[Relevance Check] {len(low_volume_keywords)}/{total_keywords} "
            f"keywords have volume < {low_volume_threshold}"
        )

    # Criterion 2: DataForSEO validation success rate
    valid_keywords = [
        kw for kw in expanded_keywords
        if kw.get('search_volume') is not None and kw.get('search_volume', 0) >= 0
    ]
    validation_rate = len(valid_keywords) / total_keywords if total_keywords > 0 else 0.0

    if validation_rate < 0.5:
        issues.append(f"dataforseo_validation_failed_{validation_rate:.2f}")
        logger.debug(
            f"[Relevance Check] Only {len(valid_keywords)}/{total_keywords} "
            f"keywords validated by DataForSEO"
        )

    # Criterion 3: Semantic relevance using KeywordRelevanceValidator
    try:
        from .validation import KeywordRelevanceValidator

        validator = KeywordRelevanceValidator()
        relevance_threshold = getattr(settings, 'keyword_relevance_threshold', 0.5)

        # Prepare validation context
        project_type = solution.project_type or "saas"

        # Validate batch (limit to top 50 keywords by volume for cost efficiency)
        keywords_to_validate = sorted(
            expanded_keywords,
            key=lambda x: x.get('search_volume') or 0,
            reverse=True
        )[:50]

        validated_results = validator.validate_batch(
            keywords=keywords_to_validate,
            solution_name=solution.solution_name,
            solution_description=solution.description,
            niche_description=niche_context.niche_description if niche_context else "",
            project_type=project_type,
            threshold=relevance_threshold,
            validation_cache=validation_cache
        )

        # Extract relevant keywords
        semantically_relevant = [
            kw for kw, is_relevant, score in validated_results
            if is_relevant
        ]

        semantic_relevance_rate = (
            len(semantically_relevant) / len(keywords_to_validate)
            if keywords_to_validate else 0.0
        )

        if semantic_relevance_rate < 0.4:
            issues.append(f"semantic_mismatch_{semantic_relevance_rate:.2f}")
            logger.debug(
                f"[Relevance Check] Only {len(semantically_relevant)}/{len(keywords_to_validate)} "
                f"keywords are semantically relevant (threshold: {relevance_threshold})"
            )

        # Identify good keywords: valid volume + semantically relevant
        # Use set for O(1) lookup instead of O(n) any() check
        relevant_keywords_set = {sk.get('keyword', '').lower() for sk in semantically_relevant}
        good_keywords = [
            kw for kw in expanded_keywords
            if (
                (kw.get('search_volume') or 0) >= low_volume_threshold and
                kw.get('keyword', '').lower() in relevant_keywords_set
            )
        ]

    except (ValueError, KeyError, AttributeError) as e:
        logger.warning(f"[Relevance Check] Semantic validation failed: {e}")
        # Fallback: use volume-based filtering only
        good_keywords = [
            kw for kw in expanded_keywords
            if (kw.get('search_volume') or 0) >= low_volume_threshold
        ]
        semantic_relevance_rate = 0.5  # Neutral score on error
        issues.append("semantic_validation_error")

    # Criterion 4: Audience vocabulary alignment (15% weight)
    # Checks if keywords contain terms from actual audience discussions (Stage 6.5)
    if audience_vocabulary and expanded_keywords:
        audience_vocab_lower = {term.lower() for term in audience_vocabulary}
        audience_match_count = sum(
            1 for kw in expanded_keywords
            if any(term in kw.get('keyword', '').lower() for term in audience_vocab_lower)
        )
        audience_score = audience_match_count / len(expanded_keywords)

        if audience_score < 0.2:
            issues.append(f"low_audience_alignment_{audience_score:.2f}")
            logger.debug(
                f"[Relevance Check] Only {audience_match_count}/{len(expanded_keywords)} "
                f"keywords contain audience vocabulary terms"
            )
    else:
        audience_score = 0.5  # Neutral score if no audience data available

    # Calculate overall relevance score (weighted average)
    # 35% volume + 25% validation + 25% semantic + 15% audience
    volume_score = max(0.0, 1.0 - low_volume_ratio)
    validation_score = validation_rate
    semantic_score = semantic_relevance_rate

    relevance_score = (
        0.35 * volume_score +
        0.25 * validation_score +
        0.25 * semantic_score +
        0.15 * audience_score
    )

    logger.info(
        f"[Relevance Check] Overall score: {relevance_score:.2f} "
        f"(volume:{volume_score:.2f}, validation:{validation_score:.2f}, "
        f"semantic:{semantic_score:.2f}, audience:{audience_score:.2f})"
    )
    logger.info(
        f"[Relevance Check] Good keywords: {len(good_keywords)}/{total_keywords}, "
        f"Issues: {', '.join(issues) if issues else 'none'}"
    )

    return (relevance_score, good_keywords, issues)
