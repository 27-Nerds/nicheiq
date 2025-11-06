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
- **Cost-Optimized**: Batched API calls to minimize research costs

## Architecture

### Hybrid Flow + Crew Design

- **Flow**: Orchestrates the overall pipeline and handles straightforward stages
- **Specialized Crews**: Multi-agent teams for complex analysis tasks

### 10-Stage Research Pipeline

1. **Stage 1-4**: Niche Input & Validation
2. **Stage 5**: Search & Discover (SerperDevTool)
3. **Stage 6**: Pain Point Analysis (PainPointCrew)
4. **Stage 7**: Solution Ideation (IdeaGenerationCrew)
5. **Stage 8**: Competitive Analysis (CompetitiveCrew)
6. **Stage 9**: Keyword Validation (DataForSEOTool)
7. **Stage 10**: Final Report Generation

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
│   │   └── helpers.py           # Query generation, search helpers
│   ├── crews/                    # Specialized agent crews
│   │   ├── config/
│   │   │   ├── agents.yaml      # Agent definitions
│   │   │   └── tasks.yaml       # Task specifications
│   │   ├── pain_point_crew.py   # Stage 6: Pain point analysis
│   │   ├── idea_generation_crew.py  # Stage 7: Solution ideation
│   │   └── competitive_crew.py  # Stage 8: Competitive analysis
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
├── research_report_20240315_143022.json  # Complete research data
└── logs/
    └── nicheiq_2024-03-15.log           # Detailed execution logs
```

### Report Structure

The JSON report contains:

- **Niche Description**: Original research input
- **Search Queries**: Generated search queries
- **Reddit Posts**: Collected posts with comments
- **Twitter Threads**: Collected threads with engagement
- **Pain Point Analysis**: Validated pain points with scores
- **Solution Ideas**: Refined SaaS concepts with features
- **Competitive Analysis**: Competitor profiles and market gaps
- **Keyword Research**: Validated keywords with search volumes

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

Edit `src/nicheiq/crews/config/agents.yaml` to customize agent roles, goals, and backstories.

Edit `src/nicheiq/crews/config/tasks.yaml` to modify task descriptions and expected outputs.

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

- [ ] PDF report generation with visualizations
- [ ] Web interface for easier usage
- [ ] Additional data sources (Hacker News, Product Hunt, IndieHackers)
- [ ] Trend analysis and market timing insights
- [ ] Automated LinkedIn outreach for validation
- [ ] Integration with market research databases
- [ ] Multi-language support for international markets

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
