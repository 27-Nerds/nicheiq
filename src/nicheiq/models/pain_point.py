"""
Pydantic models for pain point analysis (Stage 6).
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..utils.slugify import slugify
from .keyword_data import OpportunityLevel


def compute_opportunity_level(
    severity_score: float,
    commercial_intent: float,
    *,
    high_severity: float = 0.6,
    high_commercial_intent: float = 0.6,
) -> OpportunityLevel:
    """Deterministic opportunity_level formula (mirrors the Task 3 rubric).

    High = severity ≥ high_severity AND commercial_intent ≥ high_commercial_intent;
    Medium = exactly one ≥ its cutoff; Low = neither. The cutoffs default to 0.6 but are
    HEURISTIC PRIORS (not outcome-calibrated) — callers in the pipeline pass the configurable
    `settings.opportunity_high_*_threshold` values. The LLM may justifiably score BELOW this
    formula (universal-theme / tool-addressability caps) via a downgrade_reason; upgrades are
    never honored (see the merge logic in pain_point_crew.py).
    """
    is_high_severity = severity_score >= high_severity
    is_high_intent = commercial_intent >= high_commercial_intent
    if is_high_severity and is_high_intent:
        return OpportunityLevel.HIGH
    if is_high_severity or is_high_intent:
        return OpportunityLevel.MEDIUM
    return OpportunityLevel.LOW


class UnvalidatedPainPoint(BaseModel):
    """Pain point extracted by analyst without severity/WTP scores yet."""

    model_config = ConfigDict(extra='ignore')

    title: str = Field(..., description="Short title of the pain point")
    parent_theme_id: Optional[str] = Field(
        default=None,
        description=(
            "Stable slug of the parent ThemeCategory.theme_id this pain point "
            "derives from. Optional in the model so unit-test fixtures don't have "
            "to fabricate theme linkage; in production the Task-2 guardrail "
            "(crew_guardrails.py) enforces non-null + matches a real theme_id "
            "from Task 1."
        ),
    )
    description: str = Field(..., description="Detailed description of the problem")
    short_summary: Optional[str] = Field(
        default=None,
        description=(
            "Punchy 1-2 sentence summary for card display. Focuses on the core user "
            "problem and its impact. Must be under 180 characters. "
            "Example: 'Manual invoicing wastes 3-5 hours weekly per user. "
            "Delays payments and introduces billing errors.'"
        ),
    )
    mention_count: int = Field(
        ...,
        description="Total UNIQUE discussions mentioning this problem"
    )
    anchor_keywords: list[str] = Field(
        ...,
        min_length=2,
        max_length=12,
        description="2-10 short anchor phrases (2-6 words each) capturing user language for this pain point. Task 4 uses the first 4 for vector search."
    )
    source_platforms: Optional[list[str]] = Field(
        default=None, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: Optional[list[str]] = Field(
        default=None, description="Categories this pain point belongs to"
    )

class ThemeCategory(BaseModel):
    """Single theme category from content categorization."""

    model_config = ConfigDict(extra='ignore')

    category_name: str = Field(..., description="Theme category name")
    theme_id: str = Field(
        default="",
        description=(
            "Stable slug auto-derived from category_name via slugify(). "
            "LLMs do NOT author this — it's set by a model_validator after init. "
            "Used by Task 2 pain points to set parent_theme_id and by the catalog "
            "frontend to group pain points under their source theme."
        ),
    )
    definition: str = Field(..., description="What this category represents")
    frequency: str = Field(..., description="High/Medium/Low based on mention count")
    mention_count: int = Field(
        ...,
        description="Number of distinct discussions mentioning this theme"
    )
    # Catalog rebuild (Phase 5.4): numeric severity score 0-100 for the public
    # catalog UI. Optional for backward compatibility — legacy reports produced
    # before this field existed have None and the catalog UI uses the
    # `frequency` string as a fallback (High=85, Medium=55, Low=25 mapping
    # in the frontend's scaleSeverity helper).
    severity_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Severity score 0-100 (NOT 0-1). Combines mention frequency with pain weight.",
    )
    primary_user_segments: list[str] = Field(
        ..., description="User types in this category"
    )
    anchor_keywords: list[str] = Field(
        ...,
        min_length=3,
        max_length=12,
        description="3-8 short anchor phrases (2-6 words each) that capture how users express this theme. Used by Task 4 for vector search."
    )

    @field_validator('anchor_keywords', mode='before')
    @classmethod
    def truncate_anchor_keywords(cls, v: object) -> object:
        if isinstance(v, list) and len(v) > 12:
            return v[:12]
        return v

    @model_validator(mode='after')
    def auto_populate_theme_id(self) -> 'ThemeCategory':
        """Always derive theme_id from category_name. LLM-supplied values are ignored."""
        derived = slugify(self.category_name)
        if self.theme_id != derived:
            object.__setattr__(self, 'theme_id', derived)
        return self

class UserSegment(BaseModel):
    """User segment identified in categorization."""

    model_config = ConfigDict(extra='ignore')

    segment_name: str = Field(..., description="User segment name")
    primary_concerns: list[str] = Field(
        ..., description="Main pain points/topics"
    )
    mention_frequency: str = Field(..., description="High/Medium/Low")

class ContentCategorizationReport(BaseModel):
    """Complete categorization report from Task 1."""

    model_config = ConfigDict(extra='ignore')

    executive_summary: str = Field(..., description="2-3 sentence overview")
    theme_categories: list[ThemeCategory] = Field(
        ..., min_length=4, description="5-10 theme categories identified (minimum 4)"
    )
    user_segments: list[UserSegment] = Field(
        ..., min_length=3, description="User segment profiles (minimum 3)"
    )
    overall_quality: str = Field(
        ..., description="High/Medium/Low rating"
    )
    overall_quality_justification: Optional[str] = Field(
        default=None, description="Justification for the quality rating"
    )

    @field_validator('theme_categories')
    @classmethod
    def validate_themes_have_anchor_keywords(cls, v: list[ThemeCategory]) -> list[ThemeCategory]:
        """Ensure each theme has anchor keywords for vector search."""
        for theme in v:
            if not theme.anchor_keywords or len(theme.anchor_keywords) < 3:
                raise ValueError(f"Theme '{theme.category_name}' needs at least 3 anchor_keywords")
        return v

class PainPointExtraction(BaseModel):
    """Output from pain_point_analyst before validation."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    extracted_pain_points: list[UnvalidatedPainPoint] = Field(
        ..., min_length=3, description="Pain points extracted from discussions (minimum 3)"
    )

    @field_validator('extracted_pain_points')
    @classmethod
    def validate_unique_titles(cls, v: list[UnvalidatedPainPoint]) -> list[UnvalidatedPainPoint]:
        """Reject duplicate titles within an extraction.

        The DB enforces @@unique([sourceJobId, title]) on CatalogPainPoint, so
        duplicates would fail at ingest. Catching them here surfaces a friendlier
        error and preserves Task 3 scoring (which matches by title).
        """
        seen: set[str] = set()
        dupes: list[str] = []
        for pp in v:
            key = pp.title.strip().lower()
            if key in seen:
                dupes.append(pp.title)
            seen.add(key)
        if dupes:
            raise ValueError(
                f"Duplicate pain point titles in extraction: {dupes}. "
                f"Each title must be unique within a job; scope titles to their theme "
                f"(e.g. 'Poor API Documentation for Bidirectional Charging' not 'Poor Documentation')."
            )
        return v

    extraction_summary: str = Field(
        ..., description="Summary of extraction process and key findings"
    )

class PainPointScoring(BaseModel):
    """Scoring data for a single pain point from validation task (Task 3 output).

    This intermediate model contains ONLY the new scoring fields added by the validator.
    Python will merge this with UnvalidatedPainPoint to create the final PainPoint.
    """

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(
        ..., description="Title reference key to match with UnvalidatedPainPoint"
    )
    severity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Severity score (0-1) based on functional workflow impact (not emotional volume)"
    )
    commercial_intent: float = Field(
        ..., ge=0.0, le=1.0,
        description=(
            "Commercial-intent / buying-signal strength (0-1): an ORDINAL indicator of how strongly "
            "the discussion shows commercial intent (paid-tool mentions, budget/spend signals, "
            "billable-time impact). NOT a calibrated willingness-to-pay or dollar value — text from "
            "self-selected public discussion cannot yield a true WTP (which needs conjoint/BDM-style "
            "elicitation). Use it to RANK relative buying signal, not to predict price."
        )
    )
    opportunity_level: OpportunityLevel = Field(
        ..., description="Overall opportunity level (high/medium/low)"
    )
    scoring_rationale: Optional[str] = Field(
        default=None, description="Brief explanation of why these scores were assigned"
    )
    downgrade_reason: Optional[str] = Field(
        default=None,
        description=(
            "Required ONLY when opportunity_level is set BELOW what the "
            "severity/WTP formula implies (e.g., universal-theme cap or "
            "tool-addressability cap). Minimum 20 characters explaining the downgrade."
        ),
    )
    tool_addressable: str = Field(
        default="full",
        description=(
            "Result of the TOOL-ADDRESSABILITY TEST already applied for the WTP cap: "
            "'full' (a software product could reduce this pain >=50%), 'partial' (helps but "
            "root cause is human/structural), or 'none' (lifestyle/mindset/emotional/structural "
            "problem with no software solution). 'none' pains are excluded from idea generation."
        ),
    )

class ValidationResult(BaseModel):
    """Task 3 output: Validation scores for all pain points (ONLY new scoring data)."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    pain_point_scores: list[PainPointScoring] = Field(
        ..., min_length=1, description="Validation scores for each extracted pain point (at least 1)"
    )
    validation_summary: str = Field(
        ..., description="Summary of validation methodology and overall assessment"
    )


# ========================================
# TASK 4: QUOTE ENRICHMENT OUTPUT MODELS
# ========================================

class ExtractedQuote(BaseModel):
    """A single quote with its source attribution from vector search."""

    model_config = ConfigDict(extra='ignore')

    quote_text: str = Field(..., description="Verbatim quote text from search results")
    post_id: str = Field(..., description="Post ID from search result metadata")


class StanceVerdict(BaseModel):
    """Stance classification for a single candidate quote against a pain claim."""

    model_config = ConfigDict(extra='ignore')

    index: int = Field(..., description="1-based index of the quote in the prompt list")
    stance: Literal["SUPPORTS", "NEUTRAL", "CONTRADICTS"] = Field(
        ...,
        description=(
            "SUPPORTS: the quote genuinely expresses/evidences the pain. "
            "NEUTRAL: on-topic but states no complaint. "
            "CONTRADICTS: positive or denies the pain."
        ),
    )
    reason: str = Field(default="", description="Short justification for the stance")


class BatchStanceResponse(BaseModel):
    """Stance verdicts for all candidate quotes of one pain point (single LLM call)."""

    model_config = ConfigDict(extra='ignore')

    verdicts: list[StanceVerdict] = Field(
        default_factory=list,
        description="One verdict per candidate quote, by 1-based index",
    )


class EnrichedPainPointQuotes(BaseModel):
    """Quotes found via vector search for one pain point."""

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(..., description="Exact title from Task 2 for matching")
    quotes: list[ExtractedQuote] = Field(
        default_factory=list,
        description="Quotes with post_id attribution from vector search metadata"
    )
    matched_post_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Unique post IDs from ALL relevance-passing vector hits for this pain "
            "point (pre top-12 quote cut). Wider than the kept quotes' post_ids; "
            "drives the discussion-volume mention_count (count broad, show narrow)."
        ),
    )


class QuoteEnrichmentResult(BaseModel):
    """Task 4 output: quotes per pain point from vector search."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    enriched_pain_points: list[EnrichedPainPointQuotes] = Field(
        ..., description="Quotes for each pain point from Task 2"
    )
    total_quotes_found: int = Field(..., description="Total quotes across all pain points")
    enrichment_summary: str = Field(..., description="2-3 sentences on search results and coverage")


class SinglePainPointQuotesResult(BaseModel):
    """Result of quote search for a single pain point (parallel enrichment)."""

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(..., description="Title of the pain point searched")
    anchor_keywords_searched: list[str] = Field(
        default_factory=list,
        description="Keywords used for search"
    )
    quotes: list[ExtractedQuote] = Field(
        default_factory=list,
        description="Quotes found (6-12 target)"
    )
    matched_post_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Unique post IDs from ALL relevance-passing vector hits "
            "(pre top-12 cut). Drives the discussion-volume mention_count."
        ),
    )
    search_summary: str = Field(
        default="",
        description="Brief summary of search results"
    )


class PainPoint(BaseModel):
    """Represents a user pain point discovered from social discussions."""

    model_config = ConfigDict(extra='ignore')

    title: str = Field(..., description="Short title of the pain point")
    parent_theme_id: Optional[str] = Field(
        default=None,
        description=(
            "Stable slug of the parent ThemeCategory.theme_id this pain point "
            "derives from. Carried through merge from UnvalidatedPainPoint so the "
            "backend can group pain points under their source theme. Optional for "
            "backward compatibility with reports generated before this field existed."
        ),
    )
    description: str = Field(..., description="Detailed description of the problem")
    short_summary: Optional[str] = Field(
        default=None,
        description=(
            "Punchy 1-2 sentence summary for card display. Focuses on the core user "
            "problem and its impact. Must be under 180 characters."
        ),
    )
    mention_count: int = Field(
        ...,
        description="Total UNIQUE discussions mentioning this problem - typically much larger than quote count"
    )
    severity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Severity score (0-1) based on functional workflow impact (not emotional volume)"
    )
    commercial_intent: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Commercial-intent / buying-signal strength (0-1): an ORDINAL signal of commercial intent "
            "read from the discussion (paid-tool mentions, budget/spend, billable-time impact), after "
            "the code-enforced tool-addressability cap. NOT a calibrated willingness-to-pay/dollar value "
            "(public text can't yield true WTP). Use to rank relative buying signal, not to predict price."
        ),
    )
    opportunity_level: OpportunityLevel = Field(
        ..., description="Overall opportunity level (high/medium/low)"
    )
    opportunity_downgrade_reason: Optional[str] = Field(
        default=None,
        description=(
            "Present when the LLM justifiably downgraded opportunity_level below "
            "the severity/WTP formula (universal-theme or tool-addressability cap). "
            "None when the level matches the code-computed formula."
        ),
    )
    representative_quotes: list[str] = Field(
        ..., description="Real user quotes representing this pain point"
    )
    source_platforms: Optional[list[str]] = Field(
        default=None, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: Optional[list[str]] = Field(
        default=None, description="Categories this pain point belongs to"
    )
    source_post_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Parallel array with representative_quotes: source_post_ids[i] is the "
            "post/thread ID where representative_quotes[i] was found. "
            "Empty string means source unknown. May contain duplicates."
        )
    )
    # Audience segment mapping (from Stage 6.5 audience mapping)
    affected_segments: Optional[list[str]] = Field(
        default=None,
        description=(
            "Audience segments from Stage 6.5 that experience this pain point "
            "(e.g., ['Solo Founders', 'Marketing Managers']). Populated when audience mapping available."
        )
    )
    evidence_segments: Optional[list[str]] = Field(
        default=None,
        description=(
            "Segments whose validated community hubs the pain's ACTUAL source posts came from "
            "(provenance-grounded, vs lexical affected_segments). None = not computed."
        )
    )

    # NEW: Solution approach mapping (from Stage 10 report generation)
    solution_approach: Optional[str] = Field(
        default=None,
        description="1-2 sentence explanation of how the selected solution addresses this pain point."
    )

    low_evidence: bool = Field(
        default=False,
        description=(
            "True when fewer than the minimum number of stance-verified quotes "
            "survived enrichment. Internal signal: triggers the severity clamp so a "
            "pain point with near-zero supporting evidence cannot keep a high score."
        ),
    )

    tool_addressable: str = Field(
        default="full",
        description=(
            "Tool-addressability verdict carried from scoring ('full' | 'partial' | 'none'). "
            "'none' pains (lifestyle/cultural/structural, no software solution) are excluded "
            "from idea generation by the addressability gate; they still appear in the catalog."
        ),
    )

class PainPointAnalysisResult(BaseModel):
    """Complete result of pain point analysis."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    pain_points: list[PainPoint] = Field(..., description="List of discovered pain points")
    total_mentions: int = Field(
        ..., description="Total number of pain point mentions across all discussions"
    )
    top_categories: list[str] = Field(
        ..., description="Top categories of pain points identified"
    )
    analysis_summary: str = Field(..., description="Executive summary of pain point analysis")
    content_categorization: Optional[ContentCategorizationReport] = Field(
        default=None,
        description="Detailed content categorization from Task 1 (themes, segments, quality)"
    )
