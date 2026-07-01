"""
Centralized configuration management for NicheIQ.
Uses pydantic-settings for type-safe environment variable loading.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _patch_tiktoken_models():
    """
    Patch tiktoken's MODEL_TO_ENCODING to support new OpenAI models.

    This runs at import time to ensure all libraries (CrewAI, LangChain)
    can tokenize new models like gpt-5.2, gpt-5.1, etc.
    """
    try:
        from tiktoken import model as tm

        # Models not yet in tiktoken 0.12.0 - all use o200k_base encoding
        new_models = {
            # GPT-5.2 series
            "gpt-5.2": "o200k_base",
            "gpt-5.2-chat-latest": "o200k_base",
            "gpt-5.2-pro": "o200k_base",
            # GPT-5.1 series
            "gpt-5.1": "o200k_base",
            "gpt-5.1-chat-latest": "o200k_base",
            "gpt-5.1-codex-max": "o200k_base",
            "gpt-5.1-codex": "o200k_base",
            "gpt-5.1-codex-mini": "o200k_base",
            # GPT-5 codex variants
            "gpt-5-codex": "o200k_base",
            "gpt-5-search-api": "o200k_base",
            "gpt-5-pro": "o200k_base",
            # o4 series
            "o4": "o200k_base",
            "o4-mini-deep-research": "o200k_base",
            # GPT-4.1 series (uses o200k_base like GPT-4o)
            "gpt-4.1": "o200k_base",
            "gpt-4.1-mini": "o200k_base",
            "gpt-4.1-nano": "o200k_base",
        }

        for model, encoding in new_models.items():
            if model not in tm.MODEL_TO_ENCODING:
                tm.MODEL_TO_ENCODING[model] = encoding

    except ImportError:
        pass  # tiktoken not installed


# Patch tiktoken at import time
_patch_tiktoken_models()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model_name: str = Field(default="gpt-4.1-mini", description="OpenAI model to use (safe non-reasoning default; prod overrides via env)")
    function_calling_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for function/tool calling (cheaper model recommended)"
    )
    content_analysis_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for content analysis (gpt-4.1-mini: needs 1M context for large Reddit content; gpt-4o is only 128K)"
    )
    content_analysis_reasoning_effort: str = Field(
        default="none",
        description=(
            "Reasoning effort for the Stage-3 content categorizer (Task 1, content_researcher). "
            "'none' = reasoning off (default; matches prior behavior). Bump to low/medium for deeper "
            "categorization. env: CONTENT_ANALYSIS_REASONING_EFFORT."
        )
    )
    pain_point_reasoning_effort: str = Field(
        default="none",
        description=(
            "Reasoning effort for the Stage-3 pain EXTRACTOR + validator (Tasks 2-3, "
            "pain_point_analyst / pain_point_validator, model pain_point_validation_llm). 'none' = "
            "off (default; the model was picked as non-reasoning to allow max_tokens). Bump to "
            "low/medium for deeper extraction. env: PAIN_POINT_REASONING_EFFORT."
        )
    )
    thread_validation_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for thread relevance validation in Stage 5 (gpt-4o-mini or gpt-3.5-turbo for cost efficiency)"
    )
    keyword_relevance_llm: str = Field(
        default="openrouter/google/gemini-3.1-flash-lite",
        description=(
            "Model for the idea-intent keyword relevance grader (UMBRELA 0-3). Panel-consensus benchmark "
            "(2026-06-30) picked gemini-3.1-flash-lite: cheap AND most central (0.959 vol-weighted agreement "
            "with the diverse panel). Keep batch small — gemini truncates long list output."
        ),
    )
    keyword_relevance_min_grade: int = Field(
        default=2, ge=0, le=3,
        description="Grade >= this counts as idea-intent (vs category-reach). Grade 2=BUYER, 3=JOB.",
    )
    keyword_relevance_batch_size: int = Field(
        default=12, ge=1, le=40,
        description="Keywords graded per LLM call. Small (<=12) to bound batch-composition + truncation effects.",
    )
    enable_contains_seed_enrichment: bool = Field(
        default=True,
        description=(
            "Stage 6 additive discovery (validated 2026-07-01): after broad expansion, grade the keyword "
            "set, take its idea-intent keywords as GROUNDED seeds, run DataForSEO keyword_suggestions "
            "(contains-seed) on them, grade the results, and MERGE the idea-intent long-tail (never "
            "removes). Surfaces 4-12x more idea-intent keywords the broad Google-Ads expansion misses "
            "(feeds honest market-sizing beachhead + SEO viability). ~$0.13/report. Escape hatch: False."
        ),
    )
    contains_seed_max_seeds: int = Field(
        default=8, ge=1, le=20,
        description="Max grounded idea-intent seeds to contains-seed expand (cost = ~$0.01/seed).",
    )
    contains_seed_per_seed: int = Field(
        default=150, ge=10, le=1000,
        description="keyword_suggestions returned per seed (cost = ~$0.0001/keyword).",
    )
    contains_seed_merge_min_grade: int = Field(
        default=3, ge=1, le=3,
        description=(
            "Min idea-intent grade for a contains-seed suggestion to be MERGED (distinct from the seed/"
            "demand min_grade of 2). A/B'd 2026-07-01 vs an independent 3-model panel (grok+claude-sonnet+"
            "qwen): 3 (JOB-only) cuts off-idea drift 46%->26% off-rate (-70% junk) while retaining 76% of "
            "the on-idea long-tail — contains-seed expansion over-produces category/adjacent BUYER terms "
            "gemini grades 2, so JOB-only is the precise merge gate. A 2nd-grader AND-filter was rejected."
        ),
    )
    contains_seed_llm_seeds: bool = Field(
        default=False,
        description=(
            "P0a: ALSO generate contains-seed grounding seeds via an LLM from the idea's value-prop + "
            "pains (real 2-3 word search phrases), not only from the broad set's idea-intent keywords. "
            "Fixes the catastrophic-drift case where the broad Google-Ads set is ~100% category (so the "
            "grounded-seed pool is empty/generic and the idea's own SEO axis is never surfaced). Prototype-"
            "validated (contains_seed_prototype.py): grounding LLM seeds in the broad idea-intent examples "
            "took LocalModelBenchmarks 0->27 idea-intent kw. Dark pending A/B; env CONTAINS_SEED_LLM_SEEDS."
        ),
    )
    contains_seed_thin_seed_threshold: int = Field(
        default=3,
        description=(
            "Thin-case auto-trigger for the idea-intent LLM seed generation (P0a). When the broad set "
            "yields FEWER than this many grounded seeds, the idea's SEO axis is under-covered and the "
            "solution's beachhead is thin (observed live: astrophotography selected solution → 1 grounded "
            "seed → beachhead 720/mo). In that thin case, fire the LLM real-phrase seed generation + one "
            "more contains-seed DataForSEO expansion REGARDLESS of contains_seed_llm_seeds, since that is "
            "exactly where idea-anchored seeds help most and category-drift risk is lowest. 0 disables the "
            "thin-case trigger. env CONTAINS_SEED_THIN_SEED_THRESHOLD."
        ),
    )
    thread_relevance_min_grade: int = Field(
        default=1,
        description=(
            "Minimum TREC/UMBRELA relevance grade (0-3) for a thread to pass validation and reach "
            "pain extraction. 1 keeps 'related' and up (recovers ~36% of relevant threads the old "
            "binary gate dropped at ~0.98 precision); 2 is stricter (highly-relevant only). "
            "env: THREAD_RELEVANCE_MIN_GRADE."
        )
    )
    stance_validation_llm: str = Field(
        default="gpt-4o-mini",
        description=(
            "Model for pain-point quote stance verification (does a retrieved quote "
            "genuinely express the pain). Cheap classifier; gpt-4o-mini recommended."
        ),
    )
    brainstorm_llm: str = Field(
        default="gpt-5.2",
        description="Model to use for solution brainstorming/ideation (gpt-5.2 recommended for creative thinking)"
    )
    brainstorm_llms: str = Field(
        default="",
        description=(
            "Comma-separated models to round-robin across divergent idea-generation "
            "samples for MODEL DIVERSITY (decorrelates ideas to reduce duplicates). "
            "Empty => use brainstorm_llm for all samples. Use decorrelated, "
            "REASONING-GRADE families (the divergent prompt is dense; weak/cheap models "
            "under-comply). Each entry MAY carry an inline '@<effort>' to set that "
            "model's reasoning effort (none/minimal/low/medium/high/xhigh); entries "
            "without '@' inherit brainstorm_reasoning_effort. This matters because some "
            "OpenRouter models leak the tool-call into the dropped 'reasoning' channel "
            "under forced tool_choice when reasoning is ON (e.g. DeepSeek -> use '@none'), "
            "while others need reasoning ON (e.g. Kimi -> '@medium'). Example: "
            "'openrouter/moonshotai/kimi-k2.6@medium,openrouter/deepseek/deepseek-v4-pro@none,"
            "openrouter/z-ai/glm-5.2@medium'. Set num_divergent_samples >= the model count."
        )
    )
    brainstorm_reasoning_effort: str | None = Field(
        default="high",
        description=(
            "Reasoning effort for GPT-5 series models: 'none', 'minimal', 'low', 'medium', "
            "'high', 'xhigh'. Default 'high' — this is the ONLY working creativity/depth "
            "knob for reasoning models (temperature is unsupported). Ignored by older models."
        )
    )
    num_divergent_samples: int = Field(
        default=2,
        ge=1,
        description=(
            "Number of INDEPENDENT divergent concept-generation calls (each under a "
            "different creative lens) pooled before filtering. Independent contexts break "
            "single-call mode collapse (temperature is inert on reasoning models). "
            "Cost scales linearly with this on the expensive brainstorm model."
        )
    )
    divergent_sample_deadline_seconds: int = Field(
        default=360,
        ge=30,
        description=(
            "Wall-clock cap for the parallel divergent fan-out. Once this elapses, the "
            "pool stops waiting for any still-running sample and proceeds with whatever "
            "completed. Guards against a single runaway model (e.g. a reasoning model "
            "held open by OpenRouter keep-alive bytes, which the per-call read-timeout "
            "does NOT cap) stalling the whole pipeline. Allows a sample's 2x retry "
            "before abandoning. NOTE: in pain-partitioned mode (enable_pain_partitioned_"
            "divergent) the fan-out runs up to divergent_max_generators (8) agents in "
            "parallel; with the lowered per-sample timeout each finishes fast, but set "
            "this to >=600 when using slower models so a straggler isn't abandoned early."
        )
    )
    # --- Per-cell tournament architecture (DEFAULT; flag kept only as a rollback to the legacy pool) ---
    enable_per_cell_tournament: bool = Field(
        default=True,
        description=(
            "Stage-5 architecture (DEFAULT). Each (pain x segment) cell runs its OWN ideator+judge "
            "tournament (tournament_refine_cell_v4) converging to one best idea; the union of per-cell "
            "winners (deduped only) is shown — replacing the pooled convergent-refine + the late "
            "per-idea improvement loop + diversity caps. Won the blind A/B on top-pain coverage. Set "
            "ENABLE_PER_CELL_TOURNAMENT=false to roll back to the legacy pooled flow (kept as the "
            "no-cells fallback). Note: ~2.5-3x the cost/latency of the pooled flow."
        )
    )
    tournament_rounds: int = Field(
        default=2,
        ge=1,
        le=4,
        description=(
            "Ideator<->reviewer rounds per cell in enable_per_cell_tournament mode "
            "(keep-best across rounds). 2 matches the validated mentor-loop default."
        )
    )
    enable_pain_partitioned_divergent: bool = Field(
        default=True,
        description=(
            "Pain-partitioned divergent ideation: instead of N broad samples each "
            "generating 8-12 concepts off the same pain list, run ONE narrow generator "
            "per selected diverse pain (capped at divergent_max_generators), each asked "
            "for a few concepts under a distinct persona + a "
            "hard-reserved non-info-product slot. Guarantees pain coverage by construction "
            "and breaks the info-product monoculture. Default OFF (land dark); flip on to "
            "A/B vs the legacy broad-sample path."
        )
    )
    enable_niche_anchor_cells: bool = Field(
        default=True,
        description=(
            "Bias each (pain × segment) generator cell toward the pain that best matches the "
            "niche description (deterministic token_jaccard relevance), so a theme's cell is "
            "seeded by the niche-defining pain rather than its highest-severity but off-niche "
            "theme-mate. When a lower-severity pain is chosen this way, a transparency caveat is "
            "added (it addresses the user's stated focus, not the top-severity research pain). "
            "Off ⇒ legacy severity-only cell selection."
        )
    )
    divergent_max_generators: int = Field(
        default=8,
        ge=2,
        le=12,
        description=(
            "Cap on the number of narrow generators in pain-partitioned mode (≈ one per "
            "selected diverse pain). ~5-8 is the sweet spot before cross-agent overlap / "
            "diminishing returns. Bounds parallel fan-out cost."
        )
    )
    divergent_target_generators: int = Field(
        default=6,
        ge=2,
        le=12,
        description=(
            "Target number of (pain × segment) generator cells in pain-partitioned mode. "
            "Cells are built from the audience affinity graph; if the selected high-priority "
            "pains yield fewer edges than this, the pain set is WIDENED (medium then low) "
            "until the target is met. Hard-capped by divergent_max_generators."
        )
    )
    # Severity-floor cell guarantee (always on): the cell allocation is opportunity/theme/segment-
    # affinity driven under per-segment + per-theme caps and a cell budget, NOT raw severity — so a
    # top-severity pain with thin/unmatched segment affinity could be crowded out entirely (e.g. a
    # sev-0.7 "morning routine" pain getting zero ideation, only a coverage caveat). The top-N pains
    # by severity now claim a cell FIRST (Round 0), bypassing the theme cap, so they can't be dropped.
    # Default 1 chosen by the A/B (scripts/floor_ab): over 24 cached niches, floor=1 lifted #1-pain
    # coverage 22/24 -> 24/24 with ZERO diversity cost; floor 2/3 bought more top-2/3 coverage but cost
    # distinct themes. Set to 0 to disable. 0 = byte-identical to the legacy allocation.
    divergent_severity_floor_count: int = Field(
        default=1, ge=0, le=8,
        description=(
            "Guarantee the top-N pains by severity each get a generator cell (Round 0, before the "
            "diversity fill) so a high-severity, thin-affinity pain can't get zero ideation. 0 disables "
            "(legacy opportunity/theme/affinity allocation)."
        ),
    )
    divergent_target_pool: int = Field(
        default=15,
        ge=6,
        le=40,
        description=(
            "Target RAW concept-pool size driving the dynamic per-cell count: "
            "per_cell = clamp(round(divergent_target_pool / n_cells), 3, 4). Keeps the pool "
            "~stable (~12-16) regardless of how many cells the affinity graph yields, so the "
            "filter has headroom without exploding cost."
        )
    )
    # --- Diversity-aware final selection (keep more ideas, de-concentrate) ---
    enable_diversity_caps: bool = Field(
        default=True,
        description=(
            "Enable diversity-aware final selection: raise the final idea count toward "
            "diversity_max_final_ideas and enforce per-segment / per-mechanism / per-project-type "
            "caps (drop-only, floor-protected). Land dark; enable after the calibration run."
        )
    )
    enable_pain_source_dedup: bool = Field(
        default=True,
        description=(
            "Enable the (source_pain × data_source_tag) near-duplicate dedup in the divergent "
            "pool — collapses concepts solving the same pain from the same data source that the "
            "M/D/J structural gate misses (no-op in the legacy broad path where source_pain is None)."
        )
    )
    enable_addressability_ideation_gate: bool = Field(
        default=True,
        description=(
            "Exclude pains the scorer judged non-tool-addressable (tool_addressable == 'none': "
            "lifestyle/cultural/structural/governance, no software solution) from idea-generator "
            "cell selection, so they don't burn a generator slot. Reuses the existing scoring "
            "verdict (no extra LLM call). Floor-protected (keeps the full set if too few addressable "
            "pains remain to seed ideation). Excluded pains still appear in the report catalog. "
            "env: ENABLE_ADDRESSABILITY_IDEATION_GATE."
        )
    )
    diversity_max_final_ideas: int = Field(
        default=10,
        ge=3,
        le=15,
        description=(
            "Ceiling on the final idea set when enable_diversity_caps is on. The per-bucket caps "
            "make ~6-8 the practical landing; raise/lower to taste. Stay under RawConceptList.max_length (15)."
        )
    )
    diversity_min_final_ideas: int = Field(
        default=5,
        ge=2,
        description=(
            "Floor on the final idea set after diversity caps: re-admit the highest-composite "
            "dropped ideas (least-represented bucket first) until this many remain, so the caps "
            "never thin the set below a useful number."
        )
    )
    diversity_max_per_segment: int = Field(
        default=2, ge=1,
        description="Max final ideas per source_segment (de-concentrates the persona skew)."
    )
    diversity_max_per_mechanism: int = Field(
        default=2, ge=1,
        description="Max final ideas per mechanism family (greedy pairwise grouping of mechanism_tag)."
    )
    diversity_max_per_project_type: int = Field(
        default=3, ge=1,
        description=(
            "Max final ideas per project_type. Lenient default (3) keeps info-products first-class; "
            "set to 2 to force stronger project-type spread."
        )
    )
    divergent_max_workers: int = Field(
        default=8,
        ge=1,
        le=16,
        description=(
            "Max concurrent divergent generator threads in pain-partitioned mode (legacy "
            "broad path stays at min(n,4)). Raise with divergent_max_generators so the "
            "extra narrow agents actually run in parallel rather than serializing."
        )
    )
    divergent_partitioned_keep_fraction: float = Field(
        default=0.67,
        ge=0.0,
        le=1.0,
        description=(
            "Keep-fraction override for the pain-partitioned path (vs divergent_keep_"
            "fraction=0.5 for the broad path). Pain-separated narrow concepts are far less "
            "redundant by construction, so the 0.5 default over-discards them."
        )
    )
    divergent_pool_cap: int = Field(
        default=15,
        ge=6,
        le=15,
        description=(
            "Upper bound on concepts kept after pooling/dedup of the divergent samples, "
            "fed to the diversity filter. Hard-capped at 15 so the pooled RawConceptList "
            "never violates its max_length; floored at 6 (the RawConceptList minimum). "
            "The ACTUAL number kept scales with divergent_keep_fraction (see below) and "
            "is only capped here — this is the ceiling, not a fixed count."
        )
    )
    divergent_keep_fraction: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of the GENERATED divergent concepts to keep through the first "
            "dedup/clamp step (before the LLM diversity filter). Default 0.5 keeps at "
            "least half of what the samples produced, so good ideas aren't discarded "
            "before the filter sees them. The kept count is floored at 6 (so a small "
            "single-model pool isn't starved) and capped at divergent_pool_cap. Dedup "
            "may still leave fewer; duplicates are never re-added to hit this target."
        )
    )
    enable_feasibility_critic: bool = Field(
        default=True,
        description=(
            "Enable the merged novelty+feasibility critic (adds build_feasibility / "
            "data_feasibility / data_access_model + drop_names to the independent critic "
            "pass). Default OFF so it can land dark and be validated before it can drop "
            "or annotate concepts. When OFF the critic behaves as the novelty-only critic."
        )
    )
    enable_verdict_data_caps: bool = Field(
        default=False,
        description=(
            "Enable the downgrade-only verdict-boundary caps (technical_feasibility capped "
            "by the critic's build_feasibility; market_fit capped by the addressed pain's "
            "opportunity ceiling). Default OFF; flip on only after the rank-stability + "
            "calibration gates. Caps NEVER mutate stored scores — ranking is unaffected."
        )
    )
    feasibility_build_data_coupling_margin: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description=(
            "Critic feasibility coupling: build_feasibility_score may not exceed "
            "data_feasibility_score by more than this margin (you can't build on data you "
            "can't obtain). Kills the 'build 0.9 on phantom data 0.3' inflation."
        )
    )
    feasibility_restricted_data_cap: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description=(
            "Critic data-feasibility ceiling when the data source is 'restricted' (per-record "
            "lookup needing a pre-known key, login/CAPTCHA, or no nameable bulk route). Also "
            "the build-feasibility ceiling when build is scored but data was left unscored."
        )
    )
    # --- SEO-realism caps (downgrade-only, mirrors the feasibility caps) -------------------
    # Always on now (the enable_seo_realism_caps flag was removed). Downgrade-only caps on
    # seo_scalability_score (account-gated SaaS, thin/combinatorial page counts, hand-seeded
    # content) — NEVER raise a score or recompute the composite, so RANKING is unaffected.
    enable_seo_handseed_cap: bool = Field(
        default=False,
        description=(
            "Enable Rule C (hand-seeded / non-programmatic content cap) — a brittle substring "
            "heuristic on the free-text content_generation_model. Off by default so v1 ships the "
            "structured-field rules (A account-gating + B page counts) only."
        )
    )
    seo_cap_require_saas_for_gating: bool = Field(
        default=True,
        description=(
            "Rule A: require project_type=='saas' (not just data_access_model=='restricted') to "
            "apply the account-gating cap. True = precise/fewer false positives; False = cap any "
            "restricted-data idea."
        )
    )
    seo_cap_gated_saas_ceiling: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Rule A ceiling: account-gated SaaS (restricted data can't seed public indexable pages)."
    )
    seo_cap_thin_pages_threshold: int = Field(
        default=50, ge=0,
        description="Rule B lower band: estimated_indexable_pages below this is 'thin' (post-Stage-12 only)."
    )
    seo_cap_thin_pages_ceiling: float = Field(
        default=0.4, ge=0.0, le=1.0,
        description="Rule B ceiling for thin page counts (< seo_cap_thin_pages_threshold)."
    )
    seo_cap_high_score_min_pages: int = Field(
        default=300, ge=0,
        description="Rule B: minimum estimated_indexable_pages required to keep a score in the 0.8+ band."
    )
    seo_cap_moderate_pages_ceiling: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Rule B ceiling for moderate page counts (threshold <= pages < high_score_min_pages)."
    )
    seo_cap_handseed_ceiling: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Rule C ceiling: hand-seeded / non-programmatic content (only when enable_seo_handseed_cap)."
    )
    divergent_dedup_similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description=(
            "Cosine-similarity threshold for the embedding-based SEMANTIC dedup of pooled "
            "divergent concepts (over name + one_liner + why_non_obvious). Concepts at or "
            "above this are treated as near-duplicates and the most-novel is kept. Catches "
            "cross-model/cross-wording dups the name/tag dedup misses. 0.0 disables it; "
            "raise toward 0.90 for fewer merges, lower toward 0.80 for more."
        )
    )

    @property
    def brainstorm_pool_resolved(self) -> list[tuple[str, str | None]]:
        """Divergent pool as (model, reasoning_effort) pairs.

        Each brainstorm_llms entry may carry an inline '@<effort>'
        (e.g. '.../deepseek-v4-pro@none'); entries without one inherit
        brainstorm_reasoning_effort. Splitting on '@' is safe — model ids use '/'
        and ':' (e.g. ':free'), never '@'. Falls back to the single brainstorm_llm."""
        out: list[tuple[str, str | None]] = []
        for entry in self.brainstorm_llms.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if "@" in entry:
                model, _, eff = entry.rpartition("@")
                out.append((model.strip(), eff.strip() or self.brainstorm_reasoning_effort))
            else:
                out.append((entry, self.brainstorm_reasoning_effort))
        return out or [(self.brainstorm_llm, self.brainstorm_reasoning_effort)]

    @property
    def brainstorm_model_pool(self) -> list[str]:
        """Divergent-sample model pool (model ids only, '@effort' stripped). Falls
        back to the single brainstorm_llm when brainstorm_llms is unset."""
        return [m for m, _ in self.brainstorm_pool_resolved]
    # Ideation reasoning tiers — decouple the convergent steps from the expensive creative
    # model. `brainstorm_llm`/`brainstorm_reasoning_effort` still drive the CREATIVE tier
    # (divergent generation + ideator), the only place raw model capability sets idea
    # originality. The two tiers below cover the convergent steps:
    #   JUDGE  = novelty critic + concept evaluator/filter (scoring/classification — no
    #            creativity needed; safe on a cheaper reasoning mini).
    #   REFINE = final-idea refiner + single-concept (re-injected) refiner (structured
    #            enhancement; writes user-facing copy, so keeps the full model by default).
    ideation_judge_llm: str = Field(
        default="gpt-5.4-mini",
        description=(
            "Model for convergent JUDGE steps (novelty critic + concept evaluator/filter). "
            "A reasoning mini is enough — these are scoring/classification tasks, not creative "
            "generation. Cheaper than brainstorm_llm; must be a reasoning model so "
            "reasoning_effort is honored (gpt-5*/o-series)."
        )
    )
    ideation_judge_reasoning_effort: str = Field(
        default="low",
        description=(
            "Reasoning effort for the JUDGE tier (novelty critic + evaluator). 'low' default — "
            "objective scoring against fixed criteria. Bump toward 'medium' if obviousness "
            "discrimination degrades on the cheaper judge model."
        )
    )
    ideation_refine_llm: str = Field(
        default="gpt-5.2",
        description=(
            "Model for the REFINE tier (final solution refiner + single-concept/re-injected "
            "refiner). Defaults to the full brainstorm model because it writes the user-facing "
            "idea copy (innovation_angle, why_it_works, value prop); drop to a reasoning mini "
            "to cut cost once a run confirms the articulation quality holds."
        )
    )
    ideation_refine_reasoning_effort: str = Field(
        default="medium",
        description=(
            "Reasoning effort for the REFINE tier. 'medium' default — structured enhancement, "
            "not divergent ideation, so it doesn't need the creative tier's 'high'."
        )
    )
    ideation_mentor_llm: str = Field(
        default="gpt-5.4-mini",
        description=(
            "Model for the creative MENTOR in the idea-improvement loop (Stage 7, post-calibration) "
            "— the reviewer that guides weak ideas toward sharper, buildable, on-pain revisions. "
            "Must be a DIFFERENT family than the ideator (ideation_refine_llm) so it doesn't self-"
            "judge leniently. gpt-5.4-mini won a 6-model bake-off (validated +0.21/+0.97 vs baseline "
            "across two runs); re-tune via scripts/idea_improvement_ab.py --v4 --reviewer-model."
        )
    )
    ideation_mentor_reasoning_effort: str = Field(
        default="medium",
        description=(
            "Reasoning effort for the mentor/reviewer tier. 'medium' default — it judges three soft "
            "dimensions and proposes a creative direction, so it benefits from reasoning."
        )
    )

    # Realism score-calibration critic (Stage 7, post-refinement). An INDEPENDENT model that
    # re-scores market_fit / technical_feasibility / novelty / seo_scalability / obviousness from
    # the anchored bands + evidence and REPLACES the generator's optimistic self-scores. Dark by
    # default — flip on after the A/B (scripts/score_calibration_ab.py) shows calibrated scores
    # move toward a stronger reference judge (lower MAE-to-reference than raw).
    enable_score_calibration: bool = Field(
        default=True,
        description=(
            "Master switch for the realism score-calibration critic. When False the generated "
            "self-scores are used as-is. Enabled by default after the A/B "
            "(scripts/score_calibration_ab.py) confirmed calibrated scores move toward a stronger "
            "reference judge on all ranking criteria (overconfidence reduced, not just lowered)."
        )
    )
    enable_grounded_dev_time: bool = Field(
        default=True,
        description=(
            "Replace the refiner's throwaway dev-time point guess with a grounded estimate: a "
            "targeted web search for comparable build complexity + a decomposed, reason-first LLM "
            "judgment anchored to the build_feasibility score, returning an honest RANGE. Off => "
            "keep the generator's raw estimate."
        )
    )
    # Targeted novelty-enhancement pass (per-cell, after calibration). For a VALIDATED-but-OBVIOUS
    # idea (decent market_fit AND high obviousness), ask the ideator for a more differentiated
    # MECHANISM on the SAME pain + SAME data, re-score it, and KEEP the revision ONLY if novelty
    # rises without market_fit / feasibility regressing. Dark by default — prototype A/B (9 runs /
    # 3 niches) showed 0/8 worse, 0/8 drifted, 6/8 genuinely better (Opus-audited); flip on after a
    # live A/B. Gate keeps cost bounded (~half of ideas qualify; only gated ideas pay the 2 calls).
    enable_novelty_enhance: bool = Field(
        default=True,
        description=(
            "Master switch for the targeted novelty-enhancement pass. When True, a validated-but-"
            "obvious cell winner gets one ideator revision (more differentiated mechanism, same pain "
            "+ data); the revision is re-scored and kept ONLY if it strictly improves (novelty lift, "
            "no market_fit/feasibility regression). Accept-guarded so it can never worsen the set."
        )
    )
    novelty_enhance_min_market_fit: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Gate: only enhance ideas whose calibrated market_fit is at least this (validated demand).",
    )
    novelty_enhance_min_obviousness: float = Field(
        default=0.55, ge=0.0, le=1.0,
        description="Gate: only enhance ideas whose calibrated obviousness is at least this (an obvious solution).",
    )
    novelty_enhance_min_novelty_lift: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description=(
            "Accept: keep the revision only if novelty rises by at least this. 0.10 chosen by the "
            "prototype A/B — both reworded-only false-positives sat at the +0.05 floor; genuine wins "
            "were >=0.10."
        ),
    )
    novelty_enhance_regression_tol: float = Field(
        default=0.05, ge=0.0, le=1.0,
        description="Accept: reject the revision if market_fit OR technical_feasibility drops by more than this.",
    )
    novelty_enhance_skip_seo_floor: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Heuristic-fallback SEO floor: skip the enhance for a directory/aggregator/comparison idea with seo >= this (used only when winning_angle is unset).",
    )
    # Angle-aware idea evaluation (always on). An in-cell agent decides each cell winner's WINNING
    # ANGLE (distribution_seo / novel_differentiation / vertical_workflow), judges it on executing THAT
    # angle, and writes a user-facing comment so low off-axis scores (e.g. low mechanism-novelty for a
    # catalog) are explained rather than penalized. Steered by the per-run idea_focus control.
    idea_angle_llm: str = Field(
        default="openrouter/qwen/qwen3.7-max",
        description=(
            "Model for the in-cell angle classifier. An evidence-weighing judgment (argue the rival "
            "angle, reject it, commit), so it runs on the reasoning-ON path like the calibration critic. "
            "Defaults to the calibration judge model; the Stage-1 A/B may retune it independently."
        ),
    )
    idea_angle_reasoning_effort: str = Field(
        default="medium",
        description="Reasoning effort for the angle classifier (reasoning-ON path), mirroring the calibration critic.",
    )
    enable_pain_relevance_filter: bool = Field(
        default=True,
        description=(
            "Post-union: trim each idea's pain_points_addressed to the pains its MECHANISM actually "
            "addresses. The grounded matcher fills that field with EVERY validated pain affecting the "
            "idea's SEGMENT (good provenance, but it over-claims — e.g. a capsule-art tool listing "
            "'identify underserved genres'). A cheap LLM (function_calling_llm) drops the same-audience-"
            "but-unaddressed pains; the source pain is always kept. Fail-soft per idea → keep the full list."
        )
    )
    novelty_enhance_llm: str = Field(
        default="openrouter/deepseek/deepseek-v4-pro:nitro",
        description=(
            "Refiner model for the novelty-enhance pass (separate from the main ideator, "
            "ideation_refine_llm). Called reasoning-off + creative=True (tool transport). Default "
            "deepseek-v4-pro: in the A/B (refiner_multi.py, 3 niches) it was the quality winner — "
            "4/4 Opus-audited GENUINE accepts (vs glm-4.7 ~78%), highest novelty reach, often lifts "
            "feasibility, reaching for real ML/DSP techniques rather than rewording. Trade-off: "
            "slower than glm-4.7. Note: creative=True sidesteps deepseek's structured-output "
            "field-drop class (the reason it is NOT the main ideator)."
        )
    )
    score_calibration_llm: str = Field(
        default="openrouter/qwen/qwen3.7-max",
        description=(
            "Model for the realism calibration critic. Independent of the brainstorm pool (judge "
            "≠ generator). Must be a reasoning model so reasoning_effort is honored. Default chosen "
            "by A/B (scripts/score_calibration_ab.py vs a gpt-5.2 reference): qwen3.7-max gave the "
            "tightest calibration to the stronger judge on all 5 criteria (mean market_fit 0.53 ≈ "
            "ref 0.53) with no overcorrection — beating gpt-5.4-mini/deepseek-v4-pro (which overshot "
            "market_fit low) and glm-5.2 (equal quality, ~2.5x slower). Cheaper OpenRouter model."
        )
    )
    score_calibration_reasoning_effort: str = Field(
        default="medium",
        description=(
            "Reasoning effort for the calibration critic. 'medium' default — it must weigh "
            "evidence against the bands, a notch above the cheaper objective-scoring judge tier."
        )
    )
    score_calibration_samples: int = Field(
        default=1,
        ge=1,
        le=7,
        description=(
            "P2: N independent calibration-critic samples per batch, aggregated to the per-criterion "
            "MEDIAN before applying (the critic is non-deterministic even at temperature 0 with reasoning "
            "on — a single draw can flip a verdict). N=1 (default) is byte-identical to the single-call "
            "path (dark). N>1 trades ~Nx critic cost on the selected batch for variance reduction; choose "
            "N against a residual-variance target from scripts/calibration_gate.py stddev, validated AFTER "
            "the critic's bias (market_fit realism) is settled — medianing a biased critic just stabilizes "
            "the wrong center. env SCORE_CALIBRATION_SAMPLES."
        )
    )
    ideation_refine_max_tokens: int = Field(
        default=32768,
        ge=16384,
        description=(
            "Output token cap for the final solution-refinement task. It expands up to "
            "diversity_max_final_ideas full idea specs in ONE call, so the default 16384 backstop "
            "truncates the JSON once the kept set exceeds ~6 ideas. 32768 covers ~12 full specs."
        )
    )
    niche_context_llm: str = Field(
        default="openrouter/google/gemini-3.1-flash-lite",
        description=(
            "Model for the Stage-1 niche-context + audience-scope classifier (invoke_structured). "
            "FIRST-PARTY (Google) to match the openai_model_name workhorse: first-party vendors serve "
            "response_format from their own structured-output impl, skipping the open-weight vLLM/"
            "xgrammar guided-decoder that returned empty finish_reason=stop on qwen3-235b (Stage-1 "
            "crash). The invoke_structured escalating retry is the backstop. env: NICHE_CONTEXT_LLM."
        )
    )
    keyword_validation_llm: str = Field(
        default="gpt-5-nano",
        description="Model to use for keyword relevance validation in Phase 6c (gpt-5-nano at minimal reasoning effort for cost efficiency)"
    )
    pain_point_validation_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for pain point analysis/validation in Stage 6 (use non-reasoning model to allow max_tokens)"
    )
    enable_quote_grounding_gate: bool = Field(
        default=True,
        description=(
            "Deterministic grounding gate on Stage-3 quote enrichment: drop a displayed "
            "representative_quote when it is not a verbatim/fuzzy substring of its cited source "
            "post body (catches off-source/mis-attributed fragments the fail-open stance gate lets "
            "through). Floor-protected (never pushes a pain below the low-evidence floor) and "
            "fail-open when the source body is unknown. env: ENABLE_QUOTE_GROUNDING_GATE."
        )
    )
    quote_grounding_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description=(
            "SequenceMatcher ratio a quote must reach against a sliding window of its source post "
            "to count as grounded (0.9 tolerates the minor edits left by quote cleaning/splitting)."
        )
    )
    # --- Pain-scoring cutoffs (HEURISTIC PRIORS, not outcome-calibrated). These are round-number
    # decision boundaries on subjective LLM scores; there is no labeled outcome data to optimize them
    # against (would need shipped-idea revenue for a ROC/Youden fit). Exposed here so they can be tuned
    # without code edits and are not mistaken for settled/validated thresholds. ---
    opportunity_high_severity_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Severity at/above which an axis counts as 'high' in the opportunity formula. Heuristic prior, NOT outcome-calibrated."
    )
    opportunity_high_commercial_intent_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Commercial-intent at/above which an axis counts as 'high' in the opportunity formula. Heuristic prior, NOT outcome-calibrated."
    )
    low_evidence_severity_clamp: float = Field(
        default=0.45, ge=0.0, le=1.0,
        description="Severity is clamped DOWN to this when a pain has too few stance-verified quotes. Heuristic prior, NOT outcome-calibrated."
    )
    competitor_extraction_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for extracting product/brand/tool names from social discussion sentences"
    )
    report_structured_llm: str = Field(
        default="gpt-4.1-mini",
        description=(
            "Model for LIST-HEAVY report invoke_structured schemas (FeatureComparison, "
            "First30DaysPlaybook, MarketingNarrative, IdealCustomerProfile). gemini-2.5-"
            "flash-lite truncates ~25% on long list outputs; grok-4.3 is reliable + cheap. "
            "Single-object narratives stay on OPENAI_MODEL_NAME (gemini)."
        ),
    )
    pain_solution_mapping_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for pain-to-solution mapping in Stage 10 report generation (gpt-4.1-mini: non-reasoning, good instruction-following)"
    )
    landing_page_llm: str = Field(
        default="gpt-5.2",
        description="Model to use for landing page generation (gpt-5.2 recommended for high-quality creative output)"
    )
    # 3-tier reasoning effort for landing page agents
    landing_page_creative_reasoning_effort: str = Field(
        default="high",
        description="Reasoning effort for creative agents (Strategist, Creative Director, Visual Designer, Brand Designer, Copywriter). 'high' recommended."
    )
    landing_page_execution_reasoning_effort: str = Field(
        default="medium",
        description="Reasoning effort for code generation agents (HTML Developer, Animation Enhancer). 'medium' recommended."
    )
    landing_page_validation_reasoning_effort: str = Field(
        default="low",
        description="Reasoning effort for validation agents (QA Reviewer). 'low' recommended for structured validation tasks."
    )
    landing_page_execution_llm: str = Field(
        default="gpt-5.1-codex-max",
        description="Model for execution agents (HTML Developer, Animation Enhancer, QA Reviewer). Codex models recommended for reliable code generation."
    )

    # Moonshot AI (Kimi) Configuration
    moonshot_api_key: str | None = Field(
        default=None,
        description="Moonshot AI API key for Kimi models (get from platform.moonshot.ai)"
    )
    kimi_thinking: bool = Field(
        default=True,
        description="Enable Kimi thinking mode (deeper reasoning, temp=1.0). Default: False (instant mode, temp=0.6, faster and cheaper)."
    )

    # OpenRouter Configuration (optional alternative provider, per-tier)
    # Point any chat-completion tier at an 'openrouter/<vendor>/<model>' model to route it
    # through OpenRouter. OpenAI key stays required (embeddings + Codex have no OpenRouter path).
    openrouter_api_key: str | None = Field(
        default=None,
        description="OpenRouter API key for 'openrouter/*' models (get from openrouter.ai/keys)"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter OpenAI-compatible base URL"
    )
    openrouter_site_url: str | None = Field(
        default=None,
        description="Optional HTTP-Referer header for OpenRouter attribution/ranking"
    )
    openrouter_app_name: str | None = Field(
        default=None,
        description="Optional X-Title header for OpenRouter attribution/ranking"
    )
    openrouter_structured_providers: str = Field(
        default="",
        description=(
            "Comma-separated OpenRouter provider allowlist for the STRUCTURED-output SDK path "
            "(invoke_structured). Empty => no restriction (just require_parameters). When set, the "
            "structured request adds provider.only=[...] so tool/JSON calls route ONLY to these "
            "providers — used to dodge providers whose vLLM/SGLang parser drops tool calls (e.g. an "
            "open-weight model where 'works on deepinfra/baseten/parasail, fails on cerebras'). Keep "
            "2-3 known-good providers for failover; revisit if a tier flaps (the allowlist can drift "
            "as providers/parsers change). Provider slugs are MODEL-SPECIFIC — match your workhorse."
        )
    )

    openrouter_structured_mode: str = Field(
        default="tool_choice",
        description=(
            "Structured-output transport for the OpenRouter SDK path (invoke_structured): "
            "'tool_choice' (default) forces a function tool-call; 'json_schema' uses response_format "
            "json_schema (guided/constrained decoding). json_schema emits NO tool calls, so it sidesteps "
            "the open-weight vLLM tool-parser failure (qwen finish_reason=tool_calls/empty-args) AND the "
            "Gemini-3 thought_signature 400 — making cheap open-weight models (e.g. qwen3-235b @ deepinfra) "
            "reliable structured workhorses. Pair with OPENROUTER_STRUCTURED_PROVIDERS to pin a true "
            "guided-decoding provider; the schema is auto-shaped for xgrammar (no $ref/oneOf/bounds)."
        )
    )

    @property
    def openrouter_structured_providers_list(self) -> list[str]:
        return [p.strip() for p in self.openrouter_structured_providers.split(",") if p.strip()]

    audience_digest_token_budget: int = Field(
        default=24_000,
        description=(
            "Max tokens of scraped social content the Audience Mapping crew (Stage 6.5) injects "
            "in-prompt as the 'discussion digest' (replaces RAG). Kept conservative so the digest "
            "+ the large task prompt + output + reasoning fit a 32k-64k-context open-weight model; "
            "raise it for large-context models (Gemini 2.5). Token counting is approximate for "
            "non-OpenAI tokenizers, so a safety margin is applied."
        ),
    )

    # CrewAI+ (Enterprise) - Optional
    crewai_api_key: str | None = Field(default=None, description="CrewAI+ API key")

    # Serper.dev API
    serper_api_key: str = Field(..., description="Serper.dev API key for Google Search")

    # Reddit API (PRAW)
    reddit_client_id: str = Field(..., description="Reddit client ID")
    reddit_client_secret: str = Field(..., description="Reddit client secret")
    reddit_user_agent: str = Field(
        default="NicheIQ/0.1.0", description="Reddit user agent string"
    )

    # Twitter Configuration
    twitter_username: str | None = Field(default=None, description="Twitter username")
    twitter_password: str | None = Field(default=None, description="Twitter password")
    twitter_email: str | None = Field(default=None, description="Twitter email")
    twitter_cookies_cache: str = Field(
        default="data/twitter_cookies.json",
        description="Path to cache Twitter cookies (auto-created after first login)"
    )
    enable_twitter: bool = Field(
        default=False,
        description=(
            "Enable/disable Twitter/X data collection. Default False — Twitter is disabled/optional "
            "(matches .env, .env.example, and docker-compose.prod ENABLE_TWITTER:-false); the old True "
            "default contradicted every deployment path and would wrongly enable Twitter in a no-env run."
        )
    )
    enable_reddit: bool = Field(
        default=True,
        description="Enable/disable Reddit data collection (set to False to skip Reddit entirely)"
    )
    enable_hackernews: bool = Field(
        default=True,
        description="Enable/disable Hacker News data collection via Algolia API (free, no auth needed)"
    )
    enable_youtube: bool = Field(
        default=True,
        description="Enable/disable YouTube transcript collection (requires youtube-transcript-api)"
    )
    enable_seed_enrichment: bool = Field(
        default=True,
        description="Best-effort live-evidence enrichment (Hacker News) for catalog-seeded jobs; failures never block the job"
    )
    min_hn_points: int = Field(
        default=5, description="Minimum points for Hacker News stories"
    )
    min_hn_comments: int = Field(
        default=3, description="Minimum comments for Hacker News stories"
    )
    min_youtube_views: int = Field(
        default=0, description="Minimum views for YouTube videos (0 = accept all, Serper view parsing is ~40-60% reliable)"
    )
    youtube_api_key: str | None = Field(
        default=None,
        description="YouTube Data API v3 key (optional). Enables comment collection and accurate engagement metrics."
    )
    max_youtube_videos: int = Field(
        default=25,
        description="Maximum YouTube videos to collect per run (each costs 1 API quota unit for comments)."
    )
    max_youtube_comments_per_video: int = Field(
        default=20,
        description="Maximum top comments to fetch per YouTube video (by relevance)."
    )
    min_youtube_comment_likes: int = Field(
        default=5,
        description="Minimum likes for YouTube comments to be included (reduces noise)."
    )
    min_youtube_comment_length: int = Field(
        default=50,
        description="Minimum character length for YouTube comments to be included."
    )
    webshare_api_key: str | None = Field(
        default=None,
        description="Webshare API key. When set, YouTube transcript fetching routes "
                    "through direct-mode proxies fetched from /api/v2/proxy/list. "
                    "Get key from https://proxy2.webshare.io/userapi/keys."
    )
    webshare_proxy_country_codes: list[str] | None = Field(
        default=None,
        description="Optional ISO country code filter for the Webshare proxy pool "
                    "(e.g. 'US,GB' comma-separated, or JSON array). None = all countries."
    )

    # DataForSEO API
    dataforseo_login: str = Field(..., description="DataForSEO API login")
    dataforseo_password: str = Field(..., description="DataForSEO API password")

    # Application Settings
    log_level: str = Field(default="INFO", description="Logging level")
    max_retries: int = Field(default=3, description="Maximum retry attempts for API calls")
    timeout_seconds: int = Field(default=60, description="API request timeout in seconds (increased for large batches)")
    niche_description: str | None = Field(
        default=None, description="Niche/market area to research (optional, can be provided via CLI)"
    )

    # Search Configuration
    num_search_queries: int = Field(
        default=40, description="Number of search queries to generate for discovering pain points"
    )
    enable_audience_aware_research: bool = Field(
        default=True,
        description=(
            "Part C master gate. When True AND Stage-1 detected a focusable audience "
            "(audience_scope in {segment_of_niche, community}), search-query generation and "
            "pain mining get a SOFT, ADDITIVE audience bias — broad coverage is preserved, "
            "never narrowed. Default False (research stays fully broad; audience is output-only). "
            "env: ENABLE_AUDIENCE_AWARE_RESEARCH."
        )
    )
    audience_query_allotment: int = Field(
        default=6,
        description=(
            "Part C: extra Reddit search-query slots reserved for audience-flavored queries when "
            "audience-aware research is on. Added ON TOP of num_search_queries so the broad set is "
            "untouched (additive, not a filter). env: AUDIENCE_QUERY_ALLOTMENT."
        )
    )
    query_named_entity_cap: float = Field(
        default=0.4,
        description=(
            "Product-lock-in ceiling: at most this fraction of generated search queries may name a "
            "SPECIFIC product/entity (e.g. a peptide compound). Niche-identity terms (the niche's own "
            "name/games/market) do NOT count — only true product names beyond it. Excess named-entity "
            "queries are dropped so the search isn't pre-committed to the products Stage-1 happened to "
            "list. 1.0 disables. env: QUERY_NAMED_ENTITY_CAP."
        )
    )
    min_reddit_upvotes: int = Field(
        default=10, description="Minimum upvotes for Reddit posts (higher threshold for quality)"
    )
    min_reddit_comments: int = Field(
        default=5, description="Minimum comments for Reddit posts (higher threshold for quality)"
    )
    relevance_engagement_discount: float = Field(
        default=0.8,
        description=(
            "How much a high thread-relevance grade lowers the Reddit engagement bar (popularity-"
            "bias mitigation): per-post factor = 1 - discount*(grade-1)/2, applied to "
            "min_reddit_upvotes/comments. At 0.8: grade-3 ~= 2 upvotes/1 comment, grade-2 ~= 6/3, "
            "grade-1 = full 10/5. 0 disables (current behavior). env: RELEVANCE_ENGAGEMENT_DISCOUNT."
        ),
    )
    relevance_engagement_comment_floor: int = Field(
        default=1,
        description=(
            "Minimum comments a relevance-discounted Reddit post must still have — a thread needs "
            "SOME discussion to mine pain points, no matter how on-topic. env: RELEVANCE_ENGAGEMENT_COMMENT_FLOOR."
        ),
    )
    reddit_article_min_chars: int = Field(
        default=500,
        description=(
            "A Reddit post whose selftext is at least this many chars is treated as a self-contained "
            "ARTICLE/guide: it still must clear the (relevance-scaled) upvote bar, but the comment "
            "floor is WAIVED — a high-quality how-to/analysis carries its value in its own text, not "
            "the comments (a 0-comment link post still fails). env: REDDIT_ARTICLE_MIN_CHARS."
        ),
    )
    relevance_priority_weight: float = Field(
        default=0.5,
        description=(
            "Weight of thread-relevance in the pain-point token-budget priority score: "
            "score *= (1-w) + w*grade/3. grade-3 keeps full weight, grade-1 ~0.67. 0 disables. "
            "env: RELEVANCE_PRIORITY_WEIGHT."
        ),
    )
    reddit_comment_limit: int | None = Field(
        default=None,
        description="Max MoreComments to replace (None=all comments, 32=most comments, 0=top-level only)",
    )
    min_comment_length: int = Field(
        default=50,
        description="Minimum character length for Reddit comments (filters out short/low-value comments)"
    )
    min_comment_score: int = Field(
        default=2,
        description="Minimum score for Reddit comments (filters out low-quality/downvoted comments)"
    )
    max_reddit_content_tokens: int = Field(
        default=150_000,
        description="Maximum tokens for Reddit content in PainPointCrew (filters by engagement/recency)"
    )
    enable_comment_level_pain_content: bool = Field(
        default=True,
        description=(
            "Feed the pain-point finder COMMENT-level units (each thread's OP anchor + its best "
            "comments, selected by score × niche-relevance and round-robined across threads to fit "
            "the token budget) instead of whole comment trees from a few threads. Massively widens "
            "thread coverage within the same budget. Off ⇒ legacy whole-thread formatting + the "
            "post-level auto-reduction loop."
        )
    )
    pain_min_comment_chars: int = Field(
        default=80,
        description="Minimum comment length (chars) to be eligible as a comment-level evidence unit."
    )
    pain_op_snippet_chars: int = Field(
        default=1000,
        description="Max chars of a thread's OP selftext kept as the context anchor for its comments."
    )
    min_twitter_likes: int = Field(default=10, description="Minimum likes for Twitter posts (higher threshold for quality)")
    min_twitter_replies: int = Field(
        default=5, description="Minimum replies for Twitter posts (higher threshold for quality)"
    )

    # Keyword Research Configuration
    keyword_min_search_volume: int = Field(
        default=50, description="Minimum monthly search volume for keywords"
    )
    keyword_max_competition: float = Field(
        default=0.7, description="Maximum competition level (0-1)"
    )
    target_location: int | None = Field(
        default=None, description="Target location code (e.g., 2840 = United States). If None, API uses global data."
    )
    target_language: str | None = Field(
        default=None, description="Target language code (e.g., 'en'). If None, API uses default language."
    )
    keyword_relevance_threshold: float = Field(
        default=0.65,
        description="Minimum relevance score (0.0-1.0) for keyword validation in Phase 6c (never lowered)"
    )

    # SEO Refinement Settings (Stage 12)
    seo_refinement_enabled: bool = Field(
        default=True,
        description="Enable SEO score refinement based on keyword data from Stage 9"
    )
    seo_refinement_volume_baselines: dict = Field(
        default={
            'directory': 50_000,
            'aggregator': 50_000,
            'comparison-tool': 30_000,
            'marketplace': 30_000,
            'saas': 10_000
        },
        description="Baseline monthly volumes by project type for refinement calculations"
    )
    seo_refinement_max_volume_boost: float = Field(
        default=1.2,
        description="Maximum volume multiplier boost (default 1.2 = 20% boost)"
    )
    seo_refinement_max_tier1_boost: float = Field(
        default=0.20,
        description="Maximum Tier 1 keyword boost (default 0.20 = 20% boost)"
    )
    seo_refinement_volume_discount_floor: float = Field(
        default=0.7,
        description="Minimum volume discount for CAC calculations (default 0.7 = 30% max discount)"
    )
    seo_refinement_min_competition_modifier: float = Field(
        default=0.2, ge=0.0, le=1.0,
        description="Minimum competition modifier floor. Even highly competitive keywords allow some SEO value through long-tail variants."
    )
    seo_refinement_keyword_evidence_enabled: bool = Field(
        default=True,
        description="Enable keyword-evidence floor: when real keyword data shows SEO opportunity, prevent a false-zero LLM baseline from killing the score"
    )
    seo_refinement_max_keyword_evidence: float = Field(
        default=0.35, ge=0.0, le=1.0,
        description="Maximum keyword evidence floor. Rescue mechanism cap, not a replacement for LLM assessment."
    )

    # Keyword Enrichment Settings (Stage 6 Iterative)
    keyword_enrichment_target_count: int = Field(
        default=150,
        description="Target number of keywords with meaningful search volume"
    )
    keyword_enrichment_min_volume: int = Field(
        default=500,
        description="Minimum monthly search volume for a keyword to count toward target"
    )
    keyword_enrichment_max_rounds: int = Field(
        default=5,
        description="Maximum enrichment iterations to prevent runaway costs"
    )
    keyword_enrichment_batch_size: int = Field(
        default=12,
        description="Number of seeds per DataForSEO API call (reduced for better quality)"
    )
    keyword_cluster_min_coverage: float = Field(
        default=0.7,
        description=(
            "Minimum percentage of topic clusters that must have keywords (0.0-1.0). "
            "Renamed from keyword_enrichment_min_coverage: that name was defined TWICE "
            "with different meanings, and Python silently kept the later 0.30 enrichment "
            "threshold — so this 0.7 cluster threshold never actually applied. Restoring "
            "it may add enrichment rounds (more DataForSEO calls)."
        )
    )

    # Parallel Validation Settings
    validation_parallel_enabled: bool = Field(
        default=True,
        description="Enable parallel batch processing for validation tasks (keyword and thread validation)"
    )
    keyword_validation_max_workers: int = Field(
        default=3,
        description="Maximum parallel workers for keyword validation (Phase 6c). Recommended: 3-5 for balance of speed and API limits"
    )
    keyword_validation_batch_size: int = Field(
        default=50,
        description="Number of keywords per API call within each parallel worker (Phase 6c). Recommended: 50-150"
    )
    thread_validation_max_workers: int = Field(
        default=4,
        description="Maximum parallel workers for thread validation (Stage 5). Recommended: 3-5 for balanced throughput"
    )

    # Token Monitoring Configuration (Soft Caps for Cost Control)
    token_monitoring_enabled: bool = Field(
        default=True,
        description="Enable token counting and cost monitoring for LLM inputs"
    )
    token_warning_threshold: int = Field(
        default=200_000,
        description="Log warning when content exceeds this token count (for cost visibility)"
    )
    token_soft_cap_enabled: bool = Field(
        default=False,
        description="Enable soft cap enforcement (logs critical warning but doesn't fail)"
    )
    token_soft_cap: int = Field(
        default=400_000,
        description="Soft cap token limit - if enabled, logs critical warning when exceeded"
    )
    cost_logging_enabled: bool = Field(
        default=True,
        description="Log estimated API costs for token usage"
    )

    # Reddit Post Cache (PostgreSQL-backed)
    reddit_post_cache_enabled: bool = Field(
        default=True,
        description="Enable PostgreSQL-backed Reddit thread cache to avoid re-fetching posts via PRAW"
    )

    # Reddit Freshness Search Configuration
    reddit_freshness_search_enabled: bool = Field(
        default=True,
        description="Enable date-filtered Serper search pass for fresh Reddit posts"
    )
    reddit_freshness_tbs: str = Field(
        default="qdr:y",
        description="Google tbs (time-based search) param for freshness pass (qdr:d, qdr:m, qdr:y)"
    )
    reddit_freshness_query_fraction: float = Field(
        default=0.3,
        description="Fraction of queries to use for freshness Serper pass (0.0-1.0)"
    )

    # PRAW Native Search Configuration
    reddit_native_search_enabled: bool = Field(
        default=True,
        description="Enable PRAW native subreddit search for very recent posts"
    )
    reddit_native_search_time_filter: str = Field(
        default="month",
        description="PRAW time_filter for native search (hour, day, week, month, year, all)"
    )
    reddit_native_search_query_fraction: float = Field(
        default=0.25,
        description="Fraction of queries to use for PRAW native search (0.0-1.0)"
    )
    reddit_native_search_max_results: int = Field(
        default=10,
        description="Max results per query+subreddit combination in PRAW native search"
    )

    # Token Budget Freshness Reserve
    token_budget_freshness_reserve: float = Field(
        default=0.25,
        description="Fraction of token budget reserved for fresh posts (0 = disabled)"
    )
    token_budget_freshness_days: int = Field(
        default=180,
        description="Posts younger than this (days) are considered 'fresh' for token budget reserve"
    )

    # Solution Validation Configuration
    top_solutions_for_validation: int = Field(
        default=5,
        description=(
            "Number of top solutions to validate with pricing, keywords, and competitive "
            "analysis. Default 5 covers ALL refined solutions (3-5 generated) so novel "
            "ideas aren't structurally excluded from demand validation; batched keyword "
            "expansion keeps the API cost roughly flat vs the old top-3."
        )
    )

    # keyword validation: Keyword Validation Configuration
    keyword_validation_enabled: bool = Field(
        default=True,
        description="Enable keyword demand validation for top N solutions before final selection"
    )
    # NOTE: keyword_min_search_volume (used by validation too) is defined once
    # in the Keyword Research Configuration section above — it was previously
    # duplicated here with the same default, which Python silently collapsed.
    keyword_min_volume_threshold: int = Field(
        default=10,
        description="Minimum search volume threshold for relevance checking (lower than min_search_volume)"
    )
    keyword_pivot_max_attempts: int = Field(
        default=3,
        description=(
            "Maximum number of pivot attempts (different seed generation strategies) before "
            "accepting best result. Most successful validations land on attempts 1-2; "
            "3 keeps an adequate fallback at lower DataForSEO cost."
        )
    )
    keyword_quick_expansion_size: int = Field(
        default=50,
        description="Target number of keywords for quick expansion during relevance testing"
    )

    # Phase 6c: Keyword Enrichment Quality Gates
    keyword_enrichment_min_coverage: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Minimum coverage rate for keyword enrichment (validated/total). Default 0.30 = warn if <30% pass validation"
    )
    # SEO kill-question (Stage 6 deep research, distribution_seo ideas only). Deterministic thesis
    # stress-test computed from the already-validated keyword set (page ceiling, KD distribution,
    # winnable pages, penalty risk) + a small SERP sample. Dark by default; flip on after the A/B.
    enable_seo_kill_question: bool = Field(
        default=True,
        description=(
            "Run the deterministic SEO kill-question for a distribution_seo selected solution in Stage 6 "
            "(page-ceiling + KD distribution + forum-soft-SERP bonus + penalty-risk flag). On by default "
            "(A/B-validated 2026-06-30); set False to disable. Only fires for distribution_seo ideas."
        ),
    )
    enable_multisource_evidence_headline: bool = Field(
        default=True,
        description=(
            "EvidenceAppendix headline threads: when True, rank across Reddit + Hacker News + Twitter by "
            "normalized engagement (platform-fair) instead of Reddit-only by raw upvotes, with a per-source "
            "cap (<=60% of the 10 slots) so a small high-engagement platform can't sweep the headline. On by "
            "default (A/B-validated 2026-06-30: surfaces genuinely-high HN threads the Reddit-only path hid, "
            "cap keeps multi-source breadth). Set False for the legacy Reddit-only-by-score behavior."
        ),
    )
    enable_audience_conditioned_deep_research: bool = Field(
        default=True,
        description=(
            "Forward the Stage-1 resolved primary audience + its frustrations/current-tools into the "
            "POST-SELECTION deep research (competitor task + SEO seed generation), so the research targets "
            "the resolved audience. DISTINCT from enable_audience_aware_research (which only biases Phase-1 "
            "search/pain-mining). On by default (A/B-validated 2026-06-30: 4/4 distinct-audience checkpoints "
            "Opus-judged ON_BETTER after the directive reword that stops audience tools from displacing the "
            "solution's direct competitors; honesty preserved — never force-profiles irrelevant named tools)."
        ),
    )
    enable_seo_kill_question_floor: bool = Field(
        default=True,
        description=(
            "Ground an over-OPTIMISTIC distribution_seo Go/No-Go verdict in the SEO kill-question: when "
            "the page universe isn't winnable (winnable SHARE low / KD high), cap Go->Conditional + floor "
            "risk (downgrade-only). Keyed on the KD/winnability axis the SEO composite excludes (no "
            "double-count). KD-coverage-gated: abstains (fail-soft) when KD covers too little of the page "
            "universe to trust. On by default (A/B-validated 2026-06-30: 0/14 prior false-positives after "
            "the coverage gate + share threshold; 8/8 dense checkpoints correctly silent). Set False to disable."
        ),
    )
    enable_scoped_market_sizing: bool = Field(
        default=True,
        description=(
            "Scope market sizing to the SERVICEABLE slice the selected idea actually addresses: narrow the "
            "pain corpus to the idea's pain_points_addressed and prompt the LLM to size that slice (not the "
            "whole niche), with top-down keyword volume kept only as a labeled cross-check and a qualitative "
            "scope note instead of a fabricated bottom-up SAM. On by default (A/B-validated 2026-06-30: on a "
            "strong-contrast niche [2-3 of 29 pains] it consistently corrected an over-optimistic Strong/"
            "Aggressive verdict to Moderate/Measured — Opus-judged ON_BETTER — while a weak-contrast niche was "
            "a correct no-op; thin data — only one strong-contrast checkpoint was cached). Set False to disable."
        ),
    )
    seo_kill_question_serp_sample: int = Field(
        default=5, ge=0, le=15,
        description="Representative queries to SERP-sample for the SEO kill-question beatability read (0 = skip SERP).",
    )
    seo_kill_question_rankable_kd: float = Field(
        default=40.0, ge=0.0, le=100.0,
        description="KD below which a page is counted 'winnable' on a new (DA~0) domain for the kill-question.",
    )
    seo_kill_question_high_page_count: int = Field(
        default=500, ge=50,
        description="Page-universe size above which a tail-heavy (thin) set is flagged for scaled-content penalty risk.",
    )
    seo_kill_question_min_kd_sample: int = Field(
        default=30, ge=0,
        description="Below this many KD-scored intents, the kill-question display flags KD coverage as too sparse to judge winnability.",
    )
    seo_kill_question_min_kd_coverage: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Below this KD-coverage fraction (kd_sample_size / page_ceiling), the kill-question display flags winnability as indicative-only.",
    )
    # Angle-conditioned deep research: front-load the selected idea's winning-angle kill-question into the
    # Stage-2 crew prompts (SEO + competitor) so they investigate what actually validates/kills THAT angle.
    # The brief only ADDS the question — it never tells a crew to suppress off-angle critique; it explicitly
    # asks the crew to stress-test the angle and report true intensity. Off => the crews receive empty angle
    # vars => byte-identical to today. On by default (A/B-validated 2026-06-30); set False to disable.
    enable_angle_conditioned_research: bool = Field(
        default=True,
        description=(
            "Merge the per-idea angle brief (build_angle_brief) into the Stage-2 SEO + competitor crew "
            "prompts so each front-loads the winning angle's kill-question. Off => empty angle vars (no change)."
        ),
    )
    keyword_enrichment_target_coverage: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Target coverage rate for keyword enrichment. Default 0.60 = celebrate if ≥60% pass validation"
    )
    keyword_tiering_min_coverage: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Minimum tiering coverage (tiered_keywords/enriched_keywords). Warn if below this threshold"
    )

    # Tier difficulty gates (keywords above these thresholds get demoted to lower tiers)
    # These gates ensure "quick win" tiers only contain actually achievable keywords
    tier_0_max_difficulty: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Max keyword_difficulty for Tier 0 Premium keywords. Keywords with higher difficulty demoted to Tier 2."
    )
    tier_1_max_difficulty: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Max keyword_difficulty for Tier 1 Quick Win keywords. Keywords with higher difficulty demoted to Tier 2."
    )

    @field_validator('reddit_comment_limit', 'target_location', mode='before')
    @classmethod
    def parse_empty_string_as_none(cls, v):
        """Convert empty string to None for optional int fields."""
        if v == '':
            return None
        return v

    @field_validator('webshare_proxy_country_codes', mode='before')
    @classmethod
    def parse_country_codes(cls, v):
        """Accept comma-separated env string or JSON array; emit list[str] or None."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            return [c.strip().upper() for c in v.split(',') if c.strip()]
        return v

    @field_validator('keyword_enrichment_min_coverage', 'keyword_enrichment_target_coverage', 'keyword_tiering_min_coverage', 'keyword_cluster_min_coverage')
    @classmethod
    def validate_coverage_percentage(cls, v):
        """Validate coverage percentages are between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Coverage must be between 0.0 and 1.0")
        return v

    # Stage 10: Solution Refinement Configuration
    solution_refinement_enabled: bool = Field(
        default=True,
        description="Enable strategic refinement of selected solution based on keyword insights"
    )

    # Output Configuration
    output_dir: Path = Field(
        default=Path("./output"), description="Base output directory"
    )
    reports_dir: Path = Field(
        default=Path("./output/reports"), description="Reports output directory"
    )

    # Checkpoint Configuration
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable checkpoint/resume functionality to recover from failures"
    )
    checkpoint_dir: Path = Field(
        default=Path("./output/checkpoints"),
        description="Checkpoint storage directory"
    )
    checkpoint_max_age_days: int = Field(
        default=7,
        description="Maximum age of checkpoints before auto-cleanup (0 = disable cleanup)"
    )
    checkpoint_auto_cleanup: bool = Field(
        default=True,
        description="Automatically cleanup old checkpoints on startup"
    )

    # Report Generation Validation Thresholds
    # Market Validation Levels
    market_validation_strong_volume: int = Field(
        default=100_000,
        description="Minimum total search volume for STRONG market validation level"
    )
    market_validation_strong_pain_points: int = Field(
        default=10,
        description="Minimum pain point count for STRONG market validation level"
    )
    market_validation_moderate_volume: int = Field(
        default=30_000,
        description="Minimum total search volume for MODERATE market validation level"
    )
    market_validation_moderate_pain_points: int = Field(
        default=5,
        description="Minimum pain point count for MODERATE market validation level"
    )

    # Go/No-Go Verdict Thresholds
    verdict_go_avg_score: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        description="Minimum average score (all 4 scores) for Go verdict"
    )
    verdict_go_min_individual_score: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum individual score (market_fit, tech_feasibility) for Go verdict"
    )
    verdict_conditional_avg_score: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Minimum average score for Conditional verdict"
    )
    verdict_conditional_min_individual_score: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Minimum individual score for Conditional verdict"
    )
    enable_direction_aware_eval: bool = Field(
        default=False,
        description=(
            "P1: direction-aware evaluation. P1d (verdict): replace the uniform min(market_fit, "
            "tech_feasibility) hard gate with a LIFT-ONLY angle-binding gate "
            "max(min(mf, tech), min(mf, angle_binding_dim)) — binding dim = seo for distribution_seo, "
            "novelty for novel_differentiation, tech otherwise — so an SEO play is gated on SEO not tech, "
            "while a misclassification still passes via tech (never wrongly demotes). An INDEPENDENT tech "
            "buildability floor (tech >= verdict_conditional_min_individual_score) still blocks un-buildable "
            "ideas from Go. Dark pending the neutral-Opus-anchored A/B; env ENABLE_DIRECTION_AWARE_EVAL."
        ),
    )
    enable_llm_verdict_explanation: bool = Field(
        default=True,
        description=(
            "Explain the Go/No-Go verdict with an LLM instead of the deterministic band template. The "
            "LLM is given the ALREADY-DECIDED verdict + qualitative score bands + the winning angle + "
            "the firing rule / any downgrade, and writes 2-3 sentences of WHY it landed there. It never "
            "decides the verdict. The output is validated (must match the verdict's stance, no internal "
            "decimals) and falls back to the band template on any failure. On by default (A/B-validated "
            "2026-06-30: 10/10 band-accurate, no leaks); set False to use the deterministic template."
        ),
    )

    # STRIVE market-sizing pre-check
    strive_talked_about_min_mentions: int = Field(
        default=30,
        ge=0,
        description=(
            "Minimum corpus-wide unique discussions for the STRIVE 'Talked About' "
            "criterion. total_mentions is evidence-grounded (unique post IDs "
            "matched by quote vector search) instead of summed LLM estimates. "
            "Recalibrated 2026-06-11 from the golden run: a GOLD-tier corpus "
            "(123 relevant discussions, 910 comments) produced 44 corpus-unique "
            "mentions, so the old default of 50 — tuned to inflated LLM sums — "
            "failed strong data."
        )
    )

    # Pain Point & Competitive Thresholds
    pain_point_high_priority_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum severity score for high-priority pain point classification"
    )
    competitive_intensity_low_threshold: int = Field(
        default=3,
        description="Maximum competitor count for 'Low' competitive intensity classification"
    )
    competitive_intensity_high_threshold: int = Field(
        default=8,
        description="Minimum competitor count for 'High' competitive intensity classification"
    )

    # Report Formatting Thresholds
    report_max_quote_length: int = Field(
        default=200,
        gt=0,
        description="Maximum character length for pain point quotes in evidence appendix (0 = unlimited)"
    )

    # Score Accessor Defaults
    score_accessor_default_fallback: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default score value when score data is missing (used by ScoreAccessor)"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create output directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        if self.checkpoint_enabled:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
