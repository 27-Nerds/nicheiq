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
7. **Hacker News Tool (Algolia API)**: Direct search + comment collection → `SocialPost`
8. **Content Fencing**: Delimiter-based prompt injection defense on all scraped content
9. **Hybrid Dedup**: n-gram + token Jaccard cross-source deduplication

**Data Flow**:
```
NicheContext → QueryGenerator → Search Queries
            → SerperDev → Reddit/Twitter URLs
            → TokenOverlapPrefilter → Pre-filtered URLs
            → ThreadRelevanceValidator → Validated URLs
            → PRAW → RedditPost[]
            → HN Algolia API → SocialPost[] (generic)
            → Cross-source Dedup → SocialContentCollection
                                   ├── reddit_posts
                                   ├── twitter_threads
                                   └── generic_posts (HN, YouTube, etc.)
```

**Key Decisions**:
- Token-overlap pre-filter before LLM validation saves ~30% API costs
- HN uses Algolia API directly (free, no auth) — no Serper round-trip needed
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
evidence pass (`enable_seed_enrichment`, default on): pain/idea-derived queries → relevance
post-filter + dedup → if ≥3 posts survive, `state.social_content` is set and checkpointed as
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

#### Originality pipeline (Stage 7 ideation internals)

Ideation does **not** run a single brainstorm task. To fight mode collapse on reasoning
models (where temperature is inert and prompt technique is the only diversity lever), the
crew generates concepts through an originality pipeline before the convergent
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
   trustworthy originality signal.
3. **Pool + dedup** (`_pool_and_dedup_raw_concepts`) across all samples, capped at
   `divergent_pool_cap` (default 12). Falls back to a single divergent sample if the pool
   comes back too small.
4. **Convergent tasks** (filter → refine → select) run on the pooled concepts. The
   M/D/J-tag carry-through also copies `obviousness_score` from the pooled `RawConcept` onto
   the final refined idea by whitespace-normalized name.
5. **Deterministic coverage + bold-slot re-injection** — after refinement, code (not the
   LLM) guarantees pain-point coverage and a single **bold slot** (the most original unused
   concept). Re-injected ideas are fully refined via `_refine_single_concept` (not stubs) so
   they carry the same fields and scores as the rest.

`obviousness_score` is surfaced in the UI as **Originality** (= 1 − obviousness_score,
falling back to `novelty_score`). `novelty_score` stays the refiner's separate signal and
continues to drive the composite score and the "Innovator" superpower.

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
| `quote_density` | Average direct quotes per pain point |
| `pain_point_count` | Total pain points extracted |

**Tier thresholds:**

| Tier | Sources | Subreddits | Pain Points | Quote Density |
|------|---------|------------|-------------|---------------|
| GOLD | >= 20 | >= 4 | >= 5 | >= 8.0 |
| SILVER | >= 10 | >= 2 | >= 3 | >= 5.0 |
| BRONZE | >= 5 | — | >= 2 | >= 3.0 |
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
