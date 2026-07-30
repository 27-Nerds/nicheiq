"""
Pydantic models for research flow state management.
"""

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

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
from .seo_strategy import SEOStrategyReport, TopicCluster
from .social_content import SocialContentCollection
from .solution_idea import (
    CompetitiveEnhancements,
    IdeaGenerationResult,
    IdeaTags,
    SolutionIdea,
    SolutionSEORefinement,
)
from .solution_refinement import SolutionRefinement
from .solution_selection import SolutionSelection
from .technical_blueprint import SiteStructure, UserFlowsSection


class RuledOutFinding(TypedDict, total=False):
    """Durable envelope for an examined candidate that did not clear the bar."""

    finding_id: str
    finding_revision: int
    idea_id: str
    idea_revision: int
    identity_origin: str
    identity_operation_id: str
    idea_name: str
    pain_title: str
    segment: Optional[str]
    reason: str
    market_fit: Optional[float]
    market_fit_band: str
    prior_tier: str
    source: str
    evidence: str
    source_frame: Optional[str]
    dispatch_id: Optional[str]
    evaluation_id: Optional[str]
    evaluation_source_message_id: Optional[str]
    proposed_title: Optional[str]
    synthesis_evaluation: Optional[dict[str, Any]]
    generation_operation_id: Optional[str]
    generation_batch_ordinal: Optional[int]
    idea: dict[str, Any]


class NicheContext(BaseModel):
    """Initial niche understanding (Stage 1)."""

    model_config = ConfigDict(extra='ignore')

    niche_input: str = Field(..., description="User's niche input")
    # Audience-framing classification (Stage 1). Declared BEFORE the niche fields so that
    # under json_schema guided decoding the model classifies the input FIRST, then derives
    # the broad market — preventing audience inputs from silently narrowing market_segments.
    # Optional w/ defaults so legacy checkpoints deserialize unchanged.
    audience_scope: Optional[str] = Field(
        default=None,
        description="Intent class: 'niche' | 'segment_of_niche' | 'community' | 'too_broad'. None = niche/legacy.",
    )
    user_target_audience: Optional[str] = Field(
        default=None,
        description=(
            "The specific target audience the user is building for, when the input names one "
            "(verbatim/normalized); None for a plain niche. Detected by the Stage-1 classifier."
        ),
    )
    niche_description: str = Field(..., description="LLM-generated niche description")
    market_segments: list[str] = Field(..., description="Key market segments")
    industry_boundaries: str = Field(..., description="Industry boundaries definition")
    # Niche-anchor fields (added for niche-fidelity / drift prevention).
    # All optional with defaults so legacy checkpoints deserialize unchanged.
    anchor_entities: list[str] = Field(
        default_factory=list,
        description=(
            "8-20 specific named entities that uniquely identify this niche — "
            "proper-noun products, compounds, models, brands, or named "
            "techniques/protocols that an on-topic discussion in this niche will "
            "typically reference and an adjacent-but-different niche will not. "
            "Each entry must be a specific named item, NOT a broad category word."
        ),
    )
    disambiguation_exclusions: list[str] = Field(
        default_factory=list,
        description=(
            "Other audiences, senses, or adjacent fields that share this niche's "
            "vocabulary but are OUT of scope, so search/validation can exclude them. "
            "List the out-of-scope meanings, not the overlapping words themselves."
        ),
    )
    anchor_communities: list[str] = Field(
        default_factory=list,
        description=(
            "3-8 specific online communities / forums where this niche concentrates "
            "(e.g. a specialized subreddit). Prefer specific over general."
        ),
    )
    audience_jargon: list[str] = Field(
        default_factory=list,
        description="Insider terms/phrases the audience actually uses, for query/keyword vocabulary.",
    )
    community_search_terms: list[str] = Field(
        default_factory=list,
        description=(
            "3-6 SHORT (1-3 word) terms someone would type to FIND this niche's online communities "
            "(e.g. 'cottage food', 'music teachers'). Drive PRAW subreddit DISCOVERY — real subs found "
            "by keyword search instead of LLM-recalled names, which hallucinate for small communities "
            "(live 2026-07-02: Stage 1 confidently named the nonexistent r/CottageFood)."
        ),
    )
    # Computed at Stage 4 (NOT generated by the Stage-1 LLM) — kept last so it doesn't
    # appear in the classifier's generation flow. OUTPUT framing only; never scopes research.
    resolved_primary_audience: Optional[str] = Field(
        default=None,
        description=(
            "For audience_scope=='segment_of_niche': the discovered audience_segments.segment_name "
            "that best matches user_target_audience (the canonical label the frontend matches "
            "source_segment against). None for niche/community/too_broad."
        ),
    )

class SearchQuery(BaseModel):
    """A single search query."""

    model_config = ConfigDict(extra='ignore')

    query: str = Field(..., description="Search query text")
    query_type: str = Field(
        ..., description="Type: problem/alternative/frustration/solution"
    )
    platform: str = Field(..., description="Target platform: reddit/twitter/hackernews/youtube/both")

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
    examined_ruled_out: list[RuledOutFinding] = Field(
        default_factory=list,
        description="Structured findings for weak ideas demoted/rejected during the "
                     "idea-generation funnel (see ResearchState.idea_ruled_out)"
    )


class NicheDifficultyVerdict(BaseModel):
    """Candid 'Research Reality Check' verdict on how well software can solve this niche.

    The difficulty band + software_addressability are classified deterministically from
    already-computed pipeline signals (tool-addressability, novelty, calibration gap,
    audience fit, project-type concentration, cold-start data dependency). The prose
    (headline/narrative_summary) is written by a grounded LLM pass with a deterministic
    fallback. Bidirectional: STRONG (software can directly own the pains) -> HARD
    (software can only advise/lookup beside a physical problem).
    """

    model_config = ConfigDict(extra='ignore')

    difficulty_level: str = Field(
        ...,
        description="Software-fit difficulty band: low | medium | high | very_high"
    )
    software_addressability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0-1 estimate of how much of the niche's pain is software-addressable"
    )
    headline: str = Field(
        ...,
        description="One-line candid verdict"
    )
    narrative_summary: str = Field(
        ...,
        description="2-4 sentence candid prose verdict, grounded in the computed signals"
    )
    key_challenges: list[str] = Field(
        default_factory=list,
        description="Frictions only — what makes the niche hard, framed as what the product "
                    "must be. Strengths live in key_strengths; never mix the two, or "
                    "consumers render encouragements as risks."
    )
    key_strengths: list[str] = Field(
        default_factory=list,
        description="What makes the niche favourable. Populated only for a strong-fit niche"
    )
    low_confidence: bool = Field(
        default=False,
        description="True when the pain/idea sample is too small to be confident"
    )
    buyer_class: Optional[str] = Field(
        default=None,
        description="Who actually pays in this niche: budgeted-business | smb-operator | "
                    "prosumer | indie-hobbyist | consumer | mixed (None = not classified)"
    )
    buyer_class_note: Optional[str] = Field(
        default=None,
        description="User-facing one-liner on what the buyer class means for monetization"
    )


class RefinementHighlights(BaseModel):
    """Key strategic insights from Stage 10 solution refinement."""

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
    """Transparency into SEO score calculations from Stage 12."""

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
    keyword_evidence_floor: Optional[float] = Field(
        default=None,
        description="Keyword evidence floor value used as rescue mechanism"
    )
    floor_applied: Optional[bool] = Field(
        default=None,
        description="Whether keyword evidence floor overrode multiplicative score"
    )
    floor_reason: Optional[str] = Field(
        default=None,
        description="Why floor was applied (e.g. 'keyword_evidence_override')"
    )


class ResearchMetadata(BaseModel):
    """Metadata about the research data collection process."""

    model_config = ConfigDict(extra='ignore')

    reddit_posts_analyzed: int = Field(..., description="Total Reddit posts collected")
    reddit_comments_analyzed: int = Field(..., description="Total Reddit comments analyzed")
    twitter_threads_analyzed: int = Field(..., description="Total Twitter threads collected")
    generic_posts_analyzed: int = Field(default=0, description="Total generic source posts collected (HN, YouTube, etc.)")
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

    funnel_counts: dict = Field(
        default_factory=dict,
        description="Idea-generation funnel tallies (pains_identified, cells_run, winners, "
                    "demoted, backfill_run/accepted, candidates_shown, ...)"
    )

class AlternativeSolution(BaseModel):
    """Enhanced alternative solution with competitive analysis details."""

    model_config = ConfigDict(extra='ignore')

    # Core identification
    solution_name: str = Field(..., description="Name of the alternative solution")
    idea_id: Optional[str] = Field(
        default=None,
        description="Durable candidate identity copied from the Stage-5 idea",
    )
    idea_revision: int = Field(
        default=1,
        ge=1,
        description="Immutable revision of the candidate represented by this alternative",
    )
    identity_origin: Optional[str] = Field(
        default=None,
        description="Code-owned namespace used to mint this candidate identity",
    )
    identity_operation_id: Optional[str] = Field(
        default=None,
        description="Operation key used to mint this candidate identity",
    )
    headline: Optional[str] = Field(default=None, description="Short searchable title for the solution (5-12 words)")
    short_description: Optional[str] = Field(default=None, description="Punchy 1-2 sentence card summary (<180 chars)")
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

    # Portfolio-funnel provenance tier (mirrors BaseSolutionIdea.idea_tier; drives the report badge)
    idea_tier: str = Field(default="single", description="single | salvaged | bundle")
    # Mirrors BaseSolutionIdea.candidate_status / merged_from — alternatives are drawn from
    # visible_ideas() (demoted/absorbed already excluded), so this is realistically always
    # 'active' or 'restored' here; carried through for completeness / lineage transparency.
    candidate_status: str = Field(
        default="active",
        description="Portfolio-funnel visibility status: active | demoted | restored | absorbed "
                     "(mirrors BaseSolutionIdea.candidate_status)")
    merged_from: Optional[list[str]] = Field(
        default=None,
        description="Solution names this idea was synthesized from when idea_tier='merged'; "
                     "None on every other tier (mirrors BaseSolutionIdea.merged_from)")
    # Angle-aware evaluation (mirrors BaseSolutionIdea; set when angle eval is on, None otherwise)
    winning_angle: Optional[str] = Field(default=None, description="distribution_seo | novel_differentiation | vertical_workflow")
    angle_rationale: Optional[str] = Field(default=None, description="User-facing comment: the angle + where differentiation lives")
    novelty_rationale: Optional[str] = Field(
        default=None,
        description="Stable field name for the user-facing explanation of distinctiveness for this project type",
    )
    differentiation_locus: Optional[str] = Field(default=None, description="WHERE this idea's differentiation lives (or honest 'thin me-too')")

    # Data feasibility (from the ideation feasibility critic; annotate-only, surfaced in UI)
    data_feasibility_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Ease of obtaining required data (0-1)")
    data_access_model: Optional[str] = Field(default=None, description="public | freemium | paywalled | unofficial | restricted | blocked | unverified")
    data_acquisition_notes: Optional[str] = Field(default=None, description="Data source/route + access model + cost/ToS risk")
    build_feasibility_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Independent critic's build-feasibility estimate (0-1)")

    # NEW: Competitive landscape for this solution
    top_competitors: Optional[list[str]] = Field(default=None, description="Top 3 competitors for this solution")
    market_gaps: Optional[list[str]] = Field(default=None, description="Key market gaps this solution addresses")
    competitive_intensity: Optional[str] = Field(default=None, description="Competitive intensity: LOW, MEDIUM, HIGH")

    # NEW: Economic indicators
    estimated_development_time: Optional[str] = Field(default=None, description="Estimated development time")
    estimated_cac_organic: Optional[str] = Field(default=None, description="Estimated organic customer acquisition cost (e.g. '$15-30')")
    pricing_model: Optional[str] = Field(default=None, description="Recommended pricing model")

    # Phase 8 of detail-page IA rework — same field as BaseSolutionIdea so
    # alternatives can be cross-linked to specific pains on the catalog
    # /pain-point/[slug] page. default_factory=list preserves backwards
    # compatibility with old report.json files lacking the field.
    pain_points_addressed: list[str] = Field(default_factory=list, description="Pain point titles this alternative directly addresses")

    # Honest brief (2026-07-02): the adversarial half of the idea card. The bull case is
    # the generator's own fields (value_proposition, key_differentiator); these surface
    # the evidence and the critic's voice that were persisted but never rendered.
    demand_quotes: Optional[list[str]] = Field(
        default=None,
        description="Verbatim community quotes evidencing the addressed pains (max 3)")
    critic_concern: Optional[str] = Field(
        default=None,
        description="The calibration critic's market_fit reason, verbatim — the bear case")
    incumbent_parity: Optional[str] = Field(
        default=None,
        description="Web-verified mechanism-parity finding for top ideas (mirrors "
        "BaseSolutionIdea.incumbent_parity); None when the parity probe didn't run")
    adjacent_market_parity: Optional[str] = Field(
        default=None,
        description="Audience-independent incumbent in the adjacent commercial market the "
        "mechanism monetizes in (mirrors BaseSolutionIdea.adjacent_market_parity)")
    red_team_verdict: Optional[str] = Field(
        default=None,
        description="'survives' | 'weakened' | 'killed' from the adversarial red-team pass "
        "(mirrors BaseSolutionIdea.red_team_verdict); None = idea not red-teamed")
    red_team_caveats: Optional[list[str]] = Field(
        default=None,
        description="Up to 3 evidence-cited red-team caveats (mirrors "
        "BaseSolutionIdea.red_team_caveats); None = idea not red-teamed")
    source_segment_payability: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="0-1 payability of the source segment (permanent buyer-wallet signal)")
    source_segment_payability_class: Optional[str] = Field(
        default=None,
        description="corporate-budget | smb-budget | prosumer-wallet | personal-wallet | mixed")
    # Multi-Frame Idea Generation Portfolio: which generation FRAME minted this idea's cell
    # (mirrors BaseSolutionIdea.source_frame; CODE-FILLED, never LLM-set).
    source_frame: Optional[str] = Field(
        default=None,
        description="pain | gap | data_asset | workflow (mirrors "
        "BaseSolutionIdea.source_frame); None when not carried through")
    evaluation_id: Optional[str] = Field(
        default=None,
        description="Durable Concept Forge evaluation identity when this was an exact synthesis",
    )
    evaluation_source_message_id: Optional[str] = Field(
        default=None,
        description="Concept Forge proposal message that originated this evaluation",
    )
    proposed_title: Optional[str] = Field(
        default=None,
        description="Immutable title selected for the exact Concept Forge evaluation",
    )
    synthesis_evaluation: Optional[dict] = Field(
        default=None,
        description="Complete structured Concept Forge evaluation payload",
    )
    generation_operation_id: Optional[str] = Field(
        default=None,
        description="Durable operation identity for an append-only additional batch",
    )
    generation_batch_ordinal: Optional[int] = Field(
        default=None,
        ge=1,
        description="One-based append-only additional-batch ordinal",
    )

    # Closed-vocabulary filter facets (chips + future filtering). See docs/IDEA_TAGS.md.
    tags: Optional[IdeaTags] = Field(default=None, description="Closed-vocabulary filter facets")


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
    # Catalog rebuild (Phase 5.4): market position relative to the niche.
    # Distinct from `competitor_type` (which describes feature overlap with
    # OUR proposed solution) — `position` describes the competitor's standing
    # in the market itself. Optional for back-compat with existing reports.
    #   leader     = dominant brand recognition or market share
    #   challenger = mid-market with focused traction, scaling
    #   niche      = vertical-specific or limited footprint
    position: Optional[str] = Field(
        default=None,
        description="Market position: leader | challenger | niche",
    )

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
    """Summary of a high-engagement discussion thread for evidence appendix."""

    model_config = ConfigDict(extra='ignore')

    post_id: str = Field(..., description="Post ID")
    title: str = Field(..., description="Post title")
    subreddit: str = Field(..., description="Source label (r/subreddit, Hacker News, channel name)")
    score: int = Field(..., description="Post score (upvotes/points)")
    num_comments: int = Field(..., description="Number of comments/responses")
    url: str = Field(..., description="Link to post")
    created_utc: Optional[datetime] = Field(default=None, description="Post creation timestamp")
    key_insight: str = Field(..., description="1-sentence summary of why this thread is significant")
    platform: str = Field(default="reddit", description="Source platform (reddit, hackernews, youtube)")

class QuoteSource(BaseModel):
    """Single quote with source attribution."""

    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    quote: str = Field(..., description="The quote text")
    post_id: str = Field(..., description="Post ID where quote was found")
    source_label: str = Field(..., alias="subreddit", description="Source label (r/subreddit, Hacker News, channel name)")
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

    # Transparency: True when the run was seeded from a catalog pain/idea (no fresh
    # social-content scrape), so the report's community evidence is thinner. Drives
    # a "seeded from catalog" badge in the UI.
    seeded_from_catalog: bool = Field(
        default=False,
        description="True if this report was generated from a catalog-seeded run (pain_research / deep_idea)."
    )

    # Guided-mode (chatMode) honesty block (Phase C): True once any gate patch (G1 niche
    # context or G2 audience/pain scope, flows/gate_patches.py) was applied to this run.
    # Drives a "User adjustments" note in the report/preview UI alongside user_adjustments.
    user_adjusted: bool = Field(
        default=False,
        description="True once any guided-mode gate patch has been applied to this run."
    )
    user_adjustments: list[str] = Field(
        default_factory=list,
        description="Compact, human-readable notes describing which gate(s) were user-adjusted "
        "and what changed. Empty when user_adjusted is False."
    )

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
    niche_difficulty_verdict: Optional[NicheDifficultyVerdict] = Field(
        default=None,
        description="Research Reality Check: candid verdict on how hard this niche is to solve with software"
    )
    market_reality: Optional[dict] = Field(
        default=None,
        description=(
            "Phase-1 web-verified market facts, shown once and handed to Phase-2 deep-research "
            "once (see utils/market_brief.py): {incumbents: [{name, pricing, focus, gap, source}], "
            "wallet: {wallet_class, evidence, free_density}}. None when neither probe found data. "
            "Mirrors the preview report's top-level market_reality field."
        ),
    )
    idea_portfolio_summary: Optional[str] = Field(
        default=None,
        description=(
            "LLM-narrated honest assessment of the visible idea pool, grounded in verified "
            "Phase-1 signals. Computed once in Stage 5 (see utils/idea_portfolio_summary.py) "
            "and carried on state; None when the pool was empty or the LLM pass failed its "
            "name-coverage guardrail. Mirrors the preview report's top-level field."
        ),
    )
    refinement_highlights: Optional[RefinementHighlights] = Field(
        default=None,
        description="Key strategic insights from Stage 10 solution refinement"
    )
    stage_timing_summary: Optional[StageTimingSummary] = Field(
        default=None,
        description="Pipeline execution timing for performance visibility"
    )
    seo_calculation_transparency: Optional[SEOCalculationTransparency] = Field(
        default=None,
        description="SEO score calculation methodology from Stage 12"
    )

    # Solution Selection (Stage 5)
    selected_solution_name: str = Field(..., description="Name of the selected solution to focus on")
    selection_rationale: str = Field(..., description="Why this solution was selected over alternatives")
    original_selection_reasoning: Optional[str] = Field(
        default=None,
        description=(
            "The strategic selector's original rationale, preserved verbatim when "
            "keyword validation pivoted the winner (selection_rationale then carries "
            "an appended evidence update). None when no pivot occurred."
        ),
    )
    # runner_up_solutions removed - use alternative_solutions instead
    # selection_criteria_scores removed - ScoreAccessor is single source of truth
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

    # Keyword Validation & Refinement (keyword validation and Stage 10)
    keyword_validation_overview: Optional[str] = Field(
        default=None,
        description=(
            "Executive summary of keyword validation results across top N solution candidates from keyword validation. "
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
            "Comparative keyword analysis showing how top N solutions differ in SEO opportunity from keyword validation. "
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
            "Preview of content strategy recommendations based on keyword validation insights from keyword validation. "
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

    # Catalog rebuild (Phase 5.4): keyword clusters for the public catalog UI.
    # Sourced by report_generator._assemble_base_report directly from
    # state.seo_strategy_report.topic_clusters — that is the canonical
    # population path in the current pipeline (KeywordCluster in keyword_data.py
    # is defined but never instantiated; KeywordResearchReport is unused).
    # Optional because legacy reports + reports where SEO crew failed don't
    # have it; the projection logs a warning and the catalog UI hides the
    # section gracefully.
    #
    # Per-keyword volume/difficulty enrichment deferred — TopicCluster currently
    # carries supporting_keywords as `list[str]`. Frontend renders cluster
    # name + primary keyword + total volume + content recommendation.
    keyword_clusters: Optional[list[TopicCluster]] = Field(
        default=None,
        description="Topic clusters for the selected solution (Phase 5.4 catalog UI)"
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

    # Stage 9: Market Sizing (full object)
    # Note: Using string forward reference since MarketSizingResult is defined later in this file
    market_sizing: Optional["MarketSizingResult"] = Field(
        default=None,
        description="TAM/SAM/SOM analysis, viability verdict, growth drivers, risks from Stage 9"
    )

    # Stage 11: Trend Longevity (full object)
    # Note: Using string forward reference since TrendLongevityResult is defined later in this file
    trend_longevity: Optional["TrendLongevityResult"] = Field(
        default=None,
        description="Market momentum, trend direction, seasonality, timing recommendation from Stage 11"
    )

    # Stage 9: Full SEO Strategy (full object, not just analytics)
    seo_strategy_report: Optional[SEOStrategyReport] = Field(
        default=None,
        description="Complete SEO strategy with implementation roadmap, content strategy from Stage 6"
    )

    # Stage 13: Full Data Source Research (full object, not just string summary)
    data_source_research_full: Optional[DataSourceResearchResult] = Field(
        default=None,
        description="Full data source analysis with provider details, costs, integration plan from Stage 13"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation timestamp"
    )


class MarketSegmentPrice(BaseModel):
    """Pricing for a specific market segment."""

    segment: str = Field(..., description="Market segment name")
    price: Optional[str] = Field(default=None, description="Price for this segment")


class TrafficSourceShare(BaseModel):
    """Traffic source with its share percentage."""

    source: str = Field(..., description="Traffic source name, e.g. 'organic_search', 'direct'")
    percentage: str = Field(..., description="Share percentage, e.g. '70%'")


class RevenueMilestone(BaseModel):
    """Revenue milestone at a specific traffic level."""

    traffic: str = Field(..., description="Traffic level, e.g. '5,000 sessions/mo'")
    ad_revenue: str = Field(..., description="Ad revenue at this level")
    unlock: str = Field(..., description="What becomes available at this traffic level")
    total_potential: str = Field(..., description="Total revenue potential including all sources")


# Stage 7: Pricing Strategy Validation
class PricingStrategyResult(BaseModel):
    """Pricing strategy validation result from Stage 7."""

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
    market_segment_pricing: Optional[list[MarketSegmentPrice]] = Field(
        default=None, description="Different pricing for different market segments if applicable"
    )

    def format_summary(self) -> str:
        """Format a concise pricing summary for display and LLM prompts."""
        parts = [self.pricing_model]
        if self.pricing_model == "Freemium-Lite":
            # 2-tier model: Free + Pro. Use pro price, fall back to starter if pro is missing
            display_price = self.recommended_pro_price or self.recommended_starter_price
            if display_price:
                parts.append(f"{display_price} pro")
        else:
            if self.recommended_starter_price:
                parts.append(f"{self.recommended_starter_price} starter")
            if self.recommended_pro_price:
                parts.append(f"{self.recommended_pro_price} pro")
        if self.recommended_enterprise_price:
            parts.append(f"{self.recommended_enterprise_price} enterprise")
        # Ad/affiliate models with no subscription prices
        if not self.recommended_starter_price and not self.recommended_pro_price:
            if self.estimated_monthly_ad_revenue:
                parts.append(f"est. {self.estimated_monthly_ad_revenue}/mo ad revenue")
            if self.estimated_monthly_affiliate_revenue:
                parts.append(f"est. {self.estimated_monthly_affiliate_revenue}/mo affiliate revenue")
        if len(parts) > 1:
            return f"{parts[0]}: {', '.join(parts[1:])}"
        return parts[0]


# Stage 8: Traffic Monetization Strategy (for directories/aggregators/comparison-tools)
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
    traffic_source_breakdown: list[TrafficSourceShare] = Field(
        ..., description="Traffic source distribution as a list of objects, e.g. [{source: 'organic_search', percentage: '70%'}]"
    )

    # Ad Revenue Estimates
    estimated_cpm_rate: str = Field(
        ..., description="Estimated CPM rate for this niche (e.g., '$3-8 CPM (lifestyle niche)')"
    )
    estimated_monthly_ad_revenue: str = Field(
        ..., description="Estimated monthly ad revenue range (e.g., '$150 - $800')"
    )
    recommended_ad_networks: list[str] = Field(
        default_factory=list,
        description="Recommended ad networks based on traffic tier (e.g., ['Google AdSense', 'Mediavine', 'Ezoic'])"
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
        default_factory=list,
        description="Recommended affiliate programs for this niche"
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

    # Methodology (populated post-LLM by report generator, not by CrewAI agent)
    traffic_methodology: Optional[str] = Field(
        default=None, description="Methodology explanation for traffic projections (set by report generator)"
    )
    traffic_data_sources: Optional[list[str]] = Field(
        default=None, description="Data sources used for traffic estimation (set by report generator)"
    )

    # Growth trajectory (populated by report generator, not CrewAI)
    year3_monthly_pageviews: Optional[str] = Field(
        default=None, description="Year 3 monthly pageviews (set by report generator)"
    )
    year3_monthly_revenue: Optional[str] = Field(
        default=None, description="Year 3 monthly revenue range (set by report generator)"
    )
    full_potential_monthly_pageviews: Optional[str] = Field(
        default=None, description="Full potential monthly pageviews - all tiers (set by report generator)"
    )
    full_potential_monthly_revenue: Optional[str] = Field(
        default=None, description="Full potential monthly revenue range (set by report generator)"
    )
    revenue_growth_note: Optional[str] = Field(
        default=None, description="Contextual note explaining revenue growth path (set by report generator)"
    )
    revenue_milestones: Optional[list[RevenueMilestone]] = Field(
        default=None, description="Revenue milestones at traffic levels (set by report generator)"
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
    # Payability (permanent since the 2026-07-06 gate pass): computed post-Stage-4 by utils/segment_payability
    # from budget authority + existing-spend evidence; declared so it persists through model_dump.
    payability_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="0-1 ability/habit of this segment to PAY for software (None = not scored)")
    payability_class: Optional[str] = Field(
        default=None,
        description="corporate-budget | smb-budget | prosumer-wallet | personal-wallet")
    payability_rationale: Optional[str] = Field(
        default=None, description="One-line evidence-grounded reason for the payability call")



class InfluencerTopPost(BaseModel):
    """A top post or comment by an influencer."""

    title: str = Field(..., description="Post title or truncated comment body")
    subreddit: str = Field(..., description="Subreddit where posted")
    score: int = Field(..., description="Post/comment score")
    url: str = Field(..., description="URL to original post")

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
    top_subreddits: list[str] = Field(default_factory=list, description="Top 3 subreddits by activity")
    top_posts: list[InfluencerTopPost] = Field(default_factory=list, description="Top 3 posts/comments by score")


class AudienceMappingResult(BaseModel):
    """Complete audience mapping analysis result from Stage 6.5."""

    model_config = ConfigDict(extra='ignore')

    # Audience Segments
    # NOTE: hard min_length floors were removed (2026-06) — quality floors now live in the
    # guardrail (validate_audience_mapping). Keeping min_length here caused a double-validation
    # trap: a guardrail-passing LLM payload could still crash on re-assembly. Max caps stay.
    audience_segments: list[AudienceSegment] = Field(
        default_factory=list, max_length=5, description="3-5 distinct audience segments identified"
    )
    primary_target_segment: str = Field(..., description="Recommended primary target segment name")
    segment_prioritization_rationale: str = Field(..., description="Why this segment should be targeted first (2-3 sentences)")

    # Influencers & Communities (Python-computed in audience_mapping_crew, not LLM-produced)
    key_influencers: list[InfluencerProfile] = Field(
        default_factory=list, max_length=10, description="Top 5-10 influencers/communities in the niche"
    )
    community_hubs: list[str] = Field(..., description="Key online communities/forums (subreddits, Discord servers, forums)")

    # Content & Messaging Insights
    common_vocabulary: list[str] = Field(
        default_factory=list, max_length=15, description="10-15 terms/phrases frequently used by audience"
    )
    content_preferences: str = Field(..., description="Preferred content types and formats (e.g., tutorials, comparisons, case studies)")
    messaging_frameworks: list[str] = Field(..., description="3-5 messaging angles that resonate (e.g., 'save time', 'increase revenue')")

    # Competitive Intelligence
    tools_currently_used: list[str] = Field(..., description="Current tools/solutions audience mentions using")
    frustrations_with_existing: list[str] = Field(..., description="Top frustrations with current solutions")

    # Acquisition Strategy Implications
    recommended_channels: list[str] = Field(..., description="Top 3-5 marketing channels for this audience")
    early_adopter_tactics: Optional[str] = Field(default=None, description="Tactics to acquire first 100 users")

    @field_validator("common_vocabulary", "key_influencers", "audience_segments", mode="before")
    @classmethod
    def _truncate_overproduced_lists(cls, v, info):
        """Truncate LLM over-production to the field's max BEFORE max_length validation.

        The model otherwise hard-fails (too_long → guardrail re-prompt + wasted call) when
        the LLM returns, e.g., 20 vocabulary terms against the 15 cap. Keep-first-N is safe
        for these ranked lists; genuine UNDER-production still fails min_length (rare; retry).
        """
        caps = {"common_vocabulary": 15, "key_influencers": 10, "audience_segments": 5}
        cap = caps.get(info.field_name)
        if cap and isinstance(v, list) and len(v) > cap:
            return v[:cap]
        return v


class AudienceSegmentLLM(BaseModel):
    """Tolerant, LLM-facing mirror of AudienceSegment.

    Small/fast models emit nulls and wrong shapes; this model accepts them so one bad field
    can't fail the whole parse. Converted to the strict ``AudienceSegment`` during assembly
    in ``audience_mapping_crew`` (None scalars coerced, off-enum strings normalized).
    """

    model_config = ConfigDict(extra='ignore')

    segment_name: str = Field(..., description="Name of audience segment")
    size_estimate: Optional[str] = Field(default="Medium", description="'Large', 'Medium', 'Small'")
    pain_point_alignment: list[str] = Field(default_factory=list, description="Top pain points")
    motivation_drivers: list[str] = Field(default_factory=list, description="Key motivations (3-5)")
    expertise_level: Optional[str] = Field(default="Intermediate", description="'Beginner', 'Intermediate', 'Advanced'")
    budget_sensitivity: Optional[str] = Field(default="Medium", description="'High', 'Medium', 'Low'")
    discovery_channels: list[str] = Field(default_factory=list, description="Where they discover solutions")
    influencers_followed: Optional[list[str]] = Field(default=None, description="Influencers/communities followed")

    @field_validator(
        "pain_point_alignment", "motivation_drivers", "discovery_channels", "influencers_followed",
        mode="before",
    )
    @classmethod
    def _coerce_none_list(cls, v):
        """Small models emit scalar null for 'found none' — coerce to a safe list."""
        if v is None:
            return []
        if not isinstance(v, list):
            return [v]
        return v


class InfluencerFocus(BaseModel):
    """LLM-provided content_focus for a pre-computed influencer, keyed by its 1-based index.

    Object form (not a positional list) so misalignment is detectable: a missing/out-of-range
    index falls back to the Python-computed focus instead of silently shifting every entry.
    """

    index: int = Field(..., description="1-based number of the influencer in the provided list")
    focus: str = Field(default="", description="One-line content focus description")

    @field_validator("index", mode="before")
    @classmethod
    def _coerce_index(cls, v):
        """Accept '1', '#1', '1.' etc. from small models; non-numeric → 0 (dropped at match)."""
        if isinstance(v, bool):
            return 0
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            digits = "".join(ch for ch in v if ch.isdigit())
            return int(digits) if digits else 0
        return v


class AudienceMappingLLMResult(BaseModel):
    """Qualitative-only, LLM-facing output for Stage 6.5.

    Excludes ``key_influencers`` entirely (computed in Python). Every field tolerates the
    nulls/wrong-shapes small models emit so parse essentially never fails; quality is enforced
    by the guardrail, and the result is assembled into the strict ``AudienceMappingResult`` in
    ``audience_mapping_crew.analyze()``.
    """

    model_config = ConfigDict(extra='ignore')

    audience_segments: list[AudienceSegmentLLM] = Field(default_factory=list)
    primary_target_segment: Optional[str] = Field(default=None)
    segment_prioritization_rationale: Optional[str] = Field(default=None)

    community_hubs: list[str] = Field(default_factory=list)

    common_vocabulary: list[str] = Field(default_factory=list)
    content_preferences: Optional[str] = Field(default=None)
    messaging_frameworks: list[str] = Field(default_factory=list)

    tools_currently_used: list[str] = Field(default_factory=list)
    frustrations_with_existing: list[str] = Field(default_factory=list)

    recommended_channels: list[str] = Field(default_factory=list)
    early_adopter_tactics: Optional[str] = Field(default=None)

    influencer_focus: list[InfluencerFocus] = Field(default_factory=list)

    @field_validator(
        "community_hubs", "common_vocabulary", "messaging_frameworks",
        "tools_currently_used", "frustrations_with_existing", "recommended_channels",
        mode="before",
    )
    @classmethod
    def _coerce_str_lists(cls, v, info):
        """None→[]; scalar→[scalar]; truncate to the field's max cap."""
        if v is None:
            return []
        if not isinstance(v, list):
            return [v]
        caps = {"common_vocabulary": 15}
        cap = caps.get(info.field_name)
        if cap and len(v) > cap:
            return v[:cap]
        return v

    @field_validator("audience_segments", mode="before")
    @classmethod
    def _coerce_segments(cls, v):
        """Tolerate null/dict/string/None-element shapes; drop junk; cap at 5."""
        if v is None:
            return []
        if isinstance(v, dict):
            v = [v]
        if not isinstance(v, list):
            return []
        cleaned = []
        for item in v:
            if item is None:
                continue
            if isinstance(item, str):
                cleaned.append({"segment_name": item})
            else:
                cleaned.append(item)  # dict or model instance — let pydantic validate
        return cleaned[:5]

    @field_validator("influencer_focus", mode="before")
    @classmethod
    def _coerce_focus(cls, v):
        """None→[]; drop None elements; non-list → []."""
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        return [item for item in v if item is not None]


# Stage 9: Market Sizing & Validation
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
    """Complete market sizing and validation analysis from Stage 9."""

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


class TrendNarrativeOutput(BaseModel):
    """LLM-generated narrative/judgment fields for trend analysis (crew-internal)."""

    model_config = ConfigDict(extra='ignore')

    market_maturity: Literal["Emerging", "Growth", "Mature"] = Field(
        ..., description="Market maturity stage based on competitor age, tech adoption, discussion depth"
    )
    longevity_verdict: Literal["Sustainable", "Risky", "Fad"] = Field(
        ..., description="Long-term viability assessment"
    )
    longevity_rationale: str = Field(
        ..., description="2-3 sentences explaining longevity verdict with specific trend data"
    )

    # new_entrants_trend / competitive_activity_level / volume_growth_rate are
    # no longer LLM outputs — they're computed deterministically (competitor
    # count buckets, aggregate monthly-series growth) and merged in
    # TrendLongevityCrew.analyze().

    trend_duration: Optional[str] = Field(
        default=None, description="How long trend has been active (e.g., '2+ years growth', '6 months spike')"
    )
    peak_periods: Optional[list[str]] = Field(
        default=None, description="Peak months/quarters if seasonal (e.g., ['Q4', 'November-December'])"
    )

    community_growth_indicators: list[str] = Field(
        ..., description="3-5 signals of community growth or decline with stage citations"
    )
    trend_reversal_risks: list[str] = Field(
        ..., description="3-5 factors that could reverse positive trends with severity and evidence"
    )


class TrendLongevityResult(BaseModel):
    """Trend longevity and market momentum analysis from Stage 11."""

    model_config = ConfigDict(extra='ignore')

    # True when this result was synthesized by _create_minimal_trend_fallback
    # (no social corpus / SEO data). The Literal fields below can't express
    # "unknown", so fallback instances carry conservative placeholders — this
    # flag lets consumers (verdict computation) avoid treating placeholders
    # as real analysis. Defaults False so legacy checkpoints stay valid.
    is_fallback: bool = Field(
        default=False,
        description="True if this is a minimal fallback result, not real trend analysis",
    )

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
    new_entrants_trend: Optional[Literal["Increasing", "Stable", "Consolidating"]] = Field(
        default=None,
        description=(
            "'Increasing' (many new competitors), 'Stable', 'Consolidating' (exits/acquisitions). "
            "None when no competitor-age source data exists — never LLM-guessed "
            "(the frontend hides the stat pill on None)."
        ),
    )
    competitive_activity_level: Literal["High", "Moderate", "Low"] = Field(
        ...,
        description=(
            "Computed from competitor count: >15 = High, 5-15 = Moderate, <5 = Low "
            "(deterministic, not LLM-estimated)"
        ),
    )

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


class PainScope(BaseModel):
    """G2 guided-mode gate patch: user-scoped view over Stage 3's pain points, consumed
    ONLY at the ideation allocation choke point (UnifiedSolutionCrew._build_partition_cells).
    Non-destructive — pain_point_analysis.pain_points itself is never mutated; excluded pains
    are filtered at the top of cell-building (so severity/commercial/audience floors cannot
    resurrect them) and pinned pains are injected via the same floor-injection pattern."""

    model_config = ConfigDict(extra='ignore')

    excluded_titles: list[str] = Field(
        default_factory=list, description="Pain titles to exclude from ideation cell-building")
    pinned_titles: list[str] = Field(
        default_factory=list, description="Pain titles to guarantee a generator cell, like a floor")


class AudienceScope(BaseModel):
    """G2 guided-mode gate patch: user-scoped view over Stage 4's audience_mapping, consumed
    ONLY at the ideation allocation choke point. Non-destructive — audience_mapping.audience_segments
    is never mutated (pains' affected/evidence_segments reference those entries); exclusions/emphasis
    only filter/reorder the segment list `_build_partition_cells` reads."""

    model_config = ConfigDict(extra='ignore')

    excluded_segments: list[str] = Field(
        default_factory=list, description="Segment names to exclude from ideation cell-building")
    segment_emphasis: dict[str, str] = Field(
        default_factory=dict, description="Segment name -> 'high' | 'low' emphasis for reordering")
    primary_target_segment: Optional[str] = Field(
        default=None, description="User-overridden primary segment name (must match an existing segment)")


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
    idea_focus: str = Field(
        default="auto",
        description=(
            "User GTM-focus steer for idea generation + ranking emphasis: 'auto' (the angle agent "
            "decides, unbiased), 'novelty' (tilt toward novel_differentiation), or 'distribution' (tilt "
            "toward distribution_seo). 'auto' is neutral — the angle agent decides per idea."
        ),
    )

    # Guided-mode (chatMode) gate patches — set by apply_gate_patch (flows/gate_patches.py) from
    # a user-approved G2 patch, consumed only at UnifiedSolutionCrew._build_partition_cells (the
    # allocation choke point). None/default means byte-identical behavior to a non-guided run.
    user_pain_scope: Optional[PainScope] = Field(
        default=None, description="G2 patch: pain inclusion/exclusion scope for ideation")
    user_audience_scope: Optional[AudienceScope] = Field(
        default=None, description="G2 patch: audience segment scope for ideation")
    # Stamped True by apply_gate_patch on ANY accepted G1/G2 patch — surfaced in the report's
    # honesty block (Phase C) so a modified run is never silently indistinguishable from a
    # default one.
    user_adjusted: bool = Field(
        default=False, description="True once any guided-mode gate patch has been applied")

    # Niche-fidelity telemetry (non-scoring; surfaced as report caveats in Stage 10).
    # Keys may include: anchors_active (bool), anchor_entity_count (int),
    # query_anchor_pct (float), dropped_offniche_queries (int),
    # pain_evidence_anchor_coverage (float).
    niche_drift_telemetry: dict = Field(default_factory=dict)
    # Caveats from post-crew pain-coverage enforcement (high-severity pains a
    # solution set could not cover). Surfaced in the data-quality summary.
    idea_coverage_caveats: list[str] = Field(default_factory=list)
    idea_ruled_out: list[RuledOutFinding] = Field(
        default_factory=list,
        description=(
            "Structured 'examined & ruled out' findings from Stage 5: {idea_name, pain_title, "
            "reason, market_fit, market_fit_band, prior_tier, source, evidence, idea}."
        ),
    )
    idea_funnel_counts: dict = Field(
        default_factory=dict,
        description=(
            "Stage-5 research-funnel tallies for the UI ledger (pains_identified, cells_run, "
            "concepts_generated, survived_critics, winners, salvaged, demoted, merge_groups, "
            "variants_absorbed, backfill_run, backfill_accepted, candidates_shown)."
        ),
    )
    idea_overlap_groups: list[dict] = Field(
        default_factory=list,
        description=(
            "Variant-overlap groups a buyer would see as one product: {idea_names, "
            "shared_product}. Groups whose merge was accepted are absorbed into an "
            "idea_tier='merged' idea; the rest drive the UI's grouped-variant display."
        ),
    )
    niche_incumbent_map: list[dict] = Field(
        default_factory=list,
        description=(
            "Web-verified incumbent products for this niche from the Phase-1 parity probe: "
            "{name, pricing, focus, gap, source}. Mirrors UnifiedSolutionCrew._incumbent_rows; "
            "handed to Stage-2 deep-research crews (see utils/market_brief.py) and the report's "
            "market_reality section."
        ),
    )
    niche_wallet_brief: dict = Field(
        default_factory=dict,
        description=(
            "Niche-level tooling-spend signal from the Phase-1 wallet probe: "
            "{wallet_class, evidence, free_density}. Mirrors "
            "UnifiedSolutionCrew._niche_wallet_brief."
        ),
    )
    # User-seed pipeline (eager-meandering-feather.md Phase 4, section C): the ONE crew a later
    # seed idea uses is hydrated from persisted state rather than cold-re-probing paid Phase-1
    # work. `_incumbent_rows`/`_niche_wallet_brief` already had a state home above (niche_incumbent
    # _map/niche_wallet_brief); these two mirror the same pattern for the two caches that didn't:
    # `UnifiedSolutionCrew._data_menu_text`/`._dissatisfaction_text` are otherwise instance-only.
    niche_data_menu_text: str | None = Field(
        default=None,
        description=(
            "Rendered VERIFIED data-route menu from the Phase-1 data-menu probe (one LLM call). "
            "Mirrors UnifiedSolutionCrew._data_menu_text. None = never probed this run (not the "
            "same as '' = probed, found nothing — a hydrated crew must distinguish the two so it "
            "doesn't skip a real probe)."
        ),
    )
    niche_dissatisfaction_text: str | None = Field(
        default=None,
        description=(
            "Rendered incumbent-dissatisfaction block from the Phase-1 dissatisfaction-signal "
            "probe. Mirrors UnifiedSolutionCrew._dissatisfaction_text. None = never probed this "
            "run; '' = probed, no qualifying signal found."
        ),
    )
    idea_portfolio_summary: str | None = Field(
        default=None,
        description=(
            "LLM-narrated honest assessment of the visible idea pool, grounded in verified "
            "Phase-1 signals (see utils/idea_portfolio_summary.py). None when the pool was "
            "empty or the grounded LLM pass failed its name-coverage guardrail."
        ),
    )
    # Generic degradation ledger: every FAIL-OPEN gate or silent quality reduction anywhere in the
    # pipeline appends a one-line summary here (e.g. "Quote stance filter unavailable for 20/24 pain
    # points — quotes kept unfiltered"). Surfaced verbatim in data_quality_summary.quality_caveats.
    # Design rule: fail-open without surfacing is fail-silent (2026-07-02 cottage-food run: the stance
    # gate died for the whole run and the report looked fully validated).
    pipeline_degradations: list[str] = Field(default_factory=list)

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

    # Cached competitor mentions (extracted once, reused on regeneration)
    competitor_mentions_formatted: Optional[str] = Field(
        default=None,
        description="Formatted competitor/tool mentions. Cached to avoid re-extraction on regeneration."
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

    # Keyword Validation Results (quick validation for top N solutions)
    keyword_validation_results: Optional[list[CrewKeywordValidationResult]] = Field(
        default=None,
        description="Keyword validation results for top N solutions from keyword validation"
    )

    # Stage 10: Solution Refinement (strategic recommendations based on keyword insights)
    solution_refinement: Optional[SolutionRefinement] = Field(
        default=None,
        description="Strategic refinement recommendations from Stage 7"
    )

    # Stage 8: Pricing Strategy Validation (for top N solutions)
    pricing_strategies: Optional[list[PricingStrategyResult]] = Field(
        default=None,
        description="Pricing strategies for top N solutions from Stage 8"
    )

    # Stage 8: Traffic Monetization Strategy (for directories/aggregators/comparison-tools)
    traffic_monetization_results: Optional[list[TrafficMonetizationResult]] = Field(
        default=None,
        description="Traffic monetization strategies for directory/aggregator/comparison-tool solutions from Stage 8"
    )

    # Stage 9: Market Sizing & Validation
    market_sizing: Optional[MarketSizingResult] = Field(
        default=None,
        description="Market sizing analysis with TAM/SAM/SOM estimates and viability assessment from Stage 9"
    )

    # Stage 11: Trend Longevity Analysis
    trend_longevity: Optional[TrendLongevityResult] = Field(
        default=None,
        description="Trend longevity and market momentum analysis from Stage 11"
    )

    # Stage 9: Seed Keywords
    seed_keywords: list[str] = Field(default_factory=list, description="Seed keywords for SEO research")

    # Stage 9 Sub-Phase Checkpoints (for resume capability)
    seo_expanded_keywords: Optional[dict[str, Any]] = Field(
        default=None,
        description="Phase 6a output: expanded keywords and topic clusters from conceptual expansion"
    )
    seo_validation_results: Optional[dict[str, Any]] = Field(
        default=None,
        description="Phase 6b output: DataForSEO validated keywords meeting volume threshold"
    )
    seo_enriched_keywords: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Phase 6c output: enriched keywords with full search metrics"
    )

    # Stage 12: SEO Enrichment (refined scores using keyword data from Stage 6)
    seo_enrichment: Optional[SolutionSEORefinement] = Field(
        default=None,
        description="SEO score refinements from Stage 12 using actual keyword research data"
    )

    # Stage 9 (Legacy): Keyword Validation - DEPRECATED, kept for backward compatibility
    keyword_validation: Optional[KeywordValidationResult] = None

    # Stage 6: SEO Strategy (includes integrated keyword research)
    seo_strategy_report: Optional[SEOStrategyReport] = None

    # Stage 13: Data Source Research (for selected solution only)
    data_source_research: Optional[DataSourceResearchResult] = None

    # Stage 14: Final Report
    final_report: Optional[FinalReport] = None

    # Research Reality Check (computed end of Phase 1; shared by preview + final report)
    niche_difficulty_verdict: Optional[NicheDifficultyVerdict] = None

    # Metadata
    job_id: Optional[str] = Field(default=None, description="Unique job identifier for ChromaDB collection isolation")
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
    skipped_stages: list[float] = Field(
        default_factory=list,
        description="Stages that were skipped (e.g., stage 8 for SaaS solutions)"
    )
    seeded_from_catalog: bool = Field(
        default=False,
        description="True if seeded from a catalog pain/idea (pain_research / deep_idea), skipping "
                    "the Stage-2 social scrape. Persisted to checkpoint metadata so it survives the "
                    "awaiting-selection → Phase-2 boundary and reaches the final report."
    )
    filtering_stats: Optional[dict[str, Any]] = Field(
        default=None,
        description="Filtering statistics from Stage 5: URLs searched, relevant found, filtering rate"
    )
    sources_searched: Optional[dict[str, Any]] = Field(
        default=None,
        description="Per-platform search results: {platform: {enabled: bool, posts_found: int}}"
    )

    # Cost Tracking
    cost_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="API cost summary: total tokens, costs by stage, total cost (from CostTracker)"
    )
