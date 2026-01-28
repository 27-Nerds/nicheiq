# NicheIQ Agent Architecture Analysis

## Executive Summary

NicheIQ uses **36 specialized AI agents** organized into **11 crews**, orchestrated through a 16-stage research pipeline. Each agent has a specific role, named framework, and verification standards.

---

## Complete Agent Inventory

### 1. PainPointCrew (Stage 6) - 3 Agents

| Agent | Role | Framework |
|-------|------|-----------|
| **content_researcher** | Pattern-first categorization of raw social media discussions | Data Integrity Protocol - prohibited from fabricating, reports insufficiency |
| **pain_point_analyst** | Extract specific, actionable problems from categorized content | 3-Quote Minimum Protocol - no assumption-based claims |
| **pain_point_validator** | Score pain points with quantitative metrics (severity, WTP) | Evidence-Based Scoring - every score requires quote justification |

---

### 2. UnifiedSolutionCrew (Stage 7) - 6 Agents

| Agent | Role | Framework |
|-------|------|-----------|
| **solution_ideator** | Brainstorm SaaS solution ideas addressing validated pain points | Creative Ideation with market constraints |
| **solution_evaluator** | Evaluate ideas with market fit, feasibility, and differentiation scores | Multi-Criteria Scoring Matrix |
| **competitive_researcher** | Research competitive landscape, existing solutions, gaps | Gap Analysis Protocol |
| **market_analyst** | Analyze market dynamics, trends, and positioning opportunities | Market Dynamics Framework |
| **solution_refiner** | Enhance solutions with competitive intelligence insights | Iterative Refinement Loop |
| **strategic_selector** | Final solution selection with strategic scoring | Selection Criteria Matrix (viability × opportunity × fit) |

---

### 3. SEOStrategyCrew (Stage 9) - 11 Agents

| Agent | Role | Framework |
|-------|------|-----------|
| **keyword_strategist** | Keyword analysis, tiering, and prioritization | Tier Classification (T1/T2/T3 by difficulty × volume) |
| **content_strategist** | Content strategy, pillar pages, topic clusters | Topic-Cluster Architecture |
| **seo_specialist** | Technical SEO, implementation planning, final synthesis | Implementation Roadmap Builder |
| **premium_tier_analyst** | Analyze premium tier keywords for high-value targeting | Premium Keyword Analysis Protocol |
| **high_priority_analyst** | Identify and prioritize high-impact keyword opportunities | Priority Scoring Matrix |
| **tier_0_analyst** | Analyze tier 0 (immediate priority) keywords | Quick-Win Identification |
| **tier_1_analyst** | Analyze tier 1 (high priority) keywords | Strategic Opportunity Mapping |
| **strategic_tier_analyst** | Strategic keyword analysis for long-term positioning | Market Position Framework |
| **geographic_tier_analyst** | Location-based keyword opportunities and regional targeting | Geographic Expansion Protocol |
| **category_tier_analyst** | Category-specific keyword analysis and segmentation | Category Domination Strategy |
| **keyword_summary_analyst** | Synthesize keyword analysis into actionable summary | Executive Summary Framework |

---

### 4. AudienceMappingCrew (Stage 6.5) - 1 Agent

| Agent | Role | Framework |
|-------|------|-----------|
| **audience_researcher** | Audience segmentation, ICP development, persona creation | Behavioral Segmentation Protocol |

---

### 5. MarketSizingCrew (Stage 8.6) - 1 Agent

| Agent | Role | Framework |
|-------|------|-----------|
| **market_analyst** | TAM/SAM/SOM calculation, market viability assessment | **Triangle Validation Method (TVM)**: Keyword-Based + Top-Down + Bottom-Up. **STRIVE Rule**: 4/6 criteria for "Strong". **3-2-1 Hierarchy**: TAM >3x SAM >2x SOM |

---

### 6. TrendLongevityCrew (Stage 9.2) - 1 Agent

| Agent | Role | Framework |
|-------|------|-----------|
| **trend_analyst** | Market momentum, trend sustainability, timing assessment | **Momentum Triangle Analysis (MTA)**: Search + Discussion + Competitive momentum. Classifies: Growing/Stable/Declining. Flags fads (<12mo spike) |

---

### 7. PricingStrategyCrew (Stage 8.7) - 1 Agent

| Agent | Role | Framework |
|-------|------|-----------|
| **pricing_analyst** | Optimal pricing strategy, tier structure, unit economics | **WTP-Competitive Alignment**: Competitor benchmarks + Value-based + Unit economics + Psychology. **2:1 Viability Rule**: LTV/CAC ≥2:1 |

---

### 8. SolutionRefinementCrew (Stage 8.85) - 1 Agent

| Agent | Role | Framework |
|-------|------|-----------|
| **strategic_advisor** | Refine solution using keyword demand insights | **4D Refinement Model**: (1) Geographic priorities (2) Category pivots (3) Feature prioritization (4) Content strategy direction |

---

### 9. DataSourceCrew (Stage 9.75, conditional) - 2 Agents

| Agent | Role | Framework |
|-------|------|-----------|
| **data_source_researcher** | API/database discovery, availability verification | **3-Tier Verification**: (1) Search API docs (2) Verify public access (3) Document 3-5 fallbacks |
| **data_quality_analyst** | Evaluate quality, coverage, cost, integration complexity | **5D Quality Matrix**: Coverage × Freshness × Quality × Cost × Reliability |

---

### 10. LandingPageCrew (Optional) - 8 Agents

| Agent | Role | Framework |
|-------|------|-----------|
| **marketing_strategist** | Strategic brief with persona focus, messaging, memorable element | Strategic Landing Framework - ONE persona, ONE memorable element |
| **creative_director** | Autonomous visual strategy (archetype, intensity, hero layout) | Niche-Derived Archetypes - visual differentiation from niche analysis |
| **visual_designer** | Interprets creative direction into card treatments, visual surprises | Creative Interpretation Protocol - specific visual decisions |
| **brand_designer** | Brand identity, color palette, typography following creative direction | Category-to-Color Protocol - maps product types to optimal aesthetics |
| **landing_page_copywriter** | Conversion-focused copy following section_density from creative direction | Problem-First Framework - lead with pain, avoid AI slop patterns |
| **html_developer** | HTML/Tailwind implementation with visual design spec | Mood-to-Layout Protocol - custom layouts per design mood |
| **animation_enhancer** | Premium motion design and micro-interactions | Intensity-to-Animation Mapping - animations based on visual intensity |
| **qa_reviewer** | Validates and fixes visual design issues (layout, typography, responsive) | Structured QA Validation - quality scoring and issue fixing |

**Pipeline Flow:**
```
Strategy → Creative Direction → Visual Design → Brand Identity → Copy → HTML → Animation → QA Review
```

**Pipeline Phases:**
1. **Strategy Phase**: `marketing_strategist` creates strategic brief with ONE persona focus
2. **Creative Direction Phase**: `creative_director` + `visual_designer` define visual approach
3. **Design Phase**: `brand_designer` creates brand identity following creative direction
4. **Content Phase**: `landing_page_copywriter` writes conversion copy
5. **Implementation Phase**: `html_developer` + `animation_enhancer` build and animate
6. **Validation Phase**: `qa_reviewer` validates and fixes issues

---

### 11. TrafficMonetizationCrew (Stage 8.55, conditional) - 1 Agent

| Agent | Role | Framework |
|-------|------|-----------|
| **traffic_monetization_analyst** | Monetization strategy for directories/aggregators | Publisher Revenue Model - ads + affiliate + sponsored listings |

---

## ASCII Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              NicheIQ Research Pipeline                              │
│                           16-Stage Autonomous AI Research                           │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   INPUT     │
                                    │ Niche Idea  │
                                    └──────┬──────┘
                                           │
          ┌────────────────────────────────┴────────────────────────────────┐
          │                     STAGE 1-4: VALIDATION                        │
          │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
          │  │   Stage 1   │  │   Stage 2   │  │   Stage 3   │  │ Stage 4 │ │
          │  │   Niche     │──│   Market    │──│  Problem    │──│  Query  │ │
          │  │ Definition  │  │ Assessment  │  │ Validation  │  │ Builder │ │
          │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                     STAGE 5: DATA COLLECTION                     │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │                    Search & Discover                        │ │
          │  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │ │
          │  │  │   Serper    │    │   Reddit    │    │   Twitter   │     │ │
          │  │  │   (Search)  │    │   (PRAW)    │    │  (Scraper)  │     │ │
          │  │  └─────────────┘    └─────────────┘    └─────────────┘     │ │
          │  │                ThreadRelevanceValidator                     │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                     STAGE 6: PAIN POINT ANALYSIS                 │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │               PainPointCrew (Knowledge Sources/RAG)         │ │
          │  │                                                              │ │
          │  │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │ │
          │  │   │   content_   │──▶│  pain_point_ │──▶│  pain_point_ │   │ │
          │  │   │  researcher  │   │   analyst    │   │   validator  │   │ │
          │  │   │              │   │              │   │              │   │ │
          │  │   │ Categorize   │   │ Extract with │   │ Score with   │   │ │
          │  │   │ discussions  │   │ 3-Quote Min  │   │ evidence     │   │ │
          │  │   └──────────────┘   └──────────────┘   └──────────────┘   │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                    STAGE 6.5: AUDIENCE MAPPING                   │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │                   AudienceMappingCrew                        │ │
          │  │   ┌──────────────────────────────────────────────────────┐  │ │
          │  │   │  audience_researcher - ICP & Persona Development     │  │ │
          │  │   └──────────────────────────────────────────────────────┘  │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                   STAGE 7: SOLUTION DEVELOPMENT                  │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │               UnifiedSolutionCrew (Context Chaining)        │ │
          │  │                                                              │ │
          │  │   Task 7.1: Ideation                Task 7.2: Competitive   │ │
          │  │   ┌────────────┐ ┌────────────┐     ┌────────────────────┐  │ │
          │  │   │ solution_  │▶│ solution_  │     │ competitive_       │  │ │
          │  │   │ ideator    │ │ evaluator  │     │ researcher         │  │ │
          │  │   └────────────┘ └────────────┘     └────────────────────┘  │ │
          │  │         │              │                     │              │ │
          │  │         ▼              ▼                     ▼              │ │
          │  │   Task 7.3: Refinement         Task 7.4: Selection         │ │
          │  │   ┌────────────────────┐       ┌────────────────────┐      │ │
          │  │   │ solution_refiner   │──────▶│ strategic_selector │      │ │
          │  │   │ + market_analyst   │       │                    │      │ │
          │  │   └────────────────────┘       └────────────────────┘      │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                    STAGE 8: BUSINESS VALIDATION                  │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │                    PricingStrategyCrew                       │ │
          │  │   ┌──────────────────────────────────────────────────────┐  │ │
          │  │   │  pricing_analyst - WTP-Competitive Alignment         │  │ │
          │  │   │  LTV/CAC ≥2:1 | Tier structure | Unit economics      │  │ │
          │  │   └──────────────────────────────────────────────────────┘  │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          │                                                                  │
          │  ┌─── Stage 8.5 ───┐  ┌─── Stage 8.6 ───┐  ┌── Stage 8.7 ──┐  │
          │  │ KeywordValidate │  │ MarketSizingCrew│  │ SolutionRefine│  │
          │  │ (DataForSEO)    │  │ market_analyst  │  │ strategic_    │  │
          │  │                 │  │ TAM/SAM/SOM     │  │ advisor       │  │
          │  │                 │  │ TVM + STRIVE    │  │ 4D Refinement │  │
          │  └─────────────────┘  └─────────────────┘  └───────────────┘  │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                    STAGE 9: SEO & KEYWORDS                       │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │                    SEOStrategyCrew (CSV Input)              │ │
          │  │                                                              │ │
          │  │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │ │
          │  │   │   keyword_   │──▶│   content_   │──▶│    seo_      │   │ │
          │  │   │  strategist  │   │  strategist  │   │  specialist  │   │ │
          │  │   │              │   │              │   │              │   │ │
          │  │   │ Tier 1/2/3   │   │ Topic        │   │ Technical    │   │ │
          │  │   │ Keywords     │   │ Clusters     │   │ Roadmap      │   │ │
          │  │   └──────────────┘   └──────────────┘   └──────────────┘   │ │
          │  │                                                              │ │
          │  │   Phase 9.1a: LLM seed generation (40-50 keywords)          │ │
          │  │   Phase 9.1b: DataForSEO bulk validation                    │ │
          │  │   Phase 9.1c: Expand to 150+ with metrics & tiering         │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌────────────────────────────────────┴────────────────────────────┐
          │                   STAGE 9.2: TREND ANALYSIS                      │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │                   TrendLongevityCrew                         │ │
          │  │   ┌──────────────────────────────────────────────────────┐  │ │
          │  │   │  trend_analyst - Momentum Triangle Analysis (MTA)    │  │ │
          │  │   │  Search + Discussion + Competitive momentum signals  │  │ │
          │  │   │  Outputs: Growing/Stable/Declining | Fad detection   │  │ │
          │  │   └──────────────────────────────────────────────────────┘  │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
          ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┴─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
          ╎              CONDITIONAL STAGES (Based on solution type)        ╎
          ╎                                                                  ╎
          ╎  ┌─── Stage 9.6 ───┐  ┌─── Stage 9.7 ───┐  ┌─ Stage 8.55 ──┐  ╎
          ╎  │ SEO Refinement  │  │ DataSourceCrew  │  │ TrafficMonet. │  ╎
          ╎  │ (if enabled)    │  │ (if aggregator) │  │ (if directory)│  ╎
          ╎  │                 │  │                 │  │               │  ╎
          ╎  │                 │  │ data_source_    │  │ traffic_      │  ╎
          ╎  │                 │  │ researcher      │  │ monetization_ │  ╎
          ╎  │                 │  │ data_quality_   │  │ analyst       │  ╎
          ╎  │                 │  │ analyst         │  │               │  ╎
          ╎  └─────────────────┘  └─────────────────┘  └───────────────┘  ╎
          └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┬─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
                                   │
          ┌────────────────────────┴────────────────────────────────────────┐
          │                    STAGE 10: REPORT GENERATION                   │
          │  ┌─────────────────────────────────────────────────────────────┐ │
          │  │               Hybrid: Python (80%) + LLM (20%)              │ │
          │  │                                                              │ │
          │  │   Step 1: Python data assembly (27 fields - direct copy)    │ │
          │  │   Step 2: LLM synthesis (3 strategic fields only)           │ │
          │  │   Step 3: Enhanced sections (metadata, evidence, roadmaps)  │ │
          │  │                                                              │ │
          │  │   Outputs:                                                   │ │
          │  │   ├── Phase 1: Executive Dashboard (go/no-go verdict)       │ │
          │  │   ├── Phase 2: GTM Blueprint (ICP, channels, 30-day plan)   │ │
          │  │   └── Phase 3: Analytics & Visualizations                   │ │
          │  └─────────────────────────────────────────────────────────────┘ │
          └────────────────────────────────────┬───────────────────────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │       OUTPUT        │
                                    │  final_report.json  │
                                    │  + visualizations   │
                                    └─────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AGENT COUNT SUMMARY                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  PainPointCrew (6)       : 3 agents   │  MarketSizingCrew (8.6)    : 1 agent       │
│  AudienceMappingCrew(6.5): 1 agent    │  PricingStrategyCrew (8.7) : 1 agent       │
│  UnifiedSolutionCrew(7)  : 6 agents   │  SolutionRefinementCrew(8.85): 1 agent     │
│  SEOStrategyCrew (9)     : 11 agents  │  TrendLongevityCrew (9.2)  : 1 agent       │
│  DataSourceCrew (9.75)   : 2 agents   │  TrafficMonetizationCrew   : 1 agent       │
│  LandingPageCrew         : 8 agents   │                                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  TOTAL: 36 Specialized AI Agents across 11 Crews                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Simplified Customer-Facing Diagram

```
                           NicheIQ: How It Works
                        ═══════════════════════════

    Your Niche Idea
          │
          ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 1-4: VALIDATION                                  │
    │  Is this niche viable? What problems exist?             │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 5: DATA COLLECTION                               │
    │  Scrape Reddit + Twitter for real customer discussions  │
    │  100s-1000s of posts analyzed automatically             │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 6-7: ANALYSIS                                    │
    │  • 3 agents extract & validate pain points              │
    │  • 6 agents develop & evaluate solution ideas           │
    │  • 1 agent maps target audience personas                │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 8: BUSINESS MODEL                                │
    │  • Pricing strategy (LTV/CAC analysis)                  │
    │  • Market sizing (TAM/SAM/SOM)                          │
    │  • Solution refinement with keyword insights            │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 9: SEO & KEYWORDS                                │
    │  • 150+ keywords validated with search volume data      │
    │  • Content strategy with topic clusters                 │
    │  • Implementation roadmap                               │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 9.2: TREND ANALYSIS                              │
    │  Is the market growing, stable, or declining?           │
    │  Fad detection to avoid short-lived opportunities       │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────┐
    │  STAGE 10: FINAL REPORT                                 │
    │  • Executive dashboard with go/no-go verdict            │
    │  • Go-to-market blueprint                               │
    │  • Visualizations & analytics                           │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                    ╔═══════════════════════╗
                    ║   Validated Business  ║
                    ║   Opportunity Report  ║
                    ╚═══════════════════════╝


    ┌─────────────────────────────────────────────────────────┐
    │  36 AI AGENTS • 11 SPECIALIZED CREWS • 16 STAGES        │
    │  From idea to validated opportunity in minutes          │
    └─────────────────────────────────────────────────────────┘
```

---

## Agent Framework Quick Reference

| Crew | Key Framework | Purpose |
|------|---------------|---------|
| PainPointCrew | **3-Quote Minimum Protocol** | Ensures every pain point has evidence |
| UnifiedSolutionCrew | **Context Chaining** | Preserves all data between agents |
| MarketSizingCrew | **Triangle Validation Method + STRIVE Rule** | Defensible TAM/SAM/SOM |
| TrendLongevityCrew | **Momentum Triangle Analysis** | Fad detection, timing |
| PricingStrategyCrew | **WTP-Competitive Alignment + 2:1 Rule** | Unit economics validation |
| SolutionRefinementCrew | **4D Refinement Model** | Geographic, category, feature, content |
| DataSourceCrew | **3-Tier Verification + 5D Quality Matrix** | API validation |

---

## Data Flow Between Crews

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Social Media    │────▶│  PainPointCrew   │────▶│  Pain Points     │
│  (Reddit/Twitter)│     │  (RAG/Knowledge) │     │  (Validated)     │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                         ┌─────────────────────────────────┘
                         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Audience Data   │────▶│ UnifiedSolution  │────▶│  Selected        │
│  (from Stage 6.5)│     │ Crew (Chaining)  │     │  Solution        │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                         ┌─────────────────────────────────┘
                         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Keyword Data    │────▶│  Business Crews  │────▶│  Validated       │
│  (DataForSEO)    │     │  (8, 8.5-8.7)    │     │  Business Model  │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                         ┌─────────────────────────────────┘
                         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  150+ Keywords   │────▶│  SEOStrategyCrew │────▶│  SEO Strategy    │
│  (CSV Input)     │     │  (CSV-based)     │     │  & Roadmap       │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                         ┌─────────────────────────────────┘
                         ▼
                    ┌──────────────────┐
                    │  Final Report    │
                    │  (Python + LLM)  │
                    └──────────────────┘
```

---

## Technical Patterns Used

### 1. Knowledge Sources (RAG)
- **Used by**: PainPointCrew
- **Purpose**: Handle 400+ social media posts via semantic search
- **Config**: `chunk_size=2000, chunk_overlap=300`

### 2. Context Chaining
- **Used by**: UnifiedSolutionCrew
- **Purpose**: Pass complete Pydantic objects between tasks
- **Pattern**: `output_pydantic` + `context=[previous_task]`

### 3. CSV Input
- **Used by**: SEOStrategyCrew
- **Purpose**: 2x more token-efficient than JSON for tabular data
- **Use case**: Keyword metrics (volume, CPC, difficulty)

### 4. Guardrails
- **Used by**: UnifiedSolutionCrew, others
- **Purpose**: Validate outputs, retry on failure
- **Pattern**: `guardrail=validation_function`

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - Deep technical architecture
- [PATTERNS.md](PATTERNS.md) - Reusable code patterns
