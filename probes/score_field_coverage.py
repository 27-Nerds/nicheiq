#!/usr/bin/env python3
"""Per-run, dated coverage of the score-bearing fields on real run artifacts.

    python -m probes.score_field_coverage           # from the repo root, venv active
    python -m probes.score_field_coverage --all     # every derived field, not just the headline set

WHY THIS FILE EXISTS AS A TRACKED PROBE
---------------------------------------
Two field-loss bugs of the same class landed in one week and both were silent:

  1. `_probe_mechanism_parity` clears `winning_angle` on every idea and, since 2026-08-13,
     nothing re-derives it. Type-aware ranking was simply off for three days. Nobody noticed
     because every analysis of the checkpoint corpus averaged it as ONE population — and the
     corpus is a time series across code versions, so a step function disappears into a mean.
  2. The preview materializer writes `seo_growth_potential_score`; `BaseSolutionIdea` reads
     `seo_scalability_score` and is `extra='ignore'`, so reconstruction yielded a 3-dimension
     composite wearing a 4-dimension label. Two independent review passes shared the harness
     and agreed with each other, which proved nothing.

So this probe does three things a flat average cannot:

  * reports coverage PER DATE, so a step change is visible as a step, and
  * reports, per field, how much of the corpus was ELIGIBLE (i.e. the artifact schema carried
    the key at all). Runs that predate a feature never had the field; averaging them in pads
    the denominator and makes a live regression look like slow historical adoption.
  * reports fields that have GONE DARK. Eligibility is inferred from key presence, so a field
    deleted outright reads as "the schema never carried this" and leaves the series instead of
    scoring 0% — the padded-denominator trap inverted, and one `model_dump(exclude_none=True)`
    away. `eligibility_losses` is the detector for that; coverage alone cannot see it.
  * reports PARTIAL key removal, which is the shape the real bug takes and which all three
    instruments above are blind to. See `ragged_key_presence` and `producer_presence_losses`.

`--blind-check` prints the control: the same corpus scored as one flat average, next to the
per-date view, so you can see for yourself which of the two can detect the 2026-08-15 step.
`--presence` prints the per-date key-presence series and says why it is NOT gated.

The field SET is DERIVED (see `score_bearing_idea_fields`), never hand-listed, so a score
field added to the model tomorrow is measured tomorrow without anyone remembering this file.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
import typing
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nicheiq.models.solution_idea import BaseSolutionIdea  # noqa: E402
from nicheiq.models.solution_selection import SolutionScores  # noqa: E402
from nicheiq.utils import idea_carryover, score_helpers  # noqa: E402

# NICHEIQ_CHECKPOINT_ROOT repoints the corpus. It exists so the coverage checks can be run
# against a doctored COPY of the corpus to prove they still fail when a field is blanked —
# output/ itself is never mutated for that. It also lets CI point at an artifact bundle.
CHECKPOINT_ROOT = Path(os.environ.get("NICHEIQ_CHECKPOINT_ROOT") or (ROOT / "output" / "checkpoints"))

# Lists of BaseSolutionIdea-shaped dicts, by the key they are persisted under.
IDEA_CONTAINERS = ("solution_ideas", "alternative_solutions")
# Lists of SolutionScores-shaped dicts (this is where `composite_score` actually lives).
SCORE_CONTAINERS = ("all_solution_scores", "solution_scores")

# A key in a persisted artifact that LOOKS like it carries a score/verdict. Anything matching
# this that BaseSolutionIdea would silently drop is a candidate for bug #2 and must be declared
# in DECLARED_MODEL_BOUNDARY_ALIASES below.
SCORE_SHAPED_KEY = re.compile(
    r"(_score|_scores|_parity|_angle|_feasibility|_rank|_composite|_verdict)$|^(rank|composite|winning_angle)$"
)

# INTENTIONAL model-boundary renames. `score_helpers` documents
# `seo_scalability_score -> seo_growth_potential_score` as a deliberate BaseSolutionIdea ->
# SolutionScores mapping, so the check is NOT "these names must match" — it is "a value present
# in the source must not vanish in the reconstruction". Declaring the rename here is how a
# boundary stays intentional instead of becoming silent loss.
#
# THIS IS AN EXEMPTION LIST, so it is checked in both directions: each entry must name a real
# model field (`test_declared_model_boundary_aliases_actually_resolve`) AND must be observed
# carrying a value on the real corpus (`test_every_declared_alias_earns_its_exemption`). An
# exemption that exempts nothing is indistinguishable from a fabricated one, and this dict is
# the only thing standing between a real rename and silent field loss.
#   {persisted key: (BaseSolutionIdea field it must be read back into, why it is exempt)}
DECLARED_MODEL_BOUNDARY_ALIASES = {
    "seo_growth_potential_score": (
        "seo_scalability_score",
        "src/nicheiq/utils/score_helpers.py declares seo_scalability_score -> "
        "seo_growth_potential_score as the deliberate BaseSolutionIdea -> SolutionScores rename, "
        "and the preview materializer persists the SolutionScores spelling back onto idea rows. "
        "Measured 2026-08-16: populated on 482 of 2666 idea rows in output/checkpoints.",
    ),
}

# REMOVED 2026-08-16 — do not helpfully re-add it:
#   "competitive_advantage_score": "novelty_score"
# The rename is real (score_helpers.py:23 documents novelty_score -> competitive_advantage_score),
# but the exemption exempted NOTHING. Measured over all 2666 idea rows in output/checkpoints: the
# key is present on 484 idea rows and POPULATED on 0 of them, and `undeclared_dropped_keys` only
# ever considers populated values. So the entry could be deleted, or fabricated, with no observable
# difference — which is the property that lets a bogus exemption hide a real loss. If the
# materializer ever starts writing a value there, the detector fires and the entry comes back
# WITH the artifact that proves it is needed.
DECLARED_ALIAS_TARGETS = {k: v[0] for k, v in DECLARED_MODEL_BOUNDARY_ALIASES.items()}

# Headline fields for the default table (the brief's minimum set). `--all` prints every
# derived field. composite_score is measured on the SolutionScores containers.
HEADLINE_IDEA_FIELDS = (
    "winning_angle",
    "incumbent_parity",
    "market_fit_score",
    "technical_feasibility_score",
    "novelty_score",
    "seo_scalability_score",
    "build_feasibility_score",
)

# A date-over-date drop of at least this much, on dates that both carry enough ideas to mean
# something, is a step change rather than run-to-run noise.
STEP_DROP = 0.25
STEP_MIN_IDEAS = 8

# Artifacts above this size are skipped rather than parsed. `oversized_artifacts` reports what
# that silently costs, and a test asserts the skipped set carries no idea/score container —
# because a report drifting past this cap would leave the series without a word, which is the
# same species of silence this probe exists to catch.
OVERSIZE_BYTES = 8_000_000


# --------------------------------------------------------------------------------------
# Deriving the score-bearing SET from the code, not from a hand-written list
# --------------------------------------------------------------------------------------
def _attrs_read_in(module) -> set[str]:
    """Idea attribute names the given module actually reads off an idea."""
    src = inspect.getsource(module)
    names: set[str] = set()
    names |= set(re.findall(r'getattr\(\s*\w+\s*,\s*["\'](\w+)["\']', src))
    names |= set(re.findall(r"\bidea\.(\w+)", src))
    names |= set(re.findall(r'_extract(?:_optional)?_score\(\s*\w+\s*,\s*["\'](\w+)["\']', src))
    return names


def _optional_fields(model) -> set[str]:
    """Fields that can vanish silently. A REQUIRED field cannot: validation would refuse."""
    out = set()
    for name, field in model.model_fields.items():
        ann = field.annotation
        if type(None) in typing.get_args(ann) or not field.is_required():
            out.add(name)
    return out


def score_bearing_idea_fields(model=BaseSolutionIdea) -> frozenset[str]:
    """The SET under test, derived three ways and unioned. Never hand-listed.

    rule 1  name shape: any BaseSolutionIdea field ending in `_score`.
    rule 2  the ranker reads it: any idea attribute read inside `nicheiq.utils.score_helpers`,
            which is the module that turns ideas into a ranking.
    rule 3  evaluation state: `idea_carryover._RE_EARNED`, the code-resident enumeration of
            fields that "evaluate the OLD product and must be re-earned" — this is what pulls
            in `incumbent_parity`, which no `_score` suffix would ever catch.

    Filtered to OPTIONAL fields, because only an optional field can go missing without pydantic
    raising. That filter is what keeps `solution_name` out without a hand-written exclusion.

    `model` is a parameter only so a test can hand in a model with one extra score field and
    watch the set grow — the derivation must not be a list that happens to look derived.
    """
    model_fields = set(model.model_fields)
    by_name = {f for f in model_fields if f.endswith("_score")}
    by_ranker = _attrs_read_in(score_helpers) & model_fields
    re_earned = getattr(idea_carryover, "_RE_EARNED", None)
    if not re_earned:
        raise AssertionError(
            "idea_carryover._RE_EARNED is gone or empty — rule 3 of the score-bearing set no "
            "longer derives anything. Repoint it before trusting any number this probe prints."
        )
    return frozenset((by_name | by_ranker | set(re_earned)) & _optional_fields(model))


def score_bearing_scores_fields() -> frozenset[str]:
    """Numeric fields on SolutionScores — `composite_score` and the dimensions it is built from."""
    numeric = set()
    for name, field in SolutionScores.model_fields.items():
        ann = field.annotation
        args = set(typing.get_args(ann)) | {ann}
        if float in args or int in args:
            numeric.add(name)
    return frozenset(numeric - {"rank"})


# --------------------------------------------------------------------------------------
# Walking the artifacts
# --------------------------------------------------------------------------------------
_DIR_DATE = re.compile(r"_(\d{4})(\d{2})(\d{2})_\d{6}$")
_UUID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


def _job_id_dates(root: Path) -> dict[str, str]:
    """job uuid -> run date, harvested from the dated checkpoint directory names."""
    out: dict[str, str] = {}
    for child in root.iterdir() if root.is_dir() else []:
        if not child.is_dir():
            continue
        m, u = _DIR_DATE.search(child.name), _UUID.search(child.name)
        if m and u:
            out[u.group(1)] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return out


def _run_date(path: Path, job_dates: dict[str, str]) -> str | None:
    """ISO date of the run that produced `path`.

    Preference order matters. The dated directory name is the run's own timestamp. Top-level
    artifacts (preview_report_<job-uuid>.json) carry no date, so they are resolved through the
    job uuid to the dated directory of the same run — NOT through mtime, which the backend
    rewrites when it re-caches a preview and would silently stamp old runs with today's date,
    which is exactly the kind of quiet corruption this probe exists to catch.

    There is deliberately NO mtime fallback: an artifact that neither carries a date nor
    resolves through a job uuid is EXCLUDED from every number this probe prints. (An earlier
    revision of this docstring claimed mtime was "the last resort and is reported as such".
    It never was — no line of this function reads `st_mtime`. A comment asserting a behaviour
    the code does not have is how the regression this file monitors stayed invisible for three
    days, so the docstring was corrected to match the code rather than the reverse.)
    """
    for part in (path.parent.name, path.stem):
        m = _DIR_DATE.search(part)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    u = _UUID.search(path.stem)
    if u and u.group(1) in job_dates:
        return job_dates[u.group(1)]
    return None  # undatable: excluded rather than guessed into a bucket


def _run_key(path: Path, root: Path) -> str:
    """Identity of the run that produced `path`, RELATIVE TO THE ROOT BEING SCANNED.

    This used to compare against the import-time `CHECKPOINT_ROOT` global, which meant `--root`
    silently mis-keyed every top-level artifact: under a copied corpus the `path.parent != root`
    branch was always taken, so every `preview_report_<uuid>.json` in the root collapsed into ONE
    run named after the directory. Measured 2026-08-16 against a byte-exact copy of
    output/checkpoints: 241 runs / 117 winning_angle-eligible, versus 305 / 142 through the
    env-var path. Only the env-var path was ever correct, and it was correct by coincidence
    (`path.parent == CHECKPOINT_ROOT` happened to hold). Keep `root` a parameter.
    """
    return path.parent.name if path.parent != root else path.stem


def iter_artifacts(root: Path = CHECKPOINT_ROOT):
    """Yield (date, run_key, artifact_path, container_name, list_of_dicts, kind)."""
    root = root.resolve()
    if not root.is_dir():
        return
    job_dates = _job_id_dates(root)
    for path in sorted(root.rglob("*.json")):
        try:
            if path.stat().st_size > OVERSIZE_BYTES:
                continue  # accounted for by oversized_artifacts(), not silently dropped
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        date = _run_date(path, job_dates)
        if date is None:
            continue
        for key, kind in [(k, "idea") for k in IDEA_CONTAINERS] + [
            (k, "scores") for k in SCORE_CONTAINERS
        ]:
            rows = payload.get(key)
            if isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows):
                yield date, _run_key(path, root), path, key, rows, kind


class Coverage:
    """(date, field) -> populated / total, counted only over ELIGIBLE runs.

    A run is eligible for a field when the persisted rows carry the key at all. A run that
    predates the field never had it and is never averaged in — that is the padded-denominator
    trap, and it is what makes "slow adoption" and "live regression" look identical.

    THE INVERSE TRAP, and why `rows_by_date` exists: inferring eligibility from key presence
    means a field DELETED outright (key gone, not value nulled) reads as "the schema never
    carried this field" and drops out of the denominator instead of failing. Measured 2026-08-16:
    removing the `winning_angle` KEY from all 612 ideas on the 2026-08-15 date left every
    coverage assertion in tests/unit/test_score_field_coverage.py passing. A producer switching
    to `model_dump(exclude_none=True)` reproduces the original silent-loss bug in exactly that
    shape. `rows_by_date` counts idea rows per date INDEPENDENTLY of any field, which is what
    lets `eligibility_losses` tell "no run that day" apart from "the key stopped being written".
    """

    def __init__(self) -> None:
        self.pop: dict[tuple[str, str], int] = defaultdict(int)
        self.tot: dict[tuple[str, str], int] = defaultdict(int)
        self.eligible_runs: dict[str, set[str]] = defaultdict(set)
        self.all_runs: set[str] = set()
        self.dates: set[str] = set()
        self.per_run: dict[tuple[str, str], tuple[int, int, str]] = {}
        self.rows_by_date: dict[str, int] = defaultdict(int)

    def add(self, date: str, run: str, fields: frozenset[str], rows: list[dict]) -> None:
        self.all_runs.add(run)
        self.dates.add(date)
        self.rows_by_date[date] += len(rows)
        for field in fields:
            present = [r for r in rows if field in r]
            if not present:
                continue  # ineligible: this run's schema never carried the field
            self.eligible_runs[field].add(run)
            filled = sum(1 for r in present if _is_populated(r.get(field)))
            self.pop[(date, field)] += filled
            self.tot[(date, field)] += len(present)
            prev = self.per_run.get((run, field), (0, 0, date))
            self.per_run[(run, field)] = (prev[0] + filled, prev[1] + len(present), date)

    def frac(self, date: str, field: str) -> float | None:
        total = self.tot[(date, field)]
        return None if not total else self.pop[(date, field)] / total

    def presence(self, date: str, field: str) -> float | None:
        """Fraction of THIS DATE's rows that carry the key at all — the pooled presence series.

        REPORTED, NEVER GATED, and the reason is a measurement. Running `step_changes` over
        this series at the existing 0.25 threshold fires on 3 of the last 20 substantial idea
        dates: a 15% false-alarm rate. It is the same defect the deleted floor dict had, at a
        smaller constant. Raising the threshold buys quiet at the cost of the sensitivity the
        series was wanted for (0.50 -> 1/20; 0.75 -> 0/20 but blind to a 70% key deletion).

        The noise is not run-to-run variance, it is denominator mixing: a date pools every
        producer that ran, and producers carry different key sets, so `seo_scalability_score`
        presence swings 50%-95% purely on which stages happened to run. All three flagged
        dates are that — e.g. 2026-06-28 (69 rows) -> 2026-06-29 (25 rows) moves EIGHT fields
        by the identical 90% -> 60%, which is one producer's absence, not eight regressions.

        `ragged_key_presence` and `producer_presence_losses` close the same hole with a
        measured ZERO false alarms, because both scope the comparison to a unit that has one
        schema. Keep this method for `--presence` and for re-measuring the tradeoff; do not
        promote it to an assertion without redoing the replay above.
        """
        rows = self.rows_by_date[date]
        return None if not rows else self.tot[(date, field)] / rows

    def flat(self, field: str) -> float | None:
        """The BLIND metric: one average over the whole corpus. Kept only to be shown losing."""
        total = sum(v for (_, f), v in self.tot.items() if f == field)
        return None if not total else sum(v for (_, f), v in self.pop.items() if f == field) / total

    def eligible_dates(self, field: str) -> list[str]:
        return sorted(d for d in self.dates if self.tot[(d, field)])


def _is_populated(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def step_changes(cov: Coverage, field: str, drop: float = STEP_DROP) -> list[tuple[str, str, float, float]]:
    """Consecutive eligible dates where coverage FELL by >= `drop`.

    Requires both sides to carry enough ideas that the move is not one small run's noise.
    Returns (prev_date, date, prev_frac, frac).
    """
    out = []
    dates = [d for d in cov.eligible_dates(field) if cov.tot[(d, field)] >= STEP_MIN_IDEAS]
    for prev, cur in zip(dates, dates[1:]):
        a, b = cov.frac(prev, field), cov.frac(cur, field)
        if a is not None and b is not None and a - b >= drop:
            out.append((prev, cur, a, b))
    return out


def eligibility_losses(
    cov: Coverage, fields, min_ideas: int = STEP_MIN_IDEAS
) -> list[tuple[str, str, list[str]]]:
    """Fields that WERE written and have gone dark — the key itself stopped appearing.

    Coverage is blind to this by construction: it only counts rows where the key is present, so
    total removal shrinks the denominator to zero and the date silently leaves the series instead
    of scoring 0%. Nulling a value fails a coverage floor; DELETING the key does not, and the
    second is what `model_dump(exclude_none=True)` produces.

    A field has gone dark when its most recent eligible date is followed by at least one
    substantial run date (>= `min_ideas` idea rows, counted independently of this field) on which
    the key is absent from every row. `rows_by_date` is what makes "nobody ran anything" distinct
    from "the producer stopped writing it".

    Measured 2026-08-16 over output/checkpoints: ZERO fields have gone dark across 64 substantial
    dates, idea and SolutionScores alike. That is why this is a hard assertion and not a pinned
    allowlist — there is nothing to grandfather, so any hit is new.

    Returns [(field, last_eligible_date, [dates it is missing from])].
    """
    dates = sorted(d for d in cov.dates if cov.rows_by_date[d] >= min_ideas)
    out: list[tuple[str, str, list[str]]] = []
    for field in sorted(fields):
        eligible = [d for d in dates if cov.tot[(d, field)] > 0]
        if not eligible:
            continue  # never written on a substantial date: nothing to lose
        missing = [d for d in dates if d > eligible[-1]]
        if missing:
            out.append((field, eligible[-1], missing))
    return out


def oversized_artifacts(root: Path = CHECKPOINT_ROOT) -> list[tuple[str, int]]:
    """Artifacts `iter_artifacts` skips on size. Reported, so the skip is never silent.

    Measured 2026-08-16 over output/checkpoints: 4 files, all `stage_5_social_content.json`
    (8.9-10.0 MB), none of which carries an idea or SolutionScores container. The cap therefore
    costs this probe nothing TODAY — but a report growing past it would remove a run from every
    series here without printing a word, so the set is listed and asserted, not assumed.
    """
    root = root.resolve()
    if not root.is_dir():
        return []
    out = []
    for path in sorted(root.rglob("*.json")):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > OVERSIZE_BYTES:
            rel = str(path.relative_to(root))
            out.append((rel, size))
    return out


def ragged_key_presence(root: Path = CHECKPOINT_ROOT) -> list[tuple]:
    """PARTIAL key removal: a key present on SOME rows of one persisted list and absent from
    the rest. This is the hole the three date-level instruments above all miss.

    Why they miss it. Take a field populated on 13 of 100 rows with the KEY DELETED on the
    other 87 — precisely what `model_dump(exclude_none=True)` emits after a clearing pass nulls
    most of the values. Then:
      * `Coverage` counts only rows where the key is present, so populated/present = 13/13 and
        coverage reads a flawless 100%;
      * the date keeps a non-zero denominator, so it stays eligible and `eligibility_losses`
        stays silent — that detector fires only on TOTAL removal;
      * with coverage pinned at 100% there is no drop, so `step_changes` sees nothing;
      * and a STABLE_FULLY_COVERED field sails through its gate with a perfect record.
    Demonstrated 2026-08-16 on a byte-copy of output/checkpoints with `market_fit_score`
    deleted from 571 of the 612 idea rows on 2026-08-15: 18 of 18 tests passed, and this probe
    printed `market_fit_score  100%` against `612 ideas` on that date.

    The detector needs no threshold and no date bucketing. A persisted list is ONE
    `model_dump` of ONE model version, so every row must carry the same key set; ragged
    presence means the serializer made the key conditional on the value. Measured 2026-08-16
    over output/checkpoints: ZERO ragged (list, field) pairs across 405 persisted lists and
    2964 rows. Nothing to grandfather, so this is a hard assertion with no allowlist.

    Returns [(kind, field, artifact, container, present_rows, total_rows, populated_among_present)].
    """
    idea_fields = score_bearing_idea_fields()
    score_fields = score_bearing_scores_fields()
    out: list[tuple] = []
    for _date, _run, path, container, rows, kind in iter_artifacts(root):
        for field in sorted(idea_fields if kind == "idea" else score_fields):
            present = [r for r in rows if field in r]
            if not present or len(present) == len(rows):
                continue
            rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
            out.append((kind, field, rel, container, len(present), len(rows),
                        sum(1 for r in present if _is_populated(r.get(field)))))
    return out


def producer_of(path: Path) -> str:
    """The PRODUCER that wrote `path`, with per-run identifiers normalised away.

    `stage_5_3_refinement.json` is one producer observed across 41 dates.
    `preview_report_<uuid>.json` is ALSO one producer, but naming it by filename would make
    every run its own single-date series — and a series of length one can never show a loss,
    so the detector below would have looked clean by being vacuous. Measured: normalising
    turns 74 scopes (7 of them multi-date) into 10 scopes (8 multi-date) and raises the number
    of series that could possibly have failed from 62 to 79.
    """
    return _UUID.sub("<id>", re.sub(r"\d{8}_\d{6}", "<ts>", path.name))


def producer_presence_losses(
    root: Path = CHECKPOINT_ROOT, min_rows: int = STEP_MIN_IDEAS, min_missing: int = 2
) -> list[tuple[str, str, str, str, str, list[str]]]:
    """A producer wrote a score-bearing key, then stopped — while other producers still write it.

    This is the residual `ragged_key_presence` leaves. If `exclude_none=True` ships on a stage
    whose field is null on EVERY row of a list, that list is uniformly key-less, so it is not
    ragged. Its rows simply drop out of the per-date denominator, and because another stage on
    the same date still writes the key, `eligibility_losses` — which pools all producers per
    date — never sees the date go dark either.

    Scoping the presence series by (producer, container) removes the mix noise that makes the
    pooled per-date series unusable as a gate (see `presence` below): within one producer the
    key set is a property of that stage's code, not of which artifacts happened to run that day.

    `min_missing` is a measurement, not a taste. Replaying the last 20 substantial run dates and
    asking whether this gate would have raised a NEW finding the day each landed:

        min_missing = 1:  1/20 dates fire (5%)   -- 2026-08-13, red_team_findings
        min_missing = 2:  0/20 (0%)
        min_missing = 3:  0/20 (0%)

    The single false alarm is a field being rolled out, not one being lost: its presence record
    on `stage_5_3_refinement.json` across 41 substantial dates is `......W.W` — written on
    08-12, absent on 08-13, written again on 08-15. So one absent date is a run that did not
    exercise that stage; two consecutive is a producer that stopped. The cost is one run date of
    detection latency, which is the right trade against training people to ignore the gate.

    NOTE, unchanged and deliberately not "fixed" here: replayed the same way, the existing
    `eligibility_losses` gate has the SAME 5% rate from the SAME field on the SAME date, because
    it also reports on a single absent date. That is a real property of a shipped gate that had
    not been measured before. It is left alone: raising its threshold would cut the sensitivity
    of a detector that currently has a clean record on the corpus, and this round changed enough.

    Measured 2026-08-16 over output/checkpoints: ZERO losses at min_missing=1, 2 or 3, across 208
    (producer, container, field) series, 79 of which had at least one later substantial date on
    which they could have failed. Hard assertion, no allowlist.

    Returns [(kind, field, producer, container, last_date_written, [dates absent from])].
    """
    idea_fields = score_bearing_idea_fields()
    score_fields = score_bearing_scores_fields()
    present_rows: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows_seen: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for date, _run, path, container, rows, kind in iter_artifacts(root):
        scope = (kind, producer_of(path), container)
        rows_seen[scope][date] += len(rows)
        for field in idea_fields if kind == "idea" else score_fields:
            present_rows[(scope, field)][date] += sum(1 for r in rows if field in r)

    out = []
    for (scope, field), by_date in present_rows.items():
        dates = sorted(d for d, n in rows_seen[scope].items() if n >= min_rows)
        written = [d for d in dates if by_date.get(d, 0) > 0]
        if not written:
            continue
        missing = [d for d in dates if d > written[-1]]
        if len(missing) >= min_missing:
            out.append((scope[0], field, scope[1], scope[2], written[-1], missing))
    return sorted(out)


def build(root: Path = CHECKPOINT_ROOT) -> tuple[Coverage, Coverage]:
    idea_fields = score_bearing_idea_fields()
    score_fields = score_bearing_scores_fields()
    ideas, scores = Coverage(), Coverage()
    for date, run, _path, _container, rows, kind in iter_artifacts(root):
        if kind == "idea":
            ideas.add(date, run, idea_fields, rows)
        else:
            scores.add(date, run, score_fields, rows)
    return ideas, scores


def undeclared_dropped_keys(root: Path = CHECKPOINT_ROOT) -> dict[str, list[str]]:
    """Score-shaped keys that carry a value on disk and vanish on reconstruction.

    This is the generalisation of `probes/analyst_agreement.py::_assert_harness_sane` from one
    consumer to every persisted idea list: BaseSolutionIdea is `extra='ignore'`, so any key it
    does not know is dropped without a word. Returns {key: [example artifacts]}.
    """
    model_fields = set(BaseSolutionIdea.model_fields)
    found: dict[str, list[str]] = defaultdict(list)
    for _date, _run, path, _container, rows, kind in iter_artifacts(root):
        if kind != "idea":
            continue
        for row in rows:
            for key, value in row.items():
                if key in model_fields or not _is_populated(value):
                    continue
                if not SCORE_SHAPED_KEY.search(key):
                    continue
                if DECLARED_ALIAS_TARGETS.get(key) in model_fields:
                    continue
                rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                if rel not in found[key]:
                    found[key].append(rel)
    return dict(found)


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------
def _cell(frac: float | None) -> str:
    if frac is None:
        return "   ·"  # ineligible: schema never carried the field on this date
    return f"{frac * 100:3.0f}%"


def _print_table(cov: Coverage, fields: list[str], title: str) -> None:
    dates = sorted(cov.dates)
    dates = [d for d in dates if any(cov.tot[(d, f)] for f in fields)]
    if not dates:
        print(f"\n{title}: no eligible runs.")
        return
    print(f"\n{title}")
    head = "  date        ideas  " + "  ".join(f"{f[:16]:>16}" for f in fields)
    print(head)
    print("  " + "-" * (len(head) - 2))
    for date in dates:
        ideas = max(cov.tot[(date, f)] for f in fields)
        cells = "  ".join(f"{_cell(cov.frac(date, f)):>16}" for f in fields)
        print(f"  {date}  {ideas:5}  {cells}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="every derived field, not the headline set")
    ap.add_argument("--blind-check", action="store_true", help="flat corpus average, as a control")
    ap.add_argument("--presence", action="store_true",
                    help="per-date key-PRESENCE series (reported, not gated — see Coverage.presence)")
    ap.add_argument("--root", default=str(CHECKPOINT_ROOT))
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"no checkpoint corpus at {root}")

    idea_fields = score_bearing_idea_fields()
    score_fields = score_bearing_scores_fields()
    ideas, scores = build(root)

    print(f"corpus: {root}")
    print(f"score-bearing idea fields derived: {len(idea_fields)}  "
          f"(headline: {', '.join(HEADLINE_IDEA_FIELDS)})")
    print(f"score-bearing SolutionScores fields derived: {sorted(score_fields)}")
    print(f"runs with an idea list: {len(ideas.all_runs)}   with a scores list: {len(scores.all_runs)}")

    shown = sorted(idea_fields) if args.all else list(HEADLINE_IDEA_FIELDS)
    _print_table(ideas, shown, "populated fraction per DATE — ideas (· = field not in that run's schema)")
    _print_table(scores, sorted(score_fields), "populated fraction per DATE — SolutionScores")

    print("\nELIGIBILITY (runs whose artifacts carried the key at all; the rest are NOT averaged in)")
    for field in shown:
        n = len(ideas.eligible_runs[field])
        print(f"  {field:34} {n:4}/{len(ideas.all_runs)} runs "
              f"({n / max(len(ideas.all_runs), 1) * 100:.0f}% of corpus eligible)")
    for field in sorted(score_fields):
        n = len(scores.eligible_runs[field])
        print(f"  {field:34} {n:4}/{len(scores.all_runs)} runs "
              f"({n / max(len(scores.all_runs), 1) * 100:.0f}% of corpus eligible)  [SolutionScores]")

    print("\nSTEP CHANGES (date-over-date drop >= "
          f"{STEP_DROP:.0%}, both dates >= {STEP_MIN_IDEAS} ideas)")
    any_step = False
    for cov, fields, label in ((ideas, sorted(idea_fields), ""), (scores, sorted(score_fields), " [scores]")):
        for field in fields:
            for prev, cur, a, b in step_changes(cov, field):
                any_step = True
                print(f"  {field}{label}: {prev} {a:.0%} -> {cur} {b:.0%}   "
                      f"({a - b:.0%} drop, {cov.tot[(cur, field)]} ideas on the later date)")
    if not any_step:
        print("  none")

    print("\nFIELDS GONE DARK (the KEY itself stopped being written — invisible to coverage, "
          f"which would just call the date ineligible; dates with >= {STEP_MIN_IDEAS} ideas)")
    any_dark = False
    for cov, fields, label in ((ideas, idea_fields, ""), (scores, score_fields, " [scores]")):
        for field, last, missing in eligibility_losses(cov, fields):
            any_dark = True
            print(f"  {field}{label}: last written {last}, absent from {len(missing)} later "
                  f"date(s) e.g. {missing[0]} ({cov.rows_by_date[missing[0]]} ideas that day)")
    if not any_dark:
        print("  none")

    print("\nPARTIAL KEY REMOVAL — a key present on some rows of a list and absent from the "
          "rest (the exclude_none shape; coverage reads 100% straight through it)")
    ragged = ragged_key_presence(root)
    if ragged:
        for kind, field, art, container, present, total, pop in ragged:
            print(f"  {kind}.{field}: {present}/{total} rows of {container} carry the key "
                  f"({pop} of those populated) in {art}")
    else:
        print("  none")

    print(f"\nPRODUCER STOPPED WRITING A KEY (per producer+container, dates with "
          f">= {STEP_MIN_IDEAS} rows, absent from >= 2 consecutive later ones; the residual "
          "partial removal leaves)")
    losses = producer_presence_losses(root)
    if losses:
        for kind, field, prod, container, last, missing in losses:
            print(f"  {kind}.{field}: {prod}/{container} last wrote it {last}, absent from "
                  f"{len(missing)} later date(s) e.g. {missing[0]}")
    else:
        print("  none")

    oversize = oversized_artifacts(root)
    print(f"\nARTIFACTS SKIPPED ON SIZE (> {OVERSIZE_BYTES / 1e6:.0f} MB — excluded from every "
          "number above, so they are named rather than dropped in silence)")
    if oversize:
        for rel, size in oversize:
            print(f"  {size / 1e6:6.1f} MB  {rel}")
    else:
        print("  none")

    dropped = undeclared_dropped_keys(root)
    print("\nSILENTLY DROPPED SCORE-SHAPED KEYS (present on disk, absent after model_validate)")
    if dropped:
        for key, examples in sorted(dropped.items()):
            print(f"  {key}: {len(examples)} artifact(s), e.g. {examples[0]}")
        print("  -> declare each in DECLARED_MODEL_BOUNDARY_ALIASES or the composite is mislabeled.")
    else:
        print(f"  none undeclared (declared boundaries: {DECLARED_ALIAS_TARGETS})")

    if args.presence:
        print("\nKEY-PRESENCE PER DATE (fraction of the date's rows carrying the key at all). "
              "REPORTED, NOT GATED: stepping this series at 0.25 false-alarms on 3 of the last "
              "20 substantial dates. See Coverage.presence for the measurement.")
        dates = [d for d in sorted(ideas.dates) if ideas.rows_by_date[d] >= STEP_MIN_IDEAS]
        head = "  date        rows  " + "  ".join(f"{f[:16]:>16}" for f in shown)
        print(head)
        print("  " + "-" * (len(head) - 2))
        for date in dates:
            cells = "  ".join(f"{_cell(ideas.presence(date, f)):>16}" for f in shown)
            print(f"  {date}  {ideas.rows_by_date[date]:5}  {cells}")

    if args.blind_check:
        print("\nBLIND-METRIC CONTROL — the number that would have hidden this")
        print(f"  {'field':34} {'flat corpus avg':>16}  {'worst date':>12}  {'best date':>10}")
        for field in shown:
            flat = ideas.flat(field)
            fr = [ideas.frac(d, field) for d in ideas.eligible_dates(field)]
            fr = [f for f in fr if f is not None]
            if flat is None or not fr:
                continue
            print(f"  {field:34} {flat:15.0%}  {min(fr):11.0%}  {max(fr):9.0%}")
        print("  A flat average mixes code versions. Only the per-date column shows a step.")


if __name__ == "__main__":
    main()
