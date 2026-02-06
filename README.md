# NicheIQ

**AI-powered market research platform that transforms social media discussions into validated SaaS opportunities.**

NicheIQ is a full-stack application that combines a modern web interface with an autonomous AI research pipeline. Submit a niche, track progress in real-time, and receive comprehensive market analysis reports.

## Architecture

```
Frontend (SvelteKit) → Backend (Express) → Redis Queue → Worker → Python Pipeline
```

| Component | Technology | Description |
|-----------|------------|-------------|
| Frontend | SvelteKit 5, Tailwind CSS | Web dashboard for job management |
| Backend | Express.js, Prisma, PostgreSQL | REST API with job queue |
| Worker | Python 3.12, RQ | Async job processor |
| Pipeline | CrewAI, GPT-4o | 16-stage research automation |

---

## Features

- **Web Dashboard** - Create research jobs, track progress, view results
- **Real-time Updates** - SSE-based progress tracking with stage indicators
- **OAuth Authentication** - Google and GitHub login
- **Email Notifications** - Job completion alerts
- **16-Stage Research Pipeline** - Pain point analysis, solution ideation, competitive analysis, SEO strategy
- **Landing Page Generation** - AI-generated HTML landing pages from research reports

---

## Quick Start (Local Development)

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker (for PostgreSQL and Redis)
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### 1. Clone and Start Infrastructure

```bash
git clone https://github.com/your-org/nicheiq.git
cd nicheiq

# Start PostgreSQL and Redis
cd docker && docker compose up -d postgres redis && cd ..
```

### 2. Setup Backend

```bash
cd backend
npm install
npm run db:generate
npm run db:migrate
npm run dev
```

Backend runs at http://localhost:3001

### 3. Setup Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000

### 4. Setup Worker

```bash
# From project root
uv venv
source .venv/bin/activate
uv pip install -e .
python -m worker.run_worker
```

### 5. Configure Environment

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

**Required API Keys:**

| Service | Purpose |
|---------|---------|
| OpenAI | LLM for agent reasoning |
| Serper.dev | Google search |
| Reddit | Social data collection |
| DataForSEO | Keyword research |

---

## Project Structure

```
nicheiq/
├── frontend/              # SvelteKit web app
│   ├── src/
│   │   ├── routes/        # Pages and API routes
│   │   │   ├── (app)/     # Protected routes (dashboard, jobs, settings)
│   │   │   └── (public)/  # Public routes (login, register)
│   │   └── lib/           # Components, stores, utilities
│   └── package.json
│
├── backend/               # Express API server
│   ├── src/
│   │   ├── routes/        # API endpoints
│   │   ├── services/      # Business logic
│   │   └── middleware/    # Auth, rate limiting
│   ├── prisma/            # Database schema
│   └── package.json
│
├── worker/                # Python RQ worker
│   ├── run_worker.py      # Worker entry point
│   ├── tasks.py           # Job execution
│   └── progress.py        # Progress reporting
│
├── src/nicheiq/           # Python research pipeline
│   ├── flows/             # 16-stage orchestrator
│   ├── crews/             # CrewAI agent crews
│   ├── models/            # Pydantic data models
│   ├── tools/             # Reddit, Twitter, DataForSEO tools
│   └── report/            # Report generation
│
├── docker/                # Docker Compose configs
├── docs/                  # Documentation
└── tests/                 # Python test suite
```

---

## Development Commands

### Frontend

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server (port 3000) |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm run check` | Type check |
| `npm test` | Run tests |
| `npm run test:watch` | Watch mode |

### Backend

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server (port 3001) |
| `npm run build` | Compile TypeScript |
| `npm start` | Run compiled code |
| `npm run typecheck` | Type check |
| `npm test` | Run tests |
| `npm run db:generate` | Generate Prisma client |
| `npm run db:migrate` | Run migrations |
| `npm run db:studio` | Open Prisma Studio |

### Worker

| Command | Description |
|---------|-------------|
| `python -m worker.run_worker` | Start single worker |
| `python -m worker.run_worker --workers 4` | Start multiple workers |
| `python -m worker.run_worker --burst` | Burst mode (exit when empty) |

### Python Pipeline (Standalone)

| Command | Description |
|---------|-------------|
| `python -m nicheiq.main --niche "Your niche"` | Run research |
| `python -m nicheiq.main --niche "Your niche" --resume` | Resume from checkpoint |
| `python -m nicheiq.main --cleanup-collections` | List orphaned ChromaDB collections |
| `python -m nicheiq.main --cleanup-collections --force` | Delete all ChromaDB collections |
| `pytest` | Run tests |
| `pytest --cov` | With coverage |

---

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment instructions.

### Quick Docker Production

```bash
# Build and start all services
cd docker
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml run --rm api npx prisma migrate deploy
```

---

## Environment Variables

See [docs/ENV_REFERENCE.md](docs/ENV_REFERENCE.md) for the complete reference.

**Essential Variables:**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `OPENAI_API_KEY` | OpenAI API key |
| `SERPER_API_KEY` | Serper.dev API key |
| `REDDIT_CLIENT_ID` | Reddit API credentials |
| `REDDIT_CLIENT_SECRET` | Reddit API credentials |
| `AUTH_SECRET` | JWT secret (32+ chars) |
| `INTERNAL_SERVICE_SECRET` | Worker-to-backend auth |

---

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](CLAUDE.md) | Developer reference (commands, structure) |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment guide |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technical architecture |
| [docs/ENV_REFERENCE.md](docs/ENV_REFERENCE.md) | Environment variables |
| [docs/SETUP.md](docs/SETUP.md) | Python CLI & API key setup |

---

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [CrewAI](https://www.crewai.com/) - Multi-agent AI framework
- [OpenAI](https://openai.com/) - GPT-4 for agent reasoning
- [Serper.dev](https://serper.dev/) - Google Search API
- [DataForSEO](https://dataforseo.com/) - Keyword research
- [PRAW](https://praw.readthedocs.io/) - Reddit API
