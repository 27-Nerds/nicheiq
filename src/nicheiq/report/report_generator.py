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
        FeatureComparison,
        MarketAnalytics,
        PainPointAnalytics,
        SEOAnalytics,
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
    from ..models.solution_idea import BaseSolutionIdea, SolutionIdea, SolutionSEORefinement
    from ..models.solution_refinement import SolutionRefinement
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
    DataQualitySummary,
    EvidenceAppendix,
    FinalReport,
    PainPointEvidence,
    QuoteSource,
    RefinementHighlights,
    ResearchMetadata,
    ResearchState,
    RevenueMilestone,
    SEOCalculationTransparency,
    StageTimingSummary,
    SubredditBreakdown,
    TopRedditThread,
)
from ..utils.crew_helpers.traffic_pre_compute import (
    collect_all_tiered_keywords,
    compute_commercial_intent_ratio,
    compute_difficulty_weighted_traffic,
    compute_intent_breakdown,
    match_niche_to_cpm,
)
from ..utils.helpers import find_solution_by_name
from ..utils.idea_tags import refresh_tag_facets
from ..utils.prompts import safe_format
from .templates import ReportTemplates
from ..utils.llm_service import LLMService
from .utils import ScoreAccessor, StateAccessor
from .utils.number_formatters import format_percent, format_share

# The base Conditional verdict's generic concern. Named so the red-team floor (Phase 5.5)
# can recognize and null it on a 'killed' finding — every downgrade floor sets
# primary_concern only-if-None, and this generic would otherwise always win.
_GENERIC_CONDITIONAL_CONCERN = "Monitor market validation closely during MVP phase"

# Scoring-formula version stamped at the report root (S0.4). Bump when scoring formulas
# change (critic rubric, caps/floors, verdict thresholds, composite weights) so scores from
# different report vintages are never compared as if produced by the same formulas.
SCORING_VERSION = "2026.08"


class ExecutiveDashboardError(RuntimeError):
    """Raised when the executive dashboard cannot be produced with its verdict intact.

    Deliberately fatal. The dashboard carries the Go/No-Go verdict — the single answer a
    paid report exists to give. Shipping a completed report with `executive_dashboard: null`
    (the pre-2026-08 fail-soft) silently discarded computed NEGATIVE verdicts while the rest
    of the report kept recommending the build. A failed job is visible and retryable; a
    confidently wrong report is not.
    """


def _clean_text(value: Any) -> str | None:
    """Normalize an optional free-text field to a non-blank str, or None.

    Used at every descriptive-field boundary of the executive dashboard so an upstream None
    or "" becomes an explicit, renderable absence instead of a validation error.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# Shared with report/utils/state_accessors.py, which renders the same figures into the same
# report — the live 2026-08-03 audit found "0%" emitted independently by both modules.
_format_percent = format_percent
_format_share = format_share


# Unit ladder for money rendering, largest first.
_MONEY_UNITS: tuple[tuple[float, str], ...] = ((1e9, "B"), (1e6, "M"), (1e3, "K"))
_MONEY_SUFFIX_MULT = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9}
# "$0.000227-$0.000454M" / "$50-80M" / "$2.5B" / "$300". Ranges first (a suffix on either end
# applies to both, matching utils.validation.numeric_parsers.parse_dollar_amount).
# The suffix is optional but, when present, must not swallow the space before an ordinary
# word ("$9M in Year 1") nor match the first letter of one ("$5 million").
_MONEY_SUFFIX = r"(?:\s*([KMB])(?![A-Za-z]))?"
_MONEY_RANGE_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)" + _MONEY_SUFFIX
    + r"\s*(-|–|—|\s+to\s+)\s*\$?\s*([\d,]+(?:\.\d+)?)" + _MONEY_SUFFIX,
    re.IGNORECASE,
)
_MONEY_SINGLE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)" + _MONEY_SUFFIX, re.IGNORECASE)


def _render_money(value: float) -> str:
    """Render absolute dollars with the largest unit whose displayed number is >= 1."""
    magnitude = abs(value)
    for size, suffix in _MONEY_UNITS:
        if magnitude >= size:
            scaled = value / size
            # Trim a trailing ".0" so 800.0M renders as "$800M".
            text = f"{scaled:.2f}".rstrip("0").rstrip(".")
            return f"${text}{suffix}"
    text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"${text}"


def _rescale_money_text(text: str | None) -> str | None:
    """Rewrite every "$N[unit]" token in `text` so its unit matches its magnitude.

    Stage 9 emits TAM/SAM/SOM as free-form strings and the LLM sometimes keeps the "M" unit
    while shrinking the number, producing "$0.000227-$0.000454M" for what the same section's
    prose calls "$227-$454" (≈$1-$9/yr for the Y1 SOM). The numbers are right; the unit is
    absurd. Rescaling is lossless — it only re-expresses the same dollar value.
    """
    if not text or "$" not in text:
        return text

    def _abs(raw: str, suffix: str | None) -> float:
        return float(raw.replace(",", "")) * _MONEY_SUFFIX_MULT[(suffix or "").upper()]

    def _range_sub(m: re.Match) -> str:
        low_raw, low_suf, sep, high_raw, high_suf = m.groups()
        # A suffix on only one end applies to both ends of the range.
        low_suf = low_suf or high_suf
        high_suf = high_suf or low_suf
        low, high = _abs(low_raw, low_suf), _abs(high_raw, high_suf)
        separator = "-" if sep.strip() in {"-", "–", "—"} else " to "
        return f"{_render_money(low)}{separator}{_render_money(high)}"

    def _single_sub(m: re.Match) -> str:
        return _render_money(_abs(m.group(1), m.group(2)))

    try:
        return _MONEY_SINGLE_RE.sub(_single_sub, _MONEY_RANGE_RE.sub(_range_sub, text))
    except (ValueError, KeyError):  # unparseable token — leave the original text alone
        return text


# Money-bearing string fields on MarketSizingResult / MarketSegmentSizing.
_MARKET_SIZING_MONEY_FIELDS = (
    "total_addressable_market",
    "serviceable_available_market",
    "serviceable_obtainable_market_y1",
    "serviceable_obtainable_market_y3",
)
_SEGMENT_SIZING_MONEY_FIELDS = ("tam_estimate", "sam_estimate", "som_estimate")

# Pipeline stage names, for naming a SKIPPED stage in a caveat. Mirrors the map in
# flows/research_flow.py:_mark_stage_complete (only the numbers that can be skipped matter).
_STAGE_NAMES: dict[float, str] = {
    1: "Niche Context",
    2: "Social Content Collection",
    3: "Pain Point Analysis",
    4: "Audience Mapping",
    5: "Solution Ideation",
    5.5: "Competitive Analysis",
    6: "SEO & Keyword Strategy",
    7: "Pricing Validation",
    8: "Traffic Monetization",
    9: "Market Sizing",
    10: "Solution Refinement",
    11: "Trend Analysis",
    12: "SEO Score Refinement",
    13: "Data Source Research",
    14: "Report Generation",
}


def _stage_label(stage: float) -> str:
    name = _STAGE_NAMES.get(stage)
    number = int(stage) if float(stage).is_integer() else stage
    return f"Stage {number} ({name})" if name else f"Stage {number}"


class ReportGenerator:
    """
    Stage 14 Final Report Generation.

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

    def __init__(self, state: ResearchState, cost_tracker=None):
        """
        Initialize report generator.

        Args:
            state: Complete ResearchState containing all stage results
            cost_tracker: Optional CostTracker; when provided, the Stage-14 LLM
                calls record their token usage/cost into it (otherwise no-op).
        """
        self.state = state
        self.accessor = StateAccessor(state)
        self.score_accessor = ScoreAccessor(state.solution_selection)
        self.cost_tracker = cost_tracker
        # Reader-facing caveats raised while assembling the executive dashboard; folded into
        # data_quality_summary.quality_caveats so a degraded dashboard is never silent.
        self._dashboard_caveats: list[str] = []
        self._normalized_ms_cache = None

    def _record_cost(self, stage: str, usage) -> None:
        """Record a direct-LLM TokenUsage into the cost tracker (no-op if absent)."""
        if self.cost_tracker and usage:
            try:
                self.cost_tracker.record_llm_usage(stage, usage.to_dict())
            except Exception:
                pass

    @staticmethod
    def _merge_legacy_traffic_projection(
        traffic_monetization: Any,
        update_fields: dict[str, Any],
    ) -> Any:
        """Apply raw-tier report projections only to unevaluated legacy records.

        Deterministic Stage-8 economics may intentionally produce an unknown verdict.
        The explicit evaluation marker keeps that third state distinct from a legacy
        record. Raw SEO tier totals may include category or off-topic demand and cannot
        replace an evaluated record.
        """
        if (
            getattr(traffic_monetization, "economics_evaluated", False)
            or getattr(traffic_monetization, "viability_verdict", None) is not None
        ):
            return traffic_monetization
        return traffic_monetization.model_copy(update=update_fields)

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
        pain_count = len(final_report.detailed_pain_points) if final_report.detailed_pain_points else 0
        logger.info(
            f"[OK] Base report assembled: {pain_count} pain points, "
            f"{len(final_report.recommended_solutions)} solutions"
        )

        # Step 1.5: Enrich community hubs with real subreddit data
        self._enrich_community_hubs(final_report)

        # Store enriched solution for all downstream methods to share (RC1 fix)
        # final_report.selected_solution_details has Stage 12 SEO refinements merged
        self._enriched_solution = final_report.selected_solution_details

        # Step 2: Enhance with LLM for strategic synthesis
        logger.info("Step 2: Enhancing with LLM for strategic synthesis (optional)...")
        final_report = self._enhance_report_with_llm(final_report)

        # Step 2.5: Generate pain-solution mappings only for validated pains the selected
        # solution actually references. The full niche pain corpus remains in the Evidence
        # section, but must never acquire a fabricated solution bridge.
        if final_report.detailed_pain_points and final_report.selected_solution_details:
            solution_pain_points = self.accessor.get_solution_pain_points(
                final_report.selected_solution_details,
                limit=10,
            )
            solution_pain_titles = {pain.title for pain in solution_pain_points}
            for pain_point in final_report.detailed_pain_points:
                if pain_point.title not in solution_pain_titles:
                    pain_point.solution_approach = None
            pain_solution_mappings = self._generate_pain_solution_mappings(
                pain_points=solution_pain_points,
                solution=final_report.selected_solution_details
            )
            # Apply mappings to pain points
            if pain_solution_mappings:
                for pp in final_report.detailed_pain_points:
                    if pp.title in pain_solution_mappings:
                        pp.solution_approach = pain_solution_mappings[pp.title]
                logger.info(
                    f"[OK] Applied solution approach to {len(pain_solution_mappings)} pain points"
                )

        # Step 3: Generate enhanced report sections (Python-based data preservation)
        logger.info("Step 3: Generating enhanced report sections (Python)...")

        # Executive Dashboard (Phase 1 Enhancement) - TOP-LEVEL SUMMARY
        # Pass enriched solution from final_report (already has Stage 12 SEO refinements merged)
        final_report.executive_dashboard = self._generate_executive_dashboard(
            enriched_solution=final_report.selected_solution_details
        )
        if final_report.executive_dashboard:
            _dash = final_report.executive_dashboard
            _conf = f"{_dash.confidence_score:.2f}" if _dash.confidence_score is not None else "N/A"
            _kw = _dash.key_metrics.total_keyword_count if _dash.key_metrics else "unknown"
            logger.info(
                f"[OK] Executive dashboard generated: "
                f"{_dash.go_no_go_verdict.verdict} verdict, "
                f"confidence {_conf}, {_kw} keywords analyzed"
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

        # Analytics (Phase 3 Enhancement) - DATA-DRIVEN INSIGHTS
        (
            market_analytics,
            seo_analytics,
            competitive_analytics,
            pain_point_analytics,
        ) = self._generate_analytics()

        final_report.market_analytics = market_analytics
        final_report.seo_analytics = seo_analytics
        final_report.competitive_analytics = competitive_analytics
        final_report.pain_point_analytics = pain_point_analytics

        if market_analytics and seo_analytics:
            logger.info(
                f"[OK] Analytics generated: "
                f"Opportunity score {market_analytics.overall_opportunity_score:.2f}, "
                f"{seo_analytics.total_keywords} keywords, "
                f"{competitive_analytics.competitor_count if competitive_analytics else 0} competitors, "
                f"{pain_point_analytics.total_pain_points if pain_point_analytics else 0} pain points"
            )

        final_report.research_metadata = self._generate_research_metadata()
        if final_report.research_metadata:
            logger.info(
                f"[OK] Research metadata generated: "
                f"{final_report.research_metadata.reddit_posts_analyzed} Reddit posts, "
                f"{final_report.research_metadata.twitter_threads_analyzed} Twitter threads, "
                f"{final_report.research_metadata.generic_posts_analyzed} generic posts"
            )

        final_report.alternative_solutions = self._generate_alternative_solutions()
        if final_report.alternative_solutions:
            logger.info(
                f"[OK] Alternative solutions generated: "
                f"{len(final_report.alternative_solutions)} runner-up solutions detailed"
            )

        # Stage 10.5: Technical Blueprint (Site Structure + User Flows)
        if final_report.selected_solution_details:
            site_structure, user_flows = self._generate_technical_blueprint(
                final_report.selected_solution_details
            )
            final_report.site_structure = site_structure
            final_report.user_flows = user_flows
            if site_structure:
                logger.info(
                    f"[OK] Site structure generated: "
                    f"{len(site_structure.sections)} sections, "
                    f"{site_structure.mvp_page_count} MVP pages"
                )
            if user_flows:
                logger.info(
                    f"[OK] User flows generated: "
                    f"{len(user_flows.flows)} flows"
                )

        final_report.competitive_landscape_matrix = self._generate_competitive_landscape_matrix()
        if final_report.competitive_landscape_matrix:
            logger.info(
                f"[OK] Competitive landscape matrix generated: "
                f"{len(final_report.competitive_landscape_matrix.competitor_overlap)} "
                f"multi-solution competitors identified"
            )

        # Build detailed competitor profiles for selected solution
        final_report.competitor_profiles = self._build_competitor_profiles()
        if final_report.competitor_profiles:
            logger.info(
                f"[OK] Competitor profiles generated: "
                f"{len(final_report.competitor_profiles)} detailed profiles"
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

        # Phase 6: Data Quality & Pipeline Transparency
        final_report.data_quality_summary = self._generate_data_quality_summary()
        if final_report.data_quality_summary:
            logger.info(
                f"[OK] Data quality summary: {final_report.data_quality_summary.overall_data_quality} quality, "
                f"{len(final_report.data_quality_summary.quality_caveats)} caveats"
            )

        # Research Reality Check — computed end of Phase 1, carried on state (no re-generation).
        final_report.niche_difficulty_verdict = getattr(self.state, "niche_difficulty_verdict", None)

        # S0.4: scoring-formula version at the report root (sibling of data_quality_summary).
        # Reports generated before the 2026.08 cutover carry None here.
        final_report.scoring_version = SCORING_VERSION

        # Market-data handoff: same Phase-1 web-verified incumbent/wallet facts already shown on
        # the preview report's top-level market_reality (see research_flow._materialize_preview_report)
        # and handed to Stage-2 deep research once (utils/market_brief.py) — shown here again so the
        # final report doesn't silently drop the evidence behind the parity findings.
        final_report.market_reality = self._generate_market_reality()

        # Idea portfolio summary — computed once in Stage 5 alongside the difficulty verdict
        # above (see utils/idea_portfolio_summary.py); carried on state, never regenerated here.
        final_report.idea_portfolio_summary = getattr(self.state, "idea_portfolio_summary", None)

        final_report.refinement_highlights = self._generate_refinement_highlights()
        if final_report.refinement_highlights:
            logger.info(
                f"[OK] Refinement highlights: {len(final_report.refinement_highlights.top_strategic_insights)} insights"
            )

        final_report.stage_timing_summary = self._generate_stage_timing_summary()
        if final_report.stage_timing_summary:
            logger.info(
                f"[OK] Stage timing: {final_report.stage_timing_summary.total_duration_seconds:.1f}s total, "
                f"slowest: {final_report.stage_timing_summary.slowest_stage}"
            )

        final_report.seo_calculation_transparency = self._generate_seo_calculation_transparency()
        if final_report.seo_calculation_transparency:
            logger.info(
                f"[OK] SEO calculation transparency: "
                f"baseline={final_report.seo_calculation_transparency.baseline_seo_score}, "
                f"refined={final_report.seo_calculation_transparency.refined_seo_score}"
            )

        # Cross-section consistency validation (Layer 4: safety net)
        from ..validators.report_consistency import ReportConsistencyValidator
        validator = ReportConsistencyValidator()
        fixes, warnings = validator.reconcile(final_report, self.state)
        if fixes:
            logger.info(f"Report consistency: {len(fixes)} auto-fixes applied")
            for fix in fixes:
                logger.debug(f"  Fix: {fix}")
        if warnings:
            logger.warning(f"Report consistency: {len(warnings)} warnings")
            for w in warnings:
                logger.warning(f"  [{w.severity}] {w.message}")
            if not final_report.data_quality_summary:
                final_report.data_quality_summary = DataQualitySummary(
                    overall_data_quality="MEDIUM", quality_caveats=[]
                )
            final_report.data_quality_summary.quality_caveats.extend(
                [w.message for w in warnings if w.severity in ("ERROR", "WARNING")]
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

        # Extract pain points summary (detailed_pain_points used directly)
        pain_points_summary = self.accessor.get_pain_points_summary()
        # top_pain_points and pain_point_categories removed - use detailed_pain_points instead

        # Extract ALL recommended solutions (no limit)
        recommended_solutions = self.accessor.get_all_solution_names(selected_first=True)
        solutions_summary = self.accessor.get_solutions_summary()

        # Extract competitive summary (use existing strategic_recommendations)
        competitive_summary = self.accessor.get_competitive_summary()

        # Extract solution selection (Stage 5)
        selected_solution_name = self.accessor.get_selected_solution_name()
        selection_rationale = self.accessor.get_selection_rationale()
        original_selection_reasoning = getattr(
            self.state.solution_selection, 'original_selection_reasoning', None
        ) if self.state.solution_selection else None
        # runner_up_solutions removed - use alternative_solutions instead
        recommended_focus = self.accessor.get_recommended_focus()

        # Find selected solution details using fuzzy match helper
        selected_solution_details = self.accessor.get_selected_solution_details()

        # Extract keyword validation and refinement data (keyword validation and 8.85)
        # Extract keyword validation and content strategy data using accessor
        keyword_validation_overview = self.accessor.get_keyword_validation_overview()
        solution_keyword_comparison = self.accessor.get_keyword_validation_comparison()
        content_strategy_preview = self.accessor.get_content_strategy_preview()

        # Merge enrichments into selected_solution_details (unified enrichment pattern)
        # This merges Stage 10 (keyword refinement) + Stage 12 (SEO refinement) into base solution
        if selected_solution_details:
            selected_solution_details = self._merge_solution_enrichments(
                base_solution=selected_solution_details,
                keyword_enrichment=self.state.solution_refinement,
                seo_enrichment=getattr(self.state, 'seo_enrichment', None)
            )
            # Sync scores via ScoreAccessor (single source of truth)
            # This ensures selected_solution_details shows the same final scores
            # as executive_dashboard.key_metrics
            selected_solution_details = self._sync_solution_scores(
                selected_solution_details
            )

        # Generate template-based sections using ReportTemplates
        solution_user_journey = ReportTemplates.user_journey(selected_solution_details)
        # implementation_overview and mvp_scope are now LLM-generated in _enhance_report_with_llm()
        acquisition_strategy_summary = ReportTemplates.acquisition_strategy(selected_solution_details)
        estimated_cac_breakdown = ReportTemplates.cac_breakdown(selected_solution_details)

        # Extract pricing strategy for selected solution from list (Stage 8)
        pricing_strategy = None
        if hasattr(self.state, 'pricing_strategies') and self.state.pricing_strategies:
            for p in self.state.pricing_strategies:
                if p.solution_name == selected_solution_name:
                    pricing_strategy = p
                    break

        # Unit-economics grounding (downgrade-only). The pricing crew divides LTV by the
        # market-fit-derived *suggested* CAC band, not by this idea's CAC — and a rebuilt
        # idea publishes no CAC at all (unified_solution_crew._UNGROUNDABLE_ON_REBUILD).
        # Left alone, the report prints a headline ratio straight above a CAC table reading
        # "N/A". Compare against the exact fields that table renders and clear or label the
        # ratio; never rewrite the numeral, and never touch a ratio that honestly fails 2:1.
        if pricing_strategy is not None and selected_solution_details is not None:
            from ..validators.unit_economics import apply_ltv_cac_grounding

            pricing_strategy, grounding = apply_ltv_cac_grounding(
                pricing_strategy, selected_solution_details, selected_solution_name
            )
            if grounding.changed:
                logger.warning(
                    f"[UnitEconomics] {grounding.status} for '{selected_solution_name}': "
                    f"{grounding.degradation}"
                )
                if grounding.degradation and grounding.degradation not in (
                    self.state.pipeline_degradations
                ):
                    self.state.pipeline_degradations.append(grounding.degradation)

        # Extract traffic monetization for selected solution from list (Stage 8)
        traffic_monetization = None
        if hasattr(self.state, 'traffic_monetization_results') and self.state.traffic_monetization_results:
            for tm in self.state.traffic_monetization_results:
                if tm.solution_name == selected_solution_name:
                    traffic_monetization = tm
                    break

        # Override LLM numeric fields with pre-computed evidence-based values + populate growth trajectory
        if (
            traffic_monetization
            and getattr(self.state, 'seo_strategy_report', None)
            and not getattr(traffic_monetization, 'economics_evaluated', False)
            and getattr(traffic_monetization, 'viability_verdict', None) is None
        ):
            seo_report = self.state.seo_strategy_report
            niche_ctx = getattr(self.state, 'niche_context', None)
            niche_desc = getattr(niche_ctx, 'niche_description', '') if niche_ctx else ''
            niche_desc = niche_desc or ''

            # Collect tiered keywords
            t0 = list(getattr(seo_report, 'tier_0_keywords', None) or [])
            t1 = list(getattr(seo_report, 'tier_1_keywords', None) or [])
            t2 = list(getattr(seo_report, 'tier_2_keywords', None) or [])

            # Per-tier difficulty-weighted traffic
            t0_low, t0_high = compute_difficulty_weighted_traffic(t0)
            t1_low, t1_high = compute_difficulty_weighted_traffic(t1)
            t2_low, t2_high = compute_difficulty_weighted_traffic(t2)

            # Content compounding multiplier (internal links, topical authority)
            compound = 1.25

            # Year 1: T1 + 60% T2 (T2 needs more time to rank)
            y1_pv_low = int((t1_low + 0.6 * t2_low) * compound)
            y1_pv_high = int((t1_high + 0.6 * t2_high) * compound)

            # Year 3: T1 + T2 fully ramped
            y3_pv_low = int((t1_low + t2_low) * compound)
            y3_pv_high = int((t1_high + t2_high) * compound)

            # Full Potential: all tiers including T0 (hard keywords)
            fp_pv_low = int((t0_low + t1_low + t2_low) * compound)
            fp_pv_high = int((t0_high + t1_high + t2_high) * compound)

            # CPM from niche vertical
            cpm_low, cpm_high, vertical = match_niche_to_cpm(niche_desc)

            # Intent breakdown for affiliate estimates
            all_keywords = collect_all_tiered_keywords(seo_report)
            intent = compute_intent_breakdown(all_keywords)
            commercial_pct = compute_commercial_intent_ratio(intent)

            # --- Revenue calculations (evidence-based rates) ---
            # Ad revenue: pageviews × CPM / 1000
            y1_ad_low = int(y1_pv_low * cpm_low / 1000)
            y1_ad_high = int(y1_pv_high * cpm_high / 1000)
            y3_ad_low = int(y3_pv_low * cpm_low / 1000)
            y3_ad_high = int(y3_pv_high * cpm_high / 1000)
            fp_ad_low = int(fp_pv_low * cpm_low / 1000)
            fp_ad_high = int(fp_pv_high * cpm_high / 1000)

            # Affiliate revenue: commercial_traffic × CTR(1-3%) × CVR(1-3%) × avg commission($50-$150)
            commercial_frac = commercial_pct / 100.0
            y1_aff_low = int(y1_pv_low * commercial_frac * 0.01 * 0.01 * 50)
            y1_aff_high = int(y1_pv_high * commercial_frac * 0.03 * 0.03 * 150)
            y3_aff_low = int(y3_pv_low * commercial_frac * 0.01 * 0.01 * 50)
            y3_aff_high = int(y3_pv_high * commercial_frac * 0.03 * 0.03 * 150)
            fp_aff_low = int(fp_pv_low * commercial_frac * 0.01 * 0.01 * 50)
            fp_aff_high = int(fp_pv_high * commercial_frac * 0.03 * 0.03 * 150)

            # Totals
            y1_total_low = y1_ad_low + y1_aff_low
            y1_total_high = y1_ad_high + y1_aff_high
            y3_total_low = y3_ad_low + y3_aff_low
            y3_total_high = y3_ad_high + y3_aff_high
            fp_total_low = fp_ad_low + fp_aff_low
            fp_total_high = fp_ad_high + fp_aff_high

            # --- Revenue growth note (varies by commercial intent) ---
            if commercial_pct < 20:
                revenue_growth_note = (
                    f"These projections show ad revenue from organic search on a new domain — the most "
                    f"conservative baseline. With {commercial_pct:.0f}% commercial intent, early monetization "
                    f"comes primarily from display advertising.\n\n"
                    f"What these numbers don't include — and where the real opportunity lies:\n\n"
                    f"Content compounds: Every article is a permanent traffic asset. After the initial "
                    f"6-12 month ranking period, quality articles typically generate 30-80 sessions/month "
                    f"each, growing to 100-300+ as domain authority builds.\n\n"
                    f"Revenue multipliers at scale: Basic ad networks (AdSense, Ezoic) pay "
                    f"${cpm_low}-${cpm_high} CPM. Premium networks pay significantly more — Raptive "
                    f"accepts sites at 25,000 pageviews/month (lowered Oct 2025), and Mediavine's Journey "
                    f"program starts at just 1,000 sessions/month. Premium networks typically pay $10-$30 "
                    f"RPM for {vertical} content — a 2-4x uplift over basic networks.\n\n"
                    f"Beyond ads: Established content sites typically earn 2-4x their display ad revenue "
                    f"through additional channels — digital products, sponsored content ($1,000-$5,000/post "
                    f"for tech/B2B audiences), newsletter sponsorships, and consulting. This requires "
                    f"deliberate effort building an email list and developing products, typically achievable "
                    f"6-12 months after establishing consistent traffic.\n\n"
                    f"These projections are the floor, not the ceiling. They show what a new site earns "
                    f"using the simplest monetization model (display ads only). The growth trajectory and "
                    f"milestones below show how revenue scales as traffic grows."
                )
            elif commercial_pct < 40:
                revenue_growth_note = (
                    f"These projections represent baseline ad + affiliate revenue from organic search on a "
                    f"new domain. With {commercial_pct:.0f}% commercial intent, this niche supports hybrid "
                    f"monetization from the start — display ads for informational traffic and affiliate "
                    f"commissions for commercial-intent visitors.\n\n"
                    f"Revenue scales with traffic: as you rank for more keywords and move up in search "
                    f"positions, both traffic and revenue per visitor increase. Premium ad networks "
                    f"(Raptive at 25K pageviews, Mediavine Journey at 1K sessions) pay 2-4x basic rates. "
                    f"Affiliate conversion rates also improve as domain authority builds.\n\n"
                    f"Additional revenue channels unlock at scale — sponsored content, digital products, "
                    f"and lead generation typically add 2-3x on top of baseline ad + affiliate revenue "
                    f"for {vertical} sites, though this requires deliberate product development and "
                    f"outreach effort."
                )
            else:
                revenue_growth_note = (
                    f"Strong commercial intent ({commercial_pct:.0f}%) makes affiliate marketing viable as a "
                    f"primary revenue driver from the start. Tech/SaaS affiliate programs typically pay "
                    f"$50-$150 per conversion (e.g., Semrush $200, Freshbooks $200, with many programs "
                    f"at $20-$50). With a 1-3% click rate and 1-3% conversion rate on commercial-intent "
                    f"traffic, revenue scales directly with traffic growth.\n\n"
                    f"As traffic grows, additional monetization layers compound: premium ad networks "
                    f"(Raptive at 25K pageviews), sponsored listings, and lead generation."
                )

            # --- Revenue milestones (evidence-based thresholds) ---
            revenue_milestones = [
                RevenueMilestone(
                    traffic="5,000 sessions/mo",
                    ad_revenue=f"${int(5000 * cpm_low / 1000)}-${int(5000 * cpm_high / 1000)}/mo",
                    unlock="Ezoic, Mediavine Journey eligible (basic programmatic ads)",
                    total_potential=f"${int(5000 * cpm_low / 1000)}-${int(5000 * cpm_high * 1.3 / 1000)}/mo with affiliate",
                ),
                RevenueMilestone(
                    traffic="25,000 sessions/mo",
                    ad_revenue=f"${int(25000 * cpm_low / 1000)}-${int(25000 * cpm_high / 1000)}/mo",
                    unlock="Raptive eligible ($10-$30 RPM), newsletter sponsors viable",
                    total_potential=f"${int(25000 * 10 / 1000)}-${int(25000 * 30 / 1000)}/mo with premium ads",
                ),
                RevenueMilestone(
                    traffic="50,000 sessions/mo",
                    ad_revenue=f"${int(50000 * 10 / 1000)}-${int(50000 * 30 / 1000)}/mo",
                    unlock="Mediavine Official, premium RPMs ($10-$30), sponsored content",
                    total_potential=f"${int(50000 * 10 * 2 / 1000)}-${int(50000 * 30 * 2.5 / 1000)}/mo total",
                ),
                RevenueMilestone(
                    traffic="100,000 sessions/mo",
                    ad_revenue=f"${int(100000 * 10 / 1000)}-${int(100000 * 30 / 1000)}/mo",
                    unlock="Sponsored posts ($1K-$5K/post for tech/B2B), digital products, consulting",
                    total_potential=f"${int(100000 * 10 * 2 / 1000)}-${int(100000 * 30 * 3 / 1000)}/mo total",
                ),
            ]

            # Build model_copy update dict — growth trajectory always; the
            # evidence-based methodology label ONLY when the code projection
            # actually replaces the LLM numbers (below), so LLM-fallback
            # estimates are never labeled "evidence-based".
            evidence_methodology = (
                    "Traffic projections are computed using evidence-based models rather than flat estimates. "
                    "Click-through rates by SERP position are based on the Backlinko & ClickFlow study "
                    "(874,000 URLs, 5 million queries, updated 2025). Keyword difficulty scores are mapped "
                    "to estimated ranking probability using a model calibrated for well-optimized new sites "
                    "(DA < 30) — these are projections, not guarantees. Easy keywords (KD < 25) are "
                    "estimated at ~80% probability of page-1 ranking within 6-12 months with quality "
                    "content, medium keywords (KD 25-50) at ~45% in 9-12 months, and hard keywords "
                    "(KD 50+) at ~12% in 12-18+ months. Note: Ahrefs' aggregate data shows only 5.7% of "
                    "all published pages reach the top 10 within a year — our higher estimates assume "
                    "strategic keyword targeting and quality content execution. "
                    "Year 1 traffic ceilings are the sum of (search volume x position-based CTR x ranking probability) "
                    "across all keywords in each difficulty tier. "
                    "Monetization benchmarks use evidence-based rates: "
                    "affiliate click rates of 1-3% for commercial-intent traffic, "
                    "conversion rates of 1-3%, average SaaS commission of $50-$150, "
                    "and display CPMs of ${}-${} for {} verticals.".format(cpm_low, cpm_high, vertical)
            )

            update_fields: dict[str, Any] = {
                # Growth trajectory fields
                "year3_monthly_pageviews": f"{y3_pv_low:,}-{y3_pv_high:,}",
                "year3_monthly_revenue": f"${y3_total_low:,}-${y3_total_high:,}/mo",
                "full_potential_monthly_pageviews": f"{fp_pv_low:,}-{fp_pv_high:,}",
                "full_potential_monthly_revenue": f"${fp_total_low:,}-${fp_total_high:,}/mo",
                "revenue_growth_note": revenue_growth_note,
                "revenue_milestones": revenue_milestones,
            }

            # Override LLM numeric fields only if pre-computed values are non-zero;
            # the "evidence-based" methodology label ships ONLY with the code
            # projection — LLM-fallback estimates get an honest provenance label.
            if y1_pv_low > 0:
                update_fields.update({
                    "traffic_methodology": evidence_methodology,
                    "traffic_data_sources": [
                        "Backlinko & ClickFlow CTR Study (874K URLs)",
                        "KD-to-Ranking Probability Model (calibrated estimates for new sites)",
                        "Raptive/Mediavine Ad Network Thresholds (2025-2026)",
                        "DataForSEO Keyword Metrics",
                    ],
                    "estimated_monthly_pageviews": f"{y1_pv_low:,}-{y1_pv_high:,}",
                    "estimated_cpm_rate": f"${cpm_low}-${cpm_high} CPM ({vertical})",
                    "estimated_monthly_ad_revenue": f"${y1_ad_low:,}-${y1_ad_high:,}",
                    "estimated_monthly_affiliate_revenue": f"${y1_aff_low:,}-${y1_aff_high:,}",
                    "estimated_monthly_revenue_range": f"${y1_total_low:,}-${y1_total_high:,}",
                    "estimated_annual_revenue_range": f"${y1_total_low * 12:,}-${y1_total_high * 12:,}",
                })
            else:
                update_fields["traffic_methodology"] = (
                    "Traffic and revenue figures are LLM-modeled estimates from keyword and "
                    "competitive context. The evidence-based projection model produced a zero "
                    "Year-1 traffic ceiling for this keyword set, so these estimates could not "
                    "be independently validated — treat them as directional, not measured."
                )

            traffic_monetization = self._merge_legacy_traffic_projection(
                traffic_monetization, update_fields
            )

        # Generate market_validation based on actual metrics.
        # P0b: headline the BEACHHEAD demand (the selected solution's OWN validated keyword volume) — NOT
        # the whole-niche keyword total, which is the follow-on REACH CEILING. Headlining the category
        # number is the "1% fallacy" and makes this narrative contradict the beachhead-anchored verdict +
        # market sizing (docs/MARKET_SIZING_METHODOLOGY.md). Category volume is kept only as secondary reach.
        beachhead_vol = self.accessor.get_beachhead_search_volume()
        category_vol = self.accessor.get_primary_search_volume()
        headline_vol = beachhead_vol if beachhead_vol > 0 else category_vol
        if headline_vol == 0:
            logger.warning("⚠️ Keyword volume is 0 for market validation - check keyword pipeline")
        pain_point_count = len(self.state.pain_point_analysis.pain_points) if self.state.pain_point_analysis else 0

        # LEVEL: prefer the market-sizing viability verdict (already beachhead-anchored + LLM-judged, so
        # it stays consistent with the market-sizing section) — else fall back to volume thresholds applied
        # to the BEACHHEAD volume, not the inflated category total.
        ms_verdict = ""
        if self.state.market_sizing:
            ms_verdict = (getattr(self.state.market_sizing, "market_viability_verdict", "") or "").strip().lower()
        if ms_verdict in ("strong", "moderate", "weak"):
            validation_level = {"strong": "STRONG", "moderate": "MODERATE", "weak": "EMERGING"}[ms_verdict]
        elif (headline_vol > settings.market_validation_strong_volume and
              pain_point_count >= settings.market_validation_strong_pain_points):
            validation_level = "STRONG"
        elif (headline_vol > settings.market_validation_moderate_volume and
              pain_point_count >= settings.market_validation_moderate_pain_points):
            validation_level = "MODERATE"
        else:
            validation_level = "EMERGING"

        reach_note = (f"Broader niche reach: {category_vol:,}/mo (follow-on ceiling). "
                      if category_vol > headline_vol else "")
        # Label honestly: when there is no per-solution beachhead volume (keyword validation produced
        # none), the headline falls back to the CATEGORY total and must SAY so — calling a category
        # number "beachhead demand" is the exact 1%-fallacy presentation this narrative exists to avoid
        # (observed live 2026-07-02: 'Beachhead demand: 1,628,480' on an empty validated set).
        if beachhead_vol > 0:
            demand_line = f"Beachhead demand: {headline_vol:,} monthly searches for the solution's core keywords. "
        else:
            demand_line = (f"Category search volume: {headline_vol:,} monthly searches "
                           f"(no solution-specific beachhead demand was validated — treat as reach ceiling, "
                           f"not addressable demand). ")
        # Q-049 (additive only — the demand headline above comes from a DIFFERENT keyword
        # universe and must not be substituted): when the three-band idea-intent fields were
        # computed, append the honest idea-intent share of the ANALYZED keyword set.
        intent_note = ""
        seo_rep = self.state.seo_strategy_report
        if seo_rep is not None:
            _iiv = getattr(seo_rep, "idea_intent_monthly_volume", None)
            _off = getattr(seo_rep, "offtopic_volume_share", None)
            _cat = getattr(seo_rep, "category_volume_share", None)
            _tot = getattr(seo_rep, "total_monthly_volume", 0) or 0
            if _iiv is not None and _off is not None and _cat is not None and _tot > 0:
                intent_note = (
                    f"Idea-intent keywords account for {_iiv:,}/mo of the {_tot:,}/mo analyzed "
                    f"keyword set ({_format_share(_iiv, _tot)}); the remainder is category or "
                    f"off-topic reach. "
                )
        market_validation = (
            f"{validation_level} market validation. "
            f"{demand_line}"
            f"{reach_note}"
            f"{intent_note}"
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
                # Q-049 band fields: no keyword set to grade — explicitly None (today's behavior)
                offtopic_volume_share=None,
                category_volume_share=None,
                idea_intent_monthly_volume=None,
                key_findings=["SEO strategy generation failed - manual keyword research required"],
                tier_1_keywords=[],
                tier_1_quick_win_strategy="Complete keyword research to identify quick win opportunities.",
                content_strategy="Develop content strategy after completing keyword research.",
                technical_seo_recommendations="Standard technical SEO best practices apply.",
                competitive_positioning="Conduct keyword research to identify competitive opportunities.",
                implementation_roadmap="1. Complete keyword research\n2. Develop SEO strategy\n3. Implement content plan",
            )
        else:
            seo_strategy = self.state.seo_strategy_report

            # Derive Tier 0 premium keywords from high-scoring Tier 1 if missing
            if not seo_strategy.tier_0_keywords and seo_strategy.tier_1_keywords:
                logger.warning("⚠️ Tier 0 keywords not generated by SEO crew - deriving from Tier 1")
                # Premium keywords = Tier 1 with highest opportunity scores
                tier0_candidates = sorted(
                    [kw for kw in seo_strategy.tier_1_keywords if kw.opportunity_score],
                    key=lambda x: x.opportunity_score or 0,
                    reverse=True
                )[:5]  # Top 5 at most
                if tier0_candidates:
                    seo_strategy.tier_0_keywords = tier0_candidates
                    logger.info(f"Derived {len(tier0_candidates)} Tier 0 keywords from high-scoring Tier 1")

            # Log warning if Tier 3 geographic keywords are missing
            if not seo_strategy.tier_3_geographic_groups:
                logger.warning("⚠️ Tier 3 geographic keywords not generated by SEO crew")

        # === DATA RICHNESS ENHANCEMENTS ===
        # Extract innovation assessment from selected solution
        solution_innovation_assessment = None
        # solution_organic_discovery removed - data available in selected_solution_details
        if selected_solution_details:
            solution_innovation_assessment = {
                "novelty_score": getattr(selected_solution_details, 'novelty_score', None),
                "conventional_approach": getattr(selected_solution_details, 'conventional_approach', None),
                "innovation_angle": getattr(selected_solution_details, 'innovation_angle', None),
                "why_it_works": getattr(selected_solution_details, 'why_it_works', None),
                "solo_dev_feasibility": getattr(selected_solution_details, 'solo_dev_feasibility', None)
            }

        # Build comprehensive final report with all fields
        # NOTE: Duplicate data (audience_mapping, market_sizing, etc.) is NOT included here
        # to avoid bloat. These are available via ResearchState directly.
        return FinalReport(
            # Basic info
            niche=self.state.niche_context.niche_description,
            # Transparency: catalog-seeded runs (pain_research / deep_idea) have thinner
            # community evidence; the flag drives the "seeded from catalog" UI badge.
            seeded_from_catalog=getattr(self.state, 'seeded_from_catalog', False),
            # Guided-mode honesty block (Phase C): surfaces gate patches applied during this run.
            user_adjusted=getattr(self.state, 'user_adjusted', False),
            user_adjustments=self.accessor.get_user_adjustments_summary(),
            executive_summary=f"Market research completed for {self.state.niche_context.niche_description}. "
            f"Identified {len(self.state.pain_point_analysis.pain_points) if self.state.pain_point_analysis else 0} validated pain points and "
            f"{len(recommended_solutions)} solution concepts. "
            f"Selected solution: {selected_solution_name}.",

            # Solution selection (Stage 5)
            selected_solution_name=selected_solution_name,
            selection_rationale=selection_rationale,
            original_selection_reasoning=original_selection_reasoning,
            # runner_up_solutions removed - use alternative_solutions
            # selection_criteria_scores removed - ScoreAccessor is single source of truth
            recommended_focus=recommended_focus,

            # Detailed solution description
            selected_solution_details=selected_solution_details,
            solution_user_journey=solution_user_journey,
            # implementation_overview and mvp_scope set to None here, populated by LLM in _enhance_report_with_llm()
            solution_implementation_overview=None,
            mvp_scope_definition=None,

            # Pricing strategy (Stage 8)
            pricing_strategy=pricing_strategy,

            # Traffic monetization (Stage 8) - for directories/aggregators
            traffic_monetization=traffic_monetization,

            # Pain points (detailed_pain_points is source of truth)
            # top_pain_points and pain_point_categories removed
            pain_points_summary=pain_points_summary,
            detailed_pain_points=self.accessor.get_sorted_pain_points() if self.state.pain_point_analysis else None,

            # Solutions (ALL solutions, selected first)
            recommended_solutions=recommended_solutions if recommended_solutions else ["No solutions generated"],
            solutions_summary=solutions_summary,

            # Competitive analysis (summary only - full data in state.competitive_analysis)
            competitive_summary=competitive_summary,
            # Competitive analysis (full object - for frontend Competitors component)
            competitive_analysis=self.state.competitive_analysis,

            # Market validation (data-driven assessment)
            market_validation=market_validation,

            # Organic acquisition strategy (NEW - template-based)
            acquisition_strategy_summary=acquisition_strategy_summary,
            estimated_cac_breakdown=estimated_cac_breakdown,

            # Keyword validation & refinement (keyword validation and 8.85)
            keyword_validation_overview=keyword_validation_overview,
            solution_keyword_comparison=solution_keyword_comparison,
            content_strategy_preview=content_strategy_preview,

            # Data sourcing (summary only - full data in state.data_source_research)
            data_sourcing_recommendations=data_sourcing_recommendations,

            # Populated by _llm_next_steps(); empty list as fallback
            next_steps=[],

            # Data Richness Enhancements - Preserve Full Objects
            solution_innovation_assessment=solution_innovation_assessment,
            # solution_organic_discovery removed - use selected_solution_details
            # competitor_profiles populated in _generate_competitive_landscape_matrix()

            # REMOVED: ideation_process - not reliably populated

            # Competitive Strategic Insights (generated from landscape data)
            overall_competitive_insights=self._generate_competitive_insights(),

            # ========== FULL STAGE DATA (NEW - preserves complete pipeline outputs) ==========

            # Stage 1-4: Full Niche Context
            niche_context=self.state.niche_context,

            # Stage 6.5: Audience Intelligence (full object)
            audience_mapping=self.state.audience_mapping,

            # Stage 9: Market Sizing (full object, money strings unit-normalized)
            market_sizing=self._normalized_market_sizing(),

            # Stage 12: Trend Longevity (full object)
            trend_longevity=self.state.trend_longevity,

            # Stage 9: Full SEO Strategy (full object, not just analytics)
            seo_strategy_report=self.state.seo_strategy_report,

            # Catalog rebuild (Phase 5.4): pass-through topic clusters from the
            # SEO strategy report. Sourced top-level on FinalReport so the
            # catalog projection layer can read it without unwrapping the
            # broader seo_strategy_report. None when SEO crew failed or the
            # strategy report has no clusters yet.
            keyword_clusters=(
                self.state.seo_strategy_report.topic_clusters
                if self.state.seo_strategy_report
                else None
            ),

            # Stage 13: Full Data Source Research (full object, not just string summary)
            data_source_research_full=self.state.data_source_research,

            # Metadata
            generated_at=datetime.utcnow(),
        )

    def _normalized_market_sizing(self):
        """Stage-9 market sizing with every money string rendered in a unit that matches its
        magnitude (see `_rescale_money_text`).

        Stage 9 hands TAM/SAM/SOM over as free-form strings; the 2026-08-02 run shipped
        "$0.000227-$0.000454M" for a SAM the same section's prose called "$227-$454", and
        "$0.000001-$0.000009M" (≈$1-$9/yr) for the Year-1 SOM. Only the rendering changes —
        the dollar values are identical. Cached so the report and the GTM budget agree.
        """
        if getattr(self, "_normalized_ms_cache", None) is not None:
            return self._normalized_ms_cache

        market_sizing = self.state.market_sizing
        if market_sizing is None:
            return None

        try:
            updates = {}
            for field in _MARKET_SIZING_MONEY_FIELDS:
                original = getattr(market_sizing, field, None)
                rescaled = _rescale_money_text(original)
                if rescaled != original:
                    updates[field] = rescaled

            segments = getattr(market_sizing, "segment_sizing", None)
            if segments:
                new_segments = []
                segment_changed = False
                for segment in segments:
                    seg_updates = {}
                    for field in _SEGMENT_SIZING_MONEY_FIELDS:
                        original = getattr(segment, field, None)
                        rescaled = _rescale_money_text(original)
                        if rescaled != original:
                            seg_updates[field] = rescaled
                    if seg_updates:
                        segment_changed = True
                        new_segments.append(segment.model_copy(update=seg_updates))
                    else:
                        new_segments.append(segment)
                if segment_changed:
                    updates["segment_sizing"] = new_segments

            if updates:
                logger.info(
                    f"Market sizing: rescaled {len(updates)} money field(s) to units matching "
                    f"their magnitude"
                )
                market_sizing = market_sizing.model_copy(update=updates)
        except Exception as e:  # never let a formatting pass drop the section
            logger.warning(f"Market-sizing money normalization skipped (non-fatal): {e}")
            market_sizing = self.state.market_sizing

        self._normalized_ms_cache = market_sizing
        return market_sizing

    def _merge_solution_enrichments(
        self,
        base_solution: "BaseSolutionIdea | SolutionIdea",
        keyword_enrichment: "SolutionRefinement | None",
        seo_enrichment: "SolutionSEORefinement | None"
    ) -> "SolutionIdea":
        """
        Merge base solution with enrichments from later stages.

        This implements the unified enrichment pattern where:
        - Stage 7 creates BaseSolutionIdea with core fields (no enrichment fields)
        - Stage 10 outputs keyword enrichment (geographic priorities, features, insights)
        - Stage 12 outputs SEO enrichment (refined scores using keyword data)
        - Report generator merges all into complete SolutionIdea

        Benefits:
        - Base solutions remain immutable during pipeline
        - Each stage output is independently testable
        - Clear what data each stage contributes
        - No null fields in final output

        Args:
            base_solution: Original solution from Stage 7 (BaseSolutionIdea or legacy SolutionIdea)
            keyword_enrichment: Optional enrichment from Stage 10 (SolutionRefinementCrew)
            seo_enrichment: Optional enrichment from Stage 12 (Flow-based SEO refinement)

        Returns:
            Complete SolutionIdea with all available enrichments applied
        """
        from ..models.solution_idea import SolutionIdea

        # Create full SolutionIdea from base solution data
        # This upgrades BaseSolutionIdea to SolutionIdea, adding enrichment fields
        enriched = SolutionIdea(**base_solution.model_dump())

        # Apply keyword enrichment (Stage 10)
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

        # Apply SEO enrichment (Stage 12)
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

        # Apply pricing enrichment (Stage 8) — overwrite Stage 7 estimate with validated pricing
        if self.state.pricing_strategies:
            matching_pricing = next(
                (p for p in self.state.pricing_strategies
                 if p.solution_name == enriched.solution_name),
                None
            )
            if matching_pricing:
                enriched.pricing_strategy = matching_pricing.format_summary()
                logger.info(f"[Report] Applied pricing enrichment: {enriched.pricing_strategy}")

        # Enrich organic_discovery_queries with relevant validated SEO keywords (Stage 9)
        seo_report = getattr(self.state, 'seo_strategy_report', None)
        existing = enriched.organic_discovery_queries or []
        if seo_report and existing:
            # Collect tier_0 + tier_1 keywords, sorted by opportunity_score desc
            seo_keywords: list[tuple[str, float]] = []
            for kw in (seo_report.tier_0_keywords or []):
                seo_keywords.append((kw.keyword, kw.opportunity_score or 0.0))
            for kw in (seo_report.tier_1_keywords or []):
                seo_keywords.append((kw.keyword, kw.opportunity_score or 0.0))
            seo_keywords.sort(key=lambda x: x[1], reverse=True)

            # Build relevance terms from original LLM-generated queries
            relevance_terms: set[str] = set()
            for query in existing:
                for word in query.lower().split():
                    if len(word) > 3:
                        relevance_terms.add(word)

            existing_lower = {q.lower() for q in existing}
            max_seo_append = 5
            max_total = 10
            appended = []
            for keyword_text, _opp_score in seo_keywords:
                if len(appended) >= max_seo_append or len(existing) + len(appended) >= max_total:
                    break
                if keyword_text.lower() in existing_lower:
                    continue
                # Relevance check: SEO keyword must share a word with original queries
                keyword_words = {w for w in keyword_text.lower().split() if len(w) > 3}
                if keyword_words & relevance_terms:
                    appended.append(keyword_text)
                    existing_lower.add(keyword_text.lower())

            if appended:
                enriched.organic_discovery_queries = existing + appended
                logger.info(
                    f"[Report] Enriched organic_discovery_queries: "
                    f"{len(existing)} original + {len(appended)} SEO keywords "
                    f"= {len(enriched.organic_discovery_queries)} total"
                )

        return enriched

    def _sync_solution_scores(
        self,
        solution: "SolutionIdea",
    ) -> "SolutionIdea":
        """
        Sync solution scores and fields with final values via ScoreAccessor.

        Score Source: ScoreAccessor (single source of truth)
        - market_fit_score: ScoreAccessor.get_market_fit()
        - technical_feasibility_score: ScoreAccessor.get_technical_feasibility()
        - seo_scalability_score: ScoreAccessor.get_seo_score_canonical()

        Field Sync (Refined → Baseline):
        - estimated_cac_organic: from estimated_cac_organic_refined (Stage 12)
        - programmatic_seo_opportunity: from programmatic_seo_opportunity_refined (Stage 12)

        This ensures:
        1. selected_solution_details shows the SAME scores as executive_dashboard.key_metrics
        2. Frontend components only need to check baseline fields (no fallback chains)
        3. Refined Stage 12 values are used when available

        Args:
            solution: SolutionIdea to update (after _merge_solution_enrichments)

        Returns:
            SolutionIdea with scores and fields synced from authoritative sources
        """
        # Sync scores via ScoreAccessor (returns None when no data)
        solution.market_fit_score = self.score_accessor.get_market_fit(solution)
        solution.technical_feasibility_score = self.score_accessor.get_technical_feasibility(solution)
        solution.seo_scalability_score = self.score_accessor.get_seo_score_canonical(solution)

        # ScoreAccessor can replace the values used when tags were first derived.
        # Rebuild only the code-owned facets from those authoritative scores while
        # preserving the semantic facets already attached by the tagging step.
        solution.tags = refresh_tag_facets(solution)

        # Sync refined CAC to baseline (so frontend only needs one field)
        cac_refined = getattr(solution, 'estimated_cac_organic_refined', None)
        if cac_refined:
            solution.estimated_cac_organic = cac_refined
            logger.info(f"[Report] Using refined CAC: {cac_refined}")

        # Sync refined programmatic SEO opportunity to baseline
        seo_opp_refined = getattr(solution, 'programmatic_seo_opportunity_refined', None)
        if seo_opp_refined:
            solution.programmatic_seo_opportunity = seo_opp_refined
            logger.info(f"[Report] Using refined programmatic SEO: {seo_opp_refined[:50]}...")

        logger.info(
            f"[Report] Synced solution fields: "
            f"market_fit={solution.market_fit_score}, "
            f"tech_feasibility={solution.technical_feasibility_score}, "
            f"seo={solution.seo_scalability_score}, "
            f"cac={solution.estimated_cac_organic}"
        )

        return solution

    def _enrich_community_hubs(self, final_report: FinalReport) -> None:
        """Replace LLM-hallucinated community hubs with real subreddit data."""
        if not final_report.audience_mapping:
            return

        enriched = self.accessor.get_real_community_hubs(
            final_report.audience_mapping.community_hubs
        )
        if enriched != final_report.audience_mapping.community_hubs:
            final_report.audience_mapping.community_hubs = enriched
            logger.info(f"[OK] Enriched community_hubs with {len(enriched)} real entries")

    def _enhance_report_with_llm(self, base_report: FinalReport) -> FinalReport:
        """
        Enhance Python-generated report with LLM using 3 focused calls.

        Each call targets a specific domain to reduce hallucination risk:
        Call 1: Market narrative (executive_summary, acquisition_strategy_summary)
        Call 2: Next steps (next_steps — can reference implementation context)
        Call 3: Product planning (implementation_overview, mvp_scope_definition)
        """
        base_report = self._llm_market_narrative(base_report)
        base_report = self._llm_next_steps(base_report)
        base_report = self._llm_implementation_planning(base_report)
        return base_report

    def _llm_market_narrative(self, base_report: FinalReport) -> FinalReport:
        """LLM Call 1/3: Market narrative — executive_summary + acquisition_strategy_summary."""
        from ..utils.prompts import load_prompt

        details = base_report.selected_solution_details

        class MarketNarrative(BaseModel):
            executive_summary: str = Field(
                ..., description="4-6 sentence executive summary synthesizing the entire research"
            )
            acquisition_strategy_summary: str = Field(
                ..., description="2-3 paragraph overview of customer acquisition strategy emphasizing organic channels"
            )

        template = load_prompt("report_strategic_synthesis")
        pain_points = self.accessor.get_solution_pain_points(details) if details else []
        pain_point_titles = [pp.title for pp in pain_points[:3]]
        prompt = safe_format(template,
            niche=base_report.niche,
            selected_solution_name=base_report.selected_solution_name,
            pain_points_count=len(pain_points),
            market_validation=base_report.market_validation,
            seo_scalability=(
                details.seo_scalability_score * 10
                if details and details.seo_scalability_score is not None
                else 'N/A'
            ),
            selection_rationale=base_report.selection_rationale,
            top_pain_points=(
                ', '.join(pain_point_titles)
                or 'No validated pain point matched the selected solution.'
            ),
            project_type=details.project_type if details else 'N/A',
            indexable_pages=details.estimated_indexable_pages if details else 'N/A',
            cac_organic=details.estimated_cac_organic if details else 'N/A',
        )

        try:
            logger.info("LLM Call 1/3: Market narrative (2 fields)...")
            narrative, _usage = LLMService.invoke_structured(
                prompt=prompt, output_model=MarketNarrative, temperature=0.7
            )
            self._record_cost("Stage 14 - Market Narrative", _usage)
            base_report.executive_summary = narrative.executive_summary
            base_report.acquisition_strategy_summary = narrative.acquisition_strategy_summary
            logger.info("[OK] Market narrative complete")
        except Exception as e:
            logger.warning(f"Market narrative LLM failed: {e}. Using template-based fields.")

        return base_report

    def _llm_next_steps(self, base_report: FinalReport) -> FinalReport:
        """LLM Call 2/3: Next steps — context-aware action items."""
        from ..utils.prompts import load_prompt

        details = base_report.selected_solution_details

        class NextStepsResult(BaseModel):
            next_steps: list[str] = Field(
                ..., description="5-8 prioritized, specific action items for implementation"
            )

        template = load_prompt("report_next_steps")
        pain_points = self.accessor.get_solution_pain_points(details) if details else []
        pain_point_titles = [pp.title for pp in pain_points[:3]]
        prompt = safe_format(template,
            niche=base_report.niche,
            selected_solution_name=base_report.selected_solution_name,
            project_type=(details.project_type if details else None) or 'SaaS',
            core_features=', '.join((details.core_features if details else None) or [])[:200] or 'N/A',
            top_pain_points=(
                ', '.join(pain_point_titles)
                or 'No validated pain point matched the selected solution.'
            ),
            pricing_strategy=(details.pricing_strategy if details else None) or 'freemium',
            requires_data_aggregation=(details.requires_data_aggregation if details else None) or False,
            indexable_pages=(details.estimated_indexable_pages if details else None) or 'N/A',
        )

        try:
            logger.info("LLM Call 2/3: Next steps (1 field)...")
            result, _usage = LLMService.invoke_structured(
                prompt=prompt, output_model=NextStepsResult, temperature=0.7,
                model_name=settings.function_calling_llm
            )
            self._record_cost("Stage 14 - Next Steps", _usage)
            base_report.next_steps = result.next_steps
            logger.info("[OK] Next steps complete")
        except Exception as e:
            logger.warning(f"Next steps LLM failed: {e}. Keeping fallback next_steps.")

        return base_report

    def _llm_implementation_planning(self, base_report: FinalReport) -> FinalReport:
        """LLM Call 3/3: Product planning — implementation_overview + mvp_scope."""
        from ..utils.prompts import load_prompt

        details = base_report.selected_solution_details
        project_type = (details.project_type if details else None) or 'SaaS'
        core_features = (details.core_features if details else None) or []
        dev_time = (details.estimated_development_time if details else None) or 'TBD'
        tech_approach = (details.technical_approach if details else None) or 'N/A'
        pricing_strategy = (details.pricing_strategy if details else None) or 'freemium'

        class ImplementationPlanning(BaseModel):
            solution_implementation_overview: str = Field(
                ..., description="Markdown implementation overview with 3 phases tailored to the project type and core features"
            )
            mvp_scope_definition: str = Field(
                ..., description="Markdown MVP scope with must-have features and project-type-specific success criteria"
            )

        template = load_prompt("report_implementation_planning")
        prompt = safe_format(template,
            selected_solution_name=base_report.selected_solution_name,
            project_type=project_type,
            core_features=', '.join(core_features[:5]) if core_features else 'N/A',
            estimated_development_time=dev_time,
            technical_approach=tech_approach,
            requires_data_aggregation=(details.requires_data_aggregation if details else None) or False,
            pricing_strategy=pricing_strategy,
            content_generation_model=(details.content_generation_model if details else None) or 'N/A',
            indexable_pages=(details.estimated_indexable_pages if details else None) or 0,
        )

        try:
            logger.info("LLM Call 3/3: Implementation planning (2 fields)...")
            planning, _usage = LLMService.invoke_structured(
                prompt=prompt, output_model=ImplementationPlanning, temperature=0.7,
                model_name=settings.function_calling_llm
            )
            self._record_cost("Stage 14 - Implementation Planning", _usage)
            base_report.solution_implementation_overview = planning.solution_implementation_overview
            base_report.mvp_scope_definition = planning.mvp_scope_definition
            logger.info("[OK] Implementation planning complete")
        except Exception as e:
            logger.warning(f"Implementation planning LLM failed: {e}. Fields will be None.")

        return base_report

    def _generate_pain_solution_mappings(
        self,
        pain_points: list,
        solution: "SolutionIdea | None"
    ) -> dict[str, str]:
        """
        Generate LLM-based explanations of how the solution addresses each pain point.

        Uses settings.pain_solution_mapping_llm (gpt-4.1-mini) for structured output.

        Args:
            pain_points: List of PainPoint objects (top 10 used)
            solution: Selected SolutionIdea with features and value proposition

        Returns:
            Dictionary mapping pain point titles to solution approach explanations
        """
        from ..utils.prompts import load_prompt
        from .utils.report_pre_compute import format_pain_point_with_scores

        if not pain_points or not solution:
            return {}

        # Define minimal Pydantic models for mapping output
        # Note: OpenAI structured output doesn't support dict[str, str], so we use a list
        class PainSolutionItem(BaseModel):
            """Single pain point to solution mapping."""
            pain_point_title: str = Field(..., description="Exact title of the pain point")
            solution_approach: str = Field(..., description="1-2 sentence explanation of how the solution addresses this pain")

        class PainSolutionMapping(BaseModel):
            """List of pain point to solution mappings."""
            mappings: list[PainSolutionItem] = Field(
                ...,
                description="List of mappings from pain point titles to solution explanations"
            )

        # Format pain points for prompt (limit to top 10) with severity/WTP scores
        pain_points_to_map = pain_points[:10]
        pain_points_formatted = "\n".join(
            format_pain_point_with_scores(pp) for pp in pain_points_to_map
        )

        # Format core features
        core_features = solution.core_features or solution.key_features or []
        core_features_formatted = "\n".join([
            f"- {f}" for f in core_features[:8]
        ]) if core_features else "- General SaaS platform capabilities"

        # Load and format prompt
        try:
            template = load_prompt("pain_solution_mapping")
            prompt = safe_format(template,
                solution_name=solution.solution_name,
                value_proposition=solution.value_proposition or solution.description or "Comprehensive solution",
                core_features=core_features_formatted,
                pain_points_formatted=pain_points_formatted
            )

            logger.info(f"Generating pain-solution mappings for {len(pain_points_to_map)} pain points...")

            result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=PainSolutionMapping,
                temperature=0.5,  # Lower for consistency
                model_name=settings.pain_solution_mapping_llm
            )
            self._record_cost("Stage 14 - Pain-Solution Mapping", _usage)

            # Accept only exact titles supplied to the model. A hallucinated extra title must not
            # create a relationship the selected solution never claimed.
            allowed_titles = {pain.title for pain in pain_points_to_map}
            mappings_dict = {
                item.pain_point_title: item.solution_approach
                for item in result.mappings
                if item.pain_point_title in allowed_titles
            }
            logger.info(f"[OK] Generated {len(mappings_dict)} pain-solution mappings")
            return mappings_dict

        except Exception as e:
            logger.warning(f"Pain-solution mapping failed: {e}")
            return {}

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

            generic_posts_analyzed = len(social_content.generic_posts) if social_content.generic_posts else 0

            # A skipped stage is NOT a completed stage. research_flow._skip_stage appends to
            # BOTH completed_stages and skipped_stages (so resume doesn't re-run it), which
            # made the report claim stages 8 and 13 ran when they never did — and left the
            # reader trusting outputs (e.g. data_feasibility_score) that no stage produced.
            # The skip is surfaced as a caveat in _generate_data_quality_summary.
            skipped_stages = set(getattr(self.state, "skipped_stages", None) or [])
            completed_stages = [
                s for s in (self.state.completed_stages or []) if s not in skipped_stages
            ]

            return ResearchMetadata(
                reddit_posts_analyzed=reddit_posts_analyzed,
                reddit_comments_analyzed=reddit_comments_analyzed,
                twitter_threads_analyzed=twitter_threads_analyzed,
                generic_posts_analyzed=generic_posts_analyzed,
                top_subreddits=top_subreddits,
                collection_date=social_content.collection_timestamp,
                data_size_mb=round(data_size_mb, 2),
                # Phase 4: Include stage tracking data for diagnostic visibility
                completed_stages=completed_stages or None,
                fallback_stages=self.state.fallback_stages if self.state.fallback_stages else None,
                filtering_stats=self.state.filtering_stats,
                # Pipeline timing metadata
                started_at=self.state.started_at.isoformat() if self.state.started_at else None,
                funnel_counts=dict(getattr(self.state, "idea_funnel_counts", None) or {}),
            )
        except Exception as e:
            logger.warning(f"Failed to generate research metadata: {e}")
            return None

    # ==================================================================================
    # Phase 6: Data Quality & Pipeline Transparency Methods
    # ==================================================================================

    def _generate_data_quality_summary(self) -> DataQualitySummary | None:
        """
        Generate data quality summary from quality tiers and confidence scores.

        Computes overall quality from social content and pain point quality tiers.
        """
        try:
            # Get quality tiers from state
            social_tier = getattr(self.state, 'social_content_quality_tier', None)
            pain_tier = getattr(self.state, 'pain_point_quality_tier', None)
            confidence = getattr(self.state, 'pain_point_confidence_score', None)

            # Compute overall quality based on tiers
            quality_caveats: list[str] = []

            # Determine overall quality
            if self.state.seeded_from_catalog:
                # Catalog-seeded runs skip the social scrape, so the social
                # tier can never carry them past LOW under the standard
                # ladder. Rate them on the evidence they DO have — keyword
                # tiers + analyzed competitors — capped at MEDIUM (no fresh
                # social evidence can mean HIGH). The >= 1 competitor bar is
                # deliberately minimal; revisit if it proves too lenient.
                has_tier_keywords = bool(
                    self.state.seo_strategy_report
                    and (
                        self.state.seo_strategy_report.tier_0_keywords
                        or self.state.seo_strategy_report.tier_1_keywords
                    )
                )
                competitor_count = self.accessor.get_competitor_count()
                overall = "MEDIUM" if (has_tier_keywords and competitor_count >= 1) else "LOW"
                quality_caveats.append(
                    "Catalog-seeded research: pain points and personas come "
                    "from the catalog idea; fresh social evidence was not "
                    "collected. Quality is rated on keyword and competitor "
                    "evidence."
                )
            elif social_tier == "EXCELLENT" and pain_tier in ("GOLD", "SILVER"):
                overall = "HIGH"
            elif social_tier in ("EXCELLENT", "GOOD") and pain_tier in ("GOLD", "SILVER", "BRONZE"):
                overall = "MEDIUM"
            else:
                overall = "LOW"

            # Add caveats based on quality issues
            if social_tier == "MINIMAL":
                quality_caveats.append("Limited social content collected - results may be incomplete")
            if pain_tier == "BRONZE":
                quality_caveats.append("Pain point analysis used minimum viable data")

            # Add SEO-specific caveats for missing keyword tiers
            if self.state.seo_strategy_report:
                if not self.state.seo_strategy_report.tier_0_keywords:
                    quality_caveats.append("No premium (Tier 0) keywords found - market may be highly competitive")
                if not self.state.seo_strategy_report.tier_1_keywords:
                    quality_caveats.append("No quick-win (Tier 1) keywords found - SEO opportunities may be limited")

            # Add volume filter ratio caveat when niche-relevant volume is significantly less than total
            volume_filter_ratio = self.accessor.get_volume_filter_ratio()
            if volume_filter_ratio is not None and volume_filter_ratio < 0.5:
                niche = self.accessor.get_primary_search_volume()
                total = self.accessor.get_total_keyword_search_volume()
                quality_caveats.append(
                    f"Keyword volume filter ratio is {_format_percent(volume_filter_ratio)} — "
                    f"niche-relevant volume ({niche:,}) is significantly less than "
                    f"total SEO volume ({total:,}). Market validation uses the filtered volume."
                )

            if self.state.fallback_stages:
                fallback_names = [f"Stage {s}" for s in self.state.fallback_stages]
                quality_caveats.append(f"Fallback data used in: {', '.join(fallback_names)}")

            # Skipped stages: say so, by name. These are excluded from
            # research_metadata.completed_stages, but the reader also needs to know the
            # sections they would have produced are missing rather than empty.
            skipped_stages = sorted(set(getattr(self.state, "skipped_stages", None) or []))
            if skipped_stages:
                quality_caveats.append(
                    "Stages not run for this solution: "
                    f"{', '.join(_stage_label(s) for s in skipped_stages)}. "
                    "Sections that depend on them are absent from this report."
                )
                # Stage 13 produces the data-source research that a data-feasibility claim
                # rests on. When it never ran, the score and its calibration note are the
                # idea generator's own unverified assertion — say so rather than trust it.
                if 13 in skipped_stages:
                    _sol = (getattr(self, "_enriched_solution", None)
                            or self.accessor.get_selected_solution_details())
                    _dfs = getattr(_sol, "data_feasibility_score", None) if _sol else None
                    if _dfs is not None:
                        quality_caveats.append(
                            "Data feasibility was not independently researched: "
                            f"{_stage_label(13)} was skipped, so the data-feasibility score "
                            "and any named data sources come from the idea evaluation itself, "
                            "not from a verified sourcing pass. Treat them as unconfirmed."
                        )

            # Executive-dashboard degradations (see _generate_executive_dashboard). Recorded
            # there, surfaced here — a dashboard missing a section must not be silent.
            quality_caveats.extend(self._dashboard_caveats)

            if self.state.filtering_stats:
                filter_rate = self.state.filtering_stats.get("overall_filtering_rate", 0)
                if filter_rate > 0.7:
                    quality_caveats.append(f"High content filtering rate ({filter_rate:.0%}) - niche may be hard to research")

            # Niche-fidelity caveats (NON-scoring observability; tier/confidence
            # above are unchanged). Surface possible off-niche drift for review.
            drift = getattr(self.state, "niche_drift_telemetry", None)
            if not isinstance(drift, dict):
                drift = {}
            if drift.get("anchors_active") is False:
                quality_caveats.append(
                    "Niche-anchor extraction produced insufficient terms — drift "
                    "protection inactive for this run; verify results match the niche."
                )
            # Threshold 0.15 calibrated on real runs: a clearly-drifted run (GLP-1 /
            # generic-fitness evidence) scored ~0.05 here, while a clearly on-niche run
            # scored ~0.29. On-niche evidence often omits a literal anchor token
            # (contextually on-topic), so a higher bar produces false positives.
            ev_cov = drift.get("pain_evidence_anchor_coverage")
            if ev_cov is not None and ev_cov < 0.15:
                quality_caveats.append(
                    f"Niche-fidelity: only {_format_percent(ev_cov)} of supporting evidence mentions "
                    f"niche-specific terms — review for possible off-topic drift."
                )
            q_pct = drift.get("query_anchor_pct")
            if q_pct is not None and q_pct < 0.4:
                quality_caveats.append(
                    f"Only {_format_percent(q_pct)} of search queries were niche-anchored — "
                    f"collected content may include adjacent topics."
                )
            # Coverage gaps from idea generation (high-severity pains left uncovered).
            cov_caveats = getattr(self.state, "idea_coverage_caveats", None)
            if isinstance(cov_caveats, list):
                quality_caveats.extend(c for c in cov_caveats if isinstance(c, str))
            # Pipeline degradation ledger: every fail-open gate / silent quality reduction recorded
            # anywhere in the run (stance filter down, token pressure, …) surfaces here verbatim —
            # fail-open without surfacing is fail-silent. Deduped against what's already present.
            degradations = getattr(self.state, "pipeline_degradations", None)
            if isinstance(degradations, list):
                seen = set(quality_caveats)
                for d in degradations:
                    if isinstance(d, str) and d and d not in seen:
                        seen.add(d)
                        quality_caveats.append(d)

            return DataQualitySummary(
                social_content_quality_tier=social_tier,
                pain_point_quality_tier=pain_tier,
                pain_point_confidence_score=confidence,
                overall_data_quality=overall,
                quality_caveats=quality_caveats,
                examined_ruled_out=list(getattr(self.state, "idea_ruled_out", None) or []),
            )
        except Exception as e:
            logger.warning(f"Failed to generate data quality summary: {e}")
            return None

    def _generate_market_reality(self) -> dict | None:
        """Market-data handoff (see utils/market_brief.py): the Phase-1 web-verified incumbent
        map + niche wallet signal, surfaced once at the report's top level. None when neither
        probe found data (mirrors the preview report's always-present-but-empty shape)."""
        incumbents = list(getattr(self.state, "niche_incumbent_map", None) or [])
        wallet = dict(getattr(self.state, "niche_wallet_brief", None) or {})
        if not incumbents and not wallet:
            return None
        return {"incumbents": incumbents, "wallet": wallet}

    def _generate_refinement_highlights(self) -> RefinementHighlights | None:
        """
        Extract key strategic insights from Stage 10 solution refinement.
        """
        try:
            refinement = self.state.solution_refinement
            if not refinement:
                return None

            # Extract top strategic insights (limit to 5)
            insights = getattr(refinement, 'strategic_insights', []) or []
            top_insights = insights[:5] if insights else []

            # Extract geographic priority (first one if available)
            geo_priorities = getattr(refinement, 'geographic_priorities', []) or []
            geo_priority = geo_priorities[0] if geo_priorities else None

            # Extract feature priority (first one if available)
            # Note: feature_priorities is list[FeaturePriority], need to extract .feature_name string
            feature_priorities = getattr(refinement, 'feature_priorities', []) or []
            feature_priority = feature_priorities[0].feature_name if feature_priorities else None

            # Extract category pivot recommendation
            pivot_rec = getattr(refinement, 'category_pivot_recommendation', None)

            if not top_insights and not geo_priority and not feature_priority:
                return None

            return RefinementHighlights(
                top_strategic_insights=top_insights,
                geographic_priority=geo_priority,
                feature_priority=feature_priority,
                category_pivot_recommendation=pivot_rec,
            )
        except Exception as e:
            logger.warning(f"Failed to generate refinement highlights: {e}")
            return None

    def _generate_stage_timing_summary(self) -> StageTimingSummary | None:
        """
        Generate pipeline execution timing summary from stage completion timestamps.
        """
        try:
            # Interactive research pauses between Discovery and Deep Research while the
            # user chooses a shortlist. Completion-to-completion timestamps include that
            # human wait in the next stage, so presenting them as execution durations
            # would be materially misleading. Keep timing unavailable until split runs
            # record active per-stage durations directly.
            if getattr(self.state, "_user_selected_solutions", None):
                return None

            timestamps = self.state.stage_completion_timestamps
            if not timestamps or len(timestamps) < 2:
                return None

            # Calculate duration per stage
            stage_durations: dict[str, float] = {}
            sorted_stages = sorted(timestamps.items(), key=lambda x: x[1])

            for i in range(1, len(sorted_stages)):
                prev_stage, prev_time = sorted_stages[i - 1]
                curr_stage, curr_time = sorted_stages[i]
                duration = (curr_time - prev_time).total_seconds()
                stage_durations[curr_stage] = duration

            if not stage_durations:
                return None

            # Calculate total duration
            first_time = sorted_stages[0][1]
            last_time = sorted_stages[-1][1]
            total_duration = (last_time - first_time).total_seconds()

            # Find slowest and fastest
            slowest = max(stage_durations.items(), key=lambda x: x[1])
            fastest = min(stage_durations.items(), key=lambda x: x[1])

            return StageTimingSummary(
                total_duration_seconds=total_duration,
                stage_durations=stage_durations,
                slowest_stage=f"Stage {slowest[0]} ({slowest[1]:.1f}s)",
                fastest_stage=f"Stage {fastest[0]} ({fastest[1]:.1f}s)",
            )
        except Exception as e:
            logger.warning(f"Failed to generate stage timing summary: {e}")
            return None

    def _generate_seo_calculation_transparency(self) -> SEOCalculationTransparency | None:
        """
        Extract SEO score calculation methodology from Stage 12 enrichment.
        """
        try:
            enrichment = self.state.seo_enrichment
            if not enrichment:
                return None

            # Get baseline from selected solution
            # Note: find_solution_by_name(solution_name: str, solution_list: list)
            selected_solution = find_solution_by_name(
                self.state.solution_selection.selected_solution_name if self.state.solution_selection else None,
                self.state.idea_generation.solution_ideas if self.state.idea_generation else []
            )
            baseline_score = getattr(selected_solution, 'seo_scalability_score', None) if selected_solution else None

            # Get refined score and metadata from enrichment
            refined_score = getattr(enrichment, 'seo_scalability_score_refined', None)
            metadata_obj = getattr(enrichment, 'seo_refinement_metadata', None)

            # Convert Pydantic model to dict if needed, otherwise use empty dict
            if metadata_obj is not None and hasattr(metadata_obj, 'model_dump'):
                metadata = metadata_obj.model_dump()
            elif isinstance(metadata_obj, dict):
                metadata = metadata_obj
            else:
                metadata = {}

            # Build rationale string
            rationale_parts = []
            if metadata.get('volume_multiplier'):
                rationale_parts.append(f"Volume multiplier: {metadata['volume_multiplier']:.2f}x")
            if metadata.get('tier1_multiplier'):
                rationale_parts.append(f"Tier1 bonus: {metadata['tier1_multiplier']:.2f}x")
            if metadata.get('competition_modifier'):
                rationale_parts.append(f"Competition factor: {metadata['competition_modifier']:.2f}")
            if metadata.get('floor_applied'):
                rationale_parts.append(f"Keyword evidence floor: {metadata['keyword_evidence_floor']:.2f}")
            if metadata.get('min_competition_modifier_applied'):
                rationale_parts.append(f"Competition modifier floored (raw: {metadata.get('raw_competition_modifier', 'N/A')})")

            rationale = " | ".join(rationale_parts) if rationale_parts else None

            return SEOCalculationTransparency(
                baseline_seo_score=baseline_score,
                refined_seo_score=refined_score,
                volume_multiplier=metadata.get('volume_multiplier'),
                competition_modifier=metadata.get('competition_modifier'),
                tier1_multiplier=metadata.get('tier1_multiplier'),
                estimated_year1_pages=metadata.get('estimated_year1_pages'),
                calculation_rationale=rationale,
                keyword_evidence_floor=metadata.get('keyword_evidence_floor'),
                floor_applied=metadata.get('floor_applied'),
                floor_reason=metadata.get('floor_reason'),
            )
        except Exception as e:
            logger.warning(f"Failed to generate SEO calculation transparency: {e}")
            return None

    def _build_pivot_trigger(
        self,
        runner_up_name: str,
        runner_up_scores: dict[str, float],
        selected_scores: dict[str, float] | None,
        *,
        key_differentiator: str = "",
        project_type: str | None = None,
        selected_project_type: str | None = None,
        competitive_intensity: str | None = None,
        solo_dev_feasibility: float | None = None,
        selected_solo_dev: float | None = None,
    ) -> str:
        """
        Build a data-driven pivot trigger by comparing runner-up scores against the selected solution.

        Uses relative deltas rather than absolute thresholds so runner-up solutions
        get meaningful pivot guidance even when their raw scores are moderate.

        Args:
            runner_up_name: Name of the runner-up solution
            runner_up_scores: Dict from ScoreAccessor.get_all_scores() for the runner-up
            selected_scores: Dict from ScoreAccessor.get_all_scores() for the selected solution,
                             or None if the selected solution was not found
            key_differentiator: Runner-up's key differentiator text
            project_type: Runner-up's project type
            selected_project_type: Selected solution's project type
            competitive_intensity: Runner-up's competitive intensity (LOW/MEDIUM/HIGH)
            solo_dev_feasibility: Runner-up's solo dev feasibility score
            selected_solo_dev: Selected solution's solo dev feasibility score

        Returns:
            Data-driven pivot trigger string with scores and reasoning
        """
        from ..utils.score_helpers import score_band  # plain bands — never the raw decimal in user text
        prefix = f"Pivot to {runner_up_name} if: "

        # If no selected scores available, use lower absolute thresholds as fallback
        if selected_scores is None:
            conditions = []
            mf = runner_up_scores.get("market_fit")
            sg = runner_up_scores.get("seo_growth")
            tf = runner_up_scores.get("technical_feasibility")
            if mf is not None and mf > 0.65:
                conditions.append(f"{score_band(mf)} market fit suggests strong demand")
            if sg is not None and sg > 0.60:
                conditions.append(f"{score_band(sg)} SEO growth potential indicates a viable organic channel")
            if tf is not None and tf > 0.65:
                conditions.append(f"{score_band(tf)} technical feasibility enables faster time-to-market")
            if conditions:
                return prefix + "; ".join(conditions) + "."
            return (
                f"Pivot to {runner_up_name} if customer discovery validates demand. "
                f"Scores not yet compared against selected solution."
            )

        # Check if all scores are defaults (0.5) or None — data not yet validated
        check_keys = ("market_fit", "seo_growth", "technical_feasibility", "competitive_advantage")
        all_default = all(
            (runner_up_scores.get(k) is None or abs(runner_up_scores.get(k) - 0.5) < 0.01)
            and (selected_scores.get(k) is None or abs(selected_scores.get(k) - 0.5) < 0.01)
            for k in check_keys
        )
        if all_default:
            differentiator_note = f" Key differentiator: {key_differentiator}." if key_differentiator else ""
            return (
                f"Pivot to {runner_up_name} if: Scores not yet validated — "
                f"pivot decision should be based on customer discovery.{differentiator_note}"
            )

        # Compute deltas: positive means runner-up is stronger
        dimension_labels = {
            "market_fit": "market fit",
            "seo_growth": "SEO growth potential",
            "technical_feasibility": "technical feasibility",
            "competitive_advantage": "competitive advantage",
        }

        strong_signals = []    # delta > 0.05
        near_parity = []       # |delta| <= 0.05
        moderate_gaps = []     # -0.15 <= delta < -0.05

        for key, label in dimension_labels.items():
            ru_val = runner_up_scores.get(key)
            sel_val = selected_scores.get(key)
            if ru_val is None or sel_val is None:
                continue  # skip dimension with missing data
            delta = ru_val - sel_val

            if delta > 0.05:
                strong_signals.append((label, ru_val, sel_val, delta))
            elif abs(delta) <= 0.05:
                near_parity.append((label, ru_val, sel_val, delta))
            elif delta >= -0.15:
                moderate_gaps.append((label, ru_val, sel_val, delta))
            # delta < -0.15: skip (too far behind)

        parts = []

        # The category labels already encode the comparison direction, so the dimension names alone
        # carry the meaning — no raw scores in user-facing text.
        if strong_signals:
            parts.append("Strong pivot signal — the runner-up leads on "
                         + ", ".join(label for label, *_ in strong_signals))

        if near_parity:
            parts.append("Near-parity on " + ", ".join(label for label, *_ in near_parity))

        if moderate_gaps:
            parts.append("Worth monitoring " + ", ".join(label for label, *_ in moderate_gaps))

        # Contextual (non-score) signals
        contextual = []
        if competitive_intensity and competitive_intensity.upper() == "LOW":
            contextual.append("less saturated market segment")
        if (
            solo_dev_feasibility is not None
            and selected_solo_dev is not None
            and (solo_dev_feasibility - selected_solo_dev) > 0.15
        ):
            contextual.append("easier solo-dev path")
        if (
            project_type
            and selected_project_type
            and project_type.lower() != selected_project_type.lower()
        ):
            contextual.append(f"if user research favors {project_type} model")

        if contextual:
            parts.append("Also consider: " + ", ".join(contextual))

        if parts:
            return prefix + ". ".join(parts) + "."

        # Ultimate fallback: all dimensions behind, but still data-driven
        # Find the dimension with the smallest gap
        best_dim = None
        best_delta = -float("inf")
        for key, label in dimension_labels.items():
            ru_val = runner_up_scores.get(key)
            sel_val = selected_scores.get(key)
            if ru_val is None or sel_val is None:
                continue  # skip dimension with missing data
            delta = ru_val - sel_val
            if delta > best_delta:
                best_delta = delta
                best_dim = (label, ru_val, sel_val, delta)

        if best_dim:
            label, ru_val, sel_val, delta = best_dim
            differentiator_note = f" Key differentiator: {key_differentiator}." if key_differentiator else ""
            return (
                f"Pivot to {runner_up_name} if: its closest dimension is "
                f"{label} — validation would need to close the gap in the other areas.{differentiator_note}"
            )

        # Should not reach here, but defensive
        return (
            f"Pivot to {runner_up_name} if validation reveals "
            f"stronger market demand or competitive positioning."
        )

    def _generate_alternative_solutions(self) -> list["AlternativeSolution | None"]:
        """
        Generate enhanced alternative solution summaries for runner-up solutions.

        Returns:
            List of AlternativeSolution objects (top 4 runner-ups with full details including
            competitive analysis, core features, and economic indicators)
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

            # Find full solution details from idea_generation stage (demoted/absorbed excluded —
            # never surface a hidden idea as an alternative)
            from ..models.solution_idea import visible_ideas
            all_solutions = {idea.solution_name: idea for idea in visible_ideas(idea_generation.solution_ideas)}

            # Build competitive landscapes map for enhanced alternative solutions
            competitive_landscapes = {}
            if self.state.competitive_analysis:
                for landscape in self.state.competitive_analysis.solution_landscapes:
                    competitive_landscapes[landscape.solution_name] = landscape

            # Honest brief: pain-title → verbatim community quotes lookup (evidence half)
            from ..utils.honest_brief import build_quotes_by_pain
            pain_analysis = getattr(self.state, 'pain_point_analysis', None)
            quotes_by_pain = build_quotes_by_pain(getattr(pain_analysis, 'pain_points', None))

            # Fetch selected solution and its scores for relative comparison
            selected_solution = self.accessor.get_selected_solution_details()
            selected_scores = None
            selected_project_type = None
            selected_solo_dev = None
            if selected_solution:
                selected_scores = self.score_accessor.get_all_scores(selected_solution)
                selected_project_type = getattr(selected_solution, 'project_type', None)
                selected_solo_dev = getattr(selected_solution, 'solo_dev_feasibility', None)
                if isinstance(selected_solo_dev, (int, float)):
                    selected_solo_dev = float(selected_solo_dev)
                else:
                    selected_solo_dev = None

            selected_solution_name = getattr(solution_selection, 'selected_solution_name', None)

            alternative_solutions = []
            # Top 8 runners-up (was 4): the portfolio funnel (salvage + bundles) widens the pool to
            # ~6-12, and alternatives are the report's main breadth — bounded by pool size anyway.
            for runner_up_name in runner_up_names[:8]:
                if runner_up_name == selected_solution_name:
                    continue
                if runner_up_name not in all_solutions:
                    logger.warning(f"Runner-up solution '{runner_up_name}' not found in idea generation results")
                    continue

                solution = all_solutions[runner_up_name]

                description = solution.description or ""
                tech_approach = solution.technical_approach or ""

                key_differentiator = solution.differentiation_factors[0] if solution.differentiation_factors else ""
                diff_text = key_differentiator or ""

                best_suited_for = solution.target_personas[0] if solution.target_personas else ""
                personas_text = ', '.join(solution.target_personas[:2]) if solution.target_personas else ""

                features_text = ', '.join(solution.core_features[:5]) if solution.core_features else ""

                # Generate 2-3 paragraph summary with validated inputs
                summary = f"""**Overview:** {description}

**Key Features:** {features_text}

**Target Users:** This solution is best suited for {personas_text}.
It differentiates through {diff_text}.

**Technical Approach:** {tech_approach}
"""

                # Ensure summary is not empty after stripping
                summary = summary.strip()
                if not summary:
                    summary = f"{solution.solution_name}: Alternative solution option for this market"

                # Use ScoreAccessor for consistent score extraction with automatic fallback
                market_fit = self.score_accessor.get_market_fit(solution)
                technical_feasibility = self.score_accessor.get_technical_feasibility(solution)
                competitive_advantage = self.score_accessor.get_competitive_advantage(solution)
                seo_growth = self.score_accessor.get_seo_growth(solution)
                tag_source = solution.model_copy(update={
                    "market_fit_score": market_fit,
                    "technical_feasibility_score": technical_feasibility,
                    "seo_scalability_score": seo_growth,
                })
                alternative_tags = refresh_tag_facets(tag_source)

                # Get competitive landscape for this solution
                landscape = competitive_landscapes.get(runner_up_name)

                # Extract competitive details from landscape
                top_competitors = None
                market_gaps = None
                competitive_intensity = None

                if landscape:
                    if landscape.competitors:
                        top_competitors = [c.name for c in landscape.competitors[:3]]
                    if landscape.market_gaps:
                        market_gaps = landscape.market_gaps[:3]
                    competitive_intensity = landscape.competitive_intensity

                # Pass through solo_dev_feasibility as float (no conversion needed)
                solo_dev_feasibility_val = getattr(solution, 'solo_dev_feasibility', None)
                if isinstance(solo_dev_feasibility_val, (int, float)):
                    solo_dev_feasibility_val = float(solo_dev_feasibility_val)
                else:
                    solo_dev_feasibility_val = None

                # Build pivot trigger using relative comparison against selected solution
                runner_up_scores = self.score_accessor.get_all_scores(solution)
                pivot_trigger = self._build_pivot_trigger(
                    runner_up_name=runner_up_name,
                    runner_up_scores=runner_up_scores,
                    selected_scores=selected_scores,
                    key_differentiator=key_differentiator,
                    project_type=getattr(solution, 'project_type', None),
                    selected_project_type=selected_project_type,
                    competitive_intensity=competitive_intensity,
                    solo_dev_feasibility=solo_dev_feasibility_val,
                    selected_solo_dev=selected_solo_dev,
                )

                # Honest brief: evidence quotes for the addressed pains + the critic's voice
                from ..utils.calibration_notes import extract_criterion_reason
                from ..utils.honest_brief import demand_quotes_for
                demand_quotes = demand_quotes_for(
                    getattr(solution, 'pain_points_addressed', None), quotes_by_pain)
                critic_concern = extract_criterion_reason(
                    getattr(solution, 'calibration_notes', None), "market_fit", max_len=280)

                # Pass through estimated_cac_organic as string (no conversion needed)
                estimated_cac_organic_val = getattr(solution, 'estimated_cac_organic', None)
                if isinstance(estimated_cac_organic_val, (int, float)):
                    estimated_cac_organic_val = f"${estimated_cac_organic_val:.0f}"
                elif isinstance(estimated_cac_organic_val, str):
                    estimated_cac_organic_val = estimated_cac_organic_val
                else:
                    estimated_cac_organic_val = None

                from ..models.solution_idea import effective_red_team_state
                red_team_verdict, red_team_findings = effective_red_team_state(solution)

                alternative_solutions.append(AlternativeSolution(
                    # Existing fields (using pre-validated variables)
                    solution_name=solution.solution_name,
                    idea_id=getattr(solution, 'idea_id', None),
                    idea_revision=getattr(solution, 'idea_revision', 1),
                    identity_origin=getattr(solution, 'identity_origin', None),
                    identity_operation_id=getattr(
                        solution, 'identity_operation_id', None,
                    ),
                    headline=getattr(solution, 'headline', None),
                    short_description=getattr(solution, 'short_description', None),
                    summary=summary,  # Already stripped and validated above
                    market_fit_score=market_fit,
                    technical_feasibility_score=technical_feasibility,
                    competitive_advantage_score=competitive_advantage,
                    seo_growth_potential_score=seo_growth,
                    key_differentiator=key_differentiator,  # Pre-extracted with fallback
                    best_suited_for=best_suited_for,  # Pre-extracted with fallback
                    pivot_trigger=pivot_trigger,

                    # NEW: Core solution details
                    description=solution.description,
                    value_proposition=solution.value_proposition,
                    core_features=solution.core_features[:5] if solution.core_features else None,
                    target_personas=solution.target_personas[:3] if solution.target_personas else None,
                    technical_approach=solution.technical_approach,
                    delivery_format=getattr(solution, 'delivery_format', None),

                    # NEW: Additional scores and feasibility
                    novelty_score=getattr(solution, 'novelty_score', None),
                    solo_dev_feasibility=solo_dev_feasibility_val,  # Pass-through float
                    # Angle-aware evaluation (pass-through; None when angle eval is off)
                    idea_tier=getattr(solution, 'idea_tier', None) or "single",
                    candidate_status=getattr(solution, 'candidate_status', None) or "active",
                    merged_from=getattr(solution, 'merged_from', None),
                    winning_angle=getattr(solution, 'winning_angle', None),
                    angle_rationale=getattr(solution, 'angle_rationale', None),
                    novelty_rationale=getattr(solution, 'novelty_rationale', None),
                    differentiation_locus=getattr(solution, 'differentiation_locus', None),
                    # Data feasibility (annotate-only; from the ideation critic, may be None)
                    data_feasibility_score=getattr(solution, 'data_feasibility_score', None),
                    data_access_model=getattr(solution, 'data_access_model', None),
                    data_acquisition_notes=getattr(solution, 'data_acquisition_notes', None),
                    build_feasibility_score=getattr(solution, 'build_feasibility_score', None),

                    # NEW: Competitive landscape for this solution
                    top_competitors=top_competitors,
                    market_gaps=market_gaps,
                    competitive_intensity=competitive_intensity,

                    # NEW: Economic indicators
                    estimated_development_time=getattr(solution, 'estimated_development_time', None),
                    estimated_cac_organic=estimated_cac_organic_val,  # Pass-through string
                    pricing_model=getattr(solution, 'pricing_model', None),

                    # Phase 8 of detail-page IA rework — copy pain_points_addressed
                    # from the source BaseSolutionIdea so alternatives can be
                    # cross-linked to specific pains on the catalog UI. Defaults
                    # to [] when the source is missing the field (legacy reports).
                    pain_points_addressed=list(getattr(solution, 'pain_points_addressed', []) or []),

                    # Honest brief: evidence + the critic's voice (None when unavailable
                    # so legacy reports and quote-less pains render unchanged)
                    demand_quotes=demand_quotes or None,
                    critic_concern=critic_concern or None,
                    refine_binding_constraint=getattr(solution, 'refine_binding_constraint', None),
                    incumbent_parity=getattr(solution, 'incumbent_parity', None),
                    adjacent_market_parity=getattr(solution, 'adjacent_market_parity', None),
                    # Adversarial red-team pass (mirrors the preview-report threading in
                    # research_flow._materialize_preview_report — the final report was
                    # silently dropping these via AlternativeSolution's extra='ignore').
                    red_team_verdict=red_team_verdict,
                    red_team_caveats=list(getattr(solution, 'red_team_caveats', None) or []) or None,
                    red_team_findings=red_team_findings,
                    # Lets the UI explain a missing acquisition-cost figure instead of
                    # hiding the row: a rebuilt product's old CAC describes a product that
                    # no longer exists, and the rebuild cannot re-ground a new one.
                    rebuild_origin=getattr(solution, 'rebuild_origin', None),
                    source_segment_payability=getattr(solution, 'source_segment_payability', None),
                    source_segment_payability_class=getattr(solution, 'source_segment_payability_class', None),
                    # Multi-Frame Idea Generation Portfolio: which frame minted this idea's cell
                    source_frame=getattr(solution, 'source_frame', None),
                    evaluation_id=getattr(solution, 'evaluation_id', None),
                    evaluation_source_message_id=getattr(solution, 'evaluation_source_message_id', None),
                    proposed_title=getattr(solution, 'proposed_title', None),
                    synthesis_evaluation=getattr(solution, 'synthesis_evaluation', None),
                    generation_operation_id=getattr(solution, 'generation_operation_id', None),
                    generation_batch_ordinal=getattr(solution, 'generation_batch_ordinal', None),

                    # Closed-vocabulary filter facets (chips + future filtering).
                    tags=alternative_tags,
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

            # A landscape the relevance guard stamped `off_niche_caveat` is retained verbatim
            # upstream (downgrade-only, never rewritten) but must not be treated as a MEASUREMENT
            # here. Live audit 2026-08-03: the winner's landscape came back as Mint + YNAB —
            # personal-finance apps, produced with zero web searches — and because it was counted
            # like any other, it drove competitor_count=2 -> market_saturation_score=0.2 ->
            # competitive_intensity "Low" -> 5 market gaps, i.e. the report told the reader the
            # space was uncrowded on the strength of the fabrication.
            off_niche = [
                ls.solution_name for ls in self.state.competitive_analysis.solution_landscapes
                if getattr(ls, "off_niche_caveat", None)
            ]
            for landscape in self.state.competitive_analysis.solution_landscapes:
                if getattr(landscape, "off_niche_caveat", None):
                    logger.warning(
                        f"[CompetitiveMatrix] excluding off-niche landscape from saturation "
                        f"math: '{landscape.solution_name}' — {landscape.off_niche_caveat}"
                    )
                    continue

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

            # Create competitor matrix entries (selected solution's competitors)
            competitor_overlap = [
                CompetitorMatrixEntry(
                    competitor_name=name,
                    solutions_competed=data["solutions"],
                    competitor_type=data["type"],
                    threat_level=data["threat_level"]
                )
                for name, data in competitor_appearances.items()
            ]

            # Sort by number of solutions competed (most versatile competitors first)
            competitor_overlap.sort(key=lambda x: len(x.solutions_competed), reverse=True)

            # Generate market insight
            intensity_counts = {}
            for entry in competitive_intensity_list:
                intensity_counts[entry.intensity] = intensity_counts.get(entry.intensity, 0) + 1

            solution_word = "concept" if len(all_solutions) == 1 else "concepts"
            market_insight = f"Analyzed {len(all_solutions)} solution {solution_word} across the competitive landscape. "
            if intensity_counts:
                market_insight += f"Competitive intensity distribution: {', '.join(f'{k}: {v}' for k, v in intensity_counts.items())}. "
            if competitor_overlap:
                market_insight += f"{len(competitor_overlap)} competitor{'s' if len(competitor_overlap) != 1 else ''} identified in the competitive landscape. "
                top_competitor = competitor_overlap[0]
                market_insight += f"Most versatile competitor: {top_competitor.competitor_name} (competes in {len(top_competitor.solutions_competed)} solution categories)."

            # Say it in the report, not only in the log: a reader who sees a thin competitor
            # set must be told it is thin because a landscape was rejected, not because the
            # market is empty.
            if off_niche:
                market_insight += (
                    f" Competitive coverage is incomplete: the landscape for "
                    f"{', '.join(off_niche)} did not match this niche and was excluded from "
                    f"these counts, so treat competitor coverage here as unverified rather "
                    f"than as evidence of an empty market."
                )

            # Extract selected solution's direct competitors for executive summary. Suppressed
            # when the selected landscape itself was flagged — naming fabricated competitors in
            # the executive summary is the most load-bearing place they could appear.
            selected_competitors: list[str] = []
            selected_landscape = self.accessor.get_selected_landscape()
            if (
                selected_landscape
                and selected_landscape.competitors
                and not getattr(selected_landscape, "off_niche_caveat", None)
            ):
                selected_competitors = [c.name for c in selected_landscape.competitors]

            return CompetitiveLandscapeMatrix(
                all_solutions_analyzed=all_solutions,
                selected_solution_competitors=selected_competitors,
                competitor_overlap=competitor_overlap,
                competitive_intensity_by_solution=competitive_intensity_list,
                market_insight=market_insight
            )
        except Exception as e:
            logger.warning(f"Failed to generate competitive landscape matrix: {e}")
            return None

    def _generate_competitive_insights(self) -> str | None:
        """Generate overall competitive insights from the selected solution's landscape data.

        Returns formatted 2-3 paragraph string, or None if no landscape data.
        No LLM call — programmatic generation from structured data.
        """
        try:
            selected_landscape = self.accessor.get_selected_landscape()
            if not selected_landscape:
                return None

            paragraphs = []

            # Paragraph 1: Overview and intensity
            comp_count = len(selected_landscape.competitors) if selected_landscape.competitors else 0
            intensity = selected_landscape.competitive_intensity
            p1 = (
                f"The competitive landscape for {selected_landscape.solution_name} shows "
                f"{intensity} competitive intensity with {comp_count} identified "
                f"competitor{'s' if comp_count != 1 else ''}."
            )
            if selected_landscape.recommended_positioning:
                p1 += f" {selected_landscape.recommended_positioning}"
            paragraphs.append(p1)

            # Paragraph 2: Market gaps and differentiation
            if selected_landscape.market_gaps:
                gaps = selected_landscape.market_gaps[:5]
                p2 = f"Key market gaps identified: {'; '.join(gaps)}."
                if selected_landscape.differentiation_opportunities:
                    opps = selected_landscape.differentiation_opportunities[:3]
                    p2 += f" Top differentiation opportunities include: {'; '.join(opps)}."
                paragraphs.append(p2)

            # Paragraph 3: Pricing insights
            if selected_landscape.pricing_insights:
                paragraphs.append(f"Pricing landscape: {selected_landscape.pricing_insights}")

            return "\n\n".join(paragraphs) if paragraphs else None
        except Exception as e:
            logger.warning(f"Failed to generate competitive insights: {e}")
            return None

    def _build_competitor_profiles(self) -> list["CompetitorCard"]:
        """
        Build detailed competitor profiles for the selected solution.

        Returns:
            List of CompetitorCard objects with full competitor details
        """
        from ..models.research_state import CompetitorCard

        competitor_profiles = []

        try:
            selected_landscape = self.accessor.get_selected_landscape()
            if selected_landscape and selected_landscape.competitors:
                for comp in selected_landscape.competitors[:5]:  # Top 5 competitors
                    # Handle competitor_type which may be an enum
                    comp_type = comp.competitor_type
                    if hasattr(comp_type, 'value'):
                        comp_type = comp_type.value
                    elif hasattr(comp_type, 'name'):
                        comp_type = comp_type.name
                    else:
                        comp_type = str(comp_type)

                    # Normalize position to lowercase one of leader/challenger/niche.
                    raw_pos = getattr(comp, 'position', None)
                    position = None
                    if isinstance(raw_pos, str):
                        normalized = raw_pos.strip().lower()
                        if normalized in {'leader', 'challenger', 'niche'}:
                            position = normalized
                        else:
                            logger.warning(
                                f"Competitor '{comp.name}' has unrecognized position "
                                f"'{raw_pos}' — dropping. Expected leader/challenger/niche."
                            )

                    competitor_profiles.append(CompetitorCard(
                        name=comp.name,
                        url=comp.url,
                        competitor_type=comp_type,
                        description=comp.description,
                        key_features=comp.key_features or [],
                        pricing_model=comp.pricing_model,
                        strengths=comp.strengths or [],
                        weaknesses=comp.weaknesses or [],
                        position=position,
                    ))

            return competitor_profiles

        except Exception as e:
            logger.warning(f"Failed to build competitor profiles: {e}")
            return []

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase, collapse whitespace, strip."""
        return re.sub(r'\s+', ' ', text.lower().strip())

    @staticmethod
    def _flatten_comments(comments: list, _depth: int = 0) -> list:
        """Recursively flatten nested RedditComment trees.

        Args:
            comments: List of RedditComment objects (with .replies)
            _depth: Current recursion depth (safety guard)

        Returns:
            Flat list of all RedditComment objects
        """
        if _depth > 5:
            return []
        flat = []
        for comment in comments:
            flat.append(comment)
            if comment.replies:
                flat.extend(ReportGenerator._flatten_comments(comment.replies, _depth + 1))
        return flat

    @staticmethod
    def _flatten_generic_responses(responses: list, _depth: int = 0) -> list:
        """Recursively flatten nested SocialResponse trees."""
        if _depth > 3:
            return []
        flat = []
        for resp in responses:
            flat.append(resp)
            if resp.replies:
                flat.extend(ReportGenerator._flatten_generic_responses(resp.replies, _depth + 1))
        return flat

    @staticmethod
    def _fuzzy_match_quote(
        quote: str,
        content_index: list[tuple[str, str]],
        min_length: int = 30,
    ) -> str | None:
        """Substring containment match for a quote against indexed content.

        Args:
            quote: The cleaned quote text to match
            content_index: List of (normalized_text, post_id) tuples
            min_length: Minimum normalized quote length to attempt matching

        Returns:
            post_id if a match is found, None otherwise
        """
        normalized_quote = re.sub(r'\s+', ' ', quote.lower().strip())
        # Strip leading/trailing quote marks (use regex, not str.strip)
        normalized_quote = re.sub(r'^["\']+|["\']+$', '', normalized_quote)
        normalized_quote = re.sub(r'^\.{2,}|\.{2,}$', '', normalized_quote).strip()

        if len(normalized_quote) < min_length:
            return None

        for content_text, post_id in content_index:
            if normalized_quote in content_text:
                return post_id

        return None

    def _generate_evidence_appendix(self) -> "EvidenceAppendix | None":
        """
        Generate evidence appendix with top Reddit threads and pain point quote sources.

        Uses a 2-tier resolution strategy for quote→source mapping:
        - Tier 0: Parallel source_post_ids array (primary)
        - Tier 1: Fuzzy substring match against original content (fallback)

        Returns:
            EvidenceAppendix with traceability from pain points to original posts
        """
        if not self.state.social_content or not self.state.pain_point_analysis:
            return None

        try:
            # Multi-source headline threads ranked by platform-FAIR normalized engagement (Reddit +
            # Hacker News + Twitter), not Reddit-only by raw upvotes. normalize_engagement only reads
            # .platform/.score/.num_responses/.raw_engagement, so each source is duck-typed.
            from types import SimpleNamespace
            from ..utils.engagement_normalizer import normalize_engagement
            _plat = {"hackernews": "Hacker News", "youtube": "YouTube"}
            candidates: list[tuple[float, TopRedditThread]] = []
            for post in self.state.social_content.reddit_posts:
                eng = normalize_engagement(SimpleNamespace(
                    platform="reddit", score=post.score, num_responses=post.num_comments,
                    raw_engagement={"upvotes": post.score, "num_comments": post.num_comments}))
                candidates.append((eng, TopRedditThread(
                    post_id=post.post_id, title=post.title, subreddit=f"r/{post.subreddit}",
                    platform="reddit", score=post.score, num_comments=post.num_comments, url=post.url,
                    created_utc=post.created_utc,
                    key_insight=f"High-engagement discussion in r/{post.subreddit} ({post.score} upvotes, {post.num_comments} comments)")))
            for post in (self.state.social_content.generic_posts or []):
                label = _plat.get(post.platform, post.platform)
                candidates.append((normalize_engagement(post), TopRedditThread(
                    post_id=post.post_id, title=post.title, subreddit=label, platform=post.platform,
                    score=post.score, num_comments=post.num_responses, url=post.url,
                    created_utc=getattr(post, "created_utc", None),
                    key_insight=f"High-engagement discussion on {label} ({post.score} points, {post.num_responses} comments)")))
            for thread in self.state.social_content.twitter_threads:
                likes = thread.original_tweet.likes
                replies = getattr(thread.original_tweet, "replies", 0) or 0
                eng = normalize_engagement(SimpleNamespace(
                    platform="twitter", score=likes, num_responses=replies, raw_engagement={}))
                candidates.append((eng, TopRedditThread(
                    post_id=thread.thread_id,
                    title=(getattr(thread.original_tweet, "text", "") or thread.thread_id)[:120],
                    subreddit="Twitter", platform="twitter", score=likes, num_comments=replies,
                    url=thread.original_tweet.url, created_utc=getattr(thread.original_tweet, "created_at", None),
                    key_insight=f"High-engagement discussion on Twitter ({likes} likes)")))
            candidates.sort(key=lambda c: c[0], reverse=True)
            # Per-platform cap (<=60% of the 10-slot headline from any one source) so a small but
            # high-engagement platform can't sweep the headline and misrepresent where the evidence
            # actually concentrates (e.g. a 13-post HN minority taking 9/10 slots over 197 Reddit
            # posts). Backfill past the cap only when fewer sources exist — a single-platform corpus
            # still fills all 10 (byte-identical to an uncapped sort there).
            _per_platform_cap = 6
            picked: list[TopRedditThread] = []
            counts: dict[str, int] = {}
            for _eng, thread in candidates:
                if len(picked) >= 10:
                    break
                if counts.get(thread.platform, 0) >= _per_platform_cap:
                    continue
                picked.append(thread)
                counts[thread.platform] = counts.get(thread.platform, 0) + 1
            if len(picked) < 10:
                seen = {id(t) for t in picked}
                picked += [t for _e, t in candidates if id(t) not in seen][:10 - len(picked)]
            top_reddit_threads = picked

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
            # Include generic sources (HN, YouTube) in metadata
            _platform_labels = {"hackernews": "Hacker News", "youtube": "YouTube"}
            for post in (self.state.social_content.generic_posts or []):
                post_metadata[post.post_id] = {
                    "subreddit": _platform_labels.get(post.platform, post.platform),
                    "score": post.score,
                    "url": post.url
                }

            # Build content index for fuzzy matching: list of (normalized_text, post_id)
            content_index: list[tuple[str, str]] = []
            for post in self.state.social_content.reddit_posts:
                # Index post body
                normalized_body = self._normalize_text(post.selftext)
                if len(normalized_body) >= 30:
                    content_index.append((normalized_body, post.post_id))
                # Index all comments (flattened)
                for comment in self._flatten_comments(post.comments):
                    normalized_comment = self._normalize_text(comment.body)
                    if len(normalized_comment) >= 30:
                        content_index.append((normalized_comment, post.post_id))
            for thread in self.state.social_content.twitter_threads:
                # Index original tweet
                normalized_tweet = self._normalize_text(thread.original_tweet.text)
                if len(normalized_tweet) >= 30:
                    content_index.append((normalized_tweet, thread.thread_id))
                # Index replies
                for reply in thread.replies:
                    normalized_reply = self._normalize_text(reply.text)
                    if len(normalized_reply) >= 30:
                        content_index.append((normalized_reply, thread.thread_id))
            # Index generic sources (HN, YouTube) for fuzzy matching
            for post in (self.state.social_content.generic_posts or []):
                normalized_body = self._normalize_text(post.body)
                if len(normalized_body) >= 30:
                    content_index.append((normalized_body, post.post_id))
                for resp in self._flatten_generic_responses(post.responses):
                    normalized_resp = self._normalize_text(resp.body)
                    if len(normalized_resp) >= 30:
                        content_index.append((normalized_resp, post.post_id))

            # Map pain points to source posts
            pain_point_quote_sources = []
            for pain_point in self.state.pain_point_analysis.pain_points:
                quotes_with_sources = []

                # Get source_post_ids directly from PainPoint model (parallel array)
                source_ids = pain_point.source_post_ids if pain_point.source_post_ids else []

                for i, quote in enumerate(pain_point.representative_quotes):
                    # Tier 0: Use parallel source_post_ids array
                    source_id = ""
                    if i < len(source_ids):
                        source_id = source_ids[i]

                    # Tier 1: Fuzzy match fallback for empty source IDs
                    if not source_id:
                        matched_id = self._fuzzy_match_quote(quote, content_index)
                        if matched_id:
                            source_id = matched_id
                            logger.debug(
                                f"Fuzzy matched quote to source '{matched_id}': '{quote[:50]}...'"
                            )

                    # Final: "unknown" with debug log
                    if not source_id:
                        source_id = "unknown"
                        logger.debug(
                            f"Quote source unresolved: '{quote[:50]}...'"
                        )

                    # Defensively strip any [source: ID] tags that may remain in quotes
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

            first_cost = phases[0].estimated_monthly_cost
            cost_scaling_insight = f"Data infrastructure costs start at {first_cost} during MVP, scaling with user growth."
            if data_research.data_quality_risks:
                cost_scaling_insight += f" Primary risk: {data_research.data_quality_risks[0]}."

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

    def _generate_executive_dashboard(
        self,
        enriched_solution: "SolutionIdea | None" = None
    ) -> "ExecutiveDashboard | None":
        """
        Generate executive dashboard for quick decision-making.

        Uses hybrid approach:
        - 90% Python: Metrics computation, data extraction
        - 10% LLM: Strategic narrative (tagline, value prop, verdict rationale)

        Args:
            enriched_solution: Pre-enriched SolutionIdea from final_report.selected_solution_details
                               (already has Stage 12 SEO refinements merged). If None, falls back
                               to accessor which returns raw BaseSolutionIdea.

        Returns:
            ExecutiveDashboard carrying the go/no-go verdict. Supporting sections that could
            not be produced are None and named in `unavailable_sections`.

            None ONLY when there is no selected solution — i.e. there is no subject to reach
            a verdict about, so there is no verdict to lose.

        Raises:
            ExecutiveDashboardError: the verdict itself could not be computed or carried.
                Fatal on purpose — see the class docstring. Do not re-introduce a
                `return None` fallback here.
        """
        from ..models.executive_summary import (
            ExecutiveDashboard,
            SolutionSnapshot,
        )

        # Use enriched solution if provided, otherwise fall back to accessor (raw BaseSolutionIdea)
        selected_solution = enriched_solution or self.accessor.get_selected_solution_details()

        if not selected_solution:
            logger.warning("No selected solution found - cannot generate executive dashboard")
            return None

        # The verdict is the load-bearing output and is computed FIRST, before any of the
        # descriptive sections that historically aborted the whole dashboard. It is also
        # total: _compute_go_no_go_verdict always returns a GoNoGoVerdict (an unscorable
        # idea yields Conditional/High with the missing-data concern named).
        try:
            go_no_go_verdict = self._compute_go_no_go_verdict(selected_solution=selected_solution)
        except Exception as e:
            logger.exception("Go/No-Go verdict computation failed - report cannot be shipped")
            raise ExecutiveDashboardError(
                f"Go/No-Go verdict could not be computed: {e}"
            ) from e

        # Everything below is SUPPORTING DETAIL. Each part degrades on its own and is named
        # in `unavailable_sections`; none of it may discard the verdict above.
        unavailable: list[str] = []

        # Step 1: Compute metrics (Python)
        # Pass the enriched solution to ensure we have access to Stage 12 refined fields
        key_metrics = self._compute_executive_metrics(enriched_solution=selected_solution)
        if not key_metrics:
            logger.error("Executive dashboard: key_metrics unavailable (verdict retained)")
            unavailable.append("key_metrics")

        # Step 2: Extract core pain point (Python)
        core_pain_point = self._extract_core_pain_point(selected_solution)
        if not core_pain_point:
            logger.error("Executive dashboard: core_pain_point unavailable (verdict retained)")
            unavailable.append("core_pain_point")

        # Step 3: Generate narrative components (LLM, already fail-soft)
        try:
            narrative = self._generate_executive_narrative(
                selected_solution=selected_solution,
                core_pain_point=core_pain_point,
                key_metrics=key_metrics,
            )
        except Exception as e:
            logger.warning(f"Executive narrative unavailable (non-fatal): {e}")
            narrative = None

        # Step 4: Assemble the snapshot. Every field is normalized to a str-or-None here
        # rather than trusted: `project_type` is Optional on BaseSolutionIdea and is dropped
        # outright by the pivot/merge reconstruction paths in UnifiedSolutionCrew, and the
        # 2026-08-02 Sev-1 was exactly that None reaching a required field.
        try:
            _personas = getattr(selected_solution, "target_personas", None) or []
            _fallback_tagline = (
                getattr(selected_solution, "headline", None)
                or f"{selected_solution.solution_name} for {_personas[0] if _personas else 'target users'}"
            )
            solution_snapshot = SolutionSnapshot(
                name=_clean_text(getattr(selected_solution, "solution_name", None)),
                tagline=_clean_text(narrative.tagline if narrative else _fallback_tagline),
                core_value_prop=_clean_text(
                    narrative.core_value_prop if narrative
                    else getattr(selected_solution, "description", None)
                ),
                project_type=_clean_text(getattr(selected_solution, "project_type", None)),
                delivery_format=_clean_text(
                    getattr(selected_solution, "delivery_format", None)
                ),
            )
            if solution_snapshot.project_type is None:
                logger.warning(
                    f"Executive dashboard: '{getattr(selected_solution, 'solution_name', '?')}' "
                    f"has no project_type — the type label is omitted (verdict unaffected)"
                )
        except Exception as e:
            logger.error(f"Executive dashboard: solution snapshot unavailable ({e}) - verdict retained")
            solution_snapshot = None
            unavailable.append("recommended_solution_snapshot")

        # Compute confidence score as average of available scores
        _scores = [
            self.score_accessor.get_market_fit(selected_solution),
            self.score_accessor.get_competitive_advantage(selected_solution),
            self.score_accessor.get_technical_feasibility(selected_solution),
            self.score_accessor.get_seo_score_canonical(selected_solution),
        ]
        _valid_scores = [s for s in _scores if s is not None]
        confidence_score = sum(_valid_scores) / len(_valid_scores) if _valid_scores else None

        # Compute research depth label from pain point quality tier
        pp_tier = getattr(self.state, 'pain_point_quality_tier', None) or "BRONZE"
        research_depth_label = {
            "GOLD": "Premium Research",
            "SILVER": "Standard Research",
        }.get(pp_tier, "Basic Research")

        try:
            executive_dashboard = ExecutiveDashboard(
                recommended_solution_snapshot=solution_snapshot,
                go_no_go_verdict=go_no_go_verdict,
                core_pain_point=core_pain_point,
                key_metrics=key_metrics,
                confidence_score=confidence_score,
                research_depth_label=research_depth_label,
                unavailable_sections=unavailable,
                # niche_description removed - use root report.niche
            )
        except Exception as e:
            logger.exception("Executive dashboard assembly failed - report cannot be shipped")
            raise ExecutiveDashboardError(
                f"Executive dashboard carrying verdict '{go_no_go_verdict.verdict}' "
                f"could not be assembled: {e}"
            ) from e

        if unavailable:
            # Surfaced to the reader via _generate_data_quality_summary, not just the log.
            self._dashboard_caveats.append(
                "Executive dashboard incomplete: "
                f"{', '.join(unavailable)} could not be produced for this run. "
                "The Go/No-Go verdict is unaffected; the missing sections are absent, not empty."
            )

        _conf = f"{confidence_score:.2f}" if confidence_score is not None else "N/A"
        logger.info(
            f"[OK] Executive dashboard generated: {go_no_go_verdict.verdict} verdict, "
            f"opportunity score {_conf}"
            + (f" (unavailable: {', '.join(unavailable)})" if unavailable else "")
        )
        return executive_dashboard

    def _compute_executive_metrics(
        self,
        enriched_solution: "SolutionIdea | None" = None
    ) -> "KeyMetrics | None":
        """
        Compute top-line metrics for executive dashboard (Python-only).

        Args:
            enriched_solution: Pre-enriched SolutionIdea with Stage 12 SEO refinements.
                               Used to access seo_scalability_score_refined directly.

        Returns:
            KeyMetrics object with keyword stats, pain point stats, competitor counts
        """
        try:
            from ..models.executive_summary import KeyMetrics

            # Keyword metrics from SEO strategy
            total_keyword_search_volume = 0
            tier0_keyword_count = 0
            tier1_keyword_count = 0
            tier2_keyword_count = 0
            tier3_keyword_count = 0
            tier4_keyword_count = 0
            total_keyword_count = 0

            # Get keyword counts and volumes using accessor
            tier_counts = self.accessor.get_tier_keyword_counts()
            total_keyword_count = tier_counts["total"]
            tier0_keyword_count = tier_counts["tier_0"]
            tier1_keyword_count = tier_counts["tier_1"]
            tier2_keyword_count = tier_counts["tier_2"]
            tier3_keyword_count = tier_counts.get("tier_3", 0)
            tier4_keyword_count = tier_counts.get("tier_4", 0)
            # Use primary search volume for KeyMetrics (SEO strategy report)
            niche_vol = self.accessor.get_primary_search_volume()
            total_keyword_search_volume = niche_vol if niche_vol > 0 else self.accessor.get_total_keyword_search_volume()

            # Pain point metrics
            high_severity_pain_points = 0
            avg_pain_point_severity = 0.0
            avg_commercial_intent = 0.0

            if self.state.pain_point_analysis and self.state.pain_point_analysis.pain_points:
                pain_points = self.state.pain_point_analysis.pain_points
                high_severity_pain_points = len([
                    pp for pp in pain_points
                    if pp.severity_score >= settings.pain_point_high_priority_threshold
                ])

                avg_pain_point_severity = sum(pp.severity_score for pp in pain_points) / len(pain_points)
                avg_commercial_intent = sum(pp.commercial_intent for pp in pain_points) / len(pain_points)

            # Competitor count from selected solution's competitive analysis
            primary_competitor_count = self.accessor.get_competitor_count()

            # Social evidence metrics
            social_evidence_threads = 0
            if self.state.social_content:
                social_evidence_threads += len(self.state.social_content.reddit_posts)
                social_evidence_threads += len(self.state.social_content.twitter_threads)
                social_evidence_threads += len(self.state.social_content.generic_posts or [])

            # Extract score fields via ScoreAccessor (single source of truth)
            if enriched_solution:
                market_fit_score = self.score_accessor.get_market_fit(enriched_solution)
                competitive_advantage_score = self.score_accessor.get_competitive_advantage(enriched_solution)
                technical_feasibility_score = self.score_accessor.get_technical_feasibility(enriched_solution)
                seo_potential_score = self.score_accessor.get_seo_score_canonical(enriched_solution)
                solo_dev_feasibility = self.score_accessor.get_solo_dev_feasibility(enriched_solution)
            else:
                market_fit_score = None
                competitive_advantage_score = None
                technical_feasibility_score = None
                seo_potential_score = None
                solo_dev_feasibility = None

            return KeyMetrics(
                total_keyword_search_volume=total_keyword_search_volume,
                tier0_keyword_count=tier0_keyword_count,
                tier1_keyword_count=tier1_keyword_count,
                tier2_keyword_count=tier2_keyword_count,
                tier3_keyword_count=tier3_keyword_count,
                tier4_keyword_count=tier4_keyword_count,
                total_keyword_count=total_keyword_count,
                high_severity_pain_points=high_severity_pain_points,
                primary_competitor_count=primary_competitor_count,
                avg_pain_point_severity=avg_pain_point_severity,
                avg_commercial_intent=avg_commercial_intent,
                social_evidence_threads=social_evidence_threads,
                market_fit_score=market_fit_score,
                competitive_advantage_score=competitive_advantage_score,
                technical_feasibility_score=technical_feasibility_score,
                seo_potential_score=seo_potential_score,
                solo_dev_feasibility=solo_dev_feasibility,
            )

        except Exception as e:
            logger.warning(f"Failed to compute executive metrics: {e}")
            return None

    def _extract_core_pain_point(self, selected_solution=None) -> "CorePainPoint | None":
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

            selected_solution = selected_solution or self.accessor.get_selected_solution_details()
            scoped_pains = self.accessor.get_solution_pain_points(selected_solution, limit=1)
            if not scoped_pains:
                logger.warning("No validated pain point could be matched to the selected solution")
                return None

            top_pp = scoped_pains[0]

            # Extract representative quote (use first quote if available)
            representative_quote = "No specific quote available"
            source_platform = "Source platform unknown"

            if top_pp.representative_quotes and len(top_pp.representative_quotes) > 0:
                representative_quote = top_pp.representative_quotes[0]

            # Determine source platform from the pain point's own data
            if top_pp.source_platforms:
                source_platform = top_pp.source_platforms[0]
                # Try to add subreddit detail from source_post_ids
                if source_platform == "Reddit" and top_pp.source_post_ids and self.state.social_content:
                    for post in self.state.social_content.reddit_posts:
                        if post.post_id in top_pp.source_post_ids and post.subreddit:
                            source_platform = f"Reddit r/{post.subreddit}"
                            break
            elif top_pp.source_post_ids and self.state.social_content:
                # Fallback: match source_post_ids against known posts/threads
                reddit_ids = {p.post_id for p in self.state.social_content.reddit_posts}
                twitter_ids = {t.thread_id for t in self.state.social_content.twitter_threads}
                generic_map = {p.post_id: p.platform for p in (self.state.social_content.generic_posts or [])}
                _plat_labels = {"hackernews": "Hacker News", "youtube": "YouTube"}
                for sid in top_pp.source_post_ids:
                    if sid in reddit_ids:
                        post = next(p for p in self.state.social_content.reddit_posts if p.post_id == sid)
                        source_platform = f"Reddit r/{post.subreddit}" if post.subreddit else "Reddit"
                        break
                    elif sid in twitter_ids:
                        source_platform = "Twitter"
                        break
                    elif sid in generic_map:
                        source_platform = _plat_labels.get(generic_map[sid], generic_map[sid])
                        break

            return CorePainPoint(
                title=top_pp.title,
                severity_score=top_pp.severity_score,
                commercial_intent_score=top_pp.commercial_intent,
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
            if not core_pain_point or not selected_solution or not key_metrics:
                raise ValueError(
                    "Missing core_pain_point, selected_solution or key_metrics - "
                    "cannot generate executive narrative"
                )

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
            from ..utils.score_helpers import score_band
            _nb = lambda s: score_band(s) if s is not None else "N/A"  # band-or-N/A for prompt inputs
            template = load_prompt("report_executive_narrative")
            prompt = safe_format(template,
                solution_name=selected_solution.solution_name,
                solution_description=selected_solution.description,
                target_personas=target_personas_str,
                niche_description=self.state.niche_context.niche_description,
                pain_point_title=core_pain_point.title,
                # Feed BANDS, never raw decimals — the narrative must read in plain terms and can't
                # echo a score it never saw (mirrors the verdict-explanation + niche-summary band work).
                pain_point_severity=_nb(core_pain_point.severity_score),
                pain_point_wtp=_nb(core_pain_point.commercial_intent_score),
                market_fit_score=_nb(market_fit),
                competitive_advantage_score=_nb(competitive_advantage),
                technical_feasibility_score=_nb(technical_feasibility),
                seo_growth_score=_nb(seo_growth),
                total_keyword_count=key_metrics.total_keyword_count,
                tier1_keyword_count=key_metrics.tier1_keyword_count,
                competitor_count=key_metrics.primary_competitor_count,
                high_severity_pain_points=key_metrics.high_severity_pain_points,
                zero_keywords_note=zero_keywords_note,
                zero_competitors_note=zero_competitors_note
            )

            # Use LLMService for structured output
            result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=ExecutiveNarrative,
                temperature=0.5
            )
            self._record_cost("Stage 14 - Executive Narrative", _usage)

            # Validate output
            if self._validate_executive_narrative(result, selected_solution, core_pain_point):
                logger.info("[OK] LLM executive narrative generation successful")
                return result
            else:
                raise ValueError("LLM narrative failed validation checks - output does not meet quality standards")

        except Exception as e:
            logger.warning(f"LLM narrative generation failed (will use fallback): {e}")
            return None

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

            # Require a criterion keyword (anti-hallucination) — but NOT a numeric score.
            has_score_keyword = any(
                re.search(pattern, verdict_lower, re.IGNORECASE)
                for pattern in score_patterns
            )
            if not has_score_keyword:
                logger.warning(
                    "Verdict does not reference any criterion (market fit / feasibility / SEO …). "
                    "This may indicate hallucinated analysis rather than data-driven rationale."
                )
                return False

            # Band policy: the narrative must NOT leak a raw 0-1 score or percentage into user text
            # (the inputs are fed as bands; this rejects any echoed decimal). Mirrors the verdict guard.
            for field in (narrative.tagline, narrative.core_value_prop, narrative.verdict_rationale):
                if re.search(r"\d\.\d|\d{1,3}\s?%", field or ""):
                    logger.warning("Executive narrative leaked a raw score/percentage — rejecting for band fallback")
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

    def _get_confidence_quality_kwargs(self) -> dict:
        """Return quality-signal kwargs for ScoreAccessor.get_confidence_score()."""
        return dict(
            pain_point_quality_tier=self.state.pain_point_quality_tier,
            social_content_quality_tier=self.state.social_content_quality_tier,
            pain_point_confidence_score=self.state.pain_point_confidence_score,
        )

    def _compute_go_no_go_verdict(
        self,
        selected_solution,
        narrative_rationale: str | None = None
    ) -> "GoNoGoVerdict":
        """
        Compute go/no-go verdict based on selection criteria scores (Python-only).

        Uses score thresholds to determine verdict automatically.
        Uses enriched solution (self._enriched_solution) to ensure same object identity
        as other report sections.

        Args:
            selected_solution: SolutionIdea object
            narrative_rationale: Optional LLM-generated rationale (if None, use template)

        Returns:
            GoNoGoVerdict with verdict, rationale, and risk level
        """
        from ..models.executive_summary import GoNoGoVerdict
        from ..utils.score_helpers import score_band, _composite_for_angle

        # Use enriched solution if available (RC1 fix: object identity)
        solution = getattr(self, '_enriched_solution', None) or selected_solution

        # Get scores using ScoreAccessor with fallbacks
        market_fit = self.score_accessor.get_market_fit(solution)
        competitive_adv = self.score_accessor.get_competitive_advantage(solution)
        tech_feasibility = self.score_accessor.get_technical_feasibility(solution)
        seo_potential = self.score_accessor.get_seo_score_canonical(solution)

        # Average over the PRESENT scores (missing optional scores are no longer
        # fabricated as 0.5, so competitive_adv/seo can legitimately be None).
        # Hard requirements: market_fit and tech_feasibility (gate the verdict
        # tiers individually) plus at least 3 of 4 scores overall.
        score_names = ["market_fit", "competitive_advantage", "technical_feasibility", "seo_potential"]
        scores = [market_fit, competitive_adv, tech_feasibility, seo_potential]
        present_scores = [s for s in scores if s is not None]
        missing_names = [name for name, s in zip(score_names, scores) if s is None]
        if market_fit is None or tech_feasibility is None or len(present_scores) < 3:
            logger.warning(
                f"[Verdict Calculation] Insufficient score data. "
                f"Scores: market_fit={market_fit}, competitive_adv={competitive_adv}, "
                f"tech_feasibility={tech_feasibility}, seo_potential={seo_potential}"
            )
            return GoNoGoVerdict(
                verdict="Conditional",
                rationale=(
                    "Not enough scored data to call this confidently. "
                    "Some pipeline stages did not produce scores — "
                    "review the research output quality before making a final decision."
                ),
                risk_level="High",
                primary_concern="Missing score data — review pipeline output quality",
            )

        score_caveat = None
        if missing_names:
            score_caveat = (
                f"Note: {', '.join(missing_names)} score(s) unavailable — "
                f"verdict averages the {len(present_scores)} present scores."
            )
            logger.info(f"[Verdict Calculation] {score_caveat}")

        # Compute verdict score basis. LIFT-ONLY angle awareness (matches the angle-weighted RANKING),
        # always on when the idea has a winning angle: the angle weights can only RAISE the average
        # (max with the equal-weight mean), so a strong distribution_seo play isn't dragged down by its
        # intentionally-low novelty — but the verdict is NEVER worse than equal-weight, so a winning_angle
        # MISCLASSIFICATION can't wrongly demote a deserving idea (A/B-validated 2026-06-30: 4 correct
        # lifts, 0 demotes). No angle => exact equal-weight mean. The min(market_fit, tech) hard gate below
        # is unchanged either way.
        equal_avg = sum(present_scores) / len(present_scores)
        winning_angle = getattr(solution, "winning_angle", None)
        if winning_angle:
            # competitive_adv occupies the 'novelty' dimension (get_competitive_advantage→novelty_score)
            angle_avg = _composite_for_angle(
                market_fit, tech_feasibility, competitive_adv, seo_potential, winning_angle
            )
            avg_score = max(equal_avg, angle_avg)
        else:
            avg_score = equal_avg

        # P1d: angle-aware LIFT-ONLY hard gate. Default gate = min(market_fit, tech). For a
        # distribution_seo idea we ALSO allow the gate to pass on its binding dimension (SEO), and for
        # novel_differentiation on novelty — via max(...), so the gate is never worse than the tech-based
        # gate (a misclassification can't wrongly demote; preserves the invariant at :3017-3022). An
        # INDEPENDENT tech buildability floor still blocks an un-buildable idea from a clean Go.
        tech_gate = min(market_fit, tech_feasibility)
        gate_val = tech_gate
        buildability_ok = True
        if settings.enable_direction_aware_eval and winning_angle:
            _binding = {
                "distribution_seo": seo_potential,
                "novel_differentiation": competitive_adv,
            }.get(winning_angle)
            if _binding is not None:
                gate_val = max(tech_gate, min(market_fit, _binding))
            # Un-buildable ideas never reach Go, whatever the angle.
            buildability_ok = tech_feasibility >= settings.verdict_conditional_min_individual_score

        # Phase 1.1: Use settings thresholds instead of hard-coded values
        if (avg_score >= settings.verdict_go_avg_score and
            gate_val >= settings.verdict_go_min_individual_score and buildability_ok):
            verdict = "Go"
            risk_level = "Low"
            primary_concern = None
        elif (avg_score >= settings.verdict_conditional_avg_score and
              gate_val >= settings.verdict_conditional_min_individual_score):
            verdict = "Conditional"
            risk_level = "Medium"
            primary_concern = _GENERIC_CONDITIONAL_CONCERN
        else:
            verdict = "No-Go"
            risk_level = "High"
            # Plain-language concern (the band, never the decimal). Name the angle's binding dim.
            if market_fit < 0.6:
                primary_concern = f"{score_band(market_fit).capitalize()} market fit signals soft product-market alignment"
            elif winning_angle == "distribution_seo" and seo_potential is not None and seo_potential < 0.6:
                primary_concern = f"{score_band(seo_potential).capitalize()} SEO scalability undermines the distribution strategy"
            elif tech_feasibility < 0.6:
                primary_concern = f"{score_band(tech_feasibility).capitalize()} technical feasibility signals real build hurdles"
            else:
                primary_concern = "Overall signals fall short of the bar for a recommended build"

            # Payability reclassification (product decision, 2026-07-06): No-Go is reserved for
            # STRUCTURAL blockers (unbuildable, refuted data). A BUILDABLE idea whose market_fit
            # was grounded by weak buyer payability gets "Conditional / High risk" with the
            # condition NAMED — a paid analysis should say "validate willingness-to-pay first",
            # not "no". Scoped to the payability signal: the tech gate and non-payability
            # No-Gos are untouched, so this only reclassifies what the payability critic
            # evidence itself demoted.
            _pay = getattr(solution, "source_segment_payability", None)
            if (buildability_ok
                    and isinstance(_pay, (int, float))
                    and _pay < settings.payability_low_threshold
                    and market_fit < 0.6 <= tech_feasibility):
                from ..utils.segment_payability import payability_phrase
                verdict = "Conditional"
                risk_level = "High"
                # Qualitative phrase only — never the raw class token (band-words convention).
                primary_concern = (
                    f"The target segment is {payability_phrase(getattr(solution, 'source_segment_payability_class', None))} "
                    "with weak willingness-to-pay — the build is feasible, but validate real "
                    "payment intent (pre-sales, paid pilots, or a concierge version) before "
                    "committing to it"
                )

        # The verdict rationale is built AFTER Phase 2/3 (below) so it explains the FINAL verdict
        # (post-downgrade), in plain band language — never the internal decimals, and never the
        # pre-verdict narrative_rationale (generated before this verdict, it could argue a different one).
        pre_downgrade_verdict = verdict

        # Phase 2: Apply trend-based downgrades (downgrade-only, never upgrades)
        trend_context = None
        trend_data = self.state.trend_longevity
        if trend_data is not None and getattr(trend_data, "is_fallback", False):
            # Fallback trend data carries conservative placeholders (momentum
            # 0.5, longevity "Risky") that the downgrade rules would treat as
            # real analysis. Skip the rules, but don't pretend trend is fine:
            # floor risk at Medium and surface an explicit concern.
            if risk_level == "Low":
                risk_level = "Medium"
            if self.state.seeded_from_catalog:
                trend_context = (
                    "Catalog-seeded research: trend analysis requires a fresh "
                    "social corpus, which catalog ideas skip — momentum and "
                    "longevity are not validated. Risk floored at Medium."
                )
            else:
                trend_context = (
                    "Trend analysis used fallback data; trend-based verdict "
                    "adjustments were skipped and risk floored at Medium."
                )
            if primary_concern is None:
                primary_concern = (
                    "Trend analysis unavailable — market momentum and "
                    "longevity not validated"
                )
            logger.info(f"[Verdict Trend Adjustment] {trend_context}")
        elif trend_data is not None:
            from ..validators.score_validators import ScoreThresholds, VerdictValidator
            trend_validator = VerdictValidator(ScoreThresholds.from_settings(settings))
            verdict, risk_level, primary_concern, trend_context = (
                trend_validator.apply_trend_downgrade(
                    verdict=verdict,
                    risk_level=risk_level,
                    primary_concern=primary_concern,
                    trend_direction=trend_data.trend_direction,
                    momentum_score=trend_data.momentum_score,
                    timing_recommendation=trend_data.timing_recommendation,
                    longevity_verdict=trend_data.longevity_verdict,
                    market_maturity=trend_data.market_maturity,
                )
            )
            if trend_context:
                logger.info(f"[Verdict Trend Adjustment] {trend_context}")

        # Phase 3: Apply market viability risk floor (downgrade-only)
        market_viability_context = None
        market_sizing = self.state.market_sizing
        if market_sizing is not None:
            viability_verdict = getattr(market_sizing, 'market_viability_verdict', None) or ""
            entry_strategy = getattr(market_sizing, 'recommended_entry_strategy', None) or ""
            if viability_verdict:
                from ..validators.score_validators import ScoreThresholds as _ST
                from ..validators.score_validators import VerdictValidator as _VV
                viability_validator = _VV(_ST.from_settings(settings))
                verdict, risk_level, primary_concern, market_viability_context = (
                    viability_validator.apply_market_viability_downgrade(
                        verdict=verdict,
                        risk_level=risk_level,
                        primary_concern=primary_concern,
                        market_viability_verdict=viability_verdict,
                        recommended_entry_strategy=entry_strategy,
                    )
                )
                if market_viability_context:
                    logger.info(f"[Verdict Viability Adjustment] {market_viability_context}")

        # Phase 4: SEO kill-question floor (distribution_seo only). Grounds an over-OPTIMISTIC pSEO
        # verdict in the page-universe reality. Null-guard — the kill-question is optional/fail-soft
        # (only computed for distribution_seo).
        seo_kill_context = None
        if winning_angle == "distribution_seo":
            kq = getattr(self.state.seo_strategy_report, "seo_kill_question", None) if self.state.seo_strategy_report else None
            if kq is not None:
                from ..validators.score_validators import ScoreThresholds as _ST4, VerdictValidator as _VV4
                verdict, risk_level, primary_concern, seo_kill_context = (
                    _VV4(_ST4.from_settings(settings)).apply_seo_kill_downgrade(
                        verdict=verdict, risk_level=risk_level, primary_concern=primary_concern,
                        winnable_pages=kq.winnable_pages,
                        median_keyword_difficulty=kq.median_keyword_difficulty,
                        penalty_risk_flag=kq.penalty_risk_flag,
                        kd_sample_size=getattr(kq, "kd_sample_size", 0),
                        page_ceiling=kq.indexable_page_ceiling,
                    )
                )
                if seo_kill_context:
                    logger.info(f"[Verdict SEO-Kill Floor] {seo_kill_context}")

        # Phase 5: payability floor (permanent since the 2026-07-06 gate pass). A Go for an idea sold
        # DIRECTLY to a low-payability segment overstates the business — pain without a wallet.
        # Downgrade-only; abstains on unscored payability or non-direct-paid monetization.
        from ..validators.score_validators import ScoreThresholds as _ST5, VerdictValidator as _VV5
        _tags = getattr(solution, "tags", None)
        verdict, risk_level, primary_concern, payability_context = (
            _VV5(_ST5.from_settings(settings)).apply_payability_downgrade(
                verdict=verdict, risk_level=risk_level, primary_concern=primary_concern,
                payability=getattr(solution, "source_segment_payability", None),
                payability_class=getattr(solution, "source_segment_payability_class", None),
                monetization=getattr(_tags, "monetization", None) if _tags is not None else None,
            )
        )
        if payability_context:
            logger.info(f"[Verdict Payability Floor] {payability_context}")

        # Phase 5.5 (run-quality fixes §1, 2026-07-30): red-team floor — an adversarial
        # 'weakened'/'killed' finding on the selected idea must reach the verdict; before
        # this it was stamped on the idea and then discarded at verdict time (the audited
        # ScopeShield run shipped 'Conditional/Medium/monitor closely' after being
        # red-team weakened with devastating caveats). Runs before regulatory so the
        # structural-legal concern still outranks when both fire.
        from ..validators.score_validators import ScoreThresholds as _ST55, VerdictValidator as _VV55
        from ..models.solution_idea import effective_red_team_state as _effective_rt_state
        _rt_v, _rt_findings = _effective_rt_state(solution)
        if ((_rt_v or "").strip().lower() == "killed"
                and primary_concern == _GENERIC_CONDITIONAL_CONCERN):
            # Null the generic base concern so the killed concern can land — every floor
            # follows the only-if-None contract, and the generic Conditional concern
            # would otherwise always win.
            primary_concern = None
        verdict, risk_level, primary_concern, red_team_context = (
            _VV55(_ST55.from_settings(settings)).apply_red_team_downgrade(
                verdict=verdict, risk_level=risk_level, primary_concern=primary_concern,
                red_team_verdict=_rt_v,
                red_team_caveats=getattr(solution, "red_team_caveats", None),
                red_team_findings=_rt_findings,
            )
        )
        if red_team_context:
            logger.info(f"[Verdict Red-Team Floor] {red_team_context}")

        # Phase 6 (flagged, default OFF): stacked regulatory + grey-market exposure caps the verdict.
        # Runs last so its concern outranks earlier downgrades when both fire (structural legal risk).
        from ..validators.score_validators import ScoreThresholds as _ST6, VerdictValidator as _VV6
        verdict, risk_level, primary_concern, regulatory_context = (
            _VV6(_ST6.from_settings(settings)).apply_regulatory_risk_downgrade(
                verdict=verdict, risk_level=risk_level, primary_concern=primary_concern,
                risk_flags=getattr(_tags, "risk_flags", None) if _tags is not None else None,
            )
        )
        if regulatory_context:
            logger.info(f"[Verdict Regulatory Floor] {regulatory_context}")

        # Build the verdict explanation now the FINAL verdict is known: LLM-grounded + validated when
        # enabled, else a deterministic band template. Any downgrade is prepended transparently and the
        # score caveat (if any) appended — both deterministic, so the JSON stands on its own.
        downgrade_note = None
        if verdict != pre_downgrade_verdict:
            downgrade_note = (regulatory_context or trend_context or market_viability_context
                              or seo_kill_context or payability_context or red_team_context
                              or "post-verdict validation")
        rationale = self._generate_verdict_explanation(
            verdict=verdict,
            primary_concern=primary_concern,
            market_fit=market_fit,
            competitive_adv=competitive_adv,
            tech_feasibility=tech_feasibility,
            seo_potential=seo_potential,
            winning_angle=winning_angle,
            pre_downgrade_verdict=pre_downgrade_verdict,
            downgrade_note=downgrade_note,
            score_caveat=score_caveat,
        )
        if red_team_context and red_team_context != downgrade_note:
            # Unconditional surfacing (§1): the red-team finding must be visible even when
            # the verdict LETTER did not change — all four audited runs were already
            # Conditional, so a change-gated note alone would keep the finding invisible.
            # Deterministic append, mirroring the score_caveat convention.
            rationale = f"{rationale} {red_team_context}"

        result = GoNoGoVerdict(
            verdict=verdict,
            rationale=rationale,
            risk_level=risk_level,
            primary_concern=primary_concern,
            trend_context=trend_context,
            market_viability_context=market_viability_context,
            payability_context=payability_context,
            red_team_context=red_team_context,
        )
        # Cache for other sections (market_analytics derives its recommendation
        # from the same verdict instead of maintaining parallel thresholds)
        self._last_computed_verdict = result
        return result

    def _generate_verdict_explanation(
        self, *, verdict, primary_concern, market_fit, competitive_adv, tech_feasibility,
        seo_potential, winning_angle, pre_downgrade_verdict, downgrade_note, score_caveat,
    ) -> str:
        """The verdict rationale in plain band language. LLM-grounded + validated when
        enable_llm_verdict_explanation is on, else a deterministic band template. The verdict is
        already decided — this only EXPLAINS it. Downgrade note + score caveat are deterministic."""
        from ..utils.score_helpers import score_band
        mf_band, ca_band = score_band(market_fit), score_band(competitive_adv)

        # Deterministic band template — always the fallback (the LLM must pass validation to replace it).
        if verdict == "Go":
            body = (f"Strong opportunity — {mf_band} market fit and {ca_band} differentiation, "
                    f"clearing the bar on every dimension that gates a Go.")
        elif verdict == "Conditional":
            body = ("Promising but unproven — the signals support moving forward, but build an MVP "
                    "to validate the key assumptions before committing.")
        elif primary_concern:
            body = f"Not a build yet — {primary_concern[0].lower()}{primary_concern[1:]}."
        else:
            body = "Not a build yet — the signals fall short of the bar for a recommended build."

        if settings.enable_llm_verdict_explanation:
            llm_body = self._llm_verdict_explanation(
                verdict=verdict, primary_concern=primary_concern, mf_band=mf_band, ca_band=ca_band,
                feasibility_band=score_band(tech_feasibility), seo_band=score_band(seo_potential),
                winning_angle=winning_angle, downgrade_note=downgrade_note,
            )
            if llm_body:
                body = llm_body

        if downgrade_note and verdict != pre_downgrade_verdict:
            body = (f"Note: verdict downgraded from {pre_downgrade_verdict} to {verdict} — "
                    f"{downgrade_note}\n\n{body}")
        if score_caveat:
            body = f"{body} {score_caveat}"
        return body

    def _llm_verdict_explanation(
        self, *, verdict, primary_concern, mf_band, ca_band, feasibility_band, seo_band,
        winning_angle, downgrade_note,
    ) -> "str | None":
        """One focused LLM call explaining the DECIDED verdict in bands. Validated; None on any failure
        (caller keeps the band template). The LLM is told the verdict — it never decides it."""
        try:
            from ..models.executive_summary import VerdictExplanation
            from ..utils.prompts import load_prompt

            sol = getattr(self, "_enriched_solution", None)
            sol_name = getattr(sol, "solution_name", None) or "this idea"
            angle_phrase = (
                f"**Winning GTM angle:** {str(winning_angle).replace('_', ' ')}" if winning_angle else ""
            )
            firing = {
                "Go": "It cleared the bar on the overall score and on both gating dimensions "
                      "(market fit and technical feasibility).",
                "Conditional": "The overall score is solid but below the Go bar, or a gating dimension is "
                               "only moderate — enough to pursue with validation, not for an unqualified Go.",
                "No-Go": "The overall score or a gating dimension falls below the threshold for a "
                         "recommended build.",
            }.get(verdict, "")
            template = load_prompt("report_verdict_explanation")
            prompt = safe_format(
                template,
                verdict=verdict,
                solution_name=sol_name,
                winning_angle_phrase=angle_phrase,
                market_fit_band=mf_band,
                differentiation_band=ca_band,
                feasibility_band=feasibility_band,
                seo_band=seo_band,
                firing_context=firing,
                downgrade_context=(f"**Downgrade:** {downgrade_note}" if downgrade_note else ""),
                primary_concern=(f"**Primary concern:** {primary_concern}" if primary_concern else ""),
            )
            result, _usage = LLMService.invoke_structured(
                prompt=prompt, output_model=VerdictExplanation, temperature=0.4
            )
            self._record_cost("Stage 14 - Verdict Explanation", _usage)
            text = (getattr(result, "explanation", "") or "").strip()
            if self._verdict_explanation_valid(text, verdict):
                return text
            logger.warning("[Verdict] LLM explanation failed validation — using band template")
            return None
        except Exception as e:
            logger.warning(f"[Verdict] LLM explanation failed ({e}) — using band template")
            return None

    @staticmethod
    def _verdict_explanation_valid(text: str, verdict: str) -> bool:
        """Guard: the explanation must match the verdict's stance and expose NO internal decimals."""
        import re
        if not text or not (20 <= len(text) <= 700):
            return False
        if re.search(r"\d\.\d|\d{1,3}\s?%", text):  # no decimals, no percentages
            return False
        low = text.lower()
        if verdict == "No-Go" and any(
            p in low for p in ("strong opportunity", "clear go", "go for it", "solid opportunity",
                               "recommended pursuit", "pursue this opportunity", "green light")
        ):
            return False
        if verdict == "Go" and any(
            p in low for p in ("no-go", "not viable", "avoid this", "do not build", "don't build",
                               "not recommended", "not worth pursuing")
        ):
            return False
        return True

    # ==================================================================================
    # Go-to-Market Blueprint Generator (Phase 2 Enhancement)
    # ==================================================================================

    def _generate_gtm_blueprint(self) -> "GTMBlueprint | None":
        """
        Generate Go-to-Market blueprint for immediate execution.

        Uses hybrid approach:
        - LLM: ICP generation (enriched with audience data), marketing narrative, budget
        - Python: Channel identification, playbook orchestration

        Returns:
            GTMBlueprint with ICP, channels, messaging, content, and 30-day plan
        """
        try:
            from ..models.marketing_blueprint import GTMBlueprint

            # Step 1: Generate ICP from audience + pain point data (LLM)
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
            narrative = self._generate_marketing_narrative(icp=icp)

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

            # Generate dynamic budget estimate using LLM
            budget_estimate = self._generate_budget_estimate(
                channels=channels,
                selected_solution=selected_solution,
                icp=icp
            ) if channels else None

            gtm_blueprint = GTMBlueprint(
                ideal_customer_profile=icp,
                core_marketing_message=narrative.core_marketing_message,
                message_framework=narrative.message_framework,
                recommended_channels=channels[:3],  # Top 3 channels
                example_content_angles=narrative.content_angles[:5],  # Top 5 angles
                first_30_days_playbook=playbook,
                budget_estimate=budget_estimate
            )

            logger.info(f"[OK] GTM blueprint generated: {len(channels)} channels, {len(narrative.content_angles)} content angles")
            return gtm_blueprint

        except Exception as e:
            logger.warning(f"Failed to generate GTM blueprint: {e}")
            return None

    def _build_catalog_icp(self) -> "IdealCustomerProfile | None":
        """Python-built ICP for catalog-seeded runs (no LLM call).

        Catalog seeds have no content categorization or audience mapping —
        only persona strings (niche_context.market_segments), pain titles,
        and the solution itself. The soft persona fields can't be derived
        honestly from that, so they carry explicit catalog-seeded sentinels
        instead of LLM-invented demographics.
        """
        from ..models.marketing_blueprint import IdealCustomerProfile

        personas = (
            self.state.niche_context.market_segments
            if self.state.niche_context and self.state.niche_context.market_segments
            else []
        )
        if not personas:
            return None

        pain_points = []
        selected_solution = self.accessor.get_selected_solution_details()
        scoped_pains = (
            self.accessor.get_solution_pain_points(selected_solution, limit=5)
            if selected_solution else []
        )
        if scoped_pains:
            pain_points = [pp.title for pp in scoped_pains]
        if not pain_points:
            pain_points = ["No specific pain points identified"]

        goals = []
        if selected_solution and selected_solution.core_features:
            goals = [f"Achieve {feature.lower()}" for feature in selected_solution.core_features[:5]]
        if not goals:
            goals = ["Goals not identified from solution features"]

        sentinel = (
            "Catalog-seeded estimate — not validated against collected "
            "audience data; run full research for audience mapping."
        )
        logger.info(
            f"[ICP] Built catalog-seeded ICP from {len(personas)} personas (no LLM)"
        )
        return IdealCustomerProfile(
            persona_name=personas[0],
            demographics=sentinel,
            psychographics=sentinel,
            pain_points=pain_points,
            goals=goals,
            buying_triggers=sentinel,
            decision_criteria=sentinel,
        )

    def _extract_ideal_customer_profile(self) -> "IdealCustomerProfile | None":
        """
        Generate ICP using LLM with rich audience, pain point, and solution data.

        Gathers data from content categorization (Stage 6), audience mapping
        (Stage 6.5), pain points, and solution context, then uses
        LLMService.invoke_structured() to produce a proper IdealCustomerProfile.

        Falls back to a simplified Python-only ICP if the LLM call fails.

        Returns:
            IdealCustomerProfile with persona details, or None if insufficient data
        """
        try:
            from ..models.marketing_blueprint import IdealCustomerProfile
            from ..utils.prompts import load_prompt

            # === Guard: need content categorization with user segments ===
            if not self.state.pain_point_analysis or not self.state.pain_point_analysis.content_categorization:
                # Catalog-seeded runs skip content categorization entirely but
                # carry the idea's personas in niche_context.market_segments.
                # Build an honest Python ICP (no LLM — sparse inputs would
                # invite fabricated demographics) so the GTM blueprint can
                # still generate.
                if self.state.seeded_from_catalog:
                    catalog_icp = self._build_catalog_icp()
                    if catalog_icp is not None:
                        return catalog_icp
                logger.warning("No content categorization available for ICP")
                return None

            categorization = self.state.pain_point_analysis.content_categorization

            if not categorization.user_segments or len(categorization.user_segments) == 0:
                logger.warning("No user segments available")
                return None

            primary_segment = categorization.user_segments[0]

            # === Gather solution context ===
            selected_solution = self.accessor.get_selected_solution_details()
            solution_name = selected_solution.solution_name if selected_solution else "the solution"
            solution_description = selected_solution.description if selected_solution else ""
            value_proposition = selected_solution.value_proposition if selected_solution else ""
            project_type = (selected_solution.project_type or "SaaS Tool") if selected_solution else "SaaS Tool"
            target_personas = ", ".join(selected_solution.target_personas) if selected_solution and selected_solution.target_personas else "Not specified"

            # === Gather only validated pain points addressed by this solution ===
            pain_points = []
            scoped_pains = (
                self.accessor.get_solution_pain_points(selected_solution, limit=5)
                if selected_solution else []
            )
            if scoped_pains:
                pain_points = [pp.title for pp in scoped_pains]

            # === Infer goals from core features ===
            goals = []
            if selected_solution and selected_solution.core_features:
                goals = [f"Achieve {feature.lower()}" for feature in selected_solution.core_features[:5]]
            if not goals:
                goals = ["Goals not identified from solution features"]

            # === Niche description ===
            niche_description = ""
            if self.state.niche_context and self.state.niche_context.niche_description:
                niche_description = self.state.niche_context.niche_description

            # === Build audience mapping context (Stage 6.5) ===
            audience_mapping = self.state.audience_mapping
            primary_segment_name = primary_segment.segment_name
            primary_segment_details = ""
            audience_segments_summary = "No detailed audience segments available."
            vocabulary_list = "Not available"
            messaging_frameworks = "Not available"

            if audience_mapping:
                # Primary target segment details
                primary_segment_name = audience_mapping.primary_target_segment or primary_segment.segment_name
                # Find the matching segment for full details
                for seg in audience_mapping.audience_segments:
                    if seg.segment_name == primary_segment_name:
                        primary_segment_details = (
                            f"Size Estimate: {seg.size_estimate}\n"
                            f"Expertise Level: {seg.expertise_level}\n"
                            f"Budget Sensitivity: {seg.budget_sensitivity}\n"
                            f"Discovery Channels: {', '.join(seg.discovery_channels)}\n"
                            f"Motivation Drivers: {', '.join(seg.motivation_drivers)}\n"
                            f"Pain Point Alignment: {', '.join(seg.pain_point_alignment)}"
                        )
                        break

                # All audience segments summary
                seg_lines = []
                for seg in audience_mapping.audience_segments:
                    seg_lines.append(
                        f"- **{seg.segment_name}** (Size: {seg.size_estimate}, "
                        f"Expertise: {seg.expertise_level}, "
                        f"Budget Sensitivity: {seg.budget_sensitivity})\n"
                        f"  Channels: {', '.join(seg.discovery_channels)}\n"
                        f"  Motivations: {', '.join(seg.motivation_drivers)}"
                    )
                if seg_lines:
                    audience_segments_summary = "\n".join(seg_lines)

                # Vocabulary and messaging
                if audience_mapping.common_vocabulary:
                    vocabulary_list = ", ".join(audience_mapping.common_vocabulary)
                if audience_mapping.messaging_frameworks:
                    messaging_frameworks = "; ".join(audience_mapping.messaging_frameworks)
            else:
                # Fallback: use content categorization primary segment info
                primary_segment_details = (
                    f"Primary Concerns: {', '.join(primary_segment.primary_concerns) if primary_segment.primary_concerns else 'Not specified'}\n"
                    f"Mention Frequency: {primary_segment.mention_frequency}"
                )

            # === Format pain points and goals for prompt ===
            if pain_points:
                pain_points_list = "\n".join(f"- {pp}" for pp in pain_points)
            else:
                pain_points_list = "- No specific pain points identified"

            goals_list = "\n".join(f"- {goal}" for goal in goals)

            # === Load template and invoke LLM ===
            template = load_prompt("report_icp_generation")
            prompt = safe_format(
                template,
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description or "Not available",
                value_proposition=value_proposition or "Not available",
                project_type=project_type,
                target_personas=target_personas,
                primary_segment_name=primary_segment_name,
                primary_segment_details=primary_segment_details or "No detailed segment data available",
                audience_segments_summary=audience_segments_summary,
                pain_points_list=pain_points_list,
                goals_list=goals_list,
                vocabulary_list=vocabulary_list,
                messaging_frameworks=messaging_frameworks,
            )

            result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=IdealCustomerProfile,
                temperature=0.2,
                model_name=settings.report_schema_llm,  # list-heavy (pain_points, goals)
            )
            self._record_cost("Stage 14 - Ideal Customer Profile", _usage)
            allowed_pain_titles = set(pain_points)
            result = result.model_copy(update={
                "pain_points": [
                    title for title in result.pain_points
                    if title in allowed_pain_titles
                ],
            })
            logger.info(f"[OK] LLM ICP generation successful: persona={result.persona_name}")
            return result

        except Exception as e:
            logger.warning(f"LLM ICP generation failed, using fallback: {e}")
            # === Fallback: simplified Python ICP ===
            try:
                from ..models.marketing_blueprint import IdealCustomerProfile

                return IdealCustomerProfile(
                    persona_name=primary_segment.segment_name,
                    pain_points=pain_points if pain_points else ["No specific pain points identified"],
                    goals=goals,
                    demographics="Insufficient data for demographic profiling — run full audience mapping",
                    psychographics="Insufficient data for psychographic profiling — run full audience mapping",
                    buying_triggers="Insufficient data for buying trigger analysis — run full audience mapping",
                    decision_criteria="Insufficient data for decision criteria analysis — run full audience mapping",
                )
            except Exception as fallback_err:
                logger.warning(f"ICP fallback also failed: {fallback_err}")
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

        # EVIDENCE-backed, not scrape-volume backed. Ranking by raw collection volume made
        # r/DublinConcerts the recommended launch channel of a US-metro run (live audit
        # 2026-08-03): it was the largest raw bucket, 16 of 133 posts, and contributed
        # ZERO posts to any validated pain. The claim "Found N highly relevant discussions"
        # is a relevance claim, so it has to count posts that actually became evidence.
        # No fallback to the raw breakdown — no evidence means no recommended channel.
        # (`research_metadata.top_subreddits` keeps the raw counts; that one honestly means
        # "how much did we read".)
        subreddit_counts = self.accessor.get_evidence_subreddit_breakdown()
        if not subreddit_counts:
            return None

        top_subreddit = max(subreddit_counts, key=subreddit_counts.get)
        post_count = subreddit_counts[top_subreddit]

        return MarketingChannel(
            channel_name=f"Reddit r/{top_subreddit}",
            channel_type="Community",
            target_audience_size=f"{post_count} discussions cited as evidence",
            rationale=f"{post_count} discussion(s) in r/{top_subreddit} were cited as evidence for this run's validated pain points, so the audience is demonstrably present there.",
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
        from ..models.marketing_blueprint import MarketingChannel

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

            # Flag content gap opportunities for zero-result platforms
            sources = getattr(self.state, "sources_searched", None) or {}
            for platform, info in sources.items():
                if info.get("enabled") and info.get("posts_found", 0) == 0:
                    label = {"hackernews": "Hacker News", "youtube": "YouTube"}.get(platform, platform)
                    channels.append(MarketingChannel(
                        channel_name=f"{label} (Content Gap)",
                        channel_type="Content Gap",
                        target_audience_size="0 competing posts found",
                        rationale=f"Searched {label} and found no existing content for this niche. Potential first-mover opportunity if audience overlaps.",
                        strategy=f"Research {label}'s audience to validate fit before investing content creation effort.",
                        priority="Low",
                    ))

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

            prompt = safe_format(template,
                solution_name=selected_solution_name,
                solution_description=solution_description,
                niche_description=self.state.niche_context.niche_description,
                persona_name=icp.persona_name,
                pain_points_list=pain_points_list,
                goals_list=goals_list,
                max_content_angles=max_content_angles
            )

            # Use LLMService for structured output
            result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=MarketingNarrative,
                temperature=0.6,
                model_name=settings.report_schema_llm,  # list-heavy (content_angles)
            )
            self._record_cost("Stage 14 - Marketing Narrative", _usage)
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
        from .utils.report_pre_compute import compute_metric_calibration, compute_metric_ceiling

        # Use only research-discovered pains that resolve to this solution. Empty is honest:
        # substituting the niche's highest-ranked pain would fabricate product scope.
        top_pain_points = self.accessor.get_solution_pain_points(
            selected_solution,
            limit=3,
        )

        # Format data for prompt
        pain_points_list = format_pain_points_for_prompt(top_pain_points)
        if top_pain_points:
            pain_scope_requirement = (
                "At least 50% of action items must explicitly mention one of the provided "
                "pain point titles."
            )
        else:
            pain_scope_requirement = (
                "No validated pain matched this solution. Do not invent or borrow pain titles; "
                "prioritize testing the solution's claimed problem before building."
            )
        channels_summary = format_channels_for_prompt(channels)
        icp_summary = format_icp_for_prompt(icp)

        # Get keyword and competitive data - use centralized accessor for consistency
        tier_counts = self.accessor.get_tier_keyword_counts()
        total_keyword_count = tier_counts["total"]
        tier0_keyword_count = tier_counts["tier_0"]
        tier1_keyword_count = tier_counts["tier_1"]

        competitor_count = self.accessor.get_competitor_count()

        # Pre-compute metric calibration
        metric_calibration = compute_metric_calibration(total_keyword_count, tier1_keyword_count)
        metric_ceiling = compute_metric_ceiling(total_keyword_count, tier1_keyword_count)

        # Load template and generate prompt
        template = load_prompt("report_first_30_days_playbook")
        prompt = safe_format(template,
            solution_name=selected_solution.solution_name,
            solution_description=selected_solution.description,
            value_proposition=selected_solution.value_proposition,
            technical_approach=selected_solution.technical_approach or "Technical approach not specified",
            project_type=selected_solution.project_type or "Project type not specified",
            estimated_development_time=selected_solution.estimated_development_time or "Development timeline not estimated",
            niche=self.state.niche_context.niche_description,
            top_pain_points_list=pain_points_list,
            pain_scope_requirement=pain_scope_requirement,
            icp_summary=icp_summary,
            channels_summary=channels_summary,
            total_keyword_count=total_keyword_count,
            tier0_keyword_count=tier0_keyword_count,
            tier1_keyword_count=tier1_keyword_count,
            competitor_count=competitor_count,
            metric_calibration=metric_calibration,
            metric_ceiling=metric_ceiling,
        )

        # Use LLMService for structured output
        try:
            playbook, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=First30DaysPlaybook,
                temperature=0.6,
                model_name=settings.report_schema_llm,  # list-heavy (week_1-4_actions, success_metrics)
            )
            self._record_cost("Stage 14 - First 30 Days Playbook", _usage)
            logger.info("Successfully generated 30-day playbook via LLM")
            return playbook
        except Exception as e:
            logger.error(f"Failed to generate 30-day playbook: {e}")
            raise

    def _generate_budget_estimate(
        self,
        channels: list["MarketingChannel"],
        selected_solution: "SolutionIdea",
        icp: "IdealCustomerProfile"
    ) -> "BudgetEstimateResult | None":
        """
        Generate dynamic marketing budget estimate using LLM.

        Uses pricing strategy, market sizing, and channel mix to calculate
        a context-aware budget with allocation breakdown.

        Args:
            channels: List of MarketingChannel objects
            selected_solution: Selected solution with details
            icp: Ideal customer profile

        Returns:
            BudgetEstimateResult with budget range and allocation, or None on failure
        """
        from ..models.marketing_blueprint import BudgetEstimateResult
        from ..utils.prompts import load_prompt
        from .utils.prompt_formatters import format_channels_for_prompt
        from .utils.report_pre_compute import compute_budget_range

        try:
            # Extract pricing data - find pricing strategy for selected solution
            pricing_model = "Freemium"
            starter_price = "N/A"
            pro_price = "N/A"
            estimated_arpu = "N/A"
            estimated_ltv = "N/A"
            # NOT "3:1". Every sibling default here is an honest "N/A", but this one used to
            # hand the budget LLM a concrete ratio target invented by this line — the same
            # failure mode as the fabricated CAC: an unsourced number that reads as a finding
            # and anchors everything computed after it. Absent is the correct value.
            ltv_to_cac_ratio = "Not established"

            # Find pricing strategy for the selected solution from the list
            if hasattr(self.state, 'pricing_strategies') and self.state.pricing_strategies:
                for ps in self.state.pricing_strategies:
                    if ps.solution_name == selected_solution.solution_name:
                        pricing_model = ps.pricing_model or "Freemium"
                        starter_price = ps.recommended_starter_price or "N/A"
                        pro_price = ps.recommended_pro_price or "N/A"
                        estimated_arpu = ps.estimated_arpu or "N/A"
                        estimated_ltv = ps.estimated_ltv or "N/A"
                        ltv_to_cac_ratio = ps.ltv_to_cac_ratio or "Not established"
                        break

            # Extract market sizing data
            som_y1 = "Not calculated"
            som_y3 = "Not calculated"
            tam = "Not calculated"

            ms = self._normalized_market_sizing()
            if ms:
                som_y1 = ms.serviceable_obtainable_market_y1 or "Not calculated"
                som_y3 = ms.serviceable_obtainable_market_y3 or "Not calculated"
                tam = ms.total_addressable_market or "Not calculated"

            # Format channels
            channels_summary = format_channels_for_prompt(channels)

            # Pre-compute budget range anchor
            channel_count = len(channels) if channels else 0
            suggested_budget_range = compute_budget_range(pricing_model, channel_count)

            # Get solution and ICP details
            project_type = selected_solution.project_type or "SaaS Tool"
            persona_name = icp.persona_name if icp else "Target Customer"

            # Load template and generate prompt
            template = load_prompt("report_budget_estimate")
            prompt = safe_format(template,
                solution_name=selected_solution.solution_name,
                pricing_model=pricing_model,
                starter_price=starter_price,
                pro_price=pro_price,
                estimated_arpu=estimated_arpu,
                estimated_ltv=estimated_ltv,
                ltv_to_cac_ratio=ltv_to_cac_ratio,
                som_y1=som_y1,
                som_y3=som_y3,
                tam=tam,
                channels_summary=channels_summary,
                project_type=project_type,
                persona_name=persona_name,
                suggested_budget_range=suggested_budget_range,
                channel_count=channel_count,
            )

            # Use LLMService for structured output
            budget_result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=BudgetEstimateResult,
                temperature=0.5
            )
            self._record_cost("Stage 14 - Budget Estimate", _usage)
            logger.info(
                f"Successfully generated budget estimate: "
                f"${budget_result.monthly_budget_min}-${budget_result.monthly_budget_max}/month"
            )
            return budget_result

        except Exception as e:
            logger.warning(f"Failed to generate budget estimate, using fallback: {e}")
            return None

    # ==================================================================================
    # Analytics Generator (Phase 3 Enhancement)
    # ==================================================================================

    def _generate_analytics(self) -> tuple["MarketAnalytics | None", "SEOAnalytics | None", "CompetitiveAnalytics | None", "PainPointAnalytics | None"]:
        """
        Generate all analytics (Python-only, no LLM).

        Returns:
            Tuple of (market_analytics, seo_analytics, competitive_analytics, pain_point_analytics)
        """

        # Compute analytics
        market_analytics = self._compute_market_analytics()
        seo_analytics = self._compute_seo_analytics()
        competitive_analytics = self._compute_competitive_analytics()
        pain_point_analytics = self._compute_pain_point_analytics()

        return (market_analytics, seo_analytics, competitive_analytics, pain_point_analytics)

    def _compute_market_analytics(self) -> "MarketAnalytics | None":
        """Compute market opportunity analytics (Python-only)."""
        try:
            from ..models.analytics import MarketAnalytics

            # Use enriched solution (RC1 fix: object identity)
            selected_solution = getattr(self, '_enriched_solution', None) or self.accessor.get_selected_solution_details()
            if not selected_solution:
                return None

            # Compute overall opportunity score using ScoreAccessor
            _opp_scores = [
                self.score_accessor.get_market_fit(selected_solution),
                self.score_accessor.get_competitive_advantage(selected_solution),
                self.score_accessor.get_technical_feasibility(selected_solution),
                self.score_accessor.get_seo_score_canonical(selected_solution),
            ]
            _valid_opp = [s for s in _opp_scores if s is not None]
            overall_score = sum(_valid_opp) / len(_valid_opp) if _valid_opp else 0.5

            # Market size from primary search volume (SEO strategy report)
            market_size_category = "Small"
            niche_vol = self.accessor.get_primary_search_volume()
            sizing_volume = niche_vol if niche_vol > 0 else self.accessor.get_total_keyword_search_volume()
            if sizing_volume > 10000:
                market_size_category = "Large"
            elif sizing_volume > 1000:
                market_size_category = "Medium"

            # Competitive intensity
            competitor_count = self.accessor.get_competitor_count()

            competitive_intensity = (
                "Low" if competitor_count < settings.competitive_intensity_low_threshold
                else "Medium" if competitor_count < settings.competitive_intensity_high_threshold
                else "High"
            )

            # Recommendation: derived from the SAME verdict machinery as the
            # executive dashboard (settings thresholds + trend/viability
            # downgrades). The old inline 0.75/0.60 were stale pre-optimization
            # thresholds (commit 0ef15e3 moved to 0.72/0.55) that could
            # contradict the headline verdict in the same JSON.
            cached_verdict = getattr(self, '_last_computed_verdict', None)
            if cached_verdict is not None:
                recommendation = cached_verdict.verdict
            else:
                recommendation = self._compute_go_no_go_verdict(selected_solution).verdict

            # Selection confidence = same 4-score average as overall_score (matches hero %)
            selection_confidence = overall_score

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
            # Direct access to tier keyword lists, deduplicated
            seo = self.state.seo_strategy_report
            tier0_keywords = seo.tier_0_keywords or []
            tier1_keywords = seo.tier_1_keywords or []
            tier2_keywords = seo.tier_2_keywords or []

            seen: set[str] = set()
            high_volume = 0
            core_volume = 0
            competition_values = []

            for kw in (tier0_keywords + tier1_keywords + tier2_keywords):
                key = kw.keyword.lower().strip()
                if key in seen:
                    continue
                seen.add(key)

                core_volume += kw.search_volume or 0

                if (kw.search_volume or 0) > 1000:
                    high_volume += 1

                # Competition strings are formatted as "MEDIUM (53)" - extract numeric value
                if kw.competition:
                    comp_match = re.search(r'\((\d+)\)', kw.competition)
                    if comp_match:
                        competition_values.append(int(comp_match.group(1)))

            avg_competition = None
            if competition_values:
                avg_competition = sum(competition_values) / len(competition_values)
            else:
                logger.warning("⚠️ No competition values found in keywords - avg_competition will be null")

            return SEOAnalytics(
                tier0_count=tier0_count,
                tier1_count=tier1_count,
                tier2_count=tier2_count,
                tier3_count=tier3_count,
                tier4_count=tier4_count,
                total_keywords=total,
                total_search_volume=total_volume,
                core_search_volume=core_volume,
                keyword_diversity_score=diversity,
                high_volume_keywords=high_volume,
                avg_competition=avg_competition
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

            # Calculate avg_competitor_features from competitor key_features
            avg_competitor_features = None
            if selected_landscape.competitors:
                feature_counts = [
                    len(c.key_features)
                    for c in selected_landscape.competitors
                    if c.key_features
                ]
                if feature_counts:
                    avg_competitor_features = sum(feature_counts) / len(feature_counts)
                else:
                    logger.warning("⚠️ No competitor features found - avg_competitor_features will be null")

            # Group features semantically using LLM
            feature_comparison = None
            if selected_landscape.competitors:
                try:
                    feature_comparison = self._group_competitor_features(
                        selected_landscape.competitors
                    )
                except Exception as e:
                    logger.warning(f"Feature grouping skipped: {e}")

            return CompetitiveAnalytics(
                competitor_count=competitor_count,
                market_saturation_score=saturation,
                differentiation_strength=differentiation,
                market_gaps_identified=market_gaps,
                avg_competitor_features=avg_competitor_features,
                feature_comparison=feature_comparison
            )

        except Exception as e:
            logger.warning(f"Failed to compute competitive analytics: {e}")
            return None

    def _group_competitor_features(
        self,
        competitors: list
    ) -> "FeatureComparison | None":
        """Use LLM to semantically group similar features across competitors."""
        from ..models.analytics import FeatureComparison

        # Collect all features with their sources
        all_features = []
        for comp in competitors:
            for feature in (comp.key_features or []):
                all_features.append({
                    "competitor": comp.name,
                    "feature": feature
                })

        if len(all_features) < 4:  # Not enough features to group
            logger.debug("Skipping feature grouping: fewer than 4 features")
            return None

        # Build prompt for LLM
        prompt = f"""Analyze these competitor features and group semantically similar ones.

Features by competitor:
{json.dumps(all_features, indent=2)}

Instructions:
1. Identify features that represent the same capability (even if named differently)
2. Create 5-10 meaningful groups based on what the features actually do
3. For each group, list which competitors have it
4. Prioritize groups where 2+ competitors have the feature (shows meaningful comparison)

Return valid JSON with this structure:
{{
  "feature_groups": [
    {{
      "group_name": "AI/Smart Features",
      "description": "AI-powered automation and intelligent recommendations",
      "competitors_with_feature": ["Competitor A", "Competitor B"],
      "original_features": [
        {{"competitor": "Competitor A", "feature_text": "AI-powered matching"}},
        {{"competitor": "Competitor B", "feature_text": "Smart recommendations"}}
      ]
    }}
  ],
  "total_unique_groups": 5,
  "avg_features_per_competitor": 3.5
}}"""

        try:
            from ..utils.llm_service import LLMService

            # Use LLMService for model-agnostic invocation
            result, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=FeatureComparison,
                temperature=0.1,
                timeout=60,
                model_name=settings.report_schema_llm,  # list-heavy (feature_groups) — gemini truncates here
            )
            self._record_cost("Stage 14 - Feature Comparison", usage)

            # Update computed fields
            result.total_unique_groups = len(result.feature_groups)
            result.avg_features_per_competitor = len(all_features) / len(competitors) if competitors else 0

            logger.info(f"✅ Grouped {len(all_features)} features into {len(result.feature_groups)} semantic groups")

            return result

        except Exception as e:
            logger.warning(f"Feature grouping failed: {e}")
            return None

    def _compute_pain_point_analytics(self) -> "PainPointAnalytics | None":
        """Compute pain point analytics (Python-only)."""
        try:
            from ..models.analytics import PainPointAnalytics

            if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
                return None

            pain_points = self.state.pain_point_analysis.pain_points
            total = len(pain_points)
            high_severity = sum(1 for pp in pain_points if pp.severity_score >= settings.pain_point_high_priority_threshold)
            high_opportunity = sum(1 for pp in pain_points if pp.opportunity_level.value == "high")

            # Quadrant distribution
            quadrants = {
                "high_severity_high_wtp": 0,
                "high_severity_low_wtp": 0,
                "low_severity_high_wtp": 0,
                "low_severity_low_wtp": 0
            }

            for pp in pain_points:
                severity_high = pp.severity_score >= 0.5
                wtp_high = pp.commercial_intent >= 0.5

                if severity_high and wtp_high:
                    quadrants["high_severity_high_wtp"] += 1
                elif severity_high:
                    quadrants["high_severity_low_wtp"] += 1
                elif wtp_high:
                    quadrants["low_severity_high_wtp"] += 1
                else:
                    quadrants["low_severity_low_wtp"] += 1

            avg_severity = sum(pp.severity_score for pp in pain_points) / total
            avg_wtp = sum(pp.commercial_intent for pp in pain_points) / total

            # Top pain point
            sorted_pps = self.accessor.get_sorted_pain_points()
            top_title = sorted_pps[0].title if sorted_pps else "N/A"

            return PainPointAnalytics(
                total_pain_points=total,
                high_severity_count=high_severity,
                high_opportunity_count=high_opportunity,
                quadrant_distribution=quadrants,
                avg_severity=avg_severity,
                avg_commercial_intent=avg_wtp,
                top_pain_point_title=top_title
            )

        except Exception as e:
            logger.warning(f"Failed to compute pain point analytics: {e}")
            return None

    # ==================================================================================
    # Technical Blueprint Generation (Stage 10.5)
    # ==================================================================================

    def _generate_technical_blueprint(
        self, solution: "SolutionIdea"
    ) -> tuple["SiteStructure | None", "UserFlowsSection | None"]:
        """
        Generate site structure and user flows using TechnicalBlueprintCrew.

        Stage 10.5: Creates personalized site architecture and user journey maps
        based on the selected solution's features, personas, and project type.

        Args:
            solution: Selected solution with all enrichments applied

        Returns:
            Tuple of (SiteStructure, UserFlowsSection) or (None, None) on failure
        """
        from ..crews.technical_blueprint_crew import TechnicalBlueprintCrew

        try:
            crew = TechnicalBlueprintCrew()

            site_structure, user_flows = crew.generate(
                solution_name=solution.solution_name,
                description=solution.description or "",
                project_type=solution.project_type or "saas",
                core_features=solution.core_features or [],
                target_personas=solution.target_personas or [],
                data_sources=solution.data_sources or [],
                estimated_indexable_pages=solution.estimated_indexable_pages or 50,
                content_generation_model=solution.content_generation_model or "Manual content",
                value_proposition=solution.value_proposition or solution.description[:200] if solution.description else "",
                organic_discovery_queries=solution.organic_discovery_queries or [],
                pricing_strategy=solution.pricing_strategy or "Freemium model",
            )

            # Log usage metrics
            if crew.usage_metrics:
                logger.info(f"[Stage 10.5] Token usage: {crew.usage_metrics}")

            return site_structure, user_flows

        except Exception as e:
            logger.warning(f"[Stage 10.5] Technical Blueprint generation failed: {e}")
            return None, None
