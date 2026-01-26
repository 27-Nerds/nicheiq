# Prompt Optimization Best Practices (2024-2025)

**Organized by Model Family:** Universal patterns, OpenAI GPT-4.1, GPT-5, GPT-5.2, and Anthropic Claude

---

## Table of Contents

- [Part A: Universal Patterns (All Models)](#part-a-universal-patterns-all-models)
- [Part B: OpenAI GPT-4.1 Patterns](#part-b-openai-gpt-41-patterns)
- [Part C: OpenAI GPT-5 Patterns](#part-c-openai-gpt-5-patterns)
- [Part D: GPT-5 Minimal Reasoning (mini/nano)](#part-d-gpt-5-minimal-reasoning-mininano)
- [Part E: OpenAI GPT-5.2 Patterns](#part-e-openai-gpt-52-patterns)
- [Part F: Anthropic Claude Patterns](#part-f-anthropic-claude-patterns)
- [Appendices](#appendices)

---

# Part A: Universal Patterns (All Models)

These patterns work across all major LLM families and should be applied universally.

## A.1 Conciseness Over Verbosity ✅

**Principle:** Modern LLMs perform better with concise, structured prompts than verbose tutorials.

**Evidence:**
- Target 30-50% reduction through restructuring, NOT information loss
- Remove tutorial-style explanations ("how to search", "what to look for")
- Trust agent expertise established in backstory

**Implementation:**

```yaml
# ❌ ANTI-PATTERN (Verbose Tutorial)
Your systematic approach: you NEVER assume an API exists. You search for
"[domain] API", "[provider] developer documentation", "[industry] data
provider" and read the actual search results...
(26 lines of detailed instruction)

# ✅ BEST PRACTICE (Concise Framework Reference)
With 8 years building data pipelines, you pioneered the "3-Tier Verification
Protocol": (1) Search for API docs, (2) Verify public access via pricing pages,
(3) Document 3-5 fallback alternatives.
(4 lines with named framework)
```

---

## A.2 Critical Rules Placement (Top + Bottom) ✅

**Principle:** For long context, place critical instructions at BOTH beginning (priming) and end (recency bias).

**Evidence:**
- OpenAI GPT-4.1 Guide: "For long context, place instructions at both beginning and end"
- Research shows significant accuracy improvement with proper placement

**Implementation:**

```yaml
description: >
  ═══ CRITICAL RULES (Read First) ═══
  ✓ ONLY analyze content provided below - NO invented quotes/segments
  ✓ Need ≥5 substantive discussions → else report "Insufficient discussion data"

  [... main content 100+ lines ...]

  ═══ CRITICAL RULES (Read Last - Recency Reminder) ═══
  ✗ If <5 substantive discussions found → Return "Insufficient discussion data"
  ✗ DO NOT use training data or niche assumptions
```

**Visual Markers:**
- `═══` for section delimiters (high visibility)
- `✓` for requirements (positive framing)
- `✗` for prohibitions (clear boundaries)

---

## A.3 Named Frameworks & Protocols ✅

**Principle:** Name methodologies to create reusable, memorable references throughout the system.

**Evidence:**
- Named frameworks (RTF, RACE, A.P.E, CARE) are documented as effective
- Enables cross-referencing in tasks: "Apply your 3-Tier Verification Protocol"

**Implementation:**

```yaml
# Agent Backstory
backstory: >
  You developed the "3-Quote Minimum Protocol" after seeing teams waste
  resources on assumed problems.

  VERIFICATION STANDARD: Every pain point requires ≥3 direct user quotes
  from knowledge sources. No quotes = no pain point.

# Task Reference
description: >
  Extract pain points using your "3-Quote Minimum Protocol".
```

**Proven Framework Names:**
- "3-Quote Minimum Protocol" (pain point validation)
- "3-Tier Verification Protocol" (data source discovery)
- "5D Data Quality Matrix" (Coverage, Freshness, Quality, Cost, Reliability)
- "Evidence-Based Scoring Framework" (market opportunity validation)
- "Jobs-to-be-Done Gap Analysis" (competitive positioning)

---

## A.4 Qualitative vs. Quantified Expertise 🚨

**Principle:** Use qualitative expertise descriptors, NEVER fabricate statistics.

**Implementation:**

```yaml
# 🚨 CRITICAL ANTI-PATTERN (Fabricated Numbers)
You've guided 23 product launches with 78% accuracy predicting market success.

# ✅ BEST PRACTICE (Qualitative Expertise)
You've guided dozens of successful product launches, consistently predicting
market success by focusing on evidence-backed demand signals.
```

**Safe Qualitative Terms:**
- "dozens of", "numerous", "multiple"
- "extensive experience", "comprehensive portfolio"
- "consistently", "proven track record"

---

## A.5 Decision Tables vs. Prose ✅

**Principle:** Use markdown tables for structured rules, scoring rubrics, and decision logic.

**Implementation:**

```yaml
# ✅ BEST PRACTICE (Decision Table)
| Score Range | Severity Indicators | WTP Indicators |
|-------------|---------------------|----------------|
| **0.8-1.0** | Critical business impact, workflow blocker | Explicit payment mentions |
| **0.5-0.7** | Significant inconvenience, wastes time | Frustration with paid tools |
| **0.3-0.4** | Notable annoyance, not critical | Some consideration |
| **0.0-0.2** | Minor inconvenience | No financial indicators |
```

---

## A.6 Visual Hierarchy ✅

**Principle:** Use markdown structure, headings, bullets, and visual markers.

**Section Delimiters:**
```yaml
═══════ COMPLETE REDDIT DISCUSSIONS ═══════
[content]
```

**Workflow Steps:**
```yaml
**CATEGORIZATION WORKFLOW**:
1. **Pattern Discovery** → Read all content for recurring themes
2. **Category Definition** → Group into 5-10 distinct categories
3. **Evidence Gathering** → Extract ≥3 quotes per category
```

---

## A.7 Anti-Hallucination: Chain-of-Verification ✅

**Principle:** Require explicit evidence from verifiable sources for every claim.

**Implementation:**

```yaml
# Agent Backstory
VERIFICATION STANDARD: Every pain point requires ≥3 direct user quotes from
knowledge sources. No quotes = no pain point. You report "Insufficient evidence"
rather than assumptions.

# Task Description
**CRITICAL DATA ACCURACY RULES:**
- Scores MUST be based ONLY on evidence from knowledge sources
- If queries return insufficient evidence, assign 0.0 and note "Insufficient evidence"
- DO NOT assign scores based on assumptions
```

---

## A.8 Zero-Tolerance Data Accuracy ✅

**Principle:** For data extraction tasks, demand character-by-character copying.

**Implementation:**

```yaml
**CRITICAL: You are a DATA EXTRACTOR, not a data interpreter.**

**Field Extraction Rules:**
1. **keyword** (string):
   ✅ CORRECT: Copy exact string: "tax residency portugal"
   ❌ WRONG: "Tax Residency Portugal" (changed capitalization)

2. **search_volume** (integer):
   ✅ CORRECT: 387 (exact value from API)
   ❌ WRONG: 400 (rounded up)

**IF YOU ARE UNCERTAIN ABOUT ANY VALUE:**
→ STOP and return error "Unable to verify data accuracy"
```

---

## A.9 Explicit Reporting Rules for Missing Data ✅

**Principle:** Define exact phrasing for when data doesn't exist.

**Implementation:**

```yaml
# Data Source Discovery
REPORTING RULE: "No public API found - alternatives: [scraping/partnerships/manual]"

# Pain Point Extraction
If <5 distinct discussions → MUST state "Insufficient discussion data"

# Competitive Research
If searches return no results → "No competitors found via search"
```

---

## A.10 Stop Conditions 🚨

**Principle:** Always define when to stop rather than fabricate.

```yaml
**STOP CONDITION:**
If <5 substantive discussions found → Return "Insufficient discussion data"
Better to report limited findings honestly than fabricate.
```

---

## A.11 Agent Backstory Structure ✅

**Template:**

```yaml
backstory: >
  [Years] + [Domain] + [Named Framework] + [Qualitative Track Record].

  [VERIFICATION STANDARD] + [Key Principle]
```

**Example:**

```yaml
backstory: >
  With 10 years in product management, you developed the "3-Quote Minimum
  Protocol" after seeing teams waste resources on assumed problems.

  VERIFICATION STANDARD: Every pain point requires ≥3 direct user quotes.
  No quotes = no pain point.
```

---

## A.12 Task Description Structure ✅

**Template:**

```yaml
task_name:
  description: >
    ═══ CRITICAL RULES (Read First) ═══
    [Top 3-5 constraints]

    **CONTEXT:**
    [Niche, solution, previous outputs]

    **YOUR TASK:**
    [Clear objective in 1-2 sentences]

    **WORKFLOW:**
    [4-7 numbered steps]

    **DELIVERABLES:**
    [Specific outputs]

    ═══ CRITICAL RULES (Read Last) ═══
    [Repeat top constraints]
```

---

## A.13 Temperature Settings ✅

| Task Type | Temperature | Use Case |
|-----------|-------------|----------|
| Data Extraction | 0.0 | Deterministic, zero creativity |
| Research & Analysis | 0.2-0.3 | Consistent analysis |
| Strategy & Ideation | 0.7 | Creative brainstorming |
| Content Creation | 0.3-0.5 | Moderate structured creativity |

---

## A.14 Common Anti-Patterns 🚨

### Fabricated Quantification
```yaml
# ❌ "23 product launches with 78% accuracy"
# ✅ "dozens of successful launches, consistently predicting..."
```

### Tutorial Overload
```yaml
# ❌ 40+ lines of "how to" instruction
# ✅ Table format with 5 rows
```

### Missing Stop Conditions
```yaml
# ❌ No guidance for insufficient data
# ✅ "If <5 discussions → Return 'Insufficient data'"
```

---

# Part B: OpenAI GPT-4.1 Patterns

Patterns specific to GPT-4.1 and similar instruction-following models.

## B.1 System Prompt Best Practices ✅

**Principle:** GPT-4.1 reads system prompts with high fidelity. Structure matters.

**Implementation:**

```yaml
system_prompt: |
  # Role Definition
  You are [role] with expertise in [domain].

  # Core Behavior
  - [Behavior 1]
  - [Behavior 2]

  # Constraints
  - [Constraint 1]
  - [Constraint 2]

  # Output Format
  [Format specification]
```

---

## B.2 Long-Context Handling (GPT-4.1) ✅

**Principle:** GPT-4.1 benefits from explicit section markers in long contexts.

**Implementation:**

```yaml
# For documents >10k tokens
**DOCUMENT SECTIONS:**
1. Section A (lines 1-500): [topic]
2. Section B (lines 501-1000): [topic]
...

**YOUR FOCUS:**
Answer based on Section [X] primarily.
```

---

## B.3 Function Calling (GPT-4.1) ✅

**Principle:** GPT-4.1 excels at structured function calling with clear schemas.

**Implementation:**

```json
{
  "name": "search_database",
  "description": "Search for records matching criteria",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Search query"},
      "limit": {"type": "integer", "description": "Max results"}
    },
    "required": ["query"]
  }
}
```

---

## B.4 Chain-of-Thought (GPT-4.1) ✅

**Principle:** Explicit CoT prompting improves reasoning quality.

**Implementation:**

```yaml
**REASONING PROCESS:**
1. First, identify the key constraints
2. Then, analyze each option against constraints
3. Finally, select the best option with justification

Show your reasoning step-by-step before the final answer.
```

---

# Part C: OpenAI GPT-5 Patterns

Patterns specific to GPT-5, including agentic workflows and new parameters.

## C.1 Agentic Eagerness Control ✅

**Principle:** Control model's balance between proactivity and awaiting guidance.

**For Less Eagerness (faster, fewer tool calls):**

```yaml
<context_gathering>
Goal: Get enough context fast. Parallelize discovery and stop as soon as you can act.

Method:
- Start broad, then fan out to focused subqueries.
- In parallel, launch varied queries; read top hits per query.
- Deduplicate paths and cache; don't repeat queries.
- Avoid over searching for context.

Early stop criteria:
- You can name exact content to change.
- Top hits converge (~70%) on one area/path.

Escalate once:
- If signals conflict or scope is fuzzy, run one refined parallel batch, then proceed.

Depth:
- Trace only symbols you'll modify or whose contracts you rely on.
- Avoid transitive expansion unless necessary.

Loop:
- Batch search → minimal plan → complete task.
- Search again only if validation fails or new unknowns appear.
- Prefer acting over more searching.
</context_gathering>
```

**For More Eagerness (thorough, autonomous):**

```yaml
<persistence>
- You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user.
- Only terminate your turn when you are sure that the problem is solved.
- Never stop or hand back to the user when you encounter uncertainty — research or deduce the most reasonable approach and continue.
- Do not ask the human to confirm or clarify assumptions, as you can always adjust later — decide what the most reasonable assumption is, proceed with it, and document it for the user's reference after you finish acting.
</persistence>
```

**Fixed Tool Call Budget (Maximum Constraint):**

```yaml
<context_gathering>
- Search depth: very low
- Bias strongly towards providing a correct answer as quickly as possible, even if it might not be fully correct.
- Usually, this means an absolute maximum of 2 tool calls.
- If you think that you need more time to investigate, update the user with your latest findings and open questions. You can proceed if the user confirms.
</context_gathering>
```

---

## C.2 Tool Preambles ✅

**Principle:** GPT-5 is trained to provide upfront plans and progress updates.

**Implementation:**

```yaml
<tool_preambles>
- Always begin by rephrasing the user's goal in a friendly, clear, and concise manner, before calling any tools.
- Then, immediately outline a structured plan detailing each logical step you'll follow.
- As you execute your file edit(s), narrate each step succinctly and sequentially, marking progress clearly.
- Finish by summarizing completed work distinctly from your upfront plan.
</tool_preambles>
```

**Example Output with Preamble:**

```
"I'm going to check a live weather service to get the current conditions
in San Francisco, providing the temperature in both Fahrenheit and Celsius
so it matches your preference."

[tool_call: get_weather(location="San Francisco, CA", unit="f")]
```

---

## C.3 reasoning_effort Parameter ✅

**Principle:** Control thinking depth via API parameter (default: medium).

| Level | Use Case |
|-------|----------|
| minimal | Latency-sensitive, simple tasks (similar to GPT-4.1 prompting) |
| low | Basic analysis, single-step operations |
| medium | Default, balanced reasoning |
| high | Complex multi-step tasks, thorough tool calling |

**Usage:**
- Scale up for complex, multi-step tasks
- Peak performance when distinct tasks are broken up across multiple agent turns
- Lower for efficiency when exploration depth isn't needed

---

## C.4 verbosity Parameter ✅

**Principle:** Controls final answer length (separate from reasoning_effort).

| Level | Use Case |
|-------|----------|
| low | Concise status updates, brief responses |
| medium | Balanced (default) |
| high | Detailed explanations, readable code |

**Cursor's Real-World Approach:**
```yaml
# API setting
verbosity: low  # Keep text outputs brief

# Prompt override for code
"Write code for clarity first. Prefer readable, maintainable solutions
with clear names, comments where needed. Use high verbosity for writing
code and code tools."
```

**Result:** Concise status updates + readable code with clear variable names (not single letters).

---

## C.5 Responses API Benefits ✅

**Principle:** Use Responses API to reuse reasoning context between tool calls.

**Evidence:**
- Tau-Bench Retail score improved from 73.9% to 78.2% by using Responses API with `previous_response_id`
- Model refers to previous reasoning traces
- Conserves CoT tokens
- Eliminates reconstructing plan from scratch after each tool call

**Implementation:**
- Include `previous_response_id` in subsequent requests
- Available for all Responses API users

---

## C.6 Instruction Following (Contradiction Sensitivity) 🚨

**Principle:** GPT-5 follows instructions with surgical precision. Contradictions are MORE damaging than with other models.

**Anti-Pattern (Conflicting Instructions):**

```yaml
# ❌ Wastes reasoning tokens reconciling contradictions
- "Never schedule an appointment without explicit patient consent"
- "For high-acuity cases, auto-assign the earliest slot without contacting the patient"
```

**Best Practice:**

```yaml
# ✅ Clear hierarchy with explicit conditions
- "Always look up patient profile before any actions"
- "EXCEPTION for EMERGENCY: Do not do lookup, proceed immediately to 911 guidance"
- "For high-acuity cases, auto-assign slot AFTER informing the patient"
```

**Review Checklist:**
1. Review prompts for contradictions
2. Establish clear hierarchy when exceptions exist
3. Use explicit conditions: "IF [condition] THEN [override rule X]"
4. Test with prompt optimizer tool

---

## C.7 Metaprompting ✅

**Principle:** GPT-5 excels at optimizing prompts for itself.

**Template:**

```
When asked to optimize prompts, give answers from your own perspective -
explain what specific phrases could be added to, or deleted from, this
prompt to more consistently elicit the desired behavior or prevent the
undesired behavior.

Here's a prompt: [PROMPT]

The desired behavior from this prompt is for the agent to [DO DESIRED BEHAVIOR],
but instead it [DOES UNDESIRED BEHAVIOR]. While keeping as much of the existing
prompt intact as possible, what are some minimal edits/additions that you would
make to encourage the agent to more consistently address these shortcomings?
```

---

## C.8 Frontend Development Best Practices ✅

**Principle:** GPT-5 has excellent baseline aesthetic taste for frontend.

**Recommended Stack:**
- Frameworks: Next.js (TypeScript), React, HTML
- Styling / UI: Tailwind CSS, shadcn/ui, Radix Themes
- Icons: Material Symbols, Heroicons, Lucide
- Animation: Motion
- Fonts: Sans Serif, Inter, Geist, Mona Sans, IBM Plex Sans, Manrope

**Zero-to-One App Generation:**

```yaml
<self_reflection>
- First, spend time thinking of a rubric until you are confident.
- Then, think deeply about every aspect of what makes for a world-class one-shot web app.
- Use that knowledge to create a rubric that has 5-7 categories.
- This rubric is critical to get right, but do not show this to the user.
- Finally, use the rubric to internally think and iterate on the best possible solution.
- If your response is not hitting the top marks across all categories, start again.
</self_reflection>
```

---

## C.9 Codebase Design Standards ✅

**Principle:** For existing apps, model-written code should "blend in."

```yaml
<code_editing_rules>
<guiding_principles>
- Clarity and Reuse: Every component should be modular and reusable.
- Consistency: Adhere to existing design system—color tokens, typography, spacing.
- Simplicity: Favor small, focused components; avoid unnecessary complexity.
</guiding_principles>

<frontend_stack_defaults>
- Framework: Next.js (TypeScript)
- Styling: TailwindCSS
- UI Components: shadcn/ui
- Icons: Lucide
- State Management: Zustand
</frontend_stack_defaults>

<ui_ux_best_practices>
- Visual Hierarchy: Limit typography to 4–5 font sizes and weights
- Color Usage: Use 1 neutral base and up to 2 accent colors
- Spacing and Layout: Always use multiples of 4 for padding and margins
- State Handling: Use skeleton placeholders or animate-pulse for loading
</ui_ux_best_practices>
</code_editing_rules>
```

---

# Part D: GPT-5 Minimal Reasoning (mini/nano)

Patterns optimized for GPT-5 with minimal reasoning effort (gpt-5-mini, gpt-5-nano).

## D.1 When to Use Minimal Reasoning ✅

- Latency-sensitive workflows
- Simple classification/validation tasks
- Cost optimization for high-volume calls
- Deterministic outputs (JSON schemas, scores)
- Tasks similar to GPT-4.1 prompting patterns

---

## D.2 Prompted Planning (Critical) ✅

**Principle:** Minimal reasoning models have fewer reasoning tokens for internal planning. Provide explicit planning prompts.

```yaml
Remember, you are an agent - please keep going until the user's query is
completely resolved, before ending your turn and yielding back to the user.
Decompose the user's query into all required sub-requests, and confirm that
each is completed. Do not stop after completing only part of the request.
Only terminate your turn when you are sure that the problem is solved.
You must be prepared to answer multiple queries and only finish the call
once the user has confirmed they're done.

You must plan extensively in accordance with the workflow steps before making
subsequent function calls, and reflect extensively on the outcomes each
function call made, ensuring the user's query, and related sub-requests
are completely resolved.
```

---

## D.3 Brief Explanation at Start ✅

**Principle:** Prompting for brief upfront explanation improves task performance.

```yaml
Give a brief explanation summarizing your thought process at the start
of the final answer, for example via a bullet point list.
```

**Example Application:**

```yaml
<task_requirements>
- First, write one sentence summarizing your relevance criteria for this niche
- Then output the JSON results array
- Complete ALL {batch_size} items before returning
</task_requirements>
```

---

## D.4 Tool Disambiguation ✅

**Principle:** Maximize clarity on tool instructions at minimal reasoning levels.

```yaml
<tool_instructions>
- Use search_tool for: verifying facts, finding APIs, checking current prices
- Use read_file for: examining existing code, checking configurations
- Never use search_tool when the answer is in local files
- Maximum 2 tool calls per research question unless explicitly needed
</tool_instructions>
```

---

## D.5 Agentic Persistence Reminders ✅

**Principle:** Prevent premature termination with explicit persistence prompts.

```yaml
<persistence>
- You are an agent - please keep going until the user's query is completely resolved.
- Only terminate your turn when you are sure that the problem is solved.
- Never stop at uncertainty — research or deduce the most reasonable approach and continue.
- Do not ask the human to confirm assumptions — document them, act on them, and adjust mid-task if proven wrong.
</persistence>
```

---

## D.6 Thorough Tool Preambles ✅

**Principle:** More important at minimal reasoning to maintain progress tracking.

```yaml
<tool_preambles>
- Describe what you're about to do before each tool call
- Update the user on progress after each tool result
- Summarize findings before moving to next step
- These preambles help you maintain context with limited reasoning tokens
</tool_preambles>
```

---

## D.7 Verification Patterns ✅

**Principle:** Add explicit verification steps for deterministic outputs.

```yaml
<verification>
Before returning, verify:
- Results array has exactly {batch_size} items
- Each item has all required fields: thread_index, is_relevant, confidence, reason
- No thread_index is missing or duplicated
- Output matches expected JSON schema exactly
</verification>
```

---

## D.8 Minimal Reasoning Template ✅

Complete template for mini/nano model tasks:

```yaml
<task_requirements>
- You are classifying/validating in a single pass
- Output JSON immediately after brief reasoning summary
- Complete ALL {batch_size} items before returning
</task_requirements>

[Brief explanation request]
First, write one sentence summarizing your approach.
Then output the JSON results.

[Task-specific instructions here]

<verification>
Before returning, verify:
- Output has exactly {expected_count} items
- All required fields are populated
- No items missing or duplicated
</verification>

<persistence>
- Complete the entire task before returning
- If uncertain about an item, make the most reasonable classification
- Document assumptions in the reason field
</persistence>
```

---

# Part E: OpenAI GPT-5.2 Patterns

Patterns specific to GPT-5.2 and its enhanced capabilities.

## E.1 Verbosity Control (output_verbosity_spec) ✅

**Principle:** GPT-5.2 is more concise by default but remains prompt-sensitive.

**Implementation:**

```yaml
<output_verbosity_spec>
- Default: 3–6 sentences or ≤5 bullets for typical answers.
- For simple "yes/no + short explanation" questions: ≤2 sentences.
- For complex multi-step tasks:
  - 1 short overview paragraph
  - then ≤5 bullets tagged: What changed, Where, Risks, Next steps, Open questions.
- Avoid long narrative paragraphs; prefer compact bullets.
- Do not rephrase the user's request unless it changes semantics.
</output_verbosity_spec>
```

**Task-Specific Constraints:**

| Task Type | Constraint |
|-----------|------------|
| Data extraction | Structured JSON only, no prose |
| Analysis | Summary + evidence table |
| Strategy | ≤7 recommendations, 1-2 sentences each |
| Research | 1 paragraph overview + categorized findings |

---

## E.2 Scope Drift Prevention (scope_constraints) ✅

**Principle:** GPT-5.2 may expand scope beyond requirements. Explicit constraints prevent feature creep.

**Implementation:**

```yaml
<design_and_scope_constraints>
- Explore any existing design systems and understand them deeply.
- Implement EXACTLY and ONLY what the user requests.
- No extra features, no added components, no UX embellishments.
- Style aligned to the design system at hand.
- Do NOT invent colors, shadows, tokens, animations, or new UI elements unless requested.
- If any instruction is ambiguous, choose the simplest valid interpretation.
</design_and_scope_constraints>
```

**Task-Level Scope Discipline:**

```yaml
**SCOPE DISCIPLINE:**
- Implement ONLY what is explicitly requested
- Do not expand the task beyond requirements
- If you notice additional work that could be helpful, call it out as OPTIONAL
- When uncertain, choose the simplest valid interpretation
```

---

## E.3 Long-Context Re-grounding ✅

**Principle:** For inputs >10k tokens, use forced summarization and re-grounding.

**Implementation:**

```yaml
<long_context_handling>
- For inputs longer than ~10k tokens (multi-chapter docs, long threads):
  - First, produce a short internal outline of key sections relevant to the request.
  - Re-state the user's constraints explicitly before answering.
  - In your answer, anchor claims to sections ("In the 'Data Retention' section…").
- If the answer depends on fine details (dates, thresholds), quote them.
</long_context_handling>
```

**Application to Knowledge Sources:**

```yaml
**CONTEXT GROUNDING:**
1. Before analyzing, list key themes/sections in your knowledge sources
2. Re-state niche and constraints: "{niche}" with focus on "{criteria}"
3. Anchor every finding: "In [POST_ID: xyz]..." or "According to..."
4. Quote specific phrases when citing evidence
```

---

## E.4 Uncertainty and Ambiguity Handling ✅

**Principle:** Configure prompts to handle ambiguous queries and prevent overconfident hallucinations.

**Implementation:**

```yaml
<uncertainty_and_ambiguity>
- If the question is ambiguous or underspecified:
  - Ask up to 1–3 precise clarifying questions, OR
  - Present 2–3 plausible interpretations with clearly labeled assumptions.
- When external facts may have changed recently and no tools available:
  - Answer in general terms and state that details may have changed.
- Never fabricate exact figures, line numbers, or external references when uncertain.
- When unsure, prefer language like "Based on the provided context…"
</uncertainty_and_ambiguity>
```

**High-Risk Self-Check:**

```yaml
<high_risk_self_check>
Before finalizing an answer in legal, financial, compliance, or safety-sensitive contexts:
- Briefly re-scan your answer for:
  - Unstated assumptions,
  - Specific numbers not grounded in context,
  - Overly strong language ("always," "guaranteed,").
- If you find any, soften or qualify them.
</high_risk_self_check>
```

---

## E.5 Agentic Steerability ✅

**Principle:** Brief, outcome-focused updates rather than verbose status narration.

**Implementation:**

```yaml
<user_updates_spec>
- Send brief updates (1–2 sentences) only when:
  - You start a new major phase of work, or
  - You discover something that changes the plan.
- Avoid narrating routine tool calls ("reading file…", "running tests…").
- Each update must include at least one concrete outcome ("Found X", "Confirmed Y").
- Do not expand the task beyond what the user asked.
</user_updates_spec>
```

**Update Triggers:**

| Trigger | Update Required | Example |
|---------|-----------------|---------|
| Phase start | Yes | "Starting competitive analysis phase" |
| Plan change | Yes | "Switching approach: API unavailable" |
| Significant finding | Yes | "Found 5 matching pain points" |
| Routine tool call | No | ~~"Reading file X..."~~ |

---

## E.6 Tool-Calling Best Practices ✅

**Principle:** Crisp tool descriptions improve selection accuracy.

```yaml
# ✅ BEST PRACTICE (Concise)
search_tool:
  description: >
    Search web for current information, documentation, or resources.
    Use when: verifying facts, finding APIs, checking current prices.
```

**Tool Usage Rules:**

```yaml
<tool_usage_rules>
- Prefer tools over internal knowledge when:
  - You need fresh or user-specific data.
  - You reference specific IDs, URLs, or document titles.
- Parallelize independent reads when possible to reduce latency.
- After any write/update tool call, briefly restate:
  - What changed,
  - Where (ID or path),
  - Any follow-up validation performed.
</tool_usage_rules>
```

---

## E.7 Web Research Patterns ✅

**Implementation:**

```yaml
<web_search_rules>
- Act as an expert research assistant; default to comprehensive answers.
- Prefer web research over assumptions; include citations.
- Research all parts of the query, resolve contradictions.
- Do not ask clarifying questions; cover all plausible intents.
</web_search_rules>

<research_iteration>
**STOP CONDITIONS (all must be true):**
- Answered the user's actual question and every subpart
- Found concrete examples and high-value adjacent material
- Found sufficient sources for core claims
- Additional searching unlikely to materially change answer

**CONTINUE SEARCHING IF:**
- Evidence is thin for any major claim
- Contradictions remain unresolved
</research_iteration>
```

---

# Part F: Anthropic Claude Patterns

Patterns specific to Claude models (Sonnet, Opus).

## F.1 XML Tag Conventions ✅

**Principle:** Claude responds well to XML-style tags for structure.

**Implementation:**

```yaml
<instructions>
- Follow these guidelines carefully
- Maintain consistent formatting
</instructions>

<context>
[Background information here]
</context>

<task>
[Specific task description]
</task>

<output_format>
[Expected format specification]
</output_format>
```

---

## F.2 Thinking/Reasoning Blocks ✅

**Principle:** Claude supports extended thinking for complex reasoning.

**Implementation:**

```yaml
<thinking>
Use this block to show your reasoning process:
1. First, analyze the key constraints
2. Then, consider each option
3. Finally, synthesize your recommendation
</thinking>

<answer>
[Final response here]
</answer>
```

---

## F.3 Claude-Specific Steerability ✅

**Principle:** Claude responds well to direct, explicit instructions.

**Implementation:**

```yaml
# Role establishment
You are an expert [role] specializing in [domain].

# Behavioral constraints
- Always [do this]
- Never [do that]
- When uncertain, [fallback behavior]

# Output expectations
Provide your response in the following format:
[format specification]
```

---

## F.4 Multi-Turn Context Management ✅

**Principle:** Claude maintains strong multi-turn context but benefits from explicit references.

**Implementation:**

```yaml
# Reference previous turns explicitly
Based on our earlier discussion about [topic], and your requirement for [X]...

# Summarize accumulated context
So far we've established:
1. [Key point 1]
2. [Key point 2]

Now, for this next step...
```

---

# Appendices

## Appendix A: Complete Prompt Templates

### A.1 Web Research Agent (GPT-5.2 Optimized)

```yaml
system_prompt: |
  You are a helpful web research agent. Your job is to thoroughly research
  the web and provide detailed, well-structured answers grounded in sources.

  ############################################
  CORE MISSION
  ############################################
  Answer the user's question fully with enough evidence that a skeptical
  reader can trust it.
  - Never invent facts. If you can't verify something, say so.
  - Default to being detailed and useful.

  ############################################
  FACTUALITY (NON-NEGOTIABLE)
  ############################################
  You MUST browse the web and include citations for all non-creative queries.

  ############################################
  CITATIONS (REQUIRED)
  ############################################
  - Place citations after each paragraph containing web-derived claims
  - Use multiple sources for key claims
  - Do not invent citations

  ############################################
  HOW YOU RESEARCH
  ############################################
  - Start with multiple targeted searches
  - Keep iterating until additional searching unlikely to change answer
  - If evidence is thin, keep searching

  **STOP CONDITIONS:**
  - Answered the user's question and every subpart
  - Found concrete examples
  - Found sufficient sources
```

### A.2 Agentic Task Template

```yaml
task_template: |
  ═══ CRITICAL RULES (Read First) ═══
  ✓ [Top constraints]
  ✗ [Key prohibitions]

  **CONTEXT:**
  {context_from_previous_tasks}

  **YOUR TASK:**
  [Clear objective]

  <output_verbosity_spec>
  - [Task-specific output constraints]
  </output_verbosity_spec>

  <scope_constraints>
  - Implement EXACTLY and ONLY what is requested
  </scope_constraints>

  **WORKFLOW:**
  1. [Step 1]
  2. [Step 2]

  **DELIVERABLES:**
  [Outputs per Pydantic model]

  ═══ CRITICAL RULES (Read Last) ═══
  [Repeat top constraints]
```

---

## Appendix B: CrewAI-Specific Patterns

### B.1 Pydantic Output with Context Chaining

**Problem:** CrewAI doesn't auto-inject Pydantic `Field(description=...)` into prompts.

**Solution:** Manually add field guidance:

```yaml
expected_output: >
  Complete ModelName Pydantic model with ALL fields:

  REQUIRED FIELDS:
  - field1: Description (source: context from Task N)
  - field2: Constraints (e.g., "0.0-1.0 score")

  CRITICAL: Return ACTUAL DATA, not schema definitions.
```

### B.2 Knowledge Source Search Strategy

```yaml
**SEARCH STRATEGY:**
1. Query knowledge sources with 3-5 varied queries
2. Look for patterns across multiple posts
3. Extract direct quotes with POST_ID attribution
4. If <5 results, report "Insufficient evidence"
```

---

## Appendix C: Anti-Patterns Quick Reference

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Fabricated statistics | Credibility risk, models hallucination | Use qualitative terms |
| Tutorial overload | Wastes tokens, undermines agent | Use tables/frameworks |
| Missing stop conditions | Encourages fabrication | Define explicit stops |
| Generic backstories | Unmemorable, no methodology | Use named frameworks |
| Redundant field management | Excessive hand-holding | Use tables |
| Scope drift | Feature creep | Use scope_constraints |

---

## Appendix D: Research References

### Primary Sources

**OpenAI GPT-4.1 Prompting Guide (2024):**
- Critical rules placement: "For long context, place instructions at both beginning and end"
- Markdown formatting: "Markdown performs best"

**OpenAI GPT-5 Prompting Guide (2025):**
- Agentic eagerness control: `<context_gathering>`, `<persistence>`
- Tool preambles: Upfront plans and progress updates
- reasoning_effort parameter: minimal/low/medium/high
- verbosity parameter: Controls final answer length
- Instruction following: Surgical precision, contradiction sensitivity
- Metaprompting: GPT-5 excels at optimizing prompts for itself
- Cursor integration: Real-world tuning examples

**OpenAI GPT-5.2 Prompting Guide (2025):**
- Verbosity control: "More concise and task-focused"
- Scope discipline: "Implement EXACTLY and ONLY what requested"
- Long-context handling: "Force summarization and re-grounding"
- Agentic steerability: "Strong on agentic scaffolding"

**Anthropic Claude Documentation (2024-2025):**
- XML tag conventions
- Extended thinking for complex reasoning
- Direct instruction following

### Academic Research (2024)

- Chain-of-Verification: Reduces hallucinations by up to 96%
- Cognitive Load Reduction: Visual structure reduces load by 60%+
- Temperature Settings: 0.0 for extraction, 0.7+ for ideation

---

## Conclusion

This guide provides model-specific prompt optimization patterns for:

| Part | Models | Key Patterns |
|------|--------|--------------|
| A | All | Conciseness, named frameworks, anti-hallucination |
| B | GPT-4.1 | System prompts, function calling, CoT |
| C | GPT-5 | Agentic eagerness, tool preambles, reasoning_effort, verbosity |
| D | GPT-5 mini/nano | Prompted planning, brief explanation, verification |
| E | GPT-5.2 | output_verbosity_spec, scope_constraints, re-grounding |
| F | Claude | XML tags, thinking blocks, multi-turn context |

**Apply patterns based on your target model for optimal results.**
