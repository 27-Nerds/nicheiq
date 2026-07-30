# NicheIQ Architecture

Deep technical architecture documentation for developers and contributors.

## Table of Contents
- [Design Philosophy](#design-philosophy)
- [16-Stage Pipeline](#16-stage-pipeline)
- [Structured Output Strategy](#structured-output-strategy)
- [Data Passing Architecture](#data-passing-architecture)
- [Multi-Agent Design Patterns](#multi-agent-design-patterns)
- [Cost Optimization](#cost-optimization)

---

## Design Philosophy

### Hybrid Flow + Multi-Task Crews

NicheIQ uses a hybrid architecture combining CrewAI Flows (orchestration) with specialized multi-agent Crews (execution).

**Why This Pattern?**

1. **Flow for Orchestration**: Sequential stage management, state persistence, conditional logic
2. **Crews for Execution**: Parallel agent collaboration, task dependencies, knowledge sharing
3. **Best of Both**: Clean separation between "what to do" (Flow) and "how to do it" (Crews)

**Alternatives Considered**:
- Pure Flow (rejected: no multi-agent collaboration)
- Pure Crew (rejected: harder to manage complex pipelines)
- Separate scripts (rejected: no state management)

**Trade-offs**:
- ✅ Clear responsibility boundaries
- ✅ Easy to debug individual stages
- ✅ Flexible conditional execution
- ❌ More complex setup than single-pattern approach
- ❌ Need to manage state between Flow and Crews

---

## 16-Stage Pipeline

### Stage 1-4: Niche Validation (Flow Methods)

**Responsibility**: Validate niche has market potential

**Implementation**: Simple Flow methods (no agents needed)

**Data Flow**:
```
User Input → Niche Description
           → Market Segments Extraction
           → Industry Boundaries Definition
           → Project Types Selection
           → NicheContext Object
```

**Key Decision**: Why no agents here? Niche validation is deterministic string processing, doesn't need LLM reasoning.

---

### Stage 5: Search & Discover (Flow + Tools)

**Responsibility**: Collect social media discussions from multiple platforms

**Components**:
1. **QueryGenerator**: Creates search queries from niche context (platform-targeted)
2. **SerperDevTool**: Google search for Reddit/Twitter URLs
3. **TokenOverlapPrefilter**: Fast local relevance check (drops ~30% off-topic results before LLM)
4. **ThreadRelevanceValidator**: LLM-based relevance filtering for remaining URLs
5. **Reddit Tool (PRAW)**: Collects threads and comments → `RedditPost`
6. **Twitter Tool**: Collects tweets (optional, currently disabled) → `TwitterThread`
7. **Hacker News Tool (Algolia API)**: Candidate search → strict semantic relevance gate → comment collection → `SocialPost`
8. **Content Fencing**: Delimiter-based prompt injection defense on all scraped content
9. **Hybrid Dedup**: n-gram + token Jaccard cross-source deduplication

**Data Flow**:
```
NicheContext → QueryGenerator → Search Queries
            → SerperDev → Reddit/Twitter URLs
            → TokenOverlapPrefilter → Pre-filtered URLs
            → ThreadRelevanceValidator → Validated URLs
            → PRAW → RedditPost[]
            → HN Algolia candidates → ThreadRelevanceValidator (fail-closed) → SocialPost[] (generic)
            → Cross-source Dedup → SocialContentCollection
                                   ├── reddit_posts
                                   ├── twitter_threads
                                   └── generic_posts (HN, YouTube, etc.)
```

**Key Decisions**:
- Token-overlap pre-filter before LLM validation saves ~30% API costs
- HN uses Algolia API directly (free, no auth) — no Serper round-trip needed
- HN comment trees are fetched only after semantic grade ≥2; accepted `SocialPost` records persist the grade
- `SocialPost` generic model supports any future source (YouTube, Indie Hackers)
- Content fencing uses delimiter markers (not XML tags) to survive RAG chunking
- Per-source engagement normalization for cross-platform scoring
- Configurable comment depth (REDDIT_COMMENT_LIMIT)
- Source diversity: min 3 posts per platform in token budget

---

### Stage 6: Pain Point Analysis (PainPointCrew)

**Responsibility**: Extract and validate pain points from social discussions

**Agent**: Pain Point Analyst

**Task Flow**:
1. Extract pain points (with severity/WTP scoring)
2. Validate and deduplicate
3. **Coverage rebalance (one corrective re-extraction):** two grounded checks run after the first
   extraction — theme coverage (every non-Low theme has ≥1 pain) and **audience coverage** (an
   external critic, `utils/audience_coverage.py`, compares the extracted pains against the target
   audience and a sample of what the community actually discusses, flagging audience sub-groups the
   corpus contains but the extraction crowded out — e.g. spectators/collectors lost under a flood of
   player-rant pains). If either check finds a gap, ONE corrective Task-2 re-extraction runs with the
   gap directive folded in. The retry is **adopted only if it doesn't lose theme coverage AND improves
   theme- or audience-coverage** (original wins ties) — it can only help or no-op, never regress.

**Knowledge Sources Strategy**:
- **What**: 400+ social media posts/comments formatted as RAG chunks
- **Why**: Too large for direct prompt injection, need semantic search
- **Chunk Size**: 2000 chars (Reddit), 1500 chars (Twitter)
- **Chunk Overlap**: 300/200 chars for context preservation

**Output**: PainPointAnalysisResult with scored, validated pain points

---

### Seeded research flows (catalog pain / idea)

Catalog detail pages (`/pain-point/[slug]`, `/idea/[slug]`) and the saved-pains page can launch
research **seeded** from existing catalog data, skipping discovery stages. Three entry modes
(`Job.entryMode`), dispatched by Redis `task_type`; seeds travel in the payload (the worker has no DB):

| Mode (`entryMode`) | Trigger | Skips | Runs | Charge |
|---|---|---|---|---|
| `pain_research` (single) | pain page CTA (`painSlugs:[slug]`) | stages 1–4 | stage 5 → **awaiting-selection** → existing Phase 2 | `discovery` |
| `pain_remix` (2–5 pains) | saved-pains multi-select (2–5 slugs) | stages 1–4 | merged `pain_point_analysis` across pains → stage 5 → … | `discovery` |
| `deep_idea` | idea page CTA | stages 1–5 | Phase 2 (5.5 Competitive → 14) one-shot | `deep_research` |

**Mechanics:** the worker builds a minimal `ResearchState` (`flows/catalog_seed.py`), persists the
seeded artifacts as checkpoints, calls `_skip_stage(...)` for bypassed stages (emits SKIPPED
progress), sets `current_stage`, then runs `_execute_remaining_stages(...)` directly. Catalog text is
sanitized (injection patterns stripped via `_sanitize_social_content`); the Stage-2/3 delimiter
fencing is not applied — it belongs to raw-social-content ingestion, which seeded runs skip, and
Stage 5 consumes the same unfenced structured shapes in the normal pipeline.

**Quality passes (`flows/seed_enrichment.py`, both best-effort):** remix jobs (>1 pain) get an
LLM-synthesized cross-niche `niche_context` (one structured call; the deterministic template from
`catalog_seed.py` is the fallback on any failure). All seeded modes then run a targeted Hacker News
evidence pass (permanent): pain/idea-derived queries → the shared fail-closed HN semantic gate
(grade ≥2) → dedup → if ≥3 posts survive, `state.social_content` is set and checkpointed as
`stage_2_social_content` (so Phase-2 resume keeps it, the stage-11 trend crew gets real data
instead of its "Risky" missing-data fallback, and the report's evidence appendix has sources).
Fewer than 3 posts → nothing is persisted (the checkpoint loader's quality gate would discard a
thinner collection and reset the resume stage). Note: stage 2 still reads SKIPPED in job progress —
enrichment is an internal pass, not a stage run. Reports without a fresh full social scrape →
`FinalReport.seeded_from_catalog=True` (persisted through the Phase-2 checkpoint), surfaced as a
"seeded from catalog" badge. Idea runs also bump `CatalogIdea.researchCount` (distinct users).

**Telemetry (no events table):** adoption is queryable from `Job.entryMode`
(`pain_research`/`deep_idea`) and `CatalogIdeaResearch` rows; endpoints also emit structured
`console.log` events (`{event, userId, jobId, …}`).

---

### Stages 7-8.75: Solution Pipeline (UnifiedSolutionCrew)

**Responsibility**: Generate, analyze, and select SaaS solutions

**4-Task Sequential Pipeline**:

1. **Solution Ideation**: Brainstorm 3-5 solution concepts
2. **Competitive Analysis**: Research existing competitors
3. **Competitive Refinement**: Enhance solutions with competitive insights
4. **Solution Selection**: Score and select best solution

**Context Chaining Pattern**:
```python
@task
def task_1_ideation(self) -> Task:
    return Task(
        output_pydantic=IdeaGenerationResult,
        # ...
    )

@task
def task_2_competitive(self) -> Task:
    return Task(
        context=[self.task_1_ideation()],  # Auto-passes Pydantic object
        output_pydantic=CompetitiveAnalysisResult,
        # ...
    )
```

**Benefits**: Automatic field preservation, no manual JSON formatting, type safety

**Guardrails**: Validation functions prevent field loss during refinement

#### Novelty and obviousness pipeline (Stage 7 ideation internals)

Ideation does **not** run a single brainstorm task. To fight mode collapse on reasoning
models (where temperature is inert and prompt technique is the only diversity lever), the
crew generates concepts through a novelty/obviousness pipeline before the convergent
filter/refine/select tasks above:

1. **N independent divergent samples** (`num_divergent_samples`, default 2) — each runs the
   ideator under a different *orthogonal lens* (`_DIVERGENT_LENSES`: e.g. power-user gap,
   structural inversion + cross-domain transfer). The lenses are **domain-neutral** so the
   system works for any niche. Each sample is an independent LLM call (no shared context),
   so the samples can't collapse onto one another.
2. **Independent novelty critic** (`_score_pool_novelty`) — scores every concept's
   `obviousness_score` (0-1, **lower = more original** = the fraction of competent builders
   who'd also propose it) and **drops ideas that already exist** as shipping products. This
   critic's score *overwrites* the ideator's own obviousness estimate — it is the system's
   independent obviousness signal. This SAME pass also
   scores **build feasibility** + **data feasibility** (`data_access_model`: public/freemium/
   paywalled/unofficial/restricted/blocked/unverified), keeping ToS-gray-but-obtainable (`unofficial`) ideas and
   dropping only genuine no-route ones. The data fields are surfaced and, post-selection,
   reconciled against Stage-13's verified findings (estimate→verified). (The build-feasibility
   verdict cap, `enable_verdict_data_caps`, was removed 2026-07-07 — never validated.)
3. **Pool + dedup** (`_pool_and_dedup_raw_concepts`) across all samples, capped at
   `divergent_pool_cap` (default 12). Falls back to a single divergent sample if the pool
   comes back too small.
4. **Per-cell ideator↔judge tournaments** (DEFAULT, `enable_per_cell_tournament`). Instead of
   pooling everything into one convergent-refine crew, each `(pain × segment)` cell runs its OWN
   tournament IN PARALLEL: pre-rank the cell's concepts → expand the best into a full idea
   (`_refine_single_concept`) → `tournament_refine_cell_v4` converges it through the ideator↔mentor
   loop (below) → ONE best per cell. The union of per-cell winners (deduped only — no diversity
   caps) is shown, so every cell's pain is structurally covered (one idea each). Provenance
   (`source_pain`/segment + M/D/J tags + critic feasibility) is stamped by cell identity, not a
   name-join. Cost ~2.5–3× the pooled flow; won the blind A/B on top-pain coverage. The legacy
   **pooled convergent refine → (select)** path (refiner consumes `{pooled_concepts}`) remains as
   the fallback when there are no partition cells. Each cell emits a FULLY-SCORED idea: the
   realism re-score critic (`_calibrate_idea_scores`) and the closed-vocab tagger (`_apply_tags`)
   run per-cell in the cell's thread, alongside the deterministic feasibility + SEO-realism caps —
   so the post-union passes (step 5) only finish the few coverage-net stragglers.
   **Portfolio funnel (2026-07-02, all stages A/B-validated then made unconditional).** Post-
   tournament stages widen and strengthen the pool (each idea carries an `idea_tier`:
   `single` | `salvaged` | `bundle`):
   - **Salvage gate**: the in-cell judge picks 1 of 3-4 concepts BEFORE the calibration critic
     runs, discarding ~66% of paid generation unexamined. The gate gives the full critic one
     batch over the unclaimed losers (structural duplicates of a renamed winner are excluded)
     and promotes any scoring `>= max(0.55, own-cell winner − 0.05)` — cap `salvage_max_promoted`,
     at most 2 rescues per source pain; promoted losers get the same full expansion as winners
     and join the pool as `idea_tier='salvaged'`.
   - **Synthesis bundles**: one call composes 3-5 complementary validated pains (and the cell
     winners) into 1-2 BUNDLED products around a single user workflow — the shape buyers actually
     pay for, which one-pain-per-cell ideation structurally never produces. Additive
     (`idea_tier='bundle'`); singles remain as alternatives.
   - **Data-menu briefs**: a per-niche VERIFIED data-route menu (official/public registries,
     licensed APIs, deterministic user-input arithmetic) built once and injected into every cell
     ideator brief AND the critic's context — mechanisms start from data reality instead of dying
     on unverifiable routes (the dominant idea-killer). An **incumbent probe** similarly augments
     the community competitor-mentions block with a web-searched map of real paid products, their
     pricing, and gaps.
   - **Mechanism-parity probe** (post-calibration): web-verifies whether an incumbent already
     SHIPS each idea's core mechanism (targeted Serper queries against the probed incumbents + one
     extraction), then re-scores ALL ideas (batched) with the parity evidence in critic context and
     stamps `incumbent_parity` on each (rendered in the report's honest brief). Probe-all since
     2026-07-06 (was top-K): a second evidence-informed pass for some ideas but not others polluted
     the relative ranking. After the re-score the downgrade-only caps are re-asserted and the
     classifier outputs (`winning_angle` + rationales) cleared, so the post-union angle pass
     re-derives every idea's rationale against the FINAL capped scores — no stale score citations.
     Evidence-in-context only — the critic decides what parity means; no hard caps ('none found'
     is absence of evidence, never a score lift). Parity levels (2026-07-06): shipped / partial /
     **substitute** (free/DIY route — free official data, spreadsheet, manual workflow — already
     delivers the outcome) / none. An **adjacent-market probe** additionally groups ideas into
     mechanism families (`mechanism_tag` + `data_source_tag`), reformulates each family into
     audience-independent commercial categories (one cheap LLM call), searches those, and stamps
     `adjacent_market_parity` (name-verified against snippets; hallucinated incumbents dropped) —
     catching incumbents the idea's own audience framing hides (govcon intel behind a
     "failed-RFP digest for founders"). A **coverage tripwire** appends a quality caveat when
     ≥80% of ideas come back "none found" with no adjacent coverage. Substitute + adjacent
     evidence also feeds the recal critic (permanent since the 2026-07-06 gate replay; display always on).
   - **Segment payability** (permanent since the 2026-07-06 gate pass; prompt-side application
     removed in the 2026-07-30 de-dup): one batched LLM call scores each
     Stage-4 segment's wallet (budget sensitivity + incumbent pricing + pain commercial-intent
     evidence, blended with deterministic class priors); ideas inherit it via `source_segment`
     (niche-mean fallback keeps coverage uniform). The calibration critic scores
     payability-BLIND; the wallet reaches market_fit through exactly one path —
     cap (d) holds market_fit ≤ 0.55 below the low threshold, and a Phase-5 verdict floor
     holds direct-paid Go verdicts to Conditional. The niche-level **buyer_class** ("who pays
     here") rides the niche-difficulty narrative call and is always on.
   - **Generation lenses (permanent, 2026-07-10):** each run allocates its cell budget across FOUR
     generation lenses plus bundles, not pain-point cells alone. **Pain-point** (primary,
     unchanged) still supplies one cell per `(pain × segment)` with the severity + commercial-
     evidence floors above, and keeps reserve priority — floors are always covered first, before
     the other lenses draw from the remaining budget. Three additional single-cell lenses seed
     from evidence the pipeline has already verified elsewhere in the run rather than re-deriving
     it: **competitor-gap** (one cell from the incumbent probe's per-tool gap findings +
     dissatisfaction quotes), **data-asset** (one cell from the verified public-data menu — what
     dataset could be assembled and who pays for what it reveals — with a publication-cadence
     check that marks a product unbuildable if it needs data fresher than the source publishes),
     and **workflow** (one cell from a synthesized job-map: pains + motivation drivers + tool
     frustrations, JTBD-framed). Bundles remain the cross-pain synthesis peer, unaffected. Every
     lens idea passes the IDENTICAL scoring/validation gauntlet as pain ideas (feasibility, route
     verification, payability, parity probes, calibration critic, caps) and must anchor to a
     validated pain or the cell is dropped. Frame provenance is stamped as `source_frame` and
     surfaced in the UI as a "generation lens" chip on each idea. An 8-run A/B (2026-07) validated
     the set: `data_asset` produced a run-winning idea (0.75 market fit, duplicate-grant-expense
     detection for nonprofit bookkeepers) and the only two accepted variant-merges; `gap`
     delivered consistent mid-table survivors; `workflow` is high-variance but its wins justify
     the slot since the demotion machinery honestly retires its failures. A fifth lens
     (spend-adjacent) was tested and dropped as redundant — its wallet/toolbelt signals already
     feed every lens via the market-reality context.
   The calibration critic itself samples **N=3 per batch, per-criterion median**
   (`score_calibration_samples`; single draws carry ~0.03-0.05 stddev — gate-validated vs the
   67-idea neutral-Opus panel: κ 0.19→0.256).
   An **in-cell angle classifier** (`idea_angle_llm`, default qwen3.7-max) also runs here — after
   calibration, before the novelty enhance — assigning each cell winner a `winning_angle`
   (`distribution_seo` / `novel_differentiation` / `vertical_workflow`) with an `angle_rationale`
   and a `novelty_rationale`; the union ranks each idea by its OWN angle's weights (distribution
   upweights SEO + market_fit with a small non-zero novelty weight; novel upweights novelty;
   workflow upweights feasibility). A post-union **angle pass** re-classifies the FULL set after
   the parity re-score (the probe clears every idea's classifier outputs), so all shipped angles +
   rationales are derived against final scores; the in-cell labels only route the novelty enhance.
   The per-run **`idea_focus`** steer (`auto | novelty | distribution`, default `auto`) pulls
   three levers at once: it skews generation toward the chosen angle, biases winner-pick, and
   tilts the ranking emphasis. The UI labels the stable `novelty` value **Differentiation**;
   `auto` leaves the classifier unbiased and every `winning_angle` label stays truthful regardless
   of the steer.
   Optionally (after calibrate+caps, before SEO/tags) a **targeted
   novelty pass** (`_novelty_enhance`) fires on VALIDATED-but-OBVIOUS winners (market_fit ≥ gate AND
   obviousness ≥ gate): the refiner (`novelty_enhance_llm`, default deepseek-v4-pro) proposes a more
   differentiated MECHANISM on the SAME pain + data, the revision is re-scored, and it is KEPT only
   if novelty rises ≥ the lift threshold with no market_fit/feasibility regression — accept-guarded,
   so it can never worsen the set (A/B: 0 worse / 0 drifted across 3 niches).
5. **Deterministic coverage re-injection** — after refinement, code (not the LLM) guarantees
   pain-point coverage: a high-severity pain the diversity filter dropped is re-injected as the
   best-covering divergent concept, fully refined via `_refine_single_concept` (not a stub) so it
   carries the same fields and scores as the rest. The idempotent post-union scorers then finish
   any such re-injected idea (the in-cell winners are skipped, already scored). SEO-realism caps
   are always on (the `enable_seo_realism_caps` flag was removed), still applied on the
   `skip_selection` live/preview path and deferred to Stage 12 on the legacy one-shot path.
6. **The per-cell ideator↔mentor loop** (`tournament_refine_cell_v4`, run inside step 4) — each
   cell's idea is refined through a short ideator↔reviewer dialog where the reviewer is a *creative
   mentor* (a **different model than the ideator** so it doesn't self-judge: ideator glm-4.7,
   reviewer `deepseek-v4-pro@none` — won a blind Opus A/B over gpt-5.4-mini across 3 niches at
   ~2.5× lower cost) that pushes for a sharper, more original, on-pain idea and forbids
   scope-inflation. The loop scores only the soft dimensions; the ideator flags any uncertain data
   route as `[NEEDS-VERIFY: …]` instead of asserting an API, and a **separate web-search
   verification step** (a SAFE / Chain-of-Verification check) resolves each route THREE ways from
   the search evidence and sets `data_access_model`: **supported** → a real public/official source
   (no penalty); **refuted** → removed / gated / paywalled / nonexistent (`market_fit` capped); or
   **not-enough-info** → `unverified`, left UNCAPPED but flagged "verify before building". The rule
   is symmetric and evidence-only (no model belief): crediting needs evidence of access, blocking
   needs evidence of NON-access, and thin/silent search abstains — so the model never confabulates
   an API the loop rewards, nor blocks a real one the search merely missed. Capped at
   `tournament_rounds` (default 2). (The legacy late per-idea `_run_improvement_loop`
   was removed — the per-cell tournament IS this loop, run once per cell.)
7. **Deterministic score backstop** (`_validate_idea_scores`) — downgrade-only invariants the
   LLM doesn't reliably hold: `novelty ≤ 1 − obviousness`, and `market_fit ≤ 0.4` when the data
   route is unverified/unbuildable. Never inflates.

`obviousness_score` is surfaced in the UI as **Distinctiveness**
(= `1 − obviousness_score`, falling back to `novelty_score` for legacy records).
`novelty_score` remains the separate calibrated ranking signal and drives both the composite
score and the stored `innovator` strength key, displayed as **Distinct mechanism**. The visible
Distinctiveness value does not directly determine either one when `obviousness_score` exists.

**Research Reality Check** (end of Phase 1, `utils/niche_difficulty.py`). Right after idea
generation + audience-fit tagging, a deterministic classifier scores how well software can
actually solve the niche — `software_addressability` (from pain-point `tool_addressable`
shares) plus a `difficulty_level` band — using only already-computed signals (novelty +
raw→calibrated gap, project-type concentration, cold-start data dependency, audience fit).
A grounded best-effort LLM pass writes the candid prose (deterministic templated fallback if
it fails). The verdict is stored once on `state.niche_difficulty_verdict` and read by both the
Phase-1 preview materializer (discovery screen) and the full report — no double generation.
Same "code judges, LLM narrates" split as the score backstop above.

---

### Stage 9: SEO Strategy (SEOStrategyCrew)

**Responsibility**: Keyword research and SEO planning

**5-Task Sequential Pipeline**:

**Phase 6a-c** (Flow-managed):
- 9.5a: Generate 40-50 seed keywords (LLM)
- 9.5b: Bulk validate with DataForSEO API
- 9.5c: Expand and enrich (DataForSEO → 150+ keywords)

**Tasks 1-5** (Crew-managed):
1. Keyword Analysis & Tiering
2. Content & Technical Strategy
3. Implementation Planning
4. Final SEO Strategy Synthesis
5. Implementation Guide (templates, schema)

**CSV Input Strategy**:
- Keywords passed as CSV (not JSON or RAG)
- 2x more token-efficient than JSON
- Complete visibility (all 150 keywords in prompt)
- Industry best practice for structured tabular data

**When to use CSV vs RAG**:
- CSV: Structured metrics (keywords, pricing), moderate size (150-500 items)
- RAG: Unstructured narrative (pain points), large size (400+ items)

---

### Stage 10.5: Technical Blueprint (TechnicalBlueprintCrew)

**Responsibility**: Generate personalized site structure and user flows

**2-Task Sequential Pipeline**:

1. **Site Structure Task**: Design site architecture with pages, URLs, and MVP priorities
2. **User Flows Task**: Create user journey maps for target personas

**Agents**:
- **Product Architect**: Designs SEO-optimized site structure
- **UX Designer**: Maps user journeys from discovery to conversion

**Input Data**:
```python
crew.generate(
    solution_name="LLM Cost Calculator",
    description="Compare AI model pricing...",
    project_type="directory",
    core_features=["Price comparison", "Usage calculator"],
    target_personas=["Cost-conscious developer", "Startup CTO"],
    data_sources=["Provider APIs", "Public pricing pages"],
    estimated_indexable_pages=500,
    content_generation_model="Programmatic from API data",
    value_proposition="Save money on AI costs",
    organic_discovery_queries=["gpt-4 pricing", "claude vs gpt cost"],
    pricing_strategy="Freemium with premium alerts",
)
```

**Output**:
- `SiteStructure`: sections, pages, URL patterns, page counts, tech stack recommendation
- `UserFlowsSection`: persona-based flows with steps, entry points, conversion points

**Key Decisions**:
- Sequential tasks: User flows reference pages from site structure
- Anti-hallucination prompts: Only use features/personas from solution
- Priority framework: P0 (MVP), P1 (soon), P2 (later)

---

### Stage 10: Report Generation (Hybrid Python + LLM)

**Responsibility**: Assemble final research report

**Hybrid Approach**:

1. **Python Data Assembly** (80% of fields):
   - Direct copies from state
   - Template-based sections
   - Programmatic calculations

2. **LLM Enhancement** (20% - 3 fields only):
   - executive_summary
   - acquisition_strategy_summary
   - next_steps

3. **Python Enhanced Sections**:
   - Research metadata
   - Competitive landscape matrix
   - Evidence appendix
   - Data infrastructure roadmap

**Why Hybrid?**
- **Cost**: 85% reduction ($0.10-0.30 → $0.02-0.05)
- **Speed**: 5x faster (10s → 2s)
- **Quality**: Zero hallucination on data fields
- **Reliability**: Python fallback always succeeds

**Alternative Rejected**: Pure LLM generation (245-line prompt, high cost, slow, hallucination risk)

#### Post-selection deep-research refinements

Stages 6–10 run *after* a single idea is selected, so they're tuned to pressure-test that one
idea rather than survey the niche. Several refinements gate this behavior (see
`docs/DEEP_RESEARCH_IMPROVEMENT_PLAN.md` and `docs/ENV_REFERENCE.md`):

The Phase-1 → Phase-2 handoff is an exact, versioned operation rather than a display-name join.
The browser submits a request ID, saved-draft version, ordered shortlist fingerprint, and the
price it confirmed. The backend reloads the owner's saved draft, resolves each
`(idea_id, idea_revision)` against the current preview report, and computes the authoritative
selection snapshots and worker payload. It then atomically records the charge, dispatch, and
private outbox payload before delivery to Redis. Retries reuse the same job-scoped request ID;
queued cancellation reverses the exact originating charge and records the refund linkage.

The worker validates the ordered exact references and their narrow canonical fingerprint before
resuming the checkpoint. Legacy jobs may fall back to unique normalized names, but new dispatches
carry exact references. Report-ready and final callbacks include the dispatch identity, and the
selected result returns an exact `winner_ref`; stale callbacks cannot settle a newer operation.

- **Angle-conditioned research** (permanent): the selected idea's `winning_angle` kill-question is
  front-loaded into the SEO + competitor prompts so they investigate what would validate or kill
  *that* angle.
- **Audience-conditioned deep research** (permanent): forwards the Stage-1 resolved audience
  (tools used / frustrations) into the competitor prompt and SEO seed vocabulary, so the analysis
  judges against the real buyer.
- **SEO kill-question verdict floor** (permanent): tempers an over-optimistic distribution_seo Go
  when the page universe isn't winnable — keyed on the winnability/KD axis the SEO composite
  excludes, so no double-count.
- **Scoped market sizing** (permanent): sizes the serviceable slice the
  idea's `pain_points_addressed` represent, not the whole niche; keyword volume is a labeled
  cross-check and the SAM stays qualitative (no fabricated bottom-up number).
- The Go/No-Go verdict averages **lift-only** by angle and its explanation uses score *bands*, never
  raw decimals — consistent across all post-selection prose.

---

## Structured Output Strategy

### LLM Structured Output Pattern

**Problem**: CrewAI's LLM wrapper doesn't support `response_format` parameter for structured output.

**Solution**: Use LangChain directly for Pydantic-constrained generation:

```python
from langchain_openai import ChatOpenAI

structured_llm = ChatOpenAI(
    model=settings.openai_model_name,
    temperature=0.7,
    api_key=settings.openai_api_key
).with_structured_output(YourPydanticModel)

result = structured_llm.invoke(prompt)
```

**When to Use**:
- Generating structured data outside of CrewAI tasks
- Need guaranteed Pydantic compliance
- Report generation LLM enhancement

**When NOT to Use**:
- CrewAI tasks (use `output_pydantic` parameter instead)
- Simple string outputs
- Tool calling scenarios

---

## Validation Strategy

### Philosophy

**Core Principle**: Trust the LLM for style, validate only for data integrity.

This approach eliminates ~85% of false validation failures by focusing on what matters: data correctness, not stylistic preferences.

### Validation Boundaries

| Layer | Validates | Examples |
|-------|-----------|----------|
| **Data Generation (Stages 1-9)** | Data quality, completeness, schemas | Keyword volume > 50, score 0.0-1.0 |
| **Report Generation (Stage 10)** | Data integrity, cross-stage consistency | Referenced scores exist, no null refs |

### What We Validate

✅ **Data integrity**: Score references in verdicts, no hallucinated metrics
✅ **Schema compliance**: Pydantic handles automatically
✅ **Safety checks**: None/NaN validation, division by zero

### What We DON'T Validate

❌ **Style preferences**: Word counts, sentence counts (trust the prompt)
❌ **Vocabulary whitelists**: LLM understands "active voice" without enforcement
❌ **Arbitrary limits**: Character counts, feature splits (no business value)

### Key Validations

**Location**: `src/nicheiq/report/report_generator.py`

1. **Executive narrative** (see `_validate_executive_narrative()` method)
   - Verdict must reference actual scores (prevents hallucinations)
   - Uses word-boundary regex to prevent false positives (e.g., "score" in "underscore")

2. **None/NaN checks** (see sanity checks in `_generate_base_report()`)
   - Scores validated before calculations (prevents crashes)
   - Logs warnings when using default fallbacks

3. **Score fallbacks** (see `src/nicheiq/report/utils/score_accessor.py`)
   - Logged when using defaults (data quality visibility)
   - Default: 0.5 (configurable via `SCORE_ACCESSOR_DEFAULT_FALLBACK`)

### Configuration

**Location**: `src/nicheiq/config/settings.py:308-382`

All validation thresholds are:
- Centralized in Settings class
- Configurable via environment variables
- Type-safe with Pydantic validation (ge/le constraints)
- Self-documenting with Field descriptions

**Example - Configuring Verdict Thresholds**:

```bash
# More conservative (stricter Go verdict)
VERDICT_GO_AVG_SCORE=0.80
VERDICT_GO_MIN_INDIVIDUAL_SCORE=0.75

# Default (balanced)
VERDICT_GO_AVG_SCORE=0.72
VERDICT_GO_MIN_INDIVIDUAL_SCORE=0.60

# More lenient (easier Go verdict for exploratory research)
VERDICT_GO_AVG_SCORE=0.65
VERDICT_GO_MIN_INDIVIDUAL_SCORE=0.55
```

**See Also**:
- [ENV_REFERENCE.md](ENV_REFERENCE.md#report-generation--validation) - Complete configuration reference

### Quality Tier Framework

The `pain_point_quality_tier` (GOLD/SILVER/BRONZE/INSUFFICIENT) measures **research evidence quality**, not niche attractiveness. This separation ensures that a well-researched niche with conservative LLM severity scores is not penalized on data quality.

**Evidence metrics** (computed in Stage 6):

| Metric | Description |
|--------|-------------|
| `unique_source_count` | Distinct Reddit posts cited across all pain points |
| `subreddit_diversity` | Unique subreddits represented in evidence |
| `quote_density` | Average **stance-verified** quotes per pain point |
| `pain_point_count` | Total pain points extracted |

Quotes are stance-verified (each must genuinely express its pain) and per-post
capped, so density reflects honest evidence depth (typical range ~1–5), not the
legacy pad-to-12. Thresholds below were recalibrated to that scale.

**Tier thresholds:**

| Tier | Sources | Subreddits | Pain Points | Quote Density |
|------|---------|------------|-------------|---------------|
| GOLD | >= 20 | >= 4 | >= 5 | >= 4.0 |
| SILVER | >= 10 | >= 2 | >= 3 | >= 2.0 |
| BRONZE | >= 5 | — | >= 2 | >= 1.0 |
| INSUFFICIENT | below BRONZE — pipeline stops |

**Confidence score** is a weighted composite: `unique_source_count` (0.30), `subreddit_diversity` (0.25), `quote_density` (0.25), `pain_point_count` (0.20).

Niche attractiveness (severity, WTP, opportunity scores) is assessed separately via the Go/No-Go verdict system.

---

## Data Passing Architecture

### Three Patterns for Data Transfer

#### 1. Traditional Inputs (Metadata)

**Use For**: Small, structured, pre-processed data that must be explicitly included

**Example**:
```python
crew.kickoff(inputs={
    "niche": "expat relocation",
    "solution_name": "ExpatEase",
    "total_keywords": 150
})
```

**Task Config**:
```yaml
description: >
  Analyze {solution_name} in the {niche} niche.
  Total keywords available: {total_keywords}
```

#### 2. Knowledge Sources (RAG)

**Use For**: Large unstructured data (400+ items) requiring semantic search

**Example**:
```python
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

content = format_social_discussions(discussions)  # 446 items
knowledge = StringKnowledgeSource(
    content=content,
    chunk_size=2000,
    chunk_overlap=300
)

crew = Crew(
    agents=[analyst],
    tasks=[extract_pain_points],
    knowledge_sources=[knowledge],
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}}
)
```

**Task Config**:
```yaml
description: >
  **Search Strategy:**
  - Search for "frustrated", "difficult", "can't"
  - Extract pain points with severity indicators
```

#### 3. Context Chaining (CrewAI Best Practice)

**Use For**: Passing complete Pydantic objects between sequential tasks

**Example**:
```python
@task
def generate_data(self) -> Task:
    return Task(
        output_pydantic=MyDataModel,
        # ...
    )

@task
def enhance_data(self) -> Task:
    return Task(
        context=[self.generate_data()],  # Automatic Pydantic passing
        output_pydantic=MyEnhancedDataModel,
        # ...
    )
```

**Benefits**:
- Preserves ALL fields automatically (no manual formatting)
- Type safety with Pydantic models
- No JSON serialization/deserialization needed

### Decision Framework

| Data Type | Size | Structure | Pattern |
|-----------|------|-----------|---------|
| Metadata | Any | Structured | Traditional Inputs |
| Social discussions | 400+ | Unstructured | Knowledge Sources (RAG) |
| Agent outputs | Any | Pydantic | Context Chaining |
| Keywords | 150-500 | Tabular | CSV in Traditional Inputs |
| Competitors | 10-50 | Structured | Knowledge Sources |

---

## Multi-Agent Design Patterns

### Crew Composition Strategy

**Single-Agent Crews** (PainPointCrew):
- Use for focused, specialized tasks
- One expert perspective sufficient
- Faster execution

**Multi-Agent Crews** (UnifiedSolutionCrew):
- Use for complex, multi-perspective tasks
- Different agents for different subtasks
- Agent specialization (ideation vs analysis vs selection)

### Task Dependencies

**Sequential Tasks** (UnifiedSolutionCrew):
```python
[Task 1: Ideation] → [Task 2: Competitive] → [Task 3: Refinement] → [Task 4: Selection]
```

**Benefits**:
- Clear data flow
- Context builds progressively
- Easy to debug/checkpoint

**Parallel Tasks** (avoided in this project):
- Harder to manage state
- Risk of data inconsistency
- Mainly useful for independent analyses

### Agent Specialization

**Specialist Pattern**:
```yaml
# pain_point_agents.yaml
pain_point_analyst:
  role: Pain Point Analyst specializing in social media sentiment
  goal: Extract validated user pain points from discussions
  backstory: Expert at identifying patterns in unstructured feedback
```

**Benefits**:
- Clear role definition
- Focused expertise
- Better prompt engineering

---

## Cost Optimization

### Multi-Model Strategy

Different models for different cognitive loads:

| Use Case | Model | Rationale |
|----------|-------|-----------|
| Agent reasoning | gpt-4o | High quality needed |
| Function calling | gpt-4o-mini | Simple tool use |
| Content analysis | gpt-4o | Nuanced understanding |
| Thread validation | gpt-4o-mini | Binary decision |
| Solution ideation | gpt-4o | Creative thinking |

**Configuration**:
```bash
OPENAI_MODEL_NAME=gpt-4o            # Default agent model
FUNCTION_CALLING_LLM=gpt-4o-mini    # Tool calls
CONTENT_ANALYSIS_LLM=gpt-4o         # Categorization
THREAD_VALIDATION_LLM=gpt-4o-mini   # Relevance filter
BRAINSTORM_LLM=gpt-4o               # Ideation
```

### Batching Strategies

**DataForSEO Batching**:
- API accepts up to 1000 keywords per request
- Automatic batching in `DataForSEOExpandTool`
- Reduces API calls from 150 → 1

**Parallel Crew Execution**:
```python
with ThreadPoolExecutor(max_workers=2) as executor:  # Conservative for API limits
    futures = [executor.submit(crew.kickoff, ...) for ...]
```

### Token Monitoring

**ContentTokenMonitor**:
- Tracks token usage across stages
- Warns at configurable thresholds
- Soft caps prevent runaway costs
- No hard failures (monitoring only)

**Configuration**:
```bash
TOKEN_MONITORING_ENABLED=true
TOKEN_WARNING_THRESHOLD=200000      # Warning at 200K tokens
TOKEN_SOFT_CAP_ENABLED=false        # Optional hard cap
TOKEN_SOFT_CAP=400000               # If enabled
```

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Core patterns and best practices
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Bug fixes and debugging
- [FEATURES.md](FEATURES.md) - Feature documentation
- [PATTERNS.md](PATTERNS.md) - Code recipes and templates
- [README.md](../README.md) - Project overview
