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
    3. Apply default values for missing scores

    This eliminates 6+ duplicated score extraction patterns in ReportGenerator.
    """

    def __init__(self, solution_selection: Optional["SolutionSelectionResult"]):
        """
        Initialize with solution selection result.

        Args:
            solution_selection: SolutionSelectionResult from Stage 8.75 (can be None)
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
        default: float = 0.5
    ) -> float:
        """
        Get market fit score with fallback.

        Tries SolutionScores first, then SolutionIdea field, then default.

        Args:
            solution: SolutionIdea object
            default: Default value if score not found (default: 0.5)

        Returns:
            Market fit score (0.0-1.0)
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.market_fit_score is not None:
            return scores.market_fit_score

        # Phase 1.3: Add logging when using fallbacks
        if solution.market_fit_score is not None:
            return solution.market_fit_score

        logger.warning(
            f"[ScoreAccessor] No market_fit_score found for '{solution.solution_name}' "
            f"- using default {default}. This may indicate data quality issues."
        )
        return default

    def get_competitive_advantage(
        self,
        solution: "SolutionIdea",
        default: float = 0.5
    ) -> float:
        """
        Get competitive advantage score with fallback.

        Tries SolutionScores first, then falls back to market_fit as proxy, then default.

        Args:
            solution: SolutionIdea object
            default: Default value if score not found (default: 0.5)

        Returns:
            Competitive advantage score (0.0-1.0)
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.competitive_advantage_score is not None:
            return scores.competitive_advantage_score

        # Phase 1.3: Log fallback to market_fit proxy
        logger.debug(
            f"[ScoreAccessor] No competitive_advantage_score for '{solution.solution_name}' "
            f"- using market_fit as proxy"
        )
        # Fallback: use market_fit as proxy (established pattern in codebase)
        return self.get_market_fit(solution, default)

    def get_technical_feasibility(
        self,
        solution: "SolutionIdea",
        default: float = 0.5
    ) -> float:
        """
        Get technical feasibility score with fallback.

        Tries SolutionScores first, then SolutionIdea field, then default.

        Args:
            solution: SolutionIdea object
            default: Default value if score not found (default: 0.5)

        Returns:
            Technical feasibility score (0.0-1.0)
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.technical_feasibility_score is not None:
            return scores.technical_feasibility_score
        return solution.technical_feasibility_score if solution.technical_feasibility_score is not None else default

    def get_seo_growth(
        self,
        solution: "SolutionIdea",
        default: float = 0.5
    ) -> float:
        """
        Get SEO growth potential score with fallback.

        Tries SolutionScores first, then SolutionIdea.seo_scalability_score, then default.

        Args:
            solution: SolutionIdea object
            default: Default value if score not found (default: 0.5)

        Returns:
            SEO growth potential score (0.0-1.0)
        """
        scores = self.get_scores(solution.solution_name)
        if scores and scores.seo_growth_potential_score is not None:
            return scores.seo_growth_potential_score
        return solution.seo_scalability_score if solution.seo_scalability_score is not None else default

    def get_seo_score_canonical(
        self,
        solution: "SolutionIdea",
        default: float = 0.5
    ) -> float:
        """
        Get canonical SEO score with unified resolution order.

        Single source of truth for SEO score across all report sections.
        Resolution order:
        1. Stage 9.5 refined score (most accurate, data-driven)
        2. Stage 8.5 selection criteria score
        3. Stage 7 baseline score
        4. Default value

        Args:
            solution: SolutionIdea object
            default: Default value if score not found (default: 0.5)

        Returns:
            SEO score (0.0-1.0)
        """
        # 1. Stage 9.5 refined (most accurate, data-driven)
        if solution.seo_scalability_score_refined is not None:
            return solution.seo_scalability_score_refined

        # 2. Stage 8.5 selection criteria
        scores = self.get_scores(solution.solution_name)
        if scores and scores.seo_growth_potential_score is not None:
            return scores.seo_growth_potential_score

        # 3. Stage 7 baseline
        if solution.seo_scalability_score is not None:
            return solution.seo_scalability_score

        return default

    def get_confidence_score(
        self,
        solution: "SolutionIdea",
        pain_point_quality_tier: Optional[str] = None,
        social_content_quality_tier: Optional[str] = None,
        pain_point_confidence_score: Optional[float] = None,
    ) -> float:
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
            Confidence score (0.0-1.0)
        """
        market_fit = self.get_market_fit(solution)
        competitive_advantage = self.get_competitive_advantage(solution)
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

    def get_all_scores(self, solution: "SolutionIdea") -> dict[str, float]:
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
            "seo_growth": self.get_seo_growth(solution),
        }
