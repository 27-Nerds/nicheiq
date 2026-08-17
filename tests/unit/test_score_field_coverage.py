"""Fail when a score-bearing field silently stops being populated, or silently vanishes.

WHAT THIS GUARDS
----------------
Two bugs of ONE class landed in a single week, both silent:

  1. `_probe_mechanism_parity` clears `winning_angle` on every idea and nothing re-derives it.
     Type-aware ranking was simply off. Measured on the artifacts (NOT taken on report): the
     collapse lands between 2026-08-13 (100.0%, 26 ideas) and 2026-08-15 (12.9%, 612 ideas),
     with a partial dip on 2026-08-12 (53.1%) that recovered. It survived because every
     analysis treated the checkpoint corpus as one population — and it is a time series across
     code versions, so a step function averages away. Measured control: adding ONE regressed
     run to the 2026-08-13 corpus moves the flat corpus average for `winning_angle` from 95.6%
     to 93.3% (noise) while the latest-date figure moves from 100.0% to 14.3%.
     REPAIRED 2026-08-16 — `unified_solution_crew` re-runs `_classify_idea_angles` after the
     parity probe, and a live end-to-end run landed 13/13 ideas classified. See the honesty
     note at the bottom and `REPAIRED_REGRESSIONS`; the collapse itself stays in
     `KNOWN_STEP_CHANGES` because it happened.
  2. The preview materializer writes `seo_growth_potential_score`; `BaseSolutionIdea` reads
     `seo_scalability_score` and is `extra='ignore'`, so reconstruction produced a
     3-dimension composite wearing a 4-dimension label, moving 4 of 9 ranks.

So there are five groups of tests here:

  A. the score-bearing SET is DERIVED from the code, and demonstrably grows when the model does
  B. no score-shaped value present on disk vanishes when a model is rebuilt from the artifact
  C. per-DATE coverage and step-change pins over the real corpus
  D. a field that stops being written AT ALL (key removed, not value nulled) fails
  F. a field that stops being written on SOME rows (partial key removal) fails — see below

WHAT WAS ADDED IN THIS REVISION: PARTIAL KEY REMOVAL
----------------------------------------------------
Group D closes key removal only in its TOTAL, least likely form. The real 2026-08-15 regression
left 12.9% of values populated, not 0%. Shipped through `model_dump(exclude_none=True)` that
becomes: the key survives on the 13 populated rows and is DELETED from the other 87. Against
that shape every instrument in groups C and D reads clean:

  * coverage counts only rows carrying the key, so populated/present = 13/13 = 100%;
  * the date keeps a non-zero denominator, so it stays eligible and group D stays silent;
  * with coverage pinned at 100% there is no drop, so the step detector sees nothing;
  * `market_fit_score` is a STABLE_FULLY_COVERED field and its gate sees a perfect record.

DEMONSTRATED, not argued. A byte-copy of output/checkpoints was doctored to delete the
`market_fit_score` KEY from 571 of the 612 idea rows on 2026-08-15, leaving 41 populated:

    all 18 tests in this file PASSED, and the probe printed `market_fit_score  100%`
    against `612 ideas` on that date.

WHICH MECHANISM, AND WHY NOT THE OBVIOUS ONE
--------------------------------------------
The obvious repair is a per-date key-PRESENCE series, `tot[(date, field)] / rows_by_date[date]`,
run through the existing step detector. It was built and MEASURED before being rejected:

    step detector over the pooled presence series, last 20 substantial idea dates
      drop >= 0.25 (the threshold in use):  3/20 dates fire   -> 15% false alarm
      drop >= 0.50:                          1/20             ->  5%
      drop >= 0.75:                          0/20, but blind to a 70% key deletion

That is the deleted floor dict's defect with a smaller constant, and this file already died of
a 90% false-alarm gate once. The noise is not run-to-run variance, it is DENOMINATOR MIXING: a
date pools every producer that ran, and producers carry different key sets. 2026-06-28 (69 rows)
-> 2026-06-29 (25 rows) moves EIGHT fields by an identical 90% -> 60%, which is one producer
being absent, not eight regressions.

So the series is reported (`--presence`, `Coverage.presence`) and never gated, and the hole is
closed by two detectors scoped to a unit that has ONE schema, each with a measured zero:

  * `ragged_key_presence` — a key on some rows of one persisted LIST and absent from others.
    A list is one `model_dump` of one model version, so its key set must be uniform; ragged
    presence means the serializer made the key conditional on the value. That IS the
    exclude_none signature, it needs no threshold and no dates. Measured over
    output/checkpoints: 0 ragged (list, field) pairs across 405 lists and 2964 rows.
  * `producer_presence_losses` — the residual: a list whose field is null on EVERY row is
    uniformly key-less, so it is not ragged, and if another producer on the same date still
    writes the key the date never goes dark either. Scoped by (producer, container), where the
    key set is a property of that stage's code. Measured: 0 losses across 208 series, 79 of
    which had a later substantial date on which they could have failed.

THE ACCEPTANCE TEST: FALSE ALARMS, EVERY GATE, LAST 20 REAL RUN DATES
---------------------------------------------------------------------
Each of the last 20 substantial run dates (2026-06-29 .. 2026-08-15) was replayed as if the
corpus ended there, asking whether each gate would have raised a NEW finding the day it landed:

    1 stable-fully-covered                    0/20     0%   [existing, unchanged]
    2 step-change vs KNOWN_STEP_CHANGES       0/20     0%   [existing, unchanged]
    3 gone-dark (eligibility_losses)          1/20     5%   [existing, unchanged — see below]
    4 ragged_key_presence                     0/20     0%   [NEW]
    5 producer_presence_losses                0/20     0%   [NEW]
    6 pooled presence series @0.25            3/20    15%   [REJECTED, not a gate]
    6 pooled presence series @0.50            1/20     5%   [REJECTED]
    6 pooled presence series @0.75            0/20     0%   [REJECTED — blind to a 70% deletion]

Gate 5 reaches 0/20 because it requires the key to be absent from TWO consecutive later dates
of that producer. At one date it fires 1/20, on `red_team_findings`, whose presence record on
`stage_5_3_refinement.json` over 41 dates is `......W.W`: written 08-12, absent 08-13, written
again 08-15. That is a field being rolled out, not one being lost. The price is one run date of
detection latency.

AN UNMEASURED PROPERTY OF AN EXISTING GATE, FOUND BY THAT REPLAY AND LEFT ALONE
-------------------------------------------------------------------------------
Gate 3 is not 0/20. Replayed as-of each date, `eligibility_losses` fires on 2026-08-13 for the
same `red_team_findings` blip, for the same reason: it reports on a single absent date. Its
record on the FULL corpus is clean (zero fields dark), which is what the round that shipped it
measured, and a full-corpus zero is not the same claim as a 0/20 replay. Nobody had checked the
second one; now someone has, and 5% is written down instead of assumed.

It is deliberately NOT changed. Raising its threshold would cut the sensitivity of a detector
whose corpus record is clean, to remove one transient on a field three days old, in a round that
already adds two gates. It is recorded here so the next round decides it on the number rather
than rediscovering it.

WHAT WAS DELETED IN THIS REVISION, AND WHY — do not helpfully re-add it
----------------------------------------------------------------------
This file used to carry `PER_FIELD_LATEST_DATE_FLOOR`: 30 per-field coverage floors, 14 of them
pinned at 1.000, every one of them measured off a SINGLE date (2026-08-16). Replaying the last
20 real run dates as if each were "latest" and asking whether that gate fires:

    18 of 20 dates FAIL.  False-alarm rate 90%.

`audience_fit` was pinned at 1.000 against a real historical range of 0.067-1.000. Twelve of the
thirty entries were `*_score_raw` / `calibration_notes` fields, which
`unified_solution_crew.py:_apply` writes ONLY when the calibration critic returns a non-abstain
value for that criterion — so their "coverage" measures critic participation, not field integrity,
and it moves every single run.

A gate that fires on 90% of legitimate runs does not protect anything. It trains routine
pin-lowering, which is precisely how a real 0.94 -> 0.87 regression gets waved through, or it
gets deleted — and deleting it takes the step-change pins, the history-rewrite refusal and the
dropped-key detection down with it. The good checks die alongside the bad one.

Lowering the constants was not an option either: a lower arbitrary pin is the same defect with a
smaller constant. Two derived-from-history replacements were measured before deleting:

  * floor = the field's historical MINIMUM over prior dates (>= 8 ideas): 40-50% false alarms,
    because for a noisy field every new date has a fair chance of setting a new minimum.
  * floor = median of the trailing 5 dates, minus the same 0.25 the step detector uses:
    30-40% false alarms, and on this corpus every genuine hit it produced was ALREADY an entry
    in `KNOWN_STEP_CHANGES`. It bought nothing and cost a third of all runs.

So the floors are gone. What replaces them is the instrument that already had a demonstrated
record: fields whose coverage has been 100% on EVERY eligible date are gated at 100%
(`STABLE_FULLY_COVERED_*`), and every other derived field is enumerated in `UNGATED_BY_RECORD`
with the spread that disqualifies it. Membership is completeness-checked against
`sfc.score_bearing_idea_fields()`, so a 31st field cannot slip through ungated and unnoticed —
that was the other half of the old design's failure, floors iterating a hand-pinned dict.

    Latest-date gate false-alarm rate over the last 20 real run dates: 90% before, 0% after.

Coverage that FALLS is still caught, by the two mechanisms that measure a field against its own
history rather than against a constant: `test_no_new_coverage_step_change` (date-over-date drop
>= 25%) and `test_no_score_bearing_field_has_gone_dark`. The 2026-08-15 `winning_angle` collapse
is caught by the first; it was never the floor gate that saw it.

HONESTY NOTE — WHICH ARM WAS MEASURED, AND THE REPAIR THAT LANDED ON 2026-08-16
-------------------------------------------------------------------------------
Every number pinned below was measured against the ARTIFACTS ON DISK in `output/checkpoints/`,
which are the frozen output of runs that already happened. The first revision of this file was
written while the `winning_angle` clearing bug was live and recorded it at its real, broken
0.129 — not a coverage claim, a record that coverage was missing — and said that when a
repaired run landed the pins were to be RE-MEASURED, deliberately, rather than relaxed.

That run landed. This revision is that re-measurement, and this is what it rests on:

  * The repair: a live end-to-end run, job `8500b97d`, checkpoint
    `checkpoint_ai_visibility_for_local_businesses_in_london_..._20260816_192930`, mtime
    2026-08-16T20:08:30. `winning_angle` 13/13, `angle_rationale` 13/13,
    `differentiation_locus` 13/13 — 1.000 on all three, against 0.129 / 0.129 / 0.130 pooled
    over 2026-08-15. Same niche and same job family as the runs that carried the bug.
  * It is a repair, not a backfill. The 13 `winning_angle` values are three distinct classified
    labels (`novel_differentiation` x5, `vertical_workflow` x5, `distribution_seo` x3) with 13
    distinct matching rationales, which is a classifier having run — not a constant stamped in.
    `market_fit_claimed_route`, which shares the 08-13 -> 08-15 date pair but not the cause,
    did NOT recover (0.385 on 08-16, inside its own 0.158-0.857 record). A blanket rewrite
    would have moved it too.
  * No evidence was rewritten. All 40 of the 2026-08-15 idea artifacts still carry the key on
    every row and still populate 1-2 of 14-15, with mtimes of 2026-08-15 — older than the
    repaired run. 2026-08-13 is still 14/14. The corpus grew by exactly one run (305 -> 306
    idea runs, 78 -> 79 score runs) and both collapse steps are still OBSERVED, so
    `test_every_known_step_change_is_still_observed_and_explained` passes on the same 23
    entries it did before. Nothing was deleted to make anything green.

WHAT THE PIN BECAME, AND WHY IT IS NOT WEAKER
---------------------------------------------
`UNFIXED_REGRESSION` asserted two things: the collapse is still visible in the corpus (the
history-rewrite refusal), and the latest run date is still BELOW 0.5 (the refusal to claim
coverage we did not have). The first half is unchanged and still asserted. The second half had
to invert — a repaired field cannot go on failing a test for not being broken — so it inverted
into the mirror-image obligation in `REPAIRED_REGRESSIONS`: the repair must STAY repaired.

That is a strictly larger caught set, not a smaller one. Before, a relapse WAS the asserted
state and nothing in this file could fire on it. Now three separate things do, and each one was
checked against the shape it is supposed to catch (see `_repaired_regression_violations`):

  * the collapse pair vanishing from the corpus              -> still fails (unchanged)
  * the repaired date itself being doctored or losing its
    values (i.e. the repair never really landed)             -> fails on the pinned 08-16 value
  * a LATER run relapsing to the cleared shape               -> fails on the latest-date floor,
                                                                 AND as a new step change

The latest-date floor is derived, not invented: it is the worst level this field's OWN known
collapses landed at (`max` over its `KNOWN_STEP_CHANGES` entries, read from the corpus rather
than from the rounded pin). It carries the same `>= 8 ideas` noise guard `step_changes` uses.
Replaying every substantial eligible date of the three repaired fields as if it were the latest,
EXCLUDING the two collapse dates themselves: 0 of 55 fire — the healthy minimum is
0.871 / 0.871 / 0.789 against ceilings of 0.532 / 0.532 / 0.542. It also has no escape hatch:
adding an entry to `KNOWN_STEP_CHANGES` can only RAISE the ceiling, so the exemption list
cannot be grown to talk this gate out of a finding.

`test_a_relapse_of_a_repaired_regression_still_fails` is the positive control: a synthetic
corpus carrying the healthy -> collapse -> repair shape, then doctored back, and the detector
is asserted to name it.

HONESTY NOTE — WHERE THIS ACTUALLY RUNS
---------------------------------------
`output/` is gitignored, so on CI the corpus does not exist and every `@needs_corpus` test
SKIPS. This monitor is a dev-machine tripwire, not a CI gate, and pretending otherwise would be
the same species of decoration it exists to catch. What DOES run everywhere is the arm that
needs no corpus: the SET derivation and its growth demonstration, the classification-completeness
check, the alias resolution check, and the three positive controls that build doctored corpora
under `tmp_path` (undeclared rename, total key removal, `--root` run keying). Those are the tests
that would fail if the machinery itself broke. The corpus-gated tests are the ones that would
fail if the PIPELINE broke, and they can only do that where the artifacts are.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import create_model

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from probes import score_field_coverage as sfc  # noqa: E402

from nicheiq.models.solution_idea import BaseSolutionIdea  # noqa: E402

CORPUS = sfc.CHECKPOINT_ROOT
needs_corpus = pytest.mark.skipif(
    not CORPUS.is_dir(),
    reason=(
        f"no run-artifact corpus at {CORPUS} (output/ is gitignored). The coverage arm of this "
        "file cannot run here; the SET-derivation and reconstruction arms above still do."
    ),
)

# Corpus fingerprint at the time the classification below was measured. A LARGER corpus is fine;
# a much smaller one means someone pruned artifacts and every record-derived claim in this file
# is describing a different population than it was written against.
MEASURED_IDEA_RUNS = 306
MEASURED_SCORE_RUNS = 79

# ---------------------------------------------------------------------------------------
# The derived score-bearing set, CLASSIFIED BY ITS OWN HISTORY. Every field is in exactly one
# bucket and `test_classification_covers_every_derived_field` proves the two buckets tile the
# derived set, so a 31st score field cannot appear and quietly get no gate.
#
# Measured with `python -m probes.score_field_coverage --all` against output/checkpoints on
# 2026-08-17 (306 idea runs, 82 dates / 79 score runs, 45 dates). The previous revision measured
# 305 / 81 / 78 / 44 on 2026-08-16; the difference is the one repaired run described above.
# ---------------------------------------------------------------------------------------

# GATED. Coverage has been 100% on EVERY eligible date these fields have ever had — a
# demonstrated record, not one measurement. "Well-covered may only stay covered", so any date
# below 1.0 is a new regression. False-alarm rate replaying the last 20 real run dates: 0/20,
# which is true by construction: an unbroken record means no date in the corpus violates it.
#
# Re-measured 2026-08-17 with the repaired run in the corpus, and the membership is unchanged:
# idea market_fit_score and technical_feasibility_score are 1.000 across 82 eligible dates each,
# candidate_status across 16; all four SolutionScores members are 1.000 across 45. The repaired
# fields are NOT promoted here — see the note on UNGATED_BY_RECORD_IDEA_FIELDS below.
STABLE_FULLY_COVERED_IDEA_FIELDS = frozenset(
    {"market_fit_score", "technical_feasibility_score", "candidate_status"}
)
STABLE_FULLY_COVERED_SCORE_FIELDS = frozenset(
    {"composite_score", "market_fit_score", "seo_growth_potential_score",
     "technical_feasibility_score"}
)

# NOT GATED on a latest-date floor, each with the measured per-date spread that disqualifies it:
#   {field: (min_frac, max_frac, eligible_dates)} as measured 2026-08-17.
# These three numbers exist so a later round can see the spread before deciding to pin a floor,
# rather than measuring one date and pinning that. Refresh them with
# `python -m probes.score_field_coverage --all`.
#
# They used to be UNASSERTED comments, which meant setting novelty_score to (9.9, -3.0, 99999)
# passed every test in this file — documentation nothing could contradict, which is the same
# defect as a comment describing behaviour the code does not have.
# `test_ungated_spreads_are_consistent_with_the_corpus` now checks them, in a form that is exact
# today and stays correct as runs accumulate: while the eligible-date count is unchanged the
# triple must match the corpus to 3dp, and once new dates land only the monotone bounds are
# required (min can only fall, max can only rise, date count can only grow).
#
# What else IS asserted about this bucket:
#   * it plus the stable bucket exactly tiles the derived set (completeness), and
#   * every member must have a demonstrated dip on some date OTHER than its latest one
#     (`test_ungated_fields_have_a_demonstrated_history_of_dipping`). That is the escape hatch
#     closed: you cannot move a field that has been perfect until today into this bucket to
#     silence a failure that started today.
#
# The `*_raw` and `calibration_notes` rows are not noise-by-accident: unified_solution_crew's
# `_apply` only writes them when the calibration critic returns a non-abstain value for that
# criterion, so their coverage is a measure of critic participation and moves every run.
#
# The three clearing-bug fields stay HERE and not in the stable bucket after the repair. Their
# record is broken — 0.129 / 0.129 / 0.130 on 2026-08-15 is in the corpus forever — so gating
# them at "100% on every eligible date" would be a claim the artifacts contradict. What holds
# them to the repair is `REPAIRED_REGRESSIONS` below, which is scoped to the latest date.
UNGATED_BY_RECORD_IDEA_FIELDS = {
    "adjacent_market_parity": (0.000, 0.750, 18),
    "angle_rationale": (0.129, 1.000, 23),          # REPAIRED 2026-08-16, see REPAIRED_REGRESSIONS
    "audience_fit": (0.067, 1.000, 29),
    "build_feasibility_score": (0.923, 1.000, 31),
    "calibration_notes": (0.789, 1.000, 27),
    "data_feasibility_score": (0.923, 1.000, 31),
    "differentiation_locus": (0.130, 1.000, 21),    # REPAIRED 2026-08-16, same clearing bug
    "duplicate_of": (0.000, 0.083, 14),             # sparse by design: most ideas are not duplicates
    "incumbent_parity": (0.412, 1.000, 20),
    "market_fit_claimed_route": (0.158, 0.857, 10), # NOT repaired: 0.385 on 2026-08-16
    "market_fit_score_raw": (0.789, 1.000, 27),
    "novelty_score": (0.929, 1.000, 70),
    "novelty_score_raw": (0.737, 1.000, 27),
    "obviousness_score": (0.929, 1.000, 34),
    "obviousness_score_raw": (0.579, 1.000, 27),
    "red_team_caveats": (0.065, 0.267, 15),
    "red_team_findings": (0.077, 0.199, 3),         # min fell 0.167 -> 0.077 on the 3rd date
    "red_team_revised": (0.000, 0.097, 15),
    "red_team_verdict": (0.065, 0.267, 15),
    "red_team_vocab_mismatch": (0.000, 0.000, 12),  # never populated on any date in the corpus
    "refine_binding_constraint": (0.511, 0.614, 9),
    "seo_scalability_score": (0.886, 1.000, 82),
    "seo_scalability_score_raw": (0.400, 1.000, 27),
    "solo_dev_feasibility": (0.789, 1.000, 70),
    "solo_dev_feasibility_raw": (0.737, 1.000, 24),
    "technical_feasibility_score_raw": (0.789, 1.000, 27),
    "winning_angle": (0.129, 1.000, 23),            # REPAIRED 2026-08-16: 1.000 on 13/13 ideas
}
UNGATED_BY_RECORD_SCORE_FIELDS = {
    "adjusted_composite_score": (0.000, 1.000, 43),
    "competitive_advantage_score": (0.571, 1.000, 45),
    "keyword_demand_score": (0.000, 1.000, 43),
}

# Every date-over-date collapse the corpus currently contains:
#   (kind, field, from_date, to_date) -> the coverage the LATER date actually landed at.
# A NEW key means a score-bearing field just stopped being populated. A known key whose value
# sank BELOW the pin means a known collapse got worse — keying on the date pair alone would
# have let that through, which was found by doctoring the corpus and watching this pass when
# it should not have. This mapping is the record of what is already known and un-fixed; it is
# not a pass mark.
KNOWN_STEP_CHANGES = {
    ("idea", "adjacent_market_parity", "2026-07-09", "2026-07-10"): 0.424,
    ("idea", "angle_rationale", "2026-08-11", "2026-08-12"): 0.531,
    ("idea", "angle_rationale", "2026-08-13", "2026-08-15"): 0.129,
    ("idea", "audience_fit", "2026-06-27", "2026-06-28"): 0.637,
    ("idea", "audience_fit", "2026-07-02", "2026-07-06"): 0.391,
    ("idea", "audience_fit", "2026-07-11", "2026-07-26"): 0.066,
    ("idea", "audience_fit", "2026-07-31", "2026-08-01"): 0.451,
    ("idea", "audience_fit", "2026-08-02", "2026-08-03"): 0.250,
    ("idea", "differentiation_locus", "2026-08-11", "2026-08-12"): 0.541,
    ("idea", "differentiation_locus", "2026-08-13", "2026-08-15"): 0.130,
    ("idea", "market_fit_claimed_route", "2026-08-13", "2026-08-15"): 0.410,
    ("idea", "obviousness_score_raw", "2026-07-31", "2026-08-01"): 0.578,
    ("idea", "seo_scalability_score_raw", "2026-06-26", "2026-06-28"): 0.580,
    ("idea", "seo_scalability_score_raw", "2026-07-01", "2026-07-02"): 0.553,
    ("idea", "winning_angle", "2026-08-11", "2026-08-12"): 0.531,
    ("idea", "winning_angle", "2026-08-13", "2026-08-15"): 0.129,
    ("scores", "adjusted_composite_score", "2025-11-17", "2025-11-20"): 0.000,
    ("scores", "adjusted_composite_score", "2026-01-23", "2026-02-09"): 0.500,
    ("scores", "adjusted_composite_score", "2026-02-09", "2026-02-12"): 0.000,
    ("scores", "keyword_demand_score", "2025-11-17", "2025-11-20"): 0.000,
    ("scores", "keyword_demand_score", "2026-01-23", "2026-02-09"): 0.300,
    ("scores", "keyword_demand_score", "2026-02-09", "2026-02-12"): 0.000,
    ("scores", "keyword_demand_score", "2026-07-01", "2026-08-02"): 0.375,
}

# KNOWN_STEP_CHANGES is an EXEMPTION LIST, so every entry must earn its place twice over:
#   * it must still be OBSERVED in the corpus (`test_every_known_step_change_is_still_observed`).
#     A fabricated date pair used to pass silently — the old check only asked whether observed
#     steps were a subset of known ones, never the reverse. That reverse direction is also the
#     history-rewrite refusal, generalised from `winning_angle` to all 23 entries: deleting the
#     artifacts that prove a collapse now fails instead of turning the suite green.
#   * the FIELD it names must have a written note below saying what is known about the cause.
# Notes are per field, not per date pair, because the cause is a property of the field. Where
# the cause is not established, the note says so — an honest "unexplained" is a reason; an
# invented mechanism is not.
STEP_CHANGE_NOTES = {
    ("idea", "winning_angle"):
        "`_probe_mechanism_parity` cleared winning_angle on every idea and, from 2026-08-13, "
        "nothing re-derived it. Both date pairs are that one bug: 08-11->08-12 is the partial "
        "dip that recovered, 08-13->08-15 is the collapse. REPAIRED 2026-08-16 by re-running "
        "`_classify_idea_angles` after the parity probe; both pairs stay listed as history.",
    ("idea", "angle_rationale"):
        "Same clearing bug as winning_angle — cleared in the same pass, identical date pairs and "
        "identical landing fractions (0.531 / 0.129). Not an independent regression, and "
        "repaired by the same 2026-08-16 change; it is back to 1.000 on the same run.",
    ("idea", "differentiation_locus"):
        "Same clearing bug as winning_angle; same two date pairs, landing 0.541 / 0.130, and "
        "repaired by the same 2026-08-16 change — 1.000 on 13/13 ideas of the repaired run.",
    ("idea", "audience_fit"):
        "Five separate collapses across six weeks, the widest spread of any field in the corpus "
        "(0.067-1.000). Cause NOT established here; the repo's audience-extraction diagnosis "
        "records the regression as extraction-limited rather than a field-write failure. Listed "
        "so a NEW audience_fit collapse is still distinguishable from these.",
    ("idea", "adjacent_market_parity"):
        "One collapse, 2026-07-09 -> 2026-07-10, landing 0.424, on a date carrying 158 ideas. "
        "Cause not established; the field's whole record is wide (0.000-0.750) so this pair is "
        "recorded rather than explained.",
    ("idea", "market_fit_claimed_route"):
        "2026-08-13 -> 2026-08-15, landing 0.410. Shares its date pair with the clearing bug but "
        "the connection is not established; recorded, not explained.",
    ("idea", "obviousness_score_raw"):
        "A `*_raw` field: unified_solution_crew's `_apply` writes it only when the calibration "
        "critic returns a non-abstain obviousness score, so this measures critic participation "
        "on 2026-08-01, not a lost field write.",
    ("idea", "seo_scalability_score_raw"):
        "Same `*_raw` mechanism as obviousness_score_raw — critic participation, two early date "
        "pairs in 2026-06/07.",
    ("scores", "adjusted_composite_score"):
        "Three collapses to 0.000/0.500 in 2025-11 to 2026-02, when the adjusted-composite stage "
        "was intermittently not running at all. Cause not established beyond that.",
    ("scores", "keyword_demand_score"):
        "Four collapses, including two to 0.000 in the same 2025-11/2026-02 window as "
        "adjusted_composite_score. keyword_demand depends on the DataForSEO probe, which is "
        "cost-gated and does not run on every job.",
}

# The regression this file was written because of, AND the run that repaired it. This replaced
# `UNFIXED_REGRESSION = ("idea", "winning_angle", "2026-08-13", "2026-08-15")`, which asserted
# the collapse was still visible AND that the latest run date was still below 0.5. The first
# clause is kept verbatim below; the second inverted when the repair landed, into the obligation
# that the repair holds. See the honesty note for why that is a larger caught set, not a smaller
# one, and `_repaired_regression_violations` for the three shapes it fires on.
#
#   (kind, field) -> (collapse_from, collapse_to, repaired_date, repaired_frac)
#
# `repaired_frac` is a measurement of a FROZEN date, so it can never false-alarm on a future
# run; it is the assertion that the repair evidence itself is still on disk and still says what
# it said. Measured 2026-08-17 on job 8500b97d's checkpoint, 13 ideas, all three fields 13/13.
REPAIRED_REGRESSIONS = {
    ("idea", "winning_angle"): ("2026-08-13", "2026-08-15", "2026-08-16", 1.000),
    ("idea", "angle_rationale"): ("2026-08-13", "2026-08-15", "2026-08-16", 1.000),
    ("idea", "differentiation_locus"): ("2026-08-13", "2026-08-15", "2026-08-16", 1.000),
}

_CACHE: dict = {}


def _repaired_regression_violations(cov, observed, kind, field, record, known=None) -> list[str]:
    """Everything `REPAIRED_REGRESSIONS` claims about one field, checked against a corpus.

    Split out from the test so the positive control below can run the SAME code against a
    synthetic corpus doctored back to the broken shape. A checker only its own happy path ever
    exercises is a checker nobody has seen fire.

    Three independent failures, each named:
      1. the collapse is no longer observable  -> the evidence was rewritten or deleted;
      2. the repaired date no longer measures what it measured -> the repair evidence moved;
      3. the LATEST substantial eligible date has fallen back to (or below) the worst level this
         field's own known collapses landed at -> the regression came back on a later run.

    (3)'s ceiling is read out of the corpus via `observed`, not out of the rounded pin in
    `KNOWN_STEP_CHANGES`, so a relapse that lands at exactly the historical fraction still fires.
    """
    known = KNOWN_STEP_CHANGES if known is None else known
    collapse_from, collapse_to, repaired_date, repaired_frac = record
    bad = []

    if (kind, field, collapse_from, collapse_to) not in observed:
        bad.append(
            f"{kind}.{field}: the {collapse_from} -> {collapse_to} collapse is no longer visible "
            "in the corpus. The repair does not erase the history — either the artifacts that "
            "recorded it were removed, or the step detector stopped seeing it. Neither may pass."
        )

    if repaired_date not in cov.eligible_dates(field):
        bad.append(
            f"{kind}.{field}: the repaired run date {repaired_date} is not an eligible date any "
            "more, so this file's only evidence that the repair ever landed is gone."
        )
    elif abs(cov.frac(repaired_date, field) - repaired_frac) > 5e-4:
        bad.append(
            f"{kind}.{field}: the repaired date {repaired_date} measured {repaired_frac:.3f} "
            f"when it was pinned and measures {cov.frac(repaired_date, field):.3f} now. A frozen "
            "run does not change on its own."
        )

    landings = [
        frac for key, frac in observed.items()
        if key[0] == kind and key[1] == field and key in known
    ]
    # Same noise guard the step detector uses (`step_changes`): a date carrying a handful of
    # ideas can sit under any floor by arithmetic alone. One unclassified idea on a 2-idea run
    # is 0.500, which would clear the ceiling on nothing but sample size.
    dates = [d for d in cov.eligible_dates(field) if cov.tot[(d, field)] >= sfc.STEP_MIN_IDEAS]
    if landings and dates:
        ceiling = max(landings)
        latest = dates[-1]
        if cov.frac(latest, field) <= ceiling + 1e-9:
            bad.append(
                f"{kind}.{field}: the latest run date {latest} is at "
                f"{cov.frac(latest, field):.3f}, at or below the {ceiling:.3f} that this field's "
                "own known collapses landed at. It was repaired on "
                f"{repaired_date} and has relapsed — re-measure the pipeline, not this pin."
            )
    return bad


def _built():
    if "built" not in _CACHE:
        _CACHE["built"] = sfc.build(CORPUS)
    return _CACHE["built"]


def _observed_step_changes() -> dict[tuple[str, str, str, str], float]:
    ideas, scores = _built()
    out: dict[tuple[str, str, str, str], float] = {}
    for cov, fields, kind in (
        (ideas, sfc.score_bearing_idea_fields(), "idea"),
        (scores, sfc.score_bearing_scores_fields(), "scores"),
    ):
        for field in sorted(fields):
            for prev, cur, _a, after in sfc.step_changes(cov, field):
                out[(kind, field, prev, cur)] = after
    return out


# =======================================================================================
# Group 0 — this file must actually load and run. An import error resolves to a silent
# "PASS (0) FAIL (0)" in some harnesses, which is green and means nothing.
# =======================================================================================
def test_this_file_collects_every_test_it_declares():
    """Compare tests on disk to tests pytest can actually collect from this file."""
    source = Path(__file__).read_text(encoding="utf-8")
    declared = sorted(
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )
    assert len(declared) == 26, (
        f"this file declares {len(declared)} tests, the pinned count is 26 — update the pin "
        f"deliberately, so a test that quietly stops existing is not mistaken for a pass. "
        f"declared={declared}"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov",
         "-p", "no:cacheprovider", str(Path(__file__).resolve())],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"this file does not collect:\n{proc.stdout}\n{proc.stderr}"
    collected = {
        name for name in declared
        if f"::{name}" in proc.stdout or f"<Function {name}>" in proc.stdout
    }
    assert collected == set(declared), (
        "pytest collected a different set of tests than this file declares — the missing ones "
        f"would report as neither pass nor fail: missing={sorted(set(declared) - collected)}"
    )


# =======================================================================================
# Group A — the score-bearing SET is derived, not hand-listed
# =======================================================================================
def test_score_bearing_set_is_derived_from_the_code():
    fields = sfc.score_bearing_idea_fields()
    # The three derivation rules must each be contributing. `winning_angle` and the four
    # composite dimensions come from the ranker; `incumbent_parity` has no `_score` suffix and
    # is reachable ONLY through idea_carryover._RE_EARNED.
    for expected in (
        "winning_angle",
        "incumbent_parity",
        "market_fit_score",
        "technical_feasibility_score",
        "novelty_score",
        "seo_scalability_score",
        "build_feasibility_score",
    ):
        assert expected in fields, f"{expected} fell out of the derived score-bearing set"
    # Required fields cannot vanish silently (pydantic would refuse), so they are out of scope.
    assert "solution_name" not in fields
    assert "description" not in fields
    assert len(fields) >= 25, f"derivation collapsed to {len(fields)} fields: {sorted(fields)}"

    scores = sfc.score_bearing_scores_fields()
    assert "composite_score" in scores
    assert {"market_fit_score", "technical_feasibility_score", "competitive_advantage_score",
            "seo_growth_potential_score"} <= scores, "a composite INPUT dropped out of the set"


def test_derived_set_picks_up_a_new_score_field_without_being_told():
    """A hand-written list would not grow. This is the demonstration that the set is live."""
    before = sfc.score_bearing_idea_fields()
    assert "regulatory_risk_score" not in before
    extended = create_model(
        "ExtendedIdea",
        __base__=BaseSolutionIdea,
        regulatory_risk_score=(float | None, None),
    )
    after = sfc.score_bearing_idea_fields(extended)
    assert "regulatory_risk_score" in after, (
        "a new *_score field on the model did NOT enter the derived set — the derivation has "
        "degenerated into a hand-written list and will not notice the next field either"
    )
    assert before < after


# =======================================================================================
# Group B — no score-shaped value present on disk may vanish on reconstruction (bug #2)
# =======================================================================================
def test_declared_model_boundary_aliases_actually_resolve():
    """The declared renames must name real BaseSolutionIdea fields, or they declare nothing.

    `score_helpers` documents seo_scalability_score -> seo_growth_potential_score as an
    INTENTIONAL boundary. Declaring it is what keeps it intentional instead of silent.
    """
    model_fields = set(BaseSolutionIdea.model_fields)
    assert sfc.DECLARED_MODEL_BOUNDARY_ALIASES, "the alias list is empty; nothing declares a boundary"
    for persisted, (target, reason) in sfc.DECLARED_MODEL_BOUNDARY_ALIASES.items():
        assert target in model_fields, (
            f"alias {persisted!r} -> {target!r} points at a field BaseSolutionIdea does not "
            "have; the boundary is undeclared again"
        )
        assert persisted not in model_fields, (
            f"{persisted!r} is now a real model field — the alias is obsolete and hides the "
            "real value"
        )
        # An exemption with no written reason is an exemption nobody can review. This is the
        # cheapest half of "a bogus entry must not pass": a fabricated alias has nothing to say.
        assert isinstance(reason, str) and len(reason.split()) >= 12, (
            f"alias {persisted!r} -> {target!r} carries no usable reason. Every entry in this "
            "dict must say which code declares the rename and what evidence shows it is needed."
        )
    assert sfc.DECLARED_ALIAS_TARGETS == {
        k: v[0] for k, v in sfc.DECLARED_MODEL_BOUNDARY_ALIASES.items()
    }, "DECLARED_ALIAS_TARGETS drifted from the alias table the detector is documented against"


@needs_corpus
def test_every_declared_alias_earns_its_exemption():
    """A stale exemption must FAIL, not pass. This is where a corpus scan goes to die.

    An entry in the alias table tells `undeclared_dropped_keys` to stay quiet about a key. If no
    artifact anywhere in the corpus carries a VALUE under that key, the entry silences nothing
    observable — and an entry that silences nothing observable is indistinguishable from one
    somebody invented. That is how `competitive_advantage_score -> novelty_score` sat here: the
    rename is real and documented in score_helpers, but on idea rows the key is present 484 times
    and populated ZERO times, so `undeclared_dropped_keys` (which only looks at populated values)
    never once consulted the entry. It has been removed; see the comment in the probe.
    """
    populated = {key: 0 for key in sfc.DECLARED_MODEL_BOUNDARY_ALIASES}
    rows_seen = 0
    for _date, _run, _path, _container, rows, kind in sfc.iter_artifacts(CORPUS):
        if kind != "idea":
            continue
        for row in rows:
            rows_seen += 1
            for key in populated:
                if key in row and sfc._is_populated(row[key]):
                    populated[key] += 1
    assert rows_seen, "no idea rows scanned — the scan itself is broken, not the aliases"
    dead = sorted(k for k, n in populated.items() if n == 0)
    assert not dead, (
        f"declared model-boundary aliases that exempt nothing observable, over {rows_seen} idea "
        f"rows: {dead}. Each one is a standing permission to drop a score-shaped key, granted "
        "against no evidence that the key is ever written. Delete it; if the producer starts "
        "writing that key, the dropped-key detector will fire and it can be re-added WITH the "
        f"artifact that proves it is needed. (populated counts: {populated})"
    )


def test_dropped_key_detector_fires_on_an_undeclared_score_rename(tmp_path):
    """Positive control: the detector must SEE a violation, or it is decoration.

    The idea payload is generated from BaseSolutionIdea itself, never hand-copied from an
    artifact, so it cannot drift out of sync with the model.
    """
    required = {
        name: (["x"] if getattr(field.annotation, "__origin__", None) is list else "x")
        for name, field in BaseSolutionIdea.model_fields.items()
        if field.is_required()
    }
    idea = BaseSolutionIdea(
        **required, market_fit_score=0.7, seo_scalability_score=0.6
    ).model_dump()
    clean = tmp_path / "clean" / "checkpoint_control_20260816_000000"
    clean.mkdir(parents=True)
    (clean / "stage_5_3_refinement.json").write_text(json.dumps({"solution_ideas": [idea]}))
    assert sfc.undeclared_dropped_keys(tmp_path / "clean") == {}, (
        "the detector reports a violation on a payload built from the model itself"
    )

    violating = dict(idea)
    violating.pop("seo_scalability_score")
    violating["seo_reach_potential_score"] = 0.6  # a rename nobody declared
    dirty = tmp_path / "dirty" / "checkpoint_control_20260816_000000"
    dirty.mkdir(parents=True)
    (dirty / "stage_5_3_refinement.json").write_text(json.dumps({"solution_ideas": [violating]}))
    found = sfc.undeclared_dropped_keys(tmp_path / "dirty")
    assert "seo_reach_potential_score" in found, (
        "an undeclared score-shaped key survived the detector — this is exactly the shape of "
        f"the seo_growth_potential_score bug and it was not seen. found={found}"
    )
    rebuilt = BaseSolutionIdea.model_validate(violating)
    assert rebuilt.seo_scalability_score is None, (
        "sanity: the point is that extra='ignore' really does drop it"
    )


@needs_corpus
def test_no_score_shaped_key_on_disk_is_silently_dropped():
    """Over the REAL corpus, loaded from disk, never from a copied fixture."""
    found = sfc.undeclared_dropped_keys(CORPUS)
    assert found == {}, (
        "score-shaped keys are present in run artifacts and vanish when BaseSolutionIdea is "
        "rebuilt from them (extra='ignore'). Every composite computed from those artifacts is "
        "missing a dimension while still being labelled a full composite. Declare each in "
        f"probes/score_field_coverage.DECLARED_MODEL_BOUNDARY_ALIASES: "
        f"{ {k: v[:2] for k, v in found.items()} }"
    )


# =======================================================================================
# Group C — per-DATE coverage over the real corpus
# =======================================================================================
@needs_corpus
def test_corpus_is_the_population_the_pins_were_measured_against():
    ideas, scores = _built()
    assert len(ideas.all_runs) >= MEASURED_IDEA_RUNS * 0.9, (
        f"idea corpus shrank from {MEASURED_IDEA_RUNS} to {len(ideas.all_runs)} runs; the pins "
        "below are measuring a different population than they were written against"
    )
    assert len(scores.all_runs) >= MEASURED_SCORE_RUNS * 0.9
    assert len(ideas.dates) >= 60, "the corpus stopped being a time series"


@needs_corpus
def test_eligibility_is_reported_and_never_padded():
    """A run predating a feature never had the field and must not be averaged in.

    winning_angle is the case in point: only ~47% of runs are eligible, so scoring it over the
    whole corpus would divide a live regression by a denominator of runs that never had it.
    """
    ideas, _ = _built()
    eligible = len(ideas.eligible_runs["winning_angle"])
    total = len(ideas.all_runs)
    assert 0 < eligible < total, (
        "winning_angle eligibility is no longer partial — either every run now carries it "
        "(then re-measure) or the eligibility filter broke"
    )
    # Ineligible runs contribute nothing to any date bucket.
    for date in ideas.dates:
        pop, tot = ideas.pop[(date, "winning_angle")], ideas.tot[(date, "winning_angle")]
        assert pop <= tot
        assert tot == 0 or ideas.frac(date, "winning_angle") is not None
    # And the eligible ideas are a strict subset of all ideas seen.
    assert sum(ideas.tot[(d, "winning_angle")] for d in ideas.dates) < sum(
        ideas.tot[(d, "market_fit_score")] for d in ideas.dates
    ), "winning_angle is being counted over the same denominator as an always-present field"


def test_classification_covers_every_derived_field():
    """The gates iterate the derived SET, so a 31st score field cannot appear ungated.

    This is the completeness assertion the old floor dict never had: it was hand-pinned, so a
    field added to BaseSolutionIdea tomorrow entered `score_bearing_idea_fields()` (the derivation
    is live and proven live above) and then got NO gate at all, silently. Whenever the defect is
    "some member of a set violates a property", the fix enumerates the SET.

    Needs no corpus, so this half runs on CI where the artifacts do not exist.
    """
    for derived, stable, ungated, label in (
        (sfc.score_bearing_idea_fields(), STABLE_FULLY_COVERED_IDEA_FIELDS,
         UNGATED_BY_RECORD_IDEA_FIELDS, "idea"),
        (sfc.score_bearing_scores_fields(), STABLE_FULLY_COVERED_SCORE_FIELDS,
         UNGATED_BY_RECORD_SCORE_FIELDS, "scores"),
    ):
        classified = set(stable) | set(ungated)
        assert not (set(stable) & set(ungated)), (
            f"{label}: a field is both gated and ungated: {sorted(set(stable) & set(ungated))}"
        )
        unclassified = sorted(set(derived) - classified)
        assert not unclassified, (
            f"{label}: {len(unclassified)} score-bearing field(s) are in the derived set and in "
            f"neither bucket, so nothing gates them: {unclassified}. Measure the field's per-date "
            "record with `python -m probes.score_field_coverage --all` and put it in "
            "STABLE_FULLY_COVERED_* if it has an unbroken 100% record, otherwise in "
            "UNGATED_BY_RECORD_* with its measured spread."
        )
        phantom = sorted(classified - set(derived))
        assert not phantom, (
            f"{label}: classified field(s) that are not in the derived score-bearing set at all: "
            f"{phantom}. Either the model dropped them or the names are fabricated."
        )


@needs_corpus
def test_ungated_fields_have_a_demonstrated_history_of_dipping():
    """You may not park a field in the ungated bucket to silence a failure that started today.

    A field belongs there because its coverage genuinely moves — demonstrated by a date OTHER
    than its most recent one scoring below 100%. If the only sub-100% date is the latest one,
    that is a regression that just landed, and moving the field out of the gated bucket is how
    a monitor gets talked out of its own finding.
    """
    ideas, scores = _built()
    bad = []
    for cov, ungated, label in (
        (ideas, UNGATED_BY_RECORD_IDEA_FIELDS, "idea"),
        (scores, UNGATED_BY_RECORD_SCORE_FIELDS, "scores"),
    ):
        for field in sorted(ungated):
            dates = cov.eligible_dates(field)
            assert dates, (
                f"{label}.{field} is classified as ungated but has no eligible run date at all — "
                "was it removed from the model, or is the name wrong?"
            )
            earlier = [d for d in dates[:-1] if cov.frac(d, field) < 1.0]
            if not earlier:
                bad.append(f"{label}.{field} (latest={dates[-1]} at "
                           f"{cov.frac(dates[-1], field):.3f}, every earlier date 100%)")
    assert not bad, (
        "field(s) sitting in UNGATED_BY_RECORD_* whose record is unbroken except on the most "
        "recent date. That is not a noisy field, that is a fresh regression:\n  "
        + "\n  ".join(bad)
    )


@needs_corpus
def test_fields_with_an_unbroken_record_stay_fully_covered():
    """'Well-covered may only stay covered' — for these, every eligible date must be 100%."""
    ideas, scores = _built()
    for cov, fields, label in (
        (ideas, STABLE_FULLY_COVERED_IDEA_FIELDS, "idea"),
        (scores, STABLE_FULLY_COVERED_SCORE_FIELDS, "scores"),
    ):
        for field in sorted(fields):
            bad = [
                (d, round(cov.frac(d, field), 3))
                for d in cov.eligible_dates(field)
                if cov.frac(d, field) < 1.0
            ]
            assert not bad, (
                f"{label}.{field} had a perfect record across every eligible date and now does "
                f"not: {bad}"
            )


@needs_corpus
def test_no_new_coverage_step_change():
    """A step change is the signature of both bugs. Any NEW one is an unwatched field-loss.

    A flat per-corpus average cannot produce this test: the corpus-wide mean for winning_angle
    is 63.7%, which reads as a feature still rolling out, not as a field that stopped working.
    """
    observed = _observed_step_changes()
    new = sorted(set(observed) - set(KNOWN_STEP_CHANGES))
    assert not new, (
        "a score-bearing field's populated fraction collapsed between two run dates and nothing "
        "else noticed:\n  "
        + "\n  ".join(f"{k}.{f}: {a} -> {b} ({observed[(k, f, a, b)]:.1%})" for k, f, a, b in new)
        + "\nRun `python -m probes.score_field_coverage` for the per-date table."
    )
    worse = [
        f"{k}.{f}: {a} -> {b} landed at {observed[(k, f, a, b)]:.3f}, pinned {floor:.3f}"
        for (k, f, a, b), floor in sorted(KNOWN_STEP_CHANGES.items())
        if (k, f, a, b) in observed and observed[(k, f, a, b)] + 1e-6 < floor
    ]
    assert not worse, "a known collapse got deeper — it is not the same regression:\n  " + "\n  ".join(worse)


@needs_corpus
def test_every_known_step_change_is_still_observed_and_explained():
    """The exemption list checked in the direction it was never checked in.

    `test_no_new_coverage_step_change` only asks whether the OBSERVED steps are a subset of the
    known ones. That lets two things through: an entry naming a date pair the corpus does not
    contain (a fabricated exemption, which then also pre-authorises a real future collapse on
    those dates), and the deletion of the artifacts that prove a known collapse — which under a
    subset check makes the suite greener, exactly the wrong incentive. Asserting the reverse
    inclusion is the history-rewrite refusal generalised from `winning_angle` to every entry.
    """
    observed = _observed_step_changes()
    vanished = sorted(set(KNOWN_STEP_CHANGES) - set(observed))
    assert not vanished, (
        "KNOWN_STEP_CHANGES entries that the corpus does not contain:\n  "
        + "\n  ".join(f"{k}.{f}: {a} -> {b} (pinned {KNOWN_STEP_CHANGES[(k, f, a, b)]:.3f})"
                      for k, f, a, b in vanished)
        + "\nEither the entry is fabricated — in which case it is a standing permission for a "
          "collapse nobody has seen — or the artifacts that recorded the collapse were removed. "
          "Neither may pass. If a repaired run genuinely superseded one, say so in the honesty "
          "note and re-measure rather than deleting the line."
    )
    unexplained = sorted({(k, f) for k, f, _a, _b in KNOWN_STEP_CHANGES} - set(STEP_CHANGE_NOTES))
    assert not unexplained, (
        f"known step changes with no written note about the cause: {unexplained}. Every exempted "
        "field needs a reason a reviewer can check; 'cause not established' is an acceptable "
        "reason, an invented mechanism is not."
    )
    stale_notes = sorted(set(STEP_CHANGE_NOTES) - {(k, f) for k, f, _a, _b in KNOWN_STEP_CHANGES})
    assert not stale_notes, (
        f"notes for fields that no longer appear in KNOWN_STEP_CHANGES: {stale_notes}"
    )
    for key, note in STEP_CHANGE_NOTES.items():
        assert len(note.split()) >= 12, f"the note for {key} says nothing checkable: {note!r}"


# =======================================================================================
# Group D — total key removal. Coverage cannot see this; it needs its own detector.
# =======================================================================================
def _synthetic_corpus(base: Path, date_dirs: dict[str, list[dict]]) -> Path:
    """Write {`YYYYMMDD` -> [idea dicts]} as a checkpoint corpus and return the root."""
    base.mkdir(parents=True, exist_ok=True)
    for i, (stamp, rows) in enumerate(sorted(date_dirs.items())):
        run = base / f"checkpoint_{i:08d}-0000-0000-0000-000000000000_{stamp}_000000"
        run.mkdir(parents=True, exist_ok=True)
        (run / "stage_5_3_refinement.json").write_text(json.dumps({"solution_ideas": rows}))
    return base


def test_gone_dark_detector_fires_when_a_key_is_removed_rather_than_nulled(tmp_path):
    """Positive control for the inverted padded-denominator trap.

    Eligibility is inferred from key presence, so deleting a key outright reads as "the schema
    never carried this field" and the date drops out of the denominator instead of scoring 0%.
    Verified on the real corpus before this detector existed: removing the `winning_angle` KEY
    from all 612 ideas on the 2026-08-15 date left 12 of 12 tests passing. Nulling the same
    values fails a coverage check; removing them did not. `model_dump(exclude_none=True)` is one
    line of producer code away from doing exactly that.
    """
    fields = frozenset({"winning_angle"})
    full = [{"solution_name": f"i{n}", "winning_angle": "gap"} for n in range(12)]

    intact = sfc.build(_synthetic_corpus(tmp_path / "intact", {
        "20260810": full, "20260812": full, "20260815": full,
    }))[0]
    assert sfc.eligibility_losses(intact, fields) == [], (
        "the detector reports a loss on a corpus where nothing was lost"
    )

    # Same corpus, but the newest date's rows never carry the key at all.
    stripped = [{k: v for k, v in row.items() if k != "winning_angle"} for row in full]
    doctored = sfc.build(_synthetic_corpus(tmp_path / "doctored", {
        "20260810": full, "20260812": full, "20260815": stripped,
    }))[0]
    losses = sfc.eligibility_losses(doctored, fields)
    assert [(f, last) for f, last, _ in losses] == [("winning_angle", "2026-08-12")], (
        f"a field that stopped being written entirely was not detected: {losses}"
    )
    assert losses[0][2] == ["2026-08-15"]

    # And prove the blindness it closes: coverage alone still sees a clean 100% everywhere.
    assert doctored.eligible_dates("winning_angle") == ["2026-08-10", "2026-08-12"]
    assert all(doctored.frac(d, "winning_angle") == 1.0
               for d in doctored.eligible_dates("winning_angle")), (
        "the point of this test is that every per-date coverage number stays perfect while the "
        "field is gone; if that is no longer true, re-derive what the detector is for"
    )


@needs_corpus
def test_no_score_bearing_field_has_gone_dark():
    """Over the real corpus, iterating the DERIVED set, not a hand-pinned list.

    Re-measured 2026-08-17: zero fields have gone dark across 65 substantial idea dates and 11
    score dates. There is nothing to grandfather, so this is a hard assertion with no allowlist —
    an allowlist here would be the same tripwire-that-disables-itself shape as the old floors.
    """
    ideas, scores = _built()
    dark = []
    for cov, fields, label in (
        (ideas, sfc.score_bearing_idea_fields(), "idea"),
        (scores, sfc.score_bearing_scores_fields(), "scores"),
    ):
        for field, last, missing in sfc.eligibility_losses(cov, fields):
            dark.append(f"{label}.{field}: last written {last}, absent from {len(missing)} later "
                        f"date(s) starting {missing[0]} ({cov.rows_by_date[missing[0]]} ideas)")
    assert not dark, (
        "score-bearing field(s) stopped being written to the artifacts altogether. Coverage "
        "cannot see this — it calls those dates ineligible and averages them out of existence, "
        "which is the padded-denominator trap inverted:\n  " + "\n  ".join(dark)
    )


# =======================================================================================
# Group F — PARTIAL key removal. Coverage reads 100% straight through it and group D,
# which only sees TOTAL removal, stays silent. See the module docstring.
# =======================================================================================
def test_ragged_key_presence_fires_on_partial_key_removal(tmp_path):
    """Positive control for the 13-of-100 shape, and proof of what it closes.

    Built to the shape the real bug takes: on the newest date the field is populated on 13 of
    100 rows and the KEY IS DELETED from the other 87. Every assertion below that is about the
    OLD instruments reading clean is the reason this detector had to exist.
    """
    fields = frozenset({"market_fit_score"})
    full = [{"solution_name": f"i{n}", "market_fit_score": 0.8} for n in range(100)]
    # exclude_none: the key survives exactly where the value did.
    partial = [dict(r) if n < 13 else {"solution_name": f"i{n}"} for n, r in enumerate(full)]

    root = _synthetic_corpus(tmp_path / "partial", {
        "20260810": full, "20260812": full, "20260815": partial,
    })
    ragged = sfc.ragged_key_presence(root)
    assert [(k, f, c, p, t, pop) for k, f, _a, c, p, t, pop in ragged] == [
        ("idea", "market_fit_score", "solution_ideas", 13, 100, 13)
    ], f"partial key removal was not detected: {ragged}"

    # ---- and now the blindness it closes, asserted rather than asserted-about ----
    cov = sfc.build(root)[0]
    assert cov.frac("2026-08-15", "market_fit_score") == 1.0, (
        "the whole point: coverage reads a flawless 100% because it counts only rows that "
        "carry the key, and those are exactly the 13 that kept their value"
    )
    assert cov.tot[("2026-08-15", "market_fit_score")] == 13
    assert cov.rows_by_date["2026-08-15"] == 100
    assert sfc.eligibility_losses(cov, fields) == [], (
        "the gone-dark detector sees nothing — the date is still eligible, so removal has to "
        "be TOTAL before group D fires"
    )
    assert sfc.step_changes(cov, "market_fit_score") == [], (
        "no step either: coverage never left 100%"
    )
    # The pooled presence series WOULD see it — it is the gate's false-alarm rate, not its
    # blindness, that disqualifies it. Recorded here so the tradeoff stays visible.
    assert cov.presence("2026-08-12", "market_fit_score") == 1.0
    assert cov.presence("2026-08-15", "market_fit_score") == 0.13


def test_producer_presence_loss_fires_when_one_producer_stops_writing_a_key(tmp_path):
    """Positive control for the residual raggedness leaves: UNIFORM removal by one producer.

    If the nulled field is null on EVERY row of a list, `exclude_none` drops the key from all
    of them, so the list is not ragged. And while a DIFFERENT producer on the same date still
    writes the key, the date never goes dark. Both existing detectors are silent; this one is not.

    The absence has to span TWO consecutive later dates, which is not a taste — see
    `producer_presence_losses`: at one date the gate false-alarms on 1 of the last 20 real run
    dates, at two it does not. So this corpus has four dates, and the single-date variant below
    is asserted NOT to fire.
    """
    fields = frozenset({"winning_angle"})
    rows = [{"solution_name": f"i{n}", "winning_angle": "gap"} for n in range(12)]
    stripped = [{"solution_name": f"i{n}"} for n in range(12)]

    def corpus(name, plan):
        root = tmp_path / name
        for stamp, second in plan:
            run = root / f"checkpoint_{stamp}-0000-0000-0000-000000000000_{stamp}_000000"
            run.mkdir(parents=True)
            # Producer A keeps writing the key on every date.
            (run / "stage_5_3_refinement.json").write_text(json.dumps({"solution_ideas": rows}))
            # Producer B stops — uniformly, so no list is ragged.
            (run / "stage_7_3_refinement.json").write_text(json.dumps({"solution_ideas": second}))
        return root

    root = corpus("stopped", [("20260810", rows), ("20260812", rows),
                              ("20260814", stripped), ("20260815", stripped)])
    assert sfc.ragged_key_presence(root) == [], (
        "uniform removal must NOT be ragged — if it were, this test would be re-testing the "
        "previous detector instead of the gap between them"
    )
    cov = sfc.build(root)[0]
    assert sfc.eligibility_losses(cov, fields) == [], (
        "producer A still writes the key on every date, so no date is ineligible and the "
        "gone-dark detector cannot see producer B stop"
    )
    assert cov.frac("2026-08-15", "winning_angle") == 1.0, "coverage is clean too"

    losses = sfc.producer_presence_losses(root)
    assert losses == [
        ("idea", "winning_angle", "stage_7_3_refinement.json", "solution_ideas",
         "2026-08-12", ["2026-08-14", "2026-08-15"])
    ], f"a producer stopped writing a score-bearing key and nothing saw it: {losses}"

    # One absent date is a run that did not exercise the stage, not a producer that stopped.
    blip = corpus("blip", [("20260810", rows), ("20260812", rows),
                           ("20260814", stripped), ("20260815", rows)])
    assert sfc.producer_presence_losses(blip) == [], (
        "a single absent date must not fire: that shape is `red_team_findings` on 2026-08-13 "
        "in the real corpus, written 08-12, absent 08-13, written again 08-15"
    )


def test_producer_normalisation_keeps_uuid_named_artifacts_in_one_series(tmp_path):
    """`preview_report_<uuid>.json` must be ONE producer, not one series per run.

    Without normalisation every preview artifact is its own single-date scope, and a series of
    length one can never show a loss — the detector above would have looked clean by being
    vacuous over the 22 dates that producer covers. Measured on the real corpus: normalising
    takes the scope count from 74 (7 multi-date) to 10 (8 multi-date) and the number of series
    that could possibly fail from 62 to 79.
    """
    a = Path("preview_report_03d20ff6-3973-48b6-b414-42a71883225d.json")
    b = Path("preview_report_056b2c68-8166-42da-90cf-ef265ac00000.json")
    assert sfc.producer_of(a) == sfc.producer_of(b) == "preview_report_<id>.json"
    assert sfc.producer_of(Path("stage_5_3_refinement.json")) == "stage_5_3_refinement.json"
    assert sfc.producer_of(Path("checkpoint_20260815_120000.json")) == "checkpoint_<ts>.json"


@needs_corpus
def test_no_artifact_has_ragged_key_presence():
    """Over the real corpus. Re-measured 2026-08-17: 0 across 407 persisted lists / 2990 rows.

    Nothing to grandfather, so no allowlist — an allowlist here would be the same
    tripwire-that-disables-itself shape as the deleted floor dict.
    """
    ragged = sfc.ragged_key_presence(CORPUS)
    assert ragged == [], (
        "a score-bearing key is present on some rows of a persisted list and absent from "
        "others. A list is one model_dump of one model version, so its key set must be "
        "uniform; ragged presence means the serializer made the key conditional on the value "
        "(`model_dump(exclude_none=True)`). Coverage reads 100% straight through this:\n  "
        + "\n  ".join(f"{k}.{f}: {p}/{t} rows of {c} carry it ({pop} populated) in {a}"
                      for k, f, a, c, p, t, pop in ragged[:10])
    )


@needs_corpus
def test_no_producer_has_stopped_writing_a_score_bearing_key():
    """Over the real corpus. Measured 2026-08-16: 0 losses across 208 (producer, container,
    field) series, 79 of which had at least one later substantial date on which they could
    have failed — so the zero was a record, not a vacuum.

    RE-MEASURED 2026-08-17, and the second half of that claim no longer holds. Still 0 losses,
    still 208 (producer, container, field) pairs of which 82 have ever been written — but the
    repaired run wrote every one of those 82 on the newest substantial date of its scope, so
    ZERO series are currently in the absent-from-a-later-date state at all. Today's zero is a
    description of a complete corpus, not a set of series that survived an opportunity to fail.
    Only 2 of the 82 have ever had an absent substantial date after their first write. The gate
    is not weaker than it was; its denominator is, and saying so is cheaper than letting the
    next reader inherit "79" as if it were still true."""
    losses = sfc.producer_presence_losses(CORPUS)
    assert losses == [], (
        "a producer wrote a score-bearing key and then stopped, while other producers on the "
        "same dates kept writing it — so the date never went dark and coverage never dipped:\n  "
        + "\n  ".join(f"{k}.{f}: {p}/{c} last wrote it {last}, absent from {len(m)} later "
                      f"date(s) starting {m[0]}" for k, f, p, c, last, m in losses[:10])
    )


@needs_corpus
def test_ungated_spreads_are_consistent_with_the_corpus():
    """The UNGATED_BY_RECORD_* triples must be measurements, not decoration.

    They were unasserted comments, so `novelty_score: (9.9, -3.0, 99999)` passed everything.
    The check is exact while the population is unchanged and degrades to the monotone bounds
    afterwards, because adding run dates can only widen a spread: the minimum can only fall,
    the maximum can only rise, and the eligible-date count can only grow.
    """
    ideas, scores = _built()
    bad = []
    for cov, recorded, label in (
        (ideas, UNGATED_BY_RECORD_IDEA_FIELDS, "idea"),
        (scores, UNGATED_BY_RECORD_SCORE_FIELDS, "scores"),
    ):
        for field, (rmin, rmax, rdates) in sorted(recorded.items()):
            assert 0.0 <= rmin <= rmax <= 1.0 and rdates >= 1, (
                f"{label}.{field} records ({rmin}, {rmax}, {rdates}), which is not a coverage "
                "spread at all — min must be <= max and both must be fractions"
            )
            dates = cov.eligible_dates(field)
            fracs = [cov.frac(d, field) for d in dates]
            assert fracs, f"{label}.{field} has no eligible date; the name is wrong"
            omin, omax, on = min(fracs), max(fracs), len(dates)
            if on < rdates or omin > rmin + 5e-4 or omax < rmax - 5e-4:
                bad.append(f"{label}.{field}: recorded ({rmin:.3f}, {rmax:.3f}, {rdates}) is "
                           f"NARROWER than the corpus ({omin:.3f}, {omax:.3f}, {on}) — "
                           "impossible unless the numbers were never measured")
            elif on == rdates and (abs(omin - rmin) > 5e-4 or abs(omax - rmax) > 5e-4):
                bad.append(f"{label}.{field}: recorded ({rmin:.3f}, {rmax:.3f}, {rdates}) but "
                           f"the corpus says ({omin:.3f}, {omax:.3f}, {on}) over the SAME "
                           "number of dates — re-measure, do not adjust by hand")
    assert not bad, (
        "UNGATED_BY_RECORD_* entries that the corpus does not support. Refresh them with "
        "`python -m probes.score_field_coverage --all`:\n  " + "\n  ".join(bad)
    )


@needs_corpus
def test_artifacts_skipped_on_size_carry_no_score_containers():
    """The 8 MB cap must not silently remove a run from every series in this file.

    Measured 2026-08-16: 4 skipped files, all `stage_5_social_content.json` (8.9-10.0 MB), none
    carrying an idea or SolutionScores container — so the cap costs the probe nothing today.
    A report growing past it would, and would say nothing, so the set is asserted.
    """
    containers = [k.encode() for k in sfc.IDEA_CONTAINERS + sfc.SCORE_CONTAINERS]
    offenders = []
    for rel, size in sfc.oversized_artifacts(CORPUS):
        raw = (CORPUS / rel).read_bytes()
        if not any(b'"%s"' % c in raw for c in containers):
            continue  # cheap prefilter: the key does not appear anywhere in the bytes
        payload = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(payload, dict):
            continue
        for key in sfc.IDEA_CONTAINERS + sfc.SCORE_CONTAINERS:
            rows = payload.get(key)
            if isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows):
                offenders.append(f"{rel} ({size / 1e6:.1f} MB) carries {key} with {len(rows)} rows")
    assert not offenders, (
        "artifact(s) above the size cap carry a score-bearing container, so every run they "
        "belong to is missing from the coverage, step-change, gone-dark and partial-removal "
        "series without a word being printed. Raise sfc.OVERSIZE_BYTES or stream them:\n  "
        + "\n  ".join(offenders)
    )


# =======================================================================================
# Group E — the probe must measure the corpus it was pointed at
# =======================================================================================
def test_root_argument_keys_runs_against_the_root_being_scanned(tmp_path):
    """`--root` used to mis-key every top-level artifact, and only the env path was right.

    `_run_key` compared `path.parent` against the import-time `CHECKPOINT_ROOT` global, so under
    any other root every `preview_report_<uuid>.json` sitting directly in the root took the
    "nested" branch and got named after the DIRECTORY — collapsing all of them into one run.
    Measured against a byte-exact copy of output/checkpoints: 241 runs / 117 winning_angle-eligible
    through `--root`, versus 305 / 142 through NICHEIQ_CHECKPOINT_ROOT. The env path was correct
    only by coincidence, and it is the path the CI story would depend on.
    """
    root = tmp_path / "corpus"
    rows = [{"solution_name": "a", "market_fit_score": 1.0}]
    uuids = [f"{n:08d}-0000-0000-0000-000000000000" for n in (1, 2)]
    for u in uuids:
        run = root / f"checkpoint_{u}_20260816_000000"
        run.mkdir(parents=True)
        (run / "stage_5_3_refinement.json").write_text(json.dumps({"solution_ideas": rows}))
        # Top-level, undated: datable only through the job uuid, keyed only through the stem.
        (root / f"preview_report_{u}.json").write_text(json.dumps({"solution_ideas": rows}))

    ideas, _ = sfc.build(root)
    assert len(ideas.all_runs) == 4, (
        "the two top-level preview artifacts collapsed into a single run key, so every per-run "
        f"and eligibility number computed under --root is wrong: {sorted(ideas.all_runs)}"
    )
    assert {f"preview_report_{u}" for u in uuids} <= ideas.all_runs, (
        f"top-level artifacts are not keyed by their own stem: {sorted(ideas.all_runs)}"
    )
    assert root.name not in ideas.all_runs, "a run is named after the corpus directory"


@needs_corpus
def test_a_repaired_regression_keeps_its_evidence_and_stays_repaired():
    """The successor to `test_known_unfixed_regression_is_still_recorded_as_unfixed`.

    That test said: the 2026-08-15 winning_angle collapse is real and still unfixed, and if it
    disappears that is either a genuinely repaired run (re-measure the pins, deliberately) or
    somebody deleted the evidence — neither should pass quietly. It fired on 2026-08-16 for the
    first reason. The distinction was then MADE rather than assumed: see the honesty note for
    the four artifact-level checks (classified values not a constant, an unrelated field on the
    same date pair that did not recover, 2026-08-15 mtimes older than the repair, both collapse
    steps still observed) that establish repair rather than deletion.

    So the pin was re-measured, not dropped. It now asserts the collapse is STILL in the corpus,
    that the repaired date still measures what it measured, and that the latest date has not
    fallen back — the same refusal, pointed the other way.
    """
    ideas, scores = _built()
    observed = _observed_step_changes()
    bad = []
    for (kind, field), record in sorted(REPAIRED_REGRESSIONS.items()):
        cov = ideas if kind == "idea" else scores
        bad += _repaired_regression_violations(cov, observed, kind, field, record)
    assert not bad, "\n  ".join(["a repaired regression is not in the state this file records:"] + bad)


def test_a_relapse_of_a_repaired_regression_still_fails(tmp_path):
    """Positive control. Without this, `REPAIRED_REGRESSIONS` is a comment that cannot fail.

    Built to the real shape: healthy dates, the collapse, then the repaired date. Then each of
    the three ways the record can stop being true is doctored in, and the checker is asserted to
    name it. The third is the one that matters most — the step detector alone cannot catch a
    relapse on the date immediately after a broken one, because there is no drop between two
    broken dates.
    """
    kind, field = "idea", "winning_angle"
    good = [{"solution_name": f"i{n}", "winning_angle": "gap"} for n in range(20)]
    broken = [dict(r) if n < 2 else {**r, "winning_angle": None} for n, r in enumerate(good)]

    def cov_of(plan):
        cov = sfc.build(_synthetic_corpus(tmp_path / "-".join(plan), dict(zip(
            ("20260811", "20260813", "20260815", "20260816", "20260818"),
            [good if p == "good" else broken for p in plan],
        ))))[0]
        obs = {(kind, field, a, b): after
               for a, b, _x, after in sfc.step_changes(cov, field)}
        return cov, obs

    collapse = (kind, field, "2026-08-13", "2026-08-15")
    known = {collapse: 0.1}
    record = ("2026-08-13", "2026-08-15", "2026-08-16", 1.0)

    healthy, observed = cov_of(("good", "good", "broken", "good"))
    assert observed[collapse] == 0.1, "the synthetic corpus does not reproduce the collapse"
    assert _repaired_regression_violations(healthy, observed, kind, field, record, known) == [], (
        "the checker reports a violation on a corpus that collapsed and then genuinely recovered"
    )

    # 1. the evidence of the collapse is gone — the repaired date is all there is left.
    rewritten, obs = cov_of(("good", "good", "good", "good"))
    assert any("no longer visible in the corpus" in m for m in
               _repaired_regression_violations(rewritten, obs, kind, field, record, known)), (
        "deleting the artifacts that prove the collapse made the suite greener"
    )

    # 2. the repair itself was never really there / got doctored back.
    never, obs = cov_of(("good", "good", "broken", "broken"))
    msgs = _repaired_regression_violations(never, obs, kind, field, record, known)
    assert any("measures 0.100 now" in m for m in msgs), msgs

    # 3. THE ONE THIS EXISTS FOR: repaired, then a later run relapses. Asserted alongside the
    #    proof that the step detector is blind to it, which is why the floor is not redundant.
    relapsed, obs = cov_of(("good", "good", "broken", "good", "broken"))
    msgs = _repaired_regression_violations(relapsed, obs, kind, field, record, known)
    assert any("has relapsed" in m for m in msgs), msgs
    # The step detector DOES see this one (1.000 -> 0.100 across 08-16 -> 08-18), so both fire...
    assert (kind, field, "2026-08-16", "2026-08-18") in obs
    # ...but not when the relapse is the date straight after the collapse, with no repair between.
    straight, obs2 = cov_of(("good", "good", "broken", "broken", "broken"))
    assert [k for k in obs2 if k[2] >= "2026-08-15"] == [], (
        "sanity: two consecutive broken dates are not a step change, which is the gap the "
        "latest-date floor closes"
    )
    assert any("has relapsed" in m for m in
               _repaired_regression_violations(straight, obs2, kind, field, record, known))
