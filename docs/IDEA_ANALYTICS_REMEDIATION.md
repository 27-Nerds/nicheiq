# Idea-analytics remediation ledger

Origin: *"improve the quality of the idea analytics to match the quality you provide when selecting
ideas worth building."* Three review passes narrowed this to two code findings and one analysis task.

## Status

| ID | Finding | Rounds | State |
|----|---------|--------|-------|
| A1 | `_probe_mechanism_parity` clears `winning_angle` AFTER `_classify_idea_angles` ran — runs after 2026-08-13 ship equal-weight composites | 1 | **PASS** (fresh critic reproduced independently) |
| A2 | No per-run coverage check on score-bearing fields; both this regression and the analysis-harness bug were silent field loss | 3 | **PASS** (critic reproduced every number, incl. the unflattering ones) |
| A3 | Disposition labels: back-extract per-run verdicts from shortlist prose; baseline on the analyst's own named signals | 1 | **DONE — negative result.** Both named signals fail; disposition is not buildable on today's labels |
| A4 | 39 of 40 damaged runs carry `winning_angle: None` permanently; the fix repairs new runs, nothing backfills | 0 | **WON'T FIX** — owner's decision 2026-08-16 |
| A5 | Parity is a per-idea vocabulary lottery; `_pivot_acceptable` admits revisions only when the probe MISSES | — | **VERDICT CORRECTION ABANDONED** — 6 mechanisms killed by measurement (see below) |
| A5-R2 | Parity rendered "none found" as a fact the system does not have | 2 | **PASS** — Python + TS, critic-verified |
| A6 | Stage-1 reframes TOPIC-for-AUDIENCE inputs into the parent market, invisibly | 2 | **PASS** — round 1 FAILED (rendered nowhere); round 2 renders on 3 real surfaces |
| A7 | "Nothing gates on disclosures" | 0 | **WITHDRAWN** — two pre-generation gates exist; fail-open-with-disclosure is a documented product choice |

## Correction to A1's own dating (measured by A2, 2026-08-16)

The ledger originally said "since 2026-08-13". Measured per run-date, **2026-08-13 is still at 100%
populated**; the collapse falls between the 08-13 and 08-15 buckets. The magnitude is also sharper than
first stated: **0% → 87.1% unclassified**, not 5.4% → 84.8%. Same bug, same commit, wrong dates —
recorded here because a number in a ledger becomes a fact for the next round.

## A1 — the order regression (VERIFIED by the master agent)

`src/nicheiq/crews/unified_solution_crew.py`, post-union sequence:

```
:12040  self._classify_idea_angles(...)        <-- sets winning_angle
:12048  self._probe_serp_composition(...)      <-- READS winning_angle (this is why order was swapped)
:12058  self._probe_mechanism_parity(...)      <-- :3349 CLEARS winning_angle on every idea
```

`:3349` clears `winning_angle`, `angle_rationale`, `novelty_rationale`, `differentiation_locus`
under a comment that still claims `_classify_idea_angles` is "the very next post-union pass". It is
not, since commit `b7d9f3a` (2026-08-13, "fixes"). Nothing re-derives afterwards except `_score_wave`
(`:9246`) for wave-born ideas.

**The clearing itself is correct and must be preserved** — the parity probe changes capped scores, so
the stale rationales it clears would cite superseded numbers (observed live 2026-07-05:
`novelty_rationale` "0.45" vs final 0.7). The defect is that nothing re-derives after the clear.

Measured over `output/checkpoints/*/stage_5_3_refinement.json`, unclassified fraction per run:

```
post-feature, PRE  2026-08-13:   5.4%  (57 runs)
post-feature, POST 2026-08-13:  84.8%  (40 runs)
```

Not cosmetic: stripping angles moves the ranking in 25 of 58 runs and flips the #1 idea in 9.

**Contaminates prior evidence.** `probes/analyst_agreement.py` reports pairwise AUC 0.850, but two of
its contributing runs (`e1b42702`, `49ed2bb9`) were ranked in the broken equal-weight regime. That
number is a MIXED-REGIME measurement and must be re-derived after A1 lands.

## A2 — silent field loss has no monitor

Two independent instances in one session, same class:

1. This regression — a score-bearing field cleared and never re-derived, invisible for 3 days.
2. The analysis harness — `preview_report_*.json` writes `seo_growth_potential_score`,
   `BaseSolutionIdea` reads `seo_scalability_score` with `extra='ignore'`, so reconstruction silently
   produced a 3-dimension composite wearing a 4-dimension label. It moved 4 of 9 ranks and
   manufactured a BUILD-vs-KILLED inversion that never existed. Two review passes shared it and
   agreed with each other, which proved nothing.

The corpus is a **time series across code versions**; every pass treated it as one population. A
per-run coverage check over score-bearing fields would have caught both on the day they landed.

## Withdrawn / falsified claims — do not re-fix these

- **"The pipeline's ranking underperforms the analyst."** Not supported. Picks land at AUC 0.850,
  SEO mean percentile 0.24 / SaaS 0.20; five picks are their run's #1. (Caveat: mixed-regime, see A1;
  and substantially circular — the analyst read the same stored fields the ranker consumes.)
- **"A second SEO-first ranked list is needed."** SEO picks are not buried; two of four rank #1.
- **"Promote `data_feasibility_score` into the composite."** Measured HARMFUL: 4 worse / 2 better, and
  it demotes the LLM-API-shaped idea #3→#5 — the exact failure the owner's constraint forbids.
- **"Segment payability predicts run quality almost perfectly"** (recorded 2026-08-12). Does not
  reproduce: separation +0.013 at corpus level, and *anti*-correlated on labelled runs (0.67 pick vs
  0.84 reject). The run yielding the best SEO pick has the corpus's LOWEST max payability (0.50).
- **"`niche_difficulty_verdict` can gate spend."** `difficulty_level` is `high` on 28/32 runs, never
  `low`; `software_addressability` places a wholesale-rejected run mid-pack among productive ones.
- **"AuditLogDiff #13 vs ClearingCalc #3 is the worst inversion in the corpus."** Artifact of the
  harness bug. Real: #8 vs #6, and both carry `red_team_verdict: None` — that kill came from evidence
  outside the pipeline, unreachable by any ranking change.
- **The owner's paid-API constraint is ALREADY honored**: the calibration prompt forbids penalising an
  idea for merely using an LLM API, and `paywalled` is exempt from the market-fit cap (only
  unofficial/restricted/blocked are capped). No work warranted on that axis.

## A2 — accepted residuals, recorded so a later round does not re-litigate them

Three rounds. Round 1's latest-date floor dict (30 entries, 14 pinned at 1.000) would have failed
**18 of the last 20** real run dates — deleted, not lowered, after two history-derived alternatives
measured *worse* on replay (historical-minimum 70% FA, trailing-median 50%). Round 3's builder then
rejected the orchestrator's own proposed mechanism: a pooled per-date presence series false-alarms
3/20, because a date pools every producer that ran — 07-28 moves **eleven fields in lockstep**
0.80→0.54, which is one producer's absence, not eleven regressions.

Shipped: `ragged_key_presence` (a key present on some rows of one persisted list and absent from
others — the `exclude_none` signature; no threshold, no dates) and `producer_presence_losses` (scoped
by producer × container, uuid/timestamp normalised out — **without that normalisation the detector
looked clean by being vacuous**). Both 0/20 false alarms, independently reproduced.

**Deliberately NOT built — do not "fix" these without an observed failure:**
1. An *ungated* field dropping 1.00 → 0.85 by value-nulling (27 of 30 idea fields, below the 0.25 step
   threshold). This is the price of deleting the floors. Re-adding per-field floors was tried and
   rejected with measurement.
2. A field stamped `0.0` everywhere reads as 100% populated to every detector here — presence-shaped
   monitoring cannot see value-shaped loss.
3. `producer_presence_losses` pools "written" per date, so one surviving writer (a stale worker) or a
   producer whose dates never reach 8 rows (all `stage_7_*` containers) masks a uniform key loss.
   Demonstrated, and narrower than (1).

Pre-existing `eligibility_losses` is **not** 0/20 on an as-of replay — it fires 1/20 on
`red_team_findings` (record `......W.W`: a field being rolled out, not lost). A full-corpus zero is not
a 20-date replay zero. Left alone deliberately.

**First-week falsifier:** the next real field regression surfaces in a report or PR review rather than
this suite, and turns out to be value-shaped or in a sub-8-row `stage_7_*` producer. That would be a
structural blind spot, not an implementation miss.

## A3 — both named disposition signals FAIL. Do not re-test them.

19 reviewed runs → 28 labelled (run, direction) units, every label carrying a doc:line quote that a
test verifies is a substring of that exact line. Unit is **(run, direction)**, forced by `16606c57`
("SEO-ONLY — do not build as SaaS") and `8f35ea6b` (SaaS-rejected, SEO-carried).

| direction | signal | AUC | n_pos/n_neg | exact perm p |
|---|---|---|---|---|
| saas | none_found density | **0.430** | 5/10 | 0.671 |
| saas | public + low-CAC | 0.250 | 5/10 | 1.000 |
| seo | none_found density | 0.406 | 4/8 | 0.715 |
| seo | public + low-CAC | 0.750 | 4/8 | 0.095 |

**S1 (parity `none found` density) is falsified, and it is NOT a power problem.** 0.430 is *below*
chance and the design could have detected an effect (min achievable p = 0.0003). Counterexample:
`86e765e5` was carried with S1 = 0.000 (lowest in the corpus) while `f7863089` at 0.667 was rejected
on both directions. This contradicts the 2026-08-02 note *"3 of 6 `none found` … the NICHE was the
variable"* — that inference does not survive measurement.

**S2's 0.750 is label leakage, not weak evidence.** `IDEA-SHORTLIST-2026-08-16.md` states its ranking
method AS this signal's two components (lines 25-28) and rejects the AI-visibility SEO directions in
the signal's own words (79-80). Every SEO negative comes from that doc. **Strip the circular labels
and the negative class is empty — the AUC is UNDEFINED (n_pos=2, n_neg=0), not 0.750.**

**Verdict: disposition cannot be built on today's labels.** The cheapest unblock is to record, at
review time and BEFORE opening the artifacts, one line per (run, direction) — `build | carry_hedged |
reject` plus a free-text reason — **and stamp which fields the reviewer consulted.** That last part is
what makes the label non-circular; without it the next measurement repeats this failure. ~18-20 more
reviewed runs reaches significance (p ≈ 0.01 at 12×24, versus p = 0.095 at today's 4×8).

Denominator validated: `candidate_status == 'active'` reproduces the docs' own idea counts exactly
(118/118, 26/26, 27+1 demoted of 28) and the analyst's "3 of 6 none found" for `58f7f62a`. Eligibility
is partial and stated: parity on 200/206 ideas, CAC parsing on 188/206; `23a45a87` truncated before
the competitive stage and is ineligible rather than scored 0.0.

## A5–A7 — findings from the 2026-08-16 verification run (job `8500b97d`)

Run made to verify A1 (it did: angle classification 7% → 100%). These are separate defects it exposed.
Report: `/home/syzspectroom/work/output/final_report_20260816_203815.json`.

### A5 — parity is a per-idea vocabulary lottery, and selection prefers its misses. **WORTH FIXING.**

The report rules out *Reinstatement to Entity Continuity Dossier* ("Already well-served: **partial by
Whitespark** … evidence gathering and appeal steps") and, for the **same pain** — "Cannot restore a
Google Business Profile after verification or ownership failure" — selects *Reclaim Packet QA*
(evidence packet for a disputed GBP) as the #1 recommendation with `incumbent_parity: "none found"`.
The loser's rejection reason applies verbatim to the winner.

**Root cause.** `_probe_mechanism_parity` (`crews/unified_solution_crew.py:3121`) queries using each
idea's OWN vocabulary (:3198-3213); incumbent-name queries fire only on token overlap (:3204-3205).
Log chain: 19:54 full 13-idea probe finds Whitespark → 20:04 red-team revision born → **20:05 that
revision is probed ALONE**, after `parity_discovery_queries_per_run` (default 12) was spent, so it has
no vendor-free discovery arm → "none found" → 20:06 accepted as winner. The reset-first block
(:3261-3268) wipes parity on every re-probe by design (anti-fabrication) and nothing carries findings
across invocations.

**Adverse selection makes it structural**, `:9208`:
```python
if _comp(rev) > _comp(orig) and rev_par.startswith("none"):
```
A revision enters the pool ONLY when its parity says "none" — so revisions are admitted precisely when
the probe misses, playing that lottery with the weakest query arm.

**Systematic, measured two ways.** Master agent, grouping on `pain_points_addressed`: **77/150
multi-idea pains (51.3%) contradictory, 24/67 reports**. Investigator, different denominator: 87/285
(30.5%), 25/67. Denominators differ; the conclusion does not. Worst shape found: pain titled *"premiere
pro panel integration broken in frame.io v4"* carries `bundled_free (frame.io)` on one idea and
`none found` on another.

**Recommended fix — relocate, don't add:** probe once per (pain × mechanism-family), stamp all members,
and make re-probes INHERIT the family finding instead of re-rolling. Removes the solo-probe path rather
than layering a reconciliation pass; family infrastructure exists at :2487-2494. `_pivot_acceptable`
then reads the inherited finding.

### A6 — the input niche is reframed at Stage 1, and the drift is invisible by construction

`_generate_niche_context` (`flows/research_flow.py:3709`) classified the input `audience_scope:
"segment_of_niche"` and, by explicit design (:3837), researched the PARENT market. "AI visibility **for
local businesses in London**" names a buyer, so the topic was absorbed as a qualifier and generalised
to "the local digital search and visibility optimization market". 8 of 9 kept pains are classic local
SEO/GBP; the one on-niche pain ("Cannot make the business accurately understood by AI search") had its
idea ruled out by A5's mechanism.

**Blind spot: TOPIC-for-AUDIENCE inputs, where the topic IS the niche.** Correct for "athletes
interested in peptides"; wrong here. Changing the decision pivot (:3794-3798) carries A/B regression
risk — an experiment, not an obvious fix. **Owner's call.**

**The 3.8% caveat is dead weight — delete it.** `_apply_anchor_drift_guard`
(`utils/generation/query_generator.py:51-86`) measures **named-entity presence** over 26 Reddit
non-discovery queries, not on-nicheness. Its caveat threshold (`report_generator.py:1792-1797`) is
`< 0.4` — the same number `_cap_named_entities` actively caps TOWARD — and `ANCHOR_PCT_FLOOR = 0.0`
deliberately disabled enforcement. Verified firing on **11 of 13** reports: unconditional boilerplate.
Worse, the real drift is undetectable because anchors are generated FROM the reframed description
(`pain_evidence_anchor_coverage` read a healthy 76% against the wrong anchors).

**Cheapest real fix:** echo `niche_input` beside the derived `niche` in the report. The drift was found
by diffing those two by hand; the report should do that diff.

### A7 — "nothing gates on disclosures" was overstated. **NOT a defect.**

Two pre-generation gates exist: minimum content (`research_flow.py:4458-4464`) and the pain-quality
tier gate (:4851-4892, raises `QualityGateStopException` before Stage 5). They gate evidence
QUANTITY, not fidelity. Fail-open-with-disclosure is written into the code at every fidelity site
(":4856 Niche-drift OBSERVABILITY (non-scoring)", ":3313 never as a score change"). Deliberate,
documented product choice. A new pre-generation fidelity gate is **not worth building** — the metric
that would feed it (A6) measures the wrong thing.

## A5 — six verdict-correction mechanisms, all killed by measurement. Do not re-propose.

The defect is real: `_probe_mechanism_parity` queries using **each idea's own vocabulary**
(`crews/unified_solution_crew.py:3198-3213`), so two ideas covering the same ground get opposite
verdicts. 59.9% of multi-idea pains carry a none-vs-covered contradiction. Live case: *Reclaim Packet
QA* shipped as a #1 recommendation with "none found" while a same-pain sibling carried "partial by
Synup" — RPQA's value prop contains none of the vocabulary that finds its own incumbent.

| # | mechanism | why it died |
|---|---|---|
| 1 | group by `mechanism_tag\|data_source_tag`, inherit strictest | no-op (1-5 contradictions / 197 runs); the tag is LLM free text — the same lottery one level up |
| 2 | group by pain | over-blocks: 642 ideas none→capped, allow-case collapses to **22.9%** |
| 3 | pain × family | no-op (1 contradiction / 197 runs) |
| 4 | lineage inheritance | the live case's parent ALSO got "none found"; the evidence lived on an unrelated third idea |
| 5 | reserved discovery budget for re-probes | fails the live case — RPQA carries none of the vocabulary that finds its incumbent |
| 6 | run-scoped evidence ledger + directed LLM re-adjudication | controls clean (0.0% on 1026 decoys), allow 94.7%, precision 81.5% — but **NOT REPEATABLE**: at temperature 0.0 over 7 reps the live case flips **3/7**. A non-deterministic gate on a money-gating field. Only 8 of 513 flips changed a score. Probe: `probes/parity_ledger_ab.py` |

**The measurement that ended the program:** winners are "none found" **39.5%** of the time against a
**51.0%** base rate — probe misses do NOT systematically crown winners. The corpus-level harm is far
smaller than the live case suggests. Cost of the whole investigation: ~$2 and six wrong things not
built.

`_pivot_acceptable` (`:9208`) admitting revisions only when parity `startswith("none")` remains a
real structural oddity — 7 of 7 revision-born ideas carry "none found" **by construction**. Deleting
that clause (R3) was measured at **3 changed decisions across 4 days of logs**, one of them admitting
a `substitute`-parity revision. Rejected as not worth touching a money-gating path.
Probe: `probes/revision_gate_ab.py`.

## Gauntlet outcomes, 2026-08-16/17

**A5-R2 PASS** (2 rounds). Round 1 fixed Python; a critic found the user-facing stack still said
"No competing product found" in two helper copies, a few-shot that told the LLM to quote it, and a raw
render. Round 2 closed all of it. Notable: `utils/idea_portfolio_summary.py:237` rendered **blank**
parity as "no incumbent match found" and fed that verbatim into the portfolio-summary LLM prompt — a
manufactured negative being reasoned from, not merely displayed. The stored stamp and its `none`
prefix are untouched; ~139 consumers parse it.

**A6 PASS** (2 rounds). **Round 1 failed while green** — the disclosure was correctly gated, honestly
measured (~87% firing, exercised silent class) and fully tested, but `UnifiedHero`'s only production
mount passes a synthesized report without `niche_context`, so it rendered NOWHERE. Its test passed by
hand-building a shape no producer supplies. Round 2 extracted `NicheReframeNote.svelte` and mounted it
on the job page, `ReportContent` (covers /report, /shared, /sample-report) and `SharedDiscoveryView`,
with a class check that fails if a mount does not read `niche_context` or lands under
`aria-hidden`/`inert`.

**Accepted residual (A6):** the mount registry's spec verification is textual, so magic strings in a
comment plus one trivial test satisfies it. It polices accidental mis-wiring — which is the threat —
not deliberate spec degradation, which is a visible diff. Documented rather than hardened.

**Next place the claim will regrow** (found, not fixed): `report_generator.py:4327` renders
*"Searched {label} and found no existing content for this niche. Potential first-mover opportunity"* —
first-mover status asserted from a search miss, same defect class, different field, invisible to the
new enumeration. **0 live instances** in the 2026-08-16 report. Also `previewPlaceholders.ts:467`.

## A8 — parity-by-group: design reviewed, half rejected, and the severity restated

**The severity number I quoted all session was inflated 8×.** The rate is keying-invariant; the volume
is not:

| keyed on | multi-idea pains | contradictory | pairs |
|---|---|---|---|
| `pain_points_addressed` (idea's SELF-AUTHORED list) | 775 | 471 (60.8%) | **891** |
| `source_pain` (the pain the idea was GENERATED from) | 174 | 104 (59.8%) | **112** |

Honest figure: **~1.9 contradictory pairs per affected run**, 58 runs. Quote `source_pain`. The
grouper additionally judges ~2/3 of "contradictory" pairs to be genuinely DIFFERENT products, so part
of the 60% was never a defect.

**Refuted (do not retry):** resetting `_parity_discovery_spent`, or any per-invocation discovery
allowance. Measured: RPQA had **zero focus-overlap against all 12 incumbents**, so its name-anchored
query list was empty and the `:3212` fallback fired — which is **byte-identical to the discovery
query**. The vendor-free query DID run; executed live, it does not return Whitespark. Budget was never
the constraint. Note the counter is deliberately un-reset (`:3185-3189`), not a defect.

**Also measured, and it inverts the design's own premise:** for the Dossier, the *discovery* query does
not return Whitespark, but the *name-anchored* `"BrightLocal" google business profile reinstatement
evidence` query does (Google fuzzy-matches Whitespark in). The arm the design called load-bearing
isn't.

**Rejected: group-scoped evidence sharing / verdict inheritance.**
- Grouper IS stable (7/7 byte-identical partitions, temp 0) — clears the gate that killed the ledger.
- But **stable ≠ correct**: the mandated negative (ReceiptAsk) groups with Postmark Proof **7/7**.
- **Median absorption 88%** of each pool lands in a group → one-verdict-per-group ≈ pool-wide caps,
  i.e. the pain-grouping 22.9% allow-case collapse reborn as judge behaviour.
- **RPQA joins the Dossier group 0/7** — the red-team rewrite moved it outside semantic grouping.
- The reviewer's disqualifying finding: **"the design measures who a fix could reach, never whether
  the verdict moves."** Probe #1's judge had the Whitespark snippet AND the predecessor idea in ONE
  prompt and still stamped `none found`. The flagship case survives Steps 0-3 in full.

**Approved and in build:** Step 0 (instrumentation, zero behaviour change) + Step 1 (group membership
maintenance across `ideas[idx] = rev` successor replacement). Both justified by evidence in hand.

**Explicitly NOT built: emitting `overlap_groups` into the final report.** `report_generator.py` has 0
references; `types/report.ts:100` declares the field and **no component reads it**. The real consumers
— SelectionWorkbench (4 render sites), SolutionDetailContent, SharedDiscoveryView, the job page — all
read `previewReport?.overlap_groups`. Adding an unread field is the A6 round-1 failure repeated.

## A8 removal list — RECORDED, NOT YET ACTIONED

Recorded here because the review's process finding was that it existed only in an agent report and so
could not be audited. **Nothing below is deleted yet**; items 1-2 require Step 0's attribution data,
which does not exist until Step 0 lands.

| # | candidate | evidence today | blocked on |
|---|---|---|---|
| 1 | per-idea vendor-free discovery arm (`:3206-3211`) | 12-query budget provably exhausted by probe #1's composite order; the run's #1 pick was probed on one self-vocabulary query | Step 0 attribution — and note the reviewer's finding that name-anchored, not discovery, produced the Whitespark hit |
| 2 | per-idea incumbent-anchored arm for grouped ideas (`:3202-3205`) | incumbent `focus` texts are 3-5 generic words; overlap against them is a lottery | Step 0 attribution. **Reviewer contradicts the original justification** — do not delete on the design's reasoning |
| 3 | adjacent + toolbelt probes inside sub-3-idea waves | 8 adjacent + 3 toolbelt calls/run across 4 probe invocations; wave re-runs served candidates that were all later rejected (6 of 19 verdicts, 32%, never shipped) | successor mapping from Step 1 |
| 4 | the second grouper call at `:9333` | same output as a projection of Step-2 groups, one fewer decision point, and removes demotion-blindness (grouper ran **2s** after the sweep hid the Dossier) | Step 2, which itself needs re-measurement at its pre-demotion operating point |

**Explicitly NOT for removal:** the reset-first block (`:3261-3268`) — guards generator-fabricated
parity, a recorded gotcha class. The angle-clear + its re-derivation contract — load-bearing, verified
by the 5%→84.8% regression measurement.

**Step 2 caveat:** the 7/7 stability and 88% absorption were measured on **final** pools. Step 2 runs
the grouper on **pre-demotion** pools, and the live run proves partitions are strongly pool-sensitive
(mid-flow: one group of 4 including RTF; final: 4 disjoint groups). Those numbers do not transfer.

## Operational lessons

- When two analyses agree, check whether they share an instrument before treating agreement as
  confirmation.
- A null result used to cancel work needs the same scrutiny as a positive one. "Ranking needs no work"
  was nearly shipped as a conclusion while the ranking machinery was silently off.
