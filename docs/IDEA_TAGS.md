# Idea Tags

Closed-vocabulary **filter facets** attached to every solution idea. Displayed as chips today
(card badge + detail-modal groups); reserved for a filter sidebar later. Free-text tags don't
group, so every facet is a fixed enum.

- **Model:** `IdeaTags` in `src/nicheiq/models/solution_idea.py` (the `Literal` aliases there are
  the single source of truth for the vocabulary).
- **Assembly:** `src/nicheiq/utils/idea_tags.py` — `derive_tag_facets(idea, llm_facets)`.
- **Generation finalization:** `UnifiedSolutionCrew.execute_pipeline()` clears every incoming
  `tags` object and runs `_apply_tags()` after feasibility, parity, and SEO-realism work. This
  prevents birth-path or pre-calibration tags from surviving after their source scores change.
  The earlier angle classifier reads canonical idea fields only; provisional generated tags are
  deliberately excluded from that judgment.
- **Selection finalization:** `backfill_solution_scores()` synchronizes every existing selection
  entry's displayed component scores from the finalized idea fields, then adds any missing entries.
  The strategic selector's composite/rank is preserved; stale pre-cap component values are not.
- **Report finalization:** `ReportGenerator._sync_solution_scores()` first replaces the report's
  score fields with `ScoreAccessor`'s authoritative values, then calls `refresh_tag_facets()`
  (which delegates to `derive_tag_facets()`).
  Code-owned facets (`build_complexity`, `novelty_level`, `strengths`, and `primary_strength`) are
  rebuilt from those values while the semantic LLM facets are preserved.
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

`data_access` keeps the seven values above closed; near-synonyms LLMs emit are folded in at the
boundary instead of being added to the vocabulary — `none` / `not-data-dependent` / `official` →
`public`, `licensed` → `paywalled` (mirrored in the frontend by
`normalizeDataAccess()` in `frontend/src/lib/utils/ideaTagLabels.ts` so ideas stored before the
pipeline normalized them still render). Do NOT promote an alias into the table: a superset breaks
the chip labels, the friction sets, and mutual exclusivity with other facets.

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
  used by the `solo-friendly` strength) so "Hard to run solo" can never contradict a high Solo number; the
  `low` cut is locked to the `solo-friendly` cutoff in `STRENGTH_CUTOFFS`, so the two stay consistent.
- `novelty_level`: from `obviousness_score` (LOWER = less obvious, matching the displayed
  **Distinctiveness** value = 1 − obviousness): `≤0.30 → novel` (Distinctiveness ≥ 70),
  `≥0.60 → conventional` (Distinctiveness ≤ 40), else `moderate`. Legacy data falls back to
  `novelty_score` (higher = more novel): `≥0.70 → novel`,
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

| Stored key | UI label | Score field | Cutoff |
|---|---|---|---|
| `market-fit` | Strong demand fit | `market_fit_score` | ≥ 0.82 |
| `seo-power` | Strong organic discovery | `seo_scalability_score` | ≥ 0.85 |
| `innovator` | Distinct mechanism | canonical Distinctiveness (`1 − obviousness_score`; legacy fallback `novelty_score`) | ≥ 0.70 |
| `quick-build` | Technically straightforward | `technical_feasibility_score` | ≥ 0.85 |
| `solo-friendly` | Solo-manageable | `solo_dev_feasibility` | ≥ 0.78 |

- `tags.strengths` = all earned (modal + future filtering).
- `tags.primary_strength` = the single most exceptional = **largest margin above its cutoff**, or
  `null` if none clear (~30% of ideas). **The card shows `primary_strength`.**

`innovator` and `novelty_level` share the same canonical Distinctiveness value. When
`obviousness_score` exists it takes precedence; `novelty_score` is used only for legacy ideas
without obviousness. This prevents contradictory labels such as “Distinct mechanism” and
“Familiar approach” on the same idea.

**Why margin, not raw score.** The previous `getSuperpower()` picked the raw max, which is biased
toward higher-mean dimensions: in the historical 60-idea calibration sample it gave stored keys
`market-fit` 35% / `seo-power` 30% / `quick-build` 30% / `innovator` 1% / `solo-friendly` 3% —
two strengths were structurally invisible. Margin-above-cutoff rebalanced the same sample to
23% / 11% / 1% / 11% / 21%, with 30% showing none. The frontend reads the backend value;
`superpower.ts` keeps only the display
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

- **Idea header** (`SolutionDetail.svelte`): the single strength badge reads
  `tags.primary_strength` (legacy client-side selection only for pre-tags reports).
  The standalone `SolutionCard.svelte` that used to carry this badge was deleted with
  its only consumer, `solutions/SolutionGrid.svelte`.
- **Detail modal** (`SolutionDetailContent.svelte`): four labeled groups — **Strengths**
  (positives, variant-colored), **Model** (identity, neutral), **Growth** (channels, info), and
  **Watch-outs** (negatives, warning) — followed by a **"Why these tags"** line (`tags.rationale`).
  Display-only chips this round (no filtering); humanized via `ideaTagLabels.ts`.
- **Balanced, noteworthy-only display** (avoid clutter — most facets are the boring default):
  - **Always:** `project_type`, `target_market`, `monetization` (identity) in **Model**;
    all `growth_channels` (incl. `programmatic-seo`, a real positive) in **Growth**.
  - **Positives** (in **Strengths**): the score-cutoff strengths.
  - **Negatives** (in **Watch-outs**, warning tone): `build_complexity == high` ("Hard to run solo"),
    `novelty_level == conventional` ("Familiar approach"), friction `data_access`
    (paywalled/unofficial/restricted/blocked/**unverified**), and all `risk_flags`.
    `unverified` = the data-route verifier could neither confirm nor refute a public source — the
    idea is *not* score-penalized for it, just flagged so you can check before building.
  - **Hidden** (neutral middle, no signal): `build_complexity == medium`,
    `novelty_level == moderate/novel`*, `data_access == public/freemium`.
  - *`novel` is not shown as a separate "Distinct approach" chip when the positive is already
    carried by the `innovator` / "Distinct mechanism" strength. Suppression is **display-only**;
    all facets remain in the data.
- **Hover explanations:** every chip + the card badge show a one-line tooltip on hover. The
  `data_access` chip prefers the verifier's **per-idea, evidence-grounded note**
  (`data_acquisition_notes`, LLM-written and citing the search) over the static definition — so it
  explains why *this* idea's route is gated or unverified, not just what the label means.
  `tagDescription()` (in `ideaTagLabels.ts`) gives a qualitative, user-facing meaning for each
  value without exposing internal thresholds. The per-idea "why" for semantic facets comes from
  the LLM `rationale` line.

## Serialization

`tags` is present on `BaseSolutionIdea`/`SolutionIdea`, the report-model `AlternativeSolution`
(`research_state.py`), the preview `alternative_solutions` dict
(`research_flow._materialize_preview_report`), and the report assembly
(`report_generator._generate_alternative_solutions`). Frontend receives it via the `/solutions`
feed (`SolutionPreview.tags`) and the report (`AlternativeSolution.tags`). Worker serialization
refreshes score-owned facets for both model instances and full dicts, covering queue/resume
boundaries without trusting persisted pre-final tags.
