"""
Pydantic models for research flow state management.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .analytics import (
    CompetitiveAnalytics,
    MarketAnalytics,
    PainPointAnalytics,
    SEOAnalytics,
)
from .competitor import CompetitiveAnalysisResult
from .data_source import DataSourceResearchResult
from .executive_summary import ExecutiveDashboard
from .keyword_data import CrewKeywordValidationResult, KeywordValidationResult
from .marketing_blueprint import GTMBlueprint
from .pain_point import ContentCategorizationReport, PainPoint, PainPointAnalysisResult
from .seo_strategy import SEOStrategyReport
from .social_content import SocialContentCollection
from .solution_idea import (
    CompetitiveEnhancements,
    IdeaGenerationResult,
    SolutionIdea,
    SolutionSEORefinement,
)
from .solution_refinement import SolutionRefinement
from .solution_selection import SelectionCriteriaScore, SolutionSelection
from .technical_blueprint import SiteStructure, UserFlowsSection


class NicheContext(BaseModel):
    """Initial niche understanding (Stage 1)."""

    model_config = ConfigDict(extra='ignore')

    niche_input: str = Field(..., description="User's niche input")
    niche_description: str = Field(..., description="LLM-generated niche description")
    market_segments: list[str] = Field(..., description="Key market segments")
    industry_boundaries: str = Field(..., description="Industry boundaries definition")

class SearchQuery(BaseModel):
    """A single search query."""

    model_config = ConfigDict(extra='ignore')

    query: str = Field(..., description="Search query text")
    query_type: str = Field(
        ..., description="Type: problem/alternative/frustration/solution"
    )
    platform: str = Field(..., description="Target platform: reddit/twitter")

class SearchResultItem(BaseModel):
    """A single search result with metadata for relevance validation."""

    model_config = ConfigDict(extra='ignore')

    url: str = Field(..., description="URL of the search result")
    title: str = Field(..., description="Title of the page/post")
    snippet: str = Field(..., description="Text snippet from search result")

class ThreadRelevanceValidation(BaseModel):
    """Validation result for thread relevance to niche."""

    model_config = ConfigDict(extra='ignore')

    is_relevant: bool = Field(..., description="Whether thread is relevant to niche")
    confidence: float = Field(..., description="Confidence score 0-1")
    reason: str = Field(..., description="Brief explanation of relevance decision")

class SubredditBreakdown(BaseModel):
    """Breakdown of posts by subreddit."""

    model_config = ConfigDict(extra='ignore')

    name: str = Field(..., description="Subreddit name (without r/ prefix)")
    post_count: int = Field(..., description="Number of posts from this subreddit")


# ========== PHASE 6: Report Enhancement Models ==========

class DataQualitySummary(BaseModel):
    """Data quality assessment summary for report transparency."""

    model_config = ConfigDict(extra='ignore')

    social_content_quality_tier: Optional[str] = Field(
        default=None,
        description="Social content quality tier: EXCELLENT, GOOD, MINIMAL, INSUFFICIENT"
    )
    pain_point_quality_tier: Optional[str] = Field(
        default=None,
        description="Pain point analysis quality tier: GOLD, SILVER, BRONZE, INSUFFICIENT"
    )
    pain_point_confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for pain point analysis (0-1)"
    )
    overall_data_quality: str = Field(
        ...,
        description="Overall data quality assessment: HIGH, MEDIUM, LOW"
    )
    quality_caveats: list[str] = Field(
        default_factory=list,
        description="Warnings about data limitations or quality issues"
    )




class RefinementHighlights(BaseModel):
    """Key strategic insights from Stage 8.7 solution refinement."""

    model_config = ConfigDict(extra='ignore')

    top_strategic_insights: list[str] = Field(
        default_factory=list,
        description="Top 3-5 strategic insights from refinement analysis"
    )
    geographic_priority: Optional[str] = Field(
        default=None,
        description="Primary geographic market recommendation"
    )
    feature_priority: Optional[str] = Field(
        default=None,
        description="Top feature to build first based on keyword demand"
    )
    category_pivot_recommendation: Optional[str] = Field(
        default=None,
        description="Category pivot suggestion if applicable"
    )


class StageTimingSummary(BaseModel):
    """Pipeline execution timing summary."""

    model_config = ConfigDict(extra='ignore')

    total_duration_seconds: float = Field(
        ...,
        description="Total pipeline execution time in seconds"
    )
    stage_durations: dict[str, float] = Field(
        default_factory=dict,
        description="Duration per stage in seconds (stage number → duration)"
    )
    slowest_stage: Optional[str] = Field(
        default=None,
        description="Name/number of the slowest stage"
    )
    fastest_stage: Optional[str] = Field(
        default=None,
        description="Name/number of the fastest stage"
    )


class SEOCalculationTransparency(BaseModel):
    """Transparency into SEO score calculations from Stage 9.6."""

    model_config = ConfigDict(extra='ignore')

    baseline_seo_score: Optional[float] = Field(
        default=None,
        description="Original SEO scalability score before refinement"
    )
    refined_seo_score: Optional[float] = Field(
        default=None,
        description="Final refined SEO scalability score"
    )
    volume_multiplier: Optional[float] = Field(
        default=None,
        description="Applied volume adjustment multiplier"
    )
    competition_modifier: Optional[float] = Field(
        default=None,
        description="Competition factor applied to calculations"
    )
    tier1_multiplier: Optional[float] = Field(
        default=None,
        description="Quick-win (Tier 1) keyword bonus multiplier"
    )
    estimated_year1_pages: Optional[int] = Field(
        default=None,
        description="Projected programmatic pages in year 1"
    )
    calculation_rationale: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of score calculation"
    )


class ResearchMetadata(BaseModel):
    """Metadata about the research data collection process."""

    model_config = ConfigDict(extra='ignore')

    reddit_posts_analyzed: int = Field(..., description="Total Reddit posts collected")
    reddit_comments_analyzed: int = Field(..., description="Total Reddit comments analyzed")
    twitter_threads_analyzed: int = Field(..., description="Total Twitter threads collected")
    top_subreddits: list[SubredditBreakdown] = Field(
        ..., description="Breakdown of posts by subreddit (top 10)"
    )
    collection_date: datetime = Field(..., description="When data collection occurred")
    data_size_mb: float = Field(..., description="Total data size in megabytes")

    # NEW: Stage completion tracking (Phase 4 - diagnostic visibility)
    completed_stages: Optional[list[float]] = Field(
        default=None,
        description="List of completed pipeline stages (e.g., [5, 6, 6.5, 7, 8, 8.5, 9, 9.5, 10])"
    )
    fallback_stages: Optional[list[float]] = Field(
        default=None,
        description="Stages that used fallback/incomplete data (for quality assessment)"
    )
    filtering_stats: Optional[dict[str, Any]] = Field(
        default=None,
        description="Stage 5 URL filtering statistics (searched, relevant, filtering rate)"
    )

    # Pipeline timing metadata
    started_at: Optional[str] = Field(default=None, description="Pipeline start time (ISO 8601)")

class AlternativeSolution(BaseModel):
    """Enhanced alternative solution with competitive analysis details."""

    model_config = ConfigDict(extra='ignore')

    # Core identification
    solution_name: str = Field(..., description="Name of the alternative solution")
    summary: str = Field(..., description="2-3 paragraph overview of the solution")

    # Existing score fields
    market_fit_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Market fit score (None if not assessed)")
    technical_feasibility_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Technical feasibility (None if not assessed)")
    competitive_advantage_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Competitive advantage score (None if not assessed)")
    seo_growth_potential_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="SEO scalability score (None if not assessed)")

    # Existing strategic fields
    key_differentiator: str = Field(..., description="Primary unique value proposition")
    best_suited_for: str = Field(..., description="When this solution is the best choice")
    pivot_trigger: str = Field(..., description="Conditions that would justify pivoting to this solution")

    # NEW: Core solution details
    description: Optional[str] = Field(default=None, description="Brief description of the solution")
    value_proposition: Optional[str] = Field(default=None, description="Value proposition statement")
    core_features: Optional[list[str]] = Field(default=None, description="Top 3-5 core features")
    target_personas: Optional[list[str]] = Field(default=None, description="Primary target personas")
    technical_approach: Optional[str] = Field(default=None, description="Technical implementation approach")

    # NEW: Additional scores and feasibility
    novelty_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Innovation/novelty score")
    solo_dev_feasibility: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Solo developer feasibility score (0-1)")

    # NEW: Competitive landscape for this solution
    top_competitors: Optional[list[str]] = Field(default=None, description="Top 3 competitors for this solution")
    market_gaps: Optional[list[str]] = Field(default=None, description="Key market gaps this solution addresses")
    competitive_intensity: Optional[str] = Field(default=None, description="Competitive intensity: LOW, MEDIUM, HIGH")

    # NEW: Economic indicators
    estimated_development_time: Optional[str] = Field(default=None, description="Estimated development time")
    estimated_cac_organic: Optional[str] = Field(default=None, description="Estimated organic customer acquisition cost (e.g. '$15-30')")
    pricing_model: Optional[str] = Field(default=None, description="Recommended pricing model")

class CompetitorMatrixEntry(BaseModel):
    """Single competitor entry showing which solutions it competes against."""

    model_config = ConfigDict(extra='ignore')

    competitor_name: str = Field(..., description="Name of the competitor")
    solutions_competed: list[str] = Field(..., description="List of solution names this competitor appears in")
    competitor_type: str = Field(..., description="Type: direct, partial, indirect")
    threat_level: str = Field(..., description="Overall threat level: high, medium, low")


class CompetitorCard(BaseModel):
    """Detailed competitor profile for report - preserves full competitor data."""

    model_config = ConfigDict(extra='ignore')

    name: str = Field(..., description="Name of the competitor")
    url: Optional[str] = Field(default=None, description="Website URL")
    competitor_type: str = Field(..., description="Type: DIRECT, PARTIAL, or INDIRECT")
    description: str = Field(..., description="What this competitor offers")
    key_features: list[str] = Field(default_factory=list, description="Main features they provide")
    pricing_model: Optional[str] = Field(default=None, description="Pricing model if available")
    strengths: list[str] = Field(default_factory=list, description="Competitor strengths")
    weaknesses: list[str] = Field(default_factory=list, description="Competitor weaknesses")

class CompetitiveIntensityEntry(BaseModel):
    """Competitive intensity for a single solution."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution")
    intensity: str = Field(..., description="Competitive intensity: Low, Medium, or High")

class CompetitiveLandscapeMatrix(BaseModel):
    """Cross-solution competitive analysis showing overlap and patterns."""

    model_config = ConfigDict(extra='ignore')

    all_solutions_analyzed: list[str] = Field(..., description="Names of all solutions analyzed")
    selected_solution_competitors: list[str] = Field(
        default_factory=list,
        description="Direct competitors for the selected solution (names only for executive summary)"
    )
    competitor_overlap: list[CompetitorMatrixEntry] = Field(
        ..., description="Competitors appearing in multiple solution landscapes"
    )
    competitive_intensity_by_solution: list[CompetitiveIntensityEntry] = Field(
        ..., description="Competitive intensity for each solution analyzed"
    )
    market_insight: str = Field(
        ..., description="Strategic insight about competitive landscape patterns"
    )

class TopRedditThread(BaseModel):
    """Summary of a high-engagement Reddit thread for evidence appendix."""

    model_config = ConfigDict(extra='ignore')

    post_id: str = Field(..., description="Reddit post ID")
    title: str = Field(..., description="Post title")
    subreddit: str = Field(..., description="Subreddit name")
    score: int = Field(..., description="Post score (upvotes)")
    num_comments: int = Field(..., description="Number of comments")
    url: str = Field(..., description="Link to Reddit post")
    key_insight: str = Field(..., description="1-sentence summary of why this thread is significant")

class QuoteSource(BaseModel):
    """Single quote with source attribution."""

    model_config = ConfigDict(extra='ignore')

    quote: str = Field(..., description="The quote text")
    post_id: str = Field(..., description="Post ID where quote was found")
    subreddit: str = Field(..., description="Subreddit name")
    score: str = Field(..., description="Post score/engagement")

class PainPointEvidence(BaseModel):
    """Evidence linking pain point quotes to original Reddit posts."""

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(..., description="Pain point title")
    quotes_with_sources: list[QuoteSource] = Field(
        ..., description="List of quotes with source attribution"
    )

class EvidenceAppendix(BaseModel):
    """Appendix containing evidence traceability for research validation."""

    model_config = ConfigDict(extra='ignore')

    top_reddit_threads: list[TopRedditThread] = Field(
        ..., description="Top 10 most engaging Reddit discussions analyzed"
    )
    pain_point_quote_sources: list[PainPointEvidence] = Field(
        ..., description="Traceability from pain points to original posts"
    )

class DataInfrastructurePhase(BaseModel):
    """Single phase of data infrastructure implementation."""

    model_config = ConfigDict(extra='ignore')

    phase_number: int = Field(..., description="Phase number (1, 2, or 3)")
    phase_name: str = Field(..., description="Phase name (e.g., 'MVP', 'Growth', 'Scale')")
    timeline: str = Field(..., description="Timeline for this phase (e.g., 'Months 1-3')")
    data_sources: list[str] = Field(..., description="Data sources to integrate in this phase")
    estimated_monthly_cost: str = Field(..., description="Cost range for this phase (e.g., '$200-300')")
    key_risks: list[str] = Field(..., description="Risks and mitigation strategies")

class DataInfrastructureRoadmap(BaseModel):
    """Complete data infrastructure implementation roadmap."""

    model_config = ConfigDict(extra='ignore')

    phases: list[DataInfrastructurePhase] = Field(..., description="3-phase implementation plan")
    cost_scaling_insight: str = Field(
        ..., description="Summary of how costs scale with user growth and mitigation strategies"
    )

class FinalReport(BaseModel):
    """Final comprehensive research report (Stage 10)."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="Niche analyzed")
    executive_summary: str = Field(..., description="High-level executive summary")

    # Executive Dashboard (Phase 1 Enhancement) - TOP-LEVEL SUMMARY
    executive_dashboard: Optional[ExecutiveDashboard] = Field(
        default=None,
        description="Executive dashboard with go/no-go verdict, core pain point, and key opportunity metrics for quick decision-making"
    )

    # Go-to-Market Blueprint (Phase 2 Enhancement) - ACTIONABLE GTM STRATEGY
    go_to_market_blueprint: Optional[GTMBlueprint] = Field(
        default=None,
        description="Actionable Go-to-Market strategy with ICP, marketing channels, messaging, content angles, and 30-day playbook for immediate execution"
    )

    # Analytics & Visualizations (Phase 3 Enhancement) - DATA-DRIVEN INSIGHTS
    market_analytics: Optional[MarketAnalytics] = Field(
        default=None,
        description="Computed market opportunity analytics: overall score, market size category, selection confidence, competitive intensity, go/no-go recommendation"
    )
    seo_analytics: Optional[SEOAnalytics] = Field(
        default=None,
        description="SEO keyword distribution analytics: tier counts, total search volume, keyword diversity, high-volume keyword count"
    )
    competitive_analytics: Optional[CompetitiveAnalytics] = Field(
        default=None,
        description="Competitive density analytics: competitor count, market saturation score, differentiation strength, market gaps identified"
    )
    pain_point_analytics: Optional[PainPointAnalytics] = Field(
        default=None,
        description="Pain point priority analytics: total count, high-priority count, quadrant distribution, average severity/WTP scores"
    )

    # Data Quality & Pipeline Transparency (Phase 6)
    data_quality_summary: Optional[DataQualitySummary] = Field(
        default=None,
        description="Data quality assessment: quality tiers, confidence scores, caveats"
    )
    refinement_highlights: Optional[RefinementHighlights] = Field(
        default=None,
        description="Key strategic insights from Stage 8.7 solution refinement"
    )
    stage_timing_summary: Optional[StageTimingSummary] = Field(
        default=None,
        description="Pipeline execution timing for performance visibility"
    )
    seo_calculation_transparency: Optional[SEOCalculationTransparency] = Field(
        default=None,
        description="SEO score calculation methodology from Stage 9.6"
    )

    # Solution Selection (Stage 8.5)
    selected_solution_name: str = Field(..., description="Name of the selected solution to focus on")
    selection_rationale: str = Field(..., description="Why this solution was selected over alternatives")
    # runner_up_solutions removed - use alternative_solutions instead
    selection_criteria_scores: Optional[list[SelectionCriteriaScore]] = Field(
        default=None,
        description="Breakdown of selection criteria scores (0-1 scale): market_fit, technical_feasibility, competitive_advantage, keyword_opportunity, data_requirements"
    )
    recommended_focus: Optional[str] = Field(
        default=None,
        description="Strategic focus recommendation for the selected solution (e.g., geographic expansion, segment targeting, niche dominance)"
    )

    # Detailed Solution Description (NEW - addresses "WHAT" and "HOW" gaps)
    selected_solution_details: Optional[SolutionIdea] = Field(
        default=None,
        description="Complete details of the selected solution including features, personas, technical approach, pricing strategy"
    )
    solution_user_journey: Optional[str] = Field(
        default=None,
        description="Step-by-step user workflow explaining HOW users interact with the solution (5-8 numbered steps, markdown format)"
    )
    solution_implementation_overview: Optional[str] = Field(
        default=None,
        description="High-level implementation plan with phases, timeline, dependencies (2-3 paragraphs, markdown format)"
    )
    mvp_scope_definition: Optional[str] = Field(
        default=None,
        description="Detailed MVP scope: must-have features, post-MVP features, success criteria (markdown format with sections)"
    )

    # Site Structure and User Flows (Stage 10.5 - LLM-generated, personalized)
    site_structure: Optional[SiteStructure] = Field(
        default=None,
        description="LLM-generated site architecture with sections, pages, URL patterns, and MVP priorities"
    )
    user_flows: Optional[UserFlowsSection] = Field(
        default=None,
        description="LLM-generated user journeys showing how target personas discover, use, and convert"
    )

    # Pricing Strategy for selected solution (extracted from pricing_strategies in ResearchState)
    pricing_strategy: Optional['PricingStrategyResult'] = Field(
        default=None,
        description="Pricing strategy for the selected solution with recommended tiers, ARPU, LTV estimates"
    )

    # Traffic Monetization for selected solution (for directories/aggregators - alternative to pricing_strategy)
    traffic_monetization: Optional['TrafficMonetizationResult'] = Field(
        default=None,
        description="Traffic monetization strategy for the selected solution (ads, affiliates, sponsored listings) - used for directories/aggregators instead of pricing_strategy"
    )

    # Problem Section
    # top_pain_points removed - use detailed_pain_points instead
    pain_points_summary: str = Field(
        ..., description="Summary of pain point analysis with severity and WTP insights"
    )
    # pain_point_categories removed - derive from detailed_pain_points.categories
    detailed_pain_points: Optional[list[PainPoint]] = Field(
        default=None,
        description="Complete pain point objects with metadata (scores, quotes, categories)"
    )

    # Solution Section
    recommended_solutions: list[str] = Field(
        ..., description="Recommended solution ideas to pursue"
    )
    solutions_summary: str = Field(
        ..., description="Summary of solution ideas with market fit and differentiation"
    )

    # Competitive Section
    competitive_summary: str = Field(
        ..., description="Summary of competitive landscape and positioning opportunities"
    )
    competitive_analysis: Optional[CompetitiveAnalysisResult] = Field(
        default=None,
        description="Complete competitive analysis: solution landscapes, top opportunities, strategic recommendations (from Stage 7)"
    )

    # Market Validation
    market_validation: str = Field(..., description="Overall market validation conclusion")

    # Organic Acquisition Strategy (NEW - SEO-First Focus)
    acquisition_strategy_summary: Optional[str] = Field(
        default=None,
        description=(
            "Overview of customer acquisition strategy emphasizing organic channels. "
            "Explains the content generation model, programmatic SEO opportunities, "
            "and how the product architecture naturally creates indexable pages. "
            "2-3 paragraphs covering: (1) content creation mechanism, (2) discovery patterns, "
            "(3) scaling strategy for organic growth."
        )
    )
    estimated_cac_breakdown: Optional[str] = Field(
        default=None,
        description=(
            "Customer acquisition cost breakdown comparing organic vs paid channels. "
            "Format: Markdown table or structured text with: "
            "(1) Organic CAC estimate with rationale, "
            "(2) Paid CAC estimate for comparison, "
            "(3) CAC advantage ratio (X:1), "
            "(4) Scalability assessment. "
            "Should reference programmatic SEO page count, keyword search volumes, "
            "and project type benchmarks (directories $15-30, aggregators $20-40, etc.)."
        )
    )

    # Keyword Validation & Refinement (Stage 8.5 and 8.7)
    keyword_validation_overview: Optional[str] = Field(
        default=None,
        description=(
            "Executive summary of keyword validation results across top N solution candidates from Stage 8.5. "
            "Format: 2-3 paragraphs covering: "
            "(1) Validation methodology and data sources (e.g., DataForSEO metrics), "
            "(2) Key findings per solution with quantitative metrics (total keywords, Tier 1 count, avg search volume), "
            "(3) Cross-solution comparison highlighting keyword opportunities and competitive density. "
            "Should reference specific data points from keyword_validation_results to support strategic decisions."
        )
    )

    solution_keyword_comparison: Optional[str] = Field(
        default=None,
        description=(
            "Comparative keyword analysis showing how top N solutions differ in SEO opportunity from Stage 8.5. "
            "Format: Markdown table or structured comparison with: "
            "(1) Solution name and total validated keywords, "
            "(2) Tier 1 quick wins count and average competition level, "
            "(3) Total market volume and geographic distribution, "
            "(4) SEO difficulty assessment (Low/Medium/High) with rationale. "
            "Used to justify solution selection based on organic acquisition potential."
        )
    )

    content_strategy_preview: Optional[str] = Field(
        default=None,
        description=(
            "Preview of content strategy recommendations based on keyword validation insights from Stage 8.5. "
            "Format: 2-3 paragraphs outlining: "
            "(1) Programmatic content opportunities identified (page templates, topic clusters), "
            "(2) Geographic or categorical expansion priorities from keyword data, "
            "(3) Quick win content recommendations for immediate SEO traction (Tier 1 keywords). "
            "Serves as bridge between keyword validation and detailed SEO strategy (Stage 9)."
        )
    )

    # Data Sourcing Summary (for solutions requiring aggregation)
    data_sourcing_recommendations: str = Field(
        ..., description="Data sourcing strategy for aggregation projects"
    )

    # Next Steps
    next_steps: list[str] = Field(..., description="Recommended next steps")

    # Enhanced Report Sections (NEW - improve data preservation and traceability)
    research_metadata: Optional[ResearchMetadata] = Field(
        default=None,
        description="Metadata about data collection: Reddit/Twitter post counts, subreddit breakdown, collection date, data size"
    )
    alternative_solutions: Optional[list[AlternativeSolution]] = Field(
        default=None,
        description="Detailed summaries of runner-up solutions with scores and pivot criteria (top 2 alternatives)"
    )
    competitive_landscape_matrix: Optional[CompetitiveLandscapeMatrix] = Field(
        default=None,
        description="Cross-solution competitive analysis showing competitor overlap and intensity patterns"
    )
    evidence_appendix: Optional[EvidenceAppendix] = Field(
        default=None,
        description="Traceability appendix: top Reddit threads analyzed and pain point quote sources with post IDs"
    )
    data_infrastructure_roadmap: Optional[DataInfrastructureRoadmap] = Field(
        default=None,
        description="3-phase data infrastructure implementation plan with cost projections and scale risks"
    )
    content_categorization: Optional[ContentCategorizationReport] = Field(
        default=None,
        description="Content categorization analysis: theme categories, user segments, and discussion quality from Stage 6 Task 1"
    )

    # Data Richness Enhancements - Preserve Full Objects
    solution_innovation_assessment: Optional[dict] = Field(
        default=None,
        description="Innovation metrics: novelty_score, conventional_approach, innovation_angle, why_it_works, solo_dev_feasibility"
    )
    # solution_organic_discovery removed - use selected_solution_details.organic_discovery_queries instead
    competitor_profiles: list[CompetitorCard] = Field(
        default_factory=list,
        description="Detailed competitor profiles with features, pricing, strengths, weaknesses"
    )

    # REMOVED: ideation_process - not reliably populated, transparency not needed in final report

    # Competitive Strategic Insights (NEW - preserves overall_competitive_insights from Stage 7.5)
    overall_competitive_insights: Optional[str] = Field(
        default=None,
        description="Cross-solution competitive insights and market positioning (from Stage 7.5)"
    )

    # ========== FULL STAGE DATA (NEW - preserves complete pipeline outputs) ==========

    # Stage 1-4: Full Niche Context
    niche_context: Optional[NicheContext] = Field(
        default=None,
        description="Full niche context with market segments and industry boundaries from Stages 1-4"
    )

    # Stage 6.5: Audience Intelligence (full object)
    # Note: Using string forward reference since AudienceMappingResult is defined later in this file
    audience_mapping: Optional["AudienceMappingResult"] = Field(
        default=None,
        description="Complete audience mapping: segments, influencers, messaging frameworks from Stage 6.5"
    )

    # Stage 8.6: Market Sizing (full object)
    # Note: Using string forward reference since MarketSizingResult is defined later in this file
    market_sizing: Optional["MarketSizingResult"] = Field(
        default=None,
        description="TAM/SAM/SOM analysis, viability verdict, growth drivers, risks from Stage 8.6"
    )

    # Stage 9.5: Trend Longevity (full object)
    # Note: Using string forward reference since TrendLongevityResult is defined later in this file
    trend_longevity: Optional["TrendLongevityResult"] = Field(
        default=None,
        description="Market momentum, trend direction, seasonality, timing recommendation from Stage 9.5"
    )

    # Stage 9: Full SEO Strategy (full object, not just analytics)
    seo_strategy_report: Optional[SEOStrategyReport] = Field(
        default=None,
        description="Complete SEO strategy with implementation roadmap, content strategy from Stage 9"
    )

    # Stage 9.7: Full Data Source Research (full object, not just string summary)
    data_source_research_full: Optional[DataSourceResearchResult] = Field(
        default=None,
        description="Full data source analysis with provider details, costs, integration plan from Stage 9.7"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation timestamp"
    )


# Stage 8.7: Pricing Strategy Validation
class PricingStrategyResult(BaseModel):
    """Pricing strategy validation result from Stage 8.7."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution being priced")

    # Recommended Pricing (optional for Ad-Supported-Free/Affiliate-Only models)
    recommended_starter_price: Optional[str] = Field(
        default=None, description="Starter tier price (e.g., '$19/month') - null for ad/affiliate models"
    )
    recommended_pro_price: Optional[str] = Field(
        default=None, description="Pro tier price (e.g., '$49/month') - null for ad/affiliate models"
    )
    recommended_enterprise_price: Optional[str] = Field(
        default=None, description="Enterprise tier price if applicable"
    )

    pricing_model: Literal[
        "Freemium",           # Free tier + paid upgrades (typically 3-tier: Free/Pro/Enterprise)
        "Freemium-Lite",      # Free + single paid tier (2-tier: Free/Pro, no enterprise)
        "Subscription",       # Pure subscription (no free tier)
        "Hybrid",             # Subscription + usage-based
        "One-time",           # Single purchase
        "Usage-Based",        # Pay-per-use (API calls, credits)
        "Ad-Supported-Free",  # Free tool, monetized by ads only
        "Affiliate-Only",     # Free tool, monetized by affiliate links only
    ] = Field(
        ..., description="Pricing model type - select based on solution type and WTP scores"
    )
    pricing_rationale: str = Field(..., description="Why this pricing strategy was chosen")

    # Feature Tiers (optional for Ad-Supported-Free/Affiliate-Only models)
    free_tier_features: Optional[list[str]] = Field(
        default=None, description="Features included in free tier (if freemium)"
    )
    starter_tier_features: Optional[list[str]] = Field(
        default=None, description="Features in starter tier - null for ad/affiliate models"
    )
    pro_tier_features: Optional[list[str]] = Field(
        default=None, description="Features in pro tier - null for ad/affiliate models"
    )

    # Ad/Affiliate Revenue Fields (for Ad-Supported-Free/Affiliate-Only models)
    estimated_monthly_ad_revenue: Optional[str] = Field(
        default=None, description="Estimated monthly ad revenue (e.g., '$400-800') - for ad-supported models"
    )
    estimated_monthly_affiliate_revenue: Optional[str] = Field(
        default=None, description="Estimated monthly affiliate revenue (e.g., '$200-400') - for affiliate models"
    )
    estimated_cpm_rate: Optional[str] = Field(
        default=None, description="Estimated CPM rate (e.g., '$5-15 CPM') - for ad-supported models"
    )
    recommended_ad_networks: Optional[list[str]] = Field(
        default=None, description="Recommended ad networks (e.g., ['AdSense', 'Mediavine']) - for ad-supported models"
    )

    # Economics
    estimated_arpu: str = Field(..., description="Estimated average revenue per user (e.g., '$32/month')")
    estimated_ltv: str = Field(
        ..., description="Estimated lifetime value range (e.g., '$384 - $960 (12-30mo retention)')"
    )
    ltv_to_cac_ratio: str = Field(
        ..., description="LTV to CAC ratio estimate (e.g., '12:1 to 48:1')"
    )

    # Competitive Positioning
    price_vs_competitors: str = Field(
        ..., description="Pricing relative to competitors (e.g., '10% below median')"
    )
    value_proposition_delta: str = Field(
        ..., description="Value proposition compared to competitors (e.g., '15% more features at 20% lower price')"
    )
    pricing_confidence: Literal["High", "Medium", "Low"] = Field(
        ..., description="Confidence level: 'High', 'Medium', 'Low'"
    )

    # Validation
    wtp_validation: str = Field(
        ..., description="How pain point willingness-to-pay scores support this pricing"
    )
    market_segment_pricing: Optional[dict[str, Optional[str]]] = Field(
        default=None, description="Different pricing for different market segments if applicable"
    )


# Stage 8.55: Traffic Monetization Strategy (for directories/aggregators/comparison-tools)
class TrafficMonetizationResult(BaseModel):
    """Traffic-based monetization strategy for directories/aggregators."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution being analyzed")
    monetization_model: Literal["Ad-Supported", "Affiliate", "Hybrid-Traffic", "Lead-Gen"] = Field(
        ..., description="Primary monetization model: 'Ad-Supported', 'Affiliate', 'Hybrid-Traffic', 'Lead-Gen'"
    )

    # Traffic Projections (from keyword data)
    estimated_monthly_pageviews: str = Field(
        ..., description="Estimated monthly pageviews range (e.g., '50,000 - 100,000')"
    )
    traffic_source_breakdown: dict[str, str] = Field(
        ..., description="Traffic source distribution (e.g., {'organic_search': '70%', 'direct': '20%', 'referral': '10%'})"
    )

    # Ad Revenue Estimates
    estimated_cpm_rate: str = Field(
        ..., description="Estimated CPM rate for this niche (e.g., '$3-8 CPM (lifestyle niche)')"
    )
    estimated_monthly_ad_revenue: str = Field(
        ..., description="Estimated monthly ad revenue range (e.g., '$150 - $800')"
    )
    recommended_ad_networks: list[str] = Field(
        ...,
        min_length=1,
        description="Recommended ad networks based on traffic tier (e.g., ['Google AdSense', 'Mediavine', 'Ezoic'], minimum 1)"
    )

    # Affiliate Revenue Estimates
    affiliate_commission_rate: str = Field(
        ..., description="Typical affiliate commission rates (e.g., '5-15% (Amazon Associates)')"
    )
    estimated_affiliate_ctr: str = Field(
        ..., description="Estimated affiliate click-through rate (e.g., '2-5% of pageviews')"
    )
    estimated_monthly_affiliate_revenue: str = Field(
        ..., description="Estimated monthly affiliate revenue (e.g., '$200 - $500')"
    )
    recommended_affiliate_programs: list[str] = Field(
        ..., min_length=1, description="Recommended affiliate programs for this niche (minimum 1)"
    )

    # Premium/Sponsored Options (B2B)
    sponsored_listing_price: Optional[str] = Field(
        default=None, description="Suggested sponsored listing price (e.g., '$99/month per listing')"
    )
    premium_placement_price: Optional[str] = Field(
        default=None, description="Premium featured placement price (e.g., '$299/month featured')"
    )
    lead_gen_price_per_lead: Optional[str] = Field(
        default=None, description="Lead generation pricing (e.g., '$15-30 per qualified lead')"
    )

    # Total Revenue Projection
    estimated_monthly_revenue_range: str = Field(
        ..., description="Total estimated monthly revenue range (e.g., '$500 - $2,000')"
    )
    estimated_annual_revenue_range: str = Field(
        ..., description="Total estimated annual revenue range"
    )
    break_even_traffic_threshold: str = Field(
        ..., description="Traffic threshold for break-even (e.g., '25,000 monthly pageviews')"
    )

    # Strategy
    monetization_rationale: str = Field(
        ..., description="Explanation of why this monetization mix was recommended"
    )
    scaling_strategy: str = Field(
        ..., description="How to grow revenue as traffic scales (network upgrades, affiliate optimization, etc.)"
    )
    monetization_confidence: Literal["High", "Medium", "Low"] = Field(
        ..., description="Confidence level: 'High', 'Medium', 'Low'"
    )

    # Comparison to SaaS (context for decision-making)
    saas_alternative_viable: bool = Field(
        ..., description="Whether this could also work as a subscription SaaS"
    )
    saas_vs_traffic_recommendation: str = Field(
        ..., description="Recommendation on traffic vs SaaS monetization with rationale"
    )


# Stage 6.5: Audience & Influence Mapping
class AudienceSegment(BaseModel):
    """Individual audience segment with characteristics."""

    model_config = ConfigDict(extra='ignore')

    segment_name: str = Field(..., description="Name of audience segment (e.g., 'Solo Founders', 'Marketing Managers')")
    size_estimate: str = Field(..., description="Estimated size: 'Large', 'Medium', 'Small'")
    pain_point_alignment: list[str] = Field(..., description="Top 3 pain points this segment experiences")
    motivation_drivers: list[str] = Field(..., description="Key motivations and goals (3-5 items)")
    expertise_level: str = Field(..., description="Technical/domain expertise: 'Beginner', 'Intermediate', 'Advanced'")
    budget_sensitivity: str = Field(..., description="Price sensitivity: 'High', 'Medium', 'Low'")
    discovery_channels: list[str] = Field(..., description="Where they discover solutions (Reddit, Twitter, Google, communities)")
    influencers_followed: Optional[list[str]] = Field(default=None, description="Key influencers or communities they follow")


class InfluencerProfile(BaseModel):
    """Influencer or community leader in the niche."""

    model_config = ConfigDict(extra='ignore')

    name: str = Field(..., description="Username or community name")
    platform: str = Field(..., description="Platform: 'Reddit', 'Twitter', 'YouTube', etc.")
    follower_estimate: Optional[str] = Field(default=None, description="Follower/subscriber count estimate")
    relevance_score: float = Field(..., description="Relevance to niche (0-1 scale)")
    content_focus: str = Field(..., description="Primary content focus/topics")
    engagement_level: str = Field(..., description="'High', 'Medium', 'Low' based on discussion activity")
    outreach_priority: str = Field(..., description="'High', 'Medium', 'Low' for partnership/outreach")


class AudienceMappingResult(BaseModel):
    """Complete audience mapping analysis result from Stage 6.5."""

    model_config = ConfigDict(extra='ignore')

    # Audience Segments
    audience_segments: list[AudienceSegment] = Field(
        ..., min_length=3, max_length=5, description="3-5 distinct audience segments identified"
    )
    primary_target_segment: str = Field(..., description="Recommended primary target segment name")
    segment_prioritization_rationale: str = Field(..., description="Why this segment should be targeted first (2-3 sentences)")

    # Influencers & Communities
    key_influencers: list[InfluencerProfile] = Field(
        ..., min_length=5, max_length=10, description="Top 5-10 influencers/communities in the niche"
    )
    community_hubs: list[str] = Field(..., description="Key online communities/forums (subreddits, Discord servers, forums)")

    # Content & Messaging Insights
    common_vocabulary: list[str] = Field(
        ..., min_length=10, max_length=15, description="10-15 terms/phrases frequently used by audience"
    )
    content_preferences: str = Field(..., description="Preferred content types and formats (e.g., tutorials, comparisons, case studies)")
    messaging_frameworks: list[str] = Field(..., description="3-5 messaging angles that resonate (e.g., 'save time', 'increase revenue')")

    # Competitive Intelligence
    tools_currently_used: list[str] = Field(..., description="Current tools/solutions audience mentions using")
    frustrations_with_existing: list[str] = Field(..., description="Top frustrations with current solutions")

    # Acquisition Strategy Implications
    recommended_channels: list[str] = Field(..., description="Top 3-5 marketing channels for this audience")
    early_adopter_tactics: Optional[str] = Field(default=None, description="Tactics to acquire first 100 users")


# Stage 8.6: Market Sizing & Validation
class MarketSegmentSizing(BaseModel):
    """Market size breakdown for a specific segment."""

    model_config = ConfigDict(extra='ignore')

    segment_name: str = Field(..., description="Market segment name (e.g., 'Small SaaS Companies', 'Solo Developers')")
    tam_estimate: str = Field(..., description="Total Addressable Market size (e.g., '$500M', '2M users')")
    sam_estimate: str = Field(..., description="Serviceable Available Market size (e.g., '$150M', '600K users')")
    som_estimate: str = Field(..., description="Serviceable Obtainable Market (Year 1-3) (e.g., '$5M', '20K users')")
    sizing_methodology: str = Field(..., description="How this estimate was calculated (top-down, bottom-up, keyword-based)")
    confidence_level: str = Field(..., description="Estimate confidence: 'High', 'Medium', 'Low'")


class MarketSizingResult(BaseModel):
    """Complete market sizing and validation analysis from Stage 8.6."""

    model_config = ConfigDict(extra='ignore')

    # Overall Market Sizing (TAM/SAM/SOM)
    total_addressable_market: str = Field(..., description="TAM estimate across all segments (e.g., '$2.5B', '10M users')")
    serviceable_available_market: str = Field(..., description="SAM estimate for solution's reach (e.g., '$800M', '3M users')")
    serviceable_obtainable_market_y1: str = Field(..., description="SOM Year 1 realistic capture (e.g., '$2M', '8K users')")
    serviceable_obtainable_market_y3: str = Field(..., description="SOM Year 3 growth target (e.g., '$15M', '50K users')")

    # Market Sizing Methodology
    primary_methodology: str = Field(..., description="Primary calculation method: 'Top-Down', 'Bottom-Up', 'Keyword-Based', 'Hybrid'")
    methodology_explanation: str = Field(..., description="2-3 sentences explaining how market size was calculated")
    data_sources_used: list[str] = Field(..., description="Data sources: keyword volumes, industry reports, pain point frequency, competitor analysis")

    # Segment Breakdown (optional granular view)
    segment_sizing: Optional[list[MarketSegmentSizing]] = Field(
        default=None,
        description="Granular TAM/SAM/SOM breakdown by market segment if applicable"
    )

    # Market Validation Signals
    keyword_demand_signal: str = Field(..., description="Total monthly search volume across all keywords (e.g., '2.5M searches/month')")
    pain_point_frequency: str = Field(..., description="Discussion frequency of pain points (e.g., '5,000+ mentions across 200 threads')")
    competitor_market_presence: str = Field(..., description="Number of active competitors indicating market validation (e.g., '15+ active SaaS competitors')")

    # Growth Potential
    market_growth_rate: Optional[str] = Field(default=None, description="Estimated annual market growth rate (e.g., '15-20% CAGR')")
    growth_drivers: list[str] = Field(..., description="3-5 factors driving market growth (trends, technology adoption, regulatory changes)")

    # Market Risk Assessment
    market_saturation_level: str = Field(..., description="'Low' (<5 competitors), 'Medium' (5-15), 'High' (15+)")
    market_timing_assessment: str = Field(..., description="'Early' (emerging), 'Growth' (expanding), 'Mature' (saturated)")
    risk_factors: list[str] = Field(..., description="3-5 key market risks (saturation, regulatory, technology shifts)")

    # Viability Conclusion
    market_viability_verdict: str = Field(..., description="'Strong', 'Moderate', 'Weak' - overall market attractiveness")
    viability_rationale: str = Field(..., description="2-3 sentences justifying the viability verdict with specific metrics")
    recommended_entry_strategy: str = Field(..., description="Market entry recommendation: 'Aggressive Growth', 'Measured Expansion', 'Niche Focus', 'Reconsider'")


class TrendLongevityResult(BaseModel):
    """Trend longevity and market momentum analysis from Stage 9.2."""

    model_config = ConfigDict(extra='ignore')

    # Overall Trend Assessment
    trend_direction: Literal["Growing", "Stable", "Declining"] = Field(
        ..., description="Overall market trend direction"
    )
    trend_confidence: Literal["High", "Medium", "Low"] = Field(
        ..., description="Confidence in trend assessment based on data quality"
    )
    momentum_score: float = Field(
        ..., ge=0.0, le=1.0, description="0.0-1.0 score indicating market momentum (0=declining, 0.5=stable, 1.0=strong growth)"
    )

    # Keyword Trend Analysis
    keyword_volume_trend: Literal["Increasing", "Stable", "Decreasing"] = Field(
        ..., description="Search volume trend"
    )
    volume_growth_rate: Optional[str] = Field(default=None, description="Estimated YoY growth rate (e.g., '+25% YoY', '-10% YoY', 'Stable')")
    trend_duration: Optional[str] = Field(default=None, description="How long trend has been active (e.g., '2+ years growth', '6 months spike', 'Emerging')")

    # Discussion Momentum (Social Signals)
    discussion_frequency_trend: Literal["Increasing", "Stable", "Decreasing"] = Field(
        ..., description="Social discussion trend"
    )
    discussion_recency: str = Field(..., description="'Recent' (<6 months), 'Moderate' (6-12 months), 'Dated' (12+ months)")
    community_growth_indicators: list[str] = Field(..., description="3-5 signals of community growth or decline (new subreddits, forum activity, etc.)")

    # Competitive Momentum
    new_entrants_trend: str = Field(..., description="'Increasing' (many new competitors), 'Stable', 'Consolidating' (exits/acquisitions)")
    competitive_activity_level: str = Field(..., description="'High' (active launches), 'Moderate', 'Low' (stagnant market)")

    # Seasonality & Patterns
    seasonal_pattern: Optional[str] = Field(default=None, description="Seasonal behavior: 'Strong Seasonal', 'Mild Seasonal', 'Year-Round', 'Unknown'")
    peak_periods: Optional[list[str]] = Field(default=None, description="Peak months/quarters if seasonal (e.g., ['Q4', 'November-December'])")

    # Longevity Assessment
    market_maturity: Literal["Emerging", "Growth", "Mature"] = Field(
        ..., description="Market maturity stage: 'Emerging' (<2 years), 'Growth' (2-5 years), 'Mature' (5+ years)"
    )
    longevity_verdict: Literal["Sustainable", "Risky", "Fad"] = Field(
        ..., description="Long-term viability assessment"
    )
    longevity_rationale: str = Field(..., description="2-3 sentences explaining longevity verdict with specific trend data")

    # Risk Factors
    trend_reversal_risks: list[str] = Field(..., description="3-5 factors that could reverse positive trends (tech shifts, regulation, etc.)")
    timing_recommendation: Literal["Enter Now", "Monitor & Wait", "Missed Window"] = Field(
        ..., description="Timing advice based on trends"
    )

    # Supporting Data Summary
    data_sources_analyzed: list[str] = Field(..., description="Data sources used: keyword trends, discussion activity, competitive intel")
    analysis_timeframe: str = Field(..., description="Timeframe analyzed (e.g., '12 months', '6 months', '24 months')")

    @model_validator(mode='after')
    def validate_consistency(self) -> 'TrendLongevityResult':
        """Validate that trend direction and momentum score are consistent."""
        if self.trend_direction == "Growing" and self.momentum_score < 0.6:
            raise ValueError(
                f"Growing trend requires momentum_score >= 0.6, got {self.momentum_score}"
            )
        if self.trend_direction == "Declining" and self.momentum_score > 0.4:
            raise ValueError(
                f"Declining trend requires momentum_score <= 0.4, got {self.momentum_score}"
            )
        return self


class ResearchState(BaseModel):
    """Complete state for the research flow."""

    model_config = ConfigDict(
        extra='ignore',
        json_schema_extra={
            "example": {
                "niche_context": {},
                "search_queries": [],
                "search_results": {},
                "social_content": {},
                "pain_point_analysis": {},
                "idea_generation": {},
                "competitive_analysis": {},
                "keyword_validation": {},
                "final_report": {},
                "started_at": "2025-01-15T10:00:00",
                "completed_at": None,
                "current_stage": 1,
                "errors": [],
            }
        }
    )

    # Stage 1: Niche Analysis
    niche_context: Optional[NicheContext] = None

    # User constraints
    allowed_project_types: Optional[list[str]] = Field(
        default=None,
        description="User-specified project type constraints: saas, directory, aggregator, comparison-tool, marketplace"
    )

    # Stage 2: Query Generation
    search_queries: list[SearchQuery] = Field(default_factory=list)

    # Stage 4-5: Content Collection
    social_content: Optional[SocialContentCollection] = None
    social_content_quality_tier: Optional[str] = Field(
        default=None,
        description="Quality tier from Stage 5 validation: EXCELLENT, GOOD, MINIMAL, or INSUFFICIENT"
    )
    social_content_metrics: Optional[dict[str, int]] = Field(
        default=None,
        description="Social content collection metrics (sources, interactions, engagement)"
    )

    # Stage 6: Pain Point Analysis
    pain_point_analysis: Optional[PainPointAnalysisResult] = None
    pain_point_quality_tier: Optional[str] = Field(
        default=None,
        description="Quality tier from Stage 6 validation: GOLD, SILVER, BRONZE, or INSUFFICIENT"
    )
    pain_point_confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1) for pain point analysis quality"
    )

    # Stage 6.5: Audience & Influence Mapping
    audience_mapping: Optional[AudienceMappingResult] = Field(
        default=None,
        description="Audience segmentation and influencer mapping from Stage 6.5"
    )

    # Stage 7: Idea Generation
    idea_generation: Optional[IdeaGenerationResult] = None

    # Stage 8: Competitive Analysis
    competitive_analysis: Optional[CompetitiveAnalysisResult] = None

    # Stage 7.5: Competitive Enhancements (preserves overall_competitive_insights)
    competitive_enhancements: Optional[CompetitiveEnhancements] = Field(
        default=None,
        description="Competitive enhancements with overall_competitive_insights from Stage 7.5"
    )

    # REMOVED: ideation_process - not reliably populated

    # Stage 7.4: Solution Selection
    solution_selection: Optional[SolutionSelection] = None

    # Stage 8.5: Keyword Validation Results (quick validation for top N solutions)
    keyword_validation_results: Optional[list[CrewKeywordValidationResult]] = Field(
        default=None,
        description="Keyword validation results for top N solutions from Stage 8.5"
    )

    # Stage 8.7: Solution Refinement (strategic recommendations based on keyword insights)
    solution_refinement: Optional[SolutionRefinement] = Field(
        default=None,
        description="Strategic refinement recommendations from Stage 8.7"
    )

    # Stage 8: Pricing Strategy Validation (for top N solutions)
    pricing_strategies: Optional[list[PricingStrategyResult]] = Field(
        default=None,
        description="Pricing strategies for top N solutions from Stage 8"
    )

    # Stage 8.55: Traffic Monetization Strategy (for directories/aggregators/comparison-tools)
    traffic_monetization_results: Optional[list[TrafficMonetizationResult]] = Field(
        default=None,
        description="Traffic monetization strategies for directory/aggregator/comparison-tool solutions from Stage 8.55"
    )

    # Stage 8.6: Market Sizing & Validation
    market_sizing: Optional[MarketSizingResult] = Field(
        default=None,
        description="Market sizing analysis with TAM/SAM/SOM estimates and viability assessment from Stage 8.6"
    )

    # Stage 9.2: Trend Longevity Analysis
    trend_longevity: Optional[TrendLongevityResult] = Field(
        default=None,
        description="Trend longevity and market momentum analysis from Stage 9.2"
    )

    # Stage 9: Seed Keywords
    seed_keywords: list[str] = Field(default_factory=list, description="Seed keywords for SEO research")

    # Stage 9 Sub-Phase Checkpoints (for resume capability)
    stage_9_5a_expanded_keywords: Optional[dict[str, Any]] = Field(
        default=None,
        description="Phase 9.5a output: expanded keywords and topic clusters from conceptual expansion"
    )
    stage_9_5b_validation_results: Optional[dict[str, Any]] = Field(
        default=None,
        description="Phase 9.5b output: DataForSEO validated keywords meeting volume threshold"
    )
    stage_9_5c_enriched_keywords: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Phase 9.5c output: enriched keywords with full search metrics"
    )

    # Stage 9.5: SEO Enrichment (refined scores using keyword data from Stage 9)
    seo_enrichment: Optional[SolutionSEORefinement] = Field(
        default=None,
        description="SEO score refinements from Stage 9.5 using actual keyword research data"
    )

    # Stage 9 (Legacy): Keyword Validation - DEPRECATED, kept for backward compatibility
    keyword_validation: Optional[KeywordValidationResult] = None

    # Stage 9.5: SEO Strategy (includes integrated keyword research)
    seo_strategy_report: Optional[SEOStrategyReport] = None

    # Stage 9.75: Data Source Research (for selected solution only)
    data_source_research: Optional[DataSourceResearchResult] = None

    # Stage 10: Final Report
    final_report: Optional[FinalReport] = None

    # Metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    current_stage: int = Field(default=1, description="Current pipeline stage (1-10)")
    errors: list[str] = Field(default_factory=list, description="Errors encountered")

    # Stage Completion Tracking (NEW - for diagnostic visibility)
    completed_stages: list[float] = Field(
        default_factory=list,
        description="List of completed stage numbers (e.g., [1, 5, 6, 6.5, 7, 8, 8.5])"
    )
    stage_completion_timestamps: dict[str, datetime] = Field(
        default_factory=dict,
        description="Timestamp when each stage completed (key: stage number as string)"
    )
    fallback_stages: list[float] = Field(
        default_factory=list,
        description="Stages that used fallback/incomplete data (e.g., [9.5] if trend used fallback)"
    )
    filtering_stats: Optional[dict[str, Any]] = Field(
        default=None,
        description="Filtering statistics from Stage 5: URLs searched, relevant found, filtering rate"
    )

    # Cost Tracking
    cost_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="API cost summary: total tokens, costs by stage, total cost (from CostTracker)"
    )
