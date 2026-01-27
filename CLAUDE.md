# CLAUDE.md

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
│   └── research_flow.py # 10-stage orchestrator
├── crews/               # CrewAI crews
│   ├── pain_point_crew.py
│   ├── unified_solution_crew.py
│   ├── seo_strategy_crew.py
│   └── config/          # Agent/task YAML configs
├── models/              # Pydantic models
│   ├── research_state.py
│   ├── pain_point.py
│   └── solution_idea.py
├── tools/               # External API tools
│   ├── reddit_tool.py
│   ├── twitter_tool.py
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

4. **Frontend Types** (`frontend/src/lib/types/report.ts`)
   - Add/update TypeScript interfaces to match Pydantic models
   - Keep field names identical (snake_case)

5. **Frontend Components** (`frontend/src/lib/components/sections/`)
   - Update the relevant section component to render new fields
   - Handle optional fields with `{#if}` guards

6. **Documentation** (`docs/`)
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

## Key Documentation

- `docs/ENV_REFERENCE.md` - Complete environment variable reference
- `docs/SETUP.md` - Python CLI and API key setup guide
- `docs/ARCHITECTURE.md` - Technical architecture details
- `docs/PATTERNS.md` - CrewAI patterns and templates
- `docs/TROUBLESHOOTING.md` - Common issues and fixes
- `docs/JSON_REPORT_SCHEMA.md` - Report JSON schema reference
