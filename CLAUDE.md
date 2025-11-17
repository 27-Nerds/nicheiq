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
├── Stages 7-8.75: UnifiedSolutionCrew (Context Chaining + Guardrails)
│   ├── Task 1: Solution Ideation (brainstorm + evaluate + refine)
│   ├── Task 2: Competitive Analysis (research + gap analysis)
│   ├── Task 3: Competitive Refinement (enhance with insights)
│   └── Task 4: Solution Selection (strategic scoring)
├── Stage 9: SEOStrategyCrew (Direct CSV Input for keywords)
│   ├── Phase 9.5a: Conceptual keyword expansion (SEO crew seed generation)
│   ├── Phase 9.5b: Bulk validation with DataForSEO
│   ├── Task 1: Keyword Analysis & Tiering (CSV-based)
│   ├── Task 2: Content & Technical Strategy
│   ├── Task 3: Implementation Planning
│   ├── Task 4: Final SEO Strategy Synthesis
│   └── Task 5: Implementation Guide (Universal SEO, Templates, Schema)
│   - Stage 9.5 (conditional): SEO score refinement if SEO_REFINEMENT_ENABLED=True
│   - Stage 9.75 (conditional): Data sources if requires_data_aggregation=True
└── Stage 10: Final report generation (Hybrid: Python + LLM)
    ├── Delegated to ReportGenerator class (src/nicheiq/report/report_generator.py)
    ├── Step 1: Python data assembly (80% of fields - direct copy/templates)
    ├── Step 2: Optional LLM synthesis (3 strategic fields only)
    └── Step 3: Enhanced sections (Python: metadata, evidence, roadmaps)
```

### CRITICAL: Knowledge Sources vs Inputs Pattern

**When to use Knowledge Sources (RAG):**
- Large unstructured data (400+ items: social media discussions)
- Content where agents need semantic search capability
- Data that agents query selectively during reasoning
- Examples: PainPointCrew, UnifiedSolutionCrew (pain points + competitors), SEOStrategyCrew (pain points + competitors for seed generation ONLY)
- Note: SEOStrategyCrew uses direct CSV input for keyword data (not RAG) - see Pattern #8 below

**When to use Traditional Inputs:**
- Structured, pre-processed data
- Small metadata (counts, settings, summaries)
- Data that must be explicitly included in every task
- Examples: Metadata fields across all crews

**When to use Context Chaining (CrewAI Best Practice):**
- Passing complete Pydantic objects between sequential tasks
- Automatic field preservation (no manual formatting)
- Use `output_pydantic` + `context=[previous_task]` pattern
- Examples: UnifiedSolutionCrew (4 tasks), SEOStrategyCrew (5 tasks)

**Implementation Notes:**
- See crew files for specific chunk sizes. Typical: 2000 chars, 300 overlap for Reddit; 1500 chars, 200 overlap for Twitter
- Context chaining preserves ALL 25+ SolutionIdea fields automatically
- Keywords passed as CSV to SEO crew (2x more token-efficient than JSON, full visibility)

### CrewAI Configuration Files

Each crew has dedicated configuration files following the pattern `{crew_name}_agents.yaml` and `{crew_name}_tasks.yaml`:

- **Agents config**: Defines agent personas (role, goal, backstory)
- **Tasks config**: Defines task instructions - some use direct inputs, others use knowledge sources

**Example**: PainPointCrew uses `pain_point_agents.yaml` and `pain_point_tasks.yaml`

When modifying tasks that use knowledge sources, include search strategy instructions:
```yaml
description: >
  **Search Strategy for Knowledge Sources:**
  - Search for problems: "frustration", "difficult", "can't"
  - Search for solutions: "using", "tried", "alternative to"
```

## Common Development Commands

```bash
# Installation
uv venv && source .venv/bin/activate
uv pip install -e .

# Run research
python -m nicheiq.main --niche "AI tools for content creators"
python -m nicheiq.main --niche "Your niche" --output ./custom_output --log-level DEBUG
python -m nicheiq.main --niche "expat relocation" --project-types directory,aggregator

# Checkpoint/Resume
python -m nicheiq.main --niche "AI tools" --resume
python -m nicheiq.main --list-checkpoints
python -m nicheiq.main --niche "AI tools" --no-checkpoint

# Testing & Quality
pytest --cov=src/nicheiq --cov-report=term-missing
black src/ tests/ && ruff check src/ tests/

# Validation
python check_setup.py
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```

## Key Technical Patterns

### 1. Async Flow Execution

**Problem**: Twitter-api-client uses `asyncio.run()` internally, causing nested event loop errors.
**Solution**: Use thread executor:

```python
import asyncio

async def stage_5_search_and_discover(self):
    loop = asyncio.get_event_loop()
    twitter_threads = await loop.run_in_executor(
        None,
        lambda: asyncio.run(self.twitter_tool.collect_threads(twitter_urls))
    )
```

### 2. LLM Structured Output

**Problem**: CrewAI's LLM wrapper doesn't support `response_format` parameter.
**Solution**: Use LangChain directly for structured Pydantic output:

```python
from langchain_openai import ChatOpenAI

structured_llm = ChatOpenAI(
    model=settings.openai_model_name,
    temperature=0.7,
    api_key=settings.openai_api_key
).with_structured_output(YourPydanticModel)

result = structured_llm.invoke(prompt)
```

### 3. CrewAI Context Chaining

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

### 4. Guardrails for Field Validation

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

### 5. Knowledge Sources for Large Datasets

**Problem**: Passing 446+ keywords as text causes prompt size issues.
**Solution**: Use Knowledge Sources (RAG) for datasets >400 items:

```python
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

keyword_content = self._format_keywords_for_knowledge(enriched_keywords)
# Format: [TIER 1 - QUICK WIN] ... [TIER 2 - STRATEGIC GROWTH] ...

keyword_knowledge = StringKnowledgeSource(
    content=keyword_content,
    chunk_size=2000,
    chunk_overlap=200
)

crew = Crew(
    agents=[self.keyword_strategist()],
    tasks=[self.analyze_keywords_task()],
    knowledge_sources=[keyword_knowledge],
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}}
)
```

**Task description** should include search strategy:
```yaml
description: >
  **Search Strategy:**
  - High-priority: Search "TIER 1", "quick win", "low competition"
  - Strategic: Search "TIER 2", "strategic growth"
  - Geographic: Search country/city names
```

**Benefits**: Scales to 1000+ keywords, semantic search, efficient RAG retrieval, cost-effective.

### 6. Parallel Crew Execution

```python
def analyze_competition(self, parallel: bool = True, max_workers: int = 2):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_solution = {
            executor.submit(self._analyze_single_solution, idea, i, total): idea
            for i, idea in enumerate(self.solution_ideas.solution_ideas, 1)
        }
        for future in as_completed(future_to_solution):
            landscape = future.result()
            all_landscapes.append(landscape)
```

Conservative `max_workers=2` to respect API rate limits.

### 7. Template Variable Parsing

**Problem**: CrewAI parses ALL `{variable}` patterns as template variables. Using curly braces in examples causes KeyError.

**Solution**: Use square brackets `[ ]` or angle brackets `< >` for examples:

```yaml
# ✅ CORRECT
description: >
  Search for competitors using: "[solution name] competitors"
  Example search: "[keyword] alternatives"

# ❌ WRONG - causes KeyError
description: >
  Search for: "{solution_name} competitors"
```

**When {curly braces} ARE needed**: Only when variable is provided in `crew.kickoff(inputs={...})`.

**Rule of Thumb**: If it's instructional text, example syntax, or refers to data from context/previous tasks → use `[ ]` not `{ }`.

### 8. SEO Crew Direct CSV Input Strategy

**Problem**: Passing 150+ enriched keywords via Knowledge Sources (RAG) caused incomplete data visibility and retrieval uncertainty.

**Solution**: Use direct CSV input in task context for structured keyword data.

```python
# Format keywords as CSV (2x more efficient than JSON)
def _format_keywords_as_csv(self, keywords: List[EnrichedKeyword]) -> str:
    """Convert enriched keywords to CSV format for agent consumption."""
    rows = ["keyword,search_volume,competition,cpc,tier,geography"]
    for kw in keywords:
        rows.append(f"{kw.keyword},{kw.search_volume},{kw.competition},"
                   f"{kw.cpc},{kw.tier},{kw.geography}")
    return "\n".join(rows)

# Pass directly in task inputs (full visibility)
keywords_csv = self._format_keywords_as_csv(enriched_keywords)

crew_output = self.crew().kickoff(inputs={
    "keywords_csv": keywords_csv,
    "total_keyword_count": len(enriched_keywords),
    # ... other inputs
})
```

**Benefits**:
- Complete data visibility in task context (100% of keywords visible to agent)
- 2x more token-efficient than JSON format
- Industry best practice for structured tabular data
- Eliminates RAG retrieval uncertainty and semantic search limitations
- Agents can see exact volume/competition/CPC metrics for strategic decisions

**When CSV is better than RAG**:
- Structured data with consistent schema (keywords, pricing tables, metrics)
- Data that needs complete visibility (no sampling/retrieval needed)
- Moderate dataset sizes (150-500 items where full context fits in prompt)

**When RAG is still better**:
- Unstructured narrative content (social media discussions, articles)
- Large datasets (1000+ items where selective retrieval is required)
- Content requiring semantic search (finding themes, sentiment patterns)

**Note**: SEOStrategyCrew still uses Knowledge Sources for pain points and competitive intelligence (unstructured data), but switches to CSV for keyword data (structured metrics).

### 9. Stage 10 Hybrid Report Generation

**Problem**: Previous approach used 245-line LLM prompt to generate entire report, causing high cost ($0.10-0.30), slow speed (5-15s), and hallucination risk on data fields.

**Solution**: Hybrid approach - Python data assembly (80%) + minimal LLM for strategic synthesis (20%).

```python
def stage_10_generate_report(self):
    """Generate report using hybrid approach."""

    # Step 1: Python data assembly (80% of fields)
    final_report = self._generate_fallback_report()
    # Includes:
    # - ALL pain points (no arbitrary limits)
    # - Direct copies: selection rationale, runner-ups, scores
    # - Templates: user journey, MVP scope, CAC breakdown
    # - Existing summaries: pain_points_summary, solutions_summary, competitive_summary

    # Step 2: Optional LLM enhancement (3 strategic fields only)
    final_report = self._enhance_report_with_llm(final_report)
    # LLM generates ONLY:
    # - executive_summary (4-6 sentences)
    # - acquisition_strategy_summary (2-3 paragraphs)
    # - next_steps (5-8 action items)

    # Step 3: Enhanced sections (Python-based)
    final_report.research_metadata = self._generate_research_metadata()
    final_report.alternative_solutions = self._generate_alternative_solutions()
    # ... other enhanced sections
```

**Benefits**:
- **Cost**: 85% reduction ($0.10-0.30 → $0.02-0.05)
- **Speed**: 5x faster (10s → 2s)
- **Quality**: Same or better (zero hallucination on data fields)
- **Reliability**: Python fallback always succeeds if LLM fails
- **Data Preservation**: ALL pain points and solutions included (no arbitrary limits)

**Field Breakdown**:
- **Direct Copy** (11 fields): `selected_solution_name`, `selection_rationale`, `runner_up_solutions`, `selection_criteria_scores`, `recommended_focus`, `selected_solution_details`, `top_pain_points`, `recommended_solutions`, `competitive_analysis`, `seo_strategy`, `data_source_research`
- **Templates** (9 fields): `solution_user_journey`, `solution_implementation_overview`, `mvp_scope_definition`, `market_validation`, `pain_points_summary`, `solutions_summary`, `competitive_summary`, `data_sourcing_recommendations`, `estimated_cac_breakdown`
- **LLM** (3 fields): `executive_summary`, `acquisition_strategy_summary`, `next_steps`
- **Python Enhanced Sections** (7 fields): `research_metadata`, `alternative_solutions`, `competitive_landscape_matrix`, `evidence_appendix`, `data_infrastructure_roadmap`, `decision_framework`, `content_categorization`

**When to use Python-only** (skip LLM enhancement):
- Development/testing to save costs
- Network issues or API unavailable
- When template-based summaries are sufficient

**Implementation Details**:
- `_generate_fallback_report()`: Now production-quality (not just fallback)
- `_enhance_report_with_llm()`: Minimal ~35-line inline prompt vs previous 245 lines
- Uses shared utility: `find_solution_by_name()` from utils/helpers.py
- No arbitrary limits: ALL pain points, ALL solutions included

## Checkpoint & Resume System

Folder-based checkpoint system to recover from failures and avoid wasting API costs.

**Structure:**
```
output/checkpoints/checkpoint_{niche_slug}_{timestamp}/
├── metadata.json
├── stage_5_social_content.json
├── stage_6_pain_points.json
├── stage_7_solutions.json
├── stage_8_competitive.json
├── stage_8_75_solution_selection.json
├── stage_9_seo_strategy.json
└── stage_9_75_data_sources.json (conditional)
```

**Usage:**
```bash
python -m nicheiq.main --niche "AI tools" --resume  # Auto-resume
python -m nicheiq.main --list-checkpoints  # List all
python -m nicheiq.main --niche "AI tools" --checkpoint ./output/checkpoints/checkpoint_ai_tools_20250110_143052
```

**Configuration (.env):**
```bash
CHECKPOINT_ENABLED=true
CHECKPOINT_MAX_AGE_DAYS=7
CHECKPOINT_AUTO_CLEANUP=true
```

**Benefits**: Cost savings ($0.50-$2.00 per failed run), time savings (5-15 min), debugging aid.

**Troubleshooting**: Enable `CHECKPOINT_ENABLED=true`, use `--list-checkpoints` to verify available checkpoints.

## Important File Locations

**Core Pipeline:**
- `src/nicheiq/flows/research_flow.py` - Main 10-stage orchestrator
- `src/nicheiq/report/report_generator.py` - Stage 10 report generation (hybrid Python + LLM)

**Crews:**
- `src/nicheiq/crews/pain_point_crew.py` - Social analysis with Knowledge Sources
- `src/nicheiq/crews/idea_generation_crew.py` - Solution ideation
- `src/nicheiq/crews/competitive_crew.py` - Competitive research
- `src/nicheiq/crews/seo_strategy_crew.py` - SEO strategy with direct CSV input

**Stage 9 SEO Workflow Details:**
1. **Phase 9.5a** (SEO Crew): Generate 40-50 seed keywords via LLM
   - 70% broad market keywords (e.g., "expat health insurance")
   - 30% targeted pain point keywords (from social discussions)
   - Uses Knowledge Sources for pain points + competitors (RAG)
2. **Phase 9.5b** (Flow): Bulk validate seeds with DataForSEO
   - Filter by minimum search volume threshold
   - Remove invalid or low-volume seeds
3. **Phase 9.5c** (Flow): Expand validated seeds
   - DataForSEO expansion (up to 1000 keywords per seed)
   - Enrichment with volume, competition, CPC metrics
   - Tier classification (Tier 1: Quick Win, Tier 2: Strategic Growth)
4. **Tasks 1-5** (SEO Crew): Analyze and strategize with CSV input
   - Task 1: Keyword Analysis & Tiering
   - Task 2: Content & Technical Strategy
   - Task 3: Implementation Planning
   - Task 4: Final SEO Strategy Synthesis
   - **Task 5: Implementation Guide** (adds 3 new fields)
     - Universal SEO strategy (cross-cutting best practices)
     - Page templates by content type (detailed implementation specs)
     - Schema markup strategy (JSON-LD examples, priority types)
     - Preserves ALL 26 fields from Task 4 → Total: 29 fields in SEOStrategyReport
5. **Stage 9.5** (Flow, conditional): Refine SEO scores in selected solution
   - Only if SEO_REFINEMENT_ENABLED=True
   - Updates solution's SEO difficulty/opportunity scores using keyword data

**Configuration:**
- `src/nicheiq/crews/config/{crew_name}_agents.yaml` - Agent definitions (dedicated per crew)
- `src/nicheiq/crews/config/{crew_name}_tasks.yaml` - Task specs with search strategies (dedicated per crew)
- `src/nicheiq/config/settings.py` - Centralized settings

**Data Models:**
- `src/nicheiq/models/research_state.py` - Flow state and final report
- `src/nicheiq/models/pain_point.py` - Pain point analysis
- `src/nicheiq/models/solution_idea.py` - Solution concepts (includes `requires_data_aggregation`)
- `src/nicheiq/models/competitor.py` - Competitive analysis
- `src/nicheiq/models/keyword_data.py` - Keyword research

**Tools:**
- `src/nicheiq/tools/reddit_tool.py` - PRAW-based collector
- `src/nicheiq/tools/twitter_tool.py` - twitter-api-client wrapper
- `src/nicheiq/tools/dataforseo_tool.py` - Keyword research with batching

## API Keys & Environment

**Required:**
- `OPENAI_API_KEY` - GPT-4o for agent reasoning
- `CHROMA_OPENAI_API_KEY` - **CRITICAL** for CrewAI knowledge sources (RAG). Set to same value as `OPENAI_API_KEY`
- `SERPER_API_KEY` - Google search
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` - PRAW
- `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` - Keyword research

**Optional:**
- `TWITTER_USERNAME`, `TWITTER_PASSWORD`, `TWITTER_EMAIL` - Authenticated scraping (guest mode fallback)
- `CREWAI_API_KEY` - CrewAI+ features

**Note**: Without `CHROMA_OPENAI_API_KEY`, knowledge sources fail silently with "Failed to init knowledge" warnings.

## Advanced Configuration

**Multi-Model Strategy** (cost vs quality optimization):
- `OPENAI_MODEL_NAME` (gpt-4o): General agent reasoning
- `FUNCTION_CALLING_LLM` (gpt-4o-mini): Tool calls
- `CONTENT_ANALYSIS_LLM` (gpt-4o): Content categorization
- `THREAD_VALIDATION_LLM` (gpt-4o-mini): Relevance filtering
- `BRAINSTORM_LLM` (gpt-4o): Solution ideation

**Other Settings:**
- `ENABLE_TWITTER` (bool): Set False to skip Twitter
- `REDDIT_COMMENT_LIMIT` (int): Controls depth (None=all, 32=balanced, 0=top-level)
- `SEO_REFINEMENT_ENABLED` (bool): Toggle Stage 9.5
- `KEYWORD_ENRICHMENT_TARGET_COUNT` (int): Target keyword count (default: 150)

## When Modifying Crews

### Data Passing Validation Checklist

**CRITICAL**: Always verify input data is properly passed to agents to avoid blind operation or hallucinations.

**Pre-Flight Checklist:**
1. List all inputs in `crew.kickoff(inputs={...})`
2. Find crew's task config file (`{crew_name}_tasks.yaml` in `src/nicheiq/crews/config/`)
3. Verify placeholders: For each input key, ensure `{key}` appears in task description
4. Log input sizes for debugging
5. Validate outputs contain expected data, not hallucinations

**Common Data Passing Patterns:**

**Pattern 1: Direct Injection** (metadata, counts, names)
```python
inputs = {"solution_name": "ExpatEase", "niche": "expat relocation"}
```
```yaml
description: >
  Analyze {solution_name} in the {niche} niche.
```

**Pattern 2: Formatted Strings** (keyword lists, pain points)
```python
formatted = "\n".join([f"**{p.title}** (Severity: {p.score}/10)" for p in pain_points])
inputs = {"high_priority_list": formatted}
```
```yaml
description: >
  Generate solutions for pain points:
  {high_priority_list}
```

**Pattern 3: Knowledge Sources** (large/unstructured data >400 items)
```python
knowledge_source = StringKnowledgeSource(content=formatted_content, chunk_size=2000)
crew = Crew(..., knowledge_sources=[knowledge_source])
```
```yaml
description: >
  **Search Strategy:**
  - Search for "frustrated", "difficult"
```

**Anti-Pattern to Avoid:**
❌ Passing data without placeholder in task description
```python
crew.kickoff(inputs={"keywords": data})  # Data passed
```
```yaml
description: >
  Analyze keywords.  # NO {keywords} placeholder - agent never sees data!
```

### Adding New Crews

1. Extend `@CrewBase` class
2. Define agents with `@agent` decorator
3. Define tasks with `@task` decorator (use `context=` for dependencies)
4. Define crew assembly with `@crew` decorator
5. **Apply Data Passing Checklist** (verify all inputs properly injected)
6. Update `research_flow.py` to integrate new stage

**Modifying knowledge sources:**
- Adjust `chunk_size`/`chunk_overlap` based on content
- Add search strategy instructions to task descriptions
- Test semantic search quality

**Using output_pydantic:**
CrewAI doesn't auto-inject Pydantic `Field(description=...)` (GitHub #1338). **Workaround**:
1. Add explicit field guidance in task YAML `expected_output`
2. For context chaining, add extraction instructions:
   ```yaml
   description: >
     **HOW TO ACCESS CONTEXT:**
     Extract from previous task: field_a, field_b (PRESERVE exactly)
     Your output must contain ACTUAL VALUES from context.
   ```
3. See `PROMPT_OPTIMIZATION_BEST_PRACTICES.md` Section 5.3 for detailed patterns

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

### 10. Context-Aware Query/Keyword Generation

**Problem**: Template-driven query generation produces nonsensical results (e.g., "apps for home appliances").
**Solution**: Use context-aware generators with NicheContext (market_segments, industry_boundaries).

```python
from nicheiq.utils.helpers import KeywordSeedGenerator

generator = KeywordSeedGenerator()
result = generator.generate_seeds(
    solution=selected_solution,
    niche_context=niche_context,
    pain_points=pain_points,
    competitive_analysis=competitive_analysis
)
# Returns 40-50 keywords with semantic validation and market segment integration
```

**Available Generators**:
- `QueryGenerator` - Social media search queries
- `CompetitorQueryGenerator` - Competitor search with solution-type awareness
- `KeywordSeedGenerator` - SEO seed keywords (used in Stage 9.5a)

**Key Features**: Chain-of-thought analysis, 6 semantic validation rules, input sanitization, market segment extraction as keyword modifiers.

**Benefits**: Eliminates nonsensical patterns, leverages full niche context, generates solution-type-appropriate terminology.

### 11. Token Monitoring & Soft Caps

**Problem**: Large social media collections can approach context limits with extended models (1M tokens), causing unexpected costs.
**Solution**: Monitor token usage with soft caps for cost visibility without hard failures.

```python
from nicheiq.utils.helpers import ContentTokenMonitor

monitor = ContentTokenMonitor()

# Log content stats with cost estimate
token_count = monitor.log_content_stats(
    content=formatted_content,
    label="Stage 6 - Reddit content",
    model="gpt-4o"
)
# Logs: "Stage 6 - Reddit content: 112,430 tokens (~$0.28), 11.2% of 1M context"

# Check soft caps (warns but doesn't fail)
monitor.check_soft_cap(tokens=token_count, label="Stage 6", model="gpt-4o")
```

**Configuration** (.env):
```bash
TOKEN_MONITORING_ENABLED=true
TOKEN_WARNING_THRESHOLD=200000      # Log warning at 200K tokens
TOKEN_SOFT_CAP_ENABLED=false        # Disabled by default
TOKEN_SOFT_CAP=400000               # If enabled, log critical warning at 400K
```

**Features**:
- Accurate token counting via tiktoken
- Cost estimation for GPT-4/GPT-4o models
- Warning thresholds (always enabled)
- Optional soft caps (log critical warning when exceeded)
- No pipeline failures - monitoring only

**Usage Locations**:
- Stage 5 (ResearchFlow): Collection size monitoring
- Stage 6 (PainPointCrew): Task 1 input monitoring

**Benefits**: Cost visibility, early warnings for large collections, no failures, configurable thresholds.

## Output Structure

```
output/
├── final_report_YYYYMMDD_HHMMSS.json
├── research_state_raw_YYYYMMDD_HHMMSS.json
├── checkpoints/checkpoint_{niche}_{timestamp}/
└── logs/nicheiq_YYYY-MM-DD.log
```

### Final Report Structure

See `FinalReport` Pydantic model in `src/nicheiq/models/research_state.py` for complete schema.

**Core Sections:**
- Niche description and validation
- Selected solution details (full SolutionIdea object)
- Solution selection rationale and criteria scores
- Runner-up solution names
- Pain points with severity/WTP scores
- Solution recommendations
- Competitive analysis (for selected solution)
- SEO strategy (if Stage 9 completed)
- Data sourcing recommendations (for data aggregation solutions)
- Next steps and action items

**Enhanced Sections (Phase 3):**
1. **research_metadata**: Reddit/Twitter counts, subreddit breakdown, collection date
2. **alternative_solutions**: Top 2 runner-ups with scores, differentiators, pivot triggers
3. **competitive_landscape_matrix**: Cross-solution competitor overlap, intensity analysis
4. **evidence_appendix**: Top 10 Reddit threads, pain point quote sources with post IDs
5. **data_infrastructure_roadmap**: 3-phase plan (MVP/Growth/Scale) with costs, risks, fallbacks
6. **decision_framework**: Go/no-go/pivot criteria with rationales
7. **content_categorization**: Theme categories, user segments, discussion quality assessment

**Data Preservation**: Enhanced sections preserve ~60-70% of checkpoint data (up from ~5-10%).

## Debugging Tips

```bash
python -m nicheiq.main --niche "..." --log-level DEBUG
```

**Common Issues:**
- "Failed to init knowledge" → Missing `CHROMA_OPENAI_API_KEY`
- No embeddings created → Verify `CHROMA_OPENAI_API_KEY` is set
- Nested event loop → Handled by thread executor pattern
- DataForSEO insufficient credits → Reduce `KEYWORD_MIN_SEARCH_VOLUME`

**Report validation:**
```bash
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```
Checks for hallucinations, score rounding, CAC accuracy, page count accuracy.

## Performance Expectations

- **Duration**: 5-15 minutes per niche
- **Cost**: $0.50-$2.20 per research run
  - OpenAI (GPT-4o): $0.50-$2.00
  - Serper: $0.01-$0.05
  - DataForSEO: $0.01-$0.10
  - Reddit/Twitter: Free
