# Code Patterns & Recipes

Reusable code patterns and templates for common NicheIQ development tasks.

## Table of Contents
- [Adding New Crews](#adding-new-crews)
- [Modifying Knowledge Sources](#modifying-knowledge-sources)
- [Implementing Guardrails](#implementing-guardrails)
- [Parallel Execution Patterns](#parallel-execution-patterns)

---

## Adding New Crews

Step-by-step template for creating a new specialized crew.

### 1. Create Crew Class

```python
# src/nicheiq/crews/my_new_crew.py
from crewai import Agent, Crew, Process, Task
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel

from nicheiq.config.settings import settings


class MyCrewOutput(BaseModel):
    """Output model for my crew."""

    analysis_result: str
    recommendations: list[str]


@CrewBase
class MyNewCrew:
    """Crew for [specific purpose]."""

    agents_config = "config/my_new_agents.yaml"
    tasks_config = "config/my_new_tasks.yaml"

    def __init__(self, input_data):
        self.input_data = input_data

    @agent
    def specialist_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["specialist"],
            llm=settings.openai_model_name
        )

    @task
    def analyze_task(self) -> Task:
        return Task(
            config=self.tasks_config["analyze"],
            agent=self.specialist_agent(),
            output_pydantic=MyCrewOutput
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )
```

### 2. Create Agent Configuration

```yaml
# src/nicheiq/crews/config/my_new_agents.yaml
specialist:
  role: "Specialist in [domain]"
  goal: "Analyze [data] and provide [insights]"
  backstory: >
    You are an expert [specialist type] with deep knowledge of [domain].
    Your analyses are thorough, data-driven, and actionable.
```

### 3. Create Task Configuration

```yaml
# src/nicheiq/crews/config/my_new_tasks.yaml
analyze:
  description: >
    Analyze the provided data and generate recommendations.

    Data available: {data_description}

    **Output Requirements:**
    - analysis_result: Comprehensive analysis summary
    - recommendations: 3-5 actionable recommendations

  expected_output: >
    A MyCrewOutput Pydantic model with:
    - analysis_result (string): 2-3 paragraph analysis
    - recommendations (list[str]): 3-5 bullet points
```

### 4. Integrate into ResearchFlow

```python
# src/nicheiq/flows/research_flow.py
from nicheiq.crews.my_new_crew import MyNewCrew

class ResearchFlow(Flow[ResearchState]):

    @listen(stage_X_previous)
    def stage_Y_my_new_stage(self):
        """Stage Y: [Purpose]."""
        logger.info("Starting Stage Y: [Purpose]")

        # Prepare input data
        input_data = self._prepare_input_data()

        # Run crew
        crew = MyNewCrew(input_data=input_data)
        result = crew.crew().kickoff(inputs={
            "data_description": str(input_data)
        })

        # Update state
        self.state.my_new_data = result.pydantic

        # Save checkpoint
        self._save_checkpoint("stage_Y_my_new_stage", {
            "result": result.pydantic.model_dump()
        })
```

### 5. Data Passing Checklist

Before running, verify:

1. ✅ All `{placeholders}` in task YAML have corresponding `inputs={}` keys
2. ✅ Input sizes logged for debugging
3. ✅ Knowledge Sources use appropriate chunk sizes
4. ✅ Expected output matches Pydantic model fields
5. ✅ Output validation/guardrails if needed

---

## Modifying Knowledge Sources

### Adjusting Chunk Size

**When to change**:
- Large chunks (2000+): Long-form content, preserve context
- Small chunks (500-1000): Short snippets, precise retrieval

```python
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

# For long Reddit posts with complex threads
reddit_knowledge = StringKnowledgeSource(
    content=formatted_reddit,
    chunk_size=2000,    # Larger for context preservation
    chunk_overlap=300   # 15% overlap
)

# For short Twitter posts
twitter_knowledge = StringKnowledgeSource(
    content=formatted_tweets,
    chunk_size=1500,    # Smaller, more focused
    chunk_overlap=200   # ~13% overlap
)
```

### Adding Search Strategy Instructions

```yaml
# In task config YAML
description: >
  Analyze social discussions to extract pain points.

  **Search Strategy for Knowledge Sources:**
  - For problems: Search "frustrated", "difficult", "struggling", "can't"
  - For severity: Search "urgent", "critical", "blocking", "must have"
  - For solutions: Search "tried", "using", "alternative to", "workaround"
  - For frequency: Search "everyone", "all", "common", "widespread"

  Extract pain points with:
  - title: Short descriptive title
  - description: Detailed problem explanation
  - severity_score: 0.0-1.0 based on emotional language
  - mention_count: How many discussions mention this
```

### Testing Search Quality

```python
# Test knowledge source retrieval
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

knowledge = StringKnowledgeSource(content=test_content, chunk_size=1500)

# Manually test queries
test_queries = ["frustrated users", "pricing issues", "feature requests"]
for query in test_queries:
    results = knowledge.search(query, limit=5)
    print(f"\nQuery: {query}")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result[:200]}...")
```

---

## Implementing Guardrails

### Basic Validation Pattern

```python
def _validate_my_task_output(self, task_output) -> tuple[bool, Any]:
    """
    Guardrail function to validate task output.

    Returns:
        tuple[bool, Any]: (success, validated_result_or_error_message)
    """
    try:
        # Check Pydantic output exists
        if not task_output.pydantic:
            return (False, "CRITICAL ERROR: Return ONLY the Pydantic model")

        result = task_output.pydantic

        # Validation 1: Check required fields
        if not result.required_field:
            return (False, "Missing required_field")

        # Validation 2: Check data quality
        if len(result.items) < 3:
            return (False, f"Need at least 3 items, found {len(result.items)}")

        # Validation 3: Check for placeholders
        result_json = result.model_dump_json()
        if '[placeholder' in result_json.lower():
            return (False, "Found placeholder text - use actual values")

        # All validations passed
        return (True, result)

    except Exception as e:
        return (False, f"Validation error: {str(e)}")
```

### Apply Guardrail to Task

```python
@task
def my_protected_task(self) -> Task:
    return Task(
        config=self.tasks_config["my_task"],
        agent=self.my_agent(),
        output_pydantic=MyOutputModel,
        guardrail=self._validate_my_task_output  # Add validation
    )
```

### Field Preservation Guardrail

Prevents agents from dropping or nullifying fields during refinement:

```python
def _validate_no_field_loss(self, task_output) -> tuple[bool, Any]:
    """Ensure all expected fields are present and populated."""
    try:
        result = task_output.pydantic

        # Check count preservation
        if len(result.items) != self._expected_item_count:
            return (False, f"Item count mismatch: expected {self._expected_item_count}, got {len(result.items)}")

        # Check field population
        for item in result.items:
            if item.critical_score is None:
                return (False, f"Missing critical_score for item: {item.name}")

            if not item.description or item.description.strip() == "":
                return (False, f"Empty description for item: {item.name}")

        return (True, result)

    except Exception as e:
        return (False, f"Validation error: {str(e)}")
```

### Common Validation Patterns

```python
# Pattern 1: Minimum count validation
if len(result.items) < min_count:
    return (False, f"Need at least {min_count} items")

# Pattern 2: No placeholder text
placeholder_patterns = ['[solution', '[selected', '[category']
for pattern in placeholder_patterns:
    if pattern in result_json.lower():
        return (False, f"Found placeholder '{pattern}...'")

# Pattern 3: Score range validation
if not (0.0 <= result.score <= 1.0):
    return (False, f"Score {result.score} out of range [0.0, 1.0]")

# Pattern 4: Required field presence
required_fields = ['name', 'description', 'score']
for field in required_fields:
    if not getattr(result, field, None):
        return (False, f"Missing required field: {field}")

# Pattern 5: String length validation
if len(result.summary) < 100:
    return (False, f"Summary too short: {len(result.summary)} chars, need 100+")
```

---

## Parallel Execution Patterns

### Basic ThreadPoolExecutor Pattern

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_items_parallel(items, max_workers=2):
    """Process items in parallel with controlled concurrency."""

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_item = {
            executor.submit(process_single_item, item, i, len(items)): item
            for i, item in enumerate(items, 1)
        }

        # Collect results as they complete
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {item}: {e}")
                results.append(None)  # Or handle error appropriately

    return results
```

### Conservative Concurrency (API Rate Limits)

```python
# Conservative for API calls
max_workers = 2  # Respect API rate limits

# Example: Parallel crew execution
def analyze_solutions_parallel(self, solutions):
    """Analyze multiple solutions in parallel."""

    all_analyses = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_solution = {
            executor.submit(self._analyze_single_solution, solution): solution
            for solution in solutions
        }

        for future in as_completed(future_to_solution):
            solution = future_to_solution[future]
            try:
                analysis = future.result()
                all_analyses.append(analysis)
                logger.info(f"✓ Completed analysis for: {solution.name}")
            except Exception as e:
                logger.error(f"✗ Failed to analyze {solution.name}: {e}")

    return all_analyses
```

### Error Handling in Parallel Execution

```python
def parallel_with_error_handling(items, max_workers=2):
    """Parallel execution with comprehensive error handling."""

    results = []
    errors = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(process_item, item): item
            for item in items
        }

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result(timeout=300)  # 5 minute timeout
                results.append(result)

            except TimeoutError:
                logger.error(f"Timeout processing {item}")
                errors.append((item, "timeout"))

            except Exception as e:
                logger.error(f"Error processing {item}: {e}")
                errors.append((item, str(e)))

    # Log summary
    logger.info(f"Completed: {len(results)}/{len(items)}")
    if errors:
        logger.warning(f"Errors: {len(errors)}")
        for item, error in errors:
            logger.warning(f"  - {item}: {error}")

    return results, errors
```

### Production Example: Parallel Keyword Validation

NicheIQ uses parallel validation in production for keyword and thread validation:

```python
# src/nicheiq/utils/validation/keyword_validator.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from .thread_safe_cache import ThreadSafeValidationCache

def validate_batch_parallel(
    self,
    keywords: list[dict],
    max_workers: int = 3,
    validation_cache: dict = None,
    **kwargs
) -> list[tuple]:
    """Validate keywords in parallel with thread-safe caching."""

    # Wrap cache in thread-safe wrapper
    thread_safe_cache = None
    if validation_cache is not None:
        thread_safe_cache = ThreadSafeValidationCache(validation_cache)

    # Calculate chunk size: distribute keywords evenly
    chunk_size = max(len(keywords) // max_workers, batch_size)
    chunks = [keywords[i:i + chunk_size] for i in range(0, len(keywords), chunk_size)]

    all_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        future_to_chunk = {
            executor.submit(
                self._validate_chunk_worker,
                chunk, chunk_num, thread_safe_cache, **kwargs
            ): chunk_num
            for chunk_num, chunk in enumerate(chunks, 1)
        }

        # Collect results as they complete
        for future in as_completed(future_to_chunk):
            chunk_num = future_to_chunk[future]
            try:
                results = future.result(timeout=300)
                all_results.extend(results)
                logger.info(f"Chunk {chunk_num} complete ({len(results)} results)")
            except Exception as e:
                logger.error(f"Chunk {chunk_num} failed: {e}")

    # Update original cache with thread-safe cache results
    if validation_cache is not None and thread_safe_cache is not None:
        validation_cache.update(thread_safe_cache.get_all())

    return all_results
```

**Key Features:**
- **Thread-safe cache** prevents race conditions
- **Conservative workers** (3 for keywords, 2 for threads) respects API limits
- **Graceful degradation** on errors (continues processing other chunks)
- **Performance gain**: 3x faster (45-90s → 15-30s per run)

**Usage in research_flow.py:**
```python
# Phase 6c: Keyword validation with parallel processing
validator = KeywordRelevanceValidator()
validation_results = validator.validate_batch_parallel(
    keywords=suggestions,
    niche_description=niche_description,
    solution_name=solution_name,
    solution_description=solution_description,
    batch_size=50,  # Batch size per worker
    max_workers=3   # From settings.keyword_validation_max_workers
)
```

### When NOT to Use Parallel Execution

❌ **Don't parallelize when**:
- Tasks have strict sequential dependencies
- Shared state needs to be updated (use thread-safe wrappers)
- API has strict rate limits (< 2 requests/sec)
- Tasks are very fast (< 1 second)
- Order of results matters

✅ **Do parallelize when**:
- Tasks are independent
- Each task takes > 5 seconds
- API allows concurrent requests
- Order doesn't matter
- Benefits outweigh threading overhead

---

## CrewAI Implementation Patterns

### Context Chaining Pattern

**Problem**: Manual text formatting between stages causes field loss.

**Solution**: Use `output_pydantic` + `context=[previous_task]` for automatic Pydantic object passing:

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

**Benefits**:
- Automatic field preservation (no manual JSON formatting)
- Type safety with Pydantic validation
- Prevents field loss during multi-stage processing

### Tag / Score Carry-Through Pattern

**Problem**: A field is computed on an early-stage object (e.g. a `RawConcept`) but the
refinement LLM produces a *new* object that doesn't echo it back, and context chaining can't
guarantee the model re-emits a non-prompted scalar. Examples: `mechanism_tag` /
`data_source_tag` / `journey_tag` and `obviousness_score` in `UnifiedSolutionCrew`.

**Solution**: After refinement, copy the field from the source object onto the refined one in
**code**, matched by a whitespace-normalized name key — don't rely on the LLM:

```python
tag_lookup = {
    _norm(c.concept_name): (c.mechanism_tag, c.data_source_tag, c.journey_tag, c.obviousness_score)
    for c in filtered_concepts.concepts
}
for sol in refined_solutions.solution_ideas:
    tags = tag_lookup.get(_norm(getattr(sol, "solution_name", "")))
    if tags:
        sol.mechanism_tag, sol.data_source_tag, sol.journey_tag = tags[:3]
        if tags[3] is not None and tags[3] >= 0:   # skip the -1.0 unscored sentinel
            sol.obviousness_score = tags[3]
```

**Notes**:
- The match is by name, and refinement can rename a concept — so the consumer must tolerate a
  miss (the UI's Originality bar falls back to `novelty_score` when `obviousness_score` is null).
- Re-injected (coverage / bold-slot) ideas run the same single-concept refinement, so they
  carry the field too.

### Multi-Agent Sequential Crew Pattern

**Problem**: Complex tasks require multiple specialized agents working together.

**Solution**: Create a crew with multiple agents and sequential tasks with context chaining.

**Example**: `TechnicalBlueprintCrew` (Stage 10.5) - generates site structure and user flows.

```python
# src/nicheiq/crews/technical_blueprint_crew.py
@CrewBase
class TechnicalBlueprintCrew:
    """Crew for generating site structure and user flows."""

    agents_config = "config/technical_blueprint_agents.yaml"
    tasks_config = "config/technical_blueprint_tasks.yaml"

    @agent
    def product_architect(self) -> Agent:
        """Agent specializing in site structure design."""
        return Agent(
            config=self.agents_config["product_architect"],
            llm=ChatOpenAI(**build_llm_kwargs(model=settings.openai_model_name)),
            verbose=True,
        )

    @agent
    def ux_designer(self) -> Agent:
        """Agent specializing in user flow mapping."""
        return Agent(
            config=self.agents_config["ux_designer"],
            llm=ChatOpenAI(**build_llm_kwargs(model=settings.openai_model_name)),
            verbose=True,
        )

    @task
    def site_structure_task(self) -> Task:
        return Task(
            config=self.tasks_config["site_structure_task"],
            agent=self.product_architect(),
            output_pydantic=SiteStructure,  # Pydantic model
        )

    @task
    def user_flows_task(self) -> Task:
        return Task(
            config=self.tasks_config["user_flows_task"],
            agent=self.ux_designer(),
            output_pydantic=UserFlowsSection,
            context=[self.site_structure_task()],  # Uses site structure for page references
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.product_architect(), self.ux_designer()],
            tasks=[self.site_structure_task(), self.user_flows_task()],
            verbose=True,
            process="sequential",
        )
```

**Key Features**:
- **2 specialized agents**: Product architect (site structure) + UX designer (user flows)
- **Context chaining**: User flows task receives site structure output automatically
- **Anti-hallucination prompts**: YAML tasks explicitly state "ONLY use personas from target_personas list"
- **Priority framework**: P0 (MVP), P1 (soon), P2 (later) for page prioritization

**Output Extraction**:
```python
result = crew.kickoff(inputs={...})
tasks_output = result.tasks_output if hasattr(result, 'tasks_output') else []

if len(tasks_output) >= 1 and tasks_output[0].pydantic:
    site_structure = tasks_output[0].pydantic

if len(tasks_output) >= 2 and tasks_output[1].pydantic:
    user_flows = tasks_output[1].pydantic
```

---

### Guardrails Pattern

**Problem**: Agents may drop solutions or nullify fields during refinement tasks.

**Solution**: Add guardrail functions that validate task output and trigger retries on failure:

```python
def _validate_no_field_loss(self, task_output) -> tuple:
    """Validate that refinement didn't drop solutions or nullify scores."""
    try:
        result = task_output.pydantic

        # Check solution count
        if len(result.solution_ideas) != self._expected_solution_count:
            return (False, f"Solution count mismatch: expected {self._expected_solution_count}, got {len(result.solution_ideas)}")

        # Check critical fields
        for idea in result.solution_ideas:
            if idea.market_fit_score is None:
                return (False, f"Missing market_fit_score for '{idea.solution_name}'")

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
        guardrail=self._validate_no_field_loss,  # Auto-validates and retries on failure
    )
```

**Benefits**:
- Automatic retry on validation failure
- Prevents data loss in multi-stage workflows
- Type-safe validation with clear error messages

### Parallel Validation Pattern

**Production Implementation**: Keyword and thread validation use parallel batch processing for 3x speedup.

**Files**:
- `src/nicheiq/utils/validation/keyword_validator.py` - `validate_batch_parallel()`
- `src/nicheiq/utils/validation/thread_validator.py` - `validate_batch_parallel()`
- `src/nicheiq/utils/validation/thread_safe_cache.py` - Thread-safe cache wrapper

**Configuration** (`.env`):
```bash
VALIDATION_PARALLEL_ENABLED=true  # Global toggle (default: true)
KEYWORD_VALIDATION_MAX_WORKERS=3  # Phase 6c workers (default: 3)
THREAD_VALIDATION_MAX_WORKERS=2   # Stage 5 workers (default: 2)
```

**Key Features**:
- Thread-safe caching with `threading.Lock`
- Conservative worker counts respect API limits
- Graceful degradation (falls back to sequential if disabled)
- 3x faster validation (45-90s → 15-30s per run)

**Usage Example**:
```python
# Phase 6c keyword validation (research_flow.py)
validator = KeywordRelevanceValidator()
results = validator.validate_batch_parallel(
    keywords=suggestions,
    max_workers=3,  # From settings
    batch_size=50   # Per worker
)

# Stage 5 thread validation (research_flow.py)
validator = ThreadRelevanceValidator()
results = validator.validate_batch_parallel(
    search_results=unique_reddit_results,
    max_workers=2   # From settings
)
```

---

## Crew Modification Guide

### Data Passing Validation Checklist

**CRITICAL**: Verify all inputs are properly passed to avoid hallucinations.

1. **List all inputs** in `crew.kickoff(inputs={...})`
2. **Ensure `{key}` placeholder** exists in task YAML for each input
3. **Log input sizes** for debugging (helps catch empty/malformed data)
4. **Validate outputs** contain actual data (not placeholders)

### Adding New Crews

**Step-by-Step Guide**:

1. **Create crew class** extending `@CrewBase`:
   ```python
   from crewai import Agent, Crew, Task
   from crewai.project import CrewBase, agent, crew, task

   @CrewBase
   class MyNewCrew():
       agents_config = 'config/my_new_agents.yaml'
       tasks_config = 'config/my_new_tasks.yaml'
   ```

2. **Define agents** with `@agent` decorator:
   ```python
   @agent
   def my_agent(self) -> Agent:
       return Agent(
           config=self.agents_config['my_agent'],
           verbose=True
       )
   ```

3. **Define tasks** with `@task` decorator:
   ```python
   @task
   def my_task(self) -> Task:
       return Task(
           config=self.tasks_config['my_task'],
           agent=self.my_agent(),
           output_pydantic=MyOutputModel
       )
   ```

4. **Apply Data Passing Checklist** (see above)

5. **Add explicit field guidance** in YAML:
   - CrewAI doesn't auto-inject Pydantic field descriptions
   - Manually list required fields in `expected_output`

6. **Integrate into `research_flow.py`**:
   ```python
   crew = MyNewCrew()
   result = crew.kickoff(inputs={"key": "value"})
   ```

See [PROMPT_OPTIMIZATION.md](PROMPT_OPTIMIZATION.md) for advanced prompt patterns.

---

## CrewAI Best Practices

### Knowledge Sources (RAG)

**When to use**:
- Large datasets (400+ items)
- Unstructured content
- Semantic search needs

**Best practices**:
- Add metadata headers: `[POST_ID: ...]`, `[PLATFORM: ...]`, `[SCORE: ...]`
- Configure chunking: `chunk_size=2000, chunk_overlap=300`
- Use cost-effective embeddings: `text-embedding-3-small`
- Add search strategy instructions in task descriptions

### Structured Output (Pydantic)

**Best practices**:
- Use `output_pydantic=ModelClass` for type-safe outputs
- Use `Optional[Type] = Field(default=None)` for conditional data
- Add explicit field requirements in task `expected_output` (not auto-injected by CrewAI)

### Flow State Management

**Best practices**:
- Define Pydantic BaseModel for type safety: `class MyFlow(Flow[MyState]):`
- Extract from state in separate methods with `Optional[Model]` return type
- Use try/except with logger.warning for graceful degradation

### Context Chaining

**Best practices**:
- Pass complete Pydantic objects: `context=[previous_task]`
- Use `output_pydantic=Model` on source task
- Preserves all fields without manual formatting

### Task Configuration

**Best practices**:
- Write specific `expected_output` with field structure
- Add search strategies for knowledge source queries
- Request source IDs in output for attribution

### Guardrails

**Best practices**:
- Add validation: `guardrail=validation_function`
- Return `(True, result)` for success, `(False, error_msg)` for retry
- Validate critical data integrity (not style)

### References

- Official Docs: <https://docs.crewai.com/>
- Knowledge Sources: <https://docs.crewai.com/en/concepts/knowledge>
- Flow State: <https://docs.crewai.com/en/guides/flows/mastering-flow-state>

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Core patterns and best practices
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Bug fixes and debugging
- [FEATURES.md](FEATURES.md) - Feature documentation
- [README.md](../README.md) - Project overview
