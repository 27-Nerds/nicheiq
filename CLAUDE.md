# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Workflow Rules

Always read the relevant source file BEFORE attempting any edits. Never edit a file based on assumptions about its current content.

When writing user-facing text (tooltips, labels, descriptions) that references backend logic or calculations, always trace the actual backend code to verify accuracy before writing the text. Do not infer or assume how scores/metrics are calculated.

After implementing changes in Svelte files, check for Svelte 5 compatibility warnings (especially around state initialization from props, `$derived`, and runes). Resolve any warnings before considering the task complete.

Use an agent to trace how all score/metric values are calculated in the backend, then return a summary mapping each metric name to its calculation logic and source file before I start adding tooltips.

## Project Overview

NicheIQ is an AI-powered market research platform that transforms social media discussions into validated SaaS opportunities.

**Architecture:**

```
Frontend (SvelteKit) → Backend (Express) → Redis Queue → Worker → Python Pipeline
```

---

## Important: Python Environment

**Always activate the virtual environment before running any Python code:**

```bash
source .venv/bin/activate
```

**This project uses `uv` as the Python package manager** (faster alternative to pip):

```bash
# Create virtual environment
uv venv

# Install project in development mode
uv pip install -e ".[dev]"

# Add a new dependency
uv pip install <package>
```

---

## Frontend (`/frontend/`)

**Tech Stack:** SvelteKit 5, TypeScript, Tailwind CSS, Auth.js

**Run Development:**

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

**Run Tests:**

```bash
npm test             # Run once
npm run test:watch   # Watch mode
npm run test:coverage
```

**Build:**

```bash
npm run build        # Production build
npm run preview      # Preview production build
npm run check        # Type check
```

**Folder Structure:**

```
frontend/
├── src/
│   ├── routes/          # SvelteKit routes
│   │   ├── (app)/       # Protected routes (dashboard, jobs, settings)
│   │   ├── (public)/    # Public routes (login, register)
│   │   └── api/         # API routes
│   ├── lib/
│   │   ├── api.ts       # Backend API client
│   │   ├── components/  # UI components
│   │   ├── stores/      # Svelte stores
│   │   └── types/       # TypeScript types
│   ├── auth.ts          # Auth.js configuration
│   └── hooks.server.ts  # Server hooks
├── package.json
├── svelte.config.js
└── vite.config.ts
```

---

## Backend (`/backend/`)

**Tech Stack:** Express.js, TypeScript, Prisma, Redis, PostgreSQL

**Run Development:**

```bash
cd backend
npm install
npm run dev          # http://localhost:3001 (hot reload)
```

**Run Tests:**

```bash
npm test             # Run once
npm run test:watch   # Watch mode
npm run test:coverage
```

**Build & Production:**

```bash
npm run build        # Compile TypeScript
npm start            # Run compiled code
npm run typecheck    # Type check only
```

**Database Commands:**

```bash
npm run db:generate  # Generate Prisma client
npm run db:migrate   # Run migrations
npm run db:push      # Push schema to DB
npm run db:studio    # Open Prisma Studio
```

**Folder Structure:**

```
backend/
├── src/
│   ├── index.ts         # Express app entry point
│   ├── config.ts        # Environment configuration
│   ├── routes/          # API endpoints
│   │   ├── auth.ts      # Authentication
│   │   ├── jobs.ts      # Job CRUD
│   │   ├── users.ts     # User management
│   │   ├── workers.ts   # Worker communication (internal)
│   │   └── events.ts    # SSE endpoints
│   ├── services/        # Business logic
│   │   ├── jobService.ts
│   │   ├── queueService.ts
│   │   ├── emailService.ts
│   │   └── heartbeatService.ts
│   ├── middleware/      # Auth, rate limiting
│   └── types/           # Zod schemas
├── prisma/
│   └── schema.prisma    # Database schema
└── package.json
```

---

## Worker (`/worker/`)

**Tech Stack:** Python 3.12, RQ (Redis Queue)

**Run Worker:**

```bash
# Activate venv first!
source .venv/bin/activate

# From project root
python -m worker.run_worker

# Multiple workers
python -m worker.run_worker --workers 4

# Burst mode (exit when queue empty)
python -m worker.run_worker --burst
```

**Folder Structure:**

```
worker/
├── run_worker.py        # RQ worker entry point
├── queue_consumer.py    # Redis queue consumer
├── tasks.py             # Job execution (runs research pipeline)
├── progress.py          # Progress reporting to backend
├── heartbeat.py         # Worker health monitoring
└── status.py            # Job status updates
```

---

## Python Research Pipeline (`/src/nicheiq/`)

**Tech Stack:** Python 3.12, CrewAI, Pydantic, OpenAI

**Setup:**

```bash
# Create virtual environment with uv
uv venv
source .venv/bin/activate

# Install in development mode
uv pip install -e ".[dev]"
```

**Run Standalone:**

```bash
# Always activate venv first!
source .venv/bin/activate

# Run research
python -m nicheiq.main --niche "Your niche"

# Resume from checkpoint
python -m nicheiq.main --niche "Your niche" --resume
```

**Run Tests:**

```bash
source .venv/bin/activate
pytest                   # All tests
pytest tests/unit/       # Unit tests only
pytest tests/integration/# Integration tests only
pytest -v --cov          # With coverage
```

**Folder Structure:**

```
src/nicheiq/
├── main.py              # CLI entry point
├── flows/
│   └── research_flow.py # 16-stage orchestrator
├── crews/               # CrewAI crews
│   ├── pain_point_crew.py
│   ├── unified_solution_crew.py
│   ├── seo_strategy_crew.py
│   └── config/          # Agent/task YAML configs
├── models/              # Pydantic models
│   ├── research_state.py
│   ├── pain_point.py
│   ├── solution_idea.py
│   └── social_content.py  # RedditPost, SocialPost (generic), SocialContentCollection
├── tools/               # External API tools
│   ├── reddit_tool.py
│   ├── twitter_tool.py
│   ├── hackernews_tool.py  # Algolia HN API (free, no auth)
│   └── dataforseo_tool.py
├── report/              # Report generation
│   └── report_generator.py
└── config/
    └── settings.py      # Environment settings
```

---

## Docker Development

**Start Infrastructure (PostgreSQL + Redis):**

```bash
cd docker
docker compose up -d postgres redis
```

**Database Connection:**

- PostgreSQL: `localhost:5435` (user: nicheiq, pass: nicheiq)
- Redis: `localhost:6380`

**Full Stack (Production Profile):**

```bash
docker compose --profile production up -d
```

---

## Environment Variables

See `docs/ENV_REFERENCE.md` for complete reference.

**Essential:**

```bash
# API Keys
OPENAI_API_KEY=         # GPT-4o for agents
SERPER_API_KEY=         # Google search
REDDIT_CLIENT_ID=       # Reddit API
REDDIT_CLIENT_SECRET=

# Database
DATABASE_URL=postgresql://nicheiq:nicheiq@localhost:5435/nicheiq
REDIS_URL=redis://localhost:6380

# Auth
AUTH_SECRET=            # JWT secret (32+ chars)
INTERNAL_SERVICE_SECRET= # Worker-to-backend auth
```

---

## CrewAI Task YAML Templates

When writing task descriptions in `src/nicheiq/crews/config/*.yaml` files, **avoid using `{variable}` syntax** for literal examples or documentation. CrewAI interprets `{variable}` as template variables that get replaced at runtime.

**Problem:**

```yaml
# BAD - CrewAI will try to replace {city} with a variable
description: >
  URL pattern: /locations/{city}
```

**Solutions:**

```yaml
# GOOD - Use colon syntax for URL patterns
description: >
  URL pattern: /locations/:city

# GOOD - Use square brackets for placeholders
description: >
  URL pattern: /locations/[city]

# GOOD - Use double braces to escape (renders as literal {city})
description: >
  URL pattern: /locations/{{city}}
```

**Valid template variables** (passed via inputs dict):

- `{niche}`, `{selected_solution_name}`, `{value_proposition}`
- `{enriched_keywords_csv}`, `{top_pain_points}`, etc.

---

## CrewAI Guardrail Limitations

**Guardrails cannot modify LLM output.** The guardrail flow is:

1. LLM produces `task_output.raw`
2. Guardrail validates and returns `(True, task_output.raw)` or `(False, error)`
3. CrewAI re-parses the **original** `task_output.raw`

This means:

- Any "fix" applied during validation is discarded
- Don't write JSON repair functions in guardrails - they won't help
- If JSON is invalid, return `(False, error_message)` so CrewAI retries with a fresh LLM call
- Always return `task_output.raw` on success, never `result.model_dump_json()`

**Valid guardrail patterns:**

- Validate structure (field counts, required fields)
- Check business rules (diversity, thresholds)
- Detect truncation or repetition loops

**Invalid patterns (don't do this):**

- Fixing trailing commas, comments, or newlines
- Returning re-serialized JSON (`model_dump_json()`)

---

## Modifying Report Structure

When changing the report schema (adding/removing/modifying fields), you must update **all layers** in sequence:

1. **Pydantic Models** (`src/nicheiq/models/`)
   - Define new fields in the appropriate model (e.g., `research_state.py`, `seo_strategy.py`)
   - Use proper types and Field descriptions

2. **CrewAI Crew** (`src/nicheiq/crews/`)
   - Update task YAML configs to generate the new fields
   - Update `output_pydantic` references if model changed
   - Modify agent prompts if needed

3. **Report Generator** (`src/nicheiq/report/report_generator.py`)
   - Add field to `_assemble_base_report()` or related methods
   - Handle None/fallback cases

3b. **Preview Report Materializer** (`src/nicheiq/flows/research_flow.py`)

- Update `_materialize_preview_report()` if field affects Phase 1 sections
- Update placeholder data in `frontend/src/lib/data/previewPlaceholders.ts` if field affects locked sections

1. **Frontend Types** (`frontend/src/lib/types/report.ts`)
   - Add/update TypeScript interfaces to match Pydantic models
   - Keep field names identical (snake_case)

2. **Frontend Components** (`frontend/src/lib/components/sections/`)
   - Update the relevant section component to render new fields
   - Handle optional fields with `{#if}` guards

3. **Documentation** (`docs/`)
   - Update `JSON_REPORT_SCHEMA.md` with new field documentation
   - Update version history
   - Update `ARCHITECTURE.md` if pipeline stages changed

**Verification:**

```bash
# Python types
source .venv/bin/activate && python -c "from nicheiq.models.research_state import FinalReport; print('OK')"

# Frontend types
cd frontend && npm run check
```

---

## Multi-Source Data Collection

NicheIQ collects social content from multiple platforms. Reddit is the primary source; Hacker News is auto-enabled; Twitter is disabled/optional; YouTube is planned.

**Source architecture:**

- `RedditPost` / `TwitterThread` — platform-specific models (legacy, kept for backward compat)
- `SocialPost` — generic model for all new sources (`platform` field discriminates)
- `SocialContentCollection.generic_posts` — holds all `SocialPost` instances

**Adding a new source:**

1. Create tool in `src/nicheiq/tools/` following `hackernews_tool.py` pattern
2. Add `enable_<source>` setting in `config/settings.py`
3. Add collection block in `research_flow.py` Stage 2 (append to `generic_posts`)
4. No changes needed in PainPointCrew, content_preparers, trend_scoring — they already iterate `generic_posts`

**Content security:**
All scraped content is wrapped in delimiter fencing before reaching LLM agents:

```
======== UNTRUSTED SOCIAL CONTENT (source=hackernews, id=12345) ========
... scraped text (sanitized for injection patterns) ...
======== END UNTRUSTED CONTENT ========
```

**Quality pipeline (borrowed from last30days skill):**

- `utils/validation/dedup.py` — hybrid n-gram + token Jaccard deduplication
- `utils/engagement_normalizer.py` — per-platform engagement scoring (0-1 scale)
- `utils/snippet_extraction.py` — sliding-window best-evidence extraction
- `utils/validation/thread_validator.py:token_overlap_prefilter()` — fast pre-LLM relevance check

---

## Key Documentation

- `docs/ENV_REFERENCE.md` - Complete environment variable reference
- `docs/SETUP.md` - Python CLI and API key setup guide
- `docs/ARCHITECTURE.md` - Technical architecture details
- `docs/PATTERNS.md` - CrewAI patterns and templates
- `docs/TROUBLESHOOTING.md` - Common issues and fixes
- `docs/JSON_REPORT_SCHEMA.md` - Report JSON schema reference

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:

```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)

```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)

```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)

```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)

```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)

```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)

```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)

```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)

```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)

```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands

```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
