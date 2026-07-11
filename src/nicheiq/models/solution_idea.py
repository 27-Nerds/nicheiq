"""
Pydantic models for solution ideas (Stage 7).
"""


from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AudienceFitResult(BaseModel):
    """Output of the post-generation audience-fit judgment (output framing only).

    `serves_audience` holds the solution_name values the LLM judged to primarily serve the
    user's stated audience. Used to set SolutionIdea.audience_fit; never affects scores.
    """

    model_config = ConfigDict(extra='ignore')

    serves_audience: list[str] = Field(
        default_factory=list,
        description="solution_name values of the ideas that primarily serve the stated audience",
    )


class SEORefinementMetadata(BaseModel):
    """Metadata about SEO refinement process for transparency."""

    model_config = ConfigDict(extra='ignore')

    baseline_volume_used: Optional[int] = Field(
        default=None, description="Baseline search volume used for calculations"
    )
    volume_multiplier: Optional[float] = Field(
        default=None, description="Multiplier applied based on actual vs baseline volume"
    )
    tier1_multiplier: Optional[float] = Field(
        default=None, description="Multiplier based on Tier 1 keyword count"
    )
    competition_modifier: Optional[float] = Field(
        default=None, description="Modifier based on average competition level"
    )
    base_cac: Optional[float] = Field(
        default=None, description="Base customer acquisition cost before adjustments"
    )
    difficulty_multiplier: Optional[float] = Field(
        default=None, description="Multiplier based on keyword difficulty"
    )
    volume_discount: Optional[float] = Field(
        default=None, description="Discount applied for high volume economies of scale"
    )
    estimated_year1_pages: Optional[int] = Field(
        default=None, description="Estimated number of pages in first year"
    )
    keyword_evidence_floor: Optional[float] = Field(
        default=None, description="Keyword evidence floor value used as rescue mechanism"
    )
    floor_applied: Optional[bool] = Field(
        default=None, description="Whether keyword evidence floor overrode multiplicative score"
    )
    floor_reason: Optional[str] = Field(
        default=None, description="Why floor was applied (e.g. 'keyword_evidence_override')"
    )
    min_competition_modifier_applied: Optional[bool] = Field(
        default=None, description="Whether competition modifier was floored to minimum"
    )

class SolutionSEORefinement(BaseModel):
    """
    SEO score refinements from Stage 12 using actual keyword data.

    Contains ONLY the refined/new fields added after keyword research.
    Used in unified enrichment pattern where each stage outputs only its additions,
    then report generator merges all enrichments into complete SolutionIdea.
    """
    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of solution being refined")

    seo_scalability_score_refined: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Refined SEO scalability score using actual keyword volume data from Stage 9"
    )

    estimated_cac_organic_refined: Optional[str] = Field(
        default=None,
        description="Refined organic CAC range based on keyword difficulty and volume (e.g., '$12-25')"
    )

    programmatic_seo_opportunity_refined: Optional[str] = Field(
        default=None,
        description="Quantified programmatic SEO opportunity with page count estimates"
    )

    estimated_indexable_pages: Optional[int] = Field(
        default=None,
        description="Estimated number of indexable pages based on keyword research and content model"
    )

    seo_refinement_metadata: Optional[SEORefinementMetadata] = Field(
        default=None,
        description="Detailed calculation metadata showing how refined scores were derived"
    )

class SolutionEvaluation(BaseModel):
    """Evaluation scores and analysis for a single solution."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution being evaluated")
    technical_feasibility_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Technical feasibility score (0.0-1.0 scale)"
    )
    market_fit_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Product-market fit score (0.0-1.0 scale)"
    )
    development_complexity: str = Field(
        ..., description="Development complexity: Low, Medium, or High"
    )
    estimated_development_time: str = Field(
        ..., description="Estimated time to MVP (e.g., '3-4 months', '6-8 months')"
    )
    differentiation_potential: float = Field(
        ..., ge=0.0, le=1.0,
        description="Differentiation potential score (0.0-1.0 scale)"
    )
    organic_acquisition_potential: float = Field(
        ..., ge=0.0, le=1.0,
        description="Organic acquisition potential score (0.0-1.0 scale) - effectiveness of SEO/content for customer acquisition"
    )
    strengths: list[str] = Field(..., description="Key advantages and positive factors")
    weaknesses: list[str] = Field(..., description="Concerns, risks, or challenges")
    key_risks: list[str] = Field(..., description="Critical factors that could cause failure")

class EvaluationResult(BaseModel):
    """Complete evaluation results for all solutions."""

    model_config = ConfigDict(extra='ignore')

    evaluations: list[SolutionEvaluation] = Field(
        ..., description="Evaluation for each solution"
    )
    ranking: list[str] = Field(
        ..., description="Solution names ranked by overall opportunity"
    )
    comparative_analysis: str = Field(
        ..., description="Side-by-side comparison and recommendation"
    )


# ---------------------------------------------------------------------------
# Idea tag facets (closed vocabularies) — see docs/IDEA_TAGS.md
# These Literal aliases are the single source of truth for the tag vocabulary,
# reused by IdeaTags below and by the LLM tagging output model (SolutionTagBatch).
# ---------------------------------------------------------------------------
ProjectTypeTag = Literal[
    "aggregator", "saas", "comparison-tool", "directory", "marketplace", "other"
]
TargetMarketTag = Literal["b2b", "b2c", "prosumer", "b2b2c"]
MonetizationTag = Literal[
    "subscription", "one-time", "commission", "usage-based",
    "advertising", "affiliate", "licensing",
]
GrowthChannelTag = Literal[
    "programmatic-seo", "content", "community", "paid-ads",
    "network-effects", "integrations",
]
RiskFlagTag = Literal["regulatory", "tos-risk", "grey-market", "trust-dependent"]
DataAccessTag = Literal[
    "public", "freemium", "paywalled", "unofficial", "restricted", "blocked", "unverified"
]
BuildComplexityTag = Literal["low", "medium", "high"]
NoveltyLevelTag = Literal["conventional", "moderate", "novel"]
StrengthTag = Literal[
    "market-fit", "seo-power", "innovator", "quick-build", "solo-friendly"
]
# How often the buyer USES the product — not how it bills. Episodic usage sold as a
# subscription churns between events; the deterministic pricing-shape check reads this.
UsageCadenceTag = Literal["continuous", "periodic", "episodic", "one-shot"]


class IdeaTags(BaseModel):
    """
    Closed-vocabulary filter facets for an idea, displayed as chips (now) and used
    for filtering (later). Assembled in `utils.idea_tags.derive_tag_facets()`:
    LLM-generated semantic facets are merged with code-derived buckets and facets
    reused from existing idea fields. See docs/IDEA_TAGS.md.
    """

    model_config = ConfigDict(extra='ignore')

    # Reused verbatim from existing idea fields (cross-job filters)
    project_type: Optional[ProjectTypeTag] = Field(default=None)
    data_access: Optional[DataAccessTag] = Field(default=None)

    # LLM-generated semantic facets
    target_market: Optional[TargetMarketTag] = Field(default=None)
    monetization: Optional[MonetizationTag] = Field(
        default=None, description="Primary revenue model"
    )
    monetization_secondary: Optional[MonetizationTag] = Field(default=None)
    growth_channels: list[GrowthChannelTag] = Field(default_factory=list)
    risk_flags: list[RiskFlagTag] = Field(default_factory=list)
    usage_cadence: Optional[UsageCadenceTag] = Field(
        default=None, description="How often the buyer uses the product (not how it bills)"
    )

    # Code-derived pricing-shape check: usage cadence vs monetization (episodic/one-shot
    # usage sold as a subscription churns between events). Informational — never a score.
    pricing_shape_mismatch: bool = Field(default=False)
    pricing_shape_note: Optional[str] = Field(default=None)

    # Code-derived from scores
    build_complexity: Optional[BuildComplexityTag] = Field(default=None)
    novelty_level: Optional[NoveltyLevelTag] = Field(default=None)
    # All earned strengths (modal + future filtering)
    strengths: list[StrengthTag] = Field(default_factory=list)
    # The single most-exceptional strength (max margin above cutoff), or None — card badge
    primary_strength: Optional[StrengthTag] = Field(default=None)

    # LLM's one-sentence justification of the non-obvious (semantic) tag calls — "Why these tags".
    rationale: Optional[str] = Field(default=None)


class BaseSolutionIdea(BaseModel):
    """
    Solution idea as output by Stage 7 (UnifiedSolutionCrew).

    Contains ONLY the fields that Stage 7 should populate. Does NOT include:
    - Stage 10 keyword refinement fields (keyword_geographic_priorities, etc.)
    - Stage 12 SEO refinement fields (seo_scalability_score_refined, etc.)

    Those fields are added via Python merging in report_generator._merge_solution_enrichments()
    using separate output models (SolutionRefinement, SolutionSEORefinement).
    """

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the proposed product")
    headline: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable title (5-12 words) that communicates what the product does. "
            "NOT the code name. Should read like a search query a real person types into Google. "
            "Examples: 'CI/CD-style reliability testing for AI agents', "
            "'Real-time eviction risk scores by neighborhood'."
        )
    )
    short_description: Optional[str] = Field(
        default=None,
        description=(
            "Punchy 1-2 sentence summary for card display. Focuses on what the user gets "
            "and why it matters — not the full user journey. Must be under 180 characters. "
            "Example: 'Run automated test suites against agent outputs before every deploy. "
            "Catch hallucinations, format drift, and regression.'"
        )
    )
    description: str = Field(
        ...,
        description=(
            "Detailed description of HOW the solution works from the user's perspective. "
            "Should include the complete user journey: what users see when they arrive, "
            "what actions they take, what inputs they provide, what results they get, "
            "and how the solution delivers value. Must be specific and concrete enough "
            "that someone could visualize using the service (4-6 sentences minimum)."
        )
    )
    value_proposition: str = Field(
        ...,
        description=(
            "One-line value proposition clearly stating the core benefit. "
            "Should be a single compelling sentence that captures the unique value "
            "compared to alternatives. Not a tagline - a clear statement of what users get."
        )
    )
    pain_points_addressed: list[str] = Field(
        ..., description="List of pain points this solution addresses"
    )
    # Grounded generation provenance (code-filled from the divergent (pain × segment) cell
    # that produced this idea; NOT an LLM self-report). Surfaced on the Stage-1 selection UI.
    source_pain: Optional[str] = Field(
        default=None, description="Title of the pain point the generating cell focused on"
    )
    source_segment: Optional[str] = Field(
        default=None, description="Name of the audience segment the generating cell reasoned as"
    )
    # Multi-Frame Idea Generation Portfolio: which generation FRAME minted this idea's cell —
    # 'pain' (default/legacy) | 'gap' | 'data_asset' | 'workflow'.
    source_frame: Optional[str] = Field(
        default="pain",
        description=(
            "CODE-FILLED after generation — ALWAYS leave as the default; never set by the LLM. "
            "The typed generation frame that minted this idea's cell."
        ),
    )
    # Payability inherited from source_segment (permanent buyer-wallet signal): stamped in code so
    # the pure cap in _validate_idea_caps can read it off the idea. None = flag off / unscored.
    source_segment_payability: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="CODE-FILLED after generation — ALWAYS leave null/omit this field"
    )
    source_segment_payability_class: Optional[str] = Field(
        default=None,
        description="CODE-FILLED after generation — ALWAYS leave null/omit this field"
    )
    audience_fit: Optional[bool] = Field(
        default=None,
        description=(
            "OUTPUT-framing only: True when this idea serves the user's stated target audience "
            "(set post-generation by ResearchFlow._tag_audience_fit; None when no audience). "
            "Never influences generation or scores; drives the frontend primary/adjacent split."
        ),
    )
    core_features: list[str] = Field(
        ..., description="Key features for minimum viable product"
    )
    target_personas: list[str] = Field(
        ..., description="Target user persona descriptions"
    )
    technical_approach: Optional[str] = Field(
        default=None, description="Technical architecture and implementation approach"
    )
    differentiation_factors: Optional[list[str]] = Field(
        default=None, description="Unique factors that differentiate from competitors"
    )
    requires_data_aggregation: bool = Field(
        default=False,
        description="Whether product requires external data aggregation",
    )
    data_sources: Optional[list[str]] = Field(
        default=None,
        description="Potential data sources if aggregation is required — clean source NAMES only "
        "(e.g. 'Reddit API', 'SEC EDGAR'); never embed [NEEDS-VERIFY: ...] flags here (those go in "
        "data_acquisition_notes)",
    )
    estimated_development_time: Optional[str] = Field(
        default=None, description="Estimated time to build MVP (grounded range, e.g. '6-10 weeks')"
    )
    dev_time_rationale: Optional[str] = Field(
        default=None,
        description="One-line LLM reasoning for the build-time estimate (the binding/most-involved component)",
    )
    pricing_strategy: Optional[str] = Field(
        default=None, description="Detailed pricing model and monetization strategy"
    )
    market_fit_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "Product-market fit (0-1), anchored to the addressed VALIDATED pains. "
            "0.85-1.0: directly addresses a high-severity (≥0.6) / high-mention / GOLD-tier "
            "pain with no dominant incumbent; 0.5-0.7: 1-2 high-severity pains or a crowded "
            "but addressable market; ≤0.4: low-severity / thin-evidence pain, a pain not "
            "in the validated set, OR the solution's core mechanism/data route is unverified "
            "(a real pain solved by a product that can't actually be built/sourced is not a fit). "
            "Set proportional to the addressed pain's severity."
        ),
    )
    technical_feasibility_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "Can this be BUILT AT ALL with currently available tech and data? (0-1; capability, "
            "distinct from solo_dev_feasibility which is scope/effort). 0.85-1.0: every component "
            "has a production library or hosted API AND the required data is confirmed obtainable "
            "in bulk; 0.65-0.84: one component needs careful architecture but documented solutions "
            "exist; 0.40-0.64: 2+ components have no off-the-shelf solution or data availability is "
            "uncertain/unverified; 0.10-0.39: needs unreliable AI capability, exotic infra, or "
            "unobtainable data. Gates the verdict (<0.60 ⇒ No-Go)."
        ),
    )
    # Data feasibility — can a solo dev actually OBTAIN the data this idea needs?
    # Distinct from technical_feasibility_score (can it be BUILT). Populated in code via
    # carry-over from the independent feasibility critic, not by the convergent LLM.
    # Surfaced in the report/UI; annotate-only (does NOT gate the verdict).
    data_feasibility_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "How readily a solo dev can obtain the required data (0-1). 0.9-1.0 free/public; "
            "0.6-0.8 paywalled-but-affordable or unofficial-API (ToS-gray, obtainable); "
            "0.3-0.5 expensive/restricted; 0.0-0.2 no obtainable route. Annotate-only."
        ),
    )
    data_access_model: Optional[str] = Field(
        default=None,
        description=(
            "How the required data is obtained: 'public' | 'freemium' | 'paywalled' | "
            "'unofficial' (unofficial API / scraping lib, ToS-gray — kept + flagged) | "
            "'restricted' | 'blocked'. The Stage-7 critic drops 'blocked' RawConcepts, but the v4 "
            "data-route verifier can also set 'blocked' AFTER that drop (when a route is unverified/"
            "unobtainable) — those ideas SURVIVE and are market_fit/feasibility capped, not dropped. "
            "The verifier's own 'official' verdict is canonicalized to 'public' (obtainable) or "
            "'blocked' (not) so it always lands in this enum — see idea_improvement_loop_v4."
        ),
    )
    data_acquisition_notes: Optional[str] = Field(
        default=None,
        description=(
            "Short note: what data the idea needs, the source/route, access model + rough "
            "cost; for 'unofficial'/'paywalled' name the tool + the ToS/cost risk."
        ),
    )
    # Independent build-feasibility estimate from the critic. Carried for the downgrade-only
    # verdict cap (min(technical_feasibility_score, build_feasibility_score)); NOT part of the
    # composite ranking (score_helpers reads only market_fit/tech_feas/novelty/seo).
    build_feasibility_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Independent critic estimate of build feasibility (0-1); caps the verdict tech gate (downgrade-only).",
    )
    project_type: Optional[str] = Field(
        default=None,
        description="Project type category: saas, directory, aggregator, comparison-tool, marketplace"
    )

    # Structural-dedup tags (M/D/J) carried over from the source RawConcept during
    # refinement. Persisted so the cross-run/regeneration dedup can catch a
    # structurally-identical idea that was merely REWORDED (text-based dedup misses
    # those). Populated in code (UnifiedSolutionCrew.execute_pipeline), not by the LLM.
    mechanism_tag: Optional[str] = Field(
        default=None, description="Core value-production mechanism (hyphenated phrase)"
    )
    data_source_tag: Optional[str] = Field(
        default=None, description="Primary data source (hyphenated phrase)"
    )
    journey_tag: Optional[str] = Field(
        default=None, description="User journey (hyphenated phrase)"
    )

    # Closed-vocabulary filter facets (chips + future filtering). Populated in code
    # (UnifiedSolutionCrew tagging step → utils.idea_tags.derive_tag_facets), not by the
    # refinement LLM. See docs/IDEA_TAGS.md.
    tags: Optional[IdeaTags] = Field(default=None)

    # SEO & Organic Acquisition Fields (Stage 7 estimates - before keyword research)
    programmatic_seo_opportunity: Optional[str] = Field(
        default=None,
        description=(
            "Assessment of programmatic SEO potential for this solution type. "
            "Examples: 'High - directory listings generate natural SEO pages', "
            "'Medium - comparison pages create indexable content', "
            "'Low - pure SaaS with minimal content generation'. "
            "Should reference specific content generation patterns and estimated page count potential."
        )
    )

    content_generation_model: Optional[str] = Field(
        default=None,
        description=(
            "Description of how this solution naturally generates SEO-friendly content. "
            "Examples: 'User submissions create unique tool pages', "
            "'Aggregated data creates comparison landing pages', "
            "'Manual content marketing via blog and guides'. "
            "Focus on WHAT content gets created, not HOW to build it technically."
        )
    )

    organic_discovery_queries: Optional[list[str]] = Field(
        default=None,
        description=(
            "5-10 example search queries where users would naturally discover this solution organically. "
            "Should reflect actual search intent patterns that the solution's content would rank for. "
            "Examples: 'best [tool type] for [use case]', '[problem] solutions', '[category] comparison'"
        )
    )

    estimated_cac_organic: Optional[str] = Field(
        default=None,
        description=(
            "Estimated customer acquisition cost via organic channels (SEO, content marketing). "
            "Format: '$X-Y per customer' with rationale. "
            "Consider: programmatic content generation reduces CAC dramatically vs paid channels. "
            "Examples: '$5-15 (programmatic SEO pages)', '$50-100 (traditional SEO + content)', "
            "'$200+ (limited content opportunities, relies on paid)'"
        )
    )

    estimated_cac_paid: Optional[str] = Field(
        default=None,
        description=(
            "Estimated customer acquisition cost via paid channels (ads, PPC) for comparison. "
            "Format: '$X-Y per customer' with rationale. "
            "Use for CAC comparison to highlight organic advantage. "
            "Examples: '$100-300 (competitive keywords)', '$50-150 (niche keywords)'"
        )
    )

    seo_scalability_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "SEO scalability assessment (0-1 scale). "
            "How easily can this solution scale organic traffic through content? "
            "0.8-1.0: High programmatic SEO potential (directories, aggregators) — REQUIRES a real, "
            "enumerable content corpus and a non-cold-start seeding path (programmatically generatable "
            "pages alone don't count if the underlying data is restricted/unverified or must be "
            "hand-seeded; cap at 0.5 in that case). "
            "0.5-0.7: Moderate content generation (comparison tools, marketplaces) "
            "0.2-0.4: Limited content scaling (traditional SaaS) "
            "0.0-0.1: Minimal SEO leverage (tool-only products)"
        )
    )

    estimated_indexable_pages: Optional[int] = Field(
        default=None,
        description=(
            "Estimated total potential indexable pages for SEO. "
            "Represents the full scope of programmatic content generation potential. "
            "Used for CAC calculations and growth projections. "
            "Populated during Stage 12 SEO refinement based on keyword research."
        )
    )

    # Novelty & Solo-Dev Feasibility Fields (Stage 7)
    novelty_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Innovation/uniqueness score (0-1 scale). "
            "Assign AFTER filling conventional_approach, innovation_angle, and why_it_works. "
            "Derive the score from the strength of those three fields: "
            "0.8-1.0: innovation_angle describes a mechanism no competitor uses, "
            "AND why_it_works cites specific community evidence. "
            "0.5-0.7: innovation_angle shows a genuine structural difference, "
            "AND why_it_works references validated pain point data. "
            "0.3-0.4: innovation_angle is a minor twist on conventional_approach, "
            "OR why_it_works relies on general reasoning without research data. "
            "0.0-0.2: No meaningful divergence from conventional_approach."
        )
    )

    conventional_approach: Optional[str] = Field(
        default=None,
        description=(
            "What most builders would attempt for this problem space. "
            "Describe the obvious, default strategy that a typical founder or developer "
            "would pursue — the well-trodden path. Be specific about the approach, not vague. "
            "Example: 'Most would build a full comparison platform with user reviews and editorial content.'"
        )
    )

    innovation_angle: Optional[str] = Field(
        default=None,
        description=(
            "How this solution diverges from the conventional approach. "
            "Explain the specific twist, constraint, or mechanism that makes this solution "
            "different from what most would try. Focus on the structural difference. "
            "Example: 'This focuses exclusively on automated speed tests from 50+ global locations, "
            "publishing objective latency data rather than subjective reviews.'"
        )
    )

    why_it_works: Optional[str] = Field(
        default=None,
        description=(
            "Evidence-based reason why the innovation angle succeeds. "
            "Ground this in specific pain point data, community signals, or market evidence "
            "from the research. Reference real user behavior or validated frustrations. "
            "Example: 'Community threads show users distrust subjective reviews and specifically "
            "ask for real-world speed data — 14 threads with 200+ upvotes mention this gap.'"
        )
    )

    why_it_works_short: Optional[str] = Field(
        default=None,
        description=(
            "One-sentence card summary of why_it_works. Max 120 chars. "
            "Distill the core evidence into a single punchy claim. "
            "Write AFTER why_it_works. Keep the specific evidence. "
            "Example: '14 threads (200+ upvotes) show users want objective speed data, not reviews.'"
        )
    )

    solo_dev_feasibility: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Feasibility for ONE person to build AND indefinitely OPERATE this (0-1). The binding "
            "constraint is ONGOING burden, not build time: weight support load, uptime / on-call "
            "demands, manual moderation, continuous hand-seeding, and how many channels it must be "
            "marketed on — these sink solo founders far more often than build complexity. Build effort "
            "is the SECONDARY axis. Cannot exceed build feasibility (you can't solo-run what you can't "
            "build). "
            "0.9-1.0: ships in <2 months AND runs hands-off — static/API-backed, no human-in-the-loop, "
            "support is occasional email. "
            "0.7-0.8: simple backend, light support, weekly check-ins. "
            "0.4-0.6: 3-6 month build OR a real recurring ops load (seeded corpus, human-in-the-loop, "
            "daily monitoring). "
            "0.0-0.3: heavy infra, 24/7 on-call / constant moderation, or needs a team / enterprise "
            "sales. A maintenance-heavy product is NOT solo-feasible at 0.8+ however easy it is to build."
        )
    )
    obviousness_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Independent novelty critic's estimate of how OBVIOUS this idea is "
            "(0-1, LOWER = more original): the fraction of competent builders who would "
            "also propose essentially this concept. Carried from the source RawConcept "
            "during refinement (same name-match pattern as the M/D/J tags). Bands: "
            "0.0-0.2 highly novel (<5% would), 0.3-0.5 somewhat novel, 0.6-0.8 mildly "
            "obvious, 0.8-1.0 cached first-thought. Surfaced in the UI as 'Originality' "
            "(= 1 - obviousness_score)."
        )
    )

    # Realism-calibration provenance (Stage 7 post-refinement). When the independent realism
    # critic re-scores an idea, the generator's ORIGINAL self-scores are preserved here so the
    # change is auditable (and the A/B harness can compare raw vs calibrated). These MUST be
    # declared fields — BaseSolutionIdea is extra='ignore', so undeclared extras would be dropped
    # on the next model_validate / checkpoint reload. None until the critic runs (flag-gated).
    market_fit_score_raw: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Generator's original market_fit_score before realism calibration (audit/A-B only).",
    )
    technical_feasibility_score_raw: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Generator's original technical_feasibility_score before realism calibration.",
    )
    novelty_score_raw: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Generator's original novelty_score before realism calibration.",
    )
    seo_scalability_score_raw: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Generator's original seo_scalability_score before realism calibration.",
    )
    obviousness_score_raw: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Pre-refinement critic's original obviousness_score before realism re-score.",
    )
    solo_dev_feasibility_raw: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Generator's original solo_dev_feasibility before realism calibration (audit/A-B only).",
    )
    calibration_notes: Optional[str] = Field(
        default=None,
        description="Realism critic's per-criterion 1-line reasons (audit/transparency; not user-facing).",
    )
    incumbent_parity: Optional[str] = Field(
        default=None,
        description=(
            "Web-verified mechanism-parity finding for top ideas, e.g. 'shipped by MoeGo: "
            "route optimization (Smart Schedule)' or 'none found'. Set by the parity probe; "
            "None when the probe didn't run for this idea."
        ),
    )
    adjacent_market_parity: Optional[str] = Field(
        default=None,
        description=(
            "CODE-FILLED by the web-verified adjacent-market probe — ALWAYS leave null/omit "
            "this field. (Audience-independent incumbent in the adjacent commercial market the "
            "mechanism monetizes in; None = no finding / probe didn't run.)"
        ),
    )
    red_team_verdict: Optional[str] = Field(
        default=None,
        description=(
            "CODE-FILLED by the adversarial red-team pass over top visible ideas — ALWAYS leave "
            "null/omit this field. One of 'survives' | 'weakened' | 'killed'; None = idea not "
            "red-teamed."
        ),
    )
    red_team_caveats: Optional[list[str]] = Field(
        default=None,
        description=(
            "CODE-FILLED by the red-team pass — ALWAYS leave null/omit this field. Up to 3 "
            "evidence-cited kill/weaken caveats; None = idea not red-teamed."
        ),
    )
    red_team_revised: Optional[bool] = Field(
        default=None,
        description=(
            "CODE-FILLED by the red-team revision tail — ALWAYS leave null/omit this field. "
            "True when the adversarial pass produced a revision that BEAT the original and "
            "cleared its own parity re-probe (the shown idea IS the revision); None otherwise."
        ),
    )
    idea_tier: str = Field(
        default="single",
        description=(
            "Portfolio-funnel provenance tier: 'single' (a per-cell tournament winner — one focused "
            "tool), 'salvaged' (a tournament loser the calibration critic rescued via the salvage "
            "gate), or 'bundle' (a synthesis-stage product composing several complementary pains). "
            "Drives the report's tier badge; default 'single' keeps legacy data unchanged."
        ),
    )
    candidate_status: str = Field(
        default="active",
        description=(
            "Visibility status of this idea in the candidate list: 'active' (shown), "
            "'demoted' (below the demotion bar - hidden, surfaced as an examined-and-ruled-out finding), "
            "'restored' (demoted but shown anyway by the min-visible floor guard), "
            "'absorbed' (variant folded into an idea_tier='merged' synthesis - hidden, recorded as lineage). "
            "Distinct from idea_tier, which is birth provenance."
        ),
    )
    merged_from: Optional[list[str]] = Field(
        default=None,
        description=(
            "CODE-FILLED on idea_tier='merged' syntheses: solution_names of the variant ideas "
            "this product was merged from (their candidate_status becomes 'absorbed'). "
            "None on every other tier — ALWAYS leave null/omit this field."
        ),
    )
    # Angle-aware evaluation (set by the in-cell angle classifier; None only on classify fail-soft).
    winning_angle: Optional[str] = Field(
        default=None,
        description=(
            "The GTM angle the agent judged best for this idea+pain: 'distribution_seo', "
            "'novel_differentiation', or 'vertical_workflow'. None when angle evaluation is off."
        ),
    )
    angle_rationale: Optional[str] = Field(
        default=None,
        description=(
            "User-facing comment (1-3 sentences): names the winning angle, why it fits this pain, and "
            "WHERE this idea's differentiation lives — so a low off-axis score (e.g. low mechanism-novelty "
            "for a catalog) is explained, not read as a flaw."
        ),
    )
    novelty_rationale: Optional[str] = Field(
        default=None,
        description=(
            "User-facing one-liner tying the novelty score to the project_type (why it's expected/low/high "
            "for this type), for the novelty score tooltip."
        ),
    )
    differentiation_locus: Optional[str] = Field(
        default=None,
        description=(
            "WHERE this idea's differentiation lives in its winning angle (data representation / mechanism / "
            "workflow step), or 'thin me-too' stated honestly. Internal research signal: the classifier "
            "computes it and Stage-2 deep research conditions on it. None when angle evaluation is off."
        ),
    )


class SolutionIdea(BaseSolutionIdea):
    """
    Full solution idea with all enrichments from Stage 7, 8.85, and 9.5.

    Extends BaseSolutionIdea with fields populated by later pipeline stages:
    - Stage 10: Keyword refinement fields (from SolutionRefinement)
    - Stage 12: SEO refinement fields (from SolutionSEORefinement)

    Used in final reports after merging. NOT used as LLM output model in Stage 7.
    The report_generator._merge_solution_enrichments() creates SolutionIdea instances
    by combining BaseSolutionIdea with SolutionRefinement and SolutionSEORefinement.
    """

    # Stage 10: Keyword Validation & Refinement (from SolutionRefinement)
    keyword_geographic_priorities: Optional[list[str]] = Field(
        default=None,
        description=(
            "Geographic priorities identified from keyword validation data (keyword validation). "
            "List of 3-8 countries/regions with highest keyword opportunity based on search volume and competition. "
            "Examples: 'Portugal (450 keywords, avg vol 1.2k)', 'Spain (320 keywords, avg vol 890)', "
            "'Germany (280 keywords, high competition)'. "
            "Used for geographic expansion planning and localized content strategy."
        )
    )

    keyword_feature_priorities: Optional[list[str]] = Field(
        default=None,
        description=(
            "Feature or category priorities identified from keyword themes in keyword validation validation. "
            "List of 3-8 feature areas or product categories with strong keyword support. "
            "Examples: 'Health insurance (580 keywords, Tier 1: 45)', 'Tax planning (320 keywords, Tier 1: 28)', "
            "'Banking services (210 keywords, high competition)'. "
            "Informs MVP scope and product roadmap decisions based on organic discovery potential."
        )
    )

    keyword_strategic_insights: Optional[str] = Field(
        default=None,
        description=(
            "Strategic insights derived from keyword validation data in keyword validation. "
            "2-3 sentence analysis covering: unexpected keyword opportunities discovered, "
            "competitive gaps revealed by low-competition/high-volume keywords, "
            "or geographic/categorical patterns that suggest pivot opportunities. "
            "Examples: 'Discovered untapped demand in Eastern Europe with 30% lower competition', "
            "'Tax residency keywords show 3x higher volume than anticipated, suggesting product expansion'."
        )
    )

    category_pivot_suggestion: Optional[str] = Field(
        default=None,
        description=(
            "Category or positioning pivot suggestion based on keyword validation findings from keyword validation. "
            "Single sentence recommendation if keyword data reveals stronger opportunity in adjacent category. "
            "Format: 'Consider pivoting from [original positioning] to [suggested positioning] based on [data insight]'. "
            "Examples: 'Consider pivoting from general expat directory to tax-focused platform based on 2.5x higher keyword volume in tax residency vertical', "
            "'null' if current positioning aligns with keyword data. Set to None if no pivot recommended."
        )
    )

    # Stage 12: Refined SEO Metrics (from SolutionSEORefinement)
    seo_scalability_score_refined: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Refined SEO scalability score based on actual keyword data from Stage 9. "
            "Adjusts the architectural estimate using: "
            "(1) total keyword volume vs baseline, "
            "(2) Tier 1 quick win count, "
            "(3) average competition level. "
            "Compare to seo_scalability_score to see impact of market reality."
        )
    )

    estimated_cac_organic_refined: Optional[str] = Field(
        default=None,
        description=(
            "Refined organic CAC estimate based on actual keyword difficulty and volume. "
            "Format: '$X-Y per customer' with adjusted range. "
            "Factors in: (1) Tier 1 keyword competition levels, "
            "(2) total market volume for economies of scale. "
            "Compare to estimated_cac_organic to see refinement."
        )
    )

    programmatic_seo_opportunity_refined: Optional[str] = Field(
        default=None,
        description=(
            "Refined programmatic SEO assessment with quantitative page count estimates. "
            "Based on discovered keyword opportunities: Tier 1 landing pages, "
            "topic clusters, geographic/category variations. "
            "Includes both the calculated page potential and the original qualitative assessment."
        )
    )

    seo_refinement_metadata: Optional[SEORefinementMetadata] = Field(
        default=None,
        description=(
            "Metadata about the SEO refinement process for transparency. "
            "Includes: baseline_volume_used, volume_multiplier, tier1_multiplier, "
            "competition_modifier, base_cac, difficulty_multiplier, volume_discount, "
            "estimated_year1_pages. Useful for debugging and understanding score changes."
        )
    )


class IdeaGenerationResult(BaseModel):
    """
    Complete result of solution idea generation (Stage 7).

    Uses BaseSolutionIdea (NOT SolutionIdea) to ensure LLM only outputs
    Stage 7 fields. Enrichment fields from Stage 10 and 12 are added
    later via Python merging in report_generator._merge_solution_enrichments().
    """

    model_config = ConfigDict(extra='ignore')

    solution_ideas: list[BaseSolutionIdea] = Field(
        ..., min_length=3, description="Generated solution concepts (minimum 3)"
    )
    recommended_solution: Optional[str] = Field(
        default=None, description="Recommended solution name from the list"
    )
    @field_validator('solution_ideas')
    @classmethod
    def validate_required_fields(cls, v: list[BaseSolutionIdea]) -> list[BaseSolutionIdea]:
        """Ensure each solution has all required fields populated."""
        for idea in v:
            if not idea.solution_name or not idea.solution_name.strip():
                raise ValueError("Solution missing solution_name")
            if not idea.description or not idea.description.strip():
                raise ValueError(f"Solution '{idea.solution_name}' missing description")
            if not idea.pain_points_addressed:
                raise ValueError(f"Solution '{idea.solution_name}' missing pain_points_addressed")
            if not idea.core_features:
                raise ValueError(f"Solution '{idea.solution_name}' missing core_features")
            if idea.market_fit_score is None:
                raise ValueError(f"Solution '{idea.solution_name}' missing market_fit_score")
            if idea.technical_feasibility_score is None:
                raise ValueError(f"Solution '{idea.solution_name}' missing technical_feasibility_score")
        return v

class SolutionEnhancement(BaseModel):
    """Enhancement data for a single solution from competitive analysis."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Solution name (must match Task 1)")
    new_core_features: list[str] = Field(
        default_factory=list,
        description="NEW features to add from competitive analysis (not all features)"
    )
    new_differentiation_factors: list[str] = Field(
        default_factory=list,
        description="NEW differentiation factors from competitive gaps (not all factors)"
    )
    value_proposition_update: Optional[str] = Field(
        default=None,
        description="Updated value proposition (only if competitive analysis suggests refinement)"
    )
    pricing_strategy_update: Optional[str] = Field(
        default=None,
        description="Refined pricing strategy (only if competitive analysis suggests changes)"
    )
    market_fit_score_adjustment: Optional[float] = Field(
        default=None,
        ge=-0.1,
        le=0.1,
        description="Market fit score adjustment based on competitive insights (max ±0.1)"
    )

class CompetitiveEnhancements(BaseModel):
    """
    Task 3 output: Competitive enhancements for solutions (ONLY new/changed data).

    Contains competitive insights to enhance solutions from Task 1.
    These enhancements will be merged with Task 1 solutions via Python.
    """

    model_config = ConfigDict(extra='ignore')

    solution_enhancements: list[SolutionEnhancement] = Field(
        ...,
        min_length=1,
        description="Enhancements for each solution based on competitive analysis (at least 1)"
    )
    overall_competitive_insights: str = Field(
        ...,
        description="Cross-solution competitive insights and market positioning (2-3 paragraphs)"
    )

    @field_validator('solution_enhancements')
    @classmethod
    def validate_solution_names(cls, v: list[SolutionEnhancement]) -> list[SolutionEnhancement]:
        """Ensure each enhancement has a valid solution_name."""
        for enh in v:
            if not enh.solution_name or not enh.solution_name.strip():
                raise ValueError("Each enhancement must have a solution_name")
        return v


# REMOVED: IdeationProcess class - not reliably populated, transparency not needed in final report


# =============================================================================
# Divergent-Convergent Ideation Models (3-Task Architecture)
# =============================================================================

class RawConcept(BaseModel):
    """
    Lightweight concept from divergent exploration (Task 1).

    Minimal fields to capture wild ideas quickly without premature evaluation.
    Each concept should be generated using one of the forced ideation techniques.
    """

    model_config = ConfigDict(extra='ignore')

    concept_name: str = Field(
        ...,
        description="Short, descriptive name for the concept (e.g., 'PlumbingCostCalc', 'RemoteTaxAdvisors')"
    )
    one_liner: str = Field(
        ...,
        description=(
            "1-2 sentence description of what this solution does and why it's interesting. "
            "Focus on the unique angle, not generic 'helps users with X'. "
            "Example: 'Aggregates plumber pricing from 50 cities to generate [City] plumbing cost pages.'"
        )
    )
    ideation_technique: str = Field(
        ...,
        description=(
            "Which ideation technique generated this concept. One of: "
            "'niche_drilling' (specific sub-niche), "
            "'data_source_inversion' (unique data source), "
            "'cross_industry_template' (pattern from other industry), "
            "'atomic_feature' (single feature as product), "
            "'community_flip' (users create content for each other), "
            "'platform_leverage' (build on existing platform APIs/ecosystems like Shopify, Stripe, GitHub)"
        )
    )
    project_type: str = Field(
        ...,
        description="Project type: directory, aggregator, comparison-tool, marketplace, saas, or other"
    )
    target_keywords: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description=(
            "2-5 example SEO keywords this solution would target. "
            "Must be specific search queries users would type. "
            "Example: ['[city] plumbing cost', 'plumber prices near me', 'how much does plumber charge']"
        )
    )
    data_source_hint: Optional[str] = Field(
        default=None,
        description=(
            "Hint about the primary data source or mechanism. "
            "Examples: 'Reddit discussions', 'Government APIs', 'User submissions', 'Web scraping [sites]'"
        )
    )
    data_route: Optional[str] = Field(
        default=None,
        description=(
            "The CONCRETE bulk route this concept's data is obtainable through — a downloadable "
            "dump, a list/index/search endpoint, an official API, or first-party user submissions. "
            "Write 'not-data-dependent' for pure-computation products, or 'NO-BULK' if the source is "
            "only a per-record lookup / login-gated / unverified. The critic verifies this claim."
        )
    )
    # Generation provenance — stamped by code with the (pain × segment) cell that generated this
    # concept (declared so model_dump/deepcopy preserve them; models are extra='ignore').
    source_pain: Optional[str] = Field(
        default=None, description="Title of the pain point the generating cell focused on"
    )
    source_segment: Optional[str] = Field(
        default=None, description="Name of the audience segment the generating cell reasoned as"
    )
    # Multi-Frame Idea Generation Portfolio: frame identity + focus identity, stamped by
    # `_one_sample` from the generating cell so `_group_pool_by_cell` can regroup the pool.
    source_frame: Optional[str] = Field(
        default=None, description="Generation frame ('pain'|'gap'|'data_asset'|'workflow')"
    )
    source_focus_key: Optional[str] = Field(
        default=None, description="FrameFocus.key of the non-pain focus that generated this concept"
    )
    why_non_obvious: Optional[str] = Field(
        default=None,
        description=(
            "Articulate the specific insight that makes this idea non-trivial. "
            "Must explain WHY this approach is not obvious. "
            "Must be specific to THIS concept — generic phrases like 'unique approach', "
            "'nobody has built this', 'innovative solution' are INVALID. "
            "Example: 'Building permit data is public but scattered across 3,100 counties; "
            "aggregating it creates a cost truth-source that beats estimate-based competitors.'"
        )
    )
    distribution_channel: Optional[str] = Field(
        default="seo",
        description=(
            "Primary distribution channel: 'seo' (default, organic search), "
            "'platform_marketplace' (Shopify App Store, Figma plugins — must ALSO have SEO keywords), "
            "'hybrid' (platform + SEO). SEO remains the primary acquisition strategy; "
            "platform distribution is a bonus, not a replacement."
        )
    )

    # Structural-dedup tags (M/D/J): the same tags from the prompt's dedup gate,
    # persisted as fields so code can verify the gate actually ran — within a
    # batch and against the cross-run blacklist. Optional in the model for
    # backward compatibility; the Task-2 guardrail enforces presence.
    mechanism_tag: Optional[str] = Field(
        default=None,
        description="Short hyphenated phrase for the core value-production mechanism (e.g., 'aggregates-public-records')",
    )
    data_source_tag: Optional[str] = Field(
        default=None,
        description="Short hyphenated phrase for the primary data source (e.g., 'government-open-data')",
    )
    journey_tag: Optional[str] = Field(
        default=None,
        description="Short hyphenated phrase for the user journey (e.g., 'search-lands-on-page')",
    )

    # Verbalized-Sampling self-estimate of how OBVIOUS this concept is (anti
    # mode-collapse). Sentinel -1.0 means "not scored" — distinguishable from a
    # genuine mid value so the filter can treat missing as a soft warning, not a
    # real score. Lower = more novel.
    obviousness_score: float = Field(
        default=-1.0,
        description=(
            "0.0-1.0 estimate of how likely a generic competent builder would ALSO "
            "propose this concept (lower = more novel). Bands: "
            "0.0-0.2 = highly novel (<5% of builders would generate it); "
            "0.3-0.5 = somewhat novel (needs a specific insight); "
            "0.6-0.8 = mildly obvious (standard technique applied to the niche); "
            "0.8-1.0 = cached first-thought (would appear on the anti-obvious blacklist). "
            "Leave at the -1.0 default only if genuinely unable to estimate."
        ),
    )

    # Feasibility-critic outputs (sentinel -1.0 = not scored, like obviousness_score).
    # Carried onto the final idea; build_feasibility_score caps the verdict, the data_*
    # fields are surfaced. ToS-gray-but-obtainable data => 'unofficial' (kept + flagged),
    # never dropped for ToS alone.
    data_feasibility_score: float = Field(
        default=-1.0,
        description="0-1 ease of obtaining the required data (lower = harder); -1.0 = not scored.",
    )
    build_feasibility_score: float = Field(
        default=-1.0,
        description="0-1 independent build-feasibility estimate; -1.0 = not scored.",
    )
    data_access_model: Optional[str] = Field(
        default=None,
        description="public | freemium | paywalled | unofficial | restricted | blocked.",
    )
    data_acquisition_notes: Optional[str] = Field(
        default=None,
        description="Short note: data source/route, access model + cost/ToS risk (≤120 chars).",
    )

    # Internal critic drop-marks set during per-sample scoring (_score_concepts) and consumed by
    # the post-barrier finalizer (_finalize_critic_pool). exclude=True keeps them out of every
    # model_dump so they never leak into the report/frontend — they only carry the drop decision
    # from the threaded scorer to the single-threaded finalizer.
    critic_already_exists: bool = Field(default=False, exclude=True)  # novelty: close equivalent exists
    critic_no_route: bool = Field(default=False, exclude=True)        # feasibility: no obtainable data route


class RawConceptList(BaseModel):
    """
    Output of divergent exploration task (Task 1).

    Contains 8-12 raw concepts generated using forced ideation techniques.
    No evaluation or scoring at this stage - quantity and variety over quality.
    """

    model_config = ConfigDict(extra='ignore')

    concepts: list[RawConcept] = Field(
        ...,
        min_length=6,
        max_length=15,
        description="8-12 raw concepts from divergent exploration (minimum 6, maximum 15)"
    )
    techniques_used: list[str] = Field(
        ...,
        description="List of ideation techniques applied during exploration"
    )
    pain_points_referenced: list[str] = Field(
        ...,
        description="Pain point titles that informed the concept generation"
    )


def visible_ideas(ideas: list) -> list:
    """The shared visibility projection: ideas the USER sees as candidates.

    Excludes 'demoted' (weak winners surfaced as examined-and-ruled-out findings instead) and
    'absorbed' (variants folded into an idea_tier='merged' synthesis). Both stay in
    solution_ideas for state/checkpoint consistency — apply THIS filter at every user-facing
    boundary (worker preview payloads, preview/final report assembly, headless selection,
    regenerate payloads). Accepts model objects or dicts."""
    out = []
    for i in ideas or []:
        status = (i.get("candidate_status") if isinstance(i, dict)
                  else getattr(i, "candidate_status", None)) or "active"
        if status not in ("demoted", "absorbed"):
            out.append(i)
    return out
