"""
Stage 10 Report Generation Module

Handles final report generation using a hybrid approach:
- 80% Python data assembly (direct copy + templates)
- 20% LLM strategic synthesis (3 fields only)

Cost: ~$0.02-0.05 per report (vs $0.10-0.30 previously)
Speed: ~2-3 seconds (vs 5-15 seconds previously)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..models.research_state import (
    FinalReport,
    ResearchState,
    ResearchMetadata,
    SubredditBreakdown,
    AlternativeSolution,
    CompetitiveLandscapeMatrix,
    CompetitorMatrixEntry,
    CompetitiveIntensityEntry,
    EvidenceAppendix,
    TopRedditThread,
    PainPointEvidence,
    QuoteSource,
    DataInfrastructureRoadmap,
    DataInfrastructurePhase,
    DecisionFramework,
    DecisionCriterion,
    PivotTrigger,
)
from ..utils.helpers import find_solution_by_name


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
        niche_description: The niche being researched
    """

    def __init__(self, state: ResearchState, niche_description: str):
        """
        Initialize report generator.

        Args:
            state: Complete ResearchState containing all stage results
            niche_description: The niche being analyzed
        """
        self.state = state
        self.niche_description = niche_description

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
        final_report = self._generate_fallback_report()
        logger.info(
            f"[OK] Base report generated: {len(final_report.top_pain_points)} pain points, "
            f"{len(final_report.recommended_solutions)} solutions"
        )

        # Step 2: Enhance with LLM for strategic synthesis
        logger.info("Step 2: Enhancing with LLM for strategic synthesis (optional)...")
        final_report = self._enhance_report_with_llm(final_report)

        # Step 3: Generate enhanced report sections (Python-based data preservation)
        logger.info("Step 3: Generating enhanced report sections (Python)...")

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

        final_report.decision_framework = self._generate_decision_framework()
        if final_report.decision_framework:
            logger.info(
                f"[OK] Decision framework generated: "
                f"{len(final_report.decision_framework.go_criteria)} go criteria, "
                f"{len(final_report.decision_framework.no_go_criteria)} no-go criteria, "
                f"{len(final_report.decision_framework.pivot_triggers)} pivot triggers"
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

    def _generate_fallback_report(self) -> FinalReport:
        """
        Generate production-quality FinalReport using Python data assembly (no LLM).

        This method creates a complete report by directly copying and formatting data
        from all previous stages. Can be used standalone or enhanced with LLM for
        strategic synthesis fields.
        """
        from datetime import datetime

        # Extract ALL pain points sorted by priority (severity + WTP)
        top_pain_points = []
        pain_points_summary = "No pain point analysis available."
        if self.state.pain_point_analysis:
            sorted_pps = sorted(
                self.state.pain_point_analysis.pain_points,
                key=lambda x: (x.severity_score + x.willingness_to_pay) / 2,
                reverse=True,
            )
            # Include ALL pain points with severity/WTP scores (no arbitrary limit)
            top_pain_points = [
                f"{pp.title} - {pp.description} (Severity: {pp.severity_score:.1f}/10, WTP: {pp.willingness_to_pay:.1f}/10)"
                for pp in sorted_pps
            ]
            # Use existing analysis_summary from Stage 6
            pain_points_summary = self.state.pain_point_analysis.analysis_summary

        # Extract ALL recommended solutions (no limit)
        recommended_solutions = []
        solutions_summary = "No solution ideas generated."
        if self.state.idea_generation:
            # Put selected solution first, then others
            all_solutions = [sol.solution_name for sol in self.state.idea_generation.solution_ideas]
            if self.state.solution_selection:
                selected_name = self.state.solution_selection.selected_solution_name
                if selected_name in all_solutions:
                    all_solutions.remove(selected_name)
                    all_solutions.insert(0, selected_name)
            recommended_solutions = all_solutions
            # Use existing market_insights from Stage 7
            solutions_summary = self.state.idea_generation.market_insights

        # Extract competitive summary (use existing strategic_recommendations)
        competitive_summary = "No competitive analysis available."
        if self.state.competitive_analysis:
            # Use existing strategic_recommendations from Stage 8
            competitive_summary = self.state.competitive_analysis.strategic_recommendations

        # Extract solution selection (Stage 8.5)
        selected_solution_name = "No solution selected"
        selection_rationale = "Solution selection was not completed. Review recommended solutions and perform manual selection."
        runner_up_solutions = []
        selection_criteria_scores = []  # Must be list, not dict
        recommended_focus = "To be determined after solution selection"

        if self.state.solution_selection:
            selected_solution_name = self.state.solution_selection.selected_solution_name
            selection_rationale = self.state.solution_selection.selection_rationale
            runner_up_solutions = self.state.solution_selection.runner_up_solutions
            selection_criteria_scores = self.state.solution_selection.selection_criteria_scores
            recommended_focus = self.state.solution_selection.recommended_focus

        # Find selected solution details using fuzzy match helper
        selected_solution_details = None
        if self.state.solution_selection and self.state.idea_generation:
            selected_solution_details = find_solution_by_name(
                self.state.solution_selection.selected_solution_name,
                self.state.idea_generation.solution_ideas
            )

        # Generate solution_user_journey from features
        solution_user_journey = None
        if selected_solution_details and selected_solution_details.core_features:
            steps = [f"{i}. {feature}" for i, feature in enumerate(selected_solution_details.core_features, 1)]
            solution_user_journey = f"## User Journey\n\n" + "\n".join(steps)

        # Generate solution_implementation_overview template
        solution_implementation_overview = None
        if selected_solution_details:
            dev_time = selected_solution_details.estimated_development_time or "3-6 months"
            tech = selected_solution_details.technical_approach or "modern web technologies"
            solution_implementation_overview = f"""## Implementation Overview

**Phase 1: MVP Development** ({dev_time})
Build core functionality using {tech}. Focus on delivering essential features.

**Phase 2: Enhancement & Scaling**
Add advanced features, optimize performance, implement user feedback.

**Phase 3: Market Expansion**
Expand to new markets or segments based on validated learnings."""

        # Generate mvp_scope_definition template
        mvp_scope_definition = None
        if selected_solution_details and selected_solution_details.core_features:
            must_have = selected_solution_details.core_features[:4]
            post_mvp = selected_solution_details.core_features[4:]

            mvp_text = "## MVP Scope\n\n### Must-Have Features\n"
            mvp_text += "\n".join([f"- {f}" for f in must_have])
            if post_mvp:
                mvp_text += "\n\n### Post-MVP Features\n"
                mvp_text += "\n".join([f"- {f}" for f in post_mvp])
            mvp_text += "\n\n### Success Criteria\n"
            mvp_text += "- 100+ active users within 3 months\n- 60%+ weekly active users\n- First paying customer within 6 months"
            mvp_scope_definition = mvp_text

        # Generate acquisition_strategy_summary template
        acquisition_strategy_summary = None
        if selected_solution_details:
            page_count = selected_solution_details.estimated_indexable_pages or 1000
            acquisition_strategy_summary = f"""## Customer Acquisition Strategy

**Content Generation Model:** The solution architecture enables programmatic generation of {page_count:,}+ indexable pages through {selected_solution_details.project_type or 'directory'} functionality.

**Discovery Patterns:** Users will discover the platform through organic search queries targeting {selected_solution_details.value_proposition}.

**Scaling Strategy:** Each data entity creates a unique landing page, enabling exponential growth in organic traffic as the database expands."""

        # Generate estimated_cac_breakdown template
        estimated_cac_breakdown = None
        if selected_solution_details:
            cac_organic = selected_solution_details.estimated_cac_organic or "N/A"
            cac_paid = selected_solution_details.estimated_cac_paid or "N/A"
            scalability = selected_solution_details.seo_scalability_score or 0.7

            estimated_cac_breakdown = f"""## CAC Breakdown

| Channel | Estimated CAC | Rationale |
|---------|--------------|-----------|
| Organic (SEO) | {cac_organic} | Programmatic content via {selected_solution_details.estimated_indexable_pages or 1000}+ pages |
| Paid (SEM) | {cac_paid} | Industry benchmark for paid acquisition |

**SEO Scalability:** {scalability:.1f}/10 - {"Excellent" if scalability >= 0.8 else "Good" if scalability >= 0.6 else "Moderate"} organic growth potential.

**CAC Advantage:** Organic acquisition through programmatic SEO significantly reduces customer acquisition costs compared to paid channels."""

        # Generate market_validation based on actual metrics
        total_volume = self.state.keyword_validation.overall_market_size if self.state.keyword_validation else 0
        pain_point_count = len(self.state.pain_point_analysis.pain_points) if self.state.pain_point_analysis else 0

        if total_volume > 100_000 and pain_point_count >= 10:
            validation_level = "STRONG"
        elif total_volume > 30_000 and pain_point_count >= 5:
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
            recs = [f"## Data Sourcing Strategy\n"]
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
            niche=self.niche_description,
            executive_summary=f"Market research completed for {self.niche_description}. "
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

    def _enhance_report_with_llm(self, base_report: FinalReport) -> FinalReport:
        """
        Enhance Python-generated report with LLM for 3 strategic synthesis fields only.

        Takes a complete report from _generate_fallback_report() and uses LLM to generate:
        1. executive_summary (4-6 sentence strategic synthesis)
        2. acquisition_strategy_summary (2-3 paragraph SEO strategy narrative)
        3. next_steps (5-8 prioritized action items)

        All other fields are preserved from base_report.
        """
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field

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

        # Build minimal context prompt (~50 lines vs 245 lines)
        prompt = f"""You are a strategic market research analyst creating final synthesis for a comprehensive market research report.

**Research Context:**
Niche: {base_report.niche}
Selected Solution: {base_report.selected_solution_name}
Pain Points Identified: {len(base_report.top_pain_points)}
Market Validation: {base_report.market_validation}
SEO Scalability: {base_report.selected_solution_details.seo_scalability_score if base_report.selected_solution_details else 'N/A'}/10

**Your Task:**
Generate ONLY these 3 strategic synthesis fields:

1. **executive_summary** (4-6 sentences):
   - Compelling narrative synthesizing the entire research
   - Highlight the selected solution and selection rationale
   - Key market opportunity and recommended direction

2. **acquisition_strategy_summary** (2-3 paragraphs):
   - Explain HOW the product architecture creates indexable pages
   - What search queries users will use to discover the solution
   - How organic acquisition will scale (programmatic SEO approach)

3. **next_steps** (5-8 action items):
   - Concrete, prioritized, sequenced actions
   - Include validation, MVP development, SEO implementation
   - Be specific and actionable

**Key Data for Context:**
- Selection Rationale: {base_report.selection_rationale}
- Top 3 Pain Points: {', '.join(base_report.top_pain_points[:3])}
- Project Type: {base_report.selected_solution_details.project_type if base_report.selected_solution_details else 'N/A'}
- Indexable Pages: {base_report.selected_solution_details.estimated_indexable_pages if base_report.selected_solution_details else 'N/A'}
- CAC Organic: ${base_report.selected_solution_details.estimated_cac_organic if base_report.selected_solution_details else 'N/A'}

Return JSON with these 3 fields only."""

        try:
            logger.info("Enhancing report with LLM for strategic synthesis (3 fields)...")

            # Use minimal LLM call for 3 fields (GPT-4o, temp 0.7 for strategic creativity)
            structured_llm = ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.7,
                api_key=settings.openai_api_key
            ).with_structured_output(StrategicSynthesis)

            synthesis = structured_llm.invoke(prompt)

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

    def _generate_research_metadata(self) -> Optional["ResearchMetadata"]:
        """
        Generate research metadata section with social content collection statistics.

        Returns:
            ResearchMetadata object with Reddit/Twitter stats, subreddit breakdown, and collection info
        """
        if not self.state.social_content:
            return None

        try:
            # Count Reddit posts and comments
            reddit_posts_analyzed = len(self.state.social_content.reddit_posts)
            reddit_comments_analyzed = sum(len(post.comments) for post in self.state.social_content.reddit_posts)

            # Count Twitter threads
            twitter_threads_analyzed = len(self.state.social_content.twitter_threads)

            # Calculate subreddit breakdown (top 10)
            subreddit_counts: Dict[str, int] = {}
            for post in self.state.social_content.reddit_posts:
                subreddit_counts[post.subreddit] = subreddit_counts.get(post.subreddit, 0) + 1

            top_subreddits = [
                SubredditBreakdown(name=name, post_count=count)
                for name, count in sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]

            # Calculate data size (rough estimate from JSON serialization)
            social_content_json = self.state.social_content.model_dump_json()
            data_size_mb = len(social_content_json.encode('utf-8')) / (1024 * 1024)

            return ResearchMetadata(
                reddit_posts_analyzed=reddit_posts_analyzed,
                reddit_comments_analyzed=reddit_comments_analyzed,
                twitter_threads_analyzed=twitter_threads_analyzed,
                top_subreddits=top_subreddits,
                collection_date=self.state.social_content.collection_timestamp,
                data_size_mb=round(data_size_mb, 2)
            )
        except Exception as e:
            logger.warning(f"Failed to generate research metadata: {e}")
            return None

    def _generate_alternative_solutions(self) -> Optional[List["AlternativeSolution"]]:
        """
        Generate alternative solution summaries for runner-up solutions.

        Returns:
            List of AlternativeSolution objects (top 2 runner-ups with full details)
        """
        if not self.state.solution_selection or not self.state.idea_generation:
            return None

        try:
            # Get runner-up solution names
            runner_up_names = self.state.solution_selection.runner_up_solutions or []
            if not runner_up_names:
                return None

            # Find full solution details from idea_generation stage
            all_solutions = {idea.solution_name: idea for idea in self.state.idea_generation.solution_ideas}

            # Build score lookup map from all_solution_scores
            score_map = {}
            if self.state.solution_selection.all_solution_scores:
                score_map = {
                    scores.solution_name: scores
                    for scores in self.state.solution_selection.all_solution_scores
                }

            alternative_solutions = []
            for runner_up_name in runner_up_names[:2]:  # Top 2 runners-up
                if runner_up_name not in all_solutions:
                    logger.warning(f"Runner-up solution '{runner_up_name}' not found in idea generation results")
                    continue

                solution = all_solutions[runner_up_name]

                # Get scores from all_solution_scores if available
                scores = score_map.get(runner_up_name)

                # Generate 2-3 paragraph summary
                summary = f"""**Overview:** {solution.description}

**Key Features:** {', '.join(solution.core_features[:5])}

**Target Users:** This solution is best suited for {', '.join(solution.target_personas[:2])}.
It differentiates through {solution.differentiation_factors[0] if solution.differentiation_factors else 'unique positioning'}.

**Technical Approach:** {solution.technical_approach}
"""

                # Use scores from SolutionSelection if available, otherwise fall back to solution fields
                if scores:
                    market_fit = scores.market_fit_score
                    technical_feasibility = scores.technical_feasibility_score
                    competitive_advantage = scores.competitive_advantage_score
                    seo_growth = scores.seo_growth_potential_score
                else:
                    # Fallback to solution fields if all_solution_scores not populated
                    market_fit = solution.market_fit_score or 0.0
                    technical_feasibility = solution.technical_feasibility_score or 0.0
                    competitive_advantage = solution.market_fit_score or 0.7  # Use market_fit as proxy
                    seo_growth = solution.seo_scalability_score or 0.0

                # Determine pivot trigger based on solution characteristics
                pivot_trigger = f"Pivot to {runner_up_name} if: "
                if market_fit > 0.9:
                    pivot_trigger += "user research reveals significantly higher demand for this specific pain point, "
                if seo_growth > 0.85:
                    pivot_trigger += "SEO keyword volume for this solution is 2x higher than primary choice, "
                if technical_feasibility > 0.9:
                    pivot_trigger += "faster time-to-market is critical and this solution has simpler tech requirements"

                alternative_solutions.append(AlternativeSolution(
                    solution_name=solution.solution_name,
                    summary=summary.strip(),
                    market_fit_score=market_fit,
                    technical_feasibility_score=technical_feasibility,
                    competitive_advantage_score=competitive_advantage,
                    seo_growth_potential_score=seo_growth,
                    key_differentiator=solution.differentiation_factors[0] if solution.differentiation_factors else "Unique market positioning",
                    best_suited_for=solution.target_personas[0] if solution.target_personas else "Target user segment",
                    pivot_trigger=pivot_trigger.rstrip(", ")
                ))

            return alternative_solutions if alternative_solutions else None
        except Exception as e:
            logger.warning(f"Failed to generate alternative solutions: {e}")
            return None

    def _generate_competitive_landscape_matrix(self) -> Optional["CompetitiveLandscapeMatrix"]:
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
            competitor_appearances: Dict[str, Dict[str, Any]] = {}
            competitive_intensity_list: List[CompetitiveIntensityEntry] = []

            for landscape in self.state.competitive_analysis.solution_landscapes:
                # Track competitive intensity
                competitive_intensity_list.append(
                    CompetitiveIntensityEntry(
                        solution_name=landscape.solution_name,
                        intensity=landscape.competitive_intensity
                    )
                )

                # Track competitor appearances
                for competitor in landscape.competitors:
                    if competitor.name not in competitor_appearances:
                        competitor_appearances[competitor.name] = {
                            "solutions": [],
                            "type": competitor.competitor_type,
                            "threat_level": "medium"  # default
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

    def _generate_evidence_appendix(self) -> Optional["EvidenceAppendix"]:
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
            post_metadata: Dict[str, Dict[str, Any]] = {}
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
                # Match quotes to source posts using source_post_ids if available
                source_ids = pain_point.source_post_ids if hasattr(pain_point, 'source_post_ids') else []

                for i, quote in enumerate(pain_point.representative_quotes[:3]):  # Top 3 quotes
                    source_id = source_ids[i] if i < len(source_ids) else "unknown"
                    metadata = post_metadata.get(source_id, {"subreddit": "Unknown", "score": 0})

                    quotes_with_sources.append(QuoteSource(
                        quote=quote[:200] + "..." if len(quote) > 200 else quote,  # Truncate long quotes
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

    def _generate_data_infrastructure_roadmap(self) -> Optional["DataInfrastructureRoadmap"]:
        """
        Generate 3-phase data infrastructure implementation roadmap with cost projections.

        Returns:
            DataInfrastructureRoadmap with phased implementation plan and cost scaling insight
        """
        if not self.state.data_source_research:
            return None

        try:
            data_research = self.state.data_source_research

            # Extract implementation roadmap phases from existing data
            phases = []

            # NEW: Use structured implementation_phases if available
            if data_research.implementation_phases:
                phases = [
                    DataInfrastructurePhase(
                        phase_number=phase.phase_number,
                        phase_name=phase.phase_name,
                        timeline=phase.timeline,
                        data_sources=phase.data_sources,
                        estimated_monthly_cost=phase.estimated_monthly_cost,
                        key_risks=phase.fallback_strategies[:3] if phase.fallback_strategies else []
                    )
                    for phase in data_research.implementation_phases
                ]
            # FALLBACK: Parse implementation roadmap text if available
            elif data_research.implementation_roadmap:
                roadmap_text = data_research.implementation_roadmap
                # Extract phases from formatted text (simple parsing)
                phase_texts = roadmap_text.split("Phase ")
                for i, phase_text in enumerate(phase_texts[1:], start=1):  # Skip first empty split
                    lines = phase_text.strip().split("\n")
                    phase_name_line = lines[0] if lines else f"Phase {i}"

                    # Extract phase name (e.g., "1 (Months 1-3): Launch MVP..." -> "MVP")
                    if ":" in phase_name_line:
                        phase_name_full = phase_name_line.split(":", 1)[1].strip()
                        phase_name = phase_name_full.split()[0] if phase_name_full else f"Phase {i}"
                        timeline_match = phase_name_line.split("(")[1].split(")")[0] if "(" in phase_name_line else f"Months {i*3-2}-{i*3}"
                    else:
                        phase_name = f"Phase {i}"
                        timeline_match = f"Months {i*3-2}-{i*3}"

                    # Extract data sources mentioned in phase text
                    data_sources = []
                    for source in data_research.primary_data_sources[:3]:  # Top 3 sources
                        if source.provider.lower() in phase_text.lower():
                            data_sources.append(source.provider)

                    phases.append(DataInfrastructurePhase(
                        phase_number=i,
                        phase_name=phase_name if phase_name != f"Phase {i}" else ["MVP", "Growth", "Scale"][i-1] if i <= 3 else f"Phase {i}",
                        timeline=timeline_match,
                        data_sources=data_sources if data_sources else [s.provider for s in data_research.primary_data_sources[:2]],
                        estimated_monthly_cost=data_research.estimated_monthly_cost.split(";")[i-1].strip() if ";" in data_research.estimated_monthly_cost else data_research.estimated_monthly_cost,
                        key_risks=[risk.strip() for risk in data_research.data_quality_risks[:2]] if data_research.data_quality_risks else []
                    ))

            # If parsing failed, create default 3-phase structure
            if len(phases) < 3:
                phases = [
                    DataInfrastructurePhase(
                        phase_number=1,
                        phase_name="MVP",
                        timeline="Months 1-3",
                        data_sources=[s.provider for s in data_research.primary_data_sources[:2]],
                        estimated_monthly_cost=data_research.estimated_monthly_cost.split(";")[0] if ";" in data_research.estimated_monthly_cost else data_research.estimated_monthly_cost.split("/")[0] if "/" in data_research.estimated_monthly_cost else data_research.estimated_monthly_cost,
                        key_risks=[data_research.data_quality_risks[0]] if data_research.data_quality_risks else []
                    ),
                    DataInfrastructurePhase(
                        phase_number=2,
                        phase_name="Growth",
                        timeline="Months 4-6",
                        data_sources=[s.provider for s in data_research.primary_data_sources],
                        estimated_monthly_cost="Scale with usage",
                        key_risks=[data_research.data_quality_risks[1]] if len(data_research.data_quality_risks) > 1 else []
                    ),
                    DataInfrastructurePhase(
                        phase_number=3,
                        phase_name="Scale",
                        timeline="Months 7-12",
                        data_sources=[s.provider for s in data_research.primary_data_sources] + [s.provider for s in data_research.fallback_sources[:1]],
                        estimated_monthly_cost="High volume - implement cost optimization",
                        key_risks=[data_research.data_quality_risks[2]] if len(data_research.data_quality_risks) > 2 else ["Cost scaling at high volume"]
                    )
                ]

            # Generate cost scaling insight
            cost_scaling_insight = f"Data infrastructure costs start at {phases[0].estimated_monthly_cost} during MVP, " \
                                   f"scaling with user growth. {data_research.data_quality_risks[0] if data_research.data_quality_risks else 'Monitor API rate limits and implement fallback strategies'} " \
                                   f"Critical mitigation: Implement tiered data source strategy with free/low-cost sources for baseline features, " \
                                   f"premium APIs for advanced personalization. Monitor unit economics to prevent cost spiral at scale."

            return DataInfrastructureRoadmap(
                phases=phases[:3],  # Ensure exactly 3 phases
                cost_scaling_insight=cost_scaling_insight
            )
        except Exception as e:
            logger.warning(f"Failed to generate data infrastructure roadmap: {e}")
            return None

    def _generate_decision_framework(self) -> Optional["DecisionFramework"]:
        """
        Generate go/no-go criteria and pivot triggers for decision-making.

        Returns:
            DecisionFramework with actionable criteria based on research findings
        """
        if not self.state.pain_point_analysis or not self.state.solution_selection:
            return None

        try:
            # Generate go criteria based on research findings
            go_criteria = [
                DecisionCriterion(
                    criterion_type="go",
                    condition="Validate 3+ high-severity pain points (severity >0.7) from Reddit threads with score >20",
                    rationale="Confirms real user demand with social validation signals"
                ),
                DecisionCriterion(
                    criterion_type="go",
                    condition="At least 2 identified competitors have <$10M funding or are bootstrapped",
                    rationale="Indicates beatable competitive landscape without dominant well-funded players"
                ),
            ]

            # Add SEO-related go criterion if available
            if self.state.seo_strategy_report:
                go_criteria.append(DecisionCriterion(
                    criterion_type="go",
                    condition="Top 10 target keywords show >10k monthly combined search volume with competition <60",
                    rationale="Validates organic acquisition channel viability and CAC estimates"
                ))

            # Add data sourcing go criterion if applicable
            if self.state.data_source_research:
                go_criteria.append(DecisionCriterion(
                    criterion_type="go",
                    condition="Secure 2+ core data sources with confirmed API access or free tier availability",
                    rationale="De-risks technical feasibility and MVP launch timeline"
                ))

            # Generate no-go criteria
            no_go_criteria = [
                DecisionCriterion(
                    criterion_type="no-go",
                    condition="Pain point validation shows <5 discussions total or <10 total mentions across all pain points",
                    rationale="Insufficient market signal indicates weak demand or poor niche-market fit"
                ),
                DecisionCriterion(
                    criterion_type="no-go",
                    condition="Competitive analysis reveals 3+ direct competitors with >$50M funding each",
                    rationale="Over-saturated market with well-capitalized incumbents makes differentiation extremely difficult"
                ),
                DecisionCriterion(
                    criterion_type="no-go",
                    condition="SEO keyword research shows <5k monthly search volume for top 10 keywords combined",
                    rationale="Insufficient organic demand makes customer acquisition cost prohibitively high"
                ),
            ]

            # Add data sourcing no-go criterion if applicable
            if self.state.data_source_research:
                no_go_criteria.append(DecisionCriterion(
                    criterion_type="no-go",
                    condition="Data source costs exceed $5k/month at 10k users, breaking unit economics",
                    rationale="Unsustainable cost structure prevents profitable scaling"
                ))

            # Generate pivot triggers based on alternative solutions
            pivot_triggers = []
            if self.state.solution_selection.runner_up_solutions:
                for runner_up_name in self.state.solution_selection.runner_up_solutions[:2]:
                    pivot_triggers.append(PivotTrigger(
                        trigger_condition=f"User interviews reveal {runner_up_name} pain points are 2x more frequently mentioned than selected solution pain points",
                        pivot_to_solution=runner_up_name,
                        rationale="Market demand signal stronger for alternative approach, justifies strategic pivot"
                    ))

            # Add generic pivot trigger
            pivot_triggers.append(PivotTrigger(
                trigger_condition="MVP validation shows <10% conversion from landing page to signup after 100+ visitors",
                pivot_to_solution=self.state.solution_selection.runner_up_solutions[0] if self.state.solution_selection.runner_up_solutions else "Alternative approach",
                rationale="Low conversion indicates value proposition mismatch, warrants testing alternative solution framing"
            ))

            return DecisionFramework(
                go_criteria=go_criteria,
                no_go_criteria=no_go_criteria,
                pivot_triggers=pivot_triggers
            )
        except Exception as e:
            logger.warning(f"Failed to generate decision framework: {e}")
            return None

    # ==================================================================================
    # Output Helpers
    # ==================================================================================

    def _display_executive_summary(self, report: FinalReport):
        """Display formatted executive summary to console."""
        logger.info("\n" + "=" * 80)
        logger.info("RESEARCH COMPLETE - FINAL REPORT")
        logger.info("=" * 80)
        logger.info(f"\nNiche: {report.niche}\n")
        logger.info("EXECUTIVE SUMMARY:")
        logger.info(report.executive_summary)
        logger.info(f"\n{'=' * 80}")
        logger.info("TOP PAIN POINTS:")
        for i, pp in enumerate(report.top_pain_points, 1):
            logger.info(f"  {i}. {pp}")
        logger.info(f"\n{'=' * 80}")
        logger.info("RECOMMENDED SOLUTIONS:")
        for i, sol in enumerate(report.recommended_solutions, 1):
            logger.info(f"  {i}. {sol}")
        logger.info(f"\n{'=' * 80}\n")
