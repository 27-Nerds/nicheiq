# Testing Guide

Comprehensive guide to testing and validation in NicheIQ.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Organization](#test-organization)
- [Running Tests](#running-tests)
- [Validation Scripts](#validation-scripts)
- [Test Categories](#test-categories)
- [Writing Tests](#writing-tests)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Pre-Run Validation

Before running research, validate your environment setup:

```bash
python check_setup.py
```

**Checks:**

- Python version (3.10+)
- Required dependencies installed
- `.env` file exists
- API keys configured
- Output directory writable

### Run Tests

```bash
# All tests (unit + integration)
pytest

# Fast unit tests only (no API calls)
pytest tests/unit/

# With coverage report
pytest --cov=src/nicheiq --cov-report=term-missing

# Specific test file
pytest tests/unit/test_models.py -v
```

### Post-Run Validation

After generating a report, validate for hallucinations and data integrity:

```bash
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```

**Checks:**

- Pain point conflation (research vs solution)
- Score accuracy (no rounding errors)
- CAC value precision
- Page count accuracy
- Competition intensity labels

---

## Test Organization

NicheIQ uses a three-tier testing structure:

### 1. Unit Tests (`tests/unit/`)

Fast, focused tests with no external dependencies or API calls.

**Characteristics:**

- Run in milliseconds
- Test individual functions/classes
- Use mocks for external dependencies
- Safe to run frequently during development

**Examples:**

- `test_config.py` - Settings validation
- `test_models.py` - Pydantic model validation
- `test_utils.py` - Utility function tests
- `test_model_helpers.py` - Report utility tests

**Run:**

```bash
pytest tests/unit/ -v
```

### 2. Validation Scripts (Root Directory)

User-facing tools for environment and output validation.

**Scripts:**

- `check_setup.py` - Pre-run environment validation
- `validate_report.py` - Post-run hallucination detection

**Not part of pytest suite** - designed for manual execution.

---

## Running Tests

### Basic Usage

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run specific test
pytest tests/unit/test_models.py::test_pain_point_model -v

# Run tests matching pattern
pytest -k "test_keyword" -v
```

### Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov=src/nicheiq --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=src/nicheiq --cov-report=html
open htmlcov/index.html

# Generate both terminal and HTML
pytest --cov=src/nicheiq --cov-report=term-missing --cov-report=html
```

**Coverage Goals:**

- Unit tests: >80% coverage
- Critical paths: >90% coverage

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4
```

### CI/CD Usage

```bash
# Fast CI run (unit tests only)
pytest tests/unit/ --cov=src/nicheiq --cov-report=xml

# Full CI run (all tests)
pytest --cov=src/nicheiq --cov-report=xml --junitxml=junit.xml
```

---

## Validation Scripts

### check_setup.py

Validates environment before running research.

**Usage:**

```bash
python check_setup.py
```

**Output:**

```
✓ Python version: 3.12.7
✓ Dependencies installed: crewai, praw, pydantic, ...
✓ .env file found
✓ API keys configured: OPENAI_API_KEY, SERPER_API_KEY, ...
✓ Output directory writable: ./output/

All checks passed! You're ready to run NicheIQ.
```

**Exit Codes:**

- `0`: All checks passed
- `1`: One or more checks failed

### validate_report.py

Detects hallucinations and validates data integrity in generated reports.

**Usage:**

```bash
python validate_report.py <final_report.json> <research_state_raw.json>
```

**Example:**

```bash
python validate_report.py \
  output/final_report_20250122_143052.json \
  output/research_state_raw_20250122_143052.json
```

**Validation Categories:**

1. **Pain Point Conflation** - Ensures research vs solution pain points not mixed
2. **Score Accuracy** - Validates severity/WTP scores (no rounding)
3. **CAC Precision** - Checks exact CAC ranges preserved
4. **Page Count** - Verifies exact values from metadata
5. **Competition Intensity** - No invented labels

**Output:**

```
Validating final report...

✓ Pain point conflation check passed
✓ Pain point scores accurate (no rounding)
✓ CAC values precise
✓ Page counts accurate
✓ Competition intensity labels valid

All validations passed!
```

**Exit Codes:**

- `0`: All validations passed
- `1`: One or more validations failed

---

## Test Categories

### Configuration Tests

**Files:**

- `tests/unit/test_config.py`

**What they test:**

- Settings loading from .env
- Default value handling
- Type conversions
- Model configuration

**Run:**

```bash
pytest tests/unit/test_config.py -v
```

### Model Validation Tests

**Files:**

- `tests/unit/test_models.py`
- `tests/unit/test_model_helpers.py`
- `tests/unit/test_keyword_validation_crew_models.py`

**What they test:**

- Pydantic model validation
- Field constraints
- Type checking
- Model serialization/deserialization

**Run:**

```bash
pytest tests/unit/test_models.py -v
```

### Utility Function Tests

**Files:**

- `tests/unit/test_utils.py`
- `tests/unit/test_helpers_validation.py`
- `tests/unit/test_search_helpers.py`

**What they test:**

- Helper functions
- Data transformations
- Formatting utilities
- Search query generation

**Run:**

```bash
pytest tests/unit/test_utils.py -v
```

### Generation Tests

**Files:**

- `tests/integration/test_query_generator.py`
- `tests/integration/test_keyword_seed_generator.py`
- `tests/integration/test_competitor_query_generator.py`
- `tests/integration/test_hybrid_seed_generation.py`

**What they test:**

- Context-aware query generation
- Keyword seed generation
- Semantic validation
- NicheContext integration

**Run:**

```bash
pytest tests/integration/test_query_generator.py -v
```

### LLM Integration Tests

**Files:**

- `tests/unit/test_llm_service.py`
- `tests/unit/test_llm_service_components.py`
- `tests/integration/test_llm_service_integration.py`

**What they test:**

- LLMService centralized API
- Model selection
- Structured output generation
- Error handling

**Run:**

```bash
pytest tests/unit/test_llm_service.py -v
```

### Knowledge Sources Tests

**Files:**

- `tests/integration/test_knowledge_sources.py`

**What they test:**

- CrewAI RAG integration
- StringKnowledgeSource chunking
- Embedding generation
- Semantic search

**Run:**

```bash
pytest tests/integration/test_knowledge_sources.py -v
```

### Report Generation Tests

**Files:**

- `tests/unit/test_final_report_generator.py`
- `tests/integration/test_final_report_fix.py`
- `tests/integration/test_anti_hallucination.py`

**What they test:**

- Hybrid report generation (Python + LLM)
- Data assembly
- Hallucination detection
- Field preservation

**Run:**

```bash
pytest tests/unit/test_final_report_generator.py -v
```

### DataForSEO Tests

**Files:**

- `tests/integration/test_dataforseo.py`
- `tests/integration/test_dataforseo_tools.py`

**What they test:**

- DataForSEO API integration
- Keyword validation
- Batch processing
- Error handling

**Run:**

```bash
pytest tests/integration/test_dataforseo.py -v
```

### Token Monitoring Tests

**Files:**

- `tests/unit/test_token_monitor.py`
- `tests/integration/test_token_monitoring.py`

**What they test:**

- Token counting accuracy
- Cost estimation
- Warning thresholds
- Soft caps

**Run:**

```bash
pytest tests/unit/test_token_monitor.py -v
```

### Checkpoint System Tests

**Files:**

- `tests/integration/test_checkpoint_reconstruction.py`

**What they test:**

- Checkpoint creation
- State persistence
- Resume functionality
- Stage reconstruction

**Run:**

```bash
pytest tests/integration/test_checkpoint_reconstruction.py -v
```

### SEO Tests

**Files:**

- `tests/unit/test_seo_strategy_validators.py`
- `tests/unit/test_score_refinement.py`
- `tests/integration/test_seo_csv_format.py`
- `tests/integration/test_seo_csv_format_simple.py`

**What they test:**

- SEO strategy validation
- CSV format handling
- Keyword tier classification
- Score refinement logic

**Run:**

```bash
pytest tests/unit/test_seo_strategy_validators.py -v
```

---

## Writing Tests

### Test Structure

Follow pytest conventions:

```python
# tests/unit/test_my_feature.py
import pytest
from nicheiq.utils.my_module import my_function


class TestMyFeature:
    """Test suite for my_feature."""

    def test_basic_functionality(self):
        """Test basic usage."""
        result = my_function("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test edge case handling."""
        with pytest.raises(ValueError):
            my_function(None)

    @pytest.mark.parametrize("input,expected", [
        ("a", "A"),
        ("b", "B"),
    ])
    def test_multiple_inputs(self, input, expected):
        """Test multiple inputs."""
        assert my_function(input) == expected
```

### Fixtures

Use `conftest.py` for shared fixtures:

```python
# tests/conftest.py
import pytest
from nicheiq.models.research_state import ResearchState


@pytest.fixture
def sample_research_state():
    """Provide sample research state for tests."""
    return ResearchState(
        niche_description="AI tools for content creators",
        # ... other fields
    )
```

**Usage:**

```python
def test_with_fixture(sample_research_state):
    """Test using fixture."""
    assert sample_research_state.niche_description == "AI tools for content creators"
```

### Mocking External APIs

Use `pytest-mock` for API mocking:

```python
def test_api_call(mocker):
    """Test API call with mock."""
    mock_response = {"result": "success"}
    mocker.patch("requests.post", return_value=mock_response)

    result = my_api_function()
    assert result == mock_response
```

### Test Naming

- Use descriptive names: `test_<feature>_<scenario>`
- Group related tests in classes
- Use docstrings to explain test purpose

---

## Troubleshooting

### Tests Not Found

**Issue:** `pytest` doesn't find tests

**Solutions:**

1. Ensure test files start with `test_`
2. Check test functions start with `test_`
3. Verify pytest can import modules: `pytest --collect-only`

### Import Errors

**Issue:** `ModuleNotFoundError: No module named 'nicheiq'`

**Solution:**

```bash
# Install package in editable mode
pip install -e .

# Or activate venv
source .venv/bin/activate
```

### Slow Tests

**Issue:** Tests take too long

**Solutions:**

1. Run unit tests only: `pytest tests/unit/`
2. Use parallel execution: `pytest -n 4`
3. Skip slow tests: `pytest -m "not slow"`

### API Rate Limits

**Issue:** Integration tests hit API rate limits

**Solutions:**

1. Run unit tests only for development
2. Use mocks for API calls
3. Add delays between tests: `pytest --maxfail=1`

### Coverage Too Low

**Issue:** Coverage report shows low coverage

**Solutions:**

1. Focus on critical paths first
2. Add tests for uncovered lines
3. Check coverage report: `pytest --cov=src/nicheiq --cov-report=html`

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Testing commands reference
- [README.md](../README.md) - Quick start testing
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common test issues
- [PATTERNS.md](PATTERNS.md) - Testing patterns

---

**Last Updated**: 2025-01-22
