"""Score extraction utilities for report generation."""

from typing import TYPE_CHECKING, Optional

from loguru import logger

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
        return solution.market_fit_score if solution.market_fit_score is not None else default

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
