# Features Guide

Advanced features and configuration options for NicheIQ power users.

## Table of Contents
- [Checkpoint & Resume System](#checkpoint--resume-system)
- [Token Monitoring & Cost Control](#token-monitoring--cost-control)
- [Multi-Model Strategy](#multi-model-strategy)
- [Context-Aware Query Generation](#context-aware-query-generation)

---

## Checkpoint & Resume System

Folder-based checkpoint system to recover from failures and avoid wasting API costs.

### How It Works

NicheIQ automatically saves state after each major stage to allow resuming from failures or interruptions.

**Folder Structure**:
```
output/checkpoints/checkpoint_{niche_slug}_{timestamp}/
├── metadata.json                          # Checkpoint metadata
├── stage_5_social_content.json           # Social media collection
├── stage_6_pain_points.json              # Pain point analysis
├── stage_7_solutions.json                # Solution ideation
├── stage_8_competitive.json              # Competitive analysis
├── stage_8_75_solution_selection.json    # Selected solution
├── stage_9_5a_seed_expansion.json        # Conceptual keywords
├── stage_9_5b_bulk_validation.json       # DataForSEO validated keywords
├── stage_9_5c_enrichment.json            # Enriched keywords
├── stage_9_seo_strategy.json             # SEO strategy
└── stage_9_75_data_sources.json          # Data sources (conditional)
```

### Usage

#### Auto-Resume (Recommended)
```bash
# Automatically finds and resumes from latest checkpoint for this niche
python -m nicheiq.main --niche "AI tools for content creators" --resume
```

#### List Available Checkpoints
```bash
python -m nicheiq.main --list-checkpoints
```

Output example:
```
Available checkpoints:
1. checkpoint_ai_tools_20250110_143052 (niche: AI tools for content creators)
   Last stage: stage_8_competitive
   Created: 2025-01-10 14:30:52

2. checkpoint_expat_relocation_20250109_091545 (niche: expat relocation)
   Last stage: stage_9_seo_strategy
   Created: 2025-01-09 09:15:45
```

#### Resume from Specific Checkpoint
```bash
python -m nicheiq.main --niche "AI tools" --checkpoint ./output/checkpoints/checkpoint_ai_tools_20250110_143052
```

#### Disable Checkpoints
```bash
python -m nicheiq.main --niche "AI tools" --no-checkpoint
```

### ChromaDB Collection Cleanup

Each research job creates ChromaDB collections for knowledge storage. These are automatically cleaned up on completion, but orphaned collections can accumulate if a job is killed (e.g., SIGKILL, OOM) before the cleanup runs.

> **Note:** This is primarily a local development concern. In production Docker, ChromaDB data is ephemeral (no named volume), so it's destroyed on every container restart.

#### List Collections (Dry Run)
```bash
python -m nicheiq.main --cleanup-collections
```

Output example:
```
ChromaDB storage path: /home/user/.local/share/nicheiq

Found 63 collection(s):

  Name                                                   Docs
  -------------------------------------------------- --------
  knowledge_audience_ai_prompt_management                 571
  knowledge_solution_indie_hackers                        623
  ...

  Total: 63 collections, 144613 documents

This was a dry run. To delete all collections, re-run with --force
```

#### Delete All Collections
```bash
# Ensure no research jobs are running first
python -m nicheiq.main --cleanup-collections --force
```

### Configuration

Add to `.env` file:

```bash
# Enable/disable checkpoint system
CHECKPOINT_ENABLED=true

# Maximum age of checkpoints before auto-cleanup (days)
CHECKPOINT_MAX_AGE_DAYS=7

# Automatically clean up old checkpoints
CHECKPOINT_AUTO_CLEANUP=true
```

### Benefits

1. **Cost Savings**: Resume from failure without re-running expensive stages ($0.50-$2.00 saved per failed run)
2. **Time Savings**: Skip completed stages (5-15 minutes saved)
3. **Debugging Aid**: Inspect intermediate results at each stage
4. **Fault Tolerance**: Handles API failures, network issues, crashes gracefully

### Troubleshooting Checkpoints

**Issue**: `--resume` doesn't find checkpoint

**Solutions**:
1. Verify `CHECKPOINT_ENABLED=true` in `.env`
2. Use `--list-checkpoints` to see available checkpoints
3. Ensure niche name matches exactly (case-sensitive)
4. Check checkpoint hasn't been auto-cleaned (older than `CHECKPOINT_MAX_AGE_DAYS`)

**Issue**: Checkpoint from partial/corrupted run

**Solution**:
```bash
# Delete corrupted checkpoint and start fresh
rm -rf output/checkpoints/checkpoint_niche_timestamp
python -m nicheiq.main --niche "your niche"
```

### Inspecting Checkpoints

View checkpoint metadata:
```bash
cat output/checkpoints/checkpoint_*/metadata.json | jq .
```

View specific stage data:
```bash
# Pain points
cat output/checkpoints/checkpoint_*/stage_6_pain_points.json | jq '.pain_points | length'

# Solution ideas
cat output/checkpoints/checkpoint_*/stage_7_solutions.json | jq '.solution_ideas[].solution_name'

# SEO keywords
cat output/checkpoints/checkpoint_*/stage_9_5c_enrichment.json | jq '.enriched_keywords | length'
```

---

## Token Monitoring & Cost Control

Monitor token usage with soft caps for cost visibility without hard failures.

### How It Works

`ContentTokenMonitor` tracks token usage across stages and warns when approaching limits.

### Features

1. **Accurate Token Counting**: Uses tiktoken for precise counts
2. **Cost Estimation**: Calculates estimated cost for GPT-4/GPT-4o models
3. **Warning Thresholds**: Logs warnings at configurable limits
4. **Soft Caps**: Optional critical warnings when exceeded
5. **No Pipeline Failures**: Monitoring only, never blocks execution

### Usage

```python
from nicheiq.utils.helpers import ContentTokenMonitor

monitor = ContentTokenMonitor()

# Log content stats with cost estimate
token_count = monitor.log_content_stats(
    content=formatted_content,
    label="Stage 6 - Reddit content",
    model="gpt-4o"
)
# Output: "Stage 6 - Reddit content: 112,430 tokens (~$0.28), 11.2% of 1M context"

# Check soft cap (warns but doesn't fail)
monitor.check_soft_cap(tokens=token_count, label="Stage 6", model="gpt-4o")
```

### Configuration

Add to `.env` file:

```bash
# Enable token monitoring (recommended)
TOKEN_MONITORING_ENABLED=true

# Warning threshold (always enabled)
TOKEN_WARNING_THRESHOLD=200000      # Log warning at 200K tokens

# Soft cap (optional - disabled by default)
TOKEN_SOFT_CAP_ENABLED=false        # Set to true to enable
TOKEN_SOFT_CAP=400000               # If enabled, log critical warning at 400K
```

### Usage Locations

Token monitoring is active in:
- **Stage 5** (ResearchFlow): Social media collection size
- **Stage 6** (PainPointCrew): Task 1 input monitoring

### Benefits

1. **Cost Visibility**: See token counts and estimated costs
2. **Early Warnings**: Know when collections are getting large
3. **No Failures**: Logs warnings but doesn't stop pipeline
4. **Configurable**: Adjust thresholds based on budget

### Example Output

```
INFO - Stage 5 - Social content: 85,234 tokens (~$0.21), 8.5% of 1M context
WARN - Stage 6 - Reddit content: 205,430 tokens (~$0.51), 20.5% of 1M context - exceeds warning threshold (200K)
```

With soft cap enabled:
```
CRITICAL - Stage 6 input: 425,000 tokens (~$1.06), 42.5% of 1M context - EXCEEDS SOFT CAP (400K)
```

---

## Multi-Model Strategy

Optimize cost vs quality by using different models for different cognitive loads.

### Model Selection Matrix

| Use Case | Model | Cost per 1M Tokens | Rationale |
|----------|-------|-------------------|-----------|
| **General Agent Reasoning** | gpt-4o | ~$2.50 | High quality needed for complex reasoning |
| **Function/Tool Calling** | gpt-4o-mini | ~$0.15 | Simple tool use, structured outputs |
| **Content Analysis** | gpt-4o | ~$2.50 | Nuanced understanding of social discussions |
| **Thread Validation** | gpt-4o-mini | ~$0.15 | Binary decision (relevant/irrelevant) |
| **Solution Ideation** | gpt-4o | ~$2.50 | Creative thinking, strategic insights |

### Configuration

Add to `.env` file:

```bash
# Default model for all agents
OPENAI_MODEL_NAME=gpt-4o

# Specialized models for specific tasks
FUNCTION_CALLING_LLM=gpt-4o-mini    # Tool calls and structured outputs
CONTENT_ANALYSIS_LLM=gpt-4o         # Content categorization
THREAD_VALIDATION_LLM=gpt-4o-mini   # Relevance filtering
BRAINSTORM_LLM=gpt-4o               # Solution ideation
```

### Cost Impact

**Example research run** (expat relocation niche):

| Configuration | Estimated Cost | Time |
|---------------|----------------|------|
| All gpt-4o | ~$2.20 | 12 min |
| Multi-model (default) | ~$0.85 | 12 min |
| All gpt-4o-mini | ~$0.30 | 12 min |

**Savings**: 60% cost reduction with multi-model vs all gpt-4o

**Trade-off**: gpt-4o-mini may produce lower quality outputs for complex reasoning tasks (solution ideation, competitive analysis)

### When to Use Each Model

**Use gpt-4o for**:
- Strategic decision making
- Creative ideation
- Nuanced analysis
- Complex reasoning
- Critical path tasks

**Use gpt-4o-mini for**:
- Filtering/validation
- Tool calling
- Structured data extraction
- Binary decisions
- High-volume repetitive tasks

### Recommendations

1. **Start with defaults**: Multi-model configuration balances cost and quality
2. **Upgrade cautiously**: Only use gpt-4o everywhere if quality issues observed
3. **Monitor outputs**: Check solution quality with different model configs
4. **Budget-conscious**: Use more gpt-4o-mini for non-critical tasks

---

## Context-Aware Query Generation

Eliminate template-driven nonsense by using context-aware generators with semantic validation.

### Problem

Template-driven approaches produce nonsensical queries like "apps for home appliances" when niche is "home cleaning apps".

### Solution

Context-aware generators with NicheContext integration and semantic validation.

### Available Generators

#### 1. QueryGenerator (Search Queries)

Generates social media search queries from niche context.

```python
from nicheiq.utils.generation.query_generator import QueryGenerator

generator = QueryGenerator()
result = generator.generate_queries(
    niche=niche_description,
    niche_context=niche_context,  # Includes market_segments, industry_boundaries
    project_types=["directory", "aggregator"]
)
# Returns: SearchQueryResult with 10-15 validated queries
```

**Features**:
- Chain-of-thought analysis
- 6 semantic validation rules
- Market segment integration
- Input sanitization

#### 2. CompetitorQueryGenerator (Competitor Search)

Generates competitor search queries with solution-type awareness.

```python
from nicheiq.utils.generation.competitor_query_generator import CompetitorQueryGenerator

generator = CompetitorQueryGenerator()
result = generator.generate_queries(
    solution=selected_solution,  # Includes project_type
    niche_context=niche_context
)
# Returns: Competitor-specific search queries
```

**Solution-Type Mapping**:
- Directory → "directory", "listing", "database"
- Aggregator → "aggregator", "comparison", "best of"
- Marketplace → "marketplace", "platform", "exchange"

#### 3. KeywordSeedGenerator (SEO Keywords)

Generates SEO seed keywords for Stage 9.5a.

```python
from nicheiq.utils.generation.keyword_seed_generator import KeywordSeedGenerator

generator = KeywordSeedGenerator()
result = generator.generate_seeds(
    solution=selected_solution,
    niche_context=niche_context,
    pain_points=pain_points,
    competitive_analysis=competitive_analysis
)
# Returns: 40-50 validated seed keywords
```

**Distribution**:
- 70% broad market keywords (e.g., "expat health insurance")
- 30% targeted pain point keywords (from social discussions)

### Benefits

1. **No Nonsense**: Semantic validation prevents illogical combinations
2. **Context-Aware**: Leverages full niche context and market segments
3. **Solution-Aware**: Generates terminology appropriate to project type
4. **Input Sanitization**: Cleans and validates all inputs

### Validation Rules

All generators apply:
- Remove duplicates and near-duplicates
- Check semantic coherence
- Validate against niche boundaries
- Ensure market segment relevance
- Filter overly generic terms
- Prevent template artifacts

---

## Multi-Model Cost Optimization

NicheIQ uses **6 specialized models** to optimize cost vs quality, achieving 60-90% savings compared to using GPT-4o for all tasks.

### Strategy

Different cognitive tasks require different model capabilities. By routing simple tasks to cheaper models and complex reasoning to premium models, we maintain quality while dramatically reducing costs.

### Model Assignment

**High-Reasoning Tasks** (use `gpt-4o`):
- `OPENAI_MODEL_NAME` - Default agent reasoning (complex analysis, ideation)
- `CONTENT_ANALYSIS_LLM` - Social media categorization (nuanced classification)
- `BRAINSTORM_LLM` - Solution ideation (creative brainstorming)

**Simple Tasks** (use `gpt-4o-mini` or `gpt-4.1-nano`):
- `FUNCTION_CALLING_LLM=gpt-4o-mini` - Tool calls (60% cost reduction)
- `THREAD_VALIDATION_LLM=gpt-4o-mini` - Relevance filtering (60% reduction)
- `KEYWORD_VALIDATION_LLM=gpt-4.1-nano` - Keyword checks (90% reduction)
- `KEYWORD_RESEARCH_LLM=gpt-4o-mini` - SEO analysis (60% reduction)

### Cost Impact

**Per-run costs**:
- All GPT-4o: ~$2.20
- Multi-model (default): ~$0.85
- **Savings**: ~$1.35 per run (61% reduction)

**Typical usage** (10 research runs/month):
- All GPT-4o: $22/month
- Multi-model: $8.50/month
- **Savings**: $13.50/month

### Configuration

Set individual model overrides in `.env`:

```bash
# Override specific models
FUNCTION_CALLING_LLM=gpt-4o-mini
THREAD_VALIDATION_LLM=gpt-4o-mini
KEYWORD_VALIDATION_LLM=gpt-4.1-nano
KEYWORD_RESEARCH_LLM=gpt-4o-mini

# Or use all GPT-4o (higher cost, slightly better quality)
OPENAI_MODEL_NAME=gpt-4o
FUNCTION_CALLING_LLM=gpt-4o
THREAD_VALIDATION_LLM=gpt-4o
KEYWORD_VALIDATION_LLM=gpt-4o
KEYWORD_RESEARCH_LLM=gpt-4o
```

See [ENV_REFERENCE.md#specialized-model-configuration-advanced](ENV_REFERENCE.md#specialized-model-configuration-advanced) for detailed guidance.

---

## Stage 10: Hybrid Report Generation

Stage 10 uses a **hybrid approach** that combines Python data assembly (80%) with minimal LLM synthesis (20%) for 85% cost reduction and 5x speed improvement.

### Architecture

**Step 1: Python Data Assembly**
- Generates 27 fields through direct copy + templates
- Pulls data from research state without LLM processing
- Fields: niche validation, pain points, competitive analysis, SEO strategy, etc.

**Step 2: LLM Strategic Synthesis**
- Enhances only 3 strategic fields that benefit from creative synthesis:
  - `executive_summary` - High-level narrative
  - `acquisition_strategy_summary` - GTM synthesis
  - `next_steps` - Action items

**Step 3: Python Enhanced Sections**
- Adds 7 enhanced sections through Python logic:
  - Research metadata (timestamps, API usage)
  - Evidence appendix (pain point quotes)
  - Decision framework roadmaps
  - Analytics & visualizations

### Benefits

**Cost Reduction**:
- Traditional (all-LLM): $0.10-0.30 per report
- Hybrid (Python+LLM): $0.02-0.05 per report
- **Savings**: 85% cost reduction

**Speed Improvement**:
- Traditional: 30-45 seconds
- Hybrid: 5-8 seconds
- **Speedup**: 5x faster

**Quality Improvement**:
- **Zero hallucination** on data fields (Python templates)
- **Higher accuracy** on metrics (direct state access)
- **Better formatting** (consistent Python templates)

**LLM synthesis only** where it adds value: creative narratives, strategic insights, action items.

###Implementation

**Location**: `src/nicheiq/report/report_generator.py`

**Key methods**:
- `_generate_base_report()` - Python data assembly (Step 1)
- `_enhance_with_llm()` - Strategic synthesis (Step 2)
- `_add_enhanced_sections()` - Python enhancements (Step 3)

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete architecture details.

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Core patterns and best practices
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Bug fixes and debugging
- [PATTERNS.md](PATTERNS.md) - Code recipes
- [README.md](../README.md) - Project overview
- [ENV_REFERENCE.md](ENV_REFERENCE.md) - Complete configuration reference
