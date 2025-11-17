"""
Pydantic models for research flow state management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .competitor import CompetitiveAnalysisResult
from .data_source import DataSourceResearchResult
from .keyword_data import KeywordValidationResult
from .pain_point import ContentCategorizationReport, PainPointAnalysisResult
from .seo_strategy import SEOStrategyReport
from .social_content import SocialContentCollection
from .solution_idea import IdeaGenerationResult, SolutionIdea, SolutionSEORefinement
from .solution_selection import SolutionSelection, SelectionCriteriaScore
from .solution_refinement import SolutionRefinement


class NicheContext(BaseModel):
    """Initial niche understanding (Stage 1)."""

    model_config = ConfigDict(extra='forbid')

    niche_input: str = Field(..., description="User's niche input")
    niche_description: str = Field(..., description="LLM-generated niche description")
    market_segments: List[str] = Field(..., description="Key market segments")
    industry_boundaries: str = Field(..., description="Industry boundaries definition")


class SearchQuery(BaseModel):
    """A single search query."""

    model_config = ConfigDict(extra='forbid')

    query: str = Field(..., description="Search query text")
    query_type: str = Field(
        ..., description="Type: problem/alternative/frustration/solution"
    )
    platform: str = Field(..., description="Target platform: reddit/twitter")


class SearchResultItem(BaseModel):
    """A single search result with metadata for relevance validation."""

    model_config = ConfigDict(extra='forbid')

    url: str = Field(..., description="URL of the search result")
    title: str = Field(..., description="Title of the page/post")
    snippet: str = Field(..., description="Text snippet from search result")


class ThreadRelevanceValidation(BaseModel):
    """Validation result for thread relevance to niche."""

    model_config = ConfigDict(extra='forbid')

    is_relevant: bool = Field(..., description="Whether thread is relevant to niche")
    confidence: float = Field(..., description="Confidence score 0-1")
    reason: str = Field(..., description="Brief explanation of relevance decision")


class SubredditBreakdown(BaseModel):
    """Breakdown of posts by subreddit."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., description="Subreddit name (without r/ prefix)")
    post_count: int = Field(..., description="Number of posts from this subreddit")


class ResearchMetadata(BaseModel):
    """Metadata about the research data collection process."""

    model_config = ConfigDict(extra='forbid')

    reddit_posts_analyzed: int = Field(..., description="Total Reddit posts collected")
    reddit_comments_analyzed: int = Field(..., description="Total Reddit comments analyzed")
    twitter_threads_analyzed: int = Field(..., description="Total Twitter threads collected")
    top_subreddits: List[SubredditBreakdown] = Field(
        ..., description="Breakdown of posts by subreddit (top 10)"
    )
    collection_date: datetime = Field(..., description="When data collection occurred")
    data_size_mb: float = Field(..., description="Total data size in megabytes")


class AlternativeSolution(BaseModel):
    """Condensed summary of a runner-up solution for comparison."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of the alternative solution")
    summary: str = Field(..., description="2-3 paragraph overview of the solution")
    market_fit_score: float = Field(..., ge=0.0, le=1.0, description="Market fit score")
    technical_feasibility_score: float = Field(..., ge=0.0, le=1.0, description="Technical feasibility")
    competitive_advantage_score: float = Field(..., ge=0.0, le=1.0, description="Competitive advantage score")
    seo_growth_potential_score: float = Field(..., ge=0.0, le=1.0, description="SEO scalability score")
    key_differentiator: str = Field(..., description="Primary unique value proposition")
    best_suited_for: str = Field(..., description="When this solution is the best choice")
    pivot_trigger: str = Field(..., description="Conditions that would justify pivoting to this solution")


class CompetitorMatrixEntry(BaseModel):
    """Single competitor entry showing which solutions it competes against."""

    model_config = ConfigDict(extra='forbid')

    competitor_name: str = Field(..., description="Name of the competitor")
    solutions_competed: List[str] = Field(..., description="List of solution names this competitor appears in")
    competitor_type: str = Field(..., description="Type: direct, partial, indirect")
    threat_level: str = Field(..., description="Overall threat level: high, medium, low")


class CompetitiveIntensityEntry(BaseModel):
    """Competitive intensity for a single solution."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of the solution")
    intensity: str = Field(..., description="Competitive intensity: Low, Medium, or High")


class CompetitiveLandscapeMatrix(BaseModel):
    """Cross-solution competitive analysis showing overlap and patterns."""

    model_config = ConfigDict(extra='forbid')

    all_solutions_analyzed: List[str] = Field(..., description="Names of all solutions analyzed")
    competitor_overlap: List[CompetitorMatrixEntry] = Field(
        ..., description="Competitors appearing in multiple solution landscapes"
    )
    competitive_intensity_by_solution: List[CompetitiveIntensityEntry] = Field(
        ..., description="Competitive intensity for each solution analyzed"
    )
    market_insight: str = Field(
        ..., description="Strategic insight about competitive landscape patterns"
    )


class TopRedditThread(BaseModel):
    """Summary of a high-engagement Reddit thread for evidence appendix."""

    model_config = ConfigDict(extra='forbid')

    post_id: str = Field(..., description="Reddit post ID")
    title: str = Field(..., description="Post title")
    subreddit: str = Field(..., description="Subreddit name")
    score: int = Field(..., description="Post score (upvotes)")
    num_comments: int = Field(..., description="Number of comments")
    url: str = Field(..., description="Link to Reddit post")
    key_insight: str = Field(..., description="1-sentence summary of why this thread is significant")


class QuoteSource(BaseModel):
    """Single quote with source attribution."""

    model_config = ConfigDict(extra='forbid')

    quote: str = Field(..., description="The quote text")
    post_id: str = Field(..., description="Post ID where quote was found")
    subreddit: str = Field(..., description="Subreddit name")
    score: str = Field(..., description="Post score/engagement")


class PainPointEvidence(BaseModel):
    """Evidence linking pain point quotes to original Reddit posts."""

    model_config = ConfigDict(extra='forbid')

    pain_point_title: str = Field(..., description="Pain point title")
    quotes_with_sources: List[QuoteSource] = Field(
        ..., description="List of quotes with source attribution"
    )


class EvidenceAppendix(BaseModel):
    """Appendix containing evidence traceability for research validation."""

    model_config = ConfigDict(extra='forbid')

    top_reddit_threads: List[TopRedditThread] = Field(
        ..., description="Top 10 most engaging Reddit discussions analyzed"
    )
    pain_point_quote_sources: List[PainPointEvidence] = Field(
        ..., description="Traceability from pain points to original posts"
    )


class DataInfrastructurePhase(BaseModel):
    """Single phase of data infrastructure implementation."""

    model_config = ConfigDict(extra='forbid')

    phase_number: int = Field(..., description="Phase number (1, 2, or 3)")
    phase_name: str = Field(..., description="Phase name (e.g., 'MVP', 'Growth', 'Scale')")
    timeline: str = Field(..., description="Timeline for this phase (e.g., 'Months 1-3')")
    data_sources: List[str] = Field(..., description="Data sources to integrate in this phase")
    estimated_monthly_cost: str = Field(..., description="Cost range for this phase (e.g., '$200-300')")
    key_risks: List[str] = Field(..., description="Risks and mitigation strategies")


class DataInfrastructureRoadmap(BaseModel):
    """Complete data infrastructure implementation roadmap."""

    model_config = ConfigDict(extra='forbid')

    phases: List[DataInfrastructurePhase] = Field(..., description="3-phase implementation plan")
    cost_scaling_insight: str = Field(
        ..., description="Summary of how costs scale with user growth and mitigation strategies"
    )


class DecisionCriterion(BaseModel):
    """Single go/no-go decision criterion."""

    model_config = ConfigDict(extra='forbid')

    criterion_type: str = Field(..., description="Type: 'go' or 'no-go'")
    condition: str = Field(..., description="Condition to evaluate (e.g., 'SEO keyword volume >10k/mo')")
    rationale: str = Field(..., description="Why this criterion matters")


class PivotTrigger(BaseModel):
    """Condition that would trigger a pivot to an alternative solution."""

    model_config = ConfigDict(extra='forbid')

    trigger_condition: str = Field(..., description="Condition triggering pivot")
    pivot_to_solution: str = Field(..., description="Alternative solution to pivot to")
    rationale: str = Field(..., description="Why this pivot makes sense")


class DecisionFramework(BaseModel):
    """Framework for making go/no-go and pivot decisions."""

    model_config = ConfigDict(extra='forbid')

    go_criteria: List[DecisionCriterion] = Field(..., description="Criteria for proceeding with selected solution")
    no_go_criteria: List[DecisionCriterion] = Field(..., description="Criteria for stopping the project")
    pivot_triggers: List[PivotTrigger] = Field(..., description="Conditions for pivoting to alternatives")


class FinalReport(BaseModel):
    """Final comprehensive research report (Stage 10)."""

    model_config = ConfigDict(extra='forbid')

    niche: str = Field(..., description="Niche analyzed")
    executive_summary: str = Field(..., description="High-level executive summary")

    # Solution Selection (Stage 8.5)
    selected_solution_name: str = Field(..., description="Name of the selected solution to focus on")
    selection_rationale: str = Field(..., description="Why this solution was selected over alternatives")
    runner_up_solutions: Optional[List[str]] = Field(default=None, description="Other viable solutions considered")
    selection_criteria_scores: Optional[List[SelectionCriteriaScore]] = Field(
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

    # Problem Section
    top_pain_points: List[str] = Field(..., description="Top identified pain points")
    pain_points_summary: str = Field(
        ..., description="Summary of pain point analysis with severity and WTP insights"
    )

    # Solution Section
    recommended_solutions: List[str] = Field(
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
        description="Detailed competitive analysis with competitor profiles, market gaps, and differentiation opportunities"
    )

    # Market Validation
    market_validation: str = Field(..., description="Overall market validation conclusion")

    # SEO Strategy (Enhanced from simple string to comprehensive report)
    seo_strategy: Optional[SEOStrategyReport] = Field(
        default=None, description="Comprehensive SEO strategy with tiered keywords, content plan, and roadmap"
    )

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

    # Keyword Validation & Refinement (Stage 8.8 and 8.85)
    keyword_validation_overview: Optional[str] = Field(
        default=None,
        description=(
            "Executive summary of keyword validation results across top 3 solution candidates from Stage 8.8. "
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
            "Comparative keyword analysis showing how top 3 solutions differ in SEO opportunity from Stage 8.8. "
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
            "Preview of content strategy recommendations based on keyword validation insights from Stage 8.8. "
            "Format: 2-3 paragraphs outlining: "
            "(1) Programmatic content opportunities identified (page templates, topic clusters), "
            "(2) Geographic or categorical expansion priorities from keyword data, "
            "(3) Quick win content recommendations for immediate SEO traction (Tier 1 keywords). "
            "Serves as bridge between keyword validation and detailed SEO strategy (Stage 9)."
        )
    )

    # Data Sourcing (for solutions requiring aggregation)
    data_source_research: Optional[DataSourceResearchResult] = Field(
        default=None,
        description="Structured data source research results with discovered APIs, providers, cost estimates, and implementation roadmap (Stage 9.75)"
    )
    data_sourcing_recommendations: str = Field(
        ..., description="Data sourcing strategy for aggregation projects"
    )

    # Next Steps
    next_steps: List[str] = Field(..., description="Recommended next steps")

    # Enhanced Report Sections (NEW - improve data preservation and traceability)
    research_metadata: Optional[ResearchMetadata] = Field(
        default=None,
        description="Metadata about data collection: Reddit/Twitter post counts, subreddit breakdown, collection date, data size"
    )
    alternative_solutions: Optional[List[AlternativeSolution]] = Field(
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
    decision_framework: Optional[DecisionFramework] = Field(
        default=None,
        description="Go/no-go criteria and pivot triggers for decision-making"
    )
    content_categorization: Optional[ContentCategorizationReport] = Field(
        default=None,
        description="Content categorization analysis: theme categories, user segments, and discussion quality from Stage 6 Task 1"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation timestamp"
    )
    pdf_path: Optional[str] = Field(default=None, description="Path to generated PDF report")


class ResearchState(BaseModel):
    """Complete state for the research flow."""

    model_config = ConfigDict(
        extra='forbid',
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

    # Stage 2: Query Generation
    search_queries: List[SearchQuery] = Field(default_factory=list)

    # Stage 4-5: Content Collection
    social_content: Optional[SocialContentCollection] = None

    # Stage 6: Pain Point Analysis
    pain_point_analysis: Optional[PainPointAnalysisResult] = None

    # Stage 7: Idea Generation
    idea_generation: Optional[IdeaGenerationResult] = None

    # Stage 8: Competitive Analysis
    competitive_analysis: Optional[CompetitiveAnalysisResult] = None

    # Stage 8.5: Solution Selection
    solution_selection: Optional[SolutionSelection] = None

    # Stage 8.8: Keyword Validation Results (quick validation for top 3 solutions)
    keyword_validation_results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Keyword validation results for top 3 solutions from Stage 8.8"
    )

    # Stage 8.85: Solution Refinement (strategic recommendations based on keyword insights)
    solution_refinement: Optional[SolutionRefinement] = Field(
        default=None,
        description="Strategic refinement recommendations from Stage 8.85"
    )

    # Stage 9: Seed Keywords
    seed_keywords: List[str] = Field(default_factory=list, description="Seed keywords for SEO research")

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
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
