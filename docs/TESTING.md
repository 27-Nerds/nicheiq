# Testing Guide

Comprehensive guide to testing in NicheIQ across all components.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Python Pipeline Tests](#python-pipeline-tests)
- [Frontend Tests](#frontend-tests)
- [Backend Tests](#backend-tests)
- [Validation Scripts](#validation-scripts)
- [Writing Tests](#writing-tests)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Run All Tests

```bash
# Python pipeline tests
source .venv/bin/activate
pytest

# Frontend tests
cd frontend && npm test

# Backend tests
cd backend && npm test
```

### Pre-Run Validation

Before running research, validate your environment:

```bash
python check_setup.py
```

### Post-Run Validation

After generating a report, validate data integrity:

```bash
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```

---

## Test Structure

NicheIQ has three test suites corresponding to the main components:

```
nicheiq/
├── tests/                          # Python pipeline tests
│   ├── conftest.py                 # Shared fixtures
│   └── unit/
│       ├── test_*.py               # Core unit tests
│       ├── flows/                  # Flow/checkpoint tests
│       ├── report/                 # Report generation tests
│       ├── utils/validation/       # Validation utility tests
│       └── validators/             # Score/text validator tests
│
├── frontend/src/**/__tests__/      # Frontend tests (Vitest)
│   ├── lib/__tests__/              # API client tests
│   └── routes/**/__tests__/        # Route tests
│
└── backend/src/**/__tests__/       # Backend tests (Vitest)
    ├── routes/__tests__/           # API endpoint tests
    └── services/__tests__/         # Service layer tests
```

---

## Python Pipeline Tests

Located in `tests/` directory. Uses pytest.

### Running Tests

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests
pytest

# Verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_models.py -v

# Run tests matching pattern
pytest -k "test_keyword" -v

# Stop on first failure
pytest -x

# With coverage
pytest --cov=src/nicheiq --cov-report=term-missing
```

### Test Categories

#### Configuration Tests
```bash
pytest tests/unit/test_config.py -v
```
- Settings loading from .env
- Default value handling
- Type conversions

#### Model Tests
```bash
pytest tests/unit/test_models.py -v
pytest tests/unit/test_model_helpers.py -v
pytest tests/unit/test_keyword_validation_crew_models.py -v
```
- Pydantic model validation
- Field constraints
- Serialization/deserialization

#### LLM Service Tests
```bash
pytest tests/unit/test_llm_service.py -v
pytest tests/unit/test_llm_service_components.py -v
```
- Centralized LLM API
- Model selection
- Structured output generation

#### Report Generation Tests
```bash
pytest tests/unit/test_final_report_generator.py -v
pytest tests/unit/report/ -v
```
- Report assembly
- Score accessor methods
- Validation edge cases

#### Token Monitoring Tests
```bash
pytest tests/unit/test_token_monitor.py -v
```
- Token counting
- Cost estimation
- Warning thresholds

#### SEO & Keyword Tests
```bash
pytest tests/unit/test_seo_strategy_validators.py -v
pytest tests/unit/test_score_refinement.py -v
pytest tests/unit/test_keyword_filtering.py -v
```
- SEO strategy validation
- Keyword tier classification
- Score refinement logic

#### Utility Tests
```bash
pytest tests/unit/test_utils.py -v
pytest tests/unit/test_helpers_validation.py -v
pytest tests/unit/test_search_helpers.py -v
```
- Helper functions
- Data transformations
- Search query generation

#### Validation Tests
```bash
pytest tests/unit/validators/ -v
pytest tests/unit/utils/validation/ -v
```
- Score validators
- Text validators
- Checkpoint validators
- Social content validators

### Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov=src/nicheiq --cov-report=term-missing

# HTML report
pytest --cov=src/nicheiq --cov-report=html
open htmlcov/index.html

# XML for CI
pytest --cov=src/nicheiq --cov-report=xml
```

---

## Frontend Tests

Located in `frontend/src/**/__tests__/`. Uses Vitest.

### Running Tests

```bash
cd frontend

# Run once
npm test

# Watch mode
npm run test:watch

# With coverage
npm run test:coverage
```

### Test Files

| File | Description |
|------|-------------|
| `src/lib/__tests__/api.test.ts` | Backend API client tests |
| `src/routes/(app)/billing/__tests__/page.server.test.ts` | Billing page server tests |
| `src/routes/api/billing/checkout/__tests__/server.test.ts` | Checkout API tests |

### Writing Frontend Tests

```typescript
// src/lib/__tests__/example.test.ts
import { describe, it, expect, vi } from 'vitest';
import { myFunction } from '../myModule';

describe('myFunction', () => {
  it('should return expected result', () => {
    const result = myFunction('input');
    expect(result).toBe('expected');
  });

  it('should handle errors', () => {
    expect(() => myFunction(null)).toThrow();
  });
});
```

---

## Backend Tests

Located in `backend/src/**/__tests__/`. Uses Vitest.

### Running Tests

```bash
cd backend

# Run once
npm test

# Watch mode
npm run test:watch

# With coverage
npm run test:coverage
```

### Test Files

#### Route Tests (`src/routes/__tests__/`)

| File | Description |
|------|-------------|
| `billing.stripe.test.ts` | Stripe billing endpoints |
| `users.changePassword.test.ts` | Password change endpoint |
| `users.notificationPrefs.test.ts` | Notification preferences |
| `webhooks.stripe.test.ts` | Stripe webhook handling |

#### Service Tests (`src/services/__tests__/`)

| File | Description |
|------|-------------|
| `emailService.test.ts` | Email sending service |
| `notificationService.test.ts` | Notification service |
| `stripeService.test.ts` | Stripe integration |

### Writing Backend Tests

```typescript
// src/services/__tests__/example.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MyService } from '../myService';

describe('MyService', () => {
  let service: MyService;

  beforeEach(() => {
    service = new MyService();
  });

  it('should process data correctly', async () => {
    const result = await service.process({ id: 1 });
    expect(result.success).toBe(true);
  });

  it('should handle missing data', async () => {
    await expect(service.process(null)).rejects.toThrow();
  });
});
```

---

## Validation Scripts

User-facing tools for environment and output validation.

### check_setup.py

Validates environment before running research.

```bash
python check_setup.py
```

**Checks:**
- Python version (3.10+)
- Required dependencies installed
- `.env` file exists
- API keys configured
- Output directory writable

**Exit codes:** `0` = passed, `1` = failed

### validate_report.py

Detects hallucinations and validates data integrity.

```bash
python validate_report.py <final_report.json> <research_state_raw.json>
```

**Validation categories:**
- Pain point conflation (research vs solution)
- Score accuracy (no rounding errors)
- CAC value precision
- Page count accuracy
- Competition intensity labels

**Exit codes:** `0` = passed, `1` = failed

---

## Writing Tests

### Python Test Structure

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

### Using Fixtures

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

### Mocking External APIs

```python
def test_api_call(mocker):
    """Test API call with mock."""
    mock_response = {"result": "success"}
    mocker.patch("requests.post", return_value=mock_response)

    result = my_api_function()
    assert result == mock_response
```

---

## Troubleshooting

### Tests Not Found

**Issue:** pytest doesn't find tests

**Solutions:**
1. Ensure test files start with `test_`
2. Check test functions start with `test_`
3. Verify imports: `pytest --collect-only`

### Import Errors

**Issue:** `ModuleNotFoundError: No module named 'nicheiq'`

**Solution:**
```bash
# Install package in editable mode
source .venv/bin/activate
pip install -e .
```

### Slow Tests

**Solutions:**
1. Run unit tests only: `pytest tests/unit/`
2. Use parallel execution: `pip install pytest-xdist && pytest -n 4`
3. Skip slow tests with markers

### API Rate Limits

**Solutions:**
1. Use mocks for API calls
2. Run unit tests for development
3. Add delays: `pytest --maxfail=1`

### TypeScript Test Issues

**Issue:** Vitest configuration errors

**Solution:**
```bash
# Ensure dependencies installed
npm install

# Check vitest config exists
cat vitest.config.ts
```

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Testing commands reference
- [README.md](../README.md) - Quick start
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

---

**Last Updated**: 2026-01-26
