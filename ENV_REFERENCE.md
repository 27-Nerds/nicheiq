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
