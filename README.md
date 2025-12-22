# NicheIQ - Autonomous Market Research Agent

**Transform unstructured social discussions into validated SaaS opportunities**

NicheIQ is an autonomous AI-powered market research agent that analyzes social media discussions (Reddit, Twitter) to discover, validate, and recommend SaaS business opportunities. Built with CrewAI, it combines Flow-based orchestration with specialized agent Crews for comprehensive market analysis.

---

## 📚 Quick Start

**New to NicheIQ?** Start here:

- **[Getting Started Guide →](GETTING_STARTED.md)** - Complete step-by-step tutorial with API key setup
- **[Environment Variables Reference →](ENV_REFERENCE.md)** - Full .env configuration guide
- **[Example Research Run →](#running-your-first-research)** - See what to expect

**Already set up?** Jump to [Usage](#usage) or [Configuration](#configuration).

---

## Features

- **Autonomous Research Pipeline**: 10-stage automated workflow from niche input to final report
- **Social Media Analysis**: Automated collection and analysis of Reddit posts and Twitter threads
- **Pain Point Extraction**: AI-powered identification and validation of market problems
- **Solution Ideation**: Multi-agent system for generating and refining SaaS concepts
- **Competitive Analysis**: Automated competitor research and gap identification
- **Keyword Validation**: Quantitative demand validation using DataForSEO API
- **Landing Page Generation**: 4-agent pipeline to generate unique, conversion-optimized HTML landing pages
- **Hybrid Report Generation**: 80% Python + 20% LLM for fast, accurate, cost-effective reports
- **Cost-Optimized**: Batched API calls to minimize research costs

## Architecture

### Hybrid Flow + Crew Design

- **Flow**: Orchestrates the overall pipeline and handles straightforward stages
- **Specialized Crews**: Multi-agent teams for complex analysis tasks

### 10-Stage Research Pipeline

1. **Stage 1-4**: Niche Input & Validation
2. **Stage 5**: Search & Discover (SerperDevTool)
3. **Stage 6**: Pain Point Analysis (PainPointCrew)
4. **Stage 7-8.75**: Unified Solution Development (UnifiedSolutionCrew)
   - Solution ideation, competitive analysis, refinement, and selection
5. **Stage 8.8**: Keyword Demand Validation (Flow - quick validation for top 3 solutions)
6. **Stage 8.85**: Solution Refinement (SolutionRefinementCrew - strategic recommendations)
7. **Stage 9**: SEO Strategy (SEOStrategyCrew)
   - Phase 9.5a-c: Seed generation, bulk validation, enrichment
   - Tasks 1-5: Analysis, strategy, implementation guide
8. **Stage 9.75**: Data Source Research (conditional, for data aggregation solutions)
9. **Stage 10**: Final Report Generation (Hybrid Python + LLM)

## Installation

### Prerequisites

- Python 3.10 - 3.13
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/yourusername/nicheiq.git
cd nicheiq

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Using pip

```bash
# Clone and install
git clone https://github.com/yourusername/nicheiq.git
cd nicheiq

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Testing & Validation

### Pre-Run Validation

Before running research, validate your environment setup:

```bash
python check_setup.py
```

This checks Python version, dependencies, API keys, and permissions.

### Run Tests

```bash
# All tests (unit + integration)
pytest

# Fast unit tests only (no API calls)
pytest tests/unit/

# Integration tests (may make API calls)
pytest tests/integration/

# With coverage report
pytest --cov=src/nicheiq --cov-report=term-missing
```

**Test Organization:**
- `tests/unit/` - Fast tests, no external dependencies
- `tests/integration/` - End-to-end tests, may use APIs

### Post-Run Validation

After generating a report, validate for hallucinations and data integrity:

```bash
python validate_report.py output/final_report_*.json output/research_state_raw_*.json
```

**Checks:**
- Pain point accuracy
- Score precision (no rounding)
- CAC value integrity
- Competition intensity labels

See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide.

## Configuration

### 1. Set up API keys

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

### 2. Required API Keys

| Service | Purpose | Get API Key |
|---------|---------|-------------|
| OpenAI | LLM for agent reasoning | [platform.openai.com](https://platform.openai.com) |
| Serper.dev | Google search for discovery | [serper.dev](https://serper.dev) |
| Reddit (PRAW) | Reddit content collection | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
| DataForSEO | Keyword research & validation | [dataforseo.com](https://dataforseo.com) |

### 3. Optional API Keys

- **Twitter**: For authenticated Twitter scraping (guest mode available without credentials)
- **CrewAI+**: For enterprise CrewAI features

### Configuration Example

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o

# Serper.dev
SERPER_API_KEY=...

# Reddit
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=NicheIQ/0.1.0

# Twitter (Optional)
TWITTER_USERNAME=yourusername
TWITTER_PASSWORD=yourpassword
TWITTER_EMAIL=youremail@example.com

# DataForSEO
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...

# Application Settings
LOG_LEVEL=INFO
MAX_SEARCH_RESULTS=20
KEYWORD_MIN_SEARCH_VOLUME=50
KEYWORD_MAX_COMPETITION=0.7
```

**For detailed API key setup instructions, see [GETTING_STARTED.md](GETTING_STARTED.md).**

## Running Your First Research

Let's run a simple research to verify everything works:

```bash
python -m nicheiq.main --niche "AI tools for content creators"
```

### What to Expect

The research runs through 10 stages and takes 5-15 minutes:

```
================================================================================
STAGE 5: Search & Discover
================================================================================
Generating strategic search queries...
✓ Generated 15 search queries
✓ Found 20 Reddit discussion URLs
✓ Found 15 Twitter thread URLs
✓ Collected 12 quality Reddit posts
✓ Collected 8 quality Twitter threads

================================================================================
STAGE 6: Pain Point Analysis
================================================================================
Running pain point analysis crew...
✓ Identified 15 pain points
✓ High-opportunity pain points: 5
  - Manual content repurposing consuming 3-5 hours daily (Severity: 0.85, WTP: 0.78)
  - Inconsistent brand voice across platforms (Severity: 0.72, WTP: 0.65)

================================================================================
STAGE 7: Solution Ideation
================================================================================
✓ Generated 3 solution concepts
  1. ContentFlow AI: Automated multi-platform content repurposing
     Market Fit: 0.88 | Feasibility: 0.82

================================================================================
RESEARCH COMPLETE - EXECUTIVE SUMMARY
================================================================================
Niche: AI tools for content creators

Pain Points: 15 identified (5 high opportunity)
Solutions: 3 concepts generated
Keywords: 156 validated (23 high opportunity)
Total search volume: 89,420

Full report: ./output/research_report_20240315_143022.json
```

The output includes:
- **JSON Report** with all structured data
- **Logs** in `./output/logs/` for debugging
- **Pain points** with severity scores and user quotes
- **Solution ideas** with features and market fit scores
- **Competitor analysis** with gaps and opportunities
- **Keywords** with search volumes and competition data

## Usage

### Command Line Interface

```bash
# Basic usage
python -m nicheiq.main --niche "AI-powered project management for remote teams"

# With custom output directory
python -m nicheiq.main --niche "Developer tools for API testing" --output ./results

# With debug logging
python -m nicheiq.main --niche "SaaS for freelance designers" --log-level DEBUG

# Using environment variable
export NICHEIQ_NICHE="Marketing automation for small businesses"
python -m nicheiq.main
```

### Programmatic Usage

```python
from nicheiq.flows import ResearchFlow

# Initialize and run research
flow = ResearchFlow(
    niche_description="AI-powered project management for remote teams"
)

result = flow.run_research()

# Access results
print(f"Pain points found: {len(result.pain_point_analysis.pain_points)}")
print(f"Solutions generated: {len(result.solution_ideas.solution_ideas)}")
print(f"Report saved to: {result.report_path}")
```

## Project Structure

```
nicheiq/
├── src/nicheiq/
│   ├── config/
│   │   └── settings.py          # Configuration management
│   ├── models/                   # Pydantic data models
│   │   ├── pain_point.py
│   │   ├── solution_idea.py
│   │   ├── competitor.py
│   │   ├── keyword_data.py
│   │   ├── social_content.py
│   │   └── research_state.py
│   ├── tools/                    # Custom CrewAI tools
│   │   ├── reddit_tool.py       # Reddit collection (PRAW)
│   │   ├── twitter_tool.py      # Twitter scraping
│   │   └── dataforseo_tool.py   # Keyword research
│   ├── utils/                    # Helper utilities
│   │   ├── helpers.py           # Query generation, search helpers
│   │   └── prompts/             # Reusable prompt templates
│   ├── crews/                    # Specialized agent crews
│   │   ├── config/              # YAML configurations (per crew)
│   │   │   ├── pain_point_agents.yaml
│   │   │   ├── pain_point_tasks.yaml
│   │   │   ├── unified_solution_agents.yaml
│   │   │   ├── unified_solution_tasks.yaml
│   │   │   ├── seo_strategy_agents.yaml
│   │   │   ├── seo_strategy_tasks.yaml
│   │   │   ├── solution_refinement_agents.yaml
│   │   │   ├── solution_refinement_tasks.yaml
│   │   │   ├── landing_page_agents.yaml
│   │   │   ├── landing_page_tasks.yaml
│   │   │   ├── data_source_agents.yaml
│   │   │   └── data_source_tasks.yaml
│   │   ├── pain_point_crew.py          # Stage 6: Pain point analysis
│   │   ├── unified_solution_crew.py    # Stages 7-8.75: Ideation + competitive + selection
│   │   ├── seo_strategy_crew.py        # Stage 9: SEO strategy
│   │   ├── solution_refinement_crew.py # Stage 8.85: Solution refinement
│   │   ├── landing_page_crew.py        # Landing page generation (4 agents)
│   │   └── data_source_crew.py         # Stage 9.75: Data source research (conditional)
│   ├── report/                   # Report generation module
│   │   ├── report_generator.py  # Stage 10: Hybrid Python + LLM report
│   │   ├── templates/           # Report templates
│   │   └── utils/               # State accessors and helpers
│   ├── landing/                  # Landing page generation module
│   │   └── __main__.py          # CLI entry point for landing page
│   ├── flows/
│   │   └── research_flow.py     # Main 10-stage pipeline
│   └── main.py                   # CLI entry point
├── tests/                        # Test suite
├── pyproject.toml               # Project dependencies
├── .env.example                 # Environment template
└── README.md
```

## Output

Research results are saved to `./output/` (configurable):

```
output/
├── final_report_20240315_143022.json    # Complete research report
├── research_state_raw_20240315_143022.json  # Raw state data
├── checkpoints/                          # Resume capability
└── logs/
    └── nicheiq_2024-03-15.log           # Detailed execution logs
```

### Report Structure

The JSON report contains:

- **Executive Dashboard**: Go/no-go verdict, confidence score, key metrics
- **Go-to-Market Blueprint**: ICP, marketing channels, 30-day playbook
- **Pain Point Analysis**: Validated pain points with scores and quotes
- **Solution Ideas**: Refined SaaS concepts with features
- **Competitive Analysis**: Competitor profiles, market gaps, positioning matrix
- **SEO Strategy**: 150+ validated keywords, content strategy, implementation roadmap
- **Market Sizing**: TAM/SAM/SOM calculations with methodology
- **Analytics & Visualizations**: Charts and data visualizations for reports

---

## Report Generation

NicheIQ uses a **hybrid Python + LLM approach** for Stage 10 report generation, optimizing for speed, accuracy, and cost.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Stage 10: Report Generation               │
├─────────────────────────────────────────────────────────────┤
│  Step 1: Python Data Assembly (80%)                         │
│  - 27 fields direct copy from research state                │
│  - Template-based summaries and calculations                │
│  - Zero hallucination risk on data fields                   │
├─────────────────────────────────────────────────────────────┤
│  Step 2: LLM Strategic Synthesis (20%)                      │
│  - executive_summary: High-level narrative                  │
│  - acquisition_strategy_summary: GTM recommendations        │
│  - next_steps: Prioritized action items                     │
├─────────────────────────────────────────────────────────────┤
│  Step 3: Enhanced Sections (Python)                         │
│  - Executive Dashboard with go/no-go verdict                │
│  - GTM Blueprint with ICP and channels                      │
│  - Analytics with visualizations                            │
└─────────────────────────────────────────────────────────────┘
```

### Benefits

| Metric | Previous (Full LLM) | Current (Hybrid) |
|--------|---------------------|------------------|
| Cost | $0.10-0.30 | $0.02-0.05 |
| Speed | 5-15 seconds | 2-3 seconds |
| Accuracy | Variable | 100% on data fields |
| Hallucination Risk | Moderate | Zero on data |

---

## Landing Page Generation

Generate unique, conversion-optimized HTML landing pages from your research reports using a **4-agent pipeline**.

### Quick Start

```bash
# Generate landing page from research report
python -m nicheiq.landing --report output/final_report_20241216_143022.json

# Specify custom output path
python -m nicheiq.landing --report output/final_report.json --output my_landing.html
```

### 4-Agent Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                 Landing Page Generation                      │
├─────────────────────────────────────────────────────────────┤
│  Agent 1: Marketing Strategist                              │
│  - Creates strategic brief with persona focus               │
│  - Defines key messaging angle and differentiation          │
│  - Specifies ONE memorable element for the page             │
├─────────────────────────────────────────────────────────────┤
│  Agent 2: Brand Designer                                    │
│  - Creates unique color palette based on product category   │
│  - Defines design mood (minimal/bold/dark/friendly)         │
│  - Never uses generic colors - justified by product         │
├─────────────────────────────────────────────────────────────┤
│  Agent 3: Copywriter                                        │
│  - Selects which sections to include (hero/problem/etc.)    │
│  - Writes conversion-optimized copy                         │
│  - Avoids "AI slop" patterns (generic phrases)              │
├─────────────────────────────────────────────────────────────┤
│  Agent 4: HTML Developer                                    │
│  - Generates complete HTML with Tailwind CSS                │
│  - Implements memorable element from strategy               │
│  - Creates responsive, mobile-first design                  │
└─────────────────────────────────────────────────────────────┘
```

### Output

Each run produces a **unique design** tailored to your specific product:

```
Landing Page Generated Successfully!
============================================================
Output: /path/to/landing_page.html

Product: ContentFlow AI
Tagline: Repurpose once, publish everywhere

Design Mood: bold-vibrant
Primary Color: #8B5CF6
Secondary Color: #F97316

Sections Included (6):
  - hero
  - problem
  - solution
  - how_it_works
  - social_proof
  - cta

Open landing_page.html in your browser to view!
```

### Design Moods

| Mood | Best For | Characteristics |
|------|----------|-----------------|
| `minimal-professional` | B2B, Enterprise | Clean lines, whitespace, subtle shadows |
| `bold-vibrant` | Consumer, Marketing | Strong colors, large typography, gradients |
| `dark-technical` | Developer tools | Dark theme (#0F172A), monospace, neon accents |
| `friendly-approachable` | Consumer apps | Rounded corners, warm colors, playful |

### Anti-"AI Slop" Features

The landing page generator is specifically designed to avoid generic AI patterns:

- **No generic fonts**: Uses distinctive typography (Satoshi, Cabinet Grotesk, not Inter/Roboto)
- **No purple gradients on white**: Chooses bold, product-specific color palettes
- **No "revolutionize your workflow"**: Writes specific, product-relevant copy
- **No centered card heroes**: Uses full-width, dramatic layouts
- **One memorable element**: Every page has ONE thing visitors remember

## Customization

### Adjust Quality Thresholds

Edit `.env`:

```bash
MIN_REDDIT_UPVOTES=10        # Higher = more viral discussions
MIN_REDDIT_COMMENTS=5         # Higher = more engaged conversations
MIN_TWITTER_LIKES=10
MIN_TWITTER_REPLIES=5

KEYWORD_MIN_SEARCH_VOLUME=100  # Higher = more demand required
KEYWORD_MAX_COMPETITION=0.5    # Lower = easier to rank
```

### Modify Agent Behavior

Each crew has its own pair of YAML configuration files following the pattern `{crew_name}_agents.yaml` and `{crew_name}_tasks.yaml`.

**Examples:**
- Edit `src/nicheiq/crews/config/pain_point_agents.yaml` - Customize pain point analysis agent personas
- Edit `src/nicheiq/crews/config/seo_strategy_tasks.yaml` - Modify SEO strategy task descriptions

**Available crews:** pain_point, unified_solution, seo_strategy, solution_refinement, data_source

### Target Different Markets

```bash
# Target United Kingdom
TARGET_LOCATION=2826
TARGET_LANGUAGE=en

# Target Germany
TARGET_LOCATION=2276
TARGET_LANGUAGE=de
```

Find location codes: [DataForSEO Location Codes](https://docs.dataforseo.com/v3/appendix/locations/)

## Cost Optimization

NicheIQ is designed to minimize API costs:

- **DataForSEO Batching**: Up to 1,000 keywords per request for search volume
- **Efficient Search**: Configurable result limits to avoid over-fetching
- **Smart Caching**: Prompt caching for repeated agent calls
- **Quality Filtering**: Only collect high-engagement content

Typical research run costs (estimates):

- OpenAI (GPT-4o): $0.50 - $2.00
- Serper.dev: $0.01 - $0.05
- DataForSEO: $0.01 - $0.10
- Reddit/Twitter: Free (API)

**Total: ~$0.50 - $2.20 per niche research**

## Development

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=src/nicheiq --cov-report=term-missing
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

## Troubleshooting

### Common Issues

**Issue**: `ImportError: No module named 'nicheiq'`
```bash
# Solution: Install in editable mode
pip install -e .
```

**Issue**: `ValueError: Missing required environment variable`
```bash
# Solution: Ensure .env file exists and contains all required keys
cp .env.example .env
# Edit .env with your actual API keys
```

**Issue**: `twitter-api-client authentication failed`
```bash
# Solution: Either provide Twitter credentials or run without (uses guest mode)
# Guest mode has rate limits but requires no authentication
```

**Issue**: `DataForSEO API error: insufficient credits`
```bash
# Solution: Add credits to your DataForSEO account
# Or reduce KEYWORD_MIN_SEARCH_VOLUME to get fewer results
```

## Limitations

- **English-focused**: Optimized for English content analysis (multi-language support possible)
- **API Dependencies**: Requires multiple paid APIs (with free tiers available)
- **Rate Limits**: Respects platform rate limits (may take 5-15 minutes per research)
- **Content Quality**: Results depend on quality of social discussions found
- **LLM Variability**: Agent outputs may vary between runs due to LLM non-determinism

## Roadmap

- [x] Landing page generation (4-agent pipeline)
- [x] Trend analysis and market timing insights (TrendLongevityCrew)
- [x] Audience mapping and persona development (AudienceMappingCrew)
- [x] Market sizing with TAM/SAM/SOM (MarketSizingCrew)
- [ ] PDF report generation with visualizations
- [ ] Web interface for easier usage
- [ ] Additional data sources (Hacker News, Product Hunt, IndieHackers)
- [ ] Automated LinkedIn outreach for validation
- [ ] Integration with market research databases
- [ ] Multi-language support for international markets

## Documentation

For more detailed documentation, see:

- **[CLAUDE.md](CLAUDE.md)** - Main project documentation and architecture
- **[docs/AGENT_ARCHITECTURE.md](docs/AGENT_ARCHITECTURE.md)** - Complete agent analysis with 24 agents across 11 crews
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Deep technical architecture
- **[docs/PATTERNS.md](docs/PATTERNS.md)** - Reusable code patterns
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Setup guide with API keys
- **[ENV_REFERENCE.md](ENV_REFERENCE.md)** - Environment variables reference

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run code quality checks (`black`, `ruff`, `mypy`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [CrewAI](https://www.crewai.com/) - Multi-agent AI framework
- Powered by [OpenAI](https://openai.com/) - GPT-4 for agent reasoning
- Search by [Serper.dev](https://serper.dev/) - Google Search API
- Keyword data from [DataForSEO](https://dataforseo.com/)
- Reddit API via [PRAW](https://praw.readthedocs.io/)
- Twitter scraping with [twitter-api-client](https://github.com/trevorhobenshield/twitter-api-client)

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/nicheiq/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/nicheiq/discussions)
- **Documentation**: [Wiki](https://github.com/yourusername/nicheiq/wiki)

---

**Built with ❤️ for indie hackers, founders, and market researchers**
