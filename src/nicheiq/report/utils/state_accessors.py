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

from loguru import logger

from ...models.competitor import find_landscape_for_solution

if TYPE_CHECKING:
    from ...models.competitor import CompetitiveAnalysisResult
    from ...models.data_source import DataSourceResearchResult
    from ...models.keyword_data import KeywordValidationResult
    from ...models.pain_point import PainPointAnalysisResult
    from ...models.research_state import ResearchState
    from ...models.seo_strategy import SEOStrategyReport
    from ...models.solution_idea import IdeaGenerationResult, SolutionIdea
    from ...models.solution_refinement import SolutionRefinement
    from ...models.solution_selection import SolutionSelection
    from ...models.social_content import SocialContentCollection


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

    def get_solution_selection(self) -> Optional["SolutionSelection"]:
        """Get keyword validation solution selection result."""
        return self.state.solution_selection

    def get_solution_refinement(self) -> Optional["SolutionRefinement"]:
        """Get Stage 10 solution refinement result."""
        return self.state.solution_refinement

    def get_seo_strategy(self) -> Optional["SEOStrategyReport"]:
        """Get Stage 9 SEO strategy report."""
        return self.state.seo_strategy_report

    def get_data_source_research(self) -> Optional["DataSourceResearchResult"]:
        """Get Stage 13 data source research result (conditional)."""
        return self.state.data_source_research

    def get_social_content(self) -> Optional["SocialContentCollection"]:
        """Get Stage 5 social media content result."""
        return self.state.social_content

    def get_trend_longevity(self):
        """Get Stage 11 trend longevity analysis result."""
        return self.state.trend_longevity

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
            f"{pp.title} - {pp.description} (Severity: {pp.severity_score * 10:.1f}/10, WTP: {pp.willingness_to_pay * 10:.1f}/10)"
            for pp in sorted_pps
        ]

    def get_solution_pain_points(self, solution: "SolutionIdea") -> list:
        """
        Get pain points specific to a solution, sorted by priority.

        Matches pain point titles from solution.pain_points_addressed against
        the full PainPoint objects to get detailed scores and metadata.

        Args:
            solution: SolutionIdea with pain_points_addressed field

        Returns:
            List of top 3 PainPoint objects for this solution, sorted by priority.
            Falls back to top 3 overall pain points if no matches found.
        """
        if not self.state.pain_point_analysis:
            return []

        # Get all pain points
        all_pain_points = self.state.pain_point_analysis.pain_points

        # Filter to solution-specific pain points
        if solution.pain_points_addressed:
            solution_pain_points = [
                pp for pp in all_pain_points
                if pp.title in solution.pain_points_addressed
            ]
        else:
            solution_pain_points = []

        # If we found solution-specific pain points, sort and return top 3
        if solution_pain_points:
            sorted_pps = sorted(
                solution_pain_points,
                key=lambda x: (x.severity_score + x.willingness_to_pay) / 2,
                reverse=True,
            )
            return sorted_pps[:3]

        # Fallback: return top 3 overall pain points
        return self.get_sorted_pain_points()[:3]

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
        if self.state.idea_generation and self.state.idea_generation.solution_ideas:
            names = [s.solution_name for s in self.state.idea_generation.solution_ideas]
            return f"Generated {len(names)} solution concepts: {', '.join(names)}."
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
        if self.state.social_content and self.state.social_content.reddit_posts:
            return len(self.state.social_content.reddit_posts)
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
        if self.state.social_content and self.state.social_content.reddit_posts:
            for post in self.state.social_content.reddit_posts:
                subreddit = post.subreddit
                breakdown[subreddit] = breakdown.get(subreddit, 0) + 1
        return breakdown

    def get_real_community_hubs(self, llm_hubs: list[str] | None = None) -> list[str]:
        """
        Build community hubs list from real Reddit data + non-Reddit LLM hubs.

        Real subreddits (from collected posts) replace any r/... entries the LLM
        produced. Non-Reddit hubs (Discord, Slack, forums) from the LLM are preserved.

        Args:
            llm_hubs: Original community_hubs from LLM audience mapping

        Returns:
            List of community hub names: real subreddits (sorted by post count desc,
            capped at 10) followed by non-Reddit LLM hubs. Falls back to original
            LLM list if no Reddit data exists.
        """
        subreddit_breakdown = self.get_subreddit_breakdown()

        if not subreddit_breakdown:
            return llm_hubs or []

        # Build real subreddit list sorted by post count desc, capped at 10
        sorted_subreddits = sorted(
            subreddit_breakdown.items(), key=lambda x: x[1], reverse=True
        )
        real_hubs = [f"r/{name}" for name, _ in sorted_subreddits[:10]]

        # Keep non-Reddit LLM hubs (anything not starting with "r/")
        non_reddit_hubs = [
            hub for hub in (llm_hubs or [])
            if not hub.lower().startswith("r/")
        ]

        return real_hubs + non_reddit_hubs

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

    def get_tier_keyword_counts(self) -> dict[str, int]:
        """
        Get keyword counts for all SEO tiers (deduplicated across tiers).

        Keywords appearing in multiple tiers are counted only in the
        highest-priority tier (lowest tier number).

        Returns:
            Dict with keys: tier_0, tier_1, tier_2, tier_3, tier_4, total
        """
        if not self.state.seo_strategy_report:
            return {
                "tier_0": 0,
                "tier_1": 0,
                "tier_2": 0,
                "tier_3": 0,
                "tier_4": 0,
                "total": 0,
            }

        seo = self.state.seo_strategy_report
        seen: set[str] = set()
        duplicates_found = 0

        # Tier 0, 1, 2 are simple TieredKeyword lists
        tier0_count = 0
        for kw in (seo.tier_0_keywords or []):
            key = kw.keyword.lower().strip()
            if key not in seen:
                seen.add(key)
                tier0_count += 1
            else:
                duplicates_found += 1

        tier1_count = 0
        for kw in (seo.tier_1_keywords or []):
            key = kw.keyword.lower().strip()
            if key not in seen:
                seen.add(key)
                tier1_count += 1
            else:
                duplicates_found += 1

        tier2_count = 0
        for kw in (seo.tier_2_keywords or []):
            key = kw.keyword.lower().strip()
            if key not in seen:
                seen.add(key)
                tier2_count += 1
            else:
                duplicates_found += 1

        # Tier 3: Geographic groups (GeographicKeywordEntry.keyword)
        tier3_count = 0
        if seo.tier_3_geographic_groups:
            for group in seo.tier_3_geographic_groups:
                for entry in group.keywords:
                    key = entry.keyword.lower().strip()
                    if key not in seen:
                        seen.add(key)
                        tier3_count += 1
                    else:
                        duplicates_found += 1

        # Tier 4: Category groups (CategoryKeywordEntry.keyword_name)
        tier4_count = 0
        if seo.tier_4_category_groups:
            for group in seo.tier_4_category_groups:
                for entry in group.keywords:
                    key = entry.keyword_name.lower().strip()
                    if key not in seen:
                        seen.add(key)
                        tier4_count += 1
                    else:
                        duplicates_found += 1

        if duplicates_found > 0:
            logger.warning(
                f"⚠️ Found {duplicates_found} duplicate keywords across tiers "
                f"(source-side dedup may have failed)"
            )

        total_count = tier0_count + tier1_count + tier2_count + tier3_count + tier4_count

        return {
            "tier_0": tier0_count,
            "tier_1": tier1_count,
            "tier_2": tier2_count,
            "tier_3": tier3_count,
            "tier_4": tier4_count,
            "total": total_count,
        }

    def get_total_keyword_search_volume(self) -> int:
        """
        Get total search volume across all keywords (deduplicated across tiers).

        Keywords appearing in multiple tiers have their volume counted only once,
        from the highest-priority tier (lowest tier number).

        Primary source: seo_strategy_report (Stage 9 tiered keywords)
        Fallback: keyword_validation_results (keyword validation validated keywords)

        Returns:
            Sum of search volumes from available keyword data
        """
        # Primary: SEO strategy report (Stage 9)
        if self.state.seo_strategy_report:
            total_volume = 0
            seo = self.state.seo_strategy_report
            seen: set[str] = set()
            duplicates_found = 0

            # Sum tier 0, 1, 2
            for kw in (seo.tier_0_keywords or []):
                key = kw.keyword.lower().strip()
                if key not in seen:
                    seen.add(key)
                    total_volume += kw.search_volume or 0
                else:
                    duplicates_found += 1
            for kw in (seo.tier_1_keywords or []):
                key = kw.keyword.lower().strip()
                if key not in seen:
                    seen.add(key)
                    total_volume += kw.search_volume or 0
                else:
                    duplicates_found += 1
            for kw in (seo.tier_2_keywords or []):
                key = kw.keyword.lower().strip()
                if key not in seen:
                    seen.add(key)
                    total_volume += kw.search_volume or 0
                else:
                    duplicates_found += 1

            # Sum tier 3 geographic groups
            if seo.tier_3_geographic_groups:
                for group in seo.tier_3_geographic_groups:
                    for kw in group.keywords:
                        key = kw.keyword.lower().strip()
                        if key not in seen:
                            seen.add(key)
                            total_volume += kw.search_volume or 0
                        else:
                            duplicates_found += 1

            # Sum tier 4 category groups
            if seo.tier_4_category_groups:
                for group in seo.tier_4_category_groups:
                    for kw in group.keywords:
                        key = kw.keyword_name.lower().strip()
                        if key not in seen:
                            seen.add(key)
                            total_volume += kw.search_volume or 0
                        else:
                            duplicates_found += 1

            if duplicates_found > 0:
                logger.warning(
                    f"⚠️ Found {duplicates_found} duplicate keywords in volume calculation "
                    f"(source-side dedup may have failed)"
                )

            if total_volume > 0:
                return total_volume

        # Fallback: keyword_validation_results (keyword validation)
        # Used when Stage 9 SEO strategy failed or returned no keywords
        if self.state.keyword_validation_results:
            total_volume = sum(
                v.total_volume for v in self.state.keyword_validation_results
                if v.total_volume
            )
            if total_volume > 0:
                return total_volume

        return 0

    def get_primary_search_volume(self) -> int:
        """
        Get primary search volume, preferring SEO strategy report data.

        Primary: computed sum of tiered keyword volumes (when seo_strategy_report exists).
        Fallback: keyword_validation niche_relevant_volume for the selected solution.

        Returns:
            Monthly search volume, or 0 if unavailable
        """
        if self.state.seo_strategy_report:
            # Use computed total from actual tier keywords, not the stale
            # total_monthly_volume aggregate (which is set before cross-tier
            # dedup/hydration and can diverge from real keyword data).
            # There's no niche-filtering concept with SEO strategy data.
            return self.get_total_keyword_search_volume()
        # Legacy fallback: keyword validation
        if not self.state.solution_selection or not self.state.keyword_validation_results:
            return 0
        selected_name = self.state.solution_selection.selected_solution_name
        for v in self.state.keyword_validation_results:
            if v.solution_name.lower().strip() == selected_name.lower().strip():
                if v.niche_relevant_volume is not None:
                    return v.niche_relevant_volume
                return v.total_volume or 0
        return 0

    def get_niche_relevant_search_volume(self) -> int:
        """Deprecated alias for get_primary_search_volume()."""
        return self.get_primary_search_volume()

    def get_volume_filter_ratio(self) -> float | None:
        """
        Get the ratio of primary volume to Stage 9 total volume.

        Returns None when SEO strategy is the primary source (no filtering concept),
        or when either volume is unavailable.

        Returns:
            Ratio (primary / total) or None if unavailable
        """
        if self.state.seo_strategy_report:
            return None  # No filtering concept with SEO primary
        niche_vol = self.get_primary_search_volume()
        total_vol = self.get_total_keyword_search_volume()
        if total_vol == 0 or niche_vol == 0:
            return None
        return niche_vol / total_vol

    # ==================================================================================
    # Competitive Analysis Access Methods
    # ==================================================================================

    def get_selected_landscape(self):
        """
        Get competitive landscape for the selected solution.

        Finds the CompetitiveLandscape matching the selected solution name
        from Stage 8 competitive analysis. Case-insensitive, with fallback
        to first landscape.

        Returns:
            CompetitiveLandscape object for selected solution, or None if not found
        """
        if not self.state.competitive_analysis or not self.state.solution_selection:
            return None

        return find_landscape_for_solution(
            self.state.competitive_analysis,
            self.state.solution_selection.selected_solution_name,
        )

    def get_competitor_count(self) -> int:
        """
        Get number of competitors for the selected solution.

        Returns:
            Count of competitors from selected landscape, or 0 if not found
        """
        landscape = self.get_selected_landscape()
        if landscape and landscape.competitors:
            return len(landscape.competitors)
        return 0

    # ==================================================================================
    # Utility Methods
    # ==================================================================================

    def has_stage_data(self, stage_name: str) -> bool:
        """
        Check if specific stage data exists.

        Args:
            stage_name: One of 'pain_points', 'ideas', 'competitive', 'selection',
                       'refinement', 'seo', 'data_sources', 'social', 'trend'

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
            'trend': self.state.trend_longevity,
        }
        return mapping.get(stage_name) is not None

    # ==================================================================================
    # Keyword Validation Access Methods
    # ==================================================================================

    def get_keyword_validation_overview(self) -> str | None:
        """
        Generate keyword analysis overview and findings.

        When SEO strategy data is available, generates overview from tier data.
        Falls back to keyword validation methodology overview for legacy runs.

        Returns:
            Formatted markdown overview or None if no data
        """
        import json
        from loguru import logger
        from .model_helpers import safe_get_attr

        # Primary: SEO strategy report
        if self.state.seo_strategy_report:
            seo = self.state.seo_strategy_report
            total_keywords = getattr(seo, 'total_keywords_analyzed', 0) or 0
            total_volume = getattr(seo, 'total_monthly_volume', 0) or 0

            overview_parts = [
                f"## SEO Keyword Analysis Overview\n\n"
                f"Analyzed {total_keywords} keywords with {total_volume:,} total monthly search volume "
                f"across tiered strategy groups.\n\n"
                f"## Keyword Tier Breakdown\n\n"
            ]

            # Tier 0-2 stats
            for tier_num, tier_attr, tier_label in [
                (0, 'tier_0_keywords', 'Tier 0 (Premium/Foundation)'),
                (1, 'tier_1_keywords', 'Tier 1 (Quick Wins)'),
                (2, 'tier_2_keywords', 'Tier 2 (Strategic Growth)'),
            ]:
                kws = getattr(seo, tier_attr, None) or []
                count = len(kws)
                vol = sum(getattr(k, 'search_volume', 0) or 0 for k in kws)
                overview_parts.append(
                    f"**{tier_label}**: {count} keywords, {vol:,} monthly volume\n"
                )

            # Tier 3 geographic groups
            geo_groups = getattr(seo, 'tier_3_geographic_groups', None) or []
            if geo_groups:
                geo_count = sum(len(g.keywords) for g in geo_groups)
                geo_vol = sum(
                    getattr(k, 'search_volume', 0) or 0
                    for g in geo_groups for k in g.keywords
                )
                overview_parts.append(
                    f"**Tier 3 (Geographic)**: {len(geo_groups)} groups, "
                    f"{geo_count} keywords, {geo_vol:,} monthly volume\n"
                )

            # Tier 4 category groups
            cat_groups = getattr(seo, 'tier_4_category_groups', None) or []
            if cat_groups:
                cat_count = sum(len(g.keywords) for g in cat_groups)
                cat_vol = sum(
                    getattr(k, 'search_volume', 0) or 0
                    for g in cat_groups for k in g.keywords
                )
                overview_parts.append(
                    f"**Tier 4 (Category Expansion)**: {len(cat_groups)} groups, "
                    f"{cat_count} keywords, {cat_vol:,} monthly volume\n"
                )

            return "\n".join(overview_parts)

        # Fallback: keyword validation results (legacy)
        # Defensive: Handle malformed keyword_validation_results from old checkpoints
        if (self.state.keyword_validation_results and
            isinstance(self.state.keyword_validation_results, dict) and
            "data" in self.state.keyword_validation_results):
            logger.warning("Detected legacy checkpoint format for keyword_validation_results - attempting recovery")
            try:
                self.state.keyword_validation_results = json.loads(
                    self.state.keyword_validation_results["data"]
                )
            except Exception as e:
                logger.error(f"Failed to recover keyword_validation_results: {e}")
                self.state.keyword_validation_results = None

        if not self.state.keyword_validation_results:
            return None

        validation_count = len(self.state.keyword_validation_results)
        overview_parts = [
            f"## Keyword Validation Methodology\n\n"
            f"Validated top {validation_count} solution candidates using hybrid seed generation "
            f"(10 programmatic + 10 LLM seeds per solution) with DataForSEO keyword data API.\n\n"
            f"## Key Findings by Solution\n\n"
        ]

        for result in self.state.keyword_validation_results:
            sol_name = safe_get_attr(result, 'solution_name')
            validated = safe_get_attr(result, 'validated_count')
            total_vol = safe_get_attr(result, 'total_volume')
            niche_vol = safe_get_attr(result, 'niche_relevant_volume')
            demand_score = safe_get_attr(result, 'keyword_demand_score')
            demand_signal = safe_get_attr(result, 'demand_signal')

            vol_text = f"{total_vol:,} total monthly volume"
            if niche_vol is not None:
                vol_text = f"{niche_vol:,} niche-relevant volume ({total_vol:,} total)"

            overview_parts.append(
                f"**{sol_name}**: {validated}/20 keywords validated, "
                f"{vol_text}, "
                f"demand score: {demand_score:.2f} ({demand_signal})\n"
            )

        # Helper for accessing attributes from models or dicts
        def get_score(r):
            return r.get('keyword_demand_score') if isinstance(r, dict) else r.keyword_demand_score

        overview_parts.append(
            f"\n## Cross-Solution Comparison\n\n"
            f"Keyword demand scores ranged from "
            f"{min(get_score(r) for r in self.state.keyword_validation_results):.2f} to "
            f"{max(get_score(r) for r in self.state.keyword_validation_results):.2f}. "
            f"Validation enabled re-ranking based on actual search demand rather than architectural estimates."
        )

        return "\n".join(overview_parts)

    def get_keyword_validation_comparison(self) -> str | None:
        """
        Generate keyword analysis comparison table.

        When SEO strategy data is available, builds table from tier data.
        Falls back to keyword validation comparison for legacy runs.

        Returns:
            Formatted markdown table or None if no data
        """
        from .model_helpers import safe_get_attr

        # Primary: SEO strategy report
        if self.state.seo_strategy_report:
            seo = self.state.seo_strategy_report

            comparison_rows = [
                "| Tier | Keywords | Total Volume | Strategy |",
                "|------|----------|--------------|----------|"
            ]

            tier_data = [
                ('Tier 0 (Premium)', getattr(seo, 'tier_0_keywords', None) or []),
                ('Tier 1 (Quick Wins)', getattr(seo, 'tier_1_keywords', None) or []),
                ('Tier 2 (Long-tail)', getattr(seo, 'tier_2_keywords', None) or []),
            ]

            for label, kws in tier_data:
                count = len(kws)
                vol = sum(getattr(k, 'search_volume', 0) or 0 for k in kws)
                strategy = "Foundation" if "Premium" in label else ("Quick ranking" if "Quick" in label else "Content depth")
                comparison_rows.append(f"| {label} | {count} | {vol:,} | {strategy} |")

            # Tier 3 geographic
            geo_groups = getattr(seo, 'tier_3_geographic_groups', None) or []
            if geo_groups:
                geo_count = sum(len(g.keywords) for g in geo_groups)
                geo_vol = sum(
                    getattr(k, 'search_volume', 0) or 0
                    for g in geo_groups for k in g.keywords
                )
                comparison_rows.append(f"| Tier 3 (Geographic) | {geo_count} | {geo_vol:,} | Local targeting |")

            # Tier 4 category
            cat_groups = getattr(seo, 'tier_4_category_groups', None) or []
            if cat_groups:
                cat_count = sum(len(g.keywords) for g in cat_groups)
                cat_vol = sum(
                    getattr(k, 'search_volume', 0) or 0
                    for g in cat_groups for k in g.keywords
                )
                comparison_rows.append(f"| Tier 4 (Category) | {cat_count} | {cat_vol:,} | Category expansion |")

            return "\n".join(comparison_rows)

        # Fallback: keyword validation results (legacy)
        if not self.state.keyword_validation_results:
            return None

        comparison_rows = [
            "| Solution | Total Keywords | Tier 0 Premium | Tier 1 Quick Wins | Niche-Relevant Vol | Total Volume | Avg Competition | SEO Difficulty |",
            "|----------|---------------|----------------|-------------------|--------------------|--------------|-----------------|-----------  ----|"
        ]

        for result in self.state.keyword_validation_results:
            sol_name = safe_get_attr(result, 'solution_name')
            validated = safe_get_attr(result, 'validated_count')
            total_vol = safe_get_attr(result, 'total_volume')
            niche_vol = safe_get_attr(result, 'niche_relevant_volume')
            avg_comp = safe_get_attr(result, 'avg_competition')

            # Tier 0 and Tier 1 count estimation from top keywords
            top_kws = safe_get_attr(result, 'top_keywords')
            tier0_count = len([k for k in top_kws if k.get("competition", 100) < 20 and k.get("search_volume", 0) > 1000])
            tier1_count = len([k for k in top_kws if 20 <= k.get("competition", 100) < 40])

            # SEO difficulty assessment
            if avg_comp < 40:
                seo_difficulty = "Low"
            elif avg_comp < 60:
                seo_difficulty = "Medium"
            else:
                seo_difficulty = "High"

            niche_vol_str = f"{niche_vol:,}" if niche_vol is not None else "N/A"

            comparison_rows.append(
                f"| {sol_name} | {validated} | {tier0_count} | {tier1_count} | {niche_vol_str} | {total_vol:,} | {avg_comp:.1f}% | {seo_difficulty} |"
            )

        return "\n".join(comparison_rows)

    def get_content_strategy_preview(self) -> str | None:
        """
        Generate content strategy preview from refinement data.

        Returns:
            Formatted markdown preview or None if no refinement data
        """
        from .model_helpers import safe_get_attr

        if not self.state.solution_refinement:
            return None

        refinement = self.state.solution_refinement
        preview_parts = ["## Programmatic Content Opportunities\n\n"]

        # Geographic opportunities
        geo_priorities = safe_get_attr(refinement, 'geographic_priorities')
        if geo_priorities:
            preview_parts.append(
                f"Geographic expansion priorities identified: {', '.join(geo_priorities[:3])}. "
                f"Create localized landing pages for each target market.\n\n"
            )

        # Feature priorities for content clusters
        feature_priorities = safe_get_attr(refinement, 'feature_priorities')
        if feature_priorities:
            top_features = feature_priorities[:3]
            preview_parts.append(
                "## Quick Win Content Recommendations\n\n"
                "Top content clusters based on keyword support:\n"
            )
            for fp in top_features:
                # Handle feature priority as dict or object
                if isinstance(fp, dict):
                    preview_parts.append(f"- **{fp['feature_name']}**: {fp['keyword_support']} keywords, priority {fp['priority']}/10\n")
                else:
                    preview_parts.append(f"- **{fp.feature_name}**: {fp.keyword_support} keywords, priority {fp.priority}/10\n")

        # Strategic insights
        strategic_insights = safe_get_attr(refinement, 'strategic_insights')
        if strategic_insights:
            preview_parts.append("\n## Strategic Insights\n\n")
            for insight in strategic_insights:
                preview_parts.append(f"- {insight}\n")

        return "".join(preview_parts)
