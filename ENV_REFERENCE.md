# .env Configuration Reference

Quick reference for all environment variables in NicheIQ.

## Required Variables

These MUST be set for NicheIQ to work:

```bash
# OpenAI - Powers AI agents
OPENAI_API_KEY=sk-proj-...
# Get at: https://platform.openai.com/api-keys
# Cost: ~$0.50-$2.00 per research

# Serper.dev - Google Search
SERPER_API_KEY=...
# Get at: https://serper.dev
# Free tier: 2,500 searches

# Reddit - Content collection
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
# Get at: https://www.reddit.com/prefs/apps
# Free: Unlimited

# DataForSEO - Keyword research
DATAFORSEO_LOGIN=your.email@example.com
DATAFORSEO_PASSWORD=...
# Get at: https://dataforseo.com
# Free: $1 credit (~10 runs)
```

## Optional Variables

### Twitter/X Collection

```bash
# Leave blank for guest mode (rate limited)
TWITTER_USERNAME=your_handle
TWITTER_PASSWORD=your_password
TWITTER_EMAIL=your_email@example.com
```

**When to use:**
- Need more than 10-15 Twitter threads per research
- Want better rate limits
- Researching Twitter-heavy niches

**When to skip:**
- Just starting out (guest mode is fine)
- Reddit provides enough data
- Security concerns (credentials stored locally)

---

## Application Settings

### Logging

```bash
LOG_LEVEL=INFO
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Use DEBUG when troubleshooting
```

### API Behavior

```bash
MAX_RETRIES=3
# How many times to retry failed API calls
# Increase if you have unstable internet

TIMEOUT_SECONDS=30
# API request timeout in seconds
# Increase if requests are timing out
```

### Model Selection

```bash
OPENAI_MODEL_NAME=gpt-4o
# Options:
#   - gpt-4o: Recommended, best quality
#   - gpt-4o-mini: 75% cheaper, good quality
#   - gpt-4-turbo-preview: Alternative, similar cost
#   - gpt-3.5-turbo: Cheapest, lower quality
```

### Specialized Model Configuration (Advanced)

NicheIQ uses a multi-model strategy to optimize cost vs quality by assigning different models to different cognitive tasks. This can reduce costs by 60-90% while maintaining output quality.

```bash
# Default model for general agent reasoning (complex analysis, ideation)
OPENAI_MODEL_NAME=gpt-4o

# Tool Calling & Structured Outputs (60% cost reduction)
FUNCTION_CALLING_LLM=gpt-4o-mini
# Used for: Tool execution, structured data extraction
# Why mini: Simple tool calls don't need advanced reasoning

# Content Analysis & Categorization
CONTENT_ANALYSIS_LLM=gpt-4o
# Used for: Social media content categorization, sentiment analysis
# Why gpt-4o: Nuanced understanding of discussions required

# Thread Relevance Filtering (60% cost reduction)
THREAD_VALIDATION_LLM=gpt-4o-mini
# Used for: Binary decisions (relevant/irrelevant URLs)
# Why mini: Simple yes/no decisions

# Creative Ideation & Brainstorming
BRAINSTORM_LLM=gpt-4o
# Used for: Solution generation, strategic thinking
# Why gpt-4o: Complex reasoning and creativity required

# Keyword Relevance Validation (90% cost reduction)
KEYWORD_VALIDATION_LLM=gpt-4.1-nano
# Used for: Quick keyword relevance checks
# Why nano: Ultra-fast, simple validation task

# Keyword Research & Analysis (60% cost reduction)
KEYWORD_RESEARCH_LLM=gpt-4o-mini
# Used for: SEO keyword analysis and tier classification
# Why mini: Structured analysis, good with metrics
```

**Cost Impact Example** (expat relocation niche):
- All gpt-4o: ~$2.20 per run
- Multi-model (default): ~$0.85 per run (60% savings)
- Aggressive (more mini): ~$0.30 per run (85% savings)

**When to Override**:
- Budget-conscious: Use more `gpt-4o-mini` for non-critical tasks
- Quality-focused: Use `gpt-4o` everywhere if output quality issues observed
- Testing: Use `gpt-3.5-turbo` for rapid iteration (not recommended for production)

### Solution Validation

```bash
TOP_SOLUTIONS_FOR_VALIDATION=3
# Number of top-ranked solutions to validate in Stage 8 (Pricing) and Stage 8.5 (Keyword Validation)
# Use cases:
#   - 1: Fastest, only validates the top solution
#   - 3: Balanced (recommended), validates top 3 solutions
#   - 5: Thorough, validates all generated solutions
# Higher values increase API costs but provide pricing/keyword data for more solutions
# Useful when Stage 8.5 re-ranking might change the winner
```

---

## Search Configuration

### Result Limits

```bash
MAX_SEARCH_RESULTS=20
# Maximum URLs to collect per platform
# Higher = more data but slower and costlier
# Recommended: 15-25 for quality niches
```

### Reddit Quality Filters

```bash
MIN_REDDIT_UPVOTES=5
# Minimum upvotes for a post to be collected
# Higher = more viral/popular posts only
# Recommended ranges:
#   - 1-3: Include smaller discussions
#   - 5-10: Popular discussions only
#   - 20+: Very popular/viral only

MIN_REDDIT_COMMENTS=3
# Minimum comments for engagement signal
# Higher = more discussion/engagement
# Recommended ranges:
#   - 1-2: Any discussion
#   - 3-5: Active discussions
#   - 10+: Very engaged threads

REDDIT_COMMENT_LIMIT=None
# How many "load more comments" to expand
# Options:
#   - None: Load ALL comments (slowest, most complete)
#   - 32: Load most comments (balanced, recommended)
#   - 0: Top-level comments only (fastest)
# Note: More comments = slower but more pain points
```

### Twitter Quality Filters

```bash
MIN_TWITTER_LIKES=5
# Minimum likes for a tweet to be collected
# Higher = more popular tweets only

MIN_TWITTER_REPLIES=3
# Minimum replies for engagement signal
# Higher = more discussion
```

---

## Keyword Research Configuration

### Search Volume Filtering

```bash
KEYWORD_MIN_SEARCH_VOLUME=50
# Minimum monthly Google searches
# Use cases:
#   - 10-50: Niche/long-tail keywords
#   - 50-100: Balanced approach (recommended)
#   - 100-500: Popular keywords only
#   - 1000+: High-volume only (competitive)
```

### Competition Filtering

```bash
KEYWORD_MAX_COMPETITION=0.7
# Maximum competition score (0.0 = none, 1.0 = highest)
# Use cases:
#   - 0.0-0.3: Low competition (easier to rank)
#   - 0.4-0.7: Medium competition (balanced, recommended)
#   - 0.8-1.0: High competition (competitive keywords)
```

### Geographic Targeting

```bash
TARGET_LOCATION=2840
# DataForSEO location code
# Common codes:
#   - 2840: United States
#   - 2826: United Kingdom
#   - 2124: Canada
#   - 2036: Australia
#   - 2276: Germany
#   - 2250: France
# Full list: https://docs.dataforseo.com/v3/appendix/locations/
```

### Language Targeting

```bash
TARGET_LANGUAGE=en
# ISO language code
# Common codes:
#   - en: English
#   - es: Spanish
#   - de: German
#   - fr: French
#   - pt: Portuguese
#   - ja: Japanese
```

---

## Output Configuration

```bash
OUTPUT_DIR=./output
# Base directory for all outputs
# Reports and logs will be saved here

REPORTS_DIR=./output/reports
# Specific directory for JSON reports
# Can be same as OUTPUT_DIR
```

---

## Performance Optimization

### Parallel Validation

NicheIQ can process validation tasks in parallel for faster execution. This applies to:
- **Keyword validation** (Stage 9.5c): Validating 150-500+ keywords for relevance
- **Thread validation** (Stage 5): Validating Reddit/Twitter search results

```bash
# Enable/disable parallel validation (default: true)
VALIDATION_PARALLEL_ENABLED=true

# Keyword validation workers (default: 3)
# Recommended: 3-5 for balance of speed and API limits
# Stage 9.5c processes 150-500+ keywords
KEYWORD_VALIDATION_MAX_WORKERS=3

# Keywords per API call within each parallel worker (default: 50)
# Recommended: 50-150
# Lower values = more API calls but better LLM attention
# Higher values = fewer API calls but may reduce accuracy
KEYWORD_VALIDATION_BATCH_SIZE=50

# Thread validation workers (default: 2)
# Recommended: 2-3 for smaller batch volumes
# Stage 5 processes 20-100 search results
THREAD_VALIDATION_MAX_WORKERS=2
```

**Performance Impact:**
- **3x faster validation** (45-90s → 15-30s savings per run)
- **No cost increase** (same API calls, just concurrent)
- **API rate limits respected** (conservative worker counts)

**When to adjust:**
- **Increase workers (4-5)**: OpenAI Tier 2+ accounts with higher rate limits
- **Decrease workers (1-2)**: Tier 1 accounts or debugging
- **Disable parallel (`VALIDATION_PARALLEL_ENABLED=false`)**: Troubleshooting or sequential debugging

**Note:** Setting `max_workers=1` or disabling parallel validation will fall back to sequential processing with no functionality changes.

---

## Report Generation & Validation

### Validation Thresholds

These settings control the validation and scoring logic in Stage 10 (Final Report Generation). All thresholds are configurable to allow tuning for different market conditions or business requirements.

#### Market Validation Levels

```bash
# Minimum search volume for STRONG market validation
MARKET_VALIDATION_STRONG_VOLUME=100000
# Default: 100,000
# Higher values = more conservative validation

# Minimum pain point count for STRONG market validation
MARKET_VALIDATION_STRONG_PAIN_POINTS=10
# Default: 10
# Requires at least this many identified pain points

# Minimum search volume for MODERATE market validation
MARKET_VALIDATION_MODERATE_VOLUME=30000
# Default: 30,000
# Lower threshold than STRONG

# Minimum pain point count for MODERATE market validation
MARKET_VALIDATION_MODERATE_PAIN_POINTS=5
# Default: 5
# Lower threshold than STRONG
```

#### Go/No-Go Verdict Thresholds

These control the automated go/no-go decision in the executive dashboard:

```bash
# Minimum average score (all 4 dimensions) for "Go" verdict
VERDICT_GO_AVG_SCORE=0.75
# Default: 0.75 (range: 0.0-1.0)
# All scores: market_fit, competitive_advantage, technical_feasibility, seo_potential

# Minimum individual score for "Go" verdict
VERDICT_GO_MIN_INDIVIDUAL_SCORE=0.7
# Default: 0.7 (range: 0.0-1.0)
# Applies to market_fit and technical_feasibility (most critical)

# Minimum average score for "Conditional" verdict
VERDICT_CONDITIONAL_AVG_SCORE=0.60
# Default: 0.60 (range: 0.0-1.0)
# Conditional = proceed with caution

# Minimum individual score for "Conditional" verdict
VERDICT_CONDITIONAL_MIN_INDIVIDUAL_SCORE=0.55
# Default: 0.55 (range: 0.0-1.0)
# Below this = "No-Go" verdict
```

**Understanding Verdicts:**
- **Go**: All key metrics exceed thresholds - strong opportunity
- **Conditional**: Promising but has weaknesses - proceed with risk mitigation
- **No-Go**: Scores below thresholds - high risk or poor fit

#### Pain Point & Competitive Thresholds

```bash
# Minimum severity score for "high priority" pain point classification
PAIN_POINT_HIGH_PRIORITY_THRESHOLD=0.7
# Default: 0.7 (range: 0.0-1.0)
# Used in pain point analytics and prioritization

# Maximum competitor count for "Low" competitive intensity
COMPETITIVE_INTENSITY_LOW_THRESHOLD=3
# Default: 3 competitors
# < 3 competitors = Low competition

# Minimum competitor count for "High" competitive intensity
COMPETITIVE_INTENSITY_HIGH_THRESHOLD=8
# Default: 8 competitors
# >= 8 competitors = High competition
# Between low and high = Medium competition
```

#### Report Formatting

```bash
# Maximum character length for pain point quotes in evidence appendix
REPORT_MAX_QUOTE_LENGTH=200
# Default: 200 characters
# Quotes are truncated at word boundaries for readability
```

#### Score Defaults

```bash
# Default score when score data is missing (ScoreAccessor fallback)
SCORE_ACCESSOR_DEFAULT_FALLBACK=0.5
# Default: 0.5 (range: 0.0-1.0)
# A warning is logged whenever this default is used
# Lower = more conservative, higher = more optimistic
```

**When to adjust these settings:**
- **Market validation**: Adjust volume thresholds based on niche size (B2B vs B2C)
- **Verdict thresholds**: More conservative (0.80+) for high-risk markets, less conservative (0.65) for exploratory research
- **Competitive thresholds**: Adjust based on industry norms (SaaS vs physical products)
- **Default fallback**: Set to 0.0 for conservative estimates, 0.7 for optimistic

---

## Configuration Profiles

### Recommended Profiles by Use Case

#### Profile 1: Quality-Focused (Default)
```bash
MAX_SEARCH_RESULTS=20
MIN_REDDIT_UPVOTES=5
MIN_REDDIT_COMMENTS=3
MIN_TWITTER_LIKES=5
REDDIT_COMMENT_LIMIT=32
KEYWORD_MIN_SEARCH_VOLUME=50
KEYWORD_MAX_COMPETITION=0.7
```
**Best for**: Comprehensive research, validating serious opportunities

---

#### Profile 2: Fast Research
```bash
MAX_SEARCH_RESULTS=10
MIN_REDDIT_UPVOTES=10
MIN_REDDIT_COMMENTS=5
MIN_TWITTER_LIKES=10
REDDIT_COMMENT_LIMIT=0
KEYWORD_MIN_SEARCH_VOLUME=100
KEYWORD_MAX_COMPETITION=0.7
```
**Best for**: Quick validation, testing ideas, rapid iteration

---

#### Profile 3: Deep Dive
```bash
MAX_SEARCH_RESULTS=30
MIN_REDDIT_UPVOTES=3
MIN_REDDIT_COMMENTS=2
MIN_TWITTER_LIKES=3
REDDIT_COMMENT_LIMIT=None
KEYWORD_MIN_SEARCH_VOLUME=25
KEYWORD_MAX_COMPETITION=0.8
```
**Best for**: Thorough analysis, competitive markets, research reports

---

#### Profile 4: Budget-Conscious
```bash
MAX_SEARCH_RESULTS=10
MIN_REDDIT_UPVOTES=10
MIN_REDDIT_COMMENTS=5
MIN_TWITTER_LIKES=10
REDDIT_COMMENT_LIMIT=0
KEYWORD_MIN_SEARCH_VOLUME=200
OPENAI_MODEL_NAME=gpt-4o-mini
```
**Best for**: Minimizing API costs, frequent research runs

---

#### Profile 5: Niche/Long-Tail Focus
```bash
MAX_SEARCH_RESULTS=25
MIN_REDDIT_UPVOTES=1
MIN_REDDIT_COMMENTS=1
MIN_TWITTER_LIKES=1
REDDIT_COMMENT_LIMIT=32
KEYWORD_MIN_SEARCH_VOLUME=10
KEYWORD_MAX_COMPETITION=0.4
```
**Best for**: Small niches, underserved markets, long-tail opportunities

---

## Validation Checklist

Before running research, verify:

- [ ] All required variables are set (no `your_key_here` placeholders)
- [ ] API keys are valid and have credits
- [ ] No extra spaces or quotes around values
- [ ] File is saved as `.env` (not `.env.txt`)
- [ ] File is in project root directory
- [ ] `.env` is in `.gitignore` (don't commit secrets!)

**Test configuration:**
```bash
python -c "from nicheiq.config.settings import settings; print('✓ Config OK')"
```

---

## Common Mistakes

### ❌ Wrong
```bash
OPENAI_API_KEY="sk-proj-..."  # No quotes!
SERPER_API_KEY = abc123       # No spaces around =
MIN_REDDIT_UPVOTES=5.5        # Must be integer
```

### ✅ Correct
```bash
OPENAI_API_KEY=sk-proj-...
SERPER_API_KEY=abc123
MIN_REDDIT_UPVOTES=5
```

---

## Security Best Practices

1. **Never commit `.env` to git**
   - Already in `.gitignore`
   - Double-check: `git status` should not show `.env`

2. **Rotate keys periodically**
   - Generate new API keys every 3-6 months
   - Immediately rotate if accidentally exposed

3. **Use environment-specific files**
   - `.env.development` for testing
   - `.env.production` for live research
   - Load with: `ENV_FILE=.env.production python -m nicheiq.main ...`

4. **Limit API key permissions**
   - OpenAI: Set usage limits ($10/month)
   - DataForSEO: Monitor billing alerts
   - Use separate keys for development vs production

5. **Consider using secrets management**
   - For teams: Use 1Password, Vault, or AWS Secrets Manager
   - For CI/CD: Use GitHub Secrets or environment variables

---

## FAQ

**Q: What happens if I don't set optional variables?**
A: They use sensible defaults. Twitter will use guest mode, other settings use recommended values.

**Q: Can I override .env variables?**
A: Yes, set environment variables directly:
```bash
OPENAI_MODEL_NAME=gpt-4o-mini python -m nicheiq.main --niche "test"
```

**Q: Where do I find my current API usage?**
A:
- OpenAI: https://platform.openai.com/usage
- Serper: https://serper.dev/dashboard
- DataForSEO: https://app.dataforseo.com/billing

**Q: Can I use different settings per research run?**
A: Create multiple .env files:
```bash
# Load specific config
cp .env.fast .env
python -m nicheiq.main --niche "test"

# Or use environment variables
MIN_REDDIT_UPVOTES=10 python -m nicheiq.main --niche "test"
```

**Q: What's the minimum .env to get started?**
A: Just the 4 required sections (OpenAI, Serper, Reddit, DataForSEO). Everything else has defaults.

---

For detailed setup instructions, see [GETTING_STARTED.md](GETTING_STARTED.md).
