# Troubleshooting Guide

This document contains historical bug fixes, known issues, and debugging strategies for NicheIQ development.

## Table of Contents
- [Known Issues & Workarounds](#known-issues--workarounds)
- [Common Development Issues](#common-development-issues)
- [Debugging Strategies](#debugging-strategies)
- [Performance Issues](#performance-issues)

---

## Known Issues & Workarounds

### 1. Async Event Loop Issues (Twitter Integration)

**Problem**: Twitter-api-client uses `asyncio.run()` internally, causing nested event loop errors when called from async Flow methods.

**Error Message**:
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**Root Cause**: Twitter-api-client library internally calls `asyncio.run()`, which conflicts with the already-running event loop in CrewAI Flow's async methods.

**Solution**: Use thread executor pattern to run Twitter collection in a separate thread:

```python
import asyncio

async def stage_5_search_and_discover(self):
    loop = asyncio.get_event_loop()
    twitter_threads = await loop.run_in_executor(
        None,
        lambda: asyncio.run(self.twitter_tool.collect_threads(twitter_urls))
    )
```

**When This Occurs**:
- Stage 5 (Search & Discover) when Twitter collection is enabled
- Any async Flow method calling Twitter-api-client methods
- Running with `ENABLE_TWITTER=true` in environment

**Prevention**: Always use the thread executor pattern when integrating libraries that use `asyncio.run()` internally.

---

### 2. Template Variable Parsing (CrewAI Task Configs)

**Problem**: CrewAI parses ALL `{variable}` patterns as template variables in task configuration YAML files, causing KeyError when using curly braces in examples or instructions.

**Error Message**:
```
KeyError: 'solution_name'
```

**Root Cause**: CrewAI's task loader treats any `{text}` as a template variable that must be provided in `crew.kickoff(inputs={...})`. Using curly braces in instructional text or examples causes errors.

**Solution**: Use square brackets `[ ]` or angle brackets `< >` for examples and instructional text:

```yaml
# ✅ CORRECT
description: >
  Search for competitors using: "[solution name] competitors"
  Example search: "[keyword] alternatives"

# ❌ WRONG - causes KeyError
description: >
  Search for: "{solution_name} competitors"
```

**When This Occurs**:
- Task configuration YAML files in `src/nicheiq/crews/config/`
- Any instructional text, examples, or placeholder syntax in task descriptions
- References to data from context or previous tasks

**Rule of Thumb**: Only use `{curly braces}` when the variable is actually provided in `crew.kickoff(inputs={...})`. For all other cases (examples, instructions, references to context data), use `[square brackets]`.

---

### 3. Pydantic Schema Parser Bug (CrewAI Union Types)

**Problem**: Using `list[str | None]` with `default=None` or any `X | None` syntax causes CrewAI's PydanticSchemaParser to crash with AttributeError.

**Error Message**:
```
AttributeError: 'types.UnionType' object has no attribute '__name__'
```

**Root Cause**:
- The type `list[str | None]` means "a list containing strings OR Nones"
- But `default=None` means the field itself is None (not a list)
- This is semantically incorrect and triggers a bug in CrewAI's schema introspection
- When CrewAI tries to generate schema instructions, it encounters the nested Union type and attempts to call `.__name__` on a `types.UnionType` object, which doesn't have that attribute

**Solution**: Use `Optional[X]` instead of `X | None` for all Pydantic models used in CrewAI tasks:

```python
from typing import Optional
from pydantic import BaseModel, Field

# ❌ WRONG - Causes CrewAI schema parser crash
keyword_priorities: list[str | None] = Field(
    default=None,
    description="List of priorities"
)

# ✅ CORRECT - Semantically accurate and works with CrewAI
keyword_priorities: Optional[list[str]] = Field(
    default=None,
    description="List of priorities"
)
```

**When This Occurs**:
- Pydantic models used as `output_pydantic` in CrewAI tasks
- Fields that are optional (should be None or a value, not a list of Nones)
- Any Union type annotation in Pydantic models processed by CrewAI

**Fixed Locations** (73 total fixes across codebase):
- `src/nicheiq/models/solution_idea.py`: 40 occurrences
- `src/nicheiq/models/pain_point.py`: 6 occurrences
- `src/nicheiq/models/research_state.py`: 27 occurrences
- Plus 5 other model files

**Ruff Configuration**: To prevent ruff from auto-converting `Optional[X]` back to `X | None` syntax, the `UP007` and `UP045` rules are disabled in `pyproject.toml`:

```toml
[tool.ruff.lint]
ignore = [
    "E501",   # Line too long
    "UP007",  # Use X | Y for Union type annotations
    "UP045",  # Use X | None for Optional type annotations
]
```

**Important**: Always use `Optional[X]` syntax in Pydantic models. The pipe Union syntax (`X | None`) is not compatible with CrewAI's schema parser.

---

## Common Development Issues

### "Failed to init knowledge" Warning

**Symptom**: CrewAI logs show "Failed to init knowledge" warnings when running crews with Knowledge Sources.

**Cause**: Missing `CHROMA_OPENAI_API_KEY` environment variable.

**Solution**:
1. Add to `.env`:
   ```bash
   CHROMA_OPENAI_API_KEY=<your-openai-api-key>
   ```
2. **Important**: Set it to the same value as `OPENAI_API_KEY`

**Why This Happens**: CrewAI uses ChromaDB for Knowledge Sources (RAG), which requires an OpenAI API key for embeddings.

---

### No Embeddings Created

**Symptom**: Knowledge Sources fail silently, crews run but don't have access to RAG data.

**Cause**: Invalid or missing `CHROMA_OPENAI_API_KEY`.

**Solution**:
1. Verify API key is set: `echo $CHROMA_OPENAI_API_KEY`
2. Test API key: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $CHROMA_OPENAI_API_KEY"`
3. Ensure key has access to `text-embedding-3-small` model

---

### DataForSEO Insufficient Credits

**Symptom**: Keyword expansion fails with insufficient credits error.

**Cause**: DataForSEO API credits exhausted or budget exceeded.

**Solutions**:
1. **Reduce keyword target count**:
   ```bash
   KEYWORD_ENRICHMENT_TARGET_COUNT=50  # Default: 150
   ```

2. **Increase minimum search volume** (filters out low-volume keywords):
   ```bash
   KEYWORD_MIN_SEARCH_VOLUME=100  # Default: 10
   ```

3. **Monitor credits**: Check DataForSEO dashboard before running research

---

### Twitter Authentication Failures

**Symptom**: Twitter collection fails with authentication errors or empty results.

**Cause**: Invalid credentials or Twitter API rate limiting.

**Solutions**:
1. **Try guest mode** (no authentication):
   ```bash
   # Remove or comment out in .env:
   # TWITTER_USERNAME=
   # TWITTER_PASSWORD=
   # TWITTER_EMAIL=
   ```

2. **Disable Twitter entirely** if not needed:
   ```bash
   ENABLE_TWITTER=false
   ```

3. **Verify credentials** are correct and account is not locked

---

## Debugging Strategies

### Enable Debug Logging

```bash
python -m nicheiq.main --niche "your niche" --log-level DEBUG
```

This shows:
- Detailed API requests/responses
- Knowledge source search results
- Task execution flow
- Token usage statistics

---

### Inspect Checkpoints

Checkpoints preserve state between stages for debugging:

```bash
# List available checkpoints
python -m nicheiq.main --list-checkpoints

# Resume from specific checkpoint
python -m nicheiq.main --niche "your niche" --checkpoint ./output/checkpoints/checkpoint_niche_timestamp

# View checkpoint contents
cat output/checkpoints/checkpoint_niche_timestamp/metadata.json
```

Useful checkpoint files:
- `metadata.json` - Stage completion status
- `stage_6_pain_points.json` - Pain point analysis results
- `stage_7_solutions.json` - Solution ideas
- `stage_9_seo_strategy.json` - SEO analysis

---

### Clean Up Orphaned ChromaDB Collections

If a job is killed before its cleanup runs (SIGKILL, OOM, etc.), ChromaDB collections persist on disk. Use the cleanup command to audit and purge them:

```bash
# List all collections (safe, read-only)
python -m nicheiq.main --cleanup-collections

# Delete all collections (ensure no jobs are running)
python -m nicheiq.main --cleanup-collections --force

# Verify cleanup
python -m nicheiq.main --cleanup-collections
```

---

### Validate Report Output

Use the validation script to check for hallucinations and data accuracy:

```bash
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```

Checks:
- Score rounding issues
- CAC calculation accuracy
- Page count accuracy
- Data integrity

---

### Component Testing

Test individual components in isolation:

```python
# Test DataForSEO tool
from nicheiq.tools.dataforseo_tool import DataForSEOExpandTool
tool = DataForSEOExpandTool()
result = tool._run("test keyword")

# Test Knowledge Sources
from nicheiq.crews.pain_point_crew import PainPointCrew
crew = PainPointCrew(...)
# Inspect crew.knowledge_sources

# Test Query Generator
from nicheiq.utils.generation.query_generator import QueryGenerator
generator = QueryGenerator()
queries = generator.generate_queries(...)
```

---

## Performance Issues

### Slow Execution Diagnosis

**Symptom**: Research takes longer than expected (>20 minutes).

**Possible Causes & Solutions**:

1. **Large social media collections**:
   - Check `REDDIT_COMMENT_LIMIT` setting (default: 32)
   - Reduce to 16 or 0 for faster runs
   - Disable Twitter if not needed: `ENABLE_TWITTER=false`

2. **DataForSEO API delays**:
   - Bulk validation can take 30-60 seconds
   - Normal for 50+ keywords
   - Reduce `KEYWORD_ENRICHMENT_TARGET_COUNT` if too slow

3. **Model selection**:
   - Ensure using `gpt-4o-mini` for function calling
   - Check `FUNCTION_CALLING_LLM` setting
   - Verify not using expensive models everywhere

---

### Empty Results Investigation

**Symptom**: Research completes but generates no pain points or solutions.

**Debug Steps**:

1. **Check Stage 5 output**:
   ```bash
   # Enable checkpoint to see Stage 5 data
   cat output/checkpoints/.../stage_5_social_content.json | jq '.reddit_threads | length'
   ```

2. **Verify search queries**:
   - Look at SerperDev search results
   - Check if Reddit/Twitter URLs are valid
   - Ensure niche has social media discussions

3. **Inspect Knowledge Sources**:
   - Enable debug logging
   - Check if embeddings were created
   - Verify search strategies in task configs

4. **Review agent outputs**:
   - Check CrewAI+ trace batches (if enabled)
   - Look for task failures or validation issues

---

### Token Limit Warnings

**Symptom**: Warnings about approaching token limits or soft caps.

**Cause**: Large collections of social media content.

**Solutions**:

1. **Enable token monitoring** (already on by default):
   ```bash
   TOKEN_MONITORING_ENABLED=true
   TOKEN_WARNING_THRESHOLD=200000
   ```

2. **Use soft caps** to fail early:
   ```bash
   TOKEN_SOFT_CAP_ENABLED=true
   TOKEN_SOFT_CAP=400000
   ```

3. **Reduce collection size**:
   - Lower `REDDIT_COMMENT_LIMIT`
   - Reduce number of search queries
   - Filter threads more aggressively with ThreadRelevanceValidator

---

## Archived Bug Fixes (Resolved)

These issues have been resolved in recent versions. Documented here for historical context.

### DataForSEO CSV Parsing (Resolved - January 2025)

**Issue**: CSV parsing errors when processing DataForSEO API responses with special characters or inconsistent formatting.

**Error Message**:
```
ValueError: Could not parse CSV response from DataForSEO
KeyError: 'keyword' not found in parsed data
```

**Root Cause**: DataForSEO API sometimes returns CSV with:
- Inconsistent quote escaping
- Special characters in keyword fields
- Empty rows or incomplete data

**Solution Implemented**:
- Robust CSV parser with error handling
- Field validation before processing
- Fallback handling for malformed rows
- Comprehensive logging for debugging

**Reference**: `DATAFORSEO_FIX_SUMMARY.md` (archived)

---

### SEO Crew CSV Format Mismatch (Resolved - January 2025)

**Issue**: SEO Crew tasks expecting JSON format instead of CSV for keyword data, causing parsing failures.

**Error Message**:
```
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
Task failed: Could not parse keyword data
```

**Root Cause**: Task configuration files had JSON parsing logic but keyword data was passed as CSV.

**Solution Implemented**:
- Updated all SEO crew task configurations to accept CSV input
- Added CSV format validation
- Updated documentation to specify CSV format
- Added examples in task YAML descriptions

**Benefits**: 2x more token-efficient than JSON, complete data visibility

**Reference**: `SEO_CREW_CSV_FIX_SUMMARY.md` (archived)

---

### Final Report Validation Issues (Resolved - January 2025)

**Issue**: Report generation occasionally produced hallucinated data or missing fields.

**Root Cause**: LLM-based report generation (245-line prompt) caused:
- Hallucinations on numerical fields
- Missing data from state
- Inconsistent field population

**Solution Implemented**:
- Hybrid approach: Python data assembly (80%) + minimal LLM (20%)
- Only 3 fields use LLM (executive_summary, acquisition_strategy_summary, next_steps)
- All other fields use direct copy or templates
- Validation script to catch hallucinations

**Benefits**:
- 85% cost reduction ($0.10-0.30 → $0.02-0.05)
- 5x faster (10s → 2s)
- Zero hallucination on data fields
- 100% field preservation

**Reference**: `FINAL_VALIDATION_REPORT.md` (archived)

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Core patterns and best practices
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details
- [FEATURES.md](FEATURES.md) - Feature configuration and usage
- [README.md](../README.md) - Project overview
- [SETUP.md](SETUP.md) - Setup guide
