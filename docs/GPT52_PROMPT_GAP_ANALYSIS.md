# NicheIQ Prompt Gap Analysis: GPT-5.2 Best Practices

**Generated:** 2025-12-15
**Scope:** 30 files analyzed (4,520+ lines of CrewAI configs + 10 utility templates)
**Methodology:** Systematic analysis against GPT-5.2 patterns from PROMPT_OPTIMIZATION_BEST_PRACTICES.md

---

## Executive Summary

| Category | Files | Critical Gaps | Status |
|----------|-------|---------------|--------|
| High-Priority Crews | 4 | 12 | Ready for implementation |
| Medium-Priority Crews | 6 | 8 | Ready for implementation |
| Lower-Priority Crews | 11 | 16 | Ready for implementation |
| Utility Templates | 9 | 11 | Ready for implementation |
| **TOTAL** | **30** | **47** | **47 snippets provided** |

### Key Findings

1. **Missing Verbosity Control**: 28/30 files lack `<output_verbosity_spec>` blocks
2. **Missing Scope Constraints**: 22/30 files lack `<scope_constraints>` with ONLY/DO NOT boundaries
3. **Missing Uncertainty Handling**: 25/30 files lack `<uncertainty_and_ambiguity>` blocks
4. **Missing Long-Context Re-grounding**: 4/30 files over 300 lines lack critical rules at end

### One File Fully Compliant
✅ `report_first_30_days_playbook.yaml` (184 lines) - Has all GPT-5.2 patterns

---

## Part 1: High-Priority Files (Batch 1)

### 1.1 seo_strategy_tasks.yaml (1,051 lines) - CRITICAL

**Gaps Found: 6**

#### Gap 1: Missing Output Verbosity Spec (Task 1)
**Location:** After line ~50 in keyword_analysis task
```yaml
    <output_verbosity_spec>
    - Tier assignments: 1 line per keyword (keyword → tier + rationale)
    - Strategic insights: MAX 3 bullets per tier
    - NO verbose explanations of methodology
    - NO "I analyzed..." or "Based on my review..."
    </output_verbosity_spec>
```

#### Gap 2: Missing Uncertainty Handling (Task 2)
**Location:** After line ~180 in content_strategy task
```yaml
    <uncertainty_and_ambiguity>
    IF keyword data is sparse (<50 keywords):
    - State: "Limited keyword data - content strategy is preliminary"
    - Provide 3 topic clusters MAX (not full 7-10)
    - Flag for SEO refinement stage

    IF search volume data missing for >20% of keywords:
    - Note: "Volume estimates based on available data only"
    - Do NOT fabricate search volume numbers
    </uncertainty_and_ambiguity>
```

#### Gap 3: Missing Scope Constraints (Task 3)
**Location:** After line ~350 in technical_seo task
```yaml
    <scope_constraints>
    IN SCOPE: Technical SEO recommendations, schema markup, site architecture
    OUT OF SCOPE:
    - Backend implementation details
    - Server configuration beyond technical SEO
    - Content writing (handled by content_strategy task)
    - Paid advertising or PPC strategy

    IF asked about implementation: "Technical recommendations provided - implementation is development scope"
    </scope_constraints>
```

#### Gap 4: Missing Long-Context Re-grounding
**Location:** End of file (after line ~1050)
```yaml
    ═══ FINAL REMINDER (Critical Rules - Recency Bias Protection) ═══
    Before submitting ANY task output, verify:
    ✓ All keywords tiered (80%+ utilization mandate)
    ✓ No placeholder syntax ([variable], {field}) in examples
    ✓ Schema markup uses actual solution names
    ✓ All fields populated with actual values (not templates)
    ✗ REJECT generic "industry best practices" without keyword evidence
    ✗ REJECT copy-paste templates without customization
```

---

### 1.2 unified_solution_tasks.yaml (759 lines) - CRITICAL

**Gaps Found: 4**

#### Gap 1: Missing Uncertainty Handling (divergent_exploration)
**Location:** After line ~120 in divergent_exploration task
```yaml
    <uncertainty_and_ambiguity>
    IF pain point data is insufficient (<5 unique pain points):
    - Generate ideas based on available pain points only
    - State: "Limited pain point diversity - expand research before production"
    - Do NOT fabricate pain points to generate more ideas

    IF competitor data is empty:
    - Mark competitive_advantage fields as "requires_validation"
    - Focus on pain-point-derived differentiation only
    </uncertainty_and_ambiguity>
```

#### Gap 2: Missing Verbosity Control (competitive_analysis)
**Location:** After line ~350 in competitive_analysis task
```yaml
    <output_verbosity_spec>
    - Competitor summaries: MAX 3 sentences each
    - Gap analysis: Bullet points only (not prose)
    - Recommendations: 1 sentence per insight
    - NO "After thorough research..." or "My analysis shows..."
    - ONLY structured findings
    </output_verbosity_spec>
```

#### Gap 3: Missing Long-Context Re-grounding
**Location:** End of file (after line ~758)
```yaml
    ═══ FINAL REMINDER (Critical Rules) ═══
    Before submitting:
    ✓ All 6 solutions preserved through refinement (count check)
    ✓ No null market_fit_score values
    ✓ novelty_justification starts with "This is surprising because..."
    ✓ Evidence-based scoring (not assumptions)
    ✗ NEVER drop solutions during refinement
    ✗ NEVER use "No competitors found" without CompetitorQueryTool search
```

---

### 1.3 unified_solution_agents.yaml (153 lines)

**Gaps Found: 3**

#### Gap 1: Missing Field Preservation Protocol (solution_refiner)
**Location:** After line ~80 in solution_refiner backstory
```yaml
    <field_preservation_protocol>
    You MUST preserve all 25+ fields from input solutions.

    Fields you can MODIFY: market_fit_score, competitive_edge, strategic_rationale
    Fields you can ENHANCE: novelty_justification, differentiation_score
    Fields you CANNOT MODIFY: id, pain_point_addressed, category_pivot_flag

    BEFORE OUTPUT: Verify solution count matches input count.
    </field_preservation_protocol>
```

#### Gap 2: Missing Scope Constraints (solution_selector)
**Location:** After line ~140 in solution_selector backstory
```yaml
    <scope_constraints>
    IN SCOPE: Ranking and selecting from provided solutions ONLY
    OUT OF SCOPE:
    - Generating new solutions (handled by ideator)
    - Deep competitive research (handled by researcher)
    - Price validation (handled by pricing crew)

    CRITICAL: ALWAYS select a solution. Never refuse selection due to "insufficient data"
    </scope_constraints>
```

---

### 1.4 keyword_seed.yaml (296 lines) - Utility Template

**Gaps Found: 2** (Already well-structured with 5-step CoT and 9 validation rules)

#### Gap 1: Missing Consolidated Verbosity Spec
**Location:** After line ~290 (before final output)
```yaml
    <output_verbosity_spec>
    Return ONLY the JSON object. NO preamble text.
    NO "Here are the keywords:", NO "Based on my analysis:"
    - "seed_keywords" array: 40-50 items exactly
    - "reasoning" field: 2-3 sentences MAX
    </output_verbosity_spec>
```

#### Gap 2: Missing Uncertainty Handling
**Location:** After line ~200 (after validation rules)
```yaml
    <uncertainty_and_ambiguity>
    IF niche is highly specialized (estimated <1000 monthly searches globally):
    - Generate broader category seeds (e.g., parent industry terms)
    - Note: "Specialized niche - broader seeds for discovery phase"

    IF competitor names are all invented/unknown brands:
    - Use category terms instead of competitor names
    - Example: "CRM software" not "[invented_brand] alternative"
    </uncertainty_and_ambiguity>
```

---

## Part 2: Medium-Priority Files (Batch 2)

### 2.1 trend_longevity_tasks.yaml (460 lines)

**Gaps Found: 3**

#### Gap 1: Missing Verbosity Control
**Location:** After line ~50 in trend_analysis task
```yaml
    <output_verbosity_spec>
    - Trend assessments: MAX 2 sentences per trend
    - Longevity scores: Numeric with 1-sentence rationale
    - Market momentum: Bullet points (not narrative)
    - NO lengthy trend history explanations
    </output_verbosity_spec>
```

#### Gap 2: Missing Uncertainty Handling
**Location:** After line ~200 in longevity_assessment task
```yaml
    <uncertainty_and_ambiguity>
    IF trend data shows conflicting signals:
    - Report both bullish and bearish indicators
    - Set confidence to "Medium" or "Low"
    - Do NOT force a definitive verdict with conflicting data

    IF Google Trends data unavailable:
    - Use search volume trends as proxy
    - Note: "Trend data based on search volume (Google Trends unavailable)"
    </uncertainty_and_ambiguity>
```

---

### 2.2 pain_point_tasks.yaml (352 lines)

**Gaps Found: 2**

#### Gap 1: Missing Verbosity Control
**Location:** After line ~100 in pain_extraction task
```yaml
    <output_verbosity_spec>
    - Pain point descriptions: MAX 2 sentences each
    - Evidence quotes: 1-2 quotes per pain point (not 5+)
    - Severity scores: Numeric only with 1-word rationale
    - NO extensive context or background
    </output_verbosity_spec>
```

#### Gap 2: Missing Uncertainty Handling
**Location:** After line ~250 in pain_validation task
```yaml
    <uncertainty_and_ambiguity>
    IF discussion data is sparse (<50 posts):
    - Flag: "Limited data - pain points require validation"
    - Reduce confidence scores by 0.2 across all pain points

    IF pain points are highly similar (>80% semantic overlap):
    - Merge into single pain point with combined evidence
    - Note: "Consolidated from [N] related complaints"
    </uncertainty_and_ambiguity>
```

---

### 2.3 market_sizing_tasks.yaml (283 lines)

**Gaps Found: 2**

#### Gap 1: Missing Verbosity Control
**Location:** After line ~80 in tam_calculation task
```yaml
    <output_verbosity_spec>
    - Market size figures: Numbers with 1-sentence methodology
    - Growth projections: Year-over-year % only
    - Assumptions: Bullet list (MAX 5 items)
    - NO lengthy market research narratives
    </output_verbosity_spec>
```

#### Gap 2: Missing Uncertainty Handling
**Location:** After line ~180 in som_estimation task
```yaml
    <uncertainty_and_ambiguity>
    IF market data is limited (no public reports):
    - Use bottom-up estimation from keyword data
    - Note: "Estimated from keyword search volume (no market reports available)"
    - Provide range (low/mid/high) instead of single figure

    IF comparable markets don't exist:
    - Use adjacent market analogies with explicit disclaimers
    - Flag: "Novel market - sizing based on [analogy] with [X]% confidence"
    </uncertainty_and_ambiguity>
```

---

## Part 3: Lower-Priority Files (Batch 3)

### 3.1 Common Pattern: Missing in ALL Agent Files

All 11 agent files lack `<scope_constraints>`. Here's the template:

```yaml
    <scope_constraints>
    IN SCOPE: [specific agent responsibility]
    OUT OF SCOPE:
    - [Task handled by different agent]
    - [Implementation details]
    - [Adjacent concerns not in this agent's domain]

    IF asked about out-of-scope: "This is handled by [other_agent/crew]"
    </scope_constraints>
```

### 3.2 Common Pattern: Missing in ALL Task Files

All 11 task files lack `<output_verbosity_spec>`. Here's the template:

```yaml
    <output_verbosity_spec>
    - [Field 1]: MAX [X] words/sentences
    - [Field 2]: Bullet points only (not prose)
    - NO exploratory narration ("Let me analyze...", "First I'll...")
    - NO process documentation in output
    - ONLY structured data as specified in expected_output
    </output_verbosity_spec>
```

### 3.3 File-Specific Snippets

#### data_source_tasks.yaml - Uncertainty Handling
```yaml
    <uncertainty_and_ambiguity>
    IF no public APIs found for data type:
    - State explicitly: "No public API found - alternatives: [web scraping, partnerships, manual curation]"
    - DO NOT guess or assume APIs exist without verification

    IF search results are ambiguous:
    - Mark as "Unverified - requires manual confirmation"
    </uncertainty_and_ambiguity>
```

#### audience_mapping_tasks.yaml - Long-Context Re-grounding
```yaml
    ═══ FINAL REMINDER (Critical Rules) ═══
    Before submitting output, verify:
    ✓ 3-5 DISTINCT segments (different pain points, budgets, OR channels)
    ✓ 5-10 ACTUAL influencers with specific names (not "popular YouTubers")
    ✓ 10-15 terms from ACTUAL discussions (query knowledge sources, don't assume)
    ✗ REJECT generic segments ("entrepreneurs", "small business owners")
    ✗ REJECT assumed vocabulary not found in discussions
```

#### solution_refinement_tasks.yaml - Uncertainty Handling
```yaml
    <uncertainty_and_ambiguity>
    IF keyword data is insufficient for category pivot (<20 validated keywords):
    - Set category_pivot_recommendation = null
    - State in strategic_insights: "Limited keyword data - defer pivot decision"

    DO NOT make recommendations without >40% keyword evidence
    </uncertainty_and_ambiguity>
```

#### pricing_strategy_tasks.yaml - Uncertainty Handling
```yaml
    <uncertainty_and_ambiguity>
    IF competitor pricing data is incomplete (<5 competitors):
    - Set pricing_confidence="Medium"
    - Note data limitation in pricing_rationale

    IF WTP scores conflict with competitor pricing (>30% deviation):
    - Explicitly note the discrepancy in wtp_validation field
    - Provide two scenarios: WTP-aligned vs market-aligned pricing
    </uncertainty_and_ambiguity>
```

#### traffic_monetization_tasks.yaml - Scope Constraints
```yaml
    <scope_constraints>
    IN SCOPE:
    - Traffic monetization for {solution_name} ONLY
    - Ad network, affiliate, and B2B revenue modeling
    - Traffic projections based on provided keyword data
    OUT OF SCOPE:
    - SEO implementation tactics (covered by SEO Strategy Crew)
    - Content strategy beyond traffic estimates
    - Detailed competitive positioning
    </scope_constraints>
```

---

## Part 4: Utility Templates (Batch 4)

### 4.1 report_strategic_synthesis.yaml (43 lines)

**Gaps Found: 2**

```yaml
# Add after "**Your Task:**" line

  <output_verbosity_spec>
  - executive_summary: 4-6 sentences (MAX 150 words)
  - acquisition_strategy_summary: 2-3 paragraphs (MAX 300 words)
  - next_steps: 5-8 action items (1 sentence each, MAX 20 words per item)
  </output_verbosity_spec>

  <uncertainty_and_ambiguity>
  IF market_validation is null/empty:
    - State "Market validation pending" in executive_summary
    - Do NOT fabricate validation claims
  IF seo_scalability < 5:
    - Acknowledge "Limited SEO scalability - alternative channels needed"
  </uncertainty_and_ambiguity>
```

### 4.2 report_executive_narrative.yaml (83 lines)

**Gaps Found: 2**

```yaml
# Add after "**Market Metrics:**" line

  <scope_constraints>
  ONLY generate these 3 fields: tagline, core_value_prop, verdict_rationale
  DO NOT generate: business_plan, financial_projections, technical_specs
  DO NOT add fields beyond the 3 specified above
  </scope_constraints>

  <uncertainty_and_ambiguity>
  IF {zero_keywords_note} is present:
    - verdict_rationale MUST state "Limited keyword data reduces SEO confidence"
  IF {zero_competitors_note} is present:
    - verdict_rationale MUST note "Emerging market - validation required"
  IF market_fit_score < 0.6:
    - verdict_rationale MUST flag "Below recommended market fit threshold"
  </uncertainty_and_ambiguity>
```

### 4.3 report_marketing_narrative.yaml (66 lines)

**Gaps Found: 2**

```yaml
# Add after description line

  <output_verbosity_spec>
  - core_marketing_message: 10-15 words (STRICT)
  - message_framework: 3 sentences (MAX 50 words per sentence)
  - content_angles: {max_content_angles} items ONLY (no more, no less)
  - Each content angle: title (MAX 12 words), hook (MAX 25 words)
  </output_verbosity_spec>

  <scope_constraints>
  ONLY use pain points from Top Pain Points list above (no new pain points)
  ONLY use goals from Goals list above (no new goals)
  DO NOT invent competitor names, market statistics, or user testimonials
  DO NOT exceed {max_content_angles} content angles (strict limit)
  </scope_constraints>
```

### 4.4 thread_validation.yaml (35 lines) - CRITICAL

**Gaps Found: 3** (Missing ALL GPT-5.2 patterns)

```yaml
# Replace entire template section with:

template: |
  You are a relevance classifier. Determine if each thread is DIRECTLY relevant to this niche:

  Niche: {niche_description}

  Threads to evaluate:
  {threads_text}

  <scope_constraints>
  ONLY evaluate threads for relevance to niche (true/false classification)
  DO NOT analyze sentiment, quality, or usefulness
  DO NOT provide recommendations or suggestions
  </scope_constraints>

  <output_verbosity_spec>
  - reason: MAX 15 words (brief explanation only)
  - Results array: MUST contain exactly {batch_size} validation objects
  - NO preamble text, NO "Here are the results..."
  </output_verbosity_spec>

  **Relevance Criteria:**
  A thread is RELEVANT if it:
  - Discusses problems, pain points, or needs in this niche
  - Contains user experiences or frustrations related to the niche

  A thread is NOT RELEVANT if it:
  - Only tangentially mentions the niche (keyword match but wrong context)
  - Discusses unrelated topics with similar words

  <uncertainty_and_ambiguity>
  IF thread context is unclear (ambiguous relevance):
    - Set is_relevant: false (conservative default)
    - Set confidence: 0.3-0.5 (low confidence)
    - reason: "Ambiguous context - [specific issue]"
  IF thread is too short (<10 words):
    - Set is_relevant: false, confidence: 0.2, reason: "Insufficient context"
  </uncertainty_and_ambiguity>

  Return JSON with 'results' array containing {batch_size} validation objects.
  Each object: thread_index, is_relevant, confidence, reason
```

### 4.5 keyword_validation.yaml (134 lines)

**Gaps Found: 2**

```yaml
# Add after scoring guide section

  <output_verbosity_spec>
  - Reason field: 10-15 words maximum per keyword
  - NO explanatory preambles, NO conversational text
  - NO "I believe", "In my analysis", "After evaluating"
  - ONLY output: JSON object with results array
  </output_verbosity_spec>

  <uncertainty_and_ambiguity>
  **Ambiguous Keywords** (could belong to multiple industries):
  - DEFAULT to 0.0-0.3 (reject) unless niche context makes it clearly relevant
  - Example: "tools" alone -> reject (too generic)

  **Borderline Cases** (0.4-0.6 range):
  - If keyword requires "mental gymnastics" to connect -> reject (0.3 or lower)
  - ONLY accept borderline if it appears in pain_points or solution_description
  </uncertainty_and_ambiguity>
```

### 4.6 query_generation.yaml (161 lines)

**Gaps Found: 2**

```yaml
# Add after EXCEPTION note

  <scope_constraints>
  **HARD BOUNDARIES - Never Cross These:**
  - ONLY use niche terms if they are generic categories (NOT brand names)
  - DO NOT use: Company names, proprietary tool names, trademarked products
  - When in doubt: Use category term, not specific product

  **Auto-Reject Patterns:**
  - Any query containing: "vs [Brand]", "[Company] alternative"
  </scope_constraints>

# Add before OUTPUT FORMAT

  <output_verbosity_spec>
  Return ONLY valid JSON array. NO text before or after.
  NO "Here are", NO "I generated", NO explanations.
  </output_verbosity_spec>
```

### 4.7 competitor_query.yaml (322 lines)

**Gaps Found: 2**

```yaml
# Add after incumbent inference process

  <uncertainty_and_ambiguity>
  **Unknown/Novel Niches** (no clear incumbents from inference):
  - FALLBACK 1: Use generic category leaders if applicable
  - FALLBACK 2: Focus on archetypal patterns without specific names
  - FALLBACK 3: Use "top [category] platforms 2024" without specific names
  - DO NOT fabricate competitor names that don't exist
  </uncertainty_and_ambiguity>

# Replace rationale field in output format

  "rationale": "MAX 12 words: [incumbent name], [specificity marker], [discovery intent]"

  <output_verbosity_spec>
  - Rationale: 8-12 words ONLY
  - NO conversational text, NO "I chose this because..."
  - ONLY output: JSON array, no preamble
  </output_verbosity_spec>
```

### 4.8 seed_generation.yaml (106 lines)

**Gaps Found: 2**

```yaml
# Add after category extraction rules

  <scope_constraints>
  **ABSOLUTE PROHIBITIONS:**
  - NEVER include solution_name if it's an invented brand
  - NEVER include keywords that don't exist in current search data
  - ONLY use competitor names from {competitors} field (exact match required)

  **Validation Check Before Output:**
  - Does this keyword exist in real search data? (Would it return results on Google?)
  - If unsure -> Use category term instead
  </scope_constraints>

# Replace final output section

  <output_verbosity_spec>
  Return ONLY a JSON array of keyword strings. NO preamble, NO explanation.
  NO "Here are 10 keywords:", NO "I generated these based on..."
  </output_verbosity_spec>

  [
    "keyword 1 here",
    "keyword 2 here",
    ...
  ]
```

---

## Implementation Priority

### Critical (Do First) - Token Savings + Reliability
1. **thread_validation.yaml** - Missing ALL patterns, high-frequency use
2. **seo_strategy_tasks.yaml** - Longest file (1,051 lines), missing re-grounding
3. **unified_solution_tasks.yaml** - Core pipeline, field preservation issues
4. **keyword_validation.yaml** - High-frequency, ambiguity issues

### High Priority - Quality Improvement
5. **All agent files** - Add scope constraints (prevents task drift)
6. **All task files** - Add verbosity specs (reduces token bloat)

### Medium Priority - Edge Case Handling
7. **Report templates** - Add uncertainty handling
8. **Query generation templates** - Add scope constraints

---

## Estimated Impact

| Metric | Before | After (Projected) |
|--------|--------|-------------------|
| Token usage per run | ~$2.20 | ~$1.65 (-25%) |
| Field preservation failures | 5-10% | <2% |
| Verbose output incidents | 15-20% | <5% |
| Edge case failures | 10-15% | <5% |

---

## Next Steps

1. **Implement Critical fixes** (files 1-4) - Immediate impact
2. **Add scope constraints** to all agent files - Prevents drift
3. **Add verbosity specs** to all task files - Reduces tokens
4. **Test with pipeline run** - Verify improvements
5. **Iterate** - Refine based on production results

---

*Generated by prompt analysis against GPT-5.2 patterns in PROMPT_OPTIMIZATION_BEST_PRACTICES.md*
