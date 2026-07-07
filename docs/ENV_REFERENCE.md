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

# Public catalog launch gate (Phase 4.5)
SEO_LAUNCH_GATE=true
# When 'true' (default): every /ideas/*, /idea/[slug], /pain-point/[slug] page
# ships with `<meta name="robots" content="noindex,follow">` and is omitted
# from sitemap.xml.
# When 'false': pages are indexable and emit in sitemap.
# Flip to 'false' once Phase 4.5 baseline copy curation completes (≥20
# top-traffic categories have hand-written longDescription + faqJson).
# Avoids Google's thin-content penalty during the rollout window.
#
# NOTE: The gate only affects SEO (robots meta + sitemap). Pages remain fully
# functional and authenticated features (Save, Validate, login flows) work
# normally regardless of the gate state.
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

# Catalog FAQ generation (Phase B — admin-triggered LLM Q&A)
OPENAI_FAQ_MODEL=gpt-4o-mini
# Model used by /api/admin/catalog/faq/generate to draft FAQs for sub-niche,
# idea, and pain-point detail pages. Same model used across all three entity
# types in v1. Per-deploy overridable without a code release.
# Code-level fallback when unset: 'gpt-4o-mini'.
# Recommended values:
#   - gpt-4o-mini   (~$0.0008/regenerate — fast, decent quality, default)
#   - gpt-4.1-mini  (similar cost, better instruction-following)
#   - gpt-4o        (~$0.020/regenerate — best adherence to nuanced rules
#                    like 'never use solution_name codename in idea-page
#                    questions'; ~25× the per-call cost of mini variants but
#                    still trivial at admin-trigger volume)
# Production deploys should set this explicitly so SEO/ops can swap models
# without redeploying the backend.

FAQ_GENERATE_RATE_HOURLY=30
# Per-admin per-hour cap on FAQ generation calls. Stops accidental loops
# from running up OpenAI cost. 31st call within the hour returns 429 with
# a Retry-After header; admin UI surfaces a friendly toast.

FAQ_SAVE_RATE_HOURLY=60
# Per-admin per-hour cap on FAQ save calls. Saves are cheap (Prisma update +
# Redis cache bust) but kept gated as a defense-in-depth measure.
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

# Pain-Point Quote Stance Verification
STANCE_VALIDATION_LLM=gpt-4o-mini
# Used for: classifying whether a retrieved quote genuinely expresses its pain
#   point (SUPPORTS / NEUTRAL / CONTRADICTS) before it is shown. One cheap call
#   per pain point in Stage 3 enrichment.
# Why mini: short, bounded classification over <=12 quotes

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

# Divergent Ideation Diversity (reduce duplicate / theme-clustered ideas)
# BRAINSTORM_LLMS=
# Comma-separated MODEL POOL round-robined across divergent samples for MODEL DIVERSITY.
# Empty (default) => every sample uses BRAINSTORM_LLM (single model -> shared priors -> dup-prone).
# Use decorrelated, REASONING-GRADE models (the divergent prompt is dense; weak models under-comply).
# Set NUM_DIVERGENT_SAMPLES >= the pool size to actually use every model.
# Each entry MAY carry an inline '@<effort>' for PER-MODEL reasoning effort
# (none/minimal/low/medium/high/xhigh); entries without '@' inherit BRAINSTORM_REASONING_EFFORT.
# Why per-model: under a forced tool_choice (how structured output is requested), some OpenRouter
# models behave badly with reasoning ON — DeepSeek emits the tool call into the 'reasoning' channel
# and/or under-generates, so use '@none'; Kimi returns empty with reasoning OFF, so use '@medium'.
# (The OpenRouter structured path now reads tool_calls -> content -> reasoning -> reasoning_details,
# so a misbehaving sample degrades gracefully instead of hard-failing — but '@effort' still controls
# reliability and cost.) Example:
#   openrouter/moonshotai/kimi-k2.6@medium,openrouter/deepseek/deepseek-v4-pro@none,openrouter/z-ai/glm-5.2@medium

# NUM_DIVERGENT_SAMPLES=2
# Number of INDEPENDENT divergent concept-generation calls pooled before filtering.
# Independent contexts break single-call mode collapse. Cost scales linearly on the brainstorm model.

# DIVERGENT_SAMPLE_DEADLINE_SECONDS=360
# Wall-clock cap for the parallel divergent fan-out. Once it elapses, the pool stops waiting for any
# still-running sample and proceeds with whatever finished. Guards against a runaway model — a reasoning
# model held open by OpenRouter keep-alive bytes, which the per-call read-timeout does NOT cap — stalling
# the whole pipeline. Allows a sample's 2x retry (~180s each) before abandoning.

# DIVERGENT_KEEP_FRACTION=0.5
# Fraction of the GENERATED divergent concepts to keep through the dedup/clamp step. 0.5 = keep at least half
# of what the samples produced, so good ideas aren't discarded before the refiner sees them. The kept count is
# floored at 6 (so a small single-model pool isn't starved) and capped at DIVERGENT_POOL_CAP. Dedup may leave
# fewer; duplicates are never re-added to hit the target.
# Example: 31 generated -> keep 15 (half, capped); 10 generated -> keep 6 (floor); 20 -> keep 10.

# DIVERGENT_POOL_CAP=15
# Upper bound (ceiling) on concepts kept after pooling/dedup, fed directly to the refiner (the LLM diversity
# filter was removed). Hard-capped at 15 (the RawConceptList max_length). The ACTUAL count scales with
# DIVERGENT_KEEP_FRACTION — this is the ceiling.

# DIVERGENT_DEDUP_SIMILARITY_THRESHOLD=0.85
# Cosine threshold for the embedding-based SEMANTIC dedup of pooled concepts
# (over concept name + one_liner + why_non_obvious). At/above it => near-duplicate, keep the most-novel.
# Catches cross-model / cross-wording dups the name + M/D/J-tag dedup misses. 0.0 disables; floor-guarded
# to 6 concepts; FAIL-OPEN on embedding error. Embeddings always use OpenAI (no OpenRouter endpoint).

# --- Pain-partitioned divergent ideation (permanent; flag removed 2026-07-06) ----------------
# Divergent generation runs ONE narrow generator per selected diverse pain (capped at
# DIVERGENT_MAX_GENERATORS) instead of N broad samples over the same pain list (falls back to the
# broad-sample path below 2 cells). Each generator focuses on
# its single pain, reasons as a REAL audience segment (Stage 6.5; falls back to generic stance archetypes).
# Pain coverage is guaranteed by construction and idea clustering is broken. Info-products
# (directory/aggregator/comparison) are NOT penalized — they are first-class SEO monetization outcomes;
# variety comes from the per-pain partition, not a type bias.
# Auto-falls back to the legacy broad-sample path when fewer than 2 distinct pains are available.
# DIVERGENT_MAX_GENERATORS=8        # ceiling on generators (~1 per diverse pain); 5-8 is the sweet spot
# DIVERGENT_MAX_WORKERS=8           # parallel generator threads in partitioned mode (legacy path stays at 4)
# DIVERGENT_PARTITIONED_KEEP_FRACTION=0.67  # keep-fraction override (narrow pain-separated concepts dedup
#                                   # far less than broad samples, so 0.5 over-discards them)

# --- Diversity-aware final selection -----------------------------------------------------------
# ENABLE_DIVERSITY_CAPS=false
# When ON, the convergent stage keeps MORE diverse ideas instead of squeezing to ~5. The post-crew
# enforcement (after coverage re-injection, before feasibility finalize) applies drop-only per-bucket caps:
# <= DIVERSITY_MAX_PER_SEGMENT by source_segment, <= DIVERSITY_MAX_PER_MECHANISM by mechanism family
# (greedy pairwise via _tags_match, strongest-composite anchors first), <= DIVERSITY_MAX_PER_PROJECT_TYPE
# by project_type, and a hard ceiling of DIVERSITY_MAX_FINAL_IDEAS. Weakest excess (lowest composite ->
# novelty -> market_fit) is dropped; ideas are never swapped or re-refined. The single most-novel idea
# and any idea that is the SOLE coverage of a high-severity pain are PROTECTED (never dropped). A floor
# (DIVERSITY_MIN_FINAL_IDEAS) re-admits the best dropped ideas, least-represented bucket first, so the set
# never goes thin. Logs a project_type / source_segment concentration metric per run.
# ENABLE_PAIN_SOURCE_DEDUP=false
# Extra dedup stage in the raw-concept pool: collapses concepts sharing (norm(source_pain), norm(data_source_tag))
# -- same pain attacked via the same data source -- which the >=2-of-3 mechanism/data/journey gate misses
# when journey_tag differs. Keeps the lowest-obviousness concept, floor-guarded (MIN_KEEP=6). No-op for
# concepts with no source_pain (legacy broad path) -- they are never bucketed together.
# DIVERSITY_MAX_FINAL_IDEAS=10      # ceiling on the Stage-1 selection set (caps make ~6-8 typical)
# DIVERSITY_MIN_FINAL_IDEAS=5       # floor: re-admit best dropped ideas to here
# DIVERSITY_MAX_PER_SEGMENT=2       # max ideas per source_segment
# DIVERSITY_MAX_PER_MECHANISM=2     # max ideas per mechanism family
# DIVERSITY_MAX_PER_PROJECT_TYPE=3  # lenient (info-products first-class); set 2 to force type-spread

# --- SEO-realism caps (downgrade-only, always on; mirror the feasibility caps) ------------------
# SEO scalability = realistic count of distinct, indexable, non-thin pages. These caps key ONLY on
# that — page count, page quality, and indexability. They do NOT penalize data sourcing (official vs
# unofficial/scraping): that affects feasibility/durability, not whether a page ranks, and is already
# scored by the feasibility critic — folding it in here would double-count. Lowers seo_scalability_score
# where the "thousands of indexable pages" story doesn't hold:
#   Rule A — account-gated SaaS whose output pages sit behind a login (not crawlable). Proxy:
#            project_type==saas AND data_access_model==restricted (no real account_gated flag exists)
#            -> ceiling SEO_CAP_GATED_SAAS_CEILING (0.5).
#   Rule B — thin/few page counts (the core SEO signal), ONLY post-Stage-12 when estimated_indexable_pages
#            is known: < SEO_CAP_THIN_PAGES_THRESHOLD (50) -> SEO_CAP_THIN_PAGES_CEILING (0.4);
#            < SEO_CAP_HIGH_SCORE_MIN_PAGES (300) -> SEO_CAP_MODERATE_PAGES_CEILING (0.7).
#   (Rule C — hand-seeded/non-programmatic content cap — removed 2026-07-07 as unreliable.)
# NEVER raises a score and NEVER recomputes the composite: applied on the Stage-1 preview (no Task-4
# ranking exists there) and on the selected solution at Stage 12 (after ranking is locked), so solution
# RANKING is unaffected — only the displayed score + the Go/No-Go verdict become realistic. Fail-open.
# SEO_CAP_REQUIRE_SAAS_FOR_GATING=true   # Rule A: require saas, not just restricted data
# SEO_CAP_GATED_SAAS_CEILING=0.5
# SEO_CAP_THIN_PAGES_THRESHOLD=50
# SEO_CAP_THIN_PAGES_CEILING=0.4
# SEO_CAP_HIGH_SCORE_MIN_PAGES=300
# SEO_CAP_MODERATE_PAGES_CEILING=0.7
# (Data sourcing — unofficial/ToS-gray — is intentionally NOT an SEO cap; it's a feasibility concern.)

# Feasibility grounding
# The merged build+data feasibility critic is PERMANENT (flag removed 2026-07-06; previously off in
# prod — prod now runs it): it scores build_feasibility / data_feasibility, classifies data_access_model
# (public | freemium | paywalled | unofficial | restricted), KEEPS ToS-gray 'unofficial' ideas (unofficial
# API / scraping lib) and drops only genuine no-route ones. Surfaces the data fields in the report
# (alternatives badge + the selected-solution "Data Feasibility" ring). Fail-open.
# (ENABLE_VERDICT_DATA_CAPS — downgrade-only verdict-boundary caps — removed 2026-07-07, never validated.)

# Realism score-calibration critic (default ON)
ENABLE_SCORE_CALIBRATION=true
# Independent critic that, AFTER refinement, re-scores all five displayed idea criteria (market_fit,
# technical_feasibility, novelty, seo_scalability, obviousness) against the same anchored bands + evidence and
# REPLACES the generator's optimistic self-scores. Originals are kept in *_score_raw + calibration_notes.
# Counters self-grading overconfidence; runs after _finalize_feasibility, batched + parallel, fail-open per batch.
SCORE_CALIBRATION_LLM=openrouter/qwen/qwen3.7-max
# Calibration judge — independent of the brainstorm pool. A/B winner (scripts/score_calibration_ab.py vs a
# gpt-5.2 reference): tightest to the reference on all 5 criteria with no market_fit overcorrection; beat
# gpt-5.4-mini / deepseek-v4-pro (overshot market_fit low) and glm-5.2 (equal quality, ~2.5x slower).
SCORE_CALIBRATION_REASONING_EFFORT=medium
# Critic depth — weighs evidence against the bands (a notch above the JUDGE tier).

# Angle-aware idea evaluation (always on — no feature flag)
IDEA_ANGLE_LLM=openrouter/qwen/qwen3.7-max
# In-cell classifier that assigns each idea a winning_angle (distribution_seo | novel_differentiation |
# vertical_workflow) with an angle_rationale + novelty_rationale, then ranks each idea by its OWN angle's
# weights (distribution upweights SEO + market_fit with a small non-zero novelty weight; novel upweights
# novelty; workflow upweights feasibility). Runs after calibration, before the novelty enhance; a post-union
# straggler-finisher catches re-injected ideas. So a low off-axis score (low mechanism-novelty for a catalog)
# is explained, not penalized.
IDEA_ANGLE_REASONING_EFFORT=medium
# Classifier depth — picks the angle + writes the rationales.
NOVELTY_ENHANCE_SKIP_SEO_FLOOR=0.5
# Novelty-enhance skips distribution_seo-angle ideas whose SEO score is at/above this floor — their edge is
# data representation, not a novel mechanism, so low mechanism-novelty is expected and shouldn't trigger a rewrite.
# NOTE: idea_focus (auto | novelty | distribution, default auto) is a PER-RUN REQUEST PARAMETER, not an env var.
# It tilts both what gets generated and the ranking emphasis toward an angle; it steers emphasis, not the truthful
# winning_angle label. Also available as a per-batch override on "Generate more ideas".

# Post-selection deep research — pressure-testing the ONE selected idea (the post-Stage-5 stages:
# competitor 5.5, SEO 6, pricing 7, market-sizing 9, report 14). See the in-app help page /help/deep-research
# and docs/DEEP_RESEARCH_IMPROVEMENT_PLAN.md.
#
# Angle-conditioned research: PERMANENT (ENABLE_ANGLE_CONDITIONED_RESEARCH flag removed 2026-07-07,
# A/B-validated 2026-06-30). Always front-loads the selected idea's winning-angle kill-question into the
# SEO + competitor crew prompts so deep research investigates what validates/kills THAT angle (honestly
# stress-tested, never inflated).
# SEO kill-question: PERMANENT (flag removed 2026-07-06). Deterministic SEO-thesis stress-test for
# distribution_seo ideas in Stage 6 (page ceiling + KD distribution + forum-soft-SERP bonus +
# penalty-risk flag). Catches the pSEO mirage. Only fires for distribution_seo.
# (Segment payability + substitute/adjacent critic evidence are PERMANENT — their enable flags were
# removed 2026-07-06 after same-day calibration-gate passes vs a neutral Fable panel. Remaining
# tuning levers: PAYABILITY_LOW_THRESHOLD (default 0.35; 0.0 disables the cap/floor/reclassify)
# and PAYABILITY_MARKET_FIT_CAP (default 0.55).)
ENABLE_LLM_VERDICT_EXPLANATION=true
# Explain the DECIDED Go/No-Go verdict with an LLM (told the verdict + score BANDS + angle + any downgrade),
# validated to match the verdict's stance and use NO raw decimals; deterministic band template as fallback.
ENABLE_ANGLE_AWARE_VERDICT=true
# LIFT-ONLY verdict averaging: avg = max(equal-weight, angle-weighted), so a strong distribution_seo idea isn't
# penalized for low novelty, but a winning_angle misclassification can never DEMOTE it. min(market_fit,tech) gate
# unchanged (boundary-grid A/B: 4 correct lifts, 0 demotes).
#
# PERMANENT (A/B-validated 2026-06-30; flags removed 2026-07-06):
# SEO kill-question verdict floor: ground an over-OPTIMISTIC distribution_seo verdict in the kill-question: when
# the page universe isn't winnable (winnable_pages low / median KD high), cap Go->Conditional + floor risk
# Low->Medium (downgrade-only). Keyed on the KD/winnability axis the SEO composite EXCLUDES by design, so it's new
# information, not a double-count of the existing thin-page Rule-B (penalty_risk_flag is strictly secondary here).
# Scoped market sizing: size the SERVICEABLE slice the selected idea actually addresses, not the whole niche:
# narrow the pain corpus to the idea's pain_points_addressed (token-overlap match), keep top-down keyword volume
# only as a labeled cross-check, and emit a qualitative "addresses N of M pains" scope note — NO fabricated
# bottom-up SAM (there is no headcount/ACV data to build one from). Falls back to niche-wide when nothing matches.
# Audience-conditioned deep research: forward the Stage-1 RESOLVED audience (tools_currently_used /
# frustrations_with_existing) into the competitor task prompt + the SEO seed-generation vocabulary, so deep
# research judges against the real buyer. Distinct from the Phase-1 audience-aware search/pain-mining bias.
# Multi-source evidence headline: rank the report's evidence appendix across ALL sources (Reddit + HN/YouTube +
# Twitter) by normalized engagement and surface a per-thread platform tag, vs the old Reddit-only-by-raw-score
# path. Keeps the top_reddit_threads JSON key for backward compatibility.

# Idea-improvement loop — creative MENTOR (runs after calibration, before the deterministic caps)
IDEATION_MENTOR_LLM=gpt-5.4-mini
# The reviewer/mentor in the per-idea improvement loop: it scores three soft dimensions and gives ONE creative
# direction, guiding weak/unverified ideas toward sharper, buildable, on-pain revisions (the ideator stays
# IDEATION_REFINE_LLM). Use a DIFFERENT family than the ideator so it doesn't self-judge leniently. Cost-gated:
# only below-bar ideas enter; data routes are flagged + search-verified, then the deterministic cap applies.
# gpt-5.4-mini won a 6-model bake-off (validated +0.21/+0.97 vs baseline on two runs; re-tune via
# scripts/idea_improvement_ab.py --v4 --reviewer-model). Requires OPENAI_API_KEY for the default model.
IDEATION_MENTOR_REASONING_EFFORT=medium
# Mentor depth — judges soft dimensions + proposes a creative direction, so it benefits from reasoning.

# Novelty-enhance pass — refiner model (novelty-enhance is permanent; flag removed 2026-07-06)
NOVELTY_ENHANCE_LLM=openrouter/deepseek/deepseek-v4-pro:nitro
# Refiner for the targeted novelty-enhance pass: when a validated-but-obvious cell winner is gated in, this
# model proposes a more differentiated MECHANISM on the same pain + data; the revision is re-scored and kept
# only if it strictly improves. SEPARATE from IDEATION_REFINE_LLM so the main ideator stays glm-4.7. Called
# reasoning-off + creative=True (tool transport sidesteps deepseek's structured-output field-drop class — the
# reason it is NOT the ideator). A/B winner (scripts-style refiner_multi.py across 3 niches): 4/4 Opus-audited
# GENUINE accepts vs glm-4.7 ~78%, highest novelty reach, often lifts feasibility — at the cost of higher
# latency. Use a family distinct from the calibration critic (qwen) so the refiner never self-judges.

# Keyword Relevance Validation (90% cost reduction)
KEYWORD_VALIDATION_LLM=gpt-4.1-nano
# Used for: Quick keyword relevance checks
# Why nano: Ultra-fast, simple validation task

# Pain Point Validation (Stage 6 refinement)
PAIN_POINT_VALIDATION_LLM=gpt-4.1-mini
# Used for: Validating and filtering pain points
# Why mini: Binary validation decisions, cost-effective

# Pain-to-Solution Mapping
PAIN_SOLUTION_MAPPING_LLM=gpt-4o-mini
# Used for: Mapping pain points to solution features
# Why mini: Structured mapping task

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

### OpenRouter (Alternative Provider, Per-Tier)

Point any chat-completion tier at an OpenRouter-hosted model by prefixing the
model id with `openrouter/`. When NicheIQ sees the prefix it routes that tier to
`https://openrouter.ai/api/v1` using `OPENROUTER_API_KEY` (the prefix is stripped
before the bare id, e.g. `google/gemma-2-27b-it`, is sent).

```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here   # https://openrouter.ai/keys
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1   # default
OPENROUTER_SITE_URL=                                # optional HTTP-Referer header (attribution)
OPENROUTER_APP_NAME=                                # optional X-Title header (attribution)

# Example: run the cheap competitor-extraction tier on gemma
COMPETITOR_EXTRACTION_LLM=openrouter/google/gemma-2-27b-it
```

**`OPENAI_API_KEY` stays required.** OpenRouter is supplemental: embeddings (CrewAI
knowledge/RAG) have no OpenRouter endpoint, the Codex landing-page tier needs the
OpenAI Responses API, and any non-overridden tier still uses OpenAI.

**Tier safety** (which tiers tolerate a weaker OpenRouter model):

| Class | Tiers | Notes |
|-------|-------|-------|
| Conditionally safe | `THREAD_VALIDATION_LLM`, `STANCE_VALIDATION_LLM`, `KEYWORD_VALIDATION_LLM`, `COMPETITOR_EXTRACTION_LLM`, `PAIN_SOLUTION_MAPPING_LLM` | Native structured output — needs a **tool-capable** OpenRouter model (gemma may fail) |
| Risky | `OPENAI_MODEL_NAME` (shared by ~23 agents), `PAIN_POINT_VALIDATION_LLM` | CrewAI prompt-based JSON; weak models may lose data, retry, or hard-fail on plain-`Task` steps |
| Needs strong/large-context model | `CONTENT_ANALYSIS_LLM` (needs ~400K context), `FUNCTION_CALLING_LLM` (tool calls) | Pick a model with the matching capability |
| Reasoning tiers | `BRAINSTORM_LLM`/`IDEATION_*` | Use a reasoning-capable OpenRouter model — the tier's `*_REASONING_EFFORT` IS forwarded (see below) |
| Blocked (raises at startup) | `LANDING_PAGE_LLM`, `LANDING_PAGE_EXECUTION_LLM` | Plain-`Task` creative steps + Codex/Responses-API only |

Backend features also accept `openrouter/*` ids: `SUGGEST_LLM_MODEL`,
`CATEGORIZE_LLM_MODEL`, `OPENAI_FAQ_MODEL` (backend `OPENAI_API_KEY` likewise stays
required).

**How it works:** model-name prefix routing, mirroring the Kimi/Moonshot pattern.

**Reasoning on OpenRouter (default OFF):** reasoning is controlled per tier via
`*_REASONING_EFFORT` and forwarded through OpenRouter's unified `reasoning` request param
(`extra_body`), which OpenRouter normalizes to each provider's native thinking format and
**silently ignores** for models that don't support it. The policy is **off by default**:

| `*_REASONING_EFFORT` value | What we send | Effect |
|---|---|---|
| `low` / `medium` / `high` / `xhigh` (→high) | `{"reasoning": {"effort": …}}` | **Reasoning ON** at that effort |
| `none` / `minimal` / unset | `{"reasoning": {"enabled": false}}` | **Reasoning OFF** (explicit disable) |

This **supports both reasoning and non-reasoning models** and gives an explicit way to
**disable reasoning**:
- Reasoning-capable models (DeepSeek V4 Pro, GLM-5.2, Gemini 3.x Pro, Kimi K2.6) are valid
  for the reasoning tiers — set `low/medium/high` to engage thinking.
- Models that reason *by default* (Kimi, DeepSeek "think") are forced OFF on tiers that
  don't request reasoning, so they can't burn the output budget on hidden thinking and
  **truncate structured/tool-call output** (the failure seen on the validation tiers).
- Plain models (gemma, DeepSeek V4 Flash non-think) ignore the disable — no effect.

Applies uniformly across every OpenRouter path (crew agents, `invoke_structured`/`invoke_plain`,
raw `ChatOpenAI`/seed generation). The OpenAI path is unaffected (it uses `reasoning_effort`
natively).

**Cost tracking:**
- LangChain-direct calls (`LLMService.invoke_structured`/`invoke_plain` — e.g. thread/
  keyword validation, competitor extraction, pain-solution mapping, and all Stage-14
  report generation) use OpenRouter's **actual** returned `usage.cost` when present
  (`cost_source: "actual"` in the per-stage breakdown). OpenAI returns no cost, so those
  fall back to the price-table estimate (`cost_source: "estimated"`).
- CrewAI crew agents are always **estimated** from the price table — CrewAI's
  `usage_metrics` exposes tokens only, not the provider's cost. Unlisted models are
  recorded at $0 with a one-time warning (never mispriced as gpt-4o).
- `cost_summary` (in the saved `research_state_raw_*.json` and run logs) reports
  `total_cost` plus `total_cost_source` and an actual-vs-estimated split.

**Known untracked LLM cost** (lower bound caveat): thread/keyword validators and
query/seed generators discard their usage; embeddings (OpenAI) and external APIs
(Serper/Reddit/etc.) are not counted.

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

WEBSHARE_API_KEY=
# Webshare API key (optional). When set, YouTube transcript fetching routes
# through direct-mode residential proxies fetched dynamically from
# /api/v2/proxy/list. Bypasses YouTube's datacenter-IP blocks which cause
# IpBlocked errors in production worker deployments.
# Get a key at: https://proxy2.webshare.io/userapi/keys
#
# Plan compatibility: this integration uses mode=direct (per-proxy static IPs
# and credentials). Residential/backbone plans (pool_filter=residential) are
# NOT supported by this integration — they return no proxies from
# /api/v2/proxy/list?mode=direct and will fall back to direct fetching.

WEBSHARE_PROXY_COUNTRY_CODES=
# Optional ISO country code filter for the Webshare proxy pool
# (comma-separated, e.g. "US,GB"). Leave empty for no filter (all countries).

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

# Part C audience-aware research: PERMANENT (flag removed 2026-07-06; previously off in prod —
# prod now runs it). When Stage-1 detected a focusable audience (audience_scope = segment_of_niche
# or community), query generation and pain mining get a SOFT, ADDITIVE audience bias. Broad
# coverage is preserved — never narrowed; audience-less niches are a no-op.

AUDIENCE_QUERY_ALLOTMENT=6
# Extra Reddit query slots reserved for audience-flavored queries when the gate
# above is on. Added ON TOP of NUM_SEARCH_QUERIES so the broad set is untouched.
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
# Minimum topic-cluster coverage (enrichment loop stopping condition)
KEYWORD_CLUSTER_MIN_COVERAGE=0.7
# Minimum percentage of topic clusters that must have keywords (0.0-1.0)
# before the enrichment loop can stop. Renamed from
# KEYWORD_ENRICHMENT_MIN_COVERAGE, which now exclusively means the
# validated/total enrichment quality threshold (default 0.30).

# Minimum enrichment validation coverage (quality gate)
KEYWORD_ENRICHMENT_MIN_COVERAGE=0.30
# Warn when fewer than this fraction of enriched keywords pass validation

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

### Cost Logging

Cost tracking is controlled by `COST_LOGGING_ENABLED` (see Logging & Monitoring).
When on, the pipeline tracks per-stage token costs and logs a summary at the end
of the run.

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
NUM_SEARCH_QUERIES=40
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
NUM_SEARCH_QUERIES=20
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
NUM_SEARCH_QUERIES=60
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
NUM_SEARCH_QUERIES=20
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
NUM_SEARCH_QUERIES=50
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
