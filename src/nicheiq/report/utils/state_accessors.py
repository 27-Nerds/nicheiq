"""
State accessor layer for defensive data extraction from ResearchState.

This module provides a centralized, defensive layer for accessing data from
the research state. It handles null checking, provides sensible defaults,
and reduces direct state access scattered throughout ReportGenerator.

Design Benefits:
- Centralized null checking (DRY principle)
- Clear API for what data is available from state
- Easy to modify data extraction logic in one place
- Testable in isolation from ReportGenerator
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...models.competitor import CompetitiveAnalysisResult
    from ...models.data_source import DataSourceResearchResult
    from ...models.keyword_data import KeywordValidationResult
    from ...models.pain_point import PainPointAnalysisResult
    from ...models.research_state import ResearchState
    from ...models.seo_strategy import SEOStrategyReport
    from ...models.solution_idea import IdeaGenerationResult, SolutionIdea
    from ...models.solution_refinement import SolutionRefinementResult
    from ...models.solution_selection import SolutionSelectionResult
    from ...models.social_content import SocialContentResult


class StateAccessor:
    """
    Defensive accessor layer for ResearchState data.

    Provides high-level methods to extract commonly needed data with
    built-in null checking and default values.
    """

    def __init__(self, state: "ResearchState"):
        """
        Initialize state accessor.

        Args:
            state: Complete research state from all pipeline stages
        """
        self.state = state

    # ==================================================================================
    # Stage Data Access Methods
    # ==================================================================================

    def get_pain_point_analysis(self) -> Optional["PainPointAnalysisResult"]:
        """Get Stage 6 pain point analysis result."""
        return self.state.pain_point_analysis

    def get_idea_generation(self) -> Optional["IdeaGenerationResult"]:
        """Get Stage 7 solution idea generation result."""
        return self.state.idea_generation

    def get_competitive_analysis(self) -> Optional["CompetitiveAnalysisResult"]:
        """Get Stage 8 competitive analysis result."""
        return self.state.competitive_analysis

    def get_solution_selection(self) -> Optional["SolutionSelectionResult"]:
        """Get Stage 8.5 solution selection result."""
        return self.state.solution_selection

    def get_solution_refinement(self) -> Optional["SolutionRefinementResult"]:
        """Get Stage 8.85 solution refinement result."""
        return self.state.solution_refinement

    def get_seo_strategy(self) -> Optional["SEOStrategyReport"]:
        """Get Stage 9 SEO strategy report."""
        return self.state.seo_strategy_report

    def get_data_source_research(self) -> Optional["DataSourceResearchResult"]:
        """Get Stage 9.75 data source research result (conditional)."""
        return self.state.data_source_research

    def get_social_content(self) -> Optional["SocialContentResult"]:
        """Get Stage 5 social media content result."""
        return self.state.social_content

    # ==================================================================================
    # Derived Data Access Methods
    # ==================================================================================

    def get_sorted_pain_points(self) -> list:
        """
        Get all pain points sorted by priority (severity + WTP).

        Returns:
            List of PainPoint objects sorted by priority, or empty list
        """
        if not self.state.pain_point_analysis:
            return []

        return sorted(
            self.state.pain_point_analysis.pain_points,
            key=lambda x: (x.severity_score + x.willingness_to_pay) / 2,
            reverse=True,
        )

    def get_formatted_pain_points(self) -> list[str]:
        """
        Get formatted pain point strings with scores.

        Returns:
            List of formatted strings like "Title - Description (Severity: 8.5/10, WTP: 7.2/10)"
        """
        sorted_pps = self.get_sorted_pain_points()
        return [
            f"{pp.title} - {pp.description} (Severity: {pp.severity_score:.1f}/10, WTP: {pp.willingness_to_pay:.1f}/10)"
            for pp in sorted_pps
        ]

    def get_pain_points_summary(self) -> str:
        """
        Get pain points analysis summary.

        Returns:
            Summary text or default message if unavailable
        """
        if self.state.pain_point_analysis:
            return self.state.pain_point_analysis.analysis_summary
        return "No pain point analysis available."

    def get_all_solution_names(self, selected_first: bool = True) -> list[str]:
        """
        Get list of all solution names.

        Args:
            selected_first: If True, put selected solution at front of list

        Returns:
            List of solution names, or empty list if unavailable
        """
        if not self.state.idea_generation:
            return []

        all_solutions = [sol.solution_name for sol in self.state.idea_generation.solution_ideas]

        if selected_first and self.state.solution_selection:
            selected_name = self.state.solution_selection.selected_solution_name
            if selected_name in all_solutions:
                all_solutions.remove(selected_name)
                all_solutions.insert(0, selected_name)

        return all_solutions

    def get_solutions_summary(self) -> str:
        """
        Get solution ideas summary.

        Returns:
            Summary text or default message if unavailable
        """
        if self.state.idea_generation:
            return self.state.idea_generation.market_insights
        return "No solution ideas generated."

    def get_competitive_summary(self) -> str:
        """
        Get competitive analysis summary.

        Returns:
            Summary text or default message if unavailable
        """
        if self.state.competitive_analysis:
            return self.state.competitive_analysis.strategic_recommendations
        return "No competitive analysis available."

    def get_selected_solution_name(self) -> str:
        """
        Get selected solution name.

        Returns:
            Solution name or default message if not selected
        """
        if self.state.solution_selection:
            return self.state.solution_selection.selected_solution_name
        return "No solution selected"

    def get_selection_rationale(self) -> str:
        """
        Get solution selection rationale.

        Returns:
            Rationale text or default message if not available
        """
        if self.state.solution_selection:
            return self.state.solution_selection.selection_rationale
        return "Solution selection was not completed. Review recommended solutions and perform manual selection."

    def get_runner_up_solutions(self) -> list[str]:
        """
        Get runner-up solution names.

        Returns:
            List of runner-up names or empty list
        """
        if self.state.solution_selection:
            return self.state.solution_selection.runner_up_solutions
        return []

    def get_selection_criteria_scores(self) -> list:
        """
        Get selection criteria scores.

        Returns:
            List of selection criteria objects or empty list
        """
        if self.state.solution_selection:
            return self.state.solution_selection.selection_criteria_scores
        return []

    def get_recommended_focus(self) -> str:
        """
        Get recommended focus area.

        Returns:
            Focus recommendation or default message
        """
        if self.state.solution_selection:
            return self.state.solution_selection.recommended_focus
        return "To be determined after solution selection"

    def get_selected_solution_details(self) -> Optional["SolutionIdea"]:
        """
        Get complete SolutionIdea object for selected solution.

        Uses fuzzy matching to find the solution by name.

        Returns:
            SolutionIdea object or None if not found
        """
        from ...utils.helpers import find_solution_by_name

        if not self.state.solution_selection or not self.state.idea_generation:
            return None

        return find_solution_by_name(
            self.state.solution_selection.selected_solution_name,
            self.state.idea_generation.solution_ideas
        )

    # ==================================================================================
    # Social Content Access Methods
    # ==================================================================================

    def get_reddit_posts_count(self) -> int:
        """Get count of Reddit posts collected."""
        if self.state.social_content and self.state.social_content.reddit_threads:
            return len(self.state.social_content.reddit_threads)
        return 0

    def get_twitter_threads_count(self) -> int:
        """Get count of Twitter threads collected."""
        if self.state.social_content and self.state.social_content.twitter_threads:
            return len(self.state.social_content.twitter_threads)
        return 0

    def get_subreddit_breakdown(self) -> dict[str, int]:
        """
        Get breakdown of Reddit posts by subreddit.

        Returns:
            Dict mapping subreddit name to post count
        """
        breakdown = {}
        if self.state.social_content and self.state.social_content.reddit_threads:
            for thread in self.state.social_content.reddit_threads:
                subreddit = thread.subreddit
                breakdown[subreddit] = breakdown.get(subreddit, 0) + 1
        return breakdown

    # ==================================================================================
    # Keyword & SEO Access Methods
    # ==================================================================================

    def get_keyword_validation_results(self) -> list["KeywordValidationResult"]:
        """
        Get keyword validation results list.

        Returns:
            List of KeywordValidationResult objects or empty list
        """
        if hasattr(self.state, 'keyword_validation_results') and self.state.keyword_validation_results:
            return self.state.keyword_validation_results
        return []

    def has_keyword_validation(self) -> bool:
        """Check if keyword validation data exists."""
        return hasattr(self.state, 'keyword_validation') and self.state.keyword_validation is not None

    def get_total_market_volume(self) -> int:
        """Get total market search volume from keyword validation."""
        if self.has_keyword_validation():
            return self.state.keyword_validation.overall_market_size
        return 0

    # ==================================================================================
    # Utility Methods
    # ==================================================================================

    def has_stage_data(self, stage_name: str) -> bool:
        """
        Check if specific stage data exists.

        Args:
            stage_name: One of 'pain_points', 'ideas', 'competitive', 'selection',
                       'refinement', 'seo', 'data_sources', 'social'

        Returns:
            True if stage data exists
        """
        mapping = {
            'pain_points': self.state.pain_point_analysis,
            'ideas': self.state.idea_generation,
            'competitive': self.state.competitive_analysis,
            'selection': self.state.solution_selection,
            'refinement': self.state.solution_refinement,
            'seo': self.state.seo_strategy_report,
            'data_sources': self.state.data_source_research,
            'social': self.state.social_content,
        }
        return mapping.get(stage_name) is not None
