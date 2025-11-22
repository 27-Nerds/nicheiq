"""
Stage 10 Report Generation Module

Handles final report generation using a hybrid approach:
- 80% Python data assembly (direct copy + templates)
- 20% LLM strategic synthesis (3 fields only)

Cost: ~$0.02-0.05 per report (vs $0.10-0.30 previously)
Speed: ~2-3 seconds (vs 5-15 seconds previously)
"""

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models.analytics import (
        CompetitiveAnalytics,
        MarketAnalytics,
        PainPointAnalytics,
        SEOAnalytics,
        VisualizationManifest,
    )
    from ..models.executive_summary import (
        CorePainPoint,
        ExecutiveDashboard,
        ExecutiveNarrative,
        GoNoGoVerdict,
        KeyMetrics,
    )
    from ..models.marketing_blueprint import (
        First30DaysPlaybook,
        GTMBlueprint,
        IdealCustomerProfile,
        MarketingChannel,
        MarketingNarrative,
    )
    from ..models.solution_idea import SolutionIdea, SolutionRefinement, SolutionSEORefinement
from loguru import logger
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..models.research_state import (
    AlternativeSolution,
    CompetitiveIntensityEntry,
    CompetitiveLandscapeMatrix,
    CompetitorMatrixEntry,
    DataInfrastructurePhase,
    DataInfrastructureRoadmap,
    EvidenceAppendix,
    FinalReport,
    PainPointEvidence,
    QuoteSource,
    ResearchMetadata,
    ResearchState,
    SubredditBreakdown,
    TopRedditThread,
)
from ..utils.helpers import find_solution_by_name
from .templates import ReportTemplates
from ..utils.llm_service import LLMService
from .utils import ScoreAccessor, StateAccessor


class ReportGenerator:
    """
    Stage 10 Final Report Generation.

    Generates comprehensive research reports using hybrid Python + LLM approach.

    Architecture:
    - Step 1: Python data assembly (80% of fields - direct copy/templates)
    - Step 2: Optional LLM synthesis (3 strategic fields only)
    - Step 3: Enhanced sections (Python-based data preservation)

    Attributes:
        state: Complete research state from all previous stages
        accessor: StateAccessor for defensive data extraction
        score_accessor: ScoreAccessor for score extraction with fallbacks
    """

    def __init__(self, state: ResearchState):
        """
        Initialize report generator.

        Args:
            state: Complete ResearchState containing all stage results
        """
        self.state = state
        self.accessor = StateAccessor(state)
        self.score_accessor = ScoreAccessor(state.solution_selection)

    def generate_report(self) -> FinalReport:
        """
        Generate complete final report using hybrid approach.

        Returns:
            FinalReport with all sections populated

        Steps:
            1. Generate base report using Python data assembly
            2. Enhance with LLM for 3 strategic synthesis fields
            3. Add enhanced sections for data preservation
        """
        logger.info("Step 1: Building report from research data (Python)...")
        final_report = self._assemble_base_report()
        logger.info(
            f"[OK] Base report assembled: {len(final_report.top_pain_points)} pain points, "
            f"{len(final_report.recommended_solutions)} solutions"
        )

        # Step 2: Enhance with LLM for strategic synthesis
        logger.info("Step 2: Enhancing with LLM for strategic synthesis (optional)...")
        final_report = self._enhance_report_with_llm(final_report)

        # Step 3: Generate enhanced report sections (Python-based data preservation)
        logger.info("Step 3: Generating enhanced report sections (Python)...")

        # Executive Dashboard (Phase 1 Enhancement) - TOP-LEVEL SUMMARY
        final_report.executive_dashboard = self._generate_executive_dashboard()
        if final_report.executive_dashboard:
            logger.info(
                f"[OK] Executive dashboard generated: "
                f"{final_report.executive_dashboard.go_no_go_verdict.verdict} verdict, "
                f"confidence {final_report.executive_dashboard.confidence_score:.2f}, "
                f"{final_report.executive_dashboard.key_metrics.total_keyword_count} keywords analyzed"
            )

        # Go-to-Market Blueprint (Phase 2 Enhancement) - ACTIONABLE GTM STRATEGY
        final_report.go_to_market_blueprint = self._generate_gtm_blueprint()
        if final_report.go_to_market_blueprint:
            logger.info(
                f"[OK] GTM blueprint generated: "
                f"{final_report.go_to_market_blueprint.ideal_customer_profile.persona_name} persona, "
                f"{len(final_report.go_to_market_blueprint.recommended_channels)} channels, "
                f"{len(final_report.go_to_market_blueprint.example_content_angles)} content angles"
            )

        # Analytics & Visualizations (Phase 3 Enhancement) - DATA-DRIVEN INSIGHTS
        (
            market_analytics,
            seo_analytics,
            competitive_analytics,
            pain_point_analytics,
            viz_manifest,
        ) = self._generate_analytics_and_visualizations()

        final_report.market_analytics = market_analytics
        final_report.seo_analytics = seo_analytics
        final_report.competitive_analytics = competitive_analytics
        final_report.pain_point_analytics = pain_point_analytics
        final_report.visualization_manifest = viz_manifest

        if market_analytics and seo_analytics:
            logger.info(
                f"[OK] Analytics & visualizations generated: "
                f"Opportunity score {market_analytics.overall_opportunity_score:.2f}, "
                f"{seo_analytics.total_keywords} keywords, "
                f"{competitive_analytics.competitor_count if competitive_analytics else 0} competitors, "
                f"{pain_point_analytics.total_pain_points if pain_point_analytics else 0} pain points"
            )

        if viz_manifest and viz_manifest.pain_point_matrix_path:
            logger.info(
                f"[OK] Charts exported: {viz_manifest.charts_format} format"
            )

        final_report.research_metadata = self._generate_research_metadata()
        if final_report.research_metadata:
            logger.info(
                f"[OK] Research metadata generated: "
                f"{final_report.research_metadata.reddit_posts_analyzed} Reddit posts, "
                f"{final_report.research_metadata.twitter_threads_analyzed} Twitter threads"
            )

        final_report.alternative_solutions = self._generate_alternative_solutions()
        if final_report.alternative_solutions:
            logger.info(
                f"[OK] Alternative solutions generated: "
                f"{len(final_report.alternative_solutions)} runner-up solutions detailed"
            )

        final_report.competitive_landscape_matrix = self._generate_competitive_landscape_matrix()
        if final_report.competitive_landscape_matrix:
            logger.info(
                f"[OK] Competitive landscape matrix generated: "
                f"{len(final_report.competitive_landscape_matrix.competitor_overlap)} "
                f"multi-solution competitors identified"
            )

        final_report.evidence_appendix = self._generate_evidence_appendix()
        if final_report.evidence_appendix:
            logger.info(
                f"[OK] Evidence appendix generated: "
                f"{len(final_report.evidence_appendix.top_reddit_threads)} top threads, "
                f"{len(final_report.evidence_appendix.pain_point_quote_sources)} "
                f"pain points with source attribution"
            )

        final_report.data_infrastructure_roadmap = self._generate_data_infrastructure_roadmap()
        if final_report.data_infrastructure_roadmap:
            logger.info(
                f"[OK] Data infrastructure roadmap generated: "
                f"{len(final_report.data_infrastructure_roadmap.phases)}-phase implementation plan"
            )

        # Content categorization from Stage 6 Task 1
        if self.state.pain_point_analysis and self.state.pain_point_analysis.content_categorization:
            final_report.content_categorization = self.state.pain_point_analysis.content_categorization
            logger.info(
                f"[OK] Content categorization included: "
                f"{len(final_report.content_categorization.theme_categories)} theme categories, "
                f"{len(final_report.content_categorization.user_segments)} user segments"
            )

        logger.info("[OK] Final report generation complete (Hybrid approach: 80% Python, 20% LLM)")
        return final_report

    # ==================================================================================
    # Core Report Assembly Methods
    # ==================================================================================

    def _assemble_base_report(self) -> FinalReport:
        """
        Assemble base FinalReport using Python data assembly (primary report generation path).

        This method creates a complete report by directly copying and formatting data
        from all previous stages. This is the primary report generation method (80% of work),
        which can then be enhanced with LLM for strategic synthesis fields (20% of work).
        """

        # Extract ALL pain points sorted by priority (severity + WTP)
        top_pain_points = self.accessor.get_formatted_pain_points()
        pain_points_summary = self.accessor.get_pain_points_summary()

        # Extract ALL recommended solutions (no limit)
        recommended_solutions = self.accessor.get_all_solution_names(selected_first=True)
        solutions_summary = self.accessor.get_solutions_summary()

        # Extract competitive summary (use existing strategic_recommendations)
        competitive_summary = self.accessor.get_competitive_summary()

        # Extract solution selection (Stage 8.5)
        selected_solution_name = self.accessor.get_selected_solution_name()
        selection_rationale = self.accessor.get_selection_rationale()
        runner_up_solutions = self.accessor.get_runner_up_solutions()
        selection_criteria_scores = self.accessor.get_selection_criteria_scores()
        recommended_focus = self.accessor.get_recommended_focus()

        # Find selected solution details using fuzzy match helper
        selected_solution_details = self.accessor.get_selected_solution_details()

        # Extract keyword validation and refinement data (Stage 8.8 and 8.85)
        # Extract keyword validation and content strategy data using accessor
        keyword_validation_overview = self.accessor.get_keyword_validation_overview()
        solution_keyword_comparison = self.accessor.get_keyword_validation_comparison()
        content_strategy_preview = self.accessor.get_content_strategy_preview()

        # Merge enrichments into selected_solution_details (unified enrichment pattern)
        # This merges Stage 8.85 (keyword refinement) + Stage 9.5 (SEO refinement) into base solution
        if selected_solution_details:
            selected_solution_details = self._merge_solution_enrichments(
                base_solution=selected_solution_details,
                keyword_enrichment=self.state.solution_refinement,
                seo_enrichment=getattr(self.state, 'seo_enrichment', None)
            )

        # Generate template-based sections using ReportTemplates
        solution_user_journey = ReportTemplates.user_journey(selected_solution_details)
        solution_implementation_overview = ReportTemplates.implementation_overview(selected_solution_details)
        mvp_scope_definition = ReportTemplates.mvp_scope(selected_solution_details)
        acquisition_strategy_summary = ReportTemplates.acquisition_strategy(selected_solution_details)
        estimated_cac_breakdown = ReportTemplates.cac_breakdown(selected_solution_details)

        # Generate market_validation based on actual metrics
        total_volume = self.state.keyword_validation.overall_market_size if self.state.keyword_validation else 0
        pain_point_count = len(self.state.pain_point_analysis.pain_points) if self.state.pain_point_analysis else 0

        if (total_volume > settings.market_validation_strong_volume and
            pain_point_count >= settings.market_validation_strong_pain_points):
            validation_level = "STRONG"
        elif (total_volume > settings.market_validation_moderate_volume and
              pain_point_count >= settings.market_validation_moderate_pain_points):
            validation_level = "MODERATE"
        else:
            validation_level = "EMERGING"

        market_validation = (
            f"{validation_level} market validation. "
            f"Total search volume: {total_volume:,} monthly searches. "
            f"Validated pain points: {pain_point_count}. "
            f"Competitive landscape shows existing market demand."
        )

        # Generate data_sourcing_recommendations
        data_sourcing_recommendations = "No data aggregation required for this solution."
        if self.state.data_source_research:
            dsr = self.state.data_source_research
            recs = ["## Data Sourcing Strategy\n"]
            recs.append(f"**Primary Sources:** {len(dsr.primary_data_sources)} providers identified")
            for ds in dsr.primary_data_sources[:5]:
                recs.append(f"- **{ds.provider}**: {ds.coverage} ({ds.access_model}, {ds.cost_estimate})")
            recs.append(f"\n**Estimated Monthly Cost:** {dsr.estimated_monthly_cost}")
            recs.append(f"\n**Implementation Priority:** {dsr.seo_aligned_priorities or 'Focus on high-volume sources first'}")
            data_sourcing_recommendations = "\n".join(recs)

        # Get SEO strategy (should already be generated)
        if not self.state.seo_strategy_report:
            # Generate minimal SEO strategy if missing
            from ..models.seo_strategy import SEOStrategyReport
            seo_strategy = SEOStrategyReport(
                total_keywords_analyzed=0,
                total_monthly_volume=0,
                key_findings=["SEO strategy generation failed - manual keyword research required"],
                tier_1_keywords=[],
                tier_1_quick_win_strategy="SEO strategy generation failed. Conduct manual keyword research.",
                content_strategy="Develop content strategy after completing keyword research.",
                technical_seo_recommendations="Standard technical SEO best practices apply.",
                competitive_positioning="Conduct keyword research to identify competitive opportunities.",
                implementation_roadmap="1. Complete keyword research\n2. Develop SEO strategy\n3. Implement content plan",
                key_metrics_to_track=["Keyword research completion", "Initial rankings"],
                long_term_strategy="Year 1: Establish SEO foundation and baseline metrics",
                conclusion_bottom_line="Complete keyword research to enable comprehensive SEO strategy.",
                competitive_advantages=["To be determined after keyword research"],
                critical_success_factors=["Complete keyword research"],
                expected_timeline="TBD - awaiting keyword research",
                next_steps_checklist=["⬜ Complete keyword research", "⬜ Develop SEO strategy"],
            )
        else:
            seo_strategy = self.state.seo_strategy_report

        # Build comprehensive final report with all fields
        return FinalReport(
            # Basic info
            niche=self.state.niche_context.niche_description,
            executive_summary=f"Market research completed for {self.state.niche_context.niche_description}. "
            f"Identified {len(top_pain_points)} validated pain points and "
            f"{len(recommended_solutions)} solution concepts. "
            f"Selected solution: {selected_solution_name}.",

            # Solution selection (Stage 8.75)
            selected_solution_name=selected_solution_name,
            selection_rationale=selection_rationale,
            runner_up_solutions=runner_up_solutions,
            selection_criteria_scores=selection_criteria_scores,
            recommended_focus=recommended_focus,

            # Detailed solution description (NEW - production-quality templates)
            selected_solution_details=selected_solution_details,
            solution_user_journey=solution_user_journey,
            solution_implementation_overview=solution_implementation_overview,
            mvp_scope_definition=mvp_scope_definition,

            # Pain points (ALL pain points, no limit)
            top_pain_points=top_pain_points if top_pain_points else ["No pain points identified"],
            pain_points_summary=pain_points_summary,

            # Solutions (ALL solutions, selected first)
            recommended_solutions=recommended_solutions if recommended_solutions else ["No solutions generated"],
            solutions_summary=solutions_summary,

            # Competitive analysis
            competitive_summary=competitive_summary,
            competitive_analysis=self.state.competitive_analysis,

            # Market validation (data-driven assessment)
            market_validation=market_validation,

            # SEO strategy
            seo_strategy=seo_strategy,

            # Organic acquisition strategy (NEW - template-based)
            acquisition_strategy_summary=acquisition_strategy_summary,
            estimated_cac_breakdown=estimated_cac_breakdown,

            # Keyword validation & refinement (Stage 8.8 and 8.85)
            keyword_validation_overview=keyword_validation_overview,
            solution_keyword_comparison=solution_keyword_comparison,
            content_strategy_preview=content_strategy_preview,

            # Data sourcing (template or structured)
            data_source_research=self.state.data_source_research,
            data_sourcing_recommendations=data_sourcing_recommendations,

            # Next steps (generic template)
            next_steps=[
                "Review detailed research findings",
                "Validate top pain points with target users",
                "Design and develop MVP",
                "Implement SEO strategy",
                "Set up data sourcing infrastructure" if self.state.data_source_research else "Launch beta version",
            ],

            # Metadata
            generated_at=datetime.utcnow(),
        )

    def _merge_solution_enrichments(
        self,
        base_solution: "SolutionIdea",
        keyword_enrichment: "SolutionRefinement | None",
        seo_enrichment: "SolutionSEORefinement | None"
    ) -> "SolutionIdea":
        """
        Merge base solution with enrichments from later stages.

        This implements the unified enrichment pattern where:
        - Stage 7 creates base solution with core fields
        - Stage 8.85 outputs keyword enrichment (geographic priorities, features, insights)
        - Stage 9.5 outputs SEO enrichment (refined scores using keyword data)
        - Report generator merges all into complete SolutionIdea

        Benefits:
        - Base solutions remain immutable during pipeline
        - Each stage output is independently testable
        - Clear what data each stage contributes
        - No null fields in final output

        Args:
            base_solution: Original solution from Stage 7 (UnifiedSolutionCrew)
            keyword_enrichment: Optional enrichment from Stage 8.85 (SolutionRefinementCrew)
            seo_enrichment: Optional enrichment from Stage 9.5 (Flow-based SEO refinement)

        Returns:
            Complete SolutionIdea with all available enrichments applied
        """
        from copy import deepcopy

        # Start with deep copy of base solution (immutability)
        enriched = deepcopy(base_solution)

        # Apply keyword enrichment (Stage 8.85)
        if keyword_enrichment:
            # Map SolutionRefinement fields to SolutionIdea fields
            enriched.keyword_geographic_priorities = keyword_enrichment.geographic_priorities

            # Convert FeaturePriority objects to simple list of feature names
            enriched.keyword_feature_priorities = [
                f.feature_name for f in keyword_enrichment.feature_priorities
            ] if keyword_enrichment.feature_priorities else None

            # Join strategic insights into single string
            enriched.keyword_strategic_insights = ". ".join(
                keyword_enrichment.strategic_insights
            ) if keyword_enrichment.strategic_insights else None

            enriched.category_pivot_suggestion = keyword_enrichment.category_pivot_recommendation

            logger.info(
                f"[Report] Applied keyword enrichment: "
                f"{len(keyword_enrichment.geographic_priorities) if keyword_enrichment.geographic_priorities else 0} geo priorities, "
                f"{len(keyword_enrichment.feature_priorities) if keyword_enrichment.feature_priorities else 0} feature priorities"
            )

        # Apply SEO enrichment (Stage 9.5)
        if seo_enrichment:
            enriched.seo_scalability_score_refined = seo_enrichment.seo_scalability_score_refined
            enriched.estimated_cac_organic_refined = seo_enrichment.estimated_cac_organic_refined
            enriched.programmatic_seo_opportunity_refined = seo_enrichment.programmatic_seo_opportunity_refined
            enriched.estimated_indexable_pages = seo_enrichment.estimated_indexable_pages
            enriched.seo_refinement_metadata = seo_enrichment.seo_refinement_metadata

            # Format optional values (handle None)
            scalability_str = (
                f"{seo_enrichment.seo_scalability_score_refined:.2f}"
                if seo_enrichment.seo_scalability_score_refined is not None
                else "N/A"
            )
            pages_str = (
                f"{seo_enrichment.estimated_indexable_pages:,}"
                if seo_enrichment.estimated_indexable_pages is not None
                else "N/A"
            )

            logger.info(
                f"[Report] Applied SEO enrichment: "
                f"refined scalability {scalability_str}, "
                f"{pages_str} pages"
            )

        return enriched

    def _enhance_report_with_llm(self, base_report: FinalReport) -> FinalReport:
        """
        Enhance Python-generated report with LLM for 3 strategic synthesis fields only.

        Takes a complete report from _assemble_base_report() and uses LLM to generate:
        1. executive_summary (4-6 sentence strategic synthesis)
        2. acquisition_strategy_summary (2-3 paragraph SEO strategy narrative)
        3. next_steps (5-8 prioritized action items)

        All other fields are preserved from base_report.
        """
        from ..utils.prompts import load_prompt

        # Define minimal Pydantic model for 3 fields only
        class StrategicSynthesis(BaseModel):
            executive_summary: str = Field(
                ...,
                description="4-6 sentence executive summary synthesizing the entire research"
            )
            acquisition_strategy_summary: str = Field(
                ...,
                description="2-3 paragraph overview of customer acquisition strategy emphasizing organic channels"
            )
            next_steps: list[str] = Field(
                ...,
                description="5-8 prioritized, specific action items for implementation"
            )

        # Load prompt template from YAML
        template = load_prompt("report_strategic_synthesis")
        prompt = template.format(
            niche=base_report.niche,
            selected_solution_name=base_report.selected_solution_name,
            pain_points_count=len(base_report.top_pain_points),
            market_validation=base_report.market_validation,
            seo_scalability=base_report.selected_solution_details.seo_scalability_score if base_report.selected_solution_details else 'N/A',
            selection_rationale=base_report.selection_rationale,
            top_pain_points=', '.join(base_report.top_pain_points[:3]),
            project_type=base_report.selected_solution_details.project_type if base_report.selected_solution_details else 'N/A',
            indexable_pages=base_report.selected_solution_details.estimated_indexable_pages if base_report.selected_solution_details else 'N/A',
            cac_organic=base_report.selected_solution_details.estimated_cac_organic if base_report.selected_solution_details else 'N/A'
        )

        try:
            logger.info("Enhancing report with LLM for strategic synthesis (3 fields)...")

            # Use LLMService for structured output (temp 0.7 for strategic creativity)
            synthesis = LLMService.invoke_structured(
                prompt=prompt,
                output_model=StrategicSynthesis,
                temperature=0.7
            )

            # Update only the 3 strategic fields, preserve everything else
            base_report.executive_summary = synthesis.executive_summary
            base_report.acquisition_strategy_summary = synthesis.acquisition_strategy_summary
            base_report.next_steps = synthesis.next_steps

            logger.info("[OK] Report enhanced with LLM strategic synthesis")
            return base_report

        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}. Using template-based fields.")
            # Return base report unchanged if LLM fails
            return base_report

    # ==================================================================================
    # Enhanced Section Generators (6 methods)
    # ==================================================================================

    def _generate_research_metadata(self) -> "ResearchMetadata | None":
        """
        Generate research metadata section with social content collection statistics.

        Returns:
            ResearchMetadata object with Reddit/Twitter stats, subreddit breakdown, and collection info
        """
        social_content = self.accessor.get_social_content()
        if not social_content:
            return None

        try:
            # Count Reddit posts and comments
            reddit_posts_analyzed = len(social_content.reddit_posts)
            reddit_comments_analyzed = sum(len(post.comments) for post in social_content.reddit_posts)

            # Count Twitter threads
            twitter_threads_analyzed = len(social_content.twitter_threads)

            # Calculate subreddit breakdown (top 10)
            subreddit_counts = self.accessor.get_subreddit_breakdown()

            top_subreddits = [
                SubredditBreakdown(name=name, post_count=count)
                for name, count in sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]

            # Calculate data size (rough estimate from JSON serialization)
            social_content_json = social_content.model_dump_json()
            data_size_mb = len(social_content_json.encode('utf-8')) / (1024 * 1024)

            return ResearchMetadata(
                reddit_posts_analyzed=reddit_posts_analyzed,
                reddit_comments_analyzed=reddit_comments_analyzed,
                twitter_threads_analyzed=twitter_threads_analyzed,
                top_subreddits=top_subreddits,
                collection_date=social_content.collection_timestamp,
                data_size_mb=round(data_size_mb, 2)
            )
        except Exception as e:
            logger.warning(f"Failed to generate research metadata: {e}")
            return None

    def _generate_alternative_solutions(self) -> list["AlternativeSolution | None"]:
        """
        Generate alternative solution summaries for runner-up solutions.

        Returns:
            List of AlternativeSolution objects (top 2 runner-ups with full details)
        """
        solution_selection = self.accessor.get_solution_selection()
        idea_generation = self.accessor.get_idea_generation()

        if not solution_selection or not idea_generation:
            return None

        try:
            # Get runner-up solution names
            runner_up_names = self.accessor.get_runner_up_solutions()
            if not runner_up_names:
                return None

            # Find full solution details from idea_generation stage
            all_solutions = {idea.solution_name: idea for idea in idea_generation.solution_ideas}

            alternative_solutions = []
            for runner_up_name in runner_up_names[:2]:  # Top 2 runners-up
                if runner_up_name not in all_solutions:
                    logger.warning(f"Runner-up solution '{runner_up_name}' not found in idea generation results")
                    continue

                solution = all_solutions[runner_up_name]

                # Generate 2-3 paragraph summary
                summary = f"""**Overview:** {solution.description}

**Key Features:** {', '.join(solution.core_features[:5])}

**Target Users:** This solution is best suited for {', '.join(solution.target_personas[:2])}.
It differentiates through {solution.differentiation_factors[0] if solution.differentiation_factors else 'unique positioning'}.

**Technical Approach:** {solution.technical_approach}
"""

                # Use ScoreAccessor for consistent score extraction with automatic fallback
                market_fit = self.score_accessor.get_market_fit(solution)
                technical_feasibility = self.score_accessor.get_technical_feasibility(solution)
                competitive_advantage = self.score_accessor.get_competitive_advantage(solution)
                seo_growth = self.score_accessor.get_seo_growth(solution)

                # Determine pivot trigger based on solution characteristics (handle None scores)
                pivot_trigger = f"Pivot to {runner_up_name} if: "
                if market_fit is not None and market_fit > 0.9:
                    pivot_trigger += "user research reveals significantly higher demand for this specific pain point, "
                if seo_growth is not None and seo_growth > 0.85:
                    pivot_trigger += "SEO keyword volume for this solution is 2x higher than primary choice, "
                if technical_feasibility is not None and technical_feasibility > 0.9:
                    pivot_trigger += "faster time-to-market is critical and this solution has simpler tech requirements"

                alternative_solutions.append(AlternativeSolution(
                    solution_name=solution.solution_name,
                    summary=summary.strip(),
                    market_fit_score=market_fit,
                    technical_feasibility_score=technical_feasibility,
                    competitive_advantage_score=competitive_advantage,
                    seo_growth_potential_score=seo_growth,
                    key_differentiator=solution.differentiation_factors[0] if solution.differentiation_factors else "Key differentiator not identified",
                    best_suited_for=solution.target_personas[0] if solution.target_personas else "Target persona not defined",
                    pivot_trigger=pivot_trigger.rstrip(", ")
                ))

            return alternative_solutions if alternative_solutions else None
        except Exception as e:
            logger.warning(f"Failed to generate alternative solutions: {e}")
            return None

    def _generate_competitive_landscape_matrix(self) -> "CompetitiveLandscapeMatrix | None":
        """
        Generate cross-solution competitive analysis showing competitor overlap and patterns.

        Returns:
            CompetitiveLandscapeMatrix with competitor overlap and intensity analysis
        """
        if not self.state.competitive_analysis:
            return None

        try:
            # Collect all solution names
            all_solutions = [landscape.solution_name for landscape in self.state.competitive_analysis.solution_landscapes]

            # Build competitor overlap map
            competitor_appearances: dict[str, dict[str, Any]] = {}
            competitive_intensity_list: list[CompetitiveIntensityEntry] = []

            for landscape in self.state.competitive_analysis.solution_landscapes:
                # Track competitive intensity
                competitive_intensity_list.append(
                    CompetitiveIntensityEntry(
                        solution_name=landscape.solution_name,
                        intensity=landscape.competitive_intensity
                    )
                )

                # Track competitor appearances
                if landscape.competitors:  # Handle None case when no competitors found
                    for competitor in landscape.competitors:
                        if competitor.name not in competitor_appearances:
                            competitor_appearances[competitor.name] = {
                                "solutions": [],
                                "type": competitor.competitor_type,
                                "threat_level": "Threat level not assessed"
                            }
                        competitor_appearances[competitor.name]["solutions"].append(landscape.solution_name)

            # Create competitor matrix entries (only multi-solution competitors)
            competitor_overlap = [
                CompetitorMatrixEntry(
                    competitor_name=name,
                    solutions_competed=data["solutions"],
                    competitor_type=data["type"],
                    threat_level=data["threat_level"]
                )
                for name, data in competitor_appearances.items()
                if len(data["solutions"]) > 1  # Only show competitors in multiple solution spaces
            ]

            # Sort by number of solutions competed (most versatile competitors first)
            competitor_overlap.sort(key=lambda x: len(x.solutions_competed), reverse=True)

            # Generate market insight
            intensity_counts = {}
            for entry in competitive_intensity_list:
                intensity_counts[entry.intensity] = intensity_counts.get(entry.intensity, 0) + 1

            market_insight = f"Analyzed {len(all_solutions)} solution concepts across the competitive landscape. "
            if intensity_counts:
                market_insight += f"Competitive intensity distribution: {', '.join(f'{k}: {v}' for k, v in intensity_counts.items())}. "
            if competitor_overlap:
                market_insight += f"{len(competitor_overlap)} competitors appear across multiple solution spaces, indicating platform players with broad market coverage. "
                top_competitor = competitor_overlap[0]
                market_insight += f"Most versatile competitor: {top_competitor.competitor_name} (competes in {len(top_competitor.solutions_competed)} solution categories)."

            return CompetitiveLandscapeMatrix(
                all_solutions_analyzed=all_solutions,
                competitor_overlap=competitor_overlap,
                competitive_intensity_by_solution=competitive_intensity_list,
                market_insight=market_insight
            )
        except Exception as e:
            logger.warning(f"Failed to generate competitive landscape matrix: {e}")
            return None

    def _generate_evidence_appendix(self) -> "EvidenceAppendix | None":
        """
        Generate evidence appendix with top Reddit threads and pain point quote sources.

        Returns:
            EvidenceAppendix with traceability from pain points to original posts
        """
        if not self.state.social_content or not self.state.pain_point_analysis:
            return None

        try:
            # Extract top 10 Reddit threads by engagement score
            reddit_posts = sorted(
                self.state.social_content.reddit_posts,
                key=lambda p: p.score,
                reverse=True
            )[:10]

            top_reddit_threads = [
                TopRedditThread(
                    post_id=post.post_id,
                    title=post.title,
                    subreddit=post.subreddit,
                    score=post.score,
                    num_comments=post.num_comments,
                    url=post.url,
                    key_insight=f"High-engagement discussion ({post.score} score, {post.num_comments} comments) in r/{post.subreddit}"
                )
                for post in reddit_posts
            ]

            # Create post ID to metadata mapping
            post_metadata: dict[str, dict[str, Any]] = {}
            for post in self.state.social_content.reddit_posts:
                post_metadata[post.post_id] = {
                    "subreddit": post.subreddit,
                    "score": post.score,
                    "url": post.url
                }
            for thread in self.state.social_content.twitter_threads:
                post_metadata[thread.thread_id] = {
                    "subreddit": "Twitter",  # Use "Twitter" as platform indicator
                    "score": thread.original_tweet.likes,
                    "url": thread.original_tweet.url
                }

            # Map pain points to source posts
            pain_point_quote_sources = []
            for pain_point in self.state.pain_point_analysis.pain_points:
                quotes_with_sources = []

                for i, quote in enumerate(pain_point.representative_quotes[:3]):  # Top 3 quotes
                    # Re-extract source ID directly from quote suffix [source: ID]
                    source_match = re.search(r'\[source:\s*([^\]]+)\]', quote)
                    source_id = source_match.group(1).strip() if source_match else "unknown"

                    # Clean quote for display (remove [source: ID] suffix)
                    cleaned_quote = re.sub(r'\s*\[source:[^\]]+\]', '', quote).strip()

                    metadata = post_metadata.get(source_id, {"subreddit": "Unknown", "score": 0})

                    # Phase 1.1 & 2.2: Use settings for max length, truncate at word boundaries
                    if len(cleaned_quote) > settings.report_max_quote_length:
                        # Truncate at last space before limit for cleaner appearance
                        truncate_at = settings.report_max_quote_length - 3  # Reserve space for "..."
                        last_space = cleaned_quote.rfind(' ', 0, truncate_at)
                        if last_space > 0:
                            display_quote = cleaned_quote[:last_space] + "..."
                        else:
                            display_quote = cleaned_quote[:truncate_at] + "..."
                    else:
                        display_quote = cleaned_quote

                    quotes_with_sources.append(QuoteSource(
                        quote=display_quote,
                        post_id=source_id,
                        subreddit=metadata["subreddit"],
                        score=str(metadata["score"])
                    ))

                pain_point_quote_sources.append(PainPointEvidence(
                    pain_point_title=pain_point.title,
                    quotes_with_sources=quotes_with_sources
                ))

            return EvidenceAppendix(
                top_reddit_threads=top_reddit_threads,
                pain_point_quote_sources=pain_point_quote_sources
            )
        except Exception as e:
            logger.warning(f"Failed to generate evidence appendix: {e}")
            return None

    def _generate_data_infrastructure_roadmap(self) -> "DataInfrastructureRoadmap | None":
        """
        Generate data infrastructure roadmap from structured implementation_phases.

        Only processes structured data. Returns None if unavailable or incomplete.

        Returns:
            DataInfrastructureRoadmap with 3 phases, or None if data unavailable
        """
        if not self.state.data_source_research:
            return None

        try:
            data_research = self.state.data_source_research

            # Only use structured implementation_phases
            if not data_research.implementation_phases or len(data_research.implementation_phases) < 3:
                logger.debug("Structured implementation_phases unavailable or incomplete")
                return None

            # Transform structured phases directly
            phases = [
                DataInfrastructurePhase(
                    phase_number=phase.phase_number,
                    phase_name=phase.phase_name,
                    timeline=phase.timeline,
                    data_sources=phase.data_sources,
                    estimated_monthly_cost=phase.estimated_monthly_cost,
                    key_risks=phase.fallback_strategies[:3] if phase.fallback_strategies else []
                )
                for phase in data_research.implementation_phases[:3]
            ]

            # Generate cost scaling insight from data
            first_cost = phases[0].estimated_monthly_cost
            primary_risk = data_research.data_quality_risks[0] if data_research.data_quality_risks else "Monitor API rate limits and implement fallback strategies"

            cost_scaling_insight = (
                f"Data infrastructure costs start at {first_cost} during MVP, scaling with user growth. "
                f"{primary_risk}. "
                f"Critical mitigation: Implement tiered data source strategy with free/low-cost sources for baseline features, "
                f"premium APIs for advanced personalization."
            )

            return DataInfrastructureRoadmap(
                phases=phases,
                cost_scaling_insight=cost_scaling_insight
            )
        except Exception as e:
            logger.warning(f"Failed to generate data infrastructure roadmap: {e}")
            return None

    # ==================================================================================
    # Executive Dashboard Generator (Phase 1 Enhancement)
    # ==================================================================================

    def _generate_executive_dashboard(self) -> "ExecutiveDashboard | None":
        """
        Generate executive dashboard for quick decision-making.

        Uses hybrid approach:
        - 90% Python: Metrics computation, data extraction
        - 10% LLM: Strategic narrative (tagline, value prop, verdict rationale)

        Returns:
            ExecutiveDashboard object with go/no-go verdict, core pain point, and metrics
        """
        try:
            from ..models.executive_summary import (
                ExecutiveDashboard,
                SolutionSnapshot,
            )

            # Extract selected solution details
            selected_solution = self.accessor.get_selected_solution_details()

            if not selected_solution:
                logger.warning("No selected solution found - cannot generate executive dashboard")
                return None

            # Step 1: Compute metrics (Python - 60% of work)
            key_metrics = self._compute_executive_metrics()
            if not key_metrics:
                logger.warning("Failed to compute executive metrics")
                return None

            # Step 2: Extract core pain point (Python - 20% of work)
            core_pain_point = self._extract_core_pain_point()
            if not core_pain_point:
                logger.warning("Failed to extract core pain point")
                return None

            # Step 3: Generate narrative components (LLM - 10% of work)
            narrative = self._generate_executive_narrative(
                selected_solution=selected_solution,
                core_pain_point=core_pain_point,
                key_metrics=key_metrics
            )

            # Step 4: Assemble dashboard (Python - 10% of work)
            solution_snapshot = SolutionSnapshot(
                name=selected_solution.solution_name,
                tagline=narrative.tagline if narrative else f"{selected_solution.solution_name} for {selected_solution.target_personas[0] if selected_solution.target_personas else 'target users'}",
                core_value_prop=narrative.core_value_prop if narrative else selected_solution.description,
                project_type=selected_solution.project_type
            )

            # Compute go/no-go verdict
            go_no_go_verdict = self._compute_go_no_go_verdict(
                selected_solution=selected_solution,
                narrative_rationale=narrative.verdict_rationale if narrative else None
            )

            # Compute confidence score using ScoreAccessor
            confidence_score = self.score_accessor.get_confidence_score(selected_solution)

            executive_dashboard = ExecutiveDashboard(
                recommended_solution_snapshot=solution_snapshot,
                go_no_go_verdict=go_no_go_verdict,
                core_pain_point=core_pain_point,
                key_metrics=key_metrics,
                confidence_score=confidence_score,
                niche_description=self.state.niche_context.niche_description
            )

            logger.info(f"[OK] Executive dashboard generated: {go_no_go_verdict.verdict} verdict, confidence {confidence_score:.2f}")
            return executive_dashboard

        except Exception as e:
            logger.warning(f"Failed to generate executive dashboard: {e}")
            return None

    def _compute_executive_metrics(self) -> "KeyMetrics | None":
        """
        Compute top-line metrics for executive dashboard (Python-only).

        Returns:
            KeyMetrics object with keyword stats, pain point stats, competitor counts
        """
        try:
            from ..models.executive_summary import KeyMetrics

            # Keyword metrics from SEO strategy
            total_keyword_search_volume = 0
            tier1_keyword_count = 0
            tier2_keyword_count = 0
            total_keyword_count = 0

            # Get keyword counts and volumes using accessor
            tier_counts = self.accessor.get_tier_keyword_counts()
            total_keyword_count = tier_counts["total"]
            tier1_keyword_count = tier_counts["tier_1"]
            tier2_keyword_count = tier_counts["tier_2"]
            total_keyword_search_volume = self.accessor.get_total_keyword_search_volume()

            # Pain point metrics
            high_priority_pain_points = 0
            avg_pain_point_severity = 0.0
            avg_willingness_to_pay = 0.0

            if self.state.pain_point_analysis and self.state.pain_point_analysis.pain_points:
                pain_points = self.state.pain_point_analysis.pain_points
                high_priority_pain_points = len([
                    pp for pp in pain_points
                    if pp.severity_score >= settings.pain_point_high_priority_threshold
                ])

                avg_pain_point_severity = sum(pp.severity_score for pp in pain_points) / len(pain_points)
                avg_willingness_to_pay = sum(pp.willingness_to_pay for pp in pain_points) / len(pain_points)

            # Competitor count from selected solution's competitive analysis
            primary_competitor_count = self.accessor.get_competitor_count()

            # Social evidence metrics
            social_evidence_threads = 0
            if self.state.social_content:
                social_evidence_threads += len(self.state.social_content.reddit_posts)
                social_evidence_threads += len(self.state.social_content.twitter_threads)

            # Extract score fields from selected solution
            selected_solution = self.accessor.get_selected_solution_details()
            if not selected_solution:
                logger.warning("No selected solution for metrics - using default scores")
                market_fit_score = settings.score_accessor_default_fallback
                competitive_advantage_score = settings.score_accessor_default_fallback
                technical_feasibility_score = settings.score_accessor_default_fallback
                seo_potential_score = settings.score_accessor_default_fallback
            else:
                market_fit_score = self.score_accessor.get_market_fit(selected_solution)
                competitive_advantage_score = self.score_accessor.get_competitive_advantage(selected_solution)
                technical_feasibility_score = self.score_accessor.get_technical_feasibility(selected_solution)
                seo_potential_score = self.score_accessor.get_seo_growth(selected_solution)

            return KeyMetrics(
                total_keyword_search_volume=total_keyword_search_volume,
                tier1_keyword_count=tier1_keyword_count,
                tier2_keyword_count=tier2_keyword_count,
                total_keyword_count=total_keyword_count,
                high_priority_pain_points=high_priority_pain_points,
                primary_competitor_count=primary_competitor_count,
                avg_pain_point_severity=avg_pain_point_severity,
                avg_willingness_to_pay=avg_willingness_to_pay,
                social_evidence_threads=social_evidence_threads,
                market_fit_score=market_fit_score,
                competitive_advantage_score=competitive_advantage_score,
                technical_feasibility_score=technical_feasibility_score,
                seo_potential_score=seo_potential_score
            )

        except Exception as e:
            logger.warning(f"Failed to compute executive metrics: {e}")
            return None

    def _extract_core_pain_point(self) -> "CorePainPoint | None":
        """
        Extract the #1 pain point for executive dashboard (Python-only).

        Returns:
            CorePainPoint object with top pain point details and representative quote
        """
        try:
            from ..models.executive_summary import CorePainPoint

            if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
                logger.warning("No pain points available")
                return None

            # Sort by priority (severity + WTP) - defensive null coalescing
            sorted_pps = self.accessor.get_sorted_pain_points()

            top_pp = sorted_pps[0]

            # Extract representative quote (use first quote if available)
            representative_quote = "No specific quote available"
            source_platform = "Source platform unknown"

            if top_pp.representative_quotes and len(top_pp.representative_quotes) > 0:
                representative_quote = top_pp.representative_quotes[0]

            # Determine source platform from state
            if self.state.social_content:
                if self.state.social_content.reddit_posts and len(self.state.social_content.reddit_posts) > 0:
                    source_platform = "Reddit"
                    if self.state.social_content.reddit_posts[0].subreddit:
                        source_platform = f"Reddit r/{self.state.social_content.reddit_posts[0].subreddit}"
                elif self.state.social_content.twitter_threads and len(self.state.social_content.twitter_threads) > 0:
                    source_platform = "Twitter"

            return CorePainPoint(
                title=top_pp.title,
                severity_score=top_pp.severity_score,
                willingness_to_pay_score=top_pp.willingness_to_pay,
                representative_quote=representative_quote,
                source_platform=source_platform
            )

        except Exception as e:
            logger.warning(f"Failed to extract core pain point: {e}")
            return None

    def _generate_executive_narrative(
        self,
        selected_solution,
        core_pain_point,
        key_metrics
    ) -> "ExecutiveNarrative | None":
        """
        Generate executive narrative using LLM with structured output.

        Uses the prompt design from prompt-engineering-specialist agent.

        Args:
            selected_solution: SolutionIdea object
            core_pain_point: CorePainPoint object
            key_metrics: KeyMetrics object

        Returns:
            ExecutiveNarrative with tagline, value prop, and verdict rationale
        """
        try:
            from ..models.executive_summary import ExecutiveNarrative

            # Stop condition: Validate required data exists
            if not core_pain_point or not selected_solution:
                raise ValueError("Missing core_pain_point or selected_solution - cannot generate executive narrative")

            # Prepare target personas string
            target_personas_str = ', '.join(selected_solution.target_personas) if selected_solution.target_personas else "target users"

            # Get scores using ScoreAccessor (returns defaults for None values)
            scores = self.score_accessor.get_all_scores(selected_solution)
            market_fit = scores["market_fit"]
            competitive_advantage = scores["competitive_advantage"]
            technical_feasibility = scores["technical_feasibility"]
            seo_growth = scores["seo_growth"]

            # Edge case handling for metrics
            zero_keywords_note = " (Limited keyword data available)" if key_metrics.total_keyword_count == 0 else ""
            zero_competitors_note = " (Emerging market with low competition)" if key_metrics.primary_competitor_count == 0 else ""

            # Load prompt template from YAML
            from ..utils.prompts import load_prompt
            template = load_prompt("report_executive_narrative")
            prompt = template.format(
                solution_name=selected_solution.solution_name,
                solution_description=selected_solution.description,
                target_personas=target_personas_str,
                niche_description=self.state.niche_context.niche_description,
                pain_point_title=core_pain_point.title,
                pain_point_severity=f"{core_pain_point.severity_score:.1f}",
                pain_point_wtp=f"{core_pain_point.willingness_to_pay_score:.1f}",
                market_fit_score=f"{market_fit:.2f}" if market_fit is not None else "N/A",
                competitive_advantage_score=f"{competitive_advantage:.2f}" if competitive_advantage is not None else "N/A",
                technical_feasibility_score=f"{technical_feasibility:.2f}" if technical_feasibility is not None else "N/A",
                seo_growth_score=f"{seo_growth:.2f}" if seo_growth is not None else "N/A",
                total_keyword_count=key_metrics.total_keyword_count,
                tier1_keyword_count=key_metrics.tier1_keyword_count,
                competitor_count=key_metrics.primary_competitor_count,
                high_priority_pain_points=key_metrics.high_priority_pain_points,
                zero_keywords_note=zero_keywords_note,
                zero_competitors_note=zero_competitors_note
            )

            # Use LLMService for structured output
            result = LLMService.invoke_structured(
                prompt=prompt,
                output_model=ExecutiveNarrative,
                temperature=0.5
            )

            # Validate output
            if self._validate_executive_narrative(result, selected_solution, core_pain_point):
                logger.info("[OK] LLM executive narrative generation successful")
                return result
            else:
                raise ValueError("LLM narrative failed validation checks - output does not meet quality standards")

        except Exception as e:
            logger.error(f"LLM narrative generation failed: {e}")
            raise

    def _validate_executive_narrative(
        self,
        narrative,
        selected_solution,
        core_pain_point
    ) -> bool:
        """
        Validate executive narrative for data integrity only.

        Philosophy: Trust the LLM for style, validate only factual accuracy.
        Pydantic already ensures schema compliance (all fields present, correct types).
        The prompt provides clear style guidance - validation enforces data integrity.

        Validates:
        1. Verdict references actual scores (prevents hallucinated analysis)
        2. No temporal claims without data support (flags potential hallucinations)
        3. Basic sanity checks (non-empty fields)

        Does NOT validate (trust the prompt for these):
        - Word counts, sentence counts (style preferences in prompt)
        - Specific vocabulary (LLM understands "active voice" instruction)
        - Character length limits (arbitrary constraints)
        - Solution name substring matching (prompt already requires this)
        """
        import re

        try:
            # ===== VALIDATION 1: Verdict Must Reference Scores =====
            # Purpose: Ensure LLM discusses actual metrics, not invented analysis
            verdict_lower = narrative.verdict_rationale.lower()

            score_keywords = [
                "market fit", "competitive", "feasibility", "seo", "score"
            ]

            # Phase 2.1: Use word boundaries to prevent false positives (e.g., "score" in "underscore")
            score_patterns = [
                r'\bmarket\s+fit\b',
                r'\bcompetitive\b',
                r'\bfeasibility\b',
                r'\bseo\b',
                r'\bscore\b'
            ]

            # Check for either keyword mentions OR numeric score format
            has_score_keyword = any(
                re.search(pattern, verdict_lower, re.IGNORECASE)
                for pattern in score_patterns
            )
            has_numeric_score = bool(re.search(r'\b[01]\.\d{2}\b', narrative.verdict_rationale))

            if not (has_score_keyword or has_numeric_score):
                logger.warning(
                    "Verdict does not reference specific scores or criteria. "
                    "This may indicate hallucinated analysis rather than data-driven rationale."
                )
                return False

            # ===== VALIDATION 2: Temporal Claim Detection (Soft Warning) =====
            # Purpose: Flag potential hallucinations about market trends/timing
            time_words = ['recent', 'recently', 'growing', 'trending', 'emerging', 'latest']
            all_text = (
                f"{narrative.tagline} {narrative.core_value_prop} "
                f"{narrative.verdict_rationale}"
            ).lower()

            found_time_refs = [word for word in time_words if word in all_text]
            if found_time_refs:
                logger.warning(
                    f"Temporal references detected: {found_time_refs}. "
                    f"Verify these claims are based on provided data, not hallucinated trends."
                )
                # Don't fail - "emerging market" may be legitimate based on data

            # ===== VALIDATION 3: Basic Sanity Checks =====
            # Purpose: Catch edge cases where Pydantic might allow empty strings
            if not all([
                narrative.tagline.strip(),
                narrative.core_value_prop.strip(),
                narrative.verdict_rationale.strip()
            ]):
                logger.warning("One or more fields are empty or whitespace-only")
                return False

            logger.debug("Executive narrative passed all validation checks")
            return True

        except Exception as e:
            logger.warning(f"Narrative validation error: {e}")
            return False

    def _compute_go_no_go_verdict(
        self,
        selected_solution,
        narrative_rationale: str | None = None
    ) -> "GoNoGoVerdict":
        """
        Compute go/no-go verdict based on selection criteria scores (Python-only).

        Uses score thresholds to determine verdict automatically.

        Args:
            selected_solution: SolutionIdea object
            narrative_rationale: Optional LLM-generated rationale (if None, use template)

        Returns:
            GoNoGoVerdict with verdict, rationale, and risk level
        """
        from ..models.executive_summary import GoNoGoVerdict

        # Get scores using ScoreAccessor with fallbacks
        market_fit = self.score_accessor.get_market_fit(selected_solution)
        competitive_adv = self.score_accessor.get_competitive_advantage(selected_solution)
        tech_feasibility = self.score_accessor.get_technical_feasibility(selected_solution)
        seo_potential = self.score_accessor.get_seo_growth(selected_solution)

        # Validate scores are not None before calculations (Phase 1.2: None/NaN validation)
        scores = [market_fit, competitive_adv, tech_feasibility, seo_potential]
        if any(score is None for score in scores):
            logger.warning(
                f"[Verdict Calculation] One or more scores are None - using ScoreAccessor defaults. "
                f"Scores: market_fit={market_fit}, competitive_adv={competitive_adv}, "
                f"tech_feasibility={tech_feasibility}, seo_potential={seo_potential}"
            )

        # Compute verdict
        avg_score = (market_fit + competitive_adv + tech_feasibility + seo_potential) / 4

        # Phase 1.1: Use settings thresholds instead of hard-coded values
        if (avg_score >= settings.verdict_go_avg_score and
            min(market_fit, tech_feasibility) >= settings.verdict_go_min_individual_score):
            verdict = "Go"
            risk_level = "Low"
            primary_concern = None
        elif (avg_score >= settings.verdict_conditional_avg_score and
              min(market_fit, tech_feasibility) >= settings.verdict_conditional_min_individual_score):
            verdict = "Conditional"
            risk_level = "Medium"
            primary_concern = "Monitor market validation closely during MVP phase"
        else:
            verdict = "No-Go"
            risk_level = "High"
            if market_fit < 0.6:
                primary_concern = f"Low market fit score ({market_fit:.2f}) indicates weak product-market alignment"
            elif tech_feasibility < 0.6:
                primary_concern = f"Low technical feasibility ({tech_feasibility:.2f}) indicates implementation challenges"
            else:
                primary_concern = "Overall scores below confidence threshold for recommended pursuit"

        # Use LLM rationale if available, otherwise template
        if narrative_rationale:
            rationale = narrative_rationale
        else:
            if verdict == "Go":
                rationale = f"Strong scores across all criteria (avg {avg_score:.2f}). Market fit ({market_fit:.2f}) and competitive advantage ({competitive_adv:.2f}) indicate solid opportunity."
            elif verdict == "Conditional":
                rationale = f"Acceptable scores (avg {avg_score:.2f}) but requires validation. Proceed with MVP to test assumptions."
            else:
                rationale = f"Scores below threshold (avg {avg_score:.2f}). {primary_concern}"

        return GoNoGoVerdict(
            verdict=verdict,
            rationale=rationale,
            risk_level=risk_level,
            primary_concern=primary_concern
        )

    # ==================================================================================
    # Go-to-Market Blueprint Generator (Phase 2 Enhancement)
    # ==================================================================================

    def _generate_gtm_blueprint(self) -> "GTMBlueprint | None":
        """
        Generate Go-to-Market blueprint for immediate execution.

        Uses hybrid approach:
        - 70% Python: ICP extraction, channel identification, playbook generation
        - 30% LLM: Marketing message, message framework, content angles

        Returns:
            GTMBlueprint with ICP, channels, messaging, content, and 30-day plan
        """
        try:
            from ..models.marketing_blueprint import GTMBlueprint

            # Step 1: Extract ICP from user segments (Python - 30%)
            icp = self._extract_ideal_customer_profile()
            if not icp:
                logger.warning("Failed to extract ICP - cannot generate GTM blueprint")
                return None

            # Step 2: Identify marketing channels from evidence (Python - 20%)
            channels = self._identify_marketing_channels()
            if not channels or len(channels) == 0:
                logger.warning("No marketing channels identified")
                channels = []  # Continue with empty list

            # Step 3: Generate marketing narrative (LLM - 30%)
            try:
                narrative = self._generate_marketing_narrative(icp=icp)
            except Exception as e:
                logger.warning(f"Failed to generate marketing narrative: {e}, using fallback")
                # Inline fallback: construct simple narrative from ICP
                from ..models.marketing_blueprint import MarketingNarrative
                narrative = MarketingNarrative(
                    core_marketing_message=f"Solve {icp.pain_points[0]} for {icp.persona_name}" if icp.pain_points else f"Solution for {icp.persona_name}",
                    message_framework="Problem-Solution messaging framework",
                    content_angles=[f"How to solve: {pp}" for pp in icp.pain_points[:3]] if icp.pain_points else ["Educational content", "Case studies", "Practical guides"]
                )

            # Step 4: Generate 30-day playbook (LLM - 20%)
            selected_solution = self.accessor.get_selected_solution_details()
            if not selected_solution:
                logger.warning("No selected solution found - cannot generate 30-day playbook")
                return None
            playbook = self._generate_first_30_days_playbook(
                channels=channels,
                icp=icp,
                selected_solution=selected_solution
            )

            gtm_blueprint = GTMBlueprint(
                ideal_customer_profile=icp,
                core_marketing_message=narrative.core_marketing_message,
                message_framework=narrative.message_framework,
                recommended_channels=channels[:3],  # Top 3 channels
                example_content_angles=narrative.content_angles[:5],  # Top 5 angles
                first_30_days_playbook=playbook,
                budget_estimate="$500-1500/month (first 3 months: content creation + modest paid promotion)" if channels else None
            )

            logger.info(f"[OK] GTM blueprint generated: {len(channels)} channels, {len(narrative.content_angles)} content angles")
            return gtm_blueprint

        except Exception as e:
            logger.warning(f"Failed to generate GTM blueprint: {e}")
            return None

    def _extract_ideal_customer_profile(self) -> "IdealCustomerProfile | None":
        """
        Extract ICP from content categorization and pain points (Python-only).

        Returns:
            IdealCustomerProfile with persona details
        """
        try:
            from ..models.marketing_blueprint import IdealCustomerProfile

            # Extract from content_categorization if available
            if not self.state.pain_point_analysis or not self.state.pain_point_analysis.content_categorization:
                logger.warning("No content categorization available for ICP")
                return None

            categorization = self.state.pain_point_analysis.content_categorization

            # Use first user segment as primary persona
            if not categorization.user_segments or len(categorization.user_segments) == 0:
                logger.warning("No user segments available")
                return None

            primary_segment = categorization.user_segments[0]

            # Extract top pain points
            pain_points = []
            sorted_pps = self.accessor.get_sorted_pain_points()
            if sorted_pps:
                pain_points = [pp.title for pp in sorted_pps[:5]]

            # Extract goals from solution context
            goals = []
            selected_solution = self.accessor.get_selected_solution_details()
            if selected_solution and selected_solution.core_features:
                # Infer goals from core features
                goals = [f"Achieve {feature.lower()}" for feature in selected_solution.core_features[:5]]

            if not goals:
                goals = ["Customer goals not identified - conduct user research"]

            # Build psychographics with specific data or explicit message
            if pain_points:
                psychographics = f"Motivated by solving {pain_points[0]}. Psychographic profile requires user research."
            else:
                psychographics = "Psychographic profile requires user research"

            return IdealCustomerProfile(
                persona_name=primary_segment.segment_name,
                demographics=f"{primary_segment.segment_name} segment with {primary_segment.mention_frequency.lower()} activity in {self.state.niche_context.niche_description} discussions",
                psychographics=psychographics,
                pain_points=pain_points if pain_points else ["No specific pain points identified"],
                goals=goals,
                buying_triggers=f"Experiencing {pain_points[0].lower() if pain_points else 'challenges'} that impact daily operations",
                decision_criteria="Decision criteria not identified - requires customer interviews"
            )

        except Exception as e:
            logger.warning(f"Failed to extract ICP: {e}")
            return None

    def _identify_reddit_channel(self) -> "MarketingChannel | None":
        """
        Identify Reddit marketing channel from evidence.

        Returns:
            MarketingChannel for Reddit or None if no evidence
        """
        from ..models.marketing_blueprint import MarketingChannel

        if not self.state.social_content or not self.state.social_content.reddit_posts:
            return None

        subreddit_counts = self.accessor.get_subreddit_breakdown()
        if not subreddit_counts:
            return None

        top_subreddit = max(subreddit_counts, key=subreddit_counts.get)
        post_count = subreddit_counts[top_subreddit]

        return MarketingChannel(
            channel_name=f"Reddit r/{top_subreddit}",
            channel_type="Community",
            target_audience_size=f"{post_count} relevant discussions found",
            rationale=f"Found {post_count} highly relevant discussions in r/{top_subreddit} during research. This subreddit shows active engagement with target pain points.",
            strategy="Share valuable insights and case studies. Participate authentically in discussions. Avoid direct promotion - focus on helping users solve problems.",
            priority="High"
        )

    def _identify_seo_channel(self) -> "MarketingChannel | None":
        """
        Identify SEO/Content marketing channel from keyword data.

        Returns:
            MarketingChannel for SEO or None if no keyword data
        """
        from ..models.marketing_blueprint import MarketingChannel

        if not self.state.seo_strategy_report or not self.state.seo_strategy_report.tier_1_keywords:
            return None

        tier1_count = len(self.state.seo_strategy_report.tier_1_keywords)
        total_volume = sum(kw.search_volume for kw in self.state.seo_strategy_report.tier_1_keywords)

        return MarketingChannel(
            channel_name="SEO Blog / Content Marketing",
            channel_type="SEO",
            target_audience_size=f"{total_volume:,} monthly searches across {tier1_count} Tier 1 keywords",
            rationale=f"Identified {tier1_count} high-opportunity keywords with {total_volume:,} monthly search volume. Low competition allows for quick ranking wins.",
            strategy="Create comprehensive guides targeting Tier 1 keywords. Focus on solving specific pain points. Use schema markup for featured snippets. Build internal linking structure.",
            priority="High"
        )

    def _identify_twitter_channel(self) -> "MarketingChannel | None":
        """
        Identify Twitter marketing channel from evidence.

        Returns:
            MarketingChannel for Twitter or None if no evidence
        """
        from ..models.marketing_blueprint import MarketingChannel

        if not self.state.social_content or not self.state.social_content.twitter_threads:
            return None

        thread_count = len(self.state.social_content.twitter_threads)

        return MarketingChannel(
            channel_name="Twitter / X",
            channel_type="Social",
            target_audience_size=f"{thread_count} relevant conversations found",
            rationale=f"Found {thread_count} active discussions on Twitter about target pain points. Platform shows engaged community discussing solutions.",
            strategy="Share problem-solving threads. Engage with pain point discussions. Build in public. Use relevant hashtags. Focus on education over promotion.",
            priority="Medium"
        )

    def _identify_marketing_channels(self) -> list["MarketingChannel"]:
        """
        Identify top marketing channels from evidence (Python-only).

        Returns:
            List of MarketingChannel objects prioritized by evidence
        """
        try:
            channels = []

            # Try to identify each channel type
            reddit_channel = self._identify_reddit_channel()
            if reddit_channel:
                channels.append(reddit_channel)

            seo_channel = self._identify_seo_channel()
            if seo_channel:
                channels.append(seo_channel)

            twitter_channel = self._identify_twitter_channel()
            if twitter_channel:
                channels.append(twitter_channel)

            return channels

        except Exception as e:
            logger.warning(f"Failed to identify marketing channels: {e}")
            return []

    def _generate_marketing_narrative(self, icp) -> "MarketingNarrative | None":
        """
        Generate marketing narrative using LLM (message + content angles).

        Args:
            icp: IdealCustomerProfile object

        Returns:
            MarketingNarrative with messaging and content ideas
        """
        try:
            from ..models.marketing_blueprint import MarketingNarrative

            # Get top pain points
            top_pain_points = icp.pain_points[:3] if icp.pain_points else []

            # Stop condition: Insufficient pain points
            if not icp.pain_points or len(icp.pain_points) < 2:
                pain_count = len(icp.pain_points) if icp.pain_points else 0
                raise ValueError(
                    f"Insufficient pain points ({pain_count}) for marketing narrative - need at least 2"
                )

            # Get solution context
            selected_solution_name = "the solution"
            solution_description = ""
            selected_solution = self.accessor.get_selected_solution_details()
            if selected_solution:
                selected_solution_name = selected_solution.solution_name
                solution_description = selected_solution.description

            # Load prompt template from YAML
            from ..utils.prompts import load_prompt
            template = load_prompt("report_marketing_narrative")

            # Format pain points and goals as lists
            pain_points_list = '\n'.join(f"- {pp}" for pp in top_pain_points)
            goals_list = '\n'.join(f"- {goal}" for goal in icp.goals[:3])
            max_content_angles = min(len(top_pain_points), 5)

            prompt = template.format(
                solution_name=selected_solution_name,
                solution_description=solution_description,
                niche_description=self.state.niche_context.niche_description,
                persona_name=icp.persona_name,
                pain_points_list=pain_points_list,
                goals_list=goals_list,
                max_content_angles=max_content_angles
            )

            # Use LLMService for structured output
            result = LLMService.invoke_structured(
                prompt=prompt,
                output_model=MarketingNarrative,
                temperature=0.6
            )
            logger.info("[OK] LLM marketing narrative generation successful")
            return result

        except Exception as e:
            logger.error(f"LLM marketing narrative generation failed: {e}")
            raise

    def _generate_first_30_days_playbook(self, channels: list, icp: "IdealCustomerProfile", selected_solution: "SolutionIdea") -> "First30DaysPlaybook":
        """
        Generate 30-day action plan using LLM with solution-specific pain points.

        Args:
            channels: List of MarketingChannel objects
            icp: Ideal customer profile
            selected_solution: Selected solution with pain_points_addressed

        Returns:
            First30DaysPlaybook with week-by-week actions
        """
        from ..models.marketing_blueprint import First30DaysPlaybook
        from ..utils.prompts import load_prompt
        from .utils.prompt_formatters import (
            format_pain_points_for_prompt,
            format_channels_for_prompt,
            format_icp_for_prompt
        )

        # Get top research-discovered pain points (not solution assumptions)
        top_pain_points = self.accessor.get_sorted_pain_points()[:3]

        # Format data for prompt
        pain_points_list = format_pain_points_for_prompt(top_pain_points)
        channels_summary = format_channels_for_prompt(channels)
        icp_summary = format_icp_for_prompt(icp)

        # Get keyword and competitive data
        total_keyword_count = 0
        tier0_keyword_count = 0
        tier1_keyword_count = 0
        if self.state.seo_strategy_report:
            total_keyword_count = self.state.seo_strategy_report.total_keywords_analyzed or 0
            tier0_keyword_count = len(self.state.seo_strategy_report.tier_0_keywords) if self.state.seo_strategy_report.tier_0_keywords else 0
            tier1_keyword_count = len(self.state.seo_strategy_report.tier_1_keywords) if self.state.seo_strategy_report.tier_1_keywords else 0

        competitor_count = 0
        if self.state.competitive_analysis:
            competitor_count = len(self.state.competitive_analysis.solution_landscapes)

        # Load template and generate prompt
        template = load_prompt("report_first_30_days_playbook")
        prompt = template.format(
            solution_name=selected_solution.solution_name,
            solution_description=selected_solution.description,
            value_proposition=selected_solution.value_proposition,
            technical_approach=selected_solution.technical_approach or "Technical approach not specified",
            project_type=selected_solution.project_type or "Project type not specified",
            estimated_development_time=selected_solution.estimated_development_time or "Development timeline not estimated",
            niche=self.state.niche_context.niche_description,
            top_pain_points_list=pain_points_list,
            icp_summary=icp_summary,
            channels_summary=channels_summary,
            total_keyword_count=total_keyword_count,
            tier0_keyword_count=tier0_keyword_count,
            tier1_keyword_count=tier1_keyword_count,
            competitor_count=competitor_count
        )

        # Use LLMService for structured output
        try:
            playbook = LLMService.invoke_structured(
                prompt=prompt,
                output_model=First30DaysPlaybook,
                temperature=0.6
            )
            logger.info("Successfully generated 30-day playbook via LLM")
            return playbook
        except Exception as e:
            logger.error(f"Failed to generate 30-day playbook: {e}")
            raise

    # ==================================================================================
    # Analytics & Visualization Generator (Phase 3 Enhancement)
    # ==================================================================================

    def _generate_analytics_and_visualizations(self) -> tuple["MarketAnalytics | None", "SEOAnalytics | None", "CompetitiveAnalytics | None", "PainPointAnalytics | None", "VisualizationManifest | None"]:
        """
        Generate all analytics and visualizations (Python-only, no LLM).

        Returns:
            Tuple of (market_analytics, seo_analytics, competitive_analytics, pain_point_analytics, visualization_manifest)
        """

        # Compute analytics
        market_analytics = self._compute_market_analytics()
        seo_analytics = self._compute_seo_analytics()
        competitive_analytics = self._compute_competitive_analytics()
        pain_point_analytics = self._compute_pain_point_analytics()

        # Generate visualizations
        viz_manifest = self._generate_visualizations()

        return (market_analytics, seo_analytics, competitive_analytics, pain_point_analytics, viz_manifest)

    def _compute_market_analytics(self) -> "MarketAnalytics | None":
        """Compute market opportunity analytics (Python-only)."""
        try:
            from ..models.analytics import MarketAnalytics

            selected_solution = self.accessor.get_selected_solution_details()
            if not selected_solution:
                return None

            # Compute overall opportunity score using ScoreAccessor
            overall_score = (
                self.score_accessor.get_market_fit(selected_solution) +
                self.score_accessor.get_competitive_advantage(selected_solution) +
                self.score_accessor.get_technical_feasibility(selected_solution) +
                self.score_accessor.get_seo_growth(selected_solution)
            ) / 4

            # Market size from keyword volume
            market_size_category = "Small"
            if self.state.seo_strategy_report:
                total_volume = sum(kw.search_volume for kw in self.state.seo_strategy_report.tier_1_keywords)
                if total_volume > 10000:
                    market_size_category = "Large"
                elif total_volume > 1000:
                    market_size_category = "Medium"

            # Competitive intensity
            competitor_count = self.accessor.get_competitor_count()

            competitive_intensity = (
                "Low" if competitor_count < settings.competitive_intensity_low_threshold
                else "Medium" if competitor_count < settings.competitive_intensity_high_threshold
                else "High"
            )

            # Recommendation
            if overall_score >= 0.75:
                recommendation = "Go"
            elif overall_score >= 0.60:
                recommendation = "Conditional"
            else:
                recommendation = "No-Go"

            # Calculate selection confidence using ScoreAccessor
            selection_confidence = self.score_accessor.get_confidence_score(selected_solution)

            return MarketAnalytics(
                overall_opportunity_score=overall_score,
                market_size_category=market_size_category,
                selection_confidence=selection_confidence,
                competitive_intensity=competitive_intensity,
                recommendation=recommendation
            )

        except Exception as e:
            logger.warning(f"Failed to compute market analytics: {e}")
            return None

    def _compute_seo_analytics(self) -> "SEOAnalytics | None":
        """Compute SEO keyword analytics (Python-only)."""
        try:
            from ..models.analytics import SEOAnalytics

            if not self.state.seo_strategy_report:
                return None

            # Get tier counts using accessor
            counts = self.accessor.get_tier_keyword_counts()
            total = counts["total"]
            total_volume = self.accessor.get_total_keyword_search_volume()

            tier0_count = counts["tier_0"]
            tier1_count = counts["tier_1"]
            tier2_count = counts["tier_2"]
            tier3_count = counts["tier_3"]
            tier4_count = counts["tier_4"]

            # Keyword diversity (0-1): higher if keywords are distributed across tiers
            if total == 0:
                diversity = 0.0  # No keywords = no diversity
            else:
                diversity = 1.0 - (max(tier0_count, tier1_count, tier2_count, tier3_count, tier4_count) / total)

            # High volume keywords (Tier 0, 1 and 2 - premium and quick wins)
            # Direct access to tier keyword lists
            seo = self.state.seo_strategy_report
            tier0_keywords = seo.tier_0_keywords or []
            tier1_keywords = seo.tier_1_keywords or []
            tier2_keywords = seo.tier_2_keywords or []

            high_volume = sum(
                1 for kw in (tier0_keywords + tier1_keywords + tier2_keywords)
                if (kw.search_volume or 0) > 1000
            )

            return SEOAnalytics(
                tier0_count=tier0_count,
                tier1_count=tier1_count,
                tier2_count=tier2_count,
                tier3_count=tier3_count,
                tier4_count=tier4_count,
                total_keywords=total,
                total_search_volume=total_volume,
                keyword_diversity_score=diversity,
                high_volume_keywords=high_volume
            )

        except Exception as e:
            logger.warning(f"Failed to compute SEO analytics: {e}")
            return None

    def _compute_competitive_analytics(self) -> "CompetitiveAnalytics | None":
        """Compute competitive analytics (Python-only)."""
        try:
            from ..models.analytics import CompetitiveAnalytics

            if not self.state.competitive_analysis or not self.state.solution_selection:
                return None

            selected_landscape = self.accessor.get_selected_landscape()
            if not selected_landscape:
                return None

            competitor_count = self.accessor.get_competitor_count()
            market_gaps = len(selected_landscape.market_gaps)

            # Market saturation (0-1)
            saturation = min(competitor_count / 10, 1.0)

            # Differentiation strength
            if market_gaps >= 3:
                differentiation = "Strong"
            elif market_gaps >= 1:
                differentiation = "Moderate"
            else:
                differentiation = "Weak"

            return CompetitiveAnalytics(
                competitor_count=competitor_count,
                market_saturation_score=saturation,
                differentiation_strength=differentiation,
                market_gaps_identified=market_gaps
            )

        except Exception as e:
            logger.warning(f"Failed to compute competitive analytics: {e}")
            return None

    def _compute_pain_point_analytics(self) -> "PainPointAnalytics | None":
        """Compute pain point analytics (Python-only)."""
        try:
            from ..models.analytics import PainPointAnalytics

            if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
                return None

            pain_points = self.state.pain_point_analysis.pain_points
            total = len(pain_points)
            high_priority = sum(1 for pp in pain_points if pp.severity_score >= settings.pain_point_high_priority_threshold)

            # Quadrant distribution
            quadrants = {
                "high_severity_high_wtp": 0,
                "high_severity_low_wtp": 0,
                "low_severity_high_wtp": 0,
                "low_severity_low_wtp": 0
            }

            for pp in pain_points:
                severity_high = pp.severity_score >= 0.5
                wtp_high = pp.willingness_to_pay >= 0.5

                if severity_high and wtp_high:
                    quadrants["high_severity_high_wtp"] += 1
                elif severity_high:
                    quadrants["high_severity_low_wtp"] += 1
                elif wtp_high:
                    quadrants["low_severity_high_wtp"] += 1
                else:
                    quadrants["low_severity_low_wtp"] += 1

            avg_severity = sum(pp.severity_score for pp in pain_points) / total
            avg_wtp = sum(pp.willingness_to_pay for pp in pain_points) / total

            # Top pain point
            sorted_pps = self.accessor.get_sorted_pain_points()
            top_title = sorted_pps[0].title if sorted_pps else "N/A"

            return PainPointAnalytics(
                total_pain_points=total,
                high_priority_count=high_priority,
                quadrant_distribution=quadrants,
                avg_severity=avg_severity,
                avg_willingness_to_pay=avg_wtp,
                top_pain_point_title=top_title
            )

        except Exception as e:
            logger.warning(f"Failed to compute pain point analytics: {e}")
            return None

    def _generate_visualizations(self) -> "VisualizationManifest | None":
        """Generate all chart visualizations (Python-only)."""
        try:
            from datetime import datetime
            from pathlib import Path

            from ..models.analytics import VisualizationManifest
            from ..report.visualizations import ChartGenerator

            # Create output directory
            output_dir = Path("output/visualizations")
            generator = ChartGenerator(output_dir)

            # Generate pain point matrix
            pain_point_paths = None
            if self.state.pain_point_analysis and self.state.pain_point_analysis.pain_points:
                pain_point_paths = generator.generate_pain_point_matrix(
                    self.state.pain_point_analysis.pain_points
                )

            # Generate keyword opportunity chart
            keyword_paths = None
            if self.state.seo_strategy_report:
                # Get tier counts using accessor
                counts = self.accessor.get_tier_keyword_counts()
                tier_counts = {
                    "Tier 0": counts["tier_0"],
                    "Tier 1": counts["tier_1"],
                    "Tier 2": counts["tier_2"],
                    "Tier 3": counts["tier_3"],
                    "Tier 4": counts["tier_4"]
                }
                keyword_paths = generator.generate_keyword_opportunity_chart(tier_counts)

            # Generate competitive landscape
            competitive_paths = None
            selected_landscape = self.accessor.get_selected_landscape()
            if selected_landscape and selected_landscape.competitors:
                competitive_paths = generator.generate_competitive_landscape(
                    selected_landscape.competitors
                )

            return VisualizationManifest(
                pain_point_matrix_path=pain_point_paths[0] if pain_point_paths else None,
                keyword_opportunity_path=keyword_paths[0] if keyword_paths else None,
                competitive_landscape_path=competitive_paths[0] if competitive_paths else None,
                charts_format="png",
                generated_at=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"Failed to generate visualizations: {e}")
            return None

