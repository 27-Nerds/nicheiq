# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NicheIQ is an autonomous AI-powered market research agent that transforms social media discussions (Reddit, Twitter) into validated SaaS business opportunities through a 10-stage automated pipeline. Built with CrewAI, it combines Flow-based orchestration with specialized multi-agent Crews.

## Architecture

### Core Design Pattern: Hybrid Flow + Unified Multi-Task Crews

```
ResearchFlow (Main Orchestrator - research_flow.py)
├── Stages 1-4: Niche validation (Flow methods)
├── Stage 5: Search & discover (Flow + SerperDevTool)
│   - QueryGenerator for search queries
│   - ThreadRelevanceValidator filters before scraping
│   - Reddit (PRAW) + Twitter collection
├── Stage 6: PainPointCrew (Knowledge Sources + RAG)
├── Stage 6.5: AudienceMappingCrew (Audience analysis)
├── Stage 7: UnifiedSolutionCrew (Context Chaining + Guardrails)
│   ├── Task 7.1: Solution Ideation (brainstorm + evaluate + refine)
│   ├── Task 7.2: Competitive Analysis (research + gap analysis)
│   ├── Task 7.3: Competitive Refinement (enhance with insights)
│   └── Task 7.4: Solution Selection (strategic scoring)
├── Stage 8: PricingStrategyCrew (Pricing validation)
├── Stage 8.5: KeywordValidationCrew (Keyword demand validation)
├── Stage 8.6: MarketSizingCrew (TAM/SAM/SOM calculation, uses keyword data)
├── Stage 8.7: SolutionRefinementCrew (Strategic refinements)
├── Stage 9: SEOStrategyCrew (Direct CSV Input for keywords)
│   ├── Phase 9.1a: Conceptual keyword expansion (SEO crew seed generation)
│   ├── Phase 9.1b: Bulk validation with DataForSEO
│   ├── Phase 9.1c: Iterative enrichment with trend data
│   ├── Task 1: Keyword Analysis & Tiering (CSV-based)
│   ├── Task 2: Content & Technical Strategy
│   ├── Task 3: Implementation Planning
│   ├── Task 4: Final SEO Strategy Synthesis
│   └── Task 5: Implementation Guide (Universal SEO, Templates, Schema)
├── Stage 9.5: TrendLongevityCrew (Market momentum analysis)
├── Stage 9.6 (conditional): SEO score refinement if SEO_REFINEMENT_ENABLED=True
├── Stage 9.7 (conditional): DataSourceCrew if requires_data_aggregation=True
└── Stage 10: Final report generation (Hybrid: Python + LLM)
    ├── Delegated to ReportGenerator class (src/nicheiq/report/report_generator.py)
    ├── Step 1: Python data assembly (80% of fields - direct copy/templates)
    ├── Step 2: Optional LLM synthesis (3 strategic fields only)
    ├── Step 3: Enhanced sections (Python: metadata, evidence, roadmaps)
    ├── Phase 1: Executive Dashboard (go/no-go verdict, core pain point, key metrics)
    ├── Phase 2: GTM Blueprint (ICP, marketing channels, content angles, 30-day playbook)
    └── Phase 3: Analytics & Visualizations (market/SEO/competitive/pain point analytics + charts)
```

### Data Passing Patterns

**Knowledge Sources (RAG)** - Use for large unstructured data (400+ items)

- Social media discussions, pain points, competitor analysis
- Typical chunk sizes: 2000/300 (Reddit), 1500/200 (Twitter)

**Traditional Inputs** - Use for structured metadata

- Small data: counts, settings, summaries
- Must be explicitly included in every task

**Context Chaining** - Use for Pydantic object passing

- Pattern: `output_pydantic` + `context=[previous_task]`
- Preserves all fields automatically (e.g., 25+ SolutionIdea fields)

**CSV Input** - Use for structured tabular data

- Keyword metrics (2x more token-efficient than JSON)
- See Pattern #5 for implementation

### CrewAI Configuration Files

Crews use `{crew_name}_agents.yaml` (personas) and `{crew_name}_tasks.yaml` (instructions). When using Knowledge Sources, add search strategy instructions in task descriptions (see [docs/PATTERNS.md](docs/PATTERNS.md)).

## Common Development Commands

See [README.md](README.md) for complete installation, usage, testing, and development instructions.

**Quick reference:**
- Installation: `uv venv && source .venv/bin/activate && uv pip install -e .`
- Run research: `python -m nicheiq.main --niche "Your niche"`
- Checkpoint resume: `python -m nicheiq.main --niche "Your niche" --resume`
- Run tests: `pytest` (unit: `pytest tests/unit/`, integration: `pytest tests/integration/`)
- Validation: `python check_setup.py` (pre-run), `python validate_report.py` (post-run)

## Key Technical Patterns

### 1. CrewAI Context Chaining

**Problem**: Manual text formatting between stages causes field loss.
**Solution**: Use `output_pydantic` + `context=[previous_task]`:

```python
@task
def task_1_generate_data(self) -> Task:
    return Task(
        config=self.tasks_config["task_1"],
        agent=self.agent_1(),
        output_pydantic=MyDataModel,
    )

@task
def task_2_enhance_data(self) -> Task:
    return Task(
        config=self.tasks_config["task_2"],
        agent=self.agent_2(),
        context=[self.task_1_generate_data()],  # Automatic Pydantic passing
        output_pydantic=MyEnhancedDataModel,
    )
```

**Benefits**: Automatic field preservation, no manual JSON formatting, type safety.

### 2. Guardrails for Field Validation

**Problem**: Agents may drop solutions or nullify fields during refinement.
**Solution**: Add guardrail functions that validate task output:

```python
def _validate_no_field_loss(self, task_output) -> tuple:
    try:
        result = task_output.pydantic
        if len(result.solution_ideas) != self._expected_solution_count:
            return (False, f"Solution count mismatch")

        for idea in result.solution_ideas:
            if idea.market_fit_score is None:
                return (False, f"Missing market_fit_score")

        return (True, result)
    except Exception as e:
        return (False, f"Validation error: {str(e)}")

@task
def competitive_refinement_task(self) -> Task:
    return Task(
        config=self.tasks_config["competitive_refinement"],
        agent=self.solution_refiner(),
        context=[self.solution_ideation_task(), self.competitive_analysis_task()],
        output_pydantic=IdeaGenerationResult,
        guardrail=self._validate_no_field_loss,  # Auto-validates and retries
    )
```

### 3. Knowledge Sources for Large Datasets

Use RAG for datasets >400 items. Add search strategy instructions in task YAML. See [docs/PATTERNS.md](docs/PATTERNS.md) for detailed patterns and examples.

### 4. Parallel Crew Execution

Use `ThreadPoolExecutor` with conservative `max_workers=2` for API rate limiting. See [docs/PATTERNS.md](docs/PATTERNS.md#parallel-execution-patterns) for implementation patterns.

### 5. CSV Input for Structured Data

Use CSV format for structured tabular data (keywords, metrics) - 2x more token-efficient than JSON.

**When to use**:
- CSV: Structured schema, full visibility needed, 150-500 items (keywords, pricing)
- RAG: Unstructured narrative, 1000+ items, semantic search needed (discussions, articles)

### 6. Stage 10 Hybrid Report Generation

Hybrid approach: Python data assembly (80%) + minimal LLM for strategic synthesis (20%).

**Implementation**:
- Step 1: Python generates 27 fields (direct copy + templates)
- Step 2: LLM enhances 3 strategic fields (executive_summary, acquisition_strategy_summary, next_steps)
- Step 3: Python adds 7 enhanced sections (metadata, evidence, roadmaps)

**Benefits**: 85% cost reduction ($0.10-0.30 → $0.02-0.05), 5x faster, zero hallucination on data fields

## Important File Locations

**Core Pipeline:**

- `src/nicheiq/flows/research_flow.py` - Main 10-stage orchestrator
- `src/nicheiq/report/report_generator.py` - Stage 10 report generation (hybrid Python + LLM)

**Crews:**

- `src/nicheiq/crews/pain_point_crew.py` - Social analysis with Knowledge Sources
- `src/nicheiq/crews/unified_solution_crew.py` - Unified solution pipeline (ideation + competitive + selection)
- `src/nicheiq/crews/solution_refinement_crew.py` - Solution refinement using keyword insights
- `src/nicheiq/crews/seo_strategy_crew.py` - SEO strategy with direct CSV input
- `src/nicheiq/crews/data_source_crew.py` - Data source research (conditional)

**Stage 9 SEO Workflow**:

1. **9.5a**: LLM generates 40-50 seeds (70% broad market, 30% pain-driven)
2. **9.5b**: DataForSEO bulk validation (filter by volume threshold)
3. **9.5c**: Expand to 150+ keywords, enrich with metrics, tier classification
4. **Tasks 1-5**: SEO strategy (keyword analysis → content/technical → implementation → synthesis → templates/schema)
5. **9.75** (optional): Refine SEO scores if `SEO_REFINEMENT_ENABLED=true`

**Key Files**:

- Config: `src/nicheiq/config/settings.py`, `src/nicheiq/crews/config/*_agents.yaml`, `*_tasks.yaml`
- Models: `research_state.py`, `pain_point.py`, `solution_idea.py`, `keyword_data.py`, `analytics.py`
- Tools: `reddit_tool.py`, `twitter_tool.py`, `dataforseo_tool.py`
- Reports: `report_generator.py`, `visualizations.py`

## API Keys & Environment

**Required:**

- `OPENAI_API_KEY` - GPT-4o for agent reasoning
- `CHROMA_OPENAI_API_KEY` - **CRITICAL** for CrewAI knowledge sources (RAG). ChromaDB's default environment variable for OpenAI embeddings. Set to same value as `OPENAI_API_KEY`
- `SERPER_API_KEY` - Google search
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` - PRAW
- `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` - Keyword research

**Optional:**

- `TWITTER_USERNAME`, `TWITTER_PASSWORD`, `TWITTER_EMAIL` - Authenticated scraping (guest mode fallback)
- `CREWAI_API_KEY` - CrewAI+ features

**Note**: Without `CHROMA_OPENAI_API_KEY`, knowledge sources fail silently with "Failed to init knowledge" warnings.

## Configuration

See [ENV_REFERENCE.md](ENV_REFERENCE.md) for complete configuration options.

### Multi-Model Cost Optimization Strategy

NicheIQ uses 6 specialized models to optimize cost vs quality (60-90% savings):

**High-Reasoning Tasks** (use `gpt-4o`):
- `OPENAI_MODEL_NAME` - Default agent reasoning
- `CONTENT_ANALYSIS_LLM` - Social media categorization
- `BRAINSTORM_LLM` - Solution ideation

**Simple Tasks** (use `gpt-4o-mini` or `gpt-4.1-nano`):
- `FUNCTION_CALLING_LLM=gpt-4o-mini` - Tool calls (60% cost reduction)
- `THREAD_VALIDATION_LLM=gpt-4o-mini` - Relevance filtering (60% reduction)
- `KEYWORD_VALIDATION_LLM=gpt-4.1-nano` - Keyword checks (90% reduction)
- `KEYWORD_RESEARCH_LLM=gpt-4o-mini` - SEO analysis (60% reduction)

**Cost Impact**: Multi-model strategy (default) saves ~$1.35 per run vs all gpt-4o ($2.20 → $0.85)

See [ENV_REFERENCE.md#specialized-model-configuration-advanced](ENV_REFERENCE.md#specialized-model-configuration-advanced) for detailed guidance.

### Common Settings

- `ENABLE_TWITTER=false` - Skip Twitter collection
- `REDDIT_COMMENT_LIMIT=32` - Balance depth vs cost (None=all, 0=top-level)
- `CHECKPOINT_ENABLED=true` - Enable resume capability
- `TOKEN_MONITORING_ENABLED=true` - Track token usage

## When Modifying Crews

### Data Passing Validation Checklist

**CRITICAL**: Verify all inputs are properly passed to avoid hallucinations.

1. List all inputs in `crew.kickoff(inputs={...})`
2. Ensure `{key}` placeholder exists in task YAML for each input
3. Log input sizes for debugging
4. Validate outputs contain actual data (not placeholders)

See [docs/PATTERNS.md](docs/PATTERNS.md) for detailed patterns and examples.

### Adding New Crews

See [docs/PATTERNS.md#adding-new-crews](docs/PATTERNS.md#adding-new-crews) for step-by-step guide.

**Key Steps**:
1. Extend `@CrewBase`, define agents/tasks with decorators
2. Apply Data Passing Checklist
3. Add explicit field guidance in YAML (CrewAI doesn't auto-inject Pydantic descriptions)
4. Update `research_flow.py` to integrate

See [PROMPT_OPTIMIZATION_BEST_PRACTICES.md](PROMPT_OPTIMIZATION_BEST_PRACTICES.md) for advanced patterns.

## CrewAI Best Practices

**Knowledge Sources (RAG):**
- Use for large datasets (400+ items), unstructured content, semantic search needs
- Add metadata headers: `[POST_ID: ...]`, `[PLATFORM: ...]`, `[SCORE: ...]`
- Configure chunking: `chunk_size=2000, chunk_overlap=300`
- Use cost-effective embeddings: `text-embedding-3-small`

**Structured Output (Pydantic):**
- Use `output_pydantic=ModelClass` for type-safe outputs
- Use `Optional[Type] = Field(default=None)` for conditional data
- Add explicit field requirements in task `expected_output` (not auto-injected)

**Flow State Management:**
- Define Pydantic BaseModel for type safety: `class MyFlow(Flow[MyState]):`
- Extract from state in separate methods with `Optional[Model]` return type
- Use try/except with logger.warning for graceful degradation

**Context Chaining:**
- Pass complete Pydantic objects: `context=[previous_task]`
- Use `output_pydantic=Model` on source task
- Preserves all fields without manual formatting

**Task Configuration:**
- Write specific `expected_output` with field structure
- Add search strategies for knowledge source queries
- Request source IDs in output for attribution

**Guardrails:**
- Add validation: `guardrail=validation_function`
- Return `(True, result)` for success, `(False, error_msg)` for retry

**References:**
- Official Docs: https://docs.crewai.com/
- Knowledge Sources: https://docs.crewai.com/en/concepts/knowledge
- Flow State: https://docs.crewai.com/en/guides/flows/mastering-flow-state

## Output Structure

```
output/
├── final_report_YYYYMMDD_HHMMSS.json     # Complete research report
├── research_state_raw_YYYYMMDD_HHMMSS.json  # Raw state data
├── checkpoints/checkpoint_{niche}_{timestamp}/  # Resume capability
└── logs/nicheiq_YYYY-MM-DD.log           # Execution logs
```

**Final Report** (see `FinalReport` in `research_state.py`):

- Core: Niche validation, selected solution, pain points, competitive analysis, SEO strategy
- Enhanced: Research metadata, alternatives, evidence appendix, decision framework
- Analytics: Executive dashboard, GTM blueprint, visualizations (charts + metrics)

## See Also

For additional documentation, see the [docs/](docs/README.md) directory:

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Deep technical architecture, design philosophy, and data flows
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Bug fixes, known issues, and debugging strategies
- **[docs/FEATURES.md](docs/FEATURES.md)** - Advanced features (checkpoints, token monitoring, multi-model strategy)
- **[docs/PATTERNS.md](docs/PATTERNS.md)** - Reusable code patterns and templates
- **[PROMPT_OPTIMIZATION_BEST_PRACTICES.md](PROMPT_OPTIMIZATION_BEST_PRACTICES.md)** - Prompt engineering guidelines
- **[ENV_REFERENCE.md](ENV_REFERENCE.md)** - Complete environment variable reference
