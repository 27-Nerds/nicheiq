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
REDDIT_USER_AGENT=NicheIQ/0.1.0
# Get at: https://www.reddit.com/prefs/apps
# Free: Unlimited
# User agent: Identifies your app to Reddit API (default: NicheIQ/0.1.0)

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

### Analytics (Frontend)

```bash
# Google Analytics GA4 Measurement ID
PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
# Get at: https://analytics.google.com → Admin → Data Streams → your stream → Measurement ID
# Leave empty to disable analytics entirely
# Note: This is a build-time variable — must be set before `npm run build`
# In Docker: passed as a build ARG in Dockerfile.frontend
```

**When to use:**
- Production deployments where you want pageview analytics
- Set in deployment environment or `.env` before building

**When to skip:**
- Development (analytics auto-disabled via `dev` flag)
- Staging (leave empty to disable)

**GDPR:** Analytics only loads after user accepts cookies via the consent banner.

### Stripe Payments

Configure Stripe for token package purchases.

```bash
# Stripe API Secret Key (starts with sk_)
STRIPE_SECRET_KEY=sk_live_...
# Get at: https://dashboard.stripe.com/apikeys
# Use sk_test_... for development

# Stripe Webhook Signing Secret (starts with whsec_)
STRIPE_WEBHOOK_SECRET=whsec_...
# Get at: https://dashboard.stripe.com/webhooks
# Required for processing payment confirmations
```

**Setup Steps:**

1. Create a Stripe account at https://stripe.com
2. Get your API keys from https://dashboard.stripe.com/apikeys
3. Create Products and Prices in Stripe Dashboard
4. Set up a webhook endpoint (see below)
5. Select webhook events (see below)
6. Copy the webhook signing secret

**Webhook URL:**

Production:
```
https://yourdomain.com/api/webhooks/stripe
```

Local development (using Stripe CLI):
```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
stripe listen --forward-to localhost:3001/api/webhooks/stripe
```
The CLI will output a temporary `whsec_...` secret - use that for `STRIPE_WEBHOOK_SECRET` locally.

**Webhook Events to Select:**

Only these events are handled by the backend:

| Event | Purpose |
|-------|---------|
| `checkout.session.completed` | **Required** - Adds credits to user after successful payment |
| `checkout.session.expired` | Optional - Logs when checkout session expires without payment |

Skip `checkout.session.async_payment_*` events - they're for delayed payment methods (bank transfers, SEPA) which aren't used since we only accept card payments.

**Test vs Live Keys:**
- Use `sk_test_...` keys for development (no real charges)
- Use `sk_live_...` keys for production

---

### Authentication (OAuth & Internal)

Configure OAuth providers for user login and internal service authentication.

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
# Get at: https://console.cloud.google.com/apis/credentials
# Setup: Create OAuth 2.0 Client ID, add authorized redirect URIs

# GitHub OAuth
GITHUB_CLIENT_ID=Iv1.your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
# Get at: https://github.com/settings/developers
# Setup: Create OAuth App, set callback URL to /api/auth/callback/github

# Backend API URL (for frontend)
BACKEND_URL=http://localhost:3001
# Production: https://api.yourdomain.com
# Used by frontend to communicate with backend API

# Internal Service Authentication
INTERNAL_SERVICE_SECRET=your-32-char-secret-key-here
# Used for: Worker-to-backend authentication
# Generate: openssl rand -base64 32
# MUST match between backend and worker services

# Auth.js Secret
AUTH_SECRET=your-auth-secret-32-chars-minimum
# Used for: Session encryption in Auth.js
# Generate: openssl rand -base64 32
```

**OAuth Setup Steps:**

1. **Google OAuth:**
   - Go to https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Web application)
   - Add authorized redirect URI: `https://yourdomain.com/api/auth/callback/google`
   - Copy Client ID and Client Secret

2. **GitHub OAuth:**
   - Go to https://github.com/settings/developers
   - Create new OAuth App
   - Set callback URL: `https://yourdomain.com/api/auth/callback/github`
   - Copy Client ID and Client Secret

---

### Email Notifications (Backend)

Configure email notifications when jobs start, complete, or fail.

```bash
# Email Provider (smtp or sendgrid)
EMAIL_PROVIDER=smtp
# Options: smtp, sendgrid

FROM_EMAIL=noreply@yourdomain.com
# Email address shown in "From" field
```

**SendGrid API (Recommended):**

Better deliverability, tracking, and reliability.

```bash
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.your-api-key
FROM_EMAIL=noreply@yourdomain.com
```

**Setup Steps:**

1. Create a SendGrid account at https://sendgrid.com
2. Go to Settings → API Keys → Create API Key
3. Select "Full Access" or "Restricted Access" with Mail Send permissions
4. Copy the API key (shown only once!)
5. Verify your sender email/domain in Settings → Sender Authentication

Get your API key at: https://app.sendgrid.com/settings/api_keys

**SMTP Configuration:**

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@yourdomain.com
```

**SMTP Provider Examples:**

Gmail (requires App Password):
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
```

SendGrid via SMTP:
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.your-api-key
```

Amazon SES:
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-ses-smtp-user
SMTP_PASSWORD=your-ses-smtp-password
```

**User Preferences:**

Users can control which emails they receive via the API:
- `emailEnabled` - Master toggle for all notifications
- `emailOnJobStart` - Notify when job starts processing
- `emailOnJobComplete` - Notify when job completes successfully
- `emailOnJobError` - Notify when job fails

API endpoints:
- `GET /api/users/:userId/notification-preferences`
- `PUT /api/users/:userId/notification-preferences`

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

### Backend Server Configuration

```bash
# Node environment
NODE_ENV=development
# Options: development, production, test
# Affects logging, error handling, and security settings

# Server port
PORT=3001
# Backend API server port
# Default: 3001 (frontend uses 3000)

# Niche suggestion settings
SUGGEST_LLM_MODEL=gpt-4.1-nano
# Model for generating niche suggestions
# Nano model is fast and cheap for simple suggestions

SUGGEST_RATE_HOURLY=25
# Maximum niche suggestions per user per hour
# Prevents abuse of suggestion endpoint

SUGGEST_RATE_DAILY=50
# Maximum niche suggestions per user per day
# Prevents excessive API costs

# Job management
MAX_JOB_RUNTIME_HOURS=4
# Maximum hours a job can run before being killed
# Safety net for stuck jobs
# Worker sends heartbeats; jobs without heartbeat are marked failed
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

# GPT-5 Series Reasoning Control (optional)
# BRAINSTORM_REASONING_EFFORT=medium
# Values: none, minimal, low, medium, high, xhigh
# Only for GPT-5 series models (gpt-5, gpt-5.2, etc.)
# When set: Uses reasoning_effort parameter instead of temperature
# Leave UNSET for older models (gpt-4o, etc.) - they use temperature
# Note: Passing reasoning_effort to non-GPT-5 models causes API errors

# Keyword Relevance Validation (90% cost reduction)
KEYWORD_VALIDATION_LLM=gpt-4.1-nano
# Used for: Quick keyword relevance checks
# Why nano: Ultra-fast, simple validation task

# Keyword Research & Analysis (60% cost reduction)
KEYWORD_RESEARCH_LLM=gpt-4o-mini
# Used for: SEO keyword analysis and tier classification
# Why mini: Structured analysis, good with metrics

# Pain Point Validation (Stage 6 refinement)
PAIN_POINT_VALIDATION_LLM=gpt-4.1-mini
# Used for: Validating and filtering pain points
# Why mini: Binary validation decisions, cost-effective

# Pain-to-Solution Mapping
PAIN_SOLUTION_MAPPING_LLM=gpt-4o-mini
# Used for: Mapping pain points to solution features
# Why mini: Structured mapping task

# Quote Enrichment (Stage 6 Task 4)
QUOTE_ENRICHMENT_LLM=gpt-4.1-mini
# Used for: Finding verbatim quotes for pain points via vector search
# Why mini: Literal extraction task, doesn't need reasoning

# Quote enrichment target per pain point
QUOTE_ENRICHMENT_TARGET_PER_PAIN_POINT=8
# Number of quotes to find per pain point during enrichment
# Higher = more evidence but longer processing time

# Landing Page Generation (Stage 10+)
LANDING_PAGE_LLM=gpt-5.2
# Used for: Creative landing page content generation
# Why gpt-5.2: Needs strong creative and reasoning abilities

LANDING_PAGE_EXECUTION_LLM=gpt-5.1-codex-max
# Used for: Landing page code execution/generation
# Why codex: Optimized for code generation

# Landing Page Reasoning Effort (GPT-5 series only)
LANDING_PAGE_CREATIVE_REASONING_EFFORT=high
# Reasoning effort for creative content phase
# Options: none, minimal, low, medium, high, xhigh

LANDING_PAGE_EXECUTION_REASONING_EFFORT=medium
# Reasoning effort for code execution phase

LANDING_PAGE_VALIDATION_REASONING_EFFORT=low
# Reasoning effort for validation phase

# CrewAI Enterprise (Optional)
CREWAI_API_KEY=
# Optional: CrewAI+ enterprise features
# Enables: Enhanced monitoring, analytics, collaboration
# Get at: https://www.crewai.com/

CREWAI_STORAGE_DIR=
# Optional: Custom storage directory for CrewAI
# Default: Uses CrewAI's default location

# ChromaDB Embedding API Key
CHROMA_OPENAI_API_KEY=
# Optional: Separate API key for ChromaDB embeddings
# Default: Uses OPENAI_API_KEY if not set
```

### Alternative LLM Providers (Experimental)

NicheIQ supports using non-OpenAI models for specific agents. The provider is
auto-detected from the model name — just change the model and set the API key.

#### Moonshot AI (Kimi K2.5)

Kimi K2.5 is Moonshot AI's multimodal MoE model (1T total / 32B active params)
with a 256K context window. It's OpenAI-compatible and can be used as a drop-in
replacement for the landing page HTML execution agents.

```bash
# Step 1: Get an API key at https://platform.moonshot.ai
MOONSHOT_API_KEY=your_moonshot_api_key_here

# Step 2: Set the execution LLM to a Kimi model
LANDING_PAGE_EXECUTION_LLM=kimi-k2.5

# Step 3 (optional): Enable thinking mode for deeper reasoning
KIMI_THINKING=false  # default: false (instant mode)
```

**Modes:**

| Setting | Temperature | Behavior |
|---------|-------------|----------|
| `KIMI_THINKING=false` (default) | 0.6 | Instant mode — direct output, faster, cheaper |
| `KIMI_THINKING=true` | 1.0 | Thinking mode — internal reasoning before output, deeper analysis |

**Available Kimi models:**

| Model | Description |
|-------|-------------|
| `kimi-k2.5` | Multimodal MoE model, 256K context (instant mode) |

**Pricing:** $0.60/M input tokens. Free tier: 1.5M tokens/day.

**How it works:** When a model name starts with `kimi`, NicheIQ automatically
routes API calls to `https://api.moonshot.ai/v1` using your `MOONSHOT_API_KEY`.
The `reasoning_effort` parameter is ignored (only applies to GPT-5 series).

**To switch back:** Just change the model name back to an OpenAI model:
```bash
LANDING_PAGE_EXECUTION_LLM=gpt-5.1-codex-max
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
# Number of top-ranked solutions to validate in Stage 8 (Pricing) and keyword validation
# Use cases:
#   - 1: Fastest, only validates the top solution
#   - 3: Balanced (recommended), validates top 3 solutions
#   - 5: Thorough, validates all generated solutions
# Higher values increase API costs but provide pricing/keyword data for more solutions
# Useful when keyword validation re-ranking might change the winner

# Solution refinement toggle
SOLUTION_REFINEMENT_ENABLED=true
# Enable solution refinement and re-ranking after keyword validation
# When true: Solutions are refined based on keyword data
# When false: Skip refinement, use original rankings
```

---

## Search Configuration

### Data Collection Toggles

```bash
# Enable/disable data sources
ENABLE_REDDIT=true
# Enable Reddit data collection
# Set to false to skip Reddit entirely

ENABLE_TWITTER=false
# Enable Twitter/X data collection
# Default: false (requires credentials or uses rate-limited guest mode)

ENABLE_HACKERNEWS=true
# Enable Hacker News data collection via Algolia API (free, no auth needed)
# Default: true. Great for B2B/SaaS/developer niches.
# Set to false to skip HN entirely

ENABLE_YOUTUBE=false
# Enable YouTube transcript collection (requires youtube-transcript-api package)
# Default: false. Set to true to collect YouTube video transcripts and comments.

YOUTUBE_API_KEY=
# YouTube Data API v3 key (optional). Enables:
# - Accurate engagement metrics (views, likes, comment count)
# - Top YouTube comments as evidence for pain point analysis
# - Channel name and exact upload date
# Free tier: 10,000 quota units/day (~300+ research runs)
# Get a key at: https://console.cloud.google.com/apis/credentials
# If not set, YouTube still works but only collects transcripts via Serper metadata.

MAX_YOUTUBE_VIDEOS=25
# Maximum YouTube videos to collect per run (default: 25)
# Each video costs ~1 API quota unit for comment fetching

MAX_YOUTUBE_COMMENTS_PER_VIDEO=20
# Maximum top comments to fetch per video, ordered by relevance (default: 20)

MIN_YOUTUBE_COMMENT_LIKES=5
# Minimum likes for YouTube comments to be included (default: 5, reduces noise)

MIN_YOUTUBE_COMMENT_LENGTH=50
# Minimum character length for YouTube comments (default: 50)

# Hacker News quality filters
MIN_HN_POINTS=5
# Minimum points for Hacker News stories (default: 5)

MIN_HN_COMMENTS=3
# Minimum comments for Hacker News stories (default: 3)

# Search query generation
NUM_SEARCH_QUERIES=40
# Number of search queries to generate for Reddit/Twitter/HN
# Higher = more diverse results but more API calls
# Recommended: 30-50 for thorough coverage
```

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

MAX_REDDIT_CONTENT_TOKENS=400000
# Maximum tokens for Reddit content in Stage 6 (PainPointCrew)
# Posts are sorted by engagement/recency score and trimmed to fit budget
# Formula: post.score / days_old (recent high-engagement posts prioritized)
# Options:
#   - 200000: Aggressive filtering (top posts only)
#   - 400000: Balanced (recommended)
#   - 600000: Include more posts (higher cost)
# Note: Prevents context overflow while keeping best content

# Comment-level quality filters
MIN_COMMENT_LENGTH=50
# Minimum character length for comments to be included
# Filters out short, low-value comments like "this" or "same"
# Recommended: 30-100 characters

MIN_COMMENT_SCORE=2
# Minimum Reddit score (upvotes - downvotes) for comments
# Higher = only include upvoted, quality comments
# Recommended: 1-5
```

### Reddit Freshness Search

These settings control supplemental search passes that bring in recent Reddit posts that Google's default ranking tends to bury.

```bash
# Enable date-filtered Serper search pass (default: true)
REDDIT_FRESHNESS_SEARCH_ENABLED=true
# Runs a second Serper search pass on a subset of queries with a Google tbs
# (time-based search) filter so recently-published posts appear in results.
# Cost: ~8 extra Serper calls per run (~$0.008)

# Google tbs (time-based search) parameter for freshness pass
REDDIT_FRESHNESS_TBS=qdr:y
# Options:
#   - qdr:d: Last 24 hours
#   - qdr:w: Last week
#   - qdr:m: Last month
#   - qdr:y: Last year (recommended, broadest useful window)

# Fraction of queries to use for the freshness Serper pass (0.0-1.0)
REDDIT_FRESHNESS_QUERY_FRACTION=0.3
# Default: 0.3 (30% of search queries get a freshness pass)
# Higher = more fresh results but more Serper API calls
```

### PRAW Native Reddit Search

Uses Reddit's own search API (via PRAW) to find very recent posts that Google hasn't indexed yet. Targets the "freshness gap" — posts from the last month.

```bash
# Enable PRAW native subreddit search (default: true)
REDDIT_NATIVE_SEARCH_ENABLED=true
# Searches the top subreddits found in Serper results using PRAW's
# subreddit.search() with a time_filter, finding posts too new for Google.
# No extra API cost — uses existing Reddit API credentials.

# PRAW time_filter for native search
REDDIT_NATIVE_SEARCH_TIME_FILTER=month
# Options: hour, day, week, month, year, all
# Default: month (targets Google's freshness gap)

# Fraction of queries to use for PRAW native search (0.0-1.0)
REDDIT_NATIVE_SEARCH_QUERY_FRACTION=0.25
# Default: 0.25 (25% of search queries)
# Lower than freshness Serper because PRAW search is slower

# Max results per query+subreddit combination
REDDIT_NATIVE_SEARCH_MAX_RESULTS=10
# Default: 10
# Searches top 5 subreddits × selected queries
```

**How freshness search works:**

Stage 5 now runs three search passes in sequence:

1. **Standard Serper** — existing `site:reddit.com` queries (unchanged)
2. **Freshness Serper** — 30% of queries re-run with `tbs=qdr:y` date filter
3. **PRAW Native** — 25% of queries searched directly on Reddit's top subreddits

All results are deduplicated before validation. If freshness searches fail, the pipeline continues with standard results only (graceful degradation). Both freshness passes have circuit breakers: 2 consecutive Serper errors or 3 consecutive PRAW errors disable the remaining queries for that pass.

**When to adjust:**
- **Disable freshness search** (`REDDIT_FRESHNESS_SEARCH_ENABLED=false`): When researching historical niches where old posts are desirable
- **Tighten time filter** (`REDDIT_FRESHNESS_TBS=qdr:m`): When you only want very recent discussions
- **Disable PRAW search** (`REDDIT_NATIVE_SEARCH_ENABLED=false`): If Reddit API rate limits are a concern or credentials are limited

### Twitter Quality Filters

```bash
MIN_TWITTER_LIKES=5
# Minimum likes for a tweet to be collected
# Higher = more popular tweets only

MIN_TWITTER_REPLIES=3
# Minimum replies for engagement signal
# Higher = more discussion

# Twitter cookies cache path
TWITTER_COOKIES_CACHE=data/twitter_cookies.json
# Path to store Twitter session cookies
# Speeds up subsequent runs by reusing session
# Default: data/twitter_cookies.json
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

## Keyword Enrichment Configuration (Phase 6c)

Phase 6c enriches and validates keywords for relevance to the identified pain points and solutions. These settings control the enrichment process.

### Pivot Detection & Recovery

```bash
# Minimum volume threshold for pivot detection
KEYWORD_MIN_VOLUME_THRESHOLD=10
# Keywords below this volume trigger potential pivot consideration
# If too many low-volume keywords, may indicate wrong keyword focus

# Maximum pivot attempts before proceeding
KEYWORD_PIVOT_MAX_ATTEMPTS=4
# Number of times to retry with different keyword strategies
# Prevents infinite loops on difficult niches

# Quick expansion batch size
KEYWORD_QUICK_EXPANSION_SIZE=50
# Number of keywords to fetch in quick expansion rounds
# Used when initial keywords have low coverage
```

### Validation Settings

```bash
# Enable keyword validation
KEYWORD_VALIDATION_ENABLED=true
# When true: Validates keywords against pain points/solutions
# When false: Skip validation, use all keywords

# Top pain points for validation context
KEYWORD_VALIDATION_TOP_PAIN_POINTS=5
# Number of top pain points to include in validation prompt
# More = better context but higher token cost

# Top competitors for validation context
KEYWORD_VALIDATION_TOP_COMPETITORS=10
# Number of top competitors to include in validation prompt
# Helps identify competitor-branded keywords

# LLM temperature for validation
KEYWORD_VALIDATION_TEMPERATURE=0.7
# Temperature for keyword validation LLM calls
# Lower = more consistent, higher = more creative decisions

# Relevance score threshold
KEYWORD_RELEVANCE_THRESHOLD=0.65
# Minimum relevance score (0.0-1.0) to keep a keyword
# Below this = keyword is filtered out as irrelevant
```

### Enrichment Targets

```bash
# Target enriched keyword count
KEYWORD_ENRICHMENT_TARGET_COUNT=150
# Target number of enriched keywords to collect
# Enrichment continues until this target is reached

# Minimum volume for enrichment candidates
KEYWORD_ENRICHMENT_MIN_VOLUME=500
# Only enrich keywords with at least this search volume
# Prevents wasting API calls on low-value keywords

# Maximum enrichment rounds
KEYWORD_ENRICHMENT_MAX_ROUNDS=5
# Maximum iterations of enrichment process
# Prevents infinite loops on sparse niches

# Keywords per enrichment batch
KEYWORD_ENRICHMENT_BATCH_SIZE=12
# Number of keywords to process per enrichment API call
# Balances cost vs accuracy
```

### Coverage Thresholds

```bash
# Minimum coverage for enrichment
KEYWORD_ENRICHMENT_MIN_COVERAGE=0.7
# Minimum coverage score (0.0-1.0) before enrichment stops
# Coverage = how well keywords cover identified pain points

# Target coverage threshold
KEYWORD_ENRICHMENT_TARGET_COVERAGE=0.60
# Target coverage to achieve during enrichment
# Enrichment continues until this is reached or max rounds hit

# Minimum tiering coverage
KEYWORD_TIERING_MIN_COVERAGE=0.30
# Minimum coverage required before tiering keywords
# Below this = too few keywords to tier meaningfully
```

---

## SEO Refinement Configuration

SEO refinement adjusts keyword volumes and tiers based on competitive analysis and market conditions.

```bash
# Enable SEO refinement
SEO_REFINEMENT_ENABLED=true
# When true: Applies volume adjustments and tier boosts
# When false: Use raw DataForSEO volumes

# Volume baselines by keyword type (JSON format)
SEO_REFINEMENT_VOLUME_BASELINES={"brand": 1000, "product": 500, "feature": 200, "problem": 100}
# Baseline volumes for different keyword categories
# Keywords below baseline may get boosted

# Maximum volume boost multiplier
SEO_REFINEMENT_MAX_VOLUME_BOOST=1.2
# Maximum multiplier for volume adjustments
# 1.2 = up to 20% boost for undervalued keywords

# Maximum Tier 1 boost
SEO_REFINEMENT_MAX_TIER1_BOOST=0.20
# Maximum score boost for Tier 1 promotion
# 0.20 = up to 20% score boost

# Volume discount floor
SEO_REFINEMENT_VOLUME_DISCOUNT_FLOOR=0.7
# Minimum multiplier when discounting overvalued volumes
# 0.7 = never reduce volume by more than 30%
```

---

## Checkpoint Configuration

Checkpointing enables resume capability for long-running research jobs.

```bash
# Enable checkpointing
CHECKPOINT_ENABLED=true
# When true: Saves state after each pipeline stage
# When false: No checkpoints, must restart from beginning on failure

# Checkpoint directory
CHECKPOINT_DIR=./output/checkpoints
# Directory to store checkpoint files
# Each job gets a subdirectory with stage-specific checkpoints

# Maximum checkpoint age (days)
CHECKPOINT_MAX_AGE_DAYS=7
# Checkpoints older than this are considered stale
# Stale checkpoints may be ignored during resume

# Auto-cleanup old checkpoints
CHECKPOINT_AUTO_CLEANUP=true
# When true: Automatically delete old checkpoint files
# When false: Manual cleanup required
```

**Resume Usage:**
```bash
# Resume from checkpoint
python -m nicheiq.main --niche "Your niche" --resume

# Force fresh start (ignore checkpoints)
python -m nicheiq.main --niche "Your niche" --no-resume
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
- **Keyword validation** (Phase 6c): Validating 150-500+ keywords for relevance
- **Thread validation** (Stage 5): Validating Reddit/Twitter search results

```bash
# Enable/disable parallel validation (default: true)
VALIDATION_PARALLEL_ENABLED=true

# Keyword validation workers (default: 3)
# Recommended: 3-5 for balance of speed and API limits
# Phase 6c processes 150-500+ keywords
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

## Cost Tracking & Token Monitoring

NicheIQ includes comprehensive cost tracking and token monitoring to help control API expenses.

### Token Monitoring

```bash
# Enable token counting and cost monitoring (default: true)
TOKEN_MONITORING_ENABLED=true

# Log warning when content exceeds this token count
TOKEN_WARNING_THRESHOLD=200000
# Default: 200,000 tokens
# Useful for identifying expensive stages

# Enable soft cap enforcement (default: false)
TOKEN_SOFT_CAP_ENABLED=false
# When true, logs critical warning when cap exceeded

# Soft cap token limit
TOKEN_SOFT_CAP=400000
# Default: 400,000 tokens
# Only enforced if TOKEN_SOFT_CAP_ENABLED=true

# Log estimated API costs for token usage (default: true)
COST_LOGGING_ENABLED=true
# Shows per-stage cost estimates during execution
```

### Token Budget Freshness Reserve

When processing Reddit posts for pain point analysis (Stage 6), a token budget limits how many posts fit in the LLM context. By default, posts are ranked purely by quality score, which can crowd out recent posts in favor of older, high-engagement ones. The freshness reserve guarantees a portion of the budget for recent content.

```bash
# Fraction of token budget reserved for fresh posts (default: 0.25)
TOKEN_BUDGET_FRESHNESS_RESERVE=0.25
# Default: 0.25 (25% of budget reserved for posts < freshness_days old)
# Set to 0 to disable (original quality-only behavior)
# The reserved portion is filled with fresh posts sorted by quality score.
# If insufficient fresh posts exist, the unused budget flows back to the
# quality pool — no tokens are wasted.

# Age threshold for "fresh" posts in days (default: 180)
TOKEN_BUDGET_FRESHNESS_DAYS=180
# Posts younger than this are eligible for the freshness reserve.
# Uses the same RECENT_DAYS constant as discussion recency scoring.
# Options:
#   - 90: Only very recent posts get reserved budget
#   - 180: Posts from last 6 months (recommended, matches recency scoring)
#   - 365: Posts from last year
```

**When to adjust:**
- **Increase reserve** (`TOKEN_BUDGET_FRESHNESS_RESERVE=0.4`): Niches where recency matters a lot (trending topics, news-driven markets)
- **Disable reserve** (`TOKEN_BUDGET_FRESHNESS_RESERVE=0`): Historical research or niches where old discussions are most valuable
- **Tighten freshness** (`TOKEN_BUDGET_FRESHNESS_DAYS=90`): Only reserve budget for very recent posts

### Cost Budget

```bash
# Enable cost budget tracking (default: false)
COST_BUDGET_ENABLED=false
# When true, tracks cumulative costs and logs warning when approaching limit

# Maximum API cost budget per run in USD
COST_BUDGET_LIMIT=5.00
# Default: $5.00
# This is a soft limit - logs warning when exceeded but doesn't halt execution
```

**Cost Tracking Features:**
- **Per-stage breakdown**: See costs for each pipeline stage (Pain Point Analysis, Solution Ideation, SEO Strategy, etc.)
- **Input/output token costs**: Tracks both prompt and completion tokens with accurate per-model pricing
- **CrewAI + LLM tracking**: Captures costs from both CrewAI crews and direct LLM calls
- **End-of-run summary**: Formatted cost report logged at pipeline completion

**Example Output:**
```
============================================================
COST SUMMARY
============================================================
Total Tokens: 250,000
  - Input tokens:  200,000 ($0.0500)
  - Output tokens: 50,000 ($0.0200)
Total Cost: $0.0700
------------------------------------------------------------
Per-Stage Breakdown:
  Stage 6 - Pain Point Analysis: $0.0350 (150,000 in / 30,000 out)
  Stage 7 - Solution Ideation: $0.0200 (30,000 in / 15,000 out)
  Stage 9 - SEO Strategy: $0.0150 (20,000 in / 5,000 out)
============================================================
```

**When to enable cost budget:**
- **Development/testing**: Set `COST_BUDGET_LIMIT=1.00` to catch runaway costs early
- **Production**: Set to expected maximum (~$3-5) as a safety net
- **Budget-conscious**: Enable to get visibility into per-run costs

---

## Report Generation & Validation

### Validation Thresholds

These settings control the validation and scoring logic in Stage 14 (Final Report Generation). All thresholds are configurable to allow tuning for different market conditions or business requirements.

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
VERDICT_GO_AVG_SCORE=0.72
# Default: 0.72 (range: 0.0-1.0)
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
- **Verdict thresholds**: More conservative (0.80+) for high-risk markets, less conservative (0.65) for exploratory research (default: 0.72)
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

For detailed setup instructions, see [SETUP.md](SETUP.md).
