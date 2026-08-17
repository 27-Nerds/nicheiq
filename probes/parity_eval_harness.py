"""parity_eval_harness — a measurement regime for `incumbent_parity`, with its own noise floor.

WHY THIS EXISTS
---------------
`incumbent_parity` gates money: `_parity_cap` clamps `market_fit` (shipped 0.45 / partial 0.55 /
substitute 0.50 / bundled_free 0.40), and the stamp also feeds the calibration critic and novelty
scoring. A FALSE POSITIVE therefore demotes a genuinely novel idea. Eight fix attempts to
`_probe_mechanism_parity` have been evaluated at n<=3 with a stamp-COUNT metric. Both halves of
that are broken:

  * n<=3 cannot see the noise floor. Measured before this harness: one config, one run,
    temperature 0, three replays produced 9 / 10 / 6 named stamps of 14 ideas.
  * a stamp COUNT cannot see a false positive. Gate deletion named `Rite Aid Peptide Calculator`,
    a `PathToPeptides COA checklist & guide`, and `PepTok` as incumbents — content pages read as
    commercial products. Every one of those demotes a novel idea, and the count metric scores them
    as WINS.

This harness is not a fix. It is the apparatus that decides whether a fix is real. It reports
(1) a per-config noise band, (2) precision / recall / allow-case against hand labels, and
(3) a verdict that must say UNPROVEN whenever the effect is inside the band.

    python probes/parity_eval_harness.py --derive           # freeze the case set (no API calls)
    python probes/parity_eval_harness.py --record-phrases   # 1 prod LLM call per niche, vendored
    python probes/parity_eval_harness.py --smoke            # 1 case x 3 arms x 1 rep
    python probes/parity_eval_harness.py --run --reps 5
    python probes/parity_eval_harness.py --export-labels    # arm-blind pair list to hand-label
    python probes/parity_eval_harness.py --score            # metrics + noise band + verdict

WHAT IS PINNED, AND HOW (no `src/**` edit — pinning a measurement by editing the thing measured
is not a measurement)
---------------------------------------------------------------------------------------------
The probe's query text is a product of four upstream nondeterministic inputs. Three are pinned by
injecting recorded artifacts onto the crew instance, which the production code then reads through
its own cache checks:

  1. `_incumbent_rows` (drives BOTH the name-anchored query text AND the `_overlap` ranking/gate)
     <- `metadata.json:niche_incumbent_map`, which IS the persisted `_incumbent_rows`. Pinned by
     pre-setting `crew._incumbent_rows` + `crew._incumbent_probe_text`, so `_probe_incumbents()`
     returns its cache and issues no search and no LLM call.
  2. `_capability_phrases` (:2285 — the main offender: its own batched LLM call, so query text
     moved run to run) <- RECORD/REPLAY. `--record-phrases` calls the REAL production method once
     per case and vendors `{solution_name: phrase}` to disk; runs pre-seed
     `crew._capability_phrase_map`, so the method finds `todo == []` and returns the cache without
     an LLM call. The phrases are therefore generator-emitted, never hand-written.
  3. Serper results <- disk record/replay cache keyed by the normalized query. A miss calls the
     real `CachedSerperDevTool` once and records it; every later rep/arm replays bytes.
  4. `_parity_discovery_spent` is reset per idea, so the vendor-free discovery query is present
     for EVERY case in EVERY arm. In production that budget (12/run) runs out partway through a
     pool, so late ideas silently lose the arm. That confound is removed here, identically in all
     arms.

COULD NOT BE PINNED — this is the residual, and it is what the noise band measures:
  * The parity JUDGE call itself (`report_structured_llm` = grok-4.3, temperature 0,
    reasoning_effort='none'). Temperature 0 is not determinism: OpenRouter provider routing,
    batching and quantization differ between calls. It cannot be pinned without stubbing the
    judge, which would delete the phenomenon under study. Every rep re-issues it.
  * Post-refinement drift in the artifacts: `value_proposition` / `technical_approach` read from
    `stage_5_3_refinement.json` are the FINAL texts; the live probe saw whatever those fields held
    at probe time. So the corpus is faithful to the ideas as shipped, not necessarily byte-exact
    to the historical probe call. Affects all arms identically.
  * Serper index drift: a cache MISS today returns today's SERP. Recorded once, then frozen, so
    all arms/reps see identical bytes — but an arm added later must be re-recorded, and its
    results are noted as such.

SCOPE (stated, not hidden)
--------------------------
* SINGLE-IDEA POOLS. Production judges the whole pool in one call; this harness judges one idea
  per call. Reason: it makes the unit of measurement independent (a prior probe showed the judge
  reacts to peers' evidence present in a shared prompt), and it is what lets arm B be realized
  exactly (below). Total token spend is comparable (the same snippets, split across calls).
  CONSEQUENCE: absolute stamp rates here are NOT production's. Only BETWEEN-ARM contrasts are
  claimed, and every arm shares the handicap.
* The two additive arms inside `_probe_mechanism_parity` (`_probe_adjacent_markets`,
  `_probe_toolbelt_free_bundle`) are stubbed off, and the recalibration tail (`_run_parallel` ->
  `_calibrate_batch`) is stubbed to []. The change under test lives in the direct arm's query
  construction; the stubs are identical in all arms and cost ~all of the campaign's money.

THE ARMS (frozen in this docstring before the first API call; no arm was tuned against labels)
---------------------------------------------------------------------------------------------
Every arm runs the REAL `UnifiedSolutionCrew._probe_mechanism_parity`. Arms are realized by
changing only its INPUTS, never by re-implementing its body — a hand-written query builder is how
a prior validation ended up testing a phrase the generator provably never emits.

  A  `prod`      — production as it ships. Name-anchored queries only for `ranked[:2]` rows whose
                   `_overlap(focus, idea_text) > 0`, plus the vendor-free discovery query.

  B  `nogate`    — the live candidate: the `_overlap > 0` gate deleted (:3424-3427).
                   REALIZED WITHOUT EDITING src: a sentinel token is appended to EVERY incumbent
                   row's `focus`, chosen per case from the idea's own text such that it is absent
                   from every row's focus. Each row's overlap rises by exactly 1, so
                   (i) every row now passes `> 0` — the gate is deleted — and
                   (ii) `sorted(key=-overlap)` is a stable sort over uniformly shifted keys, so
                        `ranked[:2]` selects THE SAME TWO ROWS as arm A.
                   `focus` never enters a query or the judge prompt (only `name` does), so the
                   only observable difference is the presence of the previously-gated queries.
                   Asserted per case at runtime from the queries production actually emitted:
                   B's name-anchored set must equal A's plus exactly the gated rows, and must be
                   the top-2 rows by ORIGINAL overlap. A violation is a hard failure, not a note.

  K  `pain_anchored` — RECONSTRUCTION of a config reported as destructive (8/13 -> 1/13 named)
                   by anchoring the query on pain text instead of the capability phrase.
                   PROVENANCE FAILURE, stated loudly: an exhaustive search of the tree, of every
                   commit on every branch (`git log --all -S/-G`), of every `probes/`+`scripts/`
                   parity harness and of leftover /tmp scratch found NO definition of that arm and
                   NO occurrence of those numbers. The historical arm is unrecoverable, so this is
                   a reconstruction from its description, not a replay: the replayed capability
                   phrase is replaced by the idea's own `source_pain` text (artifact text,
                   truncated to the phrase's own 6-word budget — not hand-authored). Its result
                   cannot confirm or refute the reported 8/13 -> 1/13.

  D  `decoy`      — the PRIMARY known-bad control, and the harness's own blind-metric check. It
                   does not depend on unrecoverable history: the incumbent rows are swapped for
                   ANOTHER checkpoint's rows from a different niche (real, generator-emitted vendor
                   names, provably not this niche's incumbents), with the same sentinel injection
                   so the gate passes and the decoy names are actually queried. Every named stamp
                   an arm produces from a foreign vendor is a false positive by construction, so a
                   metric that cannot report D as harmful — on PRECISION, not on stamp count —
                   is blind in exactly the way the old metric was blind, and no verdict from this
                   harness may then be believed. D is also the mechanistic worst case of the
                   candidate under test: gate deletion means querying vendors the ranking already
                   judged irrelevant.

  Null-contrast controls: cases where NO row is gated in arm A. There, A and B emit byte-identical
  queries by construction, so any A-vs-B difference on that subset is pure judge noise. They are a
  second, independent read on the noise band, and they are asserted identical.

LABEL CRITERION — FROZEN BEFORE ANY MEASUREMENT (this text was written to disk before the first
judge call; see git history of this file)
-------------------------------------------------------------------------------------------------
Unit: one (case, vendor) pair, where `case` is a distinct idea and `vendor` is the `covered_by`
name a judge stamped for it. Labeled from the idea's `value_proposition` + `technical_approach`,
the judge's own `evidence` line, and the recorded search snippet the stamp was drawn from.

  yes     — the named entity is a REAL, currently-available product, first-party platform feature,
            or (for a `substitute` stamp) a concrete free/DIY route, AND it delivers this idea's
            CORE MECHANISM for this idea's buyer, outright or in substantial part.
  no      — any of: (i) not a product at all (a content page, blog post, listicle, buyer's guide,
            directory, forum thread, retailer/marketplace SKU page, a PDF checklist); (ii) a real
            product doing a DIFFERENT job than the idea's core mechanism; (iii) not identifiable
            as a specific named vendor at all.
  unclear — evidence too thin to decide either way.

BORDERLINES RESOLVE TO `no`. Stated direction, stated reason: the harm being measured is a false
positive that caps a novel idea's market_fit, so an unproven vendor must not be credited as a
genuine incumbent. Class correctness (shipped vs partial vs substitute) is NOT part of this label;
it is reported separately.

Labelling is ARM-BLIND by construction: `--export-labels` emits pairs keyed by a content hash with
arm and rep stripped, and the same vendor stamped by two arms is ONE pair with ONE label.

METRICS (why stamp counts are not among the headline numbers)
------------------------------------------------------------
  named_rate  — the OLD metric. Reported for continuity and explicitly marked blind.
  precision   — yes / (yes + no) over named stamps. `unclear` excluded, its count reported.
  recall      — pooled-oracle: an idea is gold-positive if ANY arm in ANY rep named a vendor
                labeled `yes` for it. recall(arm) = mean over gold-positive ideas of the fraction
                of that arm's reps naming a `yes` vendor. This is a LOWER bound biased toward
                whichever arm discovered the vendor; stated, not hidden.
  allow-case  — over ideas with NO `yes` vendor anywhere: fraction of (arm, rep) cells that
                correctly stamped "none found". This is the metric a stamp count cannot see.
  mf_cap_loss — mean market_fit lost to `_parity_cap` per idea, split by label. FP loss is the
                money the false positives cost; TP loss is the money the mechanism is for.

  NOISE BAND: for each metric, the min-max spread across reps within one arm, plus the A-vs-B
  spread on the null-contrast subset. A between-arm difference smaller than the band is reported
  UNPROVEN. Not "small". Not "directionally positive". Unproven.

AS-RUN RESULT (2026-08-17; 30 cases x 4 arms x 5 reps = 600 judge calls, $0.49 LLM, 166 Serper
credits; full numbers in parity_eval_harness_score.json)
-------------------------------------------------------------------------------------------------
NOISE FLOOR, label-free — two judge invocations on byte-identical queries and byte-identical
replayed snippets (n=40 pairs) disagree on the parity CLASS 7.5% of the time and on the named
VENDOR 22.5% of the time. That is the floor under every other number here.

PRODUCTION ITSELF: precision 0.353 (42 yes / 77 no of 119 named stamps). Roughly two of every
three named parity stamps fail the label criterion, and each one caps market_fit.

KNOWN-BAD VALIDATION (the harness's own blind-metric check) — on the eligible subset, unanimous
across all 5 reps: `pain_anchored` recall -42.8pp and named_rate -18.2pp, both outside the noise
floor => HARMFUL. `decoy` named_rate -17.3pp => HARMFUL, recall -22.8pp unanimous. The harness
detects a known-harmful change. NOTE what the decoy also proves: its `allow_case` reads +25.4pp,
i.e. reported ALONE, correct-abstention rate scores a deliberately broken config as an
improvement. allow_case is only interpretable next to recall.

THE LIVE CANDIDATE (`nogate`, eligible subset, unanimous in sign across all 5 reps):
precision +11.9pp, recall +20.0pp, allow_case +5.4pp, named_rate -5.5pp. Bootstrap over cases:
precision CI95 [-1.5, +29.3], recall CI95 [0.0, +48.0] — both include zero. VERDICT: UNPROVEN,
favorable-leaning. 22 eligible cases cannot resolve an effect this size; `power_to_resolve` says
41 (precision) / 32 (recall) eligible cases would. Note the stamp COUNT moves the wrong way, so
the old metric would have called this a regression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

HERE = Path(__file__).resolve().parent
CASES_F = HERE / "parity_eval_harness_cases.json"
PHRASES_F = HERE / "parity_eval_harness_phrases.json"
SERPER_F = HERE / "parity_eval_harness_serper_cache.json"
RESULTS_F = HERE / "parity_eval_harness_results.json"
LABELS_F = HERE / "parity_eval_harness_labels.json"
PAIRS_F = HERE / "parity_eval_harness_pairs.json"

CKPT_DIR = REPO / "output" / "checkpoints"
ARMS = ("prod", "nogate", "decoy", "pain_anchored")

# Corpus caps. Frozen here so the sample cannot be widened after seeing a result.
N_ELIGIBLE = 22          # cases where arm A gates >=1 of the top-2 rows (A != B possible)
N_NULL = 8               # null-contrast controls (A == B by construction)
MAX_PER_CHECKPOINT = 3   # padded-denominator guard: no niche may dominate the sample
SAMPLE_SEED = 20260817


# ---------------------------------------------------------------------------------------------
# production-faithful helpers (replicas used ONLY for case selection + runtime assertions;
# every measured query comes out of the real production method)
# ---------------------------------------------------------------------------------------------
def prod_overlap(a: str, b: str) -> set:
    """Verbatim token set of `_probe_mechanism_parity`'s local `_overlap` (:3400-3403)."""
    ta = {w for w in (a or "").lower().split() if len(w) > 3}
    tb = {w for w in (b or "").lower().split() if len(w) > 3}
    return ta & tb


def idea_text(d: dict) -> str:
    """Verbatim `idea_text` of the production loop (:3423)."""
    return f"{d.get('value_proposition') or ''} {d.get('technical_approach') or ''}"


def ranked_rows(rows: list, d: dict) -> list:
    """Production's `ranked` (:3424-3425) with its overlap counts attached."""
    scored = [(len(prod_overlap(r.get("focus", ""), idea_text(d))), r) for r in rows]
    return sorted(scored, key=lambda t: -t[0])


# ---------------------------------------------------------------------------------------------
# 1. corpus derivation
# ---------------------------------------------------------------------------------------------
def load_corpus() -> list[dict]:
    out = []
    for meta_f in sorted(CKPT_DIR.glob("*/metadata.json")):
        try:
            meta = json.loads(meta_f.read_text())
        except Exception:
            continue
        rows = meta.get("niche_incumbent_map") or []
        niche = (meta.get("niche_description") or "").strip()
        ref_f = meta_f.parent / "stage_5_3_refinement.json"
        if not rows or not niche or not ref_f.exists():
            continue
        try:
            ideas = json.loads(ref_f.read_text()).get("solution_ideas") or []
        except Exception:
            continue
        out.append({"ckpt": meta_f.parent.name, "niche": niche, "rows": rows, "ideas": ideas})
    return out


def derive(verbose: bool = True) -> dict:
    corpus = load_corpus()
    all_ideas = sum(len(c["ideas"]) for c in corpus)

    # Population census (re-derived here rather than inherited from any brief).
    n_gate_pass = n_gate_all_blocked = n_partial = 0
    for c in corpus:
        for d in c["ideas"]:
            top2 = ranked_rows(c["rows"], d)[:2]
            npass = sum(1 for n, _ in top2 if n > 0)
            if npass == len(top2) and npass > 0:
                n_gate_pass += 1
            elif npass == 0:
                n_gate_all_blocked += 1
            else:
                n_partial += 1

    # Deduplicate: the same idea recurs across regenerate/fork checkpoints of one niche.
    # Key = normalized (solution_name, value_proposition) — the two fields that decide the query.
    seen: dict[str, dict] = {}
    dupes = 0
    for c in corpus:
        for d in c["ideas"]:
            name = (d.get("solution_name") or "").strip()
            vp = " ".join((d.get("value_proposition") or "").lower().split())
            if not name or not vp:
                continue
            key = hashlib.sha256(f"{name.lower()}|{vp}".encode()).hexdigest()[:16]
            if key in seen:
                dupes += 1
                continue
            top2 = ranked_rows(c["rows"], d)[:2]
            gated = [r for n, r in top2 if n == 0]
            # sentinel for arm B: a token of the idea's own text, absent from every row's focus
            focus_tokens: set = set()
            for r in c["rows"]:
                focus_tokens |= {w for w in (r.get("focus") or "").lower().split() if len(w) > 3}
            cands = [w for w in idea_text(d).lower().split()
                     if len(w) > 3 and w.isalpha() and w not in focus_tokens]
            seen[key] = {
                "case_id": key,
                "ckpt": c["ckpt"],
                "niche": c["niche"],
                "solution_name": name,
                "eligible": len(gated) > 0,          # arm A != arm B
                "n_rows": len(c["rows"]),
                "n_gated_top2": len(gated),
                "sentinel": sorted(cands)[0] if cands else None,
                "shipped_parity": d.get("incumbent_parity"),
                "idea": d,
                "rows": c["rows"],
            }
    distinct = list(seen.values())
    usable = [c for c in distinct if c["sentinel"]]

    # Stratified, seeded, capped sample.
    rng = random.Random(SAMPLE_SEED)

    def pick(pool: list, want: int) -> list:
        pool = sorted(pool, key=lambda c: c["case_id"])
        rng.shuffle(pool)
        per: dict[str, int] = {}
        out = []
        for c in pool:
            if per.get(c["ckpt"], 0) >= MAX_PER_CHECKPOINT:
                continue
            per[c["ckpt"]] = per.get(c["ckpt"], 0) + 1
            out.append(c)
            if len(out) >= want:
                break
        return out

    elig = pick([c for c in usable if c["eligible"]], N_ELIGIBLE)
    null = pick([c for c in usable if not c["eligible"]], N_NULL)
    cases = elig + null

    # Arm D (decoy) rows: another SAMPLED checkpoint's incumbent rows, from a different niche.
    # Assigned deterministically here (frozen with the sample) so the known-bad control cannot be
    # re-rolled after seeing a result. `sentinel_decoy` must be absent from the FOREIGN focuses.
    by_ckpt = {c["ckpt"]: c["rows"] for c in cases}
    order = sorted(by_ckpt)
    for c in cases:
        i = order.index(c["ckpt"])
        c["decoy_ckpt"] = order[(i + 1) % len(order)]
        c["decoy_rows"] = by_ckpt[c["decoy_ckpt"]]
        ft: set = set()
        for r in c["decoy_rows"]:
            ft |= {w for w in (r.get("focus") or "").lower().split() if len(w) > 3}
        cands = [w for w in idea_text(c["idea"]).lower().split()
                 if len(w) > 3 and w.isalpha() and w not in ft]
        c["sentinel_decoy"] = sorted(cands)[0] if cands else None

    payload = {
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sample_seed": SAMPLE_SEED,
        "population": {
            "checkpoints_with_incumbent_map_and_ideas": len(corpus),
            "ideas_total": all_ideas,
            "ideas_distinct_after_dedup": len(distinct),
            "duplicate_ideas_dropped": dupes,
            "ideas_usable_sentinel_found": len(usable),
            "gate_top2_both_pass": n_gate_pass,
            "gate_top2_partially_blocked": n_partial,
            "gate_top2_fully_blocked": n_gate_all_blocked,
            "ELIGIBLE_for_gate_contrast": n_partial + n_gate_all_blocked,
            "ELIGIBLE_pct": round(100 * (n_partial + n_gate_all_blocked) / max(1, all_ideas), 1),
        },
        "sample": {
            "n_cases": len(cases),
            "n_eligible": len(elig),
            "n_null_contrast": len(null),
            "n_distinct_checkpoints": len({c["ckpt"] for c in cases}),
            "n_distinct_niches": len({c["niche"] for c in cases}),
        },
        "cases": cases,
    }
    CASES_F.write_text(json.dumps(payload, indent=1))
    if verbose:
        print(json.dumps({k: v for k, v in payload.items() if k != "cases"}, indent=1))
        print(f"wrote {CASES_F}")
    return payload


# ---------------------------------------------------------------------------------------------
# 2. record/replay plumbing
# ---------------------------------------------------------------------------------------------
class ReplaySerper:
    """Record/replay wrapper with the surface `_probe_mechanism_parity` uses (`.run`, `._cache`).

    A miss calls the REAL `CachedSerperDevTool` once and records the bytes; every later rep and
    arm replays them, so query-identical arms are byte-identical. `.queries` is the spy that the
    arm-B equivalence assertion reads — the queries production actually emitted, never predicted.
    """

    def __init__(self, allow_live: bool = True):
        self.disk: dict = json.loads(SERPER_F.read_text()) if SERPER_F.exists() else {}
        self._cache: dict = {}          # read by `_ma_search`; kept empty of live effects
        self.queries: list[str] = []
        self.live_calls = 0
        self.replays = 0
        self.allow_live = allow_live
        self._tool = None

    def _real(self):
        if self._tool is None:
            from nicheiq.tools.cached_serper_dev_tool import CachedSerperDevTool
            self._tool = CachedSerperDevTool()
        return self._tool

    def run(self, search_query: str = "", **kw) -> str:
        key = search_query.strip().lower()
        self.queries.append(search_query)
        if key in self.disk:
            self.replays += 1
            return self.disk[key]
        if not self.allow_live:
            raise RuntimeError(f"serper cache miss with --no-live: {search_query!r}")
        res = str(self._real().run(search_query=search_query))
        self.live_calls += 1
        self.disk[key] = res
        self.flush()
        return res

    def batch_run(self, queries: list[str]) -> dict:
        return {q: self.run(search_query=q) for q in queries}

    def flush(self) -> None:
        SERPER_F.write_text(json.dumps(self.disk, indent=0))


class _Niche:
    def __init__(self, desc: str):
        self.niche_description = desc


def build_crew(case: dict, phrases: dict, tool: ReplaySerper, rows: list, tracker=None):
    """Real `UnifiedSolutionCrew`, constructed WITHOUT `__init__` and given exactly the state the
    parity path reads. `object.__new__` avoids booting CrewAI agents (and a live SerperDevTool);
    every attribute set here is an input the production method reads through its own cache checks.
    """
    from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
    crew = object.__new__(UnifiedSolutionCrew)
    crew.niche_context = _Niche(case["niche"])
    crew.search_tool = tool
    crew.cost_tracker = tracker
    crew.audience_mapping = None
    crew.social_content = None
    crew.coverage_caveats = []
    crew._incumbent_rows = rows                     # pin 1
    crew._incumbent_probe_text = "PINNED-BY-HARNESS"
    crew._capability_phrase_map = dict(phrases)     # pin 2
    crew._parity_discovery_spent = 0                # pin 4
    crew._ma_serper_calls = 0
    crew._reset_search_arm_instrumentation()
    # Stubs — identical in every arm. The two additive probes and the recalibration tail are out
    # of scope for the query-construction change under test, and the tail is ~all of the cost.
    crew._probe_adjacent_markets = lambda top: ([], 0)
    crew._probe_toolbelt_free_bundle = lambda top: None
    crew._run_parallel = lambda *a, **k: []
    return crew


def record_phrases() -> dict:
    """One REAL production `_capability_phrases` call per checkpoint over that checkpoint's cases.
    Vendored so every later rep replays generator-emitted text."""
    from nicheiq.models.solution_idea import SolutionIdea
    payload = json.loads(CASES_F.read_text())
    store: dict = json.loads(PHRASES_F.read_text()) if PHRASES_F.exists() else {}
    by_ckpt: dict[str, list] = {}
    for c in payload["cases"]:
        by_ckpt.setdefault(c["ckpt"], []).append(c)
    tool = ReplaySerper()
    for ckpt, cases in sorted(by_ckpt.items()):
        want = [c for c in cases if c["solution_name"] not in store.get(ckpt, {})]
        if not want:
            continue
        ideas = [SolutionIdea.model_validate(c["idea"]) for c in want]
        crew = build_crew(cases[0], {}, tool, cases[0]["rows"])
        got = crew._capability_phrases(ideas)          # the REAL production method
        store.setdefault(ckpt, {}).update(got)
        PHRASES_F.write_text(json.dumps(store, indent=1))
        print(f"[phrases] {ckpt}: {len(got)} phrase(s)")
        for k, v in got.items():
            print(f"          {k!r:44s} -> {v!r}")
    missing = [(c["ckpt"], c["solution_name"]) for c in payload["cases"]
               if c["solution_name"] not in store.get(c["ckpt"], {})]
    print(f"phrases recorded for {sum(len(v) for v in store.values())} idea(s); "
          f"MISSING {len(missing)}: {missing[:5]}")
    return store


# ---------------------------------------------------------------------------------------------
# 3. the arms
# ---------------------------------------------------------------------------------------------
def arm_inputs(arm: str, case: dict, phrase: str) -> tuple[list, dict]:
    """(rows, phrase_map) for one arm. Arms differ ONLY here — never in the probe's body."""
    name = case["solution_name"]
    rows = [dict(r) for r in case["rows"]]
    if arm == "prod":
        return rows, {name: phrase}
    if arm == "nogate":
        s = case["sentinel"]
        for r in rows:
            r["focus"] = f"{r.get('focus') or ''} {s}".strip()
        return rows, {name: phrase}
    if arm == "pain_anchored":
        pain = " ".join(str(case["idea"].get("source_pain") or "").split()[:6])[:60]
        return rows, {name: pain or phrase}
    if arm == "decoy":
        drows = [dict(r) for r in case["decoy_rows"]]
        s = case["sentinel_decoy"] or case["sentinel"]
        for r in drows:
            r["focus"] = f"{r.get('focus') or ''} {s}".strip()
        return drows, {name: phrase}
    raise ValueError(arm)


def assert_arm_b_equivalence(case: dict, q_prod: list[str], q_nogate: list[str]) -> str:
    """Prove from the EMITTED queries that arm B is exactly 'the `_overlap > 0` gate deleted'.

    Returns "" on success, else a failure description (a violation is fatal, never a note).
    """
    rk = ranked_rows(case["rows"], case["idea"])[:2]
    top2_names = [r.get("name") for _, r in rk]
    passed = [r.get("name") for n, r in rk if n > 0]

    def named(qs, names):
        return [q for q in qs if any(q.startswith(f'"{n}"') for n in names if n)]

    a_named, b_named = named(q_prod, top2_names), named(q_nogate, top2_names)
    problems = []
    if sorted(a_named) != sorted(named(q_prod, passed)):
        problems.append(f"arm A emitted a name-anchored query for a GATED row: {a_named}")
    if not set(a_named) <= set(b_named):
        problems.append(f"arm B lost one of arm A's queries: A={a_named} B={b_named}")
    if len(b_named) != len(top2_names):
        problems.append(f"arm B did not query all of ranked[:2]: {b_named} vs {top2_names}")
    disc_a = [q for q in q_prod if q not in a_named]
    disc_b = [q for q in q_nogate if q not in b_named]
    if disc_a != disc_b:
        problems.append(f"discovery query differs: {disc_a} vs {disc_b}")
    if not case["eligible"] and sorted(q_prod) != sorted(q_nogate):
        problems.append(f"NULL-CONTRAST case is not query-identical: {q_prod} vs {q_nogate}")
    return "; ".join(problems)


# ---------------------------------------------------------------------------------------------
# 4. the run
# ---------------------------------------------------------------------------------------------
def parity_cap(note: str, idea=None) -> float | None:
    """The market_fit ceiling this stamp imposes — a MIRROR of rule (e) in `_validate_idea_scores`
    (:6008-6040), which is where the money actually moves. (A brief cited `:2473-2485` for the
    clamp; that range is `_get_ma_search_lock`. The `_parity_cap` helpers at :2679 / :2998 are the
    adjacent/family probes' own copies of the same mapping.)

    Faithful to rule (e) including the weak-wallet substitute branch and the
    `_is_non_direct_commercial_route` + `serp_competition == "open"` exemption, both read from the
    real production symbols. NOT modeled: composition with caps (b)/(d)/(f), which can bind lower
    for reasons unrelated to parity. Reported as parity's own marginal effect.
    """
    from nicheiq.config.settings import settings
    from nicheiq.crews.unified_solution_crew import _is_non_direct_commercial_route
    p = (note or "").strip().lower()
    if not p or p.startswith("none"):
        return None
    non_direct = bool(_is_non_direct_commercial_route(idea)) if idea is not None else False
    serp_open = getattr(idea, "serp_competition", None) == "open" if idea is not None else False
    if p.startswith("shipped"):
        return None if (non_direct and serp_open) else settings.parity_shipped_market_fit_cap
    if p.startswith("partial"):
        return None if (non_direct and serp_open) else settings.parity_partial_market_fit_cap
    if p.startswith("substitute"):
        pay = getattr(idea, "source_segment_payability", None) if idea is not None else None
        weak = (not non_direct and isinstance(pay, (int, float))
                and pay < settings.payability_low_threshold)
        return (settings.parity_substitute_weak_wallet_cap if weak
                else settings.parity_substitute_market_fit_cap)
    if p.startswith("bundled_free"):
        return settings.parity_bundled_free_cap
    return None


def parse_note(note: str) -> tuple[str, str]:
    """(parity_class, vendor) from a production note string, using production's own render shapes:
    'shipped by X: ev' / 'partial by X: ev' / 'substitute (X): ev' / 'none found'."""
    n = (note or "").strip()
    low = n.lower()
    if low.startswith("none"):
        return "none", ""
    for cls in ("shipped", "partial", "bundled_free"):
        if low.startswith(cls + " by "):
            return cls, n[len(cls) + 4:].split(":", 1)[0].strip()
    if low.startswith("substitute"):
        v = n.split("(", 1)[-1].split(")", 1)[0] if "(" in n else ""
        return "substitute", v.strip()
    if low.startswith("bundled_free"):
        v = n.split("(", 1)[-1].split(")", 1)[0] if "(" in n else ""
        return "bundled_free", v.strip()
    return "other", ""


def run(reps: int, arms: tuple, only: int | None, allow_live: bool) -> dict:
    from loguru import logger
    from nicheiq.models.solution_idea import SolutionIdea
    from nicheiq.utils.token_monitor import CostTracker

    payload = json.loads(CASES_F.read_text())
    cases = payload["cases"][:only] if only else payload["cases"]
    phrases = json.loads(PHRASES_F.read_text()) if PHRASES_F.exists() else {}
    tool = ReplaySerper(allow_live=allow_live)
    tracker = CostTracker()

    warnings: list[str] = []
    sink = logger.add(lambda m: warnings.append(m.record["message"]), level="WARNING")

    results = json.loads(RESULTS_F.read_text()) if RESULTS_F.exists() else {"cells": []}
    done = {(c["case_id"], c["arm"], c["rep"]) for c in results["cells"]}
    fatal: list[str] = []
    t0 = time.time()

    for rep in range(reps):
        for case in cases:
            phrase = phrases.get(case["ckpt"], {}).get(case["solution_name"])
            if not phrase:
                fatal.append(f"{case['case_id']}: no recorded capability phrase")
                continue
            emitted: dict[str, list[str]] = {}
            for arm in arms:
                if (case["case_id"], arm, rep) in done:
                    continue
                rows, pmap = arm_inputs(arm, case, phrase)
                idea = SolutionIdea.model_validate(case["idea"])
                mf_before = idea.market_fit_score
                crew = build_crew(case, pmap, tool, rows, tracker)
                warnings.clear()
                tool.queries = []
                crew._probe_mechanism_parity([idea])
                qs = list(tool.queries)
                emitted[arm] = qs
                note = (idea.incumbent_parity or "").strip()
                cls, vendor = parse_note(note)
                cap = parity_cap(note, idea)
                cell = {
                    "case_id": case["case_id"], "arm": arm, "rep": rep,
                    "solution_name": case["solution_name"], "ckpt": case["ckpt"],
                    "eligible": case["eligible"], "queries": qs, "phrase": pmap[case["solution_name"]],
                    "note": note, "parity_class": cls, "vendor": vendor,
                    "mf_before": mf_before,
                    "mf_capped": min(mf_before, cap) if (cap and mf_before) else mf_before,
                    "probe_warnings": [w for w in warnings if "Parity" in w or "parity" in w],
                    "stamp_written": bool(note),
                }
                results["cells"].append(cell)
                if not note:
                    fatal.append(f"{case['case_id']}/{arm}/{rep}: NO STAMP WRITTEN "
                                 f"(fail-soft swallow?) warnings={warnings[:2]}")
                print(f"[{rep}] {arm:14s} {case['solution_name'][:34]:34s} "
                      f"{cls:11s} {vendor[:30]:30s} q={len(qs)}")
            if "prod" in emitted and "nogate" in emitted:
                bad = assert_arm_b_equivalence(case, emitted["prod"], emitted["nogate"])
                if bad:
                    fatal.append(f"ARM-B EQUIVALENCE VIOLATED {case['case_id']}: {bad}")
            RESULTS_F.write_text(json.dumps(results, indent=1))

    logger.remove(sink)
    tool.flush()
    spend = {}
    try:
        spend = tracker.get_summary() if hasattr(tracker, "get_summary") else {}
    except Exception as e:
        spend = {"error": str(e)}
    results["spend"] = {
        "serper_live_calls": tool.live_calls, "serper_replays": tool.replays,
        "llm": spend, "wall_seconds": round(time.time() - t0, 1),
    }
    results["fatal"] = fatal
    RESULTS_F.write_text(json.dumps(results, indent=1))
    print(f"\nserper live={tool.live_calls} replay={tool.replays}  "
          f"wall={results['spend']['wall_seconds']}s")
    if fatal:
        print("\n!!! FATAL (results are not trustworthy until resolved):")
        for f in fatal[:20]:
            print("   ", f)
    return results


# ---------------------------------------------------------------------------------------------
# 5. labels + scoring
# ---------------------------------------------------------------------------------------------
def pair_key(case_id: str, vendor: str) -> str:
    return hashlib.sha256(f"{case_id}|{vendor.strip().lower()}".encode()).hexdigest()[:12]


def export_labels() -> None:
    """Arm-blind pair list. Arm and rep are STRIPPED: the same vendor stamped by two arms is one
    pair with one label, so a label cannot be tuned toward an arm."""
    res = json.loads(RESULTS_F.read_text())
    cases = {c["case_id"]: c for c in json.loads(CASES_F.read_text())["cases"]}
    serper = json.loads(SERPER_F.read_text()) if SERPER_F.exists() else {}
    pairs: dict = {}
    for c in res["cells"]:
        if not c["vendor"]:
            continue
        k = pair_key(c["case_id"], c["vendor"])
        p = pairs.setdefault(k, {
            "pair_key": k, "case_id": c["case_id"], "vendor": c["vendor"],
            "solution_name": c["solution_name"],
            "value_proposition": cases[c["case_id"]]["idea"].get("value_proposition"),
            "technical_approach": cases[c["case_id"]]["idea"].get("technical_approach"),
            "niche": cases[c["case_id"]]["niche"],
            "classes_seen": [], "evidence_seen": [], "queries": [],
        })
        if c["parity_class"] not in p["classes_seen"]:
            p["classes_seen"].append(c["parity_class"])
        ev = c["note"].split(":", 1)[-1].strip()
        if ev and ev not in p["evidence_seen"]:
            p["evidence_seen"].append(ev)
        for q in c["queries"]:
            if q not in p["queries"]:
                p["queries"].append(q)
    for p in pairs.values():
        # Needles: the full vendor string, then each comma-separated element, then the first word.
        # A `covered_by` holding a LIST ("FloQast, Gravity Software, OneStream") violates the
        # field's one-name contract; it is counted, not silently dropped.
        v = p["vendor"]
        parts = [x.strip() for x in v.split(",") if x.strip()]
        p["multi_vendor_field"] = len(parts) > 1
        needles = [v.lower()] + [x.lower() for x in parts] + [v.split()[0].strip(",").lower()]
        snips = []
        for q in p["queries"]:
            s = serper.get(q.strip().lower(), "")
            for nd in needles:
                if nd and nd in s.lower():
                    idx = s.lower().find(nd)
                    snips.append(s[max(0, idx - 500):idx + 900])
                    break
        p["snippet_context"] = snips[:3]
        # HALLUCINATION FLAG: the stamped vendor appears NOWHERE in the search results the judge
        # was shown. The prompt says "Cite only what the results actually show"; a miss here means
        # the name came from the model's parameters, not from the evidence — and it still caps
        # market_fit. Reported per arm as `vendor_not_in_evidence_rate`.
        p["vendor_in_snippets"] = bool(snips)
    order = sorted(pairs.values(), key=lambda p: p["pair_key"])
    PAIRS_F.write_text(json.dumps({"n_pairs": len(order), "pairs": order}, indent=1))
    print(f"wrote {PAIRS_F}: {len(order)} distinct (case, vendor) pairs to label")


def _band(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "min": round(min(vals), 3), "max": round(max(vals), 3),
            "mean": round(statistics.mean(vals), 3), "spread": round(max(vals) - min(vals), 3),
            "sd": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0}


def score() -> dict:
    from nicheiq.models.solution_idea import SolutionIdea
    res = json.loads(RESULTS_F.read_text())
    labels = json.loads(LABELS_F.read_text()).get("labels", {}) if LABELS_F.exists() else {}
    cells = res["cells"]
    # Recompute the money effect with the faithful rule-(e) mirror (cells written before that
    # mirror existed carry a cruder value; the stamp itself is untouched).
    ideas = {c["case_id"]: SolutionIdea.model_validate(c["idea"])
             for c in json.loads(CASES_F.read_text())["cases"]}
    for c in cells:
        obj = ideas.get(c["case_id"])
        cap = parity_cap(c["note"], obj)
        mf = c.get("mf_before")
        c["mf_capped"] = min(mf, cap) if (cap and isinstance(mf, (int, float))) else mf
    arms = sorted({c["arm"] for c in cells})
    reps = sorted({c["rep"] for c in cells})

    pairs = {p["pair_key"]: p for p in
             (json.loads(PAIRS_F.read_text())["pairs"] if PAIRS_F.exists() else [])}

    def lab(c) -> str:
        if not c["vendor"]:
            return "none"
        return labels.get(pair_key(c["case_id"], c["vendor"]), {}).get("label", "UNLABELED")

    def flag(c, key: str) -> bool:
        return bool(pairs.get(pair_key(c["case_id"], c["vendor"]), {}).get(key))

    # gold-positive ideas: some arm/rep named a vendor labelled `yes`
    gold_pos = {c["case_id"] for c in cells if lab(c) == "yes"}
    all_ids = {c["case_id"] for c in cells}
    gold_neg = all_ids - gold_pos

    def metrics(sel: list) -> dict:
        named = [c for c in sel if c["vendor"]]
        yes = sum(1 for c in named if lab(c) == "yes")
        no = sum(1 for c in named if lab(c) == "no")
        unc = sum(1 for c in named if lab(c) == "unclear")
        unl = sum(1 for c in named if lab(c) == "UNLABELED")
        # allow-case over gold-negative ideas
        gn = [c for c in sel if c["case_id"] in gold_neg]
        allow = sum(1 for c in gn if c["parity_class"] == "none")
        # recall over gold-positive ideas
        gp = [c for c in sel if c["case_id"] in gold_pos]
        rec_hit = sum(1 for c in gp if lab(c) == "yes")
        fp_loss = [c["mf_before"] - c["mf_capped"] for c in named
                   if lab(c) in ("no", "unclear") and c["mf_before"] is not None]
        tp_loss = [c["mf_before"] - c["mf_capped"] for c in named
                   if lab(c) == "yes" and c["mf_before"] is not None]
        return {
            "cells": len(sel), "named": len(named),
            "named_rate_BLIND_METRIC": round(len(named) / len(sel), 3) if sel else None,
            "yes": yes, "no": no, "unclear": unc, "unlabeled": unl,
            "precision": round(yes / (yes + no), 3) if (yes + no) else None,
            "recall_pooled_oracle": round(rec_hit / len(gp), 3) if gp else None,
            "allow_case": round(allow / len(gn), 3) if gn else None,
            "mf_loss_to_false_positives": round(sum(fp_loss), 3),
            "mf_loss_to_true_positives": round(sum(tp_loss), 3),
            "vendor_not_in_evidence_rate": (
                round(sum(1 for c in named if not flag(c, "vendor_in_snippets")) / len(named), 3)
                if named else None),
            "multi_vendor_field_rate": (
                round(sum(1 for c in named if flag(c, "multi_vendor_field")) / len(named), 3)
                if named else None),
        }

    out = {
        "n_cells": len(cells), "arms": arms, "reps": len(reps),
        "n_cases": len(all_ids),
        "gold_positive_ideas": len(gold_pos), "gold_negative_ideas": len(gold_neg),
        "per_arm": {}, "noise_band": {}, "null_contrast": {}, "eligible_only": {},
    }
    for a in arms:
        sel = [c for c in cells if c["arm"] == a]
        out["per_arm"][a] = metrics(sel)
        out["eligible_only"][a] = metrics([c for c in sel if c["eligible"]])
        # ---- NOISE BAND: the same arm against itself, rep by rep ----
        per_rep = {m: [] for m in ("named_rate_BLIND_METRIC", "precision", "allow_case",
                                  "recall_pooled_oracle")}
        for r in reps:
            m = metrics([c for c in sel if c["rep"] == r])
            for k in per_rep:
                if m[k] is not None:
                    per_rep[k].append(m[k])
        out["noise_band"][a] = {k: _band(v) for k, v in per_rep.items()}

    # ---- second, independent read on the band: null-contrast cases, where prod and nogate
    #      emit byte-identical queries, so any difference is judge noise ----
    nulls = [c for c in cells if not c["eligible"]]
    for a in arms:
        out["null_contrast"][a] = metrics([c for c in nulls if c["arm"] == a])
    if "prod" in arms and "nogate" in arms:
        d = {}
        for k in ("named_rate_BLIND_METRIC", "precision", "allow_case"):
            x, y = out["null_contrast"]["prod"].get(k), out["null_contrast"]["nogate"].get(k)
            d[k] = round(y - x, 3) if (x is not None and y is not None) else None
        out["null_contrast"]["nogate_minus_prod_IS_PURE_NOISE"] = d

    # ---- PAIRED per-rep contrast (the sharper test) ----
    # For each rep r, delta_r = metric(arm, r) - metric(prod, r), over the SAME cases with the SAME
    # replayed snippets. A pooled-mean-vs-single-rep-spread comparison is conservative by ~sqrt(reps);
    # this pairs within rep instead and additionally requires the sign to be unanimous. An effect is
    # only REAL when (a) every rep agrees on the sign AND (b) |mean delta| exceeds the null-contrast
    # noise floor for that metric (the A-vs-B difference on cases where the arms are query-identical).
    METRIC_KEYS = ("named_rate_BLIND_METRIC", "precision", "allow_case", "recall_pooled_oracle")
    null_floor = {}
    for k in METRIC_KEYS:
        ds = []
        for r in reps:
            x = metrics([c for c in nulls if c["arm"] == "prod" and c["rep"] == r]).get(k)
            y = metrics([c for c in nulls if c["arm"] == "nogate" and c["rep"] == r]).get(k)
            if x is not None and y is not None:
                ds.append(abs(y - x))
        null_floor[k] = round(max(ds), 3) if ds else None
    out["null_contrast_noise_floor_per_rep_abs_max"] = null_floor

    # `paired`          — all 30 cases (8 of them null-contrast, where the arms are identical by
    #                     construction, so they can only dilute a real effect toward zero).
    # `paired_eligible` — the 22 cases where arm A gates >=1 of ranked[:2], i.e. the ONLY cases
    #                     where the gate can change anything. Eligibility was frozen at --derive
    #                     time, before the first judge call, so this is a pre-specified subgroup
    #                     and not a post-hoc slice. The noise floor is unchanged (it is measured on
    #                     the null cases, which are by definition not in this subgroup).
    out["paired"] = {}
    out["paired_eligible"] = {}
    for a in arms:
        if a == "prod":
            continue
        blk, blk_e = {}, {}
        for k in METRIC_KEYS:
            ds, ds_e = [], []
            for r in reps:
                x = metrics([c for c in cells if c["arm"] == "prod" and c["rep"] == r]).get(k)
                y = metrics([c for c in cells if c["arm"] == a and c["rep"] == r]).get(k)
                if x is not None and y is not None:
                    ds.append(round(y - x, 3))
                xe = metrics([c for c in cells if c["arm"] == "prod" and c["rep"] == r
                              and c["eligible"]]).get(k)
                ye = metrics([c for c in cells if c["arm"] == a and c["rep"] == r
                              and c["eligible"]]).get(k)
                if xe is not None and ye is not None:
                    ds_e.append(round(ye - xe, 3))
            if ds_e:
                mean_e = statistics.mean(ds_e)
                floor = null_floor.get(k) or 0.0
                unan_e = all(d > 0 for d in ds_e) or all(d < 0 for d in ds_e)
                blk_e[k] = {
                    "per_rep_deltas": ds_e, "mean_delta": round(mean_e, 3),
                    "sign_unanimous": unan_e, "null_contrast_floor": floor,
                    "verdict": ("UNPROVEN (sign flips across reps)" if not unan_e else
                                "UNPROVEN (inside null-contrast noise floor)"
                                if abs(mean_e) <= floor else
                                "REAL improvement" if mean_e > 0 else "HARMFUL"),
                }
            else:
                blk_e[k] = "n/a"
            if not ds:
                blk[k] = "n/a"
                continue
            mean = statistics.mean(ds)
            floor = null_floor.get(k) or 0.0
            unanimous = all(d > 0 for d in ds) or all(d < 0 for d in ds)
            blk[k] = {
                "per_rep_deltas": ds, "mean_delta": round(mean, 3),
                "sign_unanimous": unanimous, "null_contrast_floor": floor,
                "verdict": ("UNPROVEN (sign flips across reps)" if not unanimous else
                            "UNPROVEN (inside null-contrast noise floor)" if abs(mean) <= floor else
                            "REAL improvement" if mean > 0 else "HARMFUL"),
            }
        out["paired"][a] = blk
        out["paired_eligible"][a] = blk_e

    # ---- LABEL-FREE NOISE FLOOR: replay disagreement on the null-contrast cases ----
    # On a null-contrast case the two arms issue byte-identical queries and replay byte-identical
    # snippets, so the ONLY difference between the two cells is a second invocation of the judge.
    # Any disagreement there is pure judge noise, measured without reference to any label.
    disagree_cls = disagree_vendor = pairs_n = 0
    for case_id in {c["case_id"] for c in nulls}:
        for r in reps:
            a_cell = [c for c in nulls if c["case_id"] == case_id and c["rep"] == r
                      and c["arm"] == "prod"]
            b_cell = [c for c in nulls if c["case_id"] == case_id and c["rep"] == r
                      and c["arm"] == "nogate"]
            if not (a_cell and b_cell):
                continue
            pairs_n += 1
            disagree_cls += int(a_cell[0]["parity_class"] != b_cell[0]["parity_class"])
            disagree_vendor += int(a_cell[0]["vendor"].strip().lower()
                                   != b_cell[0]["vendor"].strip().lower())
    out["judge_replay_noise_LABEL_FREE"] = {
        "identical_query_cell_pairs": pairs_n,
        "parity_class_disagreement_rate": round(disagree_cls / pairs_n, 3) if pairs_n else None,
        "named_vendor_disagreement_rate": round(disagree_vendor / pairs_n, 3) if pairs_n else None,
        "note": ("Two invocations of the judge on byte-identical queries and byte-identical "
                 "replayed snippets. This is the floor under EVERY number in this file."),
    }

    # ---- BOOTSTRAP over CASES: an effect CI, and the null-contrast noise distribution ----
    # Resampling cases (not cells) is the right unit: cases are the independent sampling unit and
    # reps within a case are correlated. 2000 draws, fixed seed, so the number is reproducible.
    def boot(subset: list, a: str, k: str, n_draws: int = 2000, seed: int = 7) -> dict:
        ids = sorted({c["case_id"] for c in subset})
        by_id = {i: [c for c in subset if c["case_id"] == i] for i in ids}
        rng2 = random.Random(seed)
        deltas = []
        for _ in range(n_draws):
            draw = [c for i in (rng2.choice(ids) for _ in ids) for c in by_id[i]]
            x = metrics([c for c in draw if c["arm"] == "prod"]).get(k)
            y = metrics([c for c in draw if c["arm"] == a]).get(k)
            if x is not None and y is not None:
                deltas.append(y - x)
        if not deltas:
            return {"n": 0}
        deltas.sort()
        lo, hi = deltas[int(0.025 * len(deltas))], deltas[int(0.975 * len(deltas)) - 1]
        return {"n_cases": len(ids), "ci95": [round(lo, 3), round(hi, 3)],
                "median": round(deltas[len(deltas) // 2], 3),
                "abs_p975": round(sorted(abs(d) for d in deltas)[int(0.975 * len(deltas)) - 1], 3)}

    elig_cells = [c for c in cells if c["eligible"]]
    out["bootstrap"] = {"note": (
        "`noise` = the same bootstrap run on the NULL-CONTRAST cases, where the two arms are "
        "query-identical, so its abs_p975 is the magnitude a difference must beat to be an "
        "effect rather than judge noise. `effect_eligible` = the candidate's contrast on the "
        "cases where the gate can change anything.")}
    for a in arms:
        if a == "prod":
            continue
        out["bootstrap"][a] = {
            k: {"effect_eligible": boot(elig_cells, a, k), "noise": boot(nulls, a, k)}
            for k in METRIC_KEYS}

    # ---- verdicts (conservative variant: pooled delta vs within-arm rep spread) ----
    def verdict(a: str, base: str = "prod") -> dict:
        v = {}
        for k in ("named_rate_BLIND_METRIC", "precision", "allow_case", "recall_pooled_oracle"):
            hi, lo = out["per_arm"][a].get(k), out["per_arm"][base].get(k)
            if hi is None or lo is None:
                v[k] = "n/a"
                continue
            delta = hi - lo
            band = max(out["noise_band"][a][k].get("spread", 0),
                       out["noise_band"][base][k].get("spread", 0))
            v[k] = {
                "delta_vs_" + base: round(delta, 3), "noise_band_spread": round(band, 3),
                "verdict": ("UNPROVEN (inside noise band)" if abs(delta) <= band
                            else ("REAL improvement" if delta > 0 else "HARMFUL")),
            }
        return v
    out["verdict_conservative"] = {a: verdict(a) for a in arms if a != "prod"}

    # ---- POWER: how many eligible cases would it take to resolve what is currently UNPROVEN? ----
    # The bootstrap CI half-width shrinks as 1/sqrt(n_cases), so the n at which the half-width
    # equals the observed effect is n_now * (halfwidth / |effect|)^2. Reported so "unproven" comes
    # with a price tag instead of a shrug.
    out["power_to_resolve"] = {}
    for a in arms:
        if a == "prod":
            continue
        blk = {}
        for k in METRIC_KEYS:
            b = out["bootstrap"][a][k]["effect_eligible"]
            if not b.get("ci95"):
                continue
            lo, hi = b["ci95"]
            eff, half = abs(b["median"]), (hi - lo) / 2
            blk[k] = {
                "observed_effect": b["median"], "ci95": b["ci95"],
                "ci_excludes_zero": (lo > 0 or hi < 0),
                "eligible_cases_needed": (int(b["n_cases"] * (half / eff) ** 2) + 1
                                          if eff > 0 else None),
                "eligible_cases_used": b["n_cases"],
            }
        out["power_to_resolve"][a] = blk

    # ---- MECHANISM: what does deleting the gate actually unlock? ----
    # Pair prod and nogate cell-by-cell on the eligible cases, isolate the queries nogate issued
    # that prod's gate suppressed, and ask whether the stamp nogate produced came from one of them.
    # This is the difference between "the config scores better" and "the config's own added
    # evidence is what produced the change".
    paired_cells: dict = {}
    for c in cells:
        paired_cells.setdefault((c["case_id"], c["rep"]), {})[c["arm"]] = c
    extra_hist: dict = {}
    unlocked = {"cells_with_extra_query": 0, "stamp_traced_to_gated_query": 0,
                "labels_of_unlocked_stamps": {}, "examples": []}
    for (cid, r), am in sorted(paired_cells.items()):
        a, b = am.get("prod"), am.get("nogate")
        if not a or not b or not a["eligible"]:
            continue
        extra = [q for q in b["queries"] if q not in a["queries"]]
        extra_hist[len(extra)] = extra_hist.get(len(extra), 0) + 1
        if not extra:
            continue
        unlocked["cells_with_extra_query"] += 1
        v = (b["vendor"] or "").strip().lower()
        if v and any(v.split()[0] in q.lower() for q in extra):
            unlocked["stamp_traced_to_gated_query"] += 1
            lb = lab(b)
            unlocked["labels_of_unlocked_stamps"][lb] = \
                unlocked["labels_of_unlocked_stamps"].get(lb, 0) + 1
            ex = [b["solution_name"], b["vendor"], lb]
            if ex not in unlocked["examples"]:
                unlocked["examples"].append(ex)
    n_no = unlocked["labels_of_unlocked_stamps"].get("no", 0)
    n_yes = unlocked["labels_of_unlocked_stamps"].get("yes", 0)
    unlocked["precision_of_unlocked_stamps"] = (round(n_yes / (n_yes + n_no), 3)
                                                if (n_yes + n_no) else None)
    unlocked["extra_queries_per_cell_hist"] = extra_hist
    unlocked["note"] = (
        "Compare `precision_of_unlocked_stamps` with prod's own precision. If they are equal, gate "
        "deletion is buying MORE stamps at the SAME quality, and any aggregate precision change "
        "must come from DISPLACEMENT (better-sourced stamps replacing worse ones on the same "
        "cases), not from the added evidence being better.")
    out["gate_unlock_analysis"] = unlocked

    (HERE / "parity_eval_harness_score.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--record-phrases", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--export-labels", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--only", type=int, default=None)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--no-live", action="store_true")
    a = ap.parse_args()
    if a.derive:
        derive()
    if a.record_phrases:
        record_phrases()
    if a.smoke:
        run(1, tuple(a.arms.split(",")), 1, not a.no_live)
    if a.run:
        run(a.reps, tuple(a.arms.split(",")), a.only, not a.no_live)
    if a.export_labels:
        export_labels()
    if a.score:
        score()


if __name__ == "__main__":
    main()
