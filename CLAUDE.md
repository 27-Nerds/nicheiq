# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NicheIQ is an autonomous AI-powered market research agent that transforms social media discussions (Reddit, Twitter) into validated SaaS business opportunities through a 10-stage automated pipeline. Built with CrewAI, it combines Flow-based orchestration with specialized multi-agent Crews.

## Architecture

### Core Design Pattern: Hybrid Flow + Specialized Crews

```
ResearchFlow (Main Orchestrator - research_flow.py)
├── Stages 1-4: Niche validation (Flow methods)
├── Stage 5: Search & discover (Flow + SerperDevTool)
├── Stage 6: PainPointCrew (Knowledge Sources + RAG)
├── Stage 7: IdeaGenerationCrew (Traditional Inputs)
├── Stage 8: CompetitiveCrew (Optional Knowledge Sources)
├── Stage 9: Keyword validation (Flow + DataForSEOTool)
└── Stage 10: Final report (Flow + LLM synthesis)
```

### CRITICAL: Knowledge Sources vs Inputs Pattern

**When to use Knowledge Sources (RAG):**
- Large unstructured data (social media discussions)
- Content where agents need semantic search capability
- Data that agents query selectively during reasoning
- Examples: PainPointCrew (always), CompetitiveCrew (conditional)

**When to use Traditional Inputs:**
- Structured, pre-processed data
- Small metadata (counts, settings)
- Data that must be explicitly included in every task
- Examples: IdeaGenerationCrew, metadata in all crews

**Current Implementation:**
- `PainPointCrew`: **Hybrid Approach** - Full content inputs for first agent, Knowledge Sources for subsequent agents
  - **First Agent (content_researcher)**: Receives ALL formatted content via traditional inputs for comprehensive categorization
  - **Subsequent Agents (pain_point_analyst, validator)**: Use Knowledge Sources (RAG) for targeted evidence retrieval
  - Reddit: 2000 char chunks, 300 overlap, depth=3, up to 30/20/10 replies per level
  - Twitter: 1500 char chunks, 200 overlap, ALL root replies, 20 nested per conversation
  - **Rationale**: Categorization requires complete visibility; evidence gathering benefits from semantic search
- `CompetitiveCrew`: Optional Knowledge Sources with filtered competitor mentions
  - Only includes discussions mentioning tools/competitors/alternatives
  - Full content, no limits (RAG handles efficiently)
- `IdeaGenerationCrew`: Traditional inputs with structured pain point data

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

## Common Development Commands

```bash
# Installation
uv venv && source .venv/bin/activate
uv pip install -e .

# Run research
python -m nicheiq.main --niche "AI tools for content creators"
python -m nicheiq.main --niche "Your niche" --output ./custom_output --log-level DEBUG

# Testing
pytest
pytest --cov=src/nicheiq --cov-report=term-missing

# Code quality
black src/ tests/
ruff check src/ tests/
mypy src/

# Verify API credentials
python check_setup.py
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

### 3. Knowledge Source Preparation

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
- Reddit: `MIN_REDDIT_UPVOTES`, `MIN_REDDIT_COMMENTS`
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

## Performance Expectations

- **Duration**: 5-15 minutes per niche
- **Cost**: $0.50-$2.20 per research run
  - OpenAI (GPT-4o): $0.50-$2.00
  - Serper: $0.01-$0.05
  - DataForSEO: $0.01-$0.10
  - Reddit/Twitter: Free

## When Modifying Crews

**Adding new crew:**
1. Extend `@CrewBase` class
2. Define agents with `@agent` decorator
3. Define tasks with `@task` decorator (use `context=` for dependencies)
4. Define crew assembly with `@crew` decorator
5. Update `research_flow.py` to integrate new stage

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

## Output Structure

```
output/
├── final_report_YYYYMMDD_HHMMSS.json  # Synthesized report
├── research_state_raw_YYYYMMDD_HHMMSS.json  # Complete state dump
└── logs/
    └── nicheiq_YYYY-MM-DD.log  # Detailed execution logs
```

Final report includes:
- Niche description and validation
- Search queries and social content collected
- Pain points with severity/WTP scores
- Solution ideas with market fit scores
- Competitive landscape with gaps
- Keyword research with search volumes
- Data sourcing recommendations (for data aggregation solutions)
