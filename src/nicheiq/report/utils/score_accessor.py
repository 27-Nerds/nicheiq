"""Score extraction utilities for report generation."""

from typing import TYPE_CHECKING, Optional

from loguru import logger

from ...validators.score_validators import ConfidenceAdjuster

if TYPE_CHECKING:
    from ...models.solution_idea import SolutionIdea
    from ...models.solution_selection import SolutionScores, SolutionSelectionResult


class ScoreAccessor:
    """
    Utility for extracting solution scores with fallback logic.

    Centralizes the pattern of:
    1. Try to get scores from SolutionSelection.all_solution_scores
    2. Fallback to SolutionIdea fields if not found
    3. Return None for missing scores (no silent defaults)

    This eliminates 6+ duplicated score extraction patterns in ReportGenerator.
    """

    def __init__(self, solution_selection: Optional["SolutionSelectionResult"]):
        """
        Initialize with solution selection result.

        Args:
            solution_selection: SolutionSelectionResult from Stage 5 (can be None)
        """
        self.solution_selection = solution_selection

    def get_scores(self, solution_name: str) -> Optional["SolutionScores"]:
        """
        Get scores from all_solution_scores by solution name.

        Args:
            solution_name: Name of solution to look up

        Returns:
            SolutionScores if found, None otherwise
        """
        if not self.solution_selection or not self.solution_selection.all_solution_scores:
            return None

        for scores in self.solution_selection.all_solution_scores:
            if scores.solution_name == solution_name:
                return scores

        logger.debug(f"No scores found for '{solution_name}' in all_solution_scores")
        return None

    def get_market_fit(
        self,
        solution: "SolutionIdea",
    ) -> float | None:
        """
        Get market fit score with fallback.

        Resolution: all_solution_scores → solution.market_fit_score → None

        Args:
            solution: SolutionIdea object

        Returns:
            Market fit score (0.0-1.0), or None if unavailable
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.market_fit_score is not None:
            return scores.market_fit_score

        if solution.market_fit_score is not None:
            return solution.market_fit_score

        logger.warning(
            f"[ScoreAccessor] No market_fit_score found for '{solution.solution_name}' "
            f"- returning None. This may indicate data quality issues."
        )
        return None

    def get_competitive_advantage(
        self,
        solution: "SolutionIdea",
    ) -> float | None:
        """
        Get competitive advantage score.

        Resolution: all_solution_scores → solution.novelty_score → None

        The old market_fit proxy fallback is gone: it double-counted market_fit
        in the verdict average and defeated the None-score guard. novelty_score
        is the same semantic mapping the backfill uses; when neither exists the
        honest answer is None (the verdict path then averages the present scores
        and adds a caveat).

        Args:
            solution: SolutionIdea object

        Returns:
            Competitive advantage score (0.0-1.0), or None if unavailable
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.competitive_advantage_score is not None:
            return scores.competitive_advantage_score

        novelty = getattr(solution, 'novelty_score', None)
        if novelty is not None:
            logger.debug(
                f"[ScoreAccessor] No competitive_advantage_score for '{solution.solution_name}' "
                f"- using novelty_score (same mapping as backfill)"
            )
            return novelty

        logger.warning(
            f"[ScoreAccessor] No competitive_advantage_score or novelty_score for "
            f"'{solution.solution_name}' - returning None (no proxy fabrication)"
        )
        return None

    def get_technical_feasibility(
        self,
        solution: "SolutionIdea",
    ) -> float | None:
        """
        Get technical feasibility score with fallback.

        Resolution: all_solution_scores → solution.technical_feasibility_score → None

        Args:
            solution: SolutionIdea object

        Returns:
            Technical feasibility score (0.0-1.0), or None if unavailable
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.technical_feasibility_score is not None:
            return scores.technical_feasibility_score
        return solution.technical_feasibility_score if solution.technical_feasibility_score is not None else None

    def get_seo_growth(
        self,
        solution: "SolutionIdea",
    ) -> float | None:
        """
        Get SEO growth potential score with fallback.

        Resolution: all_solution_scores → solution.seo_scalability_score → None

        Args:
            solution: SolutionIdea object

        Returns:
            SEO growth potential score (0.0-1.0), or None if unavailable
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.seo_growth_potential_score is not None:
            return scores.seo_growth_potential_score
        return solution.seo_scalability_score if solution.seo_scalability_score is not None else None

    def get_seo_score_canonical(
        self,
        solution: "SolutionIdea",
    ) -> float | None:
        """
        Get canonical SEO score with unified resolution order.

        Single source of truth for SEO score across all report sections.
        Resolution order:
        1. Stage 12 refined score (most accurate, data-driven)
        2. Stage 5 all_solution_scores
        3. Stage 7 baseline score
        4. None

        Args:
            solution: SolutionIdea object

        Returns:
            SEO score (0.0-1.0), or None if unavailable
        """
        # 1. Stage 12 refined (most accurate, data-driven)
        seo_refined = getattr(solution, 'seo_scalability_score_refined', None)
        if seo_refined is not None:
            return seo_refined

        # 2. Stage 5 all_solution_scores
        scores = self.get_scores(solution.solution_name)
        if scores and scores.seo_growth_potential_score is not None:
            return scores.seo_growth_potential_score

        # 3. Stage 7 baseline
        if solution.seo_scalability_score is not None:
            return solution.seo_scalability_score

        return None

    def get_confidence_score(
        self,
        solution: "SolutionIdea",
        pain_point_quality_tier: Optional[str] = None,
        social_content_quality_tier: Optional[str] = None,
        pain_point_confidence_score: Optional[float] = None,
    ) -> float | None:
        """
        Get selection confidence score, optionally adjusted for data quality.

        Base score = average of market_fit and competitive_advantage.
        When quality parameters are provided, multiplicative penalties are
        applied via ConfidenceAdjuster (downgrade-only, floor at 0.10).

        Args:
            solution: SolutionIdea object
            pain_point_quality_tier: GOLD/SILVER/BRONZE/INSUFFICIENT (or None)
            social_content_quality_tier: EXCELLENT/GOOD/MINIMAL/INSUFFICIENT (or None)
            pain_point_confidence_score: Pipeline PP confidence 0.0-1.0 (or None)

        Returns:
            Confidence score (0.0-1.0), or None if underlying scores unavailable
        """
        market_fit = self.get_market_fit(solution)
        competitive_advantage = self.get_competitive_advantage(solution)
        if market_fit is None or competitive_advantage is None:
            return None
        base_score = (market_fit + competitive_advantage) / 2

        # When no quality params supplied, return base score (backward compatible)
        if (
            pain_point_quality_tier is None
            and social_content_quality_tier is None
            and pain_point_confidence_score is None
        ):
            return base_score

        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            base_score=base_score,
            pain_point_quality_tier=pain_point_quality_tier,
            social_content_quality_tier=social_content_quality_tier,
            pain_point_confidence_score=pain_point_confidence_score,
        )

        if result.adjustment_notes:
            logger.debug(
                f"[ScoreAccessor] Confidence adjusted for '{solution.solution_name}': "
                f"{result.base_score:.3f} → {result.adjusted_score:.3f} "
                f"(multiplier={result.quality_multiplier:.3f}, "
                f"notes={result.adjustment_notes})"
            )

        return result.adjusted_score

    def get_solo_dev_feasibility(
        self,
        solution: "SolutionIdea",
    ) -> float | None:
        """
        Get solo developer feasibility score.

        Resolution: solution.solo_dev_feasibility → None

        Args:
            solution: SolutionIdea object

        Returns:
            Solo dev feasibility score (0.0-1.0), or None if unavailable
        """
        val = getattr(solution, 'solo_dev_feasibility', None)
        if isinstance(val, (int, float)):
            return float(val)
        return None

    def get_all_scores(self, solution: "SolutionIdea") -> dict[str, float | None]:
        """
        Get all scores as dict (convenience method).

        Args:
            solution: SolutionIdea object

        Returns:
            Dict with keys: market_fit, competitive_advantage, technical_feasibility, seo_growth
        """
        return {
            "market_fit": self.get_market_fit(solution),
            "competitive_advantage": self.get_competitive_advantage(solution),
            "technical_feasibility": self.get_technical_feasibility(solution),
            "seo_growth": self.get_seo_score_canonical(solution),
        }
