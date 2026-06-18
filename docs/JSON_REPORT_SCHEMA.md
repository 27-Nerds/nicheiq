# NicheIQ JSON Report Schema

This document provides a comprehensive reference for the NicheIQ research report JSON structure. All types and structures are grounded **exclusively** on the actual JSON report output.

> **Source of Truth**: Actual JSON report files (`final_report_*.json`)
> **Generated from**: `output/final_report_20260127_003149.json`

---

## Table of Contents

1. [Core Identifiers](#1-core-identifiers)
2. [Executive Summary & Dashboard](#2-executive-summary--dashboard)
3. [Go-to-Market Blueprint](#3-go-to-market-blueprint)
4. [Analytics Sections](#4-analytics-sections)
5. [Solution Selection](#5-solution-selection)
6. [Pricing & Monetization](#6-pricing--monetization)
7. [Pain Points](#7-pain-points)
8. [Competitive Analysis](#8-competitive-analysis)
9. [Market Validation](#9-market-validation)
10. [SEO Strategy](#10-seo-strategy)
11. [Audience & Context](#11-audience--context)
12. [Data Sources](#12-data-sources)
13. [Research Metadata](#13-research-metadata)
14. [Evidence & Supporting Data](#14-evidence--supporting-data)
15. [Strategy & Planning](#15-strategy--planning)
16. [Timing & Transparency](#16-timing--transparency)
17. [Type Reference](#17-type-reference)

---

## 1. Core Identifiers

| Field | Type | Description |
|-------|------|-------------|
| `niche` | `string` | The niche being researched |
| `generated_at` | `string` (ISO datetime) | Report generation timestamp |
| `seeded_from_catalog` | `boolean` | `true` when the run was seeded from a catalog pain/idea (entry mode `pain_research` / `deep_idea`) instead of a fresh discovery scrape. Such reports have thinner community evidence; the UI shows a "seeded from catalog" badge. Defaults to `false`. |

**Example:**
```json
{
  "niche": "ai llm cost calculator",
  "generated_at": "2026-01-19T20:43:34.549973"
}
```

---

## 2. Executive Summary & Dashboard

### `executive_summary: string`

High-level research summary text.

### `executive_dashboard: object`

The executive dashboard provides a quick go/no-go decision framework.

| Field | Type | Description |
|-------|------|-------------|
| `recommended_solution_snapshot` | `object` | Quick overview of recommended solution |
| `go_no_go_verdict` | `object` | Strategic recommendation |
| `core_pain_point` | `object` | The #1 pain point driving this opportunity |
| `key_metrics` | `object` | Top-line opportunity metrics |
| `confidence_score` | `number \| null` (0-1) | Overall confidence in opportunity. Null if scores unavailable. |

#### `recommended_solution_snapshot`

```json
{
  "name": "string",
  "tagline": "string",
  "core_value_prop": "string",
  "project_type": "string"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Solution name |
| `tagline` | `string` | One-sentence value proposition |
| `core_value_prop` | `string` | Core value proposition (2-3 sentences) |
| `project_type` | `string` | Solution type (e.g., "directory", "aggregator", "saas", "tool") |

#### `go_no_go_verdict`

```json
{
  "verdict": "Go",
  "rationale": "string",
  "risk_level": "Low",
  "primary_concern": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | `"Go" \| "No-Go" \| "Conditional"` | Overall recommendation |
| `rationale` | `string` | 2-3 sentence explanation |
| `risk_level` | `"Low" \| "Medium" \| "High"` | Overall risk assessment |
| `primary_concern` | `string \| null` | Main blocker if No-Go or Conditional |

#### `core_pain_point`

```json
{
  "title": "string",
  "severity_score": 0.85,
  "willingness_to_pay_score": 0.75,
  "representative_quote": "string",
  "source_platform": "Reddit r/LocalLLaMA"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | `string` | Pain point title |
| `severity_score` | `number` (0-1) | Severity score |
| `willingness_to_pay_score` | `number` (0-1) | WTP score |
| `representative_quote` | `string` | User quote illustrating pain |
| `source_platform` | `string` | Source platform |

#### `key_metrics`

```json
{
  "total_keyword_search_volume": 12210,
  "tier0_keyword_count": 1,
  "tier1_keyword_count": 24,
  "tier2_keyword_count": 40,
  "tier3_keyword_count": 0,
  "tier4_keyword_count": 107,
  "total_keyword_count": 172,
  "high_severity_pain_points": 7,
  "primary_competitor_count": 5,
  "avg_pain_point_severity": 0.76,
  "avg_willingness_to_pay": 0.72,
  "social_evidence_threads": 54,
  "market_fit_score": 0.88,
  "competitive_advantage_score": 0.7,
  "technical_feasibility_score": 0.72,
  "seo_potential_score": 0.78,
  "solo_dev_feasibility": 0.85
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_keyword_search_volume` | `number` | Total monthly search volume |
| `tier0_keyword_count` | `number` | Tier 0 (Foundation) keywords |
| `tier1_keyword_count` | `number` | Tier 1 (Quick Win) keywords |
| `tier2_keyword_count` | `number` | Tier 2 (Strategic Growth) keywords |
| `tier3_keyword_count` | `number` | Tier 3 (Geographic) keywords |
| `tier4_keyword_count` | `number` | Tier 4 (Category) keywords |
| `total_keyword_count` | `number` | Total enriched keywords |
| `high_severity_pain_points` | `number` | Pain points with severity >= 0.7 |
| `primary_competitor_count` | `number` | Direct competitors identified |
| `avg_pain_point_severity` | `number` (0-1) | Average severity |
| `avg_willingness_to_pay` | `number` (0-1) | Average WTP |
| `social_evidence_threads` | `number` | Total social threads analyzed (Reddit + Twitter + HN + generic) |
| `market_fit_score` | `number \| null` (0-1) | Market fit score |
| `competitive_advantage_score` | `number \| null` (0-1) | Competitive advantage |
| `technical_feasibility_score` | `number \| null` (0-1) | Technical feasibility |
| `seo_potential_score` | `number \| null` (0-1) | SEO growth potential |
| `solo_dev_feasibility` | `number \| null` (0-1) | Solo developer feasibility |

---

## 3. Go-to-Market Blueprint

### `go_to_market_blueprint: object`

Actionable GTM strategy for immediate execution.

| Field | Type | Description |
|-------|------|-------------|
| `ideal_customer_profile` | `object` | Detailed ICP |
| `core_marketing_message` | `string` | One-liner value proposition |
| `message_framework` | `string` | Before-After-Bridge framework |
| `recommended_channels` | `array` | Top marketing channels |
| `example_content_angles` | `array` | Content ideas |
| `first_30_days_playbook` | `object` | Week-by-week action plan |
| `budget_estimate` | `string` | Monthly budget estimate |

#### `ideal_customer_profile`

```json
{
  "persona_name": "string",
  "demographics": "string",
  "psychographics": "string",
  "pain_points": ["string"],
  "goals": ["string"],
  "buying_triggers": "string",
  "decision_criteria": "string"
}
```

#### `recommended_channels[0]`

```json
{
  "channel_name": "string",
  "channel_type": "string",
  "target_audience_size": "string",
  "rationale": "string",
  "strategy": "string",
  "priority": "High"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `channel_name` | `string` | Channel name |
| `channel_type` | `string` | Type: Social, SEO, Paid, Community |
| `target_audience_size` | `string` | Estimated audience size |
| `rationale` | `string` | Why recommended |
| `strategy` | `string` | How to approach |
| `priority` | `"High" \| "Medium" \| "Low"` | Priority level |

#### `example_content_angles[0]`

```json
{
  "title": "string",
  "content_type": "string",
  "pain_point_addressed": "string",
  "hook": "string",
  "key_points": ["string"],
  "target_channel": "string"
}
```

#### `first_30_days_playbook`

```json
{
  "week_1_actions": ["string"],
  "week_2_actions": ["string"],
  "week_3_actions": ["string"],
  "week_4_actions": ["string"],
  "success_metrics": ["string"]
}
```

---

## 4. Analytics Sections

### `market_analytics: object`

```json
{
  "overall_opportunity_score": 0.75,
  "market_size_category": "Medium",
  "selection_confidence": 0.82,
  "competitive_intensity": "Low",
  "recommendation": "Go"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `overall_opportunity_score` | `number` (0-1) | Weighted average of selection criteria |
| `market_size_category` | `"Large" \| "Medium" \| "Small"` | Market size based on volume |
| `selection_confidence` | `number` (0-1) | Confidence in solution selection |
| `competitive_intensity` | `"Low" \| "Medium" \| "High"` | Competitive landscape intensity |
| `recommendation` | `"Go" \| "Conditional" \| "No-Go"` | Overall recommendation |

### `seo_analytics: object`

```json
{
  "tier0_count": 1,
  "tier1_count": 24,
  "tier2_count": 40,
  "tier3_count": 0,
  "tier4_count": 107,
  "total_keywords": 172,
  "total_search_volume": 12210,
  "avg_competition": 16.97,
  "keyword_diversity_score": 0.77,
  "high_volume_keywords": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `tier0_count` | `number` | Premium keywords |
| `tier1_count` | `number` | Quick Win keywords |
| `tier2_count` | `number` | Strategic Growth keywords |
| `tier3_count` | `number` | Geographic/Niche keywords |
| `tier4_count` | `number` | Specialized/Category keywords |
| `total_keywords` | `number` | Total keyword count |
| `total_search_volume` | `number` | Total monthly search volume |
| `avg_competition` | `number` | Average competition (0-100) |
| `keyword_diversity_score` | `number` (0-1) | Keyword variety score |
| `high_volume_keywords` | `number` | Keywords with >1000 monthly searches |

### `competitive_analytics: object`

```json
{
  "competitor_count": 11,
  "market_saturation_score": 0.5,
  "differentiation_strength": "Strong",
  "market_gaps_identified": 6,
  "avg_competitor_features": 5.6
}
```

| Field | Type | Description |
|-------|------|-------------|
| `competitor_count` | `number` | Total unique competitors |
| `market_saturation_score` | `number` (0-1) | 0=blue ocean, 1=saturated |
| `differentiation_strength` | `"Strong" \| "Moderate" \| "Weak"` | Differentiation assessment |
| `market_gaps_identified` | `number` | Number of gaps identified |
| `avg_competitor_features` | `number` | Average feature count |

### `pain_point_analytics: object`

```json
{
  "total_pain_points": 10,
  "high_severity_count": 7,
  "high_opportunity_count": 6,
  "quadrant_distribution": {
    "high_severity_high_wtp": 6,
    "high_severity_low_wtp": 1,
    "low_severity_high_wtp": 3,
    "low_severity_low_wtp": 0
  },
  "avg_severity": 0.76,
  "avg_willingness_to_pay": 0.72,
  "top_pain_point_title": "string"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_pain_points` | `number` | Total identified |
| `high_severity_count` | `number` | Severity >= 0.7 |
| `high_opportunity_count` | `number` | Both severity >= 0.6 and WTP >= 0.6 |
| `quadrant_distribution` | `object` | Priority matrix distribution |
| `avg_severity` | `number` (0-1) | Average severity |
| `avg_willingness_to_pay` | `number` (0-1) | Average WTP |
| `top_pain_point_title` | `string` | Highest priority pain point |

### `data_quality_summary: object`

```json
{
  "social_content_quality_tier": "GOOD",
  "pain_point_quality_tier": "SILVER",
  "pain_point_confidence_score": 0.72,
  "overall_data_quality": "MEDIUM",
  "quality_caveats": ["string"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `social_content_quality_tier` | `"EXCELLENT" \| "GOOD" \| "MINIMAL" \| "INSUFFICIENT"` | Social content quality |
| `pain_point_quality_tier` | `"GOLD" \| "SILVER" \| "BRONZE" \| "INSUFFICIENT"` | Research evidence quality (see tier definitions below) |
| `pain_point_confidence_score` | `number` (0-1) | Weighted confidence score based on evidence metrics (see weights below) |
| `overall_data_quality` | `"HIGH" \| "MEDIUM" \| "LOW"` | Overall quality |
| `quality_caveats` | `array[string]` | Warnings about limitations |

**Pain Point Quality Tier** measures research evidence breadth and diversity, not niche attractiveness. Tiers are determined by four evidence metrics:

| Tier | `unique_source_count` | `subreddit_diversity` | `pain_point_count` | `quote_density` |
|------|----------------------|----------------------|-------------------|----------------|
| GOLD | >= 20 | >= 4 | >= 5 | >= 8.0 |
| SILVER | >= 10 | >= 2 | >= 3 | >= 5.0 |
| BRONZE | >= 5 | (no gate) | >= 2 | >= 3.0 |
| INSUFFICIENT | below BRONZE — pipeline stops | | | |

**Confidence score weights** (single-platform): `unique_source_count` 0.30, `subreddit_diversity` 0.25, `quote_density` 0.25, `pain_point_count` 0.20.

---

## 5. Solution Selection

### Top-Level Selection Fields

| Field | Type | Description |
|-------|------|-------------|
| `selected_solution_name` | `string` | Name of selected solution |
| `selection_rationale` | `string` | Why selected over alternatives (carries an appended keyword-validation update when the winner pivoted) |
| `original_selection_reasoning` | `string \| null` | Original strategic rationale, preserved verbatim when keyword validation pivoted the winner |
| `recommended_focus` | `string` | Strategic focus recommendation |
| `selected_solution_details` | `object` | Complete solution details (35 keys) |
| `solution_user_journey` | `string` | Step-by-step user workflow |
| `solution_implementation_overview` | `string` | High-level implementation plan |
| `mvp_scope_definition` | `string` | MVP scope definition |
| `site_structure` | `object` | LLM-generated site architecture (Stage 10.5) |
| `user_flows` | `object` | LLM-generated user journeys (Stage 10.5) |

> **Note:** `selection_criteria_scores` was removed in favor of ScoreAccessor as single source of truth.
> All diagnostic scores are now served via `key_metrics` in the executive dashboard.

### `selected_solution_details` (35 keys)

```json
{
  "solution_name": "string",
  "description": "string",
  "value_proposition": "string",
  "pain_points_addressed": ["string"],
  "core_features": ["string"],
  "target_personas": ["string"],
  "technical_approach": "string",
  "differentiation_factors": ["string"],
  "requires_data_aggregation": true,
  "data_sources": ["string"],
  "estimated_development_time": "string",
  "pricing_strategy": "string",
  "market_fit_score": 0.88,
  "technical_feasibility_score": 0.72,
  "project_type": "directory",
  "programmatic_seo_opportunity": "string",
  "content_generation_model": "string",
  "organic_discovery_queries": ["string"],
  "estimated_cac_organic": "string",
  "estimated_cac_paid": "string",
  "seo_scalability_score": 0.75,
  "estimated_indexable_pages": 1000,
  "novelty_score": 0.7,
  "conventional_approach": "string",
  "innovation_angle": "string",
  "why_it_works": "string",
  "solo_dev_feasibility": 0.6,
  "keyword_geographic_priorities": ["string"],
  "keyword_feature_priorities": ["string"],
  "keyword_strategic_insights": "string",
  "category_pivot_suggestion": null,
  "seo_scalability_score_refined": 0.78,
  "estimated_cac_organic_refined": "string",
  "programmatic_seo_opportunity_refined": "string",
  "seo_refinement_metadata": {
    "baseline_volume_used": 12210,
    "volume_multiplier": 1.1,
    "tier1_multiplier": 1.15,
    "competition_modifier": 1.08,
    "base_cac": 15,
    "difficulty_multiplier": 0.87,
    "volume_discount": 0.85,
    "estimated_year1_pages": 500
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `solution_name` | `string` | Solution name |
| `description` | `string` | Detailed description |
| `value_proposition` | `string` | Value proposition statement |
| `pain_points_addressed` | `array[string]` | Pain points solved |
| `core_features` | `array[string]` | Core features |
| `target_personas` | `array[string]` | Target user personas |
| `technical_approach` | `string` | Technical implementation |
| `differentiation_factors` | `array[string]` | Unique differentiators |
| `requires_data_aggregation` | `boolean` | Needs data sourcing |
| `data_sources` | `array[string]` | Required data sources |
| `estimated_development_time` | `string` | Dev time estimate |
| `pricing_strategy` | `string` | Pricing approach |
| `market_fit_score` | `number` (0-1) | Market fit |
| `technical_feasibility_score` | `number` (0-1) | Feasibility |
| `project_type` | `string` | Project type |
| `programmatic_seo_opportunity` | `string` | SEO opportunity description |
| `content_generation_model` | `string` | Content strategy |
| `organic_discovery_queries` | `array[string]` | Example search queries |
| `estimated_cac_organic` | `string` | Organic CAC estimate |
| `estimated_cac_paid` | `string` | Paid CAC estimate |
| `seo_scalability_score` | `number` (0-1) | SEO scalability |
| `estimated_indexable_pages` | `number` | Year 1 pages |
| `novelty_score` | `number` (0-1) | Refiner's novelty assessment; drives the composite score and the "Innovator" superpower |
| `obviousness_score` | `number\|null` (0-1) | Independent novelty critic's estimate of how OBVIOUS the idea is — **lower = more original**. Carried from the source `RawConcept` by whitespace-normalized name (M/D/J-tag pattern); `null` when the concept name didn't survive refinement. Surfaced in the UI as **Originality** (= 1 − obviousness_score). When absent (legacy data), the UI falls back to `novelty_score` **and** keeps the honest **Novelty** label rather than relabeling it as Originality |
| `conventional_approach` | `string` | What most builders would try |
| `innovation_angle` | `string` | How this solution diverges |
| `why_it_works` | `string` | Evidence-based reason it succeeds |
| `solo_dev_feasibility` | `number` (0-1) | Solo developer feasibility |
| `keyword_geographic_priorities` | `array[string]` | Geographic priorities |
| `keyword_feature_priorities` | `array[string]` | Feature priorities |
| `keyword_strategic_insights` | `string` | Strategic insights |
| `category_pivot_suggestion` | `string \| null` | Pivot recommendation |
| `seo_scalability_score_refined` | `number` (0-1) | Refined SEO score |
| `estimated_cac_organic_refined` | `string` | Refined organic CAC |
| `programmatic_seo_opportunity_refined` | `string` | Refined SEO assessment |
| `seo_refinement_metadata` | `object` | SEO calculation details |

### `site_structure: object` (Stage 10.5 - LLM-generated)

LLM-generated site architecture with sections, pages, URL patterns, and MVP priorities.

```json
{
  "overview": "Programmatic SEO-first architecture leveraging user data to generate comparison and listing pages at scale.",
  "sections": [SiteSection],
  "total_static_pages": 8,
  "total_programmatic_pages": 500,
  "mvp_page_count": 12,
  "tech_stack_recommendation": "Next.js + Supabase for SSG with dynamic data"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `overview` | `string` | 1-2 sentence architecture philosophy |
| `sections` | `array[SiteSection]` | 2-5 logical sections with pages |
| `total_static_pages` | `number` | Count of hand-crafted pages |
| `total_programmatic_pages` | `number` | Count of auto-generated pages |
| `mvp_page_count` | `number` | Pages needed for MVP launch (P0 only) |
| `tech_stack_recommendation` | `string \| null` | Suggested tech stack |

#### `SiteSection`

```json
{
  "section_name": "Core Content",
  "description": "Main value-generating comparison and listing pages",
  "pages": [SitePage]
}
```

#### `SitePage`

```json
{
  "page_name": "Product Comparison Page",
  "url_pattern": "/compare/[product-a]-vs-[product-b]",
  "page_type": "programmatic",
  "purpose": "Head-to-head comparison of two products with pricing and features",
  "estimated_count": 250,
  "priority": "P0"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `page_name` | `string` | Human-readable page name |
| `url_pattern` | `string` | URL pattern using [param] syntax |
| `page_type` | `"static" \| "programmatic" \| "dynamic"` | Page generation type |
| `purpose` | `string` | 1-sentence purpose |
| `estimated_count` | `number \| null` | For programmatic pages only |
| `priority` | `"P0" \| "P1" \| "P2"` | MVP priority (P0=must-have, P1=soon, P2=later) |

### `user_flows: object` (Stage 10.5 - LLM-generated)

LLM-generated user journeys showing how target personas discover, use, and convert.

```json
{
  "flows": [UserFlow],
  "key_insight": "Both personas share the comparison page as critical decision point - optimize for mobile conversion."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `flows` | `array[UserFlow]` | 1-3 user journey flows |
| `key_insight` | `string \| null` | Cross-flow observation or strategic insight |

#### `UserFlow`

```json
{
  "flow_name": "Organic Comparison Discovery",
  "persona": "Cost-conscious developer evaluating LLM options",
  "goal": "Find the most cost-effective LLM for their use case",
  "entry_point": "Google search: 'gpt-4 vs claude pricing comparison'",
  "steps": [UserFlowStep],
  "conversion_point": "Email signup for price alerts on the comparison page",
  "success_metric": "Signup conversion rate"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `flow_name` | `string` | Descriptive flow name |
| `persona` | `string` | Target persona from solution's target_personas |
| `goal` | `string` | What the user wants to accomplish |
| `entry_point` | `string` | How they arrive (Google search, direct, referral) |
| `steps` | `array[UserFlowStep]` | 3-7 sequential steps |
| `conversion_point` | `string` | Where/how user converts |
| `success_metric` | `string` | Measurable KPI for this flow |

#### `UserFlowStep`

```json
{
  "step_number": 1,
  "action": "User lands on comparison page from organic search",
  "page": "Product Comparison Page",
  "system_response": "Shows side-by-side pricing comparison with real-time data"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `step_number` | `number` | Step sequence (1-based) |
| `action` | `string` | What user does |
| `page` | `string` | Which page this happens on |
| `system_response` | `string \| null` | What system shows in response |

---

## 6. Pricing & Monetization

### `pricing_strategy: object` (21 keys)

The pricing strategy supports multiple monetization models, with different fields populated based on the chosen model.

#### Subscription Models Example (Freemium, Freemium-Lite, Subscription, Hybrid, One-time, Usage-Based)

```json
{
  "solution_name": "string",
  "recommended_starter_price": "$29/month",
  "recommended_pro_price": "$79/month",
  "recommended_enterprise_price": "Custom (contact sales)",
  "pricing_model": "Freemium",
  "pricing_rationale": "string",
  "free_tier_features": ["string"],
  "starter_tier_features": ["string"],
  "pro_tier_features": ["string"],
  "estimated_arpu": "$35-$55/month",
  "estimated_ltv": "$420-$990",
  "ltv_to_cac_ratio": "3:1 to 6:1",
  "price_vs_competitors": "string",
  "value_proposition_delta": "string",
  "pricing_confidence": "High",
  "wtp_validation": "string",
  "market_segment_pricing": {
    "individuals": "string",
    "professionals_small_team": "string",
    "enterprise_custom": "string",
    "nonprofit_academic": "string"
  }
}
```

#### Ad/Affiliate Models Example (Ad-Supported-Free, Affiliate-Only)

```json
{
  "solution_name": "PlumbingCostCalc",
  "recommended_starter_price": null,
  "recommended_pro_price": null,
  "recommended_enterprise_price": null,
  "pricing_model": "Ad-Supported-Free",
  "pricing_rationale": "100% free tool. WTP score of 0.22 indicates users won't pay. Monetized via display ads targeting homeowner intent traffic.",
  "free_tier_features": null,
  "starter_tier_features": null,
  "pro_tier_features": null,
  "estimated_monthly_ad_revenue": "$400-600/month",
  "estimated_monthly_affiliate_revenue": "$150-300/month",
  "estimated_cpm_rate": "$6-10 CPM (home services niche)",
  "recommended_ad_networks": ["Google AdSense", "Ezoic"],
  "estimated_arpu": "$0.012 per pageview (ads + affiliate)",
  "estimated_ltv": "N/A - traffic-based model",
  "ltv_to_cac_ratio": "N/A - SEO-driven traffic acquisition",
  "price_vs_competitors": "Free vs competitor freemium models",
  "value_proposition_delta": "100% free tool with no feature limitations",
  "pricing_confidence": "Medium",
  "wtp_validation": "Low WTP (0.22) confirms users seek free tools; monetization through ads aligns with user expectations",
  "market_segment_pricing": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `solution_name` | `string` | Solution being priced |
| `recommended_starter_price` | `string \| null` | Starter tier price (null for ad/affiliate models) |
| `recommended_pro_price` | `string \| null` | Pro tier price (null for ad/affiliate models) |
| `recommended_enterprise_price` | `string \| null` | Enterprise tier (null if not applicable) |
| `pricing_model` | `PricingModel` | Model type (see Type Reference) |
| `pricing_rationale` | `string` | Why this strategy |
| `free_tier_features` | `array[string] \| null` | Free tier features (null for ad/affiliate) |
| `starter_tier_features` | `array[string] \| null` | Starter features (null for ad/affiliate) |
| `pro_tier_features` | `array[string] \| null` | Pro features (null for ad/affiliate) |
| `estimated_monthly_ad_revenue` | `string \| null` | Monthly ad revenue estimate (ad-supported models only) |
| `estimated_monthly_affiliate_revenue` | `string \| null` | Monthly affiliate revenue (affiliate models only) |
| `estimated_cpm_rate` | `string \| null` | CPM rate estimate (ad-supported models only) |
| `recommended_ad_networks` | `array[string] \| null` | Recommended ad networks (ad-supported models only) |
| `estimated_arpu` | `string` | Average revenue per user (or per pageview for traffic models) |
| `estimated_ltv` | `string` | Lifetime value range (or "N/A" for traffic models) |
| `ltv_to_cac_ratio` | `string` | LTV:CAC ratio estimate (or "N/A" for SEO-driven traffic) |
| `price_vs_competitors` | `string` | Competitive positioning |
| `value_proposition_delta` | `string` | Value vs price comparison |
| `pricing_confidence` | `"High" \| "Medium" \| "Low"` | Confidence level |
| `wtp_validation` | `string` | WTP evidence |
| `market_segment_pricing` | `object \| null` | Segment-specific pricing |

#### Pricing Model Selection Guidance

The pricing model is selected based on WTP scores and project type:

| Pricing Model | When Used | Typical Fields Populated |
|---------------|-----------|-------------------------|
| **Freemium** | High WTP (>0.6), clear feature differentiation | All tier prices, tier features |
| **Freemium-Lite** | Moderate WTP, simple feature set | Free + Pro prices only (no Starter/Enterprise) |
| **Subscription** | B2B focus, no free tier viable | Starter/Pro/Enterprise prices |
| **Hybrid** | Subscription + usage-based | Tier prices + usage metrics |
| **One-time** | Tools, templates, digital products | Single price |
| **Usage-Based** | API/tool with variable consumption | Usage-based pricing |
| **Ad-Supported-Free** | Low WTP (<0.3), high traffic potential, directories/aggregators | Ad revenue fields, null tier prices |
| **Affiliate-Only** | Purchase-intent traffic, product comparisons | Affiliate revenue fields, null tier prices |

### `traffic_monetization: object` (22 keys)

```json
{
  "solution_name": "string",
  "monetization_model": "Hybrid-Traffic",
  "estimated_monthly_pageviews": "string",
  "traffic_source_breakdown": {
    "organic_search": "65%",
    "direct": "20%",
    "referral": "15%"
  },
  "estimated_cpm_rate": "string",
  "estimated_monthly_ad_revenue": "string",
  "recommended_ad_networks": ["string"],
  "affiliate_commission_rate": "string",
  "estimated_affiliate_ctr": "string",
  "estimated_monthly_affiliate_revenue": "string",
  "recommended_affiliate_programs": ["string"],
  "sponsored_listing_price": "string",
  "premium_placement_price": "string",
  "lead_gen_price_per_lead": "string",
  "estimated_monthly_revenue_range": "string",
  "estimated_annual_revenue_range": "string",
  "break_even_traffic_threshold": "string",
  "monetization_rationale": "string",
  "scaling_strategy": "string",
  "monetization_confidence": "High",
  "saas_alternative_viable": true,
  "saas_vs_traffic_recommendation": "string"
}
```

### `estimated_cac_breakdown: string`

CAC breakdown text (organic vs paid).

---

## 7. Pain Points

### `pain_points_summary: string`

Summary with severity/WTP insights.

### `detailed_pain_points: array` (10 items typical)

```json
{
  "title": "string",
  "description": "string",
  "mention_count": 12,
  "severity_score": 0.85,
  "willingness_to_pay": 0.8,
  "opportunity_level": "high",
  "opportunity_downgrade_reason": null,
  "representative_quotes": ["string"],
  "source_platforms": ["Reddit"],
  "categories": ["string"],
  "source_post_ids": ["abc123"],
  "affected_segments": ["string"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | `string` | Short title |
| `description` | `string` | Detailed description |
| `mention_count` | `number` | Unique discussions matched by evidence vector search (LLM estimate only when enrichment unavailable) |
| `severity_score` | `number` (0-1) | Severity (computed from evidence quotes; clamped ≤0.45 when zero quotes found) |
| `willingness_to_pay` | `number` (0-1) | WTP indicator |
| `opportunity_level` | `"high" \| "medium" \| "low"` | Code-computed from severity/WTP formula (High: both ≥0.6; Medium: one ≥0.6; Low: both <0.6); LLM may only downgrade with justification |
| `opportunity_downgrade_reason` | `string \| null` | Present when the LLM justifiably downgraded below the formula (universal-theme / niche-specificity cap) |
| `representative_quotes` | `array[string]` | User quotes |
| `source_platforms` | `array[string]` | Source platforms |
| `categories` | `array[string]` | Categories |
| `source_post_ids` | `array[string]` | Post IDs for traceability |
| `affected_segments` | `array[string]` | Affected audience segments |

---

## 8. Competitive Analysis

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `recommended_solutions` | `array[string]` | Solution recommendations |
| `solutions_summary` | `string` | Solutions overview |
| `competitive_summary` | `string` | Competitive landscape summary |
| `competitive_analysis` | `object` | Full analysis |
| `competitor_profiles` | `array[object]` | Detailed profiles |
| `overall_competitive_insights` | `string` | Strategic insights |
| `competitive_landscape_matrix` | `object` | Cross-solution matrix |

### `competitive_analysis: object`

```json
{
  "solution_landscapes": [{
    "solution_name": "string",
    "competitors": [{
      "name": "string",
      "url": "string",
      "competitor_type": "DIRECT",
      "description": "string",
      "key_features": ["string"],
      "pricing_model": "string",
      "strengths": ["string"],
      "weaknesses": ["string"]
    }],
    "market_gaps": ["string"],
    "differentiation_opportunities": ["string"],
    "competitive_intensity": "Low",
    "recommended_positioning": "string",
    "pricing_insights": "string"
  }],
  "top_opportunities": ["string"],
  "strategic_recommendations": "string"
}
```

### `competitor_profiles[0]`

```json
{
  "name": "string",
  "url": "string",
  "competitor_type": "DIRECT",
  "description": "string",
  "key_features": ["string"],
  "pricing_model": "string",
  "strengths": ["string"],
  "weaknesses": ["string"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Competitor name |
| `url` | `string` | Website URL |
| `competitor_type` | `"DIRECT" \| "PARTIAL" \| "INDIRECT"` | Type |
| `description` | `string` | What they offer |
| `key_features` | `array[string]` | Main features |
| `pricing_model` | `string` | Pricing model |
| `strengths` | `array[string]` | Strengths |
| `weaknesses` | `array[string]` | Weaknesses |

### `competitive_landscape_matrix: object`

```json
{
  "all_solutions_analyzed": ["string"],
  "selected_solution_competitors": ["string"],
  "competitor_overlap": [{
    "competitor_name": "string",
    "solutions_competed": ["string"],
    "competitor_type": "string",
    "threat_level": "string"
  }],
  "competitive_intensity_by_solution": [{
    "solution_name": "string",
    "intensity": "Low"
  }],
  "market_insight": "string"
}
```

---

## 9. Market Validation

### `market_validation: string`

Overall market validation conclusion.

### `market_sizing: object` (19 keys)

```json
{
  "total_addressable_market": "string",
  "serviceable_available_market": "string",
  "serviceable_obtainable_market_y1": "string",
  "serviceable_obtainable_market_y3": "string",
  "primary_methodology": "string",
  "methodology_explanation": "string",
  "data_sources_used": ["string"],
  "segment_sizing": [{
    "segment_name": "string",
    "tam_estimate": "string",
    "sam_estimate": "string",
    "som_estimate": "string",
    "sizing_methodology": "string",
    "confidence_level": "string"
  }],
  "keyword_demand_signal": "string",
  "pain_point_frequency": "string",
  "competitor_market_presence": "string",
  "market_growth_rate": "string",
  "growth_drivers": ["string"],
  "market_saturation_level": "Low",
  "market_timing_assessment": "string",
  "risk_factors": ["string"],
  "market_viability_verdict": "Strong",
  "viability_rationale": "string",
  "recommended_entry_strategy": "string"
}
```

### `trend_longevity: object` (20 keys)

```json
{
  "trend_direction": "Growing",
  "trend_confidence": "High",
  "momentum_score": 0.85,
  "keyword_volume_trend": "Increasing",
  "volume_growth_rate": "string",
  "trend_duration": "string",
  "discussion_frequency_trend": "Increasing",
  "discussion_recency": "Recent",
  "community_growth_indicators": ["string"],
  "new_entrants_trend": "string",
  "competitive_activity_level": "string",
  "seasonal_pattern": "string",
  "peak_periods": null,
  "market_maturity": "Growth",
  "longevity_verdict": "Sustainable",
  "longevity_rationale": "string",
  "trend_reversal_risks": ["string"],
  "timing_recommendation": "Enter Now",
  "data_sources_analyzed": ["string"],
  "analysis_timeframe": "string"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `trend_direction` | `"Growing" \| "Stable" \| "Declining"` | Trend direction |
| `trend_confidence` | `"High" \| "Medium" \| "Low"` | Confidence level |
| `momentum_score` | `number` (0-1) | Momentum indicator |
| `keyword_volume_trend` | `string` | Volume trend |
| `volume_growth_rate` | `string` | YoY growth rate |
| `trend_duration` | `string` | How long active |
| `discussion_frequency_trend` | `string` | Discussion trend |
| `discussion_recency` | `"Recent" \| "Moderate" \| "Dated"` | Recency |
| `community_growth_indicators` | `array[string]` | Growth signals |
| `new_entrants_trend` | `string` | New competitor trend |
| `competitive_activity_level` | `string` | Activity level |
| `seasonal_pattern` | `string` | Seasonality |
| `peak_periods` | `null \| string` | Peak months |
| `market_maturity` | `"Emerging" \| "Growth" \| "Mature"` | Maturity stage |
| `longevity_verdict` | `"Sustainable" \| "Risky" \| "Fad"` | Longevity assessment |
| `longevity_rationale` | `string` | Verdict explanation |
| `trend_reversal_risks` | `array[string]` | Reversal risk factors |
| `timing_recommendation` | `string` | Timing advice |
| `data_sources_analyzed` | `array[string]` | Data sources |
| `analysis_timeframe` | `string` | Timeframe analyzed |

---

## 10. SEO Strategy

### Top-Level SEO Fields

| Field | Type | Description |
|-------|------|-------------|
| `acquisition_strategy_summary` | `string` | Organic acquisition overview |
| `keyword_validation_overview` | `string` | Keyword validation summary |
| `solution_keyword_comparison` | `string` | Cross-solution comparison |
| `content_strategy_preview` | `string` | Content strategy preview |
| `seo_strategy_report` | `object` | Full SEO strategy (21 keys) |

### `seo_strategy_report: object` (21 keys)

```json
{
  "total_keywords_analyzed": 172,
  "total_monthly_volume": 12210,
  "key_findings": ["string"],

  "tier_0_keywords": [TieredKeyword],
  "tier_0_strategy": "string (markdown)",
  "tier_1_keywords": [TieredKeyword],
  "tier_1_quick_win_strategy": "string (markdown)",
  "tier_2_keywords": [TieredKeyword],
  "tier_2_strategy": "string (markdown)",
  "tier_3_geographic_groups": [GeographicKeywordGroup],
  "tier_4_category_groups": [CategoryKeywordGroup],

  "content_strategy": "string (markdown)",
  "topic_clusters": [TopicCluster],
  "technical_seo_recommendations": "string (markdown)",
  "keyword_based_page_types": [KeywordBasedPageType],
  "competitive_positioning": "string (markdown)",
  "implementation_roadmap": "string (markdown)",
  "key_metrics_to_track": ["string"],
  "risk_mitigation": "string",
  "budget_allocation": "string",
  "conclusion_bottom_line": "string",
  "next_steps_checklist": ["string"]
}
```

**Removed Fields (v2.3):**
- `seed_keywords_generated` - internal debug data, never displayed
- `keyword_driven_site_architecture` - never rendered, overlapped with keyword_based_page_types
- `long_term_strategy` - duplicated implementation_roadmap
- `competitive_advantages` - redundant with competitive_positioning
- `critical_success_factors` - overlapped with next_steps_checklist
- `expected_timeline` - duplicated implementation_roadmap
- `universal_seo_elements`, `page_type_implementations`, `schema_markup_strategy` - Task 5/6 removed, technical SEO now in technical_seo_recommendations markdown

### `TieredKeyword`

```json
{
  "keyword": "llm inference cost calculator",
  "search_volume": 320,
  "competition": "VERY_LOW (8)",
  "opportunity_score": 216.0,
  "strategy": "string",
  "intent": "transactional",
  "tier": 0,
  "tier_rationale": "string"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `keyword` | `string` | Keyword phrase |
| `search_volume` | `number` | Monthly search volume |
| `competition` | `string` | Competition level (e.g., "VERY_LOW (8)") |
| `opportunity_score` | `number` | Calculated opportunity score |
| `strategy` | `string` | Targeting strategy |
| `intent` | `string` | Search intent |
| `tier` | `number` (0-4) | Tier classification |
| `tier_rationale` | `string` | Classification explanation |

### `CategoryKeywordGroup` (tier_4_category_groups)

```json
{
  "category_name": "string",
  "total_volume": 1234,
  "keywords": [{
    "keyword_name": "string",
    "search_volume": 100,
    "competition": "LOW",
    "cpc": 0.5
  }],
  "strategy_recommendation": "string"
}
```

### `TopicCluster`

```json
{
  "cluster_name": "string",
  "primary_keyword": "string",
  "supporting_keywords": ["string"],
  "total_monthly_volume": 5000,
  "content_recommendation": "string",
  "estimated_traffic_potential": "string",
  "priority": 1
}
```

### `GeographicKeywordGroup` (tier_3_geographic_groups)

```json
{
  "region_name": "Spanish-Speaking Markets",
  "total_volume": 4500,
  "competition_level": "LOW",
  "keywords": [{
    "city": "Barcelona",
    "keyword": "expat insurance barcelona",
    "search_volume": 320,
    "notes": "High expat population"
  }],
  "strategy_notes": "Focus on major expat destinations with established communities."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `region_name` | `string` | Region name (e.g., "Spanish-Speaking Markets") |
| `total_volume` | `number` | Combined monthly search volume |
| `competition_level` | `string` | Overall competition assessment |
| `keywords` | `array[GeographicKeywordEntry]` | Keywords in this region |
| `strategy_notes` | `string` | Strategic notes (1-3 sentences) |

### `KeywordBasedPageType` (keyword_based_page_types)

```json
{
  "page_type_name": "Model Comparison Pages",
  "url_pattern": "/compare/[model-a]-vs-[model-b]",
  "target_keyword_cluster": "Tier 1 Quick Wins",
  "example_keywords": ["gpt-4 vs claude", "llm comparison"],
  "primary_intent": "commercial",

  "priority": "P0",
  "required_schema": ["Product", "FAQPage"],
  "seo_optimization_notes": "Use side-by-side comparison format with pricing tables"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `page_type_name` | `string` | Page type name based on keyword intent |
| `url_pattern` | `string` | URL pattern using [param] syntax |
| `target_keyword_cluster` | `string` | Which tier/cluster this targets |
| `example_keywords` | `array[string]` | 2-5 example keywords |
| `primary_intent` | `string` | commercial, informational, navigational, transactional |

| `priority` | `string` | P0 (Tier 1), P1 (Tier 2), P2 (Tier 3-4) |
| `required_schema` | `array[string] \| null` | Schema.org types |
| `seo_optimization_notes` | `string` | SEO guidance for these pages |

---

## 11. Audience & Context

### `niche_context: object` (4 keys)

```json
{
  "niche_input": "string",
  "niche_description": "string",
  "market_segments": ["string"],
  "industry_boundaries": "string"
}
```

### `audience_mapping: object` (13 keys)

```json
{
  "audience_segments": [{
    "segment_name": "string",
    "size_estimate": "Large",
    "pain_point_alignment": ["string"],
    "motivation_drivers": ["string"],
    "expertise_level": "Intermediate",
    "budget_sensitivity": "Medium",
    "discovery_channels": ["string"],
    "influencers_followed": ["string"]
  }],
  "primary_target_segment": "string",
  "segment_prioritization_rationale": "string",
  "key_influencers": [{
    "name": "string",
    "platform": "string",
    "follower_estimate": null,
    "relevance_score": 0.85,
    "content_focus": "string",
    "engagement_level": "string",
    "outreach_priority": "High"
  }],
  "community_hubs": ["string"],
  "common_vocabulary": ["string"],
  "content_preferences": "string",
  "messaging_frameworks": ["string"],
  "tools_currently_used": ["string"],
  "frustrations_with_existing": ["string"],
  "recommended_channels": ["string"],
  "content_strategy_direction": "string",
  "early_adopter_tactics": "string"
}
```

---

## 12. Data Sources

### `data_sourcing_recommendations: string`

Data sourcing strategy for aggregation projects.

### `data_source_research_full: object` (11 keys)

```json
{
  "solution_name": "string",
  "primary_data_sources": [DataSource],
  "fallback_sources": [DataSource],
  "source_evaluation": {
    "high_priority_sources": [EvaluatedSource],
    "medium_priority_sources": [EvaluatedSource],
    "low_priority_sources": [EvaluatedSource],
    "overall_data_quality_risk": "string",
    "critical_blockers": ["string"],
    "evaluation_summary": "string"
  },
  "implementation_phases": [RoadmapPhase],
  "data_partnerships_needed": [DataPartnership],
  "estimated_monthly_cost": "string",
  "data_quality_risks": ["string"],
  "implementation_roadmap": "string",
  "competitive_data_insights": "string",
  "seo_aligned_priorities": "string"
}
```

### `DataSource`

```json
{
  "provider": "string",
  "url": "string",
  "access_model": "free",
  "cost_estimate": "string",
  "coverage": "string",
  "update_frequency": "string",
  "integration_complexity": "LOW",
  "priority": "HIGH",
  "priority_rationale": "string",
  "data_quality_notes": "string"
}
```

### `EvaluatedSource`

```json
{
  "provider": "string",
  "url": "string",
  "priority": "HIGH",
  "priority_rationale": "string",
  "quality_metrics": {
    "coverage_score": "string",
    "freshness": "string",
    "integration_complexity": "LOW",
    "cost_viability": "string",
    "quality_assessment": "string"
  },
  "mvp_cost_estimate": "string",
  "scale_cost_estimate": "string",
  "identified_risks": ["string"],
  "mitigation_strategies": ["string"]
}
```

### `RoadmapPhase` (implementation_phases[0])

```json
{
  "phase_number": 1,
  "phase_name": "MVP",
  "timeline": "Months 1-3",
  "goal": "string",
  "data_sources": ["string"],
  "estimated_monthly_cost": "string",
  "key_milestones": ["string"],
  "fallback_strategies": ["string"]
}
```

### `DataPartnership`

```json
{
  "partner_type": "direct-partnership",
  "description": "string",
  "effort_estimate": "high",
  "timeline": "3-6 months",
  "notes": "string"
}
```

### `data_infrastructure_roadmap: object` (2 keys)

```json
{
  "phases": [{
    "phase_number": 1,
    "phase_name": "MVP",
    "timeline": "Months 1-3",
    "data_sources": ["string"],
    "estimated_monthly_cost": "string",
    "key_risks": ["string"]
  }],
  "cost_scaling_insight": "string"
}
```

---

## 13. Research Metadata

### `research_metadata: object` (10 keys)

```json
{
  "reddit_posts_analyzed": 54,
  "reddit_comments_analyzed": 1234,
  "twitter_threads_analyzed": 0,
  "generic_posts_analyzed": 12,
  "top_subreddits": [{
    "name": "LocalLLaMA",
    "post_count": 25
  }],
  "collection_date": "2026-01-19T18:30:00",
  "data_size_mb": 2.5,
  "completed_stages": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "fallback_stages": null,
  "filtering_stats": {
    "reddit_urls_searched": 100,
    "reddit_urls_relevant": 54,
    "reddit_filtering_rate": 0.54,
    "twitter_urls_searched": 0,
    "twitter_urls_relevant": 0,
    "twitter_filtering_rate": 0,
    "total_urls_searched": 100,
    "total_urls_relevant": 54,
    "overall_filtering_rate": 0.54
  }
}
```

> **Note:** `generic_posts_analyzed` counts posts from non-Reddit/Twitter sources (Hacker News, YouTube, etc.) collected via the `SocialPost` generic model. These posts are stored in `SocialContentCollection.generic_posts` and flow through the same pipeline as Reddit/Twitter content.
```

---

## 14. Evidence & Supporting Data

### `evidence_appendix: object` (2 keys)

```json
{
  "top_reddit_threads": [{
    "post_id": "string",
    "title": "string",
    "subreddit": "LocalLLaMA",
    "score": 245,
    "num_comments": 89,
    "url": "string",
    "key_insight": "string",
    "platform": "reddit"
  }],
  "pain_point_quote_sources": [{
    "pain_point_title": "string",
    "quotes_with_sources": [{
      "quote": "string",
      "post_id": "string",
      "subreddit": "LocalLLaMA",
      "score": "45"
    }]
  }]
}
```

> **Multi-source notes:**
> - `top_reddit_threads[].platform` — `"reddit"` (default), `"hackernews"`, or `"youtube"`. Added for multi-source support.
> - `top_reddit_threads[].subreddit` — For Reddit: subreddit name. For HN: `"Hacker News"`. For YouTube: channel name. (Field name kept for backward compat, semantically a source label.)
> - `quotes_with_sources[].subreddit` — Same multi-source label convention. Python model uses `source_label` with `alias="subreddit"` for the JSON key.
```

### `content_categorization: object` (6 keys)

```json
{
  "executive_summary": "string",
  "theme_categories": [{
    "category_name": "string",
    "definition": "string",
    "frequency": "High",
    "mention_count": 25,
    "primary_user_segments": ["string"],
    "representative_quotes": ["string"]
  }],
  "user_segments": [{
    "segment_name": "string",
    "primary_concerns": ["string"],
    "mention_frequency": "High"
  }],
  "discussion_quality_assessment": "string",
  "overall_quality": "GOOD",
  "overall_quality_justification": "string"
}
```

---

## 15. Strategy & Planning

### `next_steps: array[string]`

Array of 7 recommended next steps.

### `alternative_solutions: array[object]`

```json
{
  "solution_name": "string",
  "summary": "string",
  "market_fit_score": 0.75,
  "technical_feasibility_score": 0.8,
  "competitive_advantage_score": 0.65,
  "seo_growth_potential_score": 0.7,
  "key_differentiator": "string",
  "best_suited_for": "string",
  "pivot_trigger": "string",
  "description": "string",
  "value_proposition": "string",
  "core_features": ["string"],
  "target_personas": ["string"],
  "technical_approach": "string",
  "novelty_score": 0.6,
  "solo_dev_feasibility": "string",
  "top_competitors": ["string"],
  "market_gaps": ["string"],
  "competitive_intensity": "Medium",
  "estimated_development_time": "string",
  "estimated_cac_organic": 15,
  "pricing_model": null
}
```

### `solution_innovation_assessment: object`

```json
{
  "novelty_score": 0.7,
  "conventional_approach": "string",
  "innovation_angle": "string",
  "why_it_works": "string",
  "solo_dev_feasibility": 0.6
}
```

---

## 16. Timing & Transparency

### `refinement_highlights: object` (4 keys)

```json
{
  "top_strategic_insights": ["string"],
  "geographic_priority": "string",
  "feature_priority": "string",
  "category_pivot_recommendation": null
}
```

### `stage_timing_summary: object` (4 keys)

```json
{
  "total_duration_seconds": 1234.56,
  "stage_durations": {
    "stage_1": 10.5,
    "stage_5": 120.3,
    "stage_9": 300.2
  },
  "slowest_stage": "stage_9",
  "fastest_stage": "stage_1"
}
```

### `seo_calculation_transparency: object` (7 keys)

```json
{
  "baseline_seo_score": 0.75,
  "refined_seo_score": 0.78,
  "volume_multiplier": 1.1,
  "competition_modifier": 1.08,
  "tier1_multiplier": 1.15,
  "estimated_year1_pages": 500,
  "calculation_rationale": "string"
}
```

---

## 17. Type Reference

### Literal Types (Enums)

| Type | Values |
|------|--------|
| `Verdict` | `"Go"`, `"No-Go"`, `"Conditional"` |
| `RiskLevel` | `"Low"`, `"Medium"`, `"High"` |
| `Priority` | `"High"`, `"Medium"`, `"Low"` |
| `OpportunityLevel` | `"high"`, `"medium"`, `"low"` |
| `TrendDirection` | `"Growing"`, `"Stable"`, `"Declining"` |
| `MarketMaturity` | `"Emerging"`, `"Growth"`, `"Mature"` |
| `LongevityVerdict` | `"Sustainable"`, `"Risky"`, `"Fad"` |
| `TimingRecommendation` | `"Enter Now"`, `"Monitor & Wait"`, `"Missed Window"` |
| `CompetitorType` | `"DIRECT"`, `"PARTIAL"`, `"INDIRECT"` |
| `PricingModel` | `"Freemium"`, `"Freemium-Lite"`, `"Subscription"`, `"Hybrid"`, `"One-time"`, `"Usage-Based"`, `"Ad-Supported-Free"`, `"Affiliate-Only"` |
| `MonetizationModel` | `"Ad-Supported"`, `"Affiliate"`, `"Hybrid-Traffic"`, `"Lead-Gen"` |
| `DataQualityTier` | `"EXCELLENT"`, `"GOOD"`, `"MINIMAL"`, `"INSUFFICIENT"` |
| `PainPointQualityTier` | `"GOLD"`, `"SILVER"`, `"BRONZE"`, `"INSUFFICIENT"` — measures research evidence quality (source count, subreddit diversity, quote density, pain point count), not niche attractiveness |
| `OverallDataQuality` | `"HIGH"`, `"MEDIUM"`, `"LOW"` |
| `IntegrationComplexity` | `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"LOW-MEDIUM"`, `"MEDIUM-HIGH"` |
| `SourcePriority` | `"HIGH"`, `"MEDIUM"`, `"LOW"` |

### Score Ranges

| Score Type | Range | Description |
|------------|-------|-------------|
| `severity_score` | 0.0 - 1.0 | Higher = more severe pain |
| `willingness_to_pay` | 0.0 - 1.0 | Higher = more willing to pay |
| `market_fit_score` | 0.0 - 1.0 | Higher = better market fit |
| `technical_feasibility_score` | 0.0 - 1.0 | Higher = more feasible |
| `competitive_advantage_score` | 0.0 - 1.0 | Higher = stronger advantage |
| `seo_scalability_score` | 0.0 - 1.0 | Higher = better SEO opportunity |
| `momentum_score` | 0.0 - 1.0 | 0=declining, 0.5=stable, 1=strong growth |
| `confidence_score` | 0.0 - 1.0 | Higher = more confident |
| `novelty_score` | 0.0 - 1.0 | Higher = more novel |
| `obviousness_score` | 0.0 - 1.0 | **Lower = more original** (independent novelty critic). Shown as Originality = 1 − this |
| `solo_dev_feasibility` | 0.0 - 1.0 | Higher = easier for solo dev |
| `relevance_score` | 0.0 - 1.0 | Higher = more relevant |
| `avg_competition` | 0 - 100 | Lower = less competitive |
| `keyword_diversity_score` | 0.0 - 1.0 | Higher = more diverse |
| `market_saturation_score` | 0.0 - 1.0 | 0=blue ocean, 1=saturated |
| `opportunity_score` | varies | Higher = better opportunity (keyword-specific) |

---

## Complete Top-Level Field List (54 Fields)

| # | Field | Type |
|---|-------|------|
| 1 | `niche` | `string` |
| 2 | `executive_summary` | `string` |
| 3 | `executive_dashboard` | `object` |
| 4 | `go_to_market_blueprint` | `object` |
| 5 | `market_analytics` | `object` |
| 6 | `seo_analytics` | `object` |
| 7 | `competitive_analytics` | `object` |
| 8 | `pain_point_analytics` | `object` |
| 9 | `data_quality_summary` | `object` |
| 10 | `selected_solution_name` | `string` |
| 11 | `selection_rationale` | `string` |
| 12 | `recommended_focus` | `string` |
| 14 | `selected_solution_details` | `object` |
| 15 | `solution_user_journey` | `string` |
| 16 | `solution_implementation_overview` | `string` |
| 17 | `mvp_scope_definition` | `string` |
| 18 | `site_structure` | `object` |
| 19 | `user_flows` | `object` |
| 20 | `pricing_strategy` | `object` |
| 21 | `traffic_monetization` | `object` |
| 22 | `estimated_cac_breakdown` | `string` |
| 23 | `pain_points_summary` | `string` |
| 24 | `detailed_pain_points` | `array` |
| 25 | `recommended_solutions` | `array` |
| 26 | `solutions_summary` | `string` |
| 27 | `competitive_summary` | `string` |
| 28 | `competitive_analysis` | `object` |
| 29 | `competitor_profiles` | `array` |
| 30 | `overall_competitive_insights` | `string` |
| 31 | `competitive_landscape_matrix` | `object` |
| 32 | `market_validation` | `string` |
| 33 | `market_sizing` | `object` |
| 34 | `trend_longevity` | `object` |
| 35 | `acquisition_strategy_summary` | `string` |
| 36 | `keyword_validation_overview` | `string` |
| 37 | `solution_keyword_comparison` | `string` |
| 38 | `content_strategy_preview` | `string` |
| 39 | `seo_strategy_report` | `object` |
| 40 | `niche_context` | `object` |
| 41 | `audience_mapping` | `object` |
| 42 | `data_sourcing_recommendations` | `string` |
| 43 | `data_source_research_full` | `object` |
| 44 | `data_infrastructure_roadmap` | `object` |
| 45 | `research_metadata` | `object` |
| 46 | `evidence_appendix` | `object` |
| 47 | `content_categorization` | `object` |
| 48 | `next_steps` | `array` |
| 49 | `alternative_solutions` | `array` |
| 50 | `solution_innovation_assessment` | `object` |
| 51 | `refinement_highlights` | `object` |
| 52 | `stage_timing_summary` | `object` |
| 53 | `seo_calculation_transparency` | `object` |
| 54 | `generated_at` | `string` |

---

## Version History

- **v2.5** - Removed dead fields
  - Removed `pdf_path` from `FinalReport` (always null, no PDF generation exists)
  - Removed `source_engagement_metrics` from pain points (always empty)
  - Removed `rate_limits` and `fallback_for` from `DataSource` (always null)
  - Updated Complete Top-Level Field List from 55 to 54 fields

- **v2.4** - Restored tier strategy fields
  - Updated `seo_strategy_report` to 21 keys
  - Restored `tier_0_strategy`, `tier_1_quick_win_strategy`, `tier_2_strategy` (used in frontend)
  - Updated source of truth to `output/final_report_20260127_003149.json`

- **v2.3** - Simplified SEO Strategy Report structure
  - Reduced `seo_strategy_report` from 31 keys to 21 keys (originally said 19, corrected in v2.4)
  - Removed `keyword_driven_site_architecture` (overlapped with `keyword_based_page_types`)
  - Removed Task 5/6 implementation guide models (`universal_seo_elements`, `page_type_implementations`, `schema_markup_strategy`)
    - Technical SEO implementation now in `technical_seo_recommendations` markdown field
  - Removed duplicate planning fields (`long_term_strategy`, `expected_timeline`, `competitive_advantages`, `critical_success_factors`)
  - Added `GeographicKeywordGroup` documentation for tier_3 geographic keywords
  - Updated `KeywordBasedPageType` with current field structure

- **v2.2** - Added LLM-generated Site Structure and User Flows (Stage 10.5)
  - Added `site_structure` field: LLM-generated site architecture with sections, pages, URLs, and MVP priorities
    - `SiteStructure`: overview, sections, page counts, tech stack recommendation
    - `SiteSection`: section_name, description, pages
    - `SitePage`: page_name, url_pattern, page_type (static/programmatic/dynamic), purpose, estimated_count, priority (P0/P1/P2)
  - Added `user_flows` field: LLM-generated user journeys for target personas
    - `UserFlowsSection`: flows array, key_insight
    - `UserFlow`: flow_name, persona, goal, entry_point, steps, conversion_point, success_metric
    - `UserFlowStep`: step_number, action, page, system_response
  - Updated Complete Top-Level Field List from 52 to 55 fields
  - New fields generated by TechnicalBlueprintCrew (CrewAI) during report generation

- **v2.1** - Expanded pricing strategy diversity
  - Added 4 new pricing models: `Freemium-Lite`, `Usage-Based`, `Ad-Supported-Free`, `Affiliate-Only`
  - Made tier price fields optional (`null` for ad/affiliate models)
  - Added ad/affiliate revenue fields: `estimated_monthly_ad_revenue`, `estimated_monthly_affiliate_revenue`, `estimated_cpm_rate`, `recommended_ad_networks`
  - Added pricing model selection guidance table
  - Updated `pricing_strategy` field count from 17 to 21 keys
  - Added Ad/Affiliate Models JSON example

- **v2.0** - Complete rewrite grounded exclusively on actual JSON report data
  - Removed all TypeScript/frontend references
  - Documented all 52+ top-level fields with accurate types
  - Added comprehensive nested structure documentation
  - Included actual JSON examples from report files
  - Added complete type reference with enum values and score ranges
