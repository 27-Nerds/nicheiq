# Idea Tags

Closed-vocabulary **filter facets** attached to every solution idea. Displayed as chips today
(card badge + detail-modal groups); reserved for a filter sidebar later. Free-text tags don't
group, so every facet is a fixed enum.

- **Model:** `IdeaTags` in `src/nicheiq/models/solution_idea.py` (the `Literal` aliases there are
  the single source of truth for the vocabulary).
- **Assembly:** `src/nicheiq/utils/idea_tags.py` — `derive_tag_facets(idea, llm_facets)`.
- **Pipeline step:** `UnifiedSolutionCrew._apply_tags()` runs last in `execute_pipeline()` (after
  feasibility + SEO-realism finalization, which mutate the scores tags are derived from).
- **Frontend:** `IdeaTags` in `frontend/src/lib/types/job.ts`; display labels in
  `frontend/src/lib/utils/ideaTagLabels.ts`; strength badge in `superpower.ts` /
  `solution-utils.ts`.

## Facet catalog

| Facet | Values | Select | Source |
|---|---|---|---|
| `project_type` | aggregator · saas · comparison-tool · directory · marketplace · other | single | reuse `idea.project_type` |
| `monetization` (+ `monetization_secondary`) | subscription · one-time · commission · usage-based · advertising · affiliate · licensing | single primary (+optional secondary) | LLM |
| `build_complexity` | low · medium · high | single | derived |
| `novelty_level` | conventional · moderate · novel | single | derived |
| `target_market` | b2b · b2c · prosumer · b2b2c | single | LLM |
| `data_access` | public · freemium · paywalled · unofficial · restricted · blocked · unverified | single | reuse `idea.data_access_model` |
| `growth_channels` | programmatic-seo · content · community · paid-ads · network-effects · integrations | multi | LLM (+ derived pSEO) |
| `risk_flags` | regulatory · tos-risk · grey-market · trust-dependent | multi (may be empty) | LLM (+ derived tos-risk) |
| `usage_cadence` | continuous · periodic · episodic · one-shot | single | LLM |
| `pricing_shape_mismatch` (+ `pricing_shape_note`) | bool + note | — | derived (cadence × monetization) |
| `strengths` (+ `primary_strength`) | market-fit · seo-power · innovator · quick-build · solo-friendly | multi stored; one primary on the card | derived |

Facet vocabularies are **mutually exclusive** (no value appears in two facets) — enforced by
`tests/unit/utils/test_idea_tags.py::test_facet_vocabularies_are_mutually_exclusive`.

## Per-value definitions (the non-obvious ones)

**risk_flags** — scraping is NOT inherently risky; only flag genuine risk:
- `tos-risk` — acquisition plausibly violates a platform's terms or relies on an
  unofficial/restricted/login-gated route. **Benign public-data scraping (public pricing pages,
  government open data, public APIs) is NOT flagged.**
- `regulatory` — health/medical/finance/privacy compliance exposure.
- `grey-market` — legally ambiguous market (e.g. research-chemical resale).
- `trust-dependent` — value hinges on trust that's hard to bootstrap or easy to game (fake
  reviews, self-reported outcomes).

**monetization** is the **primary** revenue model. Most ideas mention several streams; tag the
one the business mainly runs on (optional `monetization_secondary` for a clear second).

**usage_cadence** (2026-07-06) is how often the buyer **uses** the product, NOT how it bills:
`continuous` (daily/weekly workflow) · `periodic` (recurring calendar cadence — monthly reports,
quarterly filings) · `episodic` (triggered by irregular events — validating an idea, raising
prices, a fundraise) · `one-shot` (value delivered once). An idea-validation tool used at project
start is `episodic` even if priced monthly.

## Derivation rules (code)

All thresholds are **standardized constants** calibrated on a 60-idea / 12-run sample. Tunable —
revisit if score distributions shift. Source: `derive_tag_facets`.

- `pricing_shape_mismatch` ← `monetization == subscription` AND `usage_cadence ∈ {episodic, one-shot}`:
  buyers churn between events; `pricing_shape_note` names the recommended shape (usage-based/credit
  packs for episodic; one-time purchase/paid report for one-shot). Informational only — never a
  score change; rendered as a "Pricing-shape mismatch" watch-out chip.
- `build_complexity` ← `solo_dev_feasibility` (fallback `build_feasibility_score` → `technical_feasibility_score`):
  `≥0.78 low · 0.65–0.78 medium · <0.65 high`. Driven by the SAME field shown as the "Solo" score (and
  used by the `solo-friendly` strength) so "Hard to build" can never contradict a high Solo number; the
  `low` cut is locked to the `solo-friendly` cutoff in `STRENGTH_CUTOFFS`, so the two stay consistent.
- `novelty_level`: from `obviousness_score` (LOWER = more original, matching the "Originality"
  header = 1 − obviousness): `≤0.30 → novel` (Orig ≥ 70), `≥0.60 → conventional` (Orig ≤ 40), else
  `moderate`. Fallback to `novelty_score` (higher = more original): `≥0.70 → novel`,
  `≤0.40 → conventional`, else `moderate`.
- pSEO: add `programmatic-seo` to `growth_channels` if `estimated_indexable_pages ≥ 500` or
  `seo_scalability_score ≥ 0.7`.
- `tos-risk`: force-added ONLY if `data_access_model == "unofficial"` (a genuinely ToS-gray
  route). `restricted` / `blocked` describe obtainability ("hard to get"), not legality, so they
  do NOT auto-flag tos-risk — the LLM still owns it for everything else. (Earlier the rule also
  fired on `restricted`/`blocked`, which over-flagged public-data scrapes that merely had
  per-lookup access.)
- Out-of-vocab LLM values are dropped; reused fields are coerced to the vocab or `None`, so the
  resulting `IdeaTags` always parses.

## Strengths logic (replaces the old "superpower" badge)

An idea earns **each** strength whose score clears a fixed per-dimension cutoff (calibrated to
~top-third so a badge stays meaningful):

| Strength | Score field | Cutoff |
|---|---|---|
| `market-fit` | `market_fit_score` | ≥ 0.82 |
| `seo-power` | `seo_scalability_score` | ≥ 0.85 |
| `innovator` | `novelty_score` | ≥ 0.70 |
| `quick-build` | `technical_feasibility_score` | ≥ 0.85 |
| `solo-friendly` | `solo_dev_feasibility` | ≥ 0.78 |

- `tags.strengths` = all earned (modal + future filtering).
- `tags.primary_strength` = the single most exceptional = **largest margin above its cutoff**, or
  `null` if none clear (~30% of ideas). **The card shows `primary_strength`.**

**Why margin, not raw score.** The previous `getSuperpower()` picked the raw max, which is biased
toward higher-mean dimensions: on 60 ideas it gave Market Fit 35% / SEO 30% / Quick Build 30% /
**Innovator 1% / Solo-Friendly 3%** — two strengths were structurally invisible. Margin-above-
cutoff rebalances to Market Fit 23% / Solo 21% / SEO 11% / Innovator 11% / Quick Build 1%, with
30% showing none. The frontend reads the backend value; `superpower.ts` keeps only the display
labels/variants (`SUPERPOWERS` / `SUPERPOWERS_DETAILED`), mapped from the hyphenated strength keys
via `strengthEntry()`.

## LLM tagging contract

`_apply_tags` makes one batch `LLMService.invoke_structured` call per run (model
`settings.ideation_judge_llm`, `temperature=0`, `reasoning_effort="medium"`, `creative=True`) over
the whole idea list, requesting the **semantic** facets (`target_market`, `monetization`,
`monetization_secondary`, `growth_channels`, `risk_flags`) plus a one-sentence `rationale`
(justifies the non-obvious calls — esp. why each risk flag and the primary monetization), joined
back by `solution_name`.

- The prompt (`_render_tagging_prompt`) gives a per-value definition + negative examples
  (e.g. "scraping public government data is NOT tos-risk"). Output model `_SolutionTagBatch` uses
  plain `str` fields (not `Literal`) so one out-of-vocab token never fails the whole batch;
  `derive_tag_facets` coerces/drops invalid values.
- `validate_solution_tags()` checks coverage (every idea tagged) and logs gaps.
- **Fail-soft:** on any LLM/parse error, derived + reused facets still attach (semantic facets
  left `None`). Tags never block the pipeline.

## Display surfaces

- **Card** (`SolutionCard.svelte`): unchanged layout; the single strength badge now reads
  `tags.primary_strength` (legacy client-side selection only for pre-tags reports).
- **Detail modal** (`SolutionDetailContent.svelte`): four labeled groups — **Strengths**
  (positives, variant-colored), **Model** (identity, neutral), **Growth** (channels, info), and
  **Watch-outs** (negatives, warning) — followed by a **"Why these tags"** line (`tags.rationale`).
  Display-only chips this round (no filtering); humanized via `ideaTagLabels.ts`.
- **Balanced, noteworthy-only display** (avoid clutter — most facets are the boring default):
  - **Always:** `project_type`, `target_market`, `monetization` (identity) in **Model**;
    all `growth_channels` (incl. `programmatic-seo`, a real positive) in **Growth**.
  - **Positives** (in **Strengths**): the score-cutoff strengths.
  - **Negatives** (in **Watch-outs**, warning tone): `build_complexity == high` ("Hard to build"),
    `novelty_level == conventional` ("Unoriginal"), friction `data_access`
    (paywalled/unofficial/restricted/blocked/**unverified**), and all `risk_flags`.
    `unverified` = the data-route verifier could neither confirm nor refute a public source — the
    idea is *not* score-penalized for it, just flagged so you can check before building.
  - **Hidden** (neutral middle, no signal): `build_complexity == medium`,
    `novelty_level == moderate/novel`*, `data_access == public/freemium`.
  - *`novel` novelty isn't shown as its own chip — the positive is already carried by the
    `innovator` strength. Suppression is **display-only**; all facets remain in the data.
- **Hover explanations:** every chip + the card badge show a one-line tooltip on hover. The
  `data_access` chip prefers the verifier's **per-idea, evidence-grounded note**
  (`data_acquisition_notes`, LLM-written and citing the search) over the static definition — so it
  explains why *this* idea's route is gated or unverified, not just what the label means.
  `tagDescription()` (in `ideaTagLabels.ts`) gives the static meaning of each value — derived
  facets state their rule/cutoff ("why"), LLM/reused facets give the definition ("what"). The
  per-idea "why" for the semantic facets comes from the LLM `rationale` line.

## Serialization

`tags` is present on `BaseSolutionIdea`/`SolutionIdea`, the report-model `AlternativeSolution`
(`research_state.py`), the preview `alternative_solutions` dict
(`research_flow._materialize_preview_report`), and the report assembly
(`report_generator._generate_alternative_solutions`). Frontend receives it via the `/solutions`
feed (`SolutionPreview.tags`) and the report (`AlternativeSolution.tags`).
