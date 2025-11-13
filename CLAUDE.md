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
├── Stage 6: PainPointCrew (Knowledge Sources + RAG)
├── Stages 7-8.75: UnifiedSolutionCrew (Context Chaining + Guardrails)
│   ├── Task 1: Solution Ideation (brainstorm + evaluate + refine)
│   ├── Task 2: Competitive Analysis (research + gap analysis)
│   ├── Task 3: Competitive Refinement (enhance with insights)
│   └── Task 4: Solution Selection (strategic scoring)
├── Stage 9: SEOStrategyCrew (Knowledge Sources for keywords)
│   ├── Task 1: Keyword Analysis & Tiering (RAG-based)
│   ├── Task 2: Content & Technical Strategy
│   ├── Task 3: Implementation Planning
│   └── Task 4: Final SEO Strategy Synthesis
└── Stage 10: Final report (Flow + LLM synthesis)
```

### CRITICAL: Knowledge Sources vs Inputs Pattern

**When to use Knowledge Sources (RAG):**
- Large unstructured data (400+ items: social media discussions, keywords)
- Content where agents need semantic search capability
- Data that agents query selectively during reasoning
- Examples: PainPointCrew (always), UnifiedSolutionCrew (pain points + competitors), SEOStrategyCrew (keywords)

**When to use Traditional Inputs:**
- Structured, pre-processed data
- Small metadata (counts, settings, summaries)
- Data that must be explicitly included in every task
- Examples: Metadata fields across all crews

**When to use Context Chaining (CrewAI Best Practice):**
- Passing complete Pydantic objects between sequential tasks
- Automatic field preservation (no manual formatting)
- Use `output_pydantic` + `context=[previous_task]` pattern
- Examples: UnifiedSolutionCrew (4 tasks), SEOStrategyCrew (4 tasks)

**Current Implementation:**
- `PainPointCrew`: **Hybrid Approach** - Full content inputs for first agent, Knowledge Sources for subsequent agents
  - **First Agent (content_researcher)**: Receives ALL formatted content via traditional inputs for comprehensive categorization
  - **Subsequent Agents (pain_point_analyst, validator)**: Use Knowledge Sources (RAG) for targeted evidence retrieval
  - Reddit: 2000 char chunks, 300 overlap, depth=3, up to 30/20/10 replies per level
  - Twitter: 1500 char chunks, 200 overlap, ALL root replies, 20 nested per conversation
  - **Rationale**: Categorization requires complete visibility; evidence gathering benefits from semantic search
- `UnifiedSolutionCrew`: **Context Chaining + Knowledge Sources** - Sequential tasks with automatic Pydantic passing
  - **Task 1 (solution_ideation)**: Pain point Knowledge Sources + metadata inputs → IdeaGenerationResult
  - **Task 2 (competitive_analysis)**: Context from Task 1 + competitor Knowledge Sources → CompetitiveAnalysisResult
  - **Task 3 (competitive_refinement)**: Context from Tasks 1 & 2 + guardrail validation → IdeaGenerationResult (enhanced)
  - **Task 4 (solution_selection)**: Context from Task 3 → SolutionSelection
  - **Rationale**: Context chaining preserves ALL 25+ SolutionIdea fields automatically, no manual formatting
- `SEOStrategyCrew`: **Knowledge Sources for Keywords** - 446+ keywords accessible via semantic search
  - Keywords formatted as tier-grouped content (Tier 1-4 sections)
  - Agents query by tier ("TIER 1", "quick win"), geography, or keyword text
  - Chunk size: 2000 chars (~40-50 keywords per chunk), 200 overlap
  - **Rationale**: Scales to 1000+ keywords, no prompt size limits, semantic search for targeting

### CrewAI Configuration Files

**agents.yaml**: Defines agent personas (role, goal, backstory)
**tasks.yaml**: Defines task instructions - some use direct inputs, others use knowledge sources

**PainPointCrew Task Pattern:**
- `categorize_content`: Receives full content via `{full_reddit_content}` and `{full_twitter_content}` placeholders
- `extract_pain_points` and `validate_pain_points`: Use knowledge sources with search strategies

When modifying tasks that use knowledge sources, include search strategy instructions:
```yaml
description: >
  **Search Strategy for Knowledge Sources:**
  - Search for problems: "frustration", "difficult", "can't"
  - Search for solutions: "using", "tried", "alternative to"
```

## Complete Pipeline Stages

The research pipeline includes main stages plus sub-stages for refinement and selection:

**Stage Flow:**
1. **Stage 1**: Niche validation via LLM
2-4. *(Reserved for future validation stages)*
5. **Stage 5**: Search & discover
   - Generates search queries with QueryGenerator
   - Validates thread relevance with ThreadRelevanceValidator (filters before scraping)
   - Collects Reddit posts (PRAW) and Twitter threads (twitter-api-client)
6. **Stage 6**: PainPointCrew analyzes social content (RAG-based)
7-8.75. **Stages 7-8.75**: UnifiedSolutionCrew (4-task pipeline with context chaining)
   - **Task 1**: Solution Ideation - generates 3-5 solutions (brainstorm + evaluate + refine)
   - **Task 2**: Competitive Analysis - researches competitors per solution + gap analysis
   - **Task 3**: Competitive Refinement - enhances solutions with insights (guardrail validated)
   - **Task 4**: Solution Selection - scores and selects best solution
9. **Stage 9**: SEOStrategyCrew with keyword Knowledge Sources (4-task pipeline)
   - **Task 1**: Keyword Analysis & Tiering - semantic search across 446+ keywords
   - **Task 2**: Content & Technical Strategy - cluster architecture + technical SEO
   - **Task 3**: Implementation Planning - phased roadmap with metrics
   - **Task 4**: Final SEO Strategy Synthesis - complete strategy with long-term vision
   - **Stage 9.5** (conditional): SEO refinement with keyword data
   - **Stage 9.75** (conditional): Data source research if `requires_data_aggregation=True`
10. **Stage 10**: Final report synthesis via LLM

**Key Decision Points:**
- Stages 7-8.75: Unified crew with sequential tasks + context chaining
- Stage 9.5: Triggered if `SEO_REFINEMENT_ENABLED=True`
- Stage 9.75: Triggered if selected solution has `requires_data_aggregation=True`

## Common Development Commands

```bash
# Installation
uv venv && source .venv/bin/activate
uv pip install -e .

# Run research
python -m nicheiq.main --niche "AI tools for content creators"
python -m nicheiq.main --niche "Your niche" --output ./custom_output --log-level DEBUG

# Run research with project type constraints
python -m nicheiq.main --niche "expat relocation" --project-types directory,aggregator
# Valid types: saas, directory, aggregator, comparison-tool, marketplace

# Checkpoint/Resume commands
python -m nicheiq.main --niche "AI tools" --resume  # Auto-resume from latest checkpoint
python -m nicheiq.main --niche "AI tools" --checkpoint ./output/checkpoints/checkpoint_ai_tools_20250110_143052  # Resume from specific checkpoint
python -m nicheiq.main --list-checkpoints  # List all checkpoints
python -m nicheiq.main --niche "AI tools" --list-checkpoints  # List checkpoints for specific niche
python -m nicheiq.main --niche "AI tools" --no-checkpoint  # Disable checkpointing

# Testing
pytest
pytest --cov=src/nicheiq --cov-report=term-missing

# Code quality
black src/ tests/
ruff check src/ tests/
mypy src/

# Verify API credentials
python check_setup.py

# Validate report for data accuracy
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```

## Key Technical Patterns

### 1. Async Flow Execution

**Problem**: Twitter-api-client uses `asyncio.run()` internally, causing nested event loop errors.
**Solution**: Use thread executor to run async Twitter collection:

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

### 3. CrewAI Context Chaining (Best Practice)

**Problem**: Manual text formatting between stages causes field loss and maintenance burden.
**Solution**: Use `output_pydantic` + `context=[previous_task]` for automatic field preservation:

```python
from crewai import Agent, Crew, Task

@task
def task_1_generate_data(self) -> Task:
    """Generate structured data."""
    return Task(
        config=self.tasks_config["task_1"],
        agent=self.agent_1(),
        output_pydantic=MyDataModel,  # Pydantic model output
    )

@task
def task_2_enhance_data(self) -> Task:
    """Enhance data from task_1."""
    return Task(
        config=self.tasks_config["task_2"],
        agent=self.agent_2(),
        context=[self.task_1_generate_data()],  # Automatic Pydantic passing
        output_pydantic=MyEnhancedDataModel,
    )

@task
def task_3_final_processing(self) -> Task:
    """Process enhanced data from task_2."""
    return Task(
        config=self.tasks_config["task_3"],
        agent=self.agent_3(),
        context=[self.task_2_enhance_data()],  # Chain continues
        output_pydantic=FinalResult,
    )
```

**Benefits**:
- Automatic field preservation (all 25+ fields of SolutionIdea preserved)
- No manual JSON formatting between tasks
- Type safety via Pydantic
- Follows CrewAI official documentation best practices

**Example**: UnifiedSolutionCrew uses 4-task chain with context passing (unified_solution_crew.py:410-450).

### 4. Guardrails for Field Validation

**Problem**: Agents may drop solutions or nullify fields during refinement.
**Solution**: Add guardrail functions that validate task output before proceeding:

```python
def _validate_no_field_loss(self, task_output) -> tuple:
    """
    Guardrail to ensure no data loss during task execution.

    Returns:
        (True, result) if valid, (False, error_message) if validation fails
    """
    try:
        result = task_output.pydantic

        # Check solution count matches input
        if len(result.solution_ideas) != self._expected_solution_count:
            return (False, f"Solution count mismatch: expected {self._expected_solution_count}, got {len(result.solution_ideas)}")

        # Validate required fields
        for idea in result.solution_ideas:
            if idea.market_fit_score is None:
                return (False, f"Missing market_fit_score in {idea.solution_name}")

        return (True, result)  # All checks passed
    except Exception as e:
        return (False, f"Validation error: {str(e)}")

@task
def competitive_refinement_task(self) -> Task:
    """Task with guardrail validation."""
    return Task(
        config=self.tasks_config["competitive_refinement"],
        agent=self.solution_refiner(),
        context=[self.solution_ideation_task(), self.competitive_analysis_task()],
        output_pydantic=IdeaGenerationResult,
        guardrail=self._validate_no_field_loss,  # Auto-validates and retries on failure
    )
```

**Benefits**:
- Automatic retry on validation failure
- Prevents field loss before it propagates downstream
- Type-safe validation with Pydantic
- Clear error messages for debugging

**Example**: UnifiedSolutionCrew uses guardrail on Task 3 (competitive refinement) to ensure no solutions dropped (unified_solution_crew.py:460-510).

### 5. Knowledge Sources for Large Datasets

**Problem**: Passing 446+ keywords as text string causes prompt size issues and prevents semantic search.
**Solution**: Use Knowledge Sources (RAG) for datasets >400 items:

```python
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

# Format keywords as tier-grouped content for semantic search
keyword_content = self._format_keywords_for_knowledge(enriched_keywords)
# Content structure:
# [TIER 1 - QUICK WIN OPPORTUNITIES]
# High volume, low competition keywords...
# - **keyword** | Volume: X/mo | Competition: LOW (15) | Opportunity: 120.5
# [TIER 2 - STRATEGIC GROWTH]
# ...

keyword_knowledge = StringKnowledgeSource(
    content=keyword_content,
    chunk_size=2000,      # ~40-50 keywords per chunk
    chunk_overlap=200     # Preserve tier boundaries
)

crew = Crew(
    agents=[self.keyword_strategist()],
    tasks=[self.analyze_keywords_task()],
    knowledge_sources=[keyword_knowledge],  # RAG-based access
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"}
    }
)
```

**Task Description Search Strategy**:
```yaml
description: >
  **ENRICHED KEYWORDS DATA (via Knowledge Sources - RAG):**

  You have access to {enriched_keywords_count} keywords via semantic search.

  **Search Strategy for Knowledge Sources:**
  - To find high-priority keywords: Search for "TIER 1", "quick win", "low competition"
  - To find strategic keywords: Search for "TIER 2", "strategic growth"
  - To explore geographic patterns: Search for country/city names
  - To get specific keyword data: Search for exact keyword phrases
```

**Benefits**:
- Scales to 1000+ keywords (no prompt size limits)
- Semantic search for targeted queries (e.g., "quick win keywords in Tier 1")
- Efficient RAG retrieval (only relevant chunks passed to agent)
- Cost-effective embeddings (~$0.0001 per 1,000 tokens)

**Examples**:
- SEOStrategyCrew: 446+ keywords accessible via semantic search (seo_strategy_crew.py:459-623)
- UnifiedSolutionCrew: Pain points (3-5 quotes each) + competitor intelligence (unified_solution_crew.py:90-265)

### 6. Knowledge Source Preparation (Legacy Pattern - Prefer Context Chaining)

Format content with metadata headers for semantic search:

```python
def _prepare_reddit_content(self) -> str:
    formatted = []
    for post in self.reddit_posts:
        formatted.append(f"""[PLATFORM: REDDIT]
[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{post.selftext}

---
## Discussion ({len(post.comments)} comments):

{self._format_comments_with_replies(post.comments)}
""")
    return "\n\n===\n\n".join(formatted)
```

Attach to crew:

```python
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

knowledge_source = StringKnowledgeSource(
    content=formatted_content,
    chunk_size=2000,      # Adjust based on content type
    chunk_overlap=300     # Preserve context
)

return Crew(
    agents=self.agents,
    tasks=self.tasks,
    knowledge_sources=[knowledge_source],
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"}
    }
)
```

### 4. Parallel Crew Execution

CompetitiveCrew supports parallel solution analysis:

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

### 5. Cost Optimization

**DataForSEO Batching**: Process up to 1,000 keywords per request:

```python
for batch_start in range(0, len(all_keywords), batch_size):
    batch = all_keywords[batch_start:batch_start + batch_size]
    # Single API call for entire batch
```

**Quality Filtering**: Apply thresholds early to reduce processing:
- Reddit: `MIN_REDDIT_UPVOTES`, `MIN_REDDIT_COMMENTS`, `MIN_COMMENT_LENGTH`, `MIN_COMMENT_SCORE`
- Twitter: `MIN_TWITTER_LIKES`, `MIN_TWITTER_REPLIES`
- Keywords: `KEYWORD_MIN_SEARCH_VOLUME`, `KEYWORD_MAX_COMPETITION`

### 6. Query Generation Pattern

Generic, niche-agnostic search queries (no brand names):

```python
# Generic patterns (70-80% of queries)
"[niche activity] problems"
"[niche role] challenges"
"frustrated with [niche task]"

# Scenario-based (20-30% of queries)
"struggling to [specific outcome]"
"tired of [pain point]"
```

See `src/nicheiq/utils/helpers.py` QueryGenerator for implementation.

### 7. Thread Relevance Validation

**Problem**: Search results include many false positives (keyword matches in wrong context).

**Solution**: Batch validate search results (title + snippet) before expensive scraping:

```python
from nicheiq.utils.helpers import ThreadRelevanceValidator

validator = ThreadRelevanceValidator()  # Uses THREAD_VALIDATION_LLM
validated = validator.validate_batch(
    niche_description="your niche",
    search_results=search_results,  # List[SearchResultItem]
    batch_size=10  # Validate 10 at a time
)

# Returns: List[(SearchResultItem, is_relevant: bool)]
relevant_results = [result for result, is_relevant in validated if is_relevant]
```

**Benefits:**
- Reduces scraping API costs by filtering before collection
- Improves signal-to-noise ratio in pain point analysis
- Uses cheaper model (gpt-4o-mini) for cost efficiency
- Batches validation requests (10 results per API call)

**Configuration:** Set `THREAD_VALIDATION_LLM` in .env (default: gpt-4o-mini)

### 8. Avoiding Template Variable Parsing in Task Descriptions

**Problem**: CrewAI parses ALL `{variable}` patterns in task descriptions as template variables requiring substitution at kickoff time. Using curly braces for examples or instructions causes `KeyError: Template variable 'variable_name' not found in inputs dictionary`.

**Common Errors**:
```yaml
# ❌ WRONG - CrewAI tries to substitute {solution_name}
description: >
  Search for competitors using: "{solution_name} competitors"

# ❌ WRONG - CrewAI expects {niche} in inputs
description: >
  Find tools in {niche} category

# ❌ WRONG - Even in comments/examples
description: >
  # Example search: "{keyword} alternatives"
```

**Solution**: Use square brackets `[ ]`, angle brackets `< >`, or descriptive text instead:

```yaml
# ✅ CORRECT - Square brackets for placeholders
description: >
  Search for competitors using: "[solution name] competitors"
  Find tools in [niche] category
  Example search: "[keyword] alternatives"

# ✅ CORRECT - Angle brackets
description: >
  Search pattern: <solution_name> + "competitors"

# ✅ CORRECT - Descriptive text
description: >
  Use the solution's name from Task 1 output to search for competitors
```

**When {curly braces} ARE needed**:
Only use `{variable}` when the variable is **actually provided in crew.kickoff(inputs={...})**:

```python
# Python - provide the variable
crew.kickoff(inputs={
    "niche": "AI tools",
    "solution_count": 5
})
```

```yaml
# YAML - can now use these variables
description: >
  Analyze {solution_count} solutions in the {niche} niche.
```

**Historical Issues**:
- unified_solution_tasks.yaml line 148: `"{solution_name} competitors"` → Changed to `"[solution name] competitors"`
- Similar errors occurred multiple times during development

**Rule of Thumb**: If it's instructional text, example syntax, or refers to data from context/previous tasks → use `[ ]` not `{ }`

## Checkpoint & Resume System

NicheIQ implements a folder-based checkpoint system to recover from failures and avoid wasting API costs.

### Architecture

**Checkpoint Structure:**
```
output/checkpoints/
└── checkpoint_{niche_slug}_{timestamp}/
    ├── metadata.json                           # Run metadata (niche, timestamps, current_stage)
    ├── stage_5_social_content.json            # Reddit/Twitter data
    ├── stage_6_pain_points.json               # Pain point analysis
    ├── stage_7_solutions.json                 # Solution ideas
    ├── stage_8_competitive.json               # Competitive landscape
    ├── stage_8_75_solution_selection.json     # Selected solution
    ├── stage_9_seo_strategy.json              # SEO strategy
    └── stage_9_75_data_sources.json           # Data source research (conditional)
```

**Checkpoint Timing:** Saves after 7 critical stages:
1. **Stage 5** (social content) - Saves Reddit/Twitter scraping
2. **Stage 6** (pain points) - Saves $0.15-0.40 in agent costs
3. **Stage 7** (solutions) - Saves $0.10-0.30 in creative reasoning
4. **Stage 8** (competitive) - Saves $0.20-0.60 in parallel execution
5. **Stage 8.75** (selection) - Enables SEO re-runs
6. **Stage 9** (SEO strategy) - Saves $0.15-0.60 + DataForSEO costs
7. **Stage 9.75** (data sources) - Conditional, saves $0.10-0.30

### Usage

**Auto-resume from latest checkpoint:**
```bash
python -m nicheiq.main --niche "AI tools" --resume
```

**Resume from specific checkpoint:**
```bash
python -m nicheiq.main --niche "AI tools" --checkpoint ./output/checkpoints/checkpoint_ai_tools_20250110_143052
```

**List available checkpoints:**
```bash
python -m nicheiq.main --list-checkpoints                  # All checkpoints
python -m nicheiq.main --niche "AI tools" --list-checkpoints  # Filter by niche
```

**Disable checkpointing:**
```bash
python -m nicheiq.main --niche "AI tools" --no-checkpoint
```

### Configuration

Set in `.env`:
```bash
CHECKPOINT_ENABLED=true  # Enable/disable checkpointing
CHECKPOINT_MAX_AGE_DAYS=7  # Auto-cleanup old checkpoints
CHECKPOINT_AUTO_CLEANUP=true  # Clean old checkpoints on startup
```

### Resume Logic

When resuming, the flow:
1. Detects latest checkpoint for niche (or uses explicit path)
2. Validates niche matches
3. Reconstructs ResearchState from checkpoint folder
4. Executes remaining stages starting from `current_stage`

**Note:** Resume skips completed stages automatically based on `current_stage` field in metadata.

### Error Recovery

The checkpoint system includes automatic retry with exponential backoff for API failures:
- **Retryable errors**: `TimeoutError`, `ConnectionError`
- **Max retries**: 3 attempts
- **Backoff**: Exponential (2^attempt seconds)
- **Non-retryable errors**: Other exceptions fail immediately

### Benefits

- **Cost savings**: $0.50-$2.00 per failed run avoided
- **Time savings**: 5-15 minutes per recovery
- **Debugging**: Inspect individual stage outputs
- **Flexibility**: Resume from any checkpoint, manual or auto

### Troubleshooting

**Checkpoint not found:**
- Ensure `CHECKPOINT_ENABLED=true` in .env
- Check `output/checkpoints/` directory exists
- Verify niche slug matches (use `--list-checkpoints` to see available checkpoints)

**Resume skips stages unexpectedly:**
- Check `metadata.json` in checkpoint folder for `current_stage` value
- Stages with `current_stage <= N` are skipped
- Use `--checkpoint` with specific folder to control which checkpoint is used

**Checkpoint cleanup:**
- Old checkpoints (>7 days by default) are auto-deleted on startup
- Disable with `CHECKPOINT_AUTO_CLEANUP=false`
- Adjust age with `CHECKPOINT_MAX_AGE_DAYS=N`

## Important File Locations

**Core Pipeline:**
- `src/nicheiq/flows/research_flow.py` - Main 10-stage orchestrator (839 lines)

**Crews (Stages 6-8):**
- `src/nicheiq/crews/pain_point_crew.py` - Social analysis with Knowledge Sources
- `src/nicheiq/crews/idea_generation_crew.py` - Solution ideation
- `src/nicheiq/crews/competitive_crew.py` - Competitive research with optional KS

**Configuration:**
- `src/nicheiq/crews/config/agents.yaml` - Agent definitions
- `src/nicheiq/crews/config/tasks.yaml` - Task specs with search strategies (670 lines)
- `src/nicheiq/config/settings.py` - Centralized settings with pydantic-settings

**Data Models:**
- `src/nicheiq/models/research_state.py` - Flow state and final report
- `src/nicheiq/models/pain_point.py` - Pain point analysis
- `src/nicheiq/models/solution_idea.py` - Solution concepts (includes `requires_data_aggregation`)
- `src/nicheiq/models/competitor.py` - Competitive analysis
- `src/nicheiq/models/keyword_data.py` - Keyword research
- `src/nicheiq/models/social_content.py` - Reddit/Twitter content

**Tools:**
- `src/nicheiq/tools/reddit_tool.py` - PRAW-based collector
- `src/nicheiq/tools/twitter_tool.py` - twitter-api-client wrapper (handles async issues)
- `src/nicheiq/tools/dataforseo_tool.py` - Keyword research with batching

## Data Aggregation Pattern

SolutionIdea model includes data sourcing tracking:

```python
class SolutionIdea(BaseModel):
    solution_name: str
    requires_data_aggregation: bool  # Set by agents
    data_sources: List[str]  # Specific APIs, databases, web scraping targets
    # ...
```

Agents in `idea_generation_crew.py` assess if solution needs external data aggregation and list specific sources. Final report includes `data_sourcing_recommendations` section.

## API Keys & Environment

Required:
- `OPENAI_API_KEY` - GPT-4o for agent reasoning
- `CHROMA_OPENAI_API_KEY` - **CRITICAL**: Required for CrewAI knowledge sources (RAG). Set to same value as `OPENAI_API_KEY`
- `SERPER_API_KEY` - Google search
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` - PRAW
- `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` - Keyword research

Optional:
- `TWITTER_USERNAME`, `TWITTER_PASSWORD`, `TWITTER_EMAIL` - Authenticated scraping (guest mode fallback)
- `CREWAI_API_KEY` - CrewAI+ features

Twitter credentials are cached in `data/twitter_cookies.json` after first successful login.

**Important Notes:**
- Without `CHROMA_OPENAI_API_KEY`, knowledge sources will silently fail with "Failed to init knowledge" warnings
- This is a CrewAI 1.3.0 requirement for ChromaDB-based vector storage

## Advanced Configuration

### Multi-Model Strategy

NicheIQ uses different models for different tasks to optimize cost vs quality:

- `OPENAI_MODEL_NAME` (gpt-4o): Default for general agent reasoning
- `FUNCTION_CALLING_LLM` (gpt-4o-mini): Tool/function calls (cost optimization)
- `CONTENT_ANALYSIS_LLM` (gpt-4o): Content categorization (quality critical)
- `THREAD_VALIDATION_LLM` (gpt-4o-mini): Relevance filtering (cost optimization)
- `BRAINSTORM_LLM` (gpt-4o): Solution ideation (supports o1-mini, claude-3-5-sonnet)

**Pattern:** Use gpt-4o-mini for deterministic/simple tasks, gpt-4o for creative/complex reasoning.

### Twitter Control

- `ENABLE_TWITTER` (bool): Set to False to skip Twitter entirely (saves cost if Twitter data not critical)
- Twitter credentials are optional - guest mode is used as fallback

### Reddit Comment Depth

- `REDDIT_COMMENT_LIMIT` (int or None): Controls MoreComments expansion
  - `None`: Fetch ALL comments (most comprehensive, slowest)
  - `32`: Fetch most comments (good balance)
  - `0`: Top-level comments only (fastest, may miss deep discussions)

### SEO Refinement (Stage 9.5)

Controls how keyword data refines solution scores:
- `SEO_REFINEMENT_ENABLED`: Toggle refinement stage (default: True)
- `SEO_REFINEMENT_VOLUME_BASELINES`: Expected volumes by project type for scoring
- Refinement updates: `seo_scalability_score_refined`, `estimated_cac_organic_refined`

### Keyword Enrichment (Stage 9.5 Iterative)

Controls iterative keyword expansion to reach target coverage:
- `KEYWORD_ENRICHMENT_TARGET_COUNT`: Target keyword count (default: 150)
- `KEYWORD_ENRICHMENT_MAX_ROUNDS`: Safety limit on iterations (default: 5)
- `KEYWORD_ENRICHMENT_MIN_COVERAGE`: Topic cluster coverage requirement (default: 0.7)
- Cost: ~$0.01-0.05 per enrichment round

## Debugging Tips

**Enable verbose logging:**
```bash
python -m nicheiq.main --niche "..." --log-level DEBUG
```

**Check crew execution:**
- Crews log agent reasoning steps when `verbose=True`
- Knowledge source queries are logged at DEBUG level
- Check `./output/logs/nicheiq_YYYY-MM-DD.log`

**Validate embeddings:**
- Only crews with knowledge sources trigger embeddings
- Embeddings are cached by CrewAI - rerunning same crew is efficient
- Cost: ~$0.0001 per 1,000 tokens with text-embedding-3-small

**Common issues:**
- **"Failed to init knowledge" warning**: Missing `CHROMA_OPENAI_API_KEY` - set it to same value as `OPENAI_API_KEY`
- **No embeddings created**: Check OpenAI dashboard for embedding API calls - if missing, verify `CHROMA_OPENAI_API_KEY` is set
- Nested event loop: Twitter scraper issue - handled by thread executor pattern
- "No module named 'nicheiq'": Run `pip install -e .`
- Twitter JSON decode error: Account rate limited or tweet private/deleted
- DataForSEO insufficient credits: Reduce `KEYWORD_MIN_SEARCH_VOLUME`

**Report validation:**
- Run `validate_report.py` after research runs to detect hallucinations and data accuracy issues
- Checks for pain point conflation, score rounding, CAC accuracy, page count accuracy, and competition intensity

## Performance Expectations

- **Duration**: 5-15 minutes per niche
- **Cost**: $0.50-$2.20 per research run
  - OpenAI (GPT-4o): $0.50-$2.00
  - Serper: $0.01-$0.05
  - DataForSEO: $0.01-$0.10
  - Reddit/Twitter: Free

## When Modifying Crews

### Data Passing Validation Checklist

**CRITICAL:** When adding new crews or modifying existing ones, always verify that input data is properly passed to agents. Failure to do so can cause agents to operate blindly without access to critical data.

**Pre-Flight Checklist:**

1. **List all inputs** passed in `crew.kickoff(inputs={...})`
2. **Find task file** (tasks.yaml or crew-specific config file)
3. **Verify placeholders** - For each input key, ensure `{key}` appears in task description
4. **Test with missing data** - What happens if input is None or empty?
5. **Log input sizes** - Always log data sizes for debugging (e.g., "Processing 446 keywords", "Passing ~22,300 chars")
6. **Validate outputs** - Check that outputs contain expected data, not hallucinations

**Common Data Passing Patterns:**

**Pattern 1: Direct Injection (Small/Structured Data)**

Best for: Metadata, counts, names, scores, small lists

```python
# Python - seo_strategy_crew.py
inputs = {
    "solution_name": "ExpatEase",
    "niche": "expat relocation",
    "feature_count": 5
}
crew.kickoff(inputs=inputs)
```

```yaml
# tasks.yaml
description: >
  Analyze {solution_name} in the {niche} niche with {feature_count} features.
```

**Pattern 2: Formatted Strings (Medium Data)**

Best for: Keyword lists, pain points, solution summaries, competitive data

```python
# Python - idea_generation_crew.py
formatted_pain_points = "\n".join([
    f"**{p.pain_point_title}** (Severity: {p.severity_score}/10)\n"
    f"- {p.pain_point_description}\n"
    f"- Mentions: {p.total_mentions}"
    for p in high_priority_pain_points
])

inputs = {
    "high_priority_list": formatted_pain_points,
    "high_priority_count": len(high_priority_pain_points)
}
```

```yaml
# tasks.yaml
description: >
  Generate solutions for {high_priority_count} high-priority pain points:

  {high_priority_list}
```

**Example:** SEO Strategy crew formats 446 keywords as readable lines (~22K chars):
```python
keyword_lines = []
for i, k in enumerate(enriched_keywords, 1):
    keyword_lines.append(
        f"{i}. {keyword} | Vol: {search_volume:,} | Comp: {comp_label} ({comp_index}) | Opp: {opp_score:.1f}"
    )
enriched_keywords_text = "\n".join(keyword_lines)
inputs = {"enriched_keywords": enriched_keywords_text}
```

**Pattern 3: Knowledge Sources (Large/Unstructured Data)**

Best for: Social media discussions, full content with thousands of items, data requiring semantic search

```python
# Python - pain_point_crew.py (__init__)
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

formatted_content = self._prepare_reddit_content()  # Format with metadata headers
self.knowledge_sources = [
    StringKnowledgeSource(
        content=formatted_content,
        chunk_size=2000,
        chunk_overlap=300
    )
]

# In crew assembly
return Crew(
    agents=self.agents,
    tasks=self.tasks,
    knowledge_sources=self.knowledge_sources,  # RAG handles retrieval
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}}
)
```

```yaml
# tasks.yaml - No placeholder needed, use search strategy
description: >
  **Search Strategy for Knowledge Sources:**
  - To find frustrations: Search for "frustrated", "difficult", "can't"
  - To find solutions: Search for "using", "tried", "alternative to"

  Analyze social media discussions to extract pain points.
```

**Anti-Patterns to Avoid:**

❌ **Passing data without placeholder:**
```python
# Python
crew.kickoff(inputs={"keywords": keyword_list})  # ← Data passed

# tasks.yaml
description: >
  Analyze keywords and create strategy.  # ← NO {keywords} placeholder!
```
**Result:** Agent never sees the keywords, operates blindly or hallucinates data.

❌ **Placeholder without data:**
```python
# Python
crew.kickoff(inputs={"solution_name": "ExpatEase"})  # ← Missing "keywords" key

# tasks.yaml
description: >
  Analyze {solution_name} with keywords: {keywords}  # ← Placeholder exists but no data!
```
**Result:** CrewAI error or placeholder appears as literal "{keywords}" in prompt.

❌ **Mismatched naming:**
```python
# Python
crew.kickoff(inputs={"keyword_list": data})  # ← Key is "keyword_list"

# tasks.yaml
description: >
  Analyze these keywords: {keywords}  # ← Placeholder is "keywords" (mismatch!)
```
**Result:** Data not injected, placeholder appears as literal "{keywords}".

❌ **Passing raw list/dict without formatting:**
```python
# Python
crew.kickoff(inputs={"keywords": [{"keyword": "visa", "vol": 1900}, ...]})  # ← Raw list

# tasks.yaml
description: >
  Analyze keywords: {keywords}
```
**Result:** Agent receives Python list representation as string: `"[{'keyword': 'visa', 'vol': 1900}, ...]"` - hard to parse.

**Real-World Example: SEO Strategy Bug (Fixed)**

**The Bug:**
```python
# Python - seo_strategy_crew.py (OLD CODE)
crew.kickoff(inputs={
    "enriched_keywords": enriched_keywords_formatted,  # ← 446 keywords passed
    "enriched_keywords_count": 446
})

# tasks.yaml (OLD)
description: >
  Apply methodology to {enriched_keywords_count} keywords.  # ← NO {enriched_keywords} placeholder!
```
**Impact:** Agent knew "there are 446 keywords" but couldn't see any of them. 438 keywords (98%) were discarded.

**The Fix:**
```python
# Python - seo_strategy_crew.py (NEW CODE)
keyword_lines = [f"{i}. {keyword} | Vol: {vol:,} | Comp: {comp} | Opp: {opp:.1f}" for ...]
enriched_keywords_text = "\n".join(keyword_lines)
crew.kickoff(inputs={
    "enriched_keywords": enriched_keywords_text,  # ← Formatted as readable text
    "enriched_keywords_count": 446
})

# tasks.yaml (NEW)
description: >
  Apply methodology to {enriched_keywords_count} keywords.

  **ENRICHED KEYWORDS DATA:**
  {enriched_keywords}  # ← Added placeholder, now all 446 keywords visible!
```

**Validation Tips:**

1. **Check logs:** Agent logs should reference specific data values (e.g., "Selected keyword: visa application process")
2. **Review outputs:** If outputs contain generic placeholders or hallucinated data, check for missing placeholders
3. **Test incrementally:** Start with small data (5-10 items) to verify injection before scaling to production size
4. **Use validation models:** Add `@model_validator` to Pydantic models to check data completeness

### Adding New Crews

**Adding new crew:**
1. Extend `@CrewBase` class
2. Define agents with `@agent` decorator
3. Define tasks with `@task` decorator (use `context=` for dependencies)
4. Define crew assembly with `@crew` decorator
5. **Apply Data Passing Checklist** (see above) to verify all inputs are properly injected
6. Update `research_flow.py` to integrate new stage

**Modifying knowledge sources:**
1. Adjust `chunk_size` and `chunk_overlap` based on content structure
2. Update task descriptions with search strategy instructions
3. Test semantic search quality - may need prompt tuning
4. No limits on content size - RAG scales efficiently

**Changing agent behavior:**
1. Edit `agents.yaml` for persona changes (role, goal, backstory)
2. Edit `tasks.yaml` for task instruction changes
3. Add search strategies if using knowledge sources
4. Test with `--log-level DEBUG` to see agent reasoning

**Using output_pydantic with complex models:**

CrewAI's `output_pydantic` parameter enables validation but has a known limitation: Pydantic `Field(description=...)` metadata is **NOT automatically injected into LLM prompts** (GitHub Issue #1338). This can cause agents to return schema definitions instead of populated data.

**Required workaround:**
1. Add `output_pydantic=ModelName` to task definition
2. In task YAML config, add explicit field guidance in `expected_output`:
   - List required fields with descriptions
   - Provide structure example for nested models
   - Add "DO NOT output schema" warnings if risk of confusion
3. For tasks with `context=[previous_tasks]`, add context extraction instructions:
   ```yaml
   description: >
     **HOW TO ACCESS CONTEXT:**
     Task N output is available in your context. Extract:
     - From Task N: field_a, field_b (PRESERVE these exactly)
     - Use to enhance: field_c, field_d

     Your output must contain ACTUAL VALUES from context, enhanced with new analysis.
   ```
4. Rationale: CrewAI doesn't auto-inject Pydantic field descriptions (GitHub #1338)
5. See `PROMPT_OPTIMIZATION_BEST_PRACTICES.md` Section 5.3 for detailed patterns

**Example:** `src/nicheiq/crews/config/unified_solution_tasks.yaml` - competitive_refinement task demonstrates all patterns (context extraction + field requirements + structure example).

## CrewAI Best Practices

### Knowledge Sources (RAG)

**When to Use:**
- Large datasets (400+ items) that need semantic search
- Unstructured content where agents query selectively
- Social media discussions, documents, large text corpora

**Pattern:**
- Add metadata headers for better retrieval: `[POST_ID: ...]`, `[PLATFORM: ...]`, `[SCORE: ...]`
- Set at crew level for shared context, agent level for specialization
- Configure chunking: `chunk_size=2000, chunk_overlap=300` (adjust for content type)
- Use cost-effective embeddings: `text-embedding-3-small`

**Example:**
```python
knowledge_source = StringKnowledgeSource(
    content=formatted_content,
    chunk_size=2000,
    chunk_overlap=300
)
crew = Crew(
    agents=[agent1, agent2],
    knowledge_sources=[knowledge_source],
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}}
)
```

### Structured Output (Pydantic)

**Best Practices:**
- Use `output_pydantic=ModelClass` for type-safe, validated outputs
- Use `Optional[Type] = Field(default=None)` for conditional data (prevents validation errors)
- Add explicit field requirements in task `expected_output` (CrewAI doesn't auto-inject Field descriptions)
- For context chaining, add extraction instructions showing which fields to copy from previous tasks

**Anti-Pattern:** ❌ Assuming Pydantic Field descriptions appear in agent prompts automatically

**Correct Pattern:** ✅ Document expected fields in task YAML `expected_output` section

### Flow State Management

**Use Structured State:**
- Define Pydantic BaseModel for type safety: `class MyFlow(Flow[MyState]):`
- Access via `self.state.field_name`
- Avoid unstructured dict state for complex flows

**Generator Pattern:**
- Extract from flow state in separate methods
- Return `Optional[Model]` for graceful degradation
- Use try/except with logger.warning for failures

**Example:**
```python
class ResearchFlow(Flow[ResearchState]):
    def _generate_section(self) -> Optional[SectionModel]:
        if not self.state.required_data:
            return None
        try:
            return SectionModel(...)
        except Exception as e:
            logger.warning(f"Failed: {e}")
            return None
```

### Context Chaining

**Pattern:** Pass complete Pydantic objects between sequential tasks
- Use `context=[previous_task]` for dependencies
- Use `output_pydantic=Model` on source task
- Agent automatically receives serialized context
- Preserves all fields without manual formatting

**Benefit:** Avoids field loss when passing complex objects between tasks

### Task Configuration

**Clear Expectations:**
- Write specific `expected_output` with field structure
- For Pydantic outputs, list required fields with descriptions
- Add search strategies for knowledge source queries
- Include examples for complex formats

**Source Attribution:**
- When agents extract from sources, request source IDs in output
- Format sources with identifiers: `[POST_ID: abc123]`
- Map extracted data back to sources in Pydantic models

### Memory & Caching

**Enable When:**
- Agents need context from previous runs (long-term memory)
- Tasks within run build on each other (short-term memory)
- Repeated calls to expensive operations (caching)

**Configure:**
```python
crew = Crew(
    agents=[...],
    memory=True,  # Enable all types
    cache=True    # Cache LLM responses
)
```

### Error Handling

**Graceful Degradation:**
- Use Optional fields for conditional sections
- Log warnings instead of raising exceptions for non-critical failures
- Provide fallback values or skip sections when data unavailable

**Validation:**
- Add guardrails to tasks: `guardrail=validation_function`
- Return `(True, result)` for success, `(False, error_msg)` for retry

### References

- Official Docs: https://docs.crewai.com/
- Knowledge Sources: https://docs.crewai.com/en/concepts/knowledge
- Structured Output: https://docs.crewai.com/en/concepts/tasks
- Flow State: https://docs.crewai.com/en/guides/flows/mastering-flow-state

## Output Structure

```
output/
├── final_report_YYYYMMDD_HHMMSS.json  # Synthesized report (enhanced with 6 new sections)
├── research_state_raw_YYYYMMDD_HHMMSS.json  # Complete state dump
├── checkpoints/                       # Checkpoint data for resume
│   └── checkpoint_{niche}_{timestamp}/
│       ├── metadata.json
│       ├── stage_5_social_content.json
│       ├── stage_6_pain_points.json
│       ├── stage_7_solutions.json
│       └── ...
└── logs/
    └── nicheiq_YYYY-MM-DD.log  # Detailed execution logs
```

### Final Report Structure

The final report (FinalReport model) includes:

**Core Sections (Existing):**
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

**Enhanced Sections (NEW - Phase 3):**

1. **research_metadata** (ResearchMetadata):
   - Reddit posts analyzed count
   - Twitter threads analyzed count
   - Top 10 subreddit breakdown with post counts
   - Collection date and data size (MB)
   - **Purpose**: Establishes research credibility and scope transparency

2. **alternative_solutions** (List[AlternativeSolution]):
   - Top 2 runner-up solutions with full summaries
   - Market fit, feasibility, competitive advantage, SEO scores
   - Key differentiator and best-suited-for guidance
   - Pivot trigger conditions
   - **Purpose**: Provides fallback options if primary solution fails validation

3. **competitive_landscape_matrix** (CompetitiveLandscapeMatrix):
   - All solutions analyzed (cross-solution view)
   - Competitor overlap analysis (multi-solution competitors)
   - Competitive intensity by solution
   - Strategic market insight
   - **Purpose**: Reveals platform players and competitive patterns across solution portfolio

4. **evidence_appendix** (EvidenceAppendix):
   - Top 10 Reddit threads by engagement score
   - Pain point quote sources with post IDs, subreddits, scores
   - Traceability from pain point → quote → original post
   - **Purpose**: Enables validation and drill-down to source data

5. **data_infrastructure_roadmap** (DataInfrastructureRoadmap):
   - 3-phase implementation plan (MVP, Growth, Scale) with structured milestones
   - Data sources per phase (linked to priority evaluation)
   - Monthly cost estimates per phase with scaling projections
   - Key risks and mitigation strategies per phase
   - Cost scaling insight summary
   - **Enhancement**: Now derived from structured RoadmapPhase objects with fallback strategies
   - **Purpose**: Surfaces hidden cost escalation risks and implementation timeline with actionable fallbacks

6. **decision_framework** (DecisionFramework):
   - Go criteria (3-4 conditions for proceeding)
   - No-go criteria (3-4 conditions for stopping)
   - Pivot triggers (conditions for switching to alternatives)
   - Each criterion includes condition + rationale
   - **Purpose**: Actionable decision-making rules for stakeholders

7. **content_categorization** (ContentCategorizationReport):
   - Executive summary of discussion landscape and findings
   - 5-10 theme categories with definitions, frequency, user segments, and quotes
   - 4-8 user segment profiles with primary concerns and mention frequency
   - Discussion quality assessment (engagement, depth, authenticity)
   - Overall quality rating with justification
   - **Purpose**: Provides thematic context for pain points, reveals user segment priorities and discussion patterns from Stage 6 Task 1

**Data Source Research (Stage 9.75 - Conditional):**

When selected solution has `requires_data_aggregation=True`, Stage 9.75 researches data sources.

**Enhanced Preservation:**
- Task 2 evaluation preserved in `source_evaluation` field within `DataSourceResearchResult`
- Priority-grouped sources (HIGH/MEDIUM/LOW) with quality metrics (coverage, freshness, complexity, cost, quality assessment)
- Per-source risk identification and mitigation strategies
- Structured 3-phase roadmap in `implementation_phases` (replaces text-only implementation_roadmap)
- Enables priority-based decision making, cost forecasting, and fallback planning
- Data preservation: 40-50% → **85-90%** of Task 2 evaluation details

**Data Preservation Rate**: With enhanced sections, final report preserves ~60-70% of checkpoint data (up from ~5-10%)

**Source Attribution**: Pain points now include `source_post_ids` and `source_engagement_metrics` fields linking to original Reddit/Twitter posts
