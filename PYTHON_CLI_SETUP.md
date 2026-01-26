# Getting Started with NicheIQ - Step by Step Guide

This guide will walk you through setting up NicheIQ from scratch, including obtaining all required API keys.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Getting API Keys](#getting-api-keys)
4. [Configuration](#configuration)
5. [Running Your First Research](#running-your-first-research)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10 or higher** (3.10, 3.11, 3.12, or 3.13)
- **Git** for cloning the repository
- **A credit/debit card** for API services (most have free tiers)
- **~30-60 minutes** to set up all API accounts

### Check Python Version

```bash
python --version
# Should show Python 3.10.x or higher
```

If you don't have Python installed:
- **macOS**: `brew install python@3.11`
- **Ubuntu/Debian**: `sudo apt install python3.11`
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

---

## Installation

### Step 1: Clone the Repository

```bash
cd ~/work  # or your preferred directory
git clone https://github.com/yourusername/nicheiq.git
cd nicheiq
```

### Step 2: Install uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager. Install it:

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation:**
```bash
uv --version
```

### Step 3: Create Virtual Environment and Install Dependencies

```bash
# Create virtual environment
uv venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Install NicheIQ and dependencies
uv pip install -e .
```

**Alternative: Using pip**

If you prefer pip over uv:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

### Step 4: Verify Installation

```bash
python -c "import nicheiq; print('NicheIQ installed successfully!')"
```

---

## Getting API Keys

You'll need API keys from 4 services. Let's get them one by one.

### 1. OpenAI API Key (Required)

**Purpose**: Powers the AI agents that analyze content and generate insights.

**Free Tier**: No free tier, but new accounts get $5 credit that expires after 3 months.

**Typical Cost**: ~$0.50-$2.00 per research run using GPT-4o.

#### Steps:

1. **Go to OpenAI Platform**
   - Visit: [https://platform.openai.com](https://platform.openai.com)
   - Click "Sign up" or "Log in"

2. **Create an Account**
   - Sign up with email or Google/Microsoft account
   - Verify your email address

3. **Add Payment Method**
   - Click your profile icon (top right) → "Billing"
   - Click "Add payment method"
   - Add a credit/debit card
   - Set usage limits if desired (e.g., $10/month)

4. **Create API Key**
   - Click your profile icon → "API keys" or visit [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
   - Click "+ Create new secret key"
   - Name it: "NicheIQ"
   - Copy the key immediately (you won't see it again!)
   - **Save it**: It looks like `sk-proj-...` (starts with `sk-`)

**What to add to .env:**
```bash
OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890AbCdEfGhIjKlMnOpQrStUvWxYz
OPENAI_MODEL_NAME=gpt-4o
```

---

### 2. Serper.dev API Key (Required)

**Purpose**: Enables Google Search to discover Reddit and Twitter discussions.

**Free Tier**: ✅ 2,500 free searches, then $50 per month for unlimited.

**Typical Cost**: ~$0.01-$0.05 per research run.

#### Steps:

1. **Go to Serper.dev**
   - Visit: [https://serper.dev](https://serper.dev)
   - Click "Get Started Free" or "Sign Up"

2. **Create Account**
   - Sign up with Google (easiest) or email
   - No credit card required for free tier!

3. **Get API Key**
   - After signup, you'll see your dashboard
   - Your API key is displayed prominently
   - Copy it (looks like: `a1b2c3d4e5f6g7h8i9j0...`)

4. **Optional: Check Usage**
   - Dashboard shows remaining free credits
   - 2,500 searches = ~100+ research runs

**What to add to .env:**
```bash
SERPER_API_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
```

---

### 3. Reddit API Credentials (Required)

**Purpose**: Collects Reddit posts and comments for pain point analysis.

**Free Tier**: ✅ Completely free, no credit card required.

**Rate Limits**: 60 requests per minute (sufficient for NicheIQ).

#### Steps:

1. **Create/Login to Reddit Account**
   - Visit: [https://www.reddit.com](https://www.reddit.com)
   - Create an account if you don't have one

2. **Go to App Preferences**
   - Visit: [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
   - Or: User Settings → Safety & Privacy → Manage third-party app authorization
   - Scroll to bottom and click "create another app..." or "are you a developer? create an app..."

3. **Create Application**
   - **Name**: "NicheIQ Research Tool"
   - **App type**: Select **"script"** (important!)
   - **Description**: "Market research automation tool"
   - **About URL**: Leave blank or use `http://localhost`
   - **Redirect URI**: `http://localhost:8080` (required, but not used)
   - Click "Create app"

4. **Copy Credentials**
   - After creation, you'll see your app listed
   - **Client ID**: The string under your app name (looks like `AbCdEf12GhIjKl`)
   - **Secret**: The string next to "secret:" (looks like `aBcDeFgHiJkLmNoPqRsTuVwXyZ123456`)

**What to add to .env:**
```bash
REDDIT_CLIENT_ID=AbCdEf12GhIjKl
REDDIT_CLIENT_SECRET=aBcDeFgHiJkLmNoPqRsTuVwXyZ123456
REDDIT_USER_AGENT=NicheIQ/0.1.0
```

**Note**: The `REDDIT_USER_AGENT` can stay as shown above.

---

### 4. DataForSEO API Credentials (Required)

**Purpose**: Provides keyword search volume data and validation.

**Free Tier**: ✅ $1 free credit on signup (enough for 5-10 research runs).

**Typical Cost**: ~$0.01-$0.10 per research run, $0.005 per API request.

#### Steps:

1. **Go to DataForSEO**
   - Visit: [https://dataforseo.com](https://dataforseo.com)
   - Click "Sign Up" (top right)

2. **Create Account**
   - Fill in:
     - Email address
     - Password
     - Company name (can be personal name)
     - Country
   - Click "Create Account"
   - Verify your email

3. **Add Payment Method (Required for free credit)**
   - After login, go to: [https://app.dataforseo.com/billing](https://app.dataforseo.com/billing)
   - Click "Add funds"
   - Add a payment method (credit/debit card)
   - You'll get $1 free credit after verification
   - Optionally, add $5-10 to start (goes a long way)

4. **Get API Credentials**
   - Go to: [https://app.dataforseo.com/api-access](https://app.dataforseo.com/api-access)
   - Or: Dashboard → "API Access" in the left menu
   - Your credentials are displayed:
     - **Login**: Usually your email address
     - **Password**: A generated API password (NOT your account password)
   - If you don't see a password, click "Generate new password"
   - **Copy both the login and password**

5. **Optional: Check Usage**
   - Dashboard shows remaining credits
   - Each keyword research request costs ~$0.005
   - NicheIQ batches keywords to minimize costs (1,000 keywords = 1 request!)

**What to add to .env:**
```bash
DATAFORSEO_LOGIN=your.email@example.com
DATAFORSEO_PASSWORD=aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0
```

**Important**: Use the API password, not your account password!

---

### 5. Twitter API (Optional)

**Purpose**: Collects Twitter/X threads for additional social insights.

**Free Tier**: ✅ Guest mode available (no API key required, limited rate).

**With Credentials**: Better rate limits and access, but requires Twitter account.

#### Option A: Skip Twitter (Use Guest Mode)

If you don't provide Twitter credentials, NicheIQ will use guest mode with rate limits.

**What to add to .env:**
```bash
# Leave these blank or commented out for guest mode
# TWITTER_USERNAME=
# TWITTER_PASSWORD=
# TWITTER_EMAIL=
```

#### Option B: Use Twitter Credentials (Better Performance)

1. **Use Your Twitter Account**
   - You need an active Twitter/X account
   - No developer account or API application required!

2. **Get Your Credentials**
   - Username: Your @username (without the @)
   - Email: The email associated with your account
   - Password: Your Twitter password

**What to add to .env:**
```bash
TWITTER_USERNAME=your_twitter_handle
TWITTER_PASSWORD=your_twitter_password
TWITTER_EMAIL=your_email@example.com
```

**Security Note**: Your credentials are only used locally and never shared. Consider:
- Using a dedicated research account
- Using app-specific passwords if available
- Never committing .env to version control (already in .gitignore)

---

## Configuration

### Step 1: Create .env File

```bash
# Copy the example file
cp .env.example .env
```

### Step 2: Edit .env File

Open `.env` in your favorite text editor:

```bash
# On macOS/Linux:
nano .env
# or
code .env  # if you have VS Code

# On Windows:
notepad .env
```

### Step 3: Fill in Your API Keys

Here's a complete example with all required values:

```bash
# =============================================================================
# NicheIQ Configuration File
# =============================================================================

# -----------------------------------------------------------------------------
# OpenAI API Configuration (REQUIRED)
# -----------------------------------------------------------------------------
OPENAI_API_KEY=sk-proj-your-actual-key-here-from-openai-platform
OPENAI_MODEL_NAME=gpt-4o  # or gpt-4-turbo-preview

# -----------------------------------------------------------------------------
# Serper.dev API (REQUIRED for Google Search)
# -----------------------------------------------------------------------------
SERPER_API_KEY=your-actual-serper-api-key-here

# -----------------------------------------------------------------------------
# Reddit API Credentials (REQUIRED for Reddit collection)
# -----------------------------------------------------------------------------
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
REDDIT_USER_AGENT=NicheIQ/0.1.0

# -----------------------------------------------------------------------------
# Twitter Scraping (OPTIONAL - leave blank for guest mode)
# -----------------------------------------------------------------------------
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password
TWITTER_EMAIL=your_twitter_email@example.com

# -----------------------------------------------------------------------------
# DataForSEO API (REQUIRED for keyword validation)
# -----------------------------------------------------------------------------
DATAFORSEO_LOGIN=your.email@example.com
DATAFORSEO_PASSWORD=your-dataforseo-api-password

# -----------------------------------------------------------------------------
# Application Settings (Optional - defaults are fine)
# -----------------------------------------------------------------------------
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
MAX_RETRIES=3
TIMEOUT_SECONDS=30

# -----------------------------------------------------------------------------
# Search Configuration (Optional - adjust for your needs)
# -----------------------------------------------------------------------------
MAX_SEARCH_RESULTS=20  # More results = more API costs
MIN_REDDIT_UPVOTES=5   # Minimum upvotes for post quality
MIN_REDDIT_COMMENTS=3  # Minimum comments for engagement
REDDIT_COMMENT_LIMIT=None  # None=all, 32=most, 0=top-level only
MIN_TWITTER_LIKES=5
MIN_TWITTER_REPLIES=3

# -----------------------------------------------------------------------------
# Keyword Research Configuration (Optional)
# -----------------------------------------------------------------------------
KEYWORD_MIN_SEARCH_VOLUME=50   # Minimum monthly searches
KEYWORD_MAX_COMPETITION=0.7     # Max competition (0.0-1.0)
TARGET_LOCATION=2840            # 2840=United States
TARGET_LANGUAGE=en              # Language code

# -----------------------------------------------------------------------------
# Output Configuration (Optional)
# -----------------------------------------------------------------------------
OUTPUT_DIR=./output
REPORTS_DIR=./output/reports
```

### Step 4: Verify Configuration

Run the validation check:

```bash
python -c "from nicheiq.config.settings import settings; print('✓ Configuration loaded successfully')"
```

If you see errors, check that:
- All required API keys are filled in
- No extra spaces around the `=` sign
- No quotes around values (just the raw key)
- File is saved as `.env` not `.env.txt`

---

## Running Your First Research

### Quick Start

Let's run a simple research to test everything:

```bash
python -m nicheiq.main --niche "AI tools for content creators"
```

### What to Expect

The research will run through 10 stages:

```
================================================================================
STAGE 1-4: Niche Input & Validation
================================================================================
✓ Niche validated: AI tools for content creators...
✓ Target location: 2840
✓ Target language: en

================================================================================
STAGE 5: Search & Discover
================================================================================
Generating strategic search queries...
✓ Generated 15 search queries
Searching Reddit for relevant discussions...
✓ Found 20 Reddit discussion URLs
Searching Twitter/X for relevant discussions...
✓ Found 15 Twitter thread URLs
Collecting Reddit posts and comments...
✓ Collected 12 quality Reddit posts
Collecting Twitter threads...
✓ Collected 8 quality Twitter threads

================================================================================
STAGE 6: Pain Point Analysis
================================================================================
Running pain point analysis crew...
✓ Identified 15 pain points
✓ Total mentions: 87
✓ High-opportunity pain points: 5

... (continues through all 10 stages) ...

================================================================================
RESEARCH COMPLETE - EXECUTIVE SUMMARY
================================================================================
Niche: AI tools for content creators

Data Collection:
  - Reddit posts: 12
  - Twitter threads: 8

Pain Points:
  - Total identified: 15
  - High opportunity: 5

Solution Ideas:
  - Concepts generated: 3
  - Recommended: AI Content Optimizer Pro

Competitive Analysis:
  - Landscapes analyzed: 3
  - Opportunities identified: 7

Keyword Validation:
  - Keywords validated: 156
  - Total search volume: 89,420
  - High opportunity keywords: 23

================================================================================
Full report available at: ./output/research_report_20240315_143022.json
================================================================================
```

### Understanding the Output

After completion, you'll have:

1. **JSON Report**: `./output/research_report_TIMESTAMP.json`
   - Complete structured data
   - All pain points, solutions, competitors, keywords
   - Can be processed programmatically

2. **Log File**: `./output/logs/nicheiq_DATE.log`
   - Detailed execution logs
   - Useful for debugging
   - Includes all agent reasoning

### Viewing Results

```bash
# Pretty-print the JSON report
cat ./output/research_report_*.json | python -m json.tool | less

# Or open in VS Code
code ./output/research_report_*.json
```

### Example Research Topics

Try these niches to test the system:

```bash
# SaaS Ideas
python -m nicheiq.main --niche "Project management for remote teams"
python -m nicheiq.main --niche "Invoice automation for freelancers"
python -m nicheiq.main --niche "Social media scheduling for small businesses"

# Developer Tools
python -m nicheiq.main --niche "API testing and monitoring tools"
python -m nicheiq.main --niche "Code review automation for development teams"

# Vertical SaaS
python -m nicheiq.main --niche "Practice management software for dentists"
python -m nicheiq.main --niche "Inventory management for restaurants"
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: "Missing required environment variable"

**Error:**
```
ERROR Missing required environment variables:
  - OPENAI_API_KEY
  - SERPER_API_KEY
```

**Solution:**
1. Ensure `.env` file exists: `ls -la .env`
2. Check file contents: `cat .env | grep API_KEY`
3. Verify no extra quotes or spaces
4. Reload environment: `source .venv/bin/activate`

---

#### Issue 2: "OpenAI API authentication failed"

**Error:**
```
openai.AuthenticationError: Invalid API key
```

**Solution:**
1. Verify API key at [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Check key starts with `sk-proj-` or `sk-`
3. Ensure no spaces or quotes in `.env`
4. Key may be expired - generate a new one

---

#### Issue 3: "Insufficient credits" (OpenAI)

**Error:**
```
openai.RateLimitError: You exceeded your current quota
```

**Solution:**
1. Go to [https://platform.openai.com/account/billing](https://platform.openai.com/account/billing)
2. Add payment method and credits
3. Set usage limits to avoid surprises
4. Check billing settings are configured

---

#### Issue 4: "DataForSEO API error: insufficient funds"

**Error:**
```
DataForSEO API error: insufficient credits
```

**Solution:**
1. Go to [https://app.dataforseo.com/billing](https://app.dataforseo.com/billing)
2. Add funds ($5-10 goes a long way)
3. Check current balance in dashboard
4. Reduce `KEYWORD_MIN_SEARCH_VOLUME` to get fewer results

---

#### Issue 5: "Reddit API rate limit"

**Error:**
```
praw.exceptions.RedditAPIException: RATELIMIT
```

**Solution:**
1. Wait a few minutes (rate limits reset)
2. Reduce `MAX_SEARCH_RESULTS` in `.env`
3. Increase `TIMEOUT_SECONDS` to 60
4. Reddit allows 60 requests/minute

---

#### Issue 6: "Twitter authentication failed"

**Error:**
```
twitter.scraper: Authentication failed
```

**Solution:**
1. **Option A**: Remove Twitter credentials to use guest mode
   ```bash
   # Comment out in .env:
   # TWITTER_USERNAME=
   # TWITTER_PASSWORD=
   ```
2. **Option B**: Verify credentials are correct
3. Twitter/X may have changed security - guest mode is safer

---

#### Issue 7: "Import Error: No module named 'nicheiq'"

**Error:**
```
ModuleNotFoundError: No module named 'nicheiq'
```

**Solution:**
```bash
# Reinstall in editable mode
pip install -e .

# Or with uv
uv pip install -e .

# Verify installation
python -c "import nicheiq; print('OK')"
```

---

#### Issue 8: "Permission denied" on Linux/macOS

**Error:**
```
PermissionError: [Errno 13] Permission denied: './output'
```

**Solution:**
```bash
# Create output directory manually
mkdir -p output/logs output/reports

# Fix permissions
chmod -R 755 output/

# Or run with custom output location
python -m nicheiq.main --niche "test" --output ~/nicheiq-output
```

---

#### Issue 9: Very Slow Execution

**Symptoms**: Research takes 20+ minutes

**Solutions:**
1. **Reduce search results**: Set `MAX_SEARCH_RESULTS=10` in `.env`
2. **Limit comment depth**: Set `REDDIT_COMMENT_LIMIT=0` (top-level only)
3. **Skip Twitter**: Remove Twitter credentials to disable collection
4. **Check internet**: Slow connection affects API calls
5. **Use faster model**: Change to `OPENAI_MODEL_NAME=gpt-4o-mini` (cheaper but less capable)

---

#### Issue 10: Empty Results / No Pain Points Found

**Symptoms**: Research completes but finds 0 pain points

**Solutions:**
1. **Lower quality thresholds**:
   ```bash
   MIN_REDDIT_UPVOTES=1
   MIN_REDDIT_COMMENTS=1
   MIN_TWITTER_LIKES=1
   ```
2. **Try a different niche**: Some topics have more discussion than others
3. **Broaden search**: Increase `MAX_SEARCH_RESULTS=30`
4. **Check logs**: `cat output/logs/nicheiq_*.log | grep "filtered out"`

---

### Getting Help

If you're still stuck:

1. **Check Logs**:
   ```bash
   # View latest log file
   tail -100 output/logs/nicheiq_$(date +%Y-%m-%d).log
   ```

2. **Enable Debug Logging**:
   ```bash
   python -m nicheiq.main --niche "test niche" --log-level DEBUG
   ```

3. **Test Individual Components**:
   ```python
   # Test Reddit collection
   from nicheiq.tools.reddit_tool import RedditCollectorTool
   tool = RedditCollectorTool()
   post = tool.collect_post("https://reddit.com/r/SaaS/comments/...")
   print(post)
   ```

4. **Open an Issue**:
   - GitHub: [https://github.com/yourusername/nicheiq/issues](https://github.com/yourusername/nicheiq/issues)
   - Include: Error message, .env config (without actual keys), log file excerpt

---

## Next Steps

Now that you have NicheIQ running:

### 1. Customize for Your Needs

Edit `.env` to adjust:
- Quality thresholds (upvotes, comments)
- Search result limits
- Target market (location, language)
- Keyword criteria

### 2. Integrate into Your Workflow

```python
# Use programmatically in your scripts
from nicheiq.flows import ResearchFlow

niches = [
    "AI tools for marketers",
    "Automation for e-commerce",
    "Analytics for SaaS founders"
]

for niche in niches:
    flow = ResearchFlow(niche_description=niche)
    result = flow.run_research()
    print(f"✓ {niche}: {len(result.pain_point_analysis.pain_points)} pain points")
```

### 3. Analyze Results

Use the JSON reports for:
- Trend analysis across multiple niches
- Competitor tracking over time
- Market opportunity scoring
- Content ideation based on pain points

### 4. Extend the System

- Add custom data sources
- Integrate with your CRM
- Build a web interface
- Create automated reports

---

## Cost Summary

Typical costs per research run:

| Service | Cost per Run | Notes |
|---------|--------------|-------|
| OpenAI (GPT-4o) | $0.50 - $2.00 | Main expense, scales with content |
| Serper.dev | $0.01 - $0.05 | 2,500 free searches |
| DataForSEO | $0.01 - $0.10 | $1 free credit |
| Reddit API | $0.00 | Completely free |
| Twitter API | $0.00 | Free (guest or authenticated) |
| **Total** | **$0.52 - $2.15** | Varies by niche complexity |

**Tips to Reduce Costs:**
- Use `gpt-4o-mini` instead of `gpt-4o` (75% cheaper)
- Lower `MAX_SEARCH_RESULTS` to 10-15
- Set `REDDIT_COMMENT_LIMIT=0` for faster processing
- Reuse research reports instead of re-running

---

## Congratulations! 🎉

You've successfully set up NicheIQ and run your first market research!

The system is now ready to help you:
- Discover validated SaaS opportunities
- Extract pain points from real discussions
- Generate solution concepts
- Analyze competition
- Validate market demand

Happy researching! 🚀
