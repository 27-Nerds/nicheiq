"""Three-band idea-intent volume accounting (Q-049 batch-1).

Folds the per-keyword ``idea_intent_grade`` stamps (written by
``_augment_idea_intent_keywords`` / the 6c-resume re-grade) into the three
SEOStrategyReport honesty fields:

- ``offtopic_volume_share``     — grade 0 (OFFTOPIC)
- ``category_volume_share``     — grade 1 + UNGRADED rows (ungraded keywords are RETAINED
                                  fail-open and counted as category reach, per the
                                  keyword_intent_validator caller contract)
- ``idea_intent_monthly_volume``— grade >= settings.keyword_relevance_min_grade

The bands are computed ONLY when graded coverage >= MIN_GRADED_COVERAGE (80%) of the
keyword set; below that every field is None (``[SEO-RELEVANCE] guard degraded`` log) and
consumers keep exactly today's behavior. ``total_monthly_volume`` is never touched.
"""

from __future__ import annotations

from loguru import logger

from ..config.settings import settings

# Band fields require the grader to have covered at least this fraction of the keyword set.
MIN_GRADED_COVERAGE = 0.8

_EMPTY_BANDS: dict = {
    "offtopic_volume_share": None,
    "category_volume_share": None,
    "idea_intent_monthly_volume": None,
}


def keyword_grade(kw) -> int | None:
    """The stamped idea_intent_grade of a keyword row (dict or object); None when absent."""
    if isinstance(kw, dict):
        g = kw.get("idea_intent_grade")
    else:
        g = getattr(kw, "idea_intent_grade", None)
    return g if isinstance(g, int) and not isinstance(g, bool) else None


def _volume(kw) -> int:
    if isinstance(kw, dict):
        return kw.get("search_volume", 0) or 0
    return getattr(kw, "search_volume", 0) or 0


def graded_coverage(keywords: list) -> float:
    """Fraction of keyword rows carrying an idea_intent_grade stamp (0.0 on empty input)."""
    if not keywords:
        return 0.0
    return sum(1 for k in keywords if keyword_grade(k) is not None) / len(keywords)


def compute_intent_volume_bands(keywords: list, min_grade: int | None = None) -> dict:
    """Compute the three band fields from stamped keyword rows.

    Returns a dict with keys matching the SEOStrategyReport fields. All values are None
    (today's behavior) when the coverage guard fails or there is no volume to split.
    """
    if not keywords:
        return dict(_EMPTY_BANDS)
    coverage = graded_coverage(keywords)
    if coverage < MIN_GRADED_COVERAGE:
        logger.info(
            f"[SEO-RELEVANCE] guard degraded (graded coverage {coverage:.0%} < "
            f"{MIN_GRADED_COVERAGE:.0%}) — idea-intent volume bands withheld"
        )
        return dict(_EMPTY_BANDS)
    if min_grade is None:
        min_grade = settings.keyword_relevance_min_grade
    total = sum(_volume(k) for k in keywords)
    if total <= 0:
        return dict(_EMPTY_BANDS)
    offtopic = sum(_volume(k) for k in keywords if keyword_grade(k) == 0)
    category = sum(_volume(k) for k in keywords if keyword_grade(k) == 1 or keyword_grade(k) is None)
    idea_intent = sum(
        _volume(k) for k in keywords
        if keyword_grade(k) is not None and keyword_grade(k) >= min_grade
    )
    return {
        "offtopic_volume_share": round(offtopic / total, 4),
        "category_volume_share": round(category / total, 4),
        "idea_intent_monthly_volume": idea_intent,
    }
