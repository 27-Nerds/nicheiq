#!/usr/bin/env python3
"""Does the `incumbent_parity` market_fit clamp earn the right to move money?

    source .venv/bin/activate
    python -m probes.parity_cap_advisory_ab            # full run, writes the results JSON
    python -m probes.parity_cap_advisory_ab --guards    # blind-metric guards only

THE QUESTION (not "is the verdict right")
-----------------------------------------
Rule (e) clamps `market_fit_score` when a web-verified incumbent finding is stamped. The
stamp's precision is contested (~0.35 on one hand-labelled criterion, 1.00 on a looser one —
`probes/parity_eval_harness.py`). This probe does not re-litigate the verdict. It asks whether
ranking quality holds when the parity term is removed from the clamp: if it does, the clamp is
spending ranking accuracy for nothing and belongs in the disclosure layer, not the score.

WHERE THE CODE ACTUALLY IS (re-derived; the briefing citation is wrong)
----------------------------------------------------------------------
* rule (e) — the clamp that moves money — is in `UnifiedSolutionCrew._validate_idea_caps`,
  unified_solution_crew.py :6006-6039 (inside a method that starts at :5942). It is NOT in
  `_validate_idea_scores` (:6097); that method is the SET-LEVEL pass and only *delegates* the
  per-idea caps to `_validate_idea_caps`. `probes/parity_eval_harness.py:560` already recorded
  the same correction.
* the `_parity_cap` helpers at :2679 and :2993 are the adjacent/family probes' own copies of the
  class->ceiling mapping, used only for overwrite comparison. Neither is the money path, and
  neither models the weak-wallet substitute branch.

ISOLATION — the whole experiment
--------------------------------
`market_fit_score_raw` is NOT the pre-cap score. It is the GENERATOR's self-score before the
CALIBRATION CRITIC (`solution_idea.py:1017`, written by `_apply` at :5593). Reverting to it would
undo the critic as well as every cap — worse than the "remove all caps" confound the brief warned
about. Verified on disk: re-running production `_validate_idea_caps` over the stored ideas is a
no-op for 1822/1885 (the 63 movers are pre-dating-rule runs), so the stored `market_fit_score` is
post-critic AND post-cap.

That means the post-critic pre-cap value v is CENSORED for exactly the ideas we care about. This
probe therefore does not guess v globally. It uses the algebra of the rules: every cap is
`if mf > K: mf = K` with K independent of mf, so the stored score is `min(v, K1, K2, ...)`.
Consequently:

* Let C_non = min of every NON-parity ceiling that applies (rules b/d/f/g), obtained by running
  PRODUCTION `_validate_idea_caps` on a copy with mf=1.0 and the five parity settings zeroed
  (rule (e) is guarded by `pcap > 0`, so zeroing them disables exactly that rule and nothing else).
* Let C_all = the same call with production settings = min(C_non, c_e).
* If C_all == C_non the parity term is NOT the binding ceiling and arm B is provably identical.
* If C_all < C_non and the stored score equals C_all, parity is the binding ceiling; only then is
  a counterfactual needed, and it is bounded: mf_B in [stored, C_non].

Arm B is reported as a BRACKET over that interval, never as a single invented number:
  B-hi   v = C_non          -> maximum possible effect of the clamp (upper bound on blast radius)
  B-imp  v = raw + delta    -> delta = median(stored - raw) measured on the UNBOUND ideas, where
                               stored == v exactly, so the imputation is fitted on disk data
  B-lo   v = stored         -> identical to arm A by construction (the trivial lower bound)

Everything else — the composite, the audience-fit penalty, the feasibility adjustment, ranking_seo,
the deterministic tie-break — comes from production `compute_solution_scores`. Nothing is re-derived.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import statistics
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from nicheiq.config.settings import settings  # noqa: E402
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew  # noqa: E402
from nicheiq.models.solution_idea import BaseSolutionIdea, visible_ideas  # noqa: E402
from nicheiq.utils.score_helpers import compute_solution_scores  # noqa: E402

# Reused, not re-derived: the rule-(e) mirror and the analyst oracle's label loaders.
from probes.analyst_agreement import (  # noqa: E402
    _NEGATIVES,
    _SEO_PICKS,
    _norm,
    _ordered_picks_from_shortlist,
    _picks_from_specs,
)
from probes.parity_eval_harness import parity_cap as mirror_parity_cap  # noqa: E402

OUT = ROOT / "probes" / "parity_cap_advisory_ab_results.json"
TOL = 0.006

# The five settings rule (e) reads. Each is `0 disables` *because* rule (e) guards on `pcap > 0`.
PARITY_SETTINGS = (
    "parity_shipped_market_fit_cap",
    "parity_partial_market_fit_cap",
    "parity_substitute_market_fit_cap",
    "parity_substitute_weak_wallet_cap",
    "parity_bundled_free_cap",
)

# Scores that must survive reconstruction (same guard as analyst_agreement: a silently dropped
# field once manufactured a BUILD-vs-KILLED inversion that never existed).
LOAD_BEARING = (
    "market_fit_score",
    "technical_feasibility_score",
    "novelty_score",
    "seo_scalability_score",
    "build_feasibility_score",
    "solo_dev_feasibility",
)

_UUID8 = re.compile(r"([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}")


@contextmanager
def parity_off():
    old = {k: getattr(settings, k) for k in PARITY_SETTINGS}
    for k in PARITY_SETTINGS:
        setattr(settings, k, 0.0)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(settings, k, v)


# ---------------------------------------------------------------------------------------------
# 1. corpus
# ---------------------------------------------------------------------------------------------
def load_corpus() -> list[dict]:
    """Every run's FINAL idea set, from the refinement checkpoint (`stage_5_3_refinement.json`).

    Not the preview corpus the analyst-oracle probe uses: `preview_report_*.json` carries none of
    `market_fit_score_raw`, `serp_competition`, or `market_fit_claimed_route` (0/498 for
    serp_competition), so rule (e)'s non-direct-route exemption and rules (f)/(g) cannot be
    reconstructed there at all. Ranking is still done with the same production ranker.
    """
    runs = []
    for path in sorted(glob.glob(str(ROOT / "output/checkpoints/*/stage_5_3_refinement.json"))):
        dirname = os.path.basename(os.path.dirname(path))
        m = _UUID8.search(dirname)
        payload = json.load(open(path))
        raws = [a for a in (payload.get("solution_ideas") or []) if isinstance(a, dict)]
        ideas = []
        for a in raws:
            try:
                idea = BaseSolutionIdea.model_validate(a)
            except Exception:
                continue
            _assert_sane(a, idea, path)
            ideas.append((a, idea))
        if not ideas:
            continue
        runs.append({
            "path": path,
            "dir": dirname,
            "run_id": m.group(1) if m else None,
            "ideas": ideas,
        })
    return runs


def _assert_sane(src: dict, idea: BaseSolutionIdea, path: str) -> None:
    for field in LOAD_BEARING:
        if isinstance(src.get(field), (int, float)) and getattr(idea, field, None) is None:
            raise SystemExit(
                f"HARNESS BUG: '{field}' present in source ({src[field]}) but None after "
                f"reconstruction on {src.get('solution_name')!r} in {path}. A score is being "
                f"dropped; fix the loader before trusting any number this probe prints."
            )


# ---------------------------------------------------------------------------------------------
# 2. ceilings, straight out of production
# ---------------------------------------------------------------------------------------------
def _ceiling(idea, start: float = 1.0) -> float:
    """min of every market_fit ceiling that applies to this idea, per PRODUCTION rule code.

    Every cap fires on `mf > K` and assigns the constant K, so starting from 1.0 makes each
    applicable rule fire once and the result is order-independent.
    """
    probe = idea.model_copy(deep=True)
    probe.market_fit_score = start
    UnifiedSolutionCrew._validate_idea_caps(None, probe)
    return probe.market_fit_score


def classify(idea) -> dict:
    """Per-idea ceiling decomposition + whether parity is the BINDING ceiling."""
    stored = getattr(idea, "market_fit_score", None)
    c_all = _ceiling(idea)
    with parity_off():
        c_non = _ceiling(idea)
    par = (getattr(idea, "incumbent_parity", None) or "").strip()
    mirror = mirror_parity_cap(par, idea)
    # cross-check the reused mirror against production's own decision
    expect = min([c_non] + ([mirror] if mirror is not None and mirror > 0 else []))
    mirror_ok = abs(expect - c_all) <= TOL
    parity_is_ceiling = c_all < c_non - TOL
    row = {
        "name": getattr(idea, "solution_name", None),
        "stored": stored,
        "raw": getattr(idea, "market_fit_score_raw", None),
        "c_all": round(c_all, 4),
        "c_non": round(c_non, 4),
        "parity": par,
        "parity_class": (par.split()[0].lower() if par else None),
        "mirror_cap": mirror,
        "mirror_ok": mirror_ok,
        "parity_is_ceiling": parity_is_ceiling,
        "status": (getattr(idea, "candidate_status", None) or "active"),
    }
    if not isinstance(stored, (int, float)):
        row["kind"] = "ineligible_no_market_fit"
    elif stored > c_all + TOL:
        # stored above the ceiling production would impose => this checkpoint predates the rule
        # (or a setting moved since). No counterfactual is defined; excluded from arm B.
        row["kind"] = "ineligible_unclamped_legacy"
    elif parity_is_ceiling and abs(stored - c_all) <= TOL:
        row["kind"] = "parity_bound"
    elif parity_is_ceiling:
        row["kind"] = "parity_slack"        # a lower ceiling than parity's already bound it
    else:
        row["kind"] = "unbound_by_parity"
    return row


# ---------------------------------------------------------------------------------------------
# 3. arms
# ---------------------------------------------------------------------------------------------
def counterfactual(row: dict, delta: float, arm: str) -> float:
    """market_fit under arm B for one idea. Only `parity_bound` ideas can move."""
    stored = row["stored"]
    if row["kind"] != "parity_bound":
        return stored
    if arm == "B-hi":
        v = 1.0
    elif arm == "B-imp":
        raw = row["raw"]
        if raw is None:
            return stored          # no fitted starting point => leave at arm A
        v = max(0.0, min(1.0, raw + delta))
    elif arm == "B-lo":
        v = stored
    elif arm == "GUARD-nocaps":
        return 1.0                 # deliberately broken: no ceiling at all
    else:
        raise ValueError(arm)
    return round(min(v, row["c_non"]), 4)


def placebo_targets(run: dict, rows: list, seed: int = 7, ref: str = "B-hi",
                    delta: float = 0.0) -> dict[int, float]:
    """THE GUARD ON THE HEADLINE NUMBER.

    Arm B raises the market_fit of the parity-bound ideas, which mechanically dilutes the rank of
    every idea that does NOT rise — including the analyst's picks. So an AUC drop under arm B is
    only evidence about PARITY if the same drop does not appear when the same number of ideas are
    raised by the same amounts in the same runs, chosen without reference to parity. This arm does
    exactly that: same run, same count, same deltas, targets drawn (seeded) from the parity-free
    ideas instead.

    `ref` names the arm being nulled, because the null must be MASS-MATCHED: B-imp raises ~10x less
    market_fit than B-hi, so comparing B-imp against a B-hi-sized placebo would compare it to an
    inflated spread and could hide a real effect.
    """
    import random
    rng = random.Random(f"{seed}:{ref}:{run['path']}")
    deltas = sorted(
        d for d in (
            (counterfactual(r, delta, ref) - r["stored"]) if ref == "B-imp"
            else (r["c_non"] - r["stored"])
            for r in rows if r["kind"] == "parity_bound"
        ) if d > TOL
    )
    pool = [i for i, r in enumerate(rows)
            if r["kind"] == "unbound_by_parity" and isinstance(r["stored"], (int, float))
            and (not r["parity_class"] or r["parity_class"] == "none")]
    rng.shuffle(pool)
    out = {}
    for d, i in zip(deltas, pool):
        out[i] = round(min(1.0, rows[i]["stored"] + d), 4)
    return out


def rank(run: dict, mf_by_index: dict[int, float] | None) -> list:
    """Production ranking of the run's VISIBLE ideas, optionally with arm-B market_fit patched in.

    Visibility is production's own `visible_ideas` projection, re-applied AFTER the patch so an
    un-demoted idea (mf crossing back over `demotion_market_fit_max`) re-enters the list exactly
    as `_sweep_demote` + the boundary filter would have left it.
    """
    bar = settings.demotion_market_fit_max
    patched = []
    for i, (_src, idea) in enumerate(run["ideas"]):
        c = idea.model_copy(deep=True)
        if mf_by_index is not None and i in mf_by_index:
            new = mf_by_index[i]
            old = c.market_fit_score
            if new is not None:
                # A demoted idea whose new mf clears the bar is no longer a ruled-out finding.
                # Guarded on `old < bar`: an idea demoted by `_sweep_no_buyer_demote` (not by the
                # mf bar) must stay demoted, or B-lo stops being identical to arm A.
                if ((c.candidate_status or "active") == "demoted"
                        and isinstance(old, (int, float)) and old < bar <= new):
                    c.candidate_status = "active"
                c.market_fit_score = new
        patched.append(c)
    vis = visible_ideas(patched)
    if len(vis) < 2:
        return []
    return compute_solution_scores(vis)


# ---------------------------------------------------------------------------------------------
# 4. oracle
# ---------------------------------------------------------------------------------------------
def oracle_labels():
    ordered = _ordered_picks_from_shortlist()
    picks = _picks_from_specs() | set(ordered)
    return picks, set(_NEGATIVES), ordered


def score_arm(runs, rows_by_run, arm, delta, picks, negs):
    """Pairwise AUC + per-pick ranks for one arm, over the ranked visible set of every run."""
    pair_hits = pair_total = 0
    perturbed = 0
    mass = 0.0
    pick_rows, neg_rows, order = [], [], {}
    for run in runs:
        rows = rows_by_run[run["path"]]
        if arm == "A":
            mf = None
        elif arm.startswith("GUARD-placebo"):
            ref = "B-imp" if "imp" in arm else "B-hi"
            mf = placebo_targets(run, rows, seed=int(arm.split("#")[-1]) if "#" in arm else 7,
                                 ref=ref, delta=delta)
        else:
            mf = {i: counterfactual(rows[i], delta, arm) for i in range(len(rows))}
        if mf:
            for i, new in mf.items():
                old = rows[i]["stored"]
                if isinstance(new, (int, float)) and isinstance(old, (int, float)) and new > old + TOL:
                    perturbed += 1
                    mass += new - old
        scores = rank(run, mf)
        if not scores:
            continue
        n = len(scores)
        order[run["path"]] = [(s.solution_name, s.composite_score) for s in scores]
        for r, s in enumerate(scores, 1):
            nm = _norm(s.solution_name)
            hit = next((p for p in picks if p in nm), None)
            neg = next((p for p in negs if p in nm), None)
            if neg:
                neg_rows.append({"run": run["run_id"] or run["dir"], "name": neg,
                                 "rank": r, "n": n, "pct": r / n})
            elif hit:
                pick_rows.append({"run": run["run_id"] or run["dir"], "name": hit,
                                  "rank": r, "n": n, "pct": r / n})
                pair_hits += n - r
                pair_total += n - 1
    return {
        "arm": arm,
        "auc": (pair_hits / pair_total) if pair_total else None,
        "pair_total": pair_total,
        "perturbed": perturbed,
        "mass": round(mass, 2),
        "picks": pick_rows,
        "negatives": neg_rows,
        "order": order,
    }


# ---------------------------------------------------------------------------------------------
# 5. main
# ---------------------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--guards", action="store_true", help="run the blind-metric guards only")
    args = ap.parse_args()

    print("[SETTINGS] parity caps: " + ", ".join(
        f"{k.replace('parity_', '').replace('_market_fit_cap', '').replace('_cap', '')}="
        f"{getattr(settings, k)}" for k in PARITY_SETTINGS))
    print(f"[SETTINGS] payability cap={settings.payability_market_fit_cap} "
          f"low_threshold={settings.payability_low_threshold} "
          f"trust={settings.selfissued_trust_market_fit_cap} "
          f"route_claim={settings.unverified_route_claim_market_fit_cap} "
          f"demotion_bar={settings.demotion_market_fit_max}")

    runs = load_corpus()
    rows_by_run = {}
    all_rows = []
    for run in runs:
        rows = [classify(idea) for _src, idea in run["ideas"]]
        rows_by_run[run["path"]] = rows
        for r in rows:
            r["run"] = run["run_id"] or run["dir"]
            r["run_path"] = run["path"]
        all_rows += rows

    # ---- denominators, stated at every step -------------------------------------------------
    distinct_runs = len({r["run"] for r in all_rows})
    distinct_uuid = len({run["run_id"] for run in runs if run["run_id"]})
    kinds = collections.Counter(r["kind"] for r in all_rows)
    stamped = [r for r in all_rows if r["parity_class"] and r["parity_class"] != "none"]
    print(f"\n[CORPUS] {len(runs)} refinement checkpoints | {len(all_rows)} idea rows | "
          f"{len({r['name'] for r in all_rows})} distinct names | {distinct_runs} distinct run keys "
          f"({distinct_uuid} with a job uuid)")
    any_stamp = [r for r in all_rows if r["parity"]]
    print(f"[CORPUS] parity field present (incl. 'none found'): {len(any_stamp)} rows / "
          f"{len({r['name'] for r in any_stamp})} distinct names")
    print(f"[CORPUS] parity field present: {sum(1 for r in all_rows if r['parity'])}  "
          f"named (cappable) stamps: {len(stamped)} rows / "
          f"{len({r['name'] for r in stamped})} distinct names / "
          f"{len({r['run'] for r in stamped})} runs")
    print(f"[CORPUS] market_fit_score_raw present: "
          f"{sum(1 for r in all_rows if r['raw'] is not None)}/{len(all_rows)} "
          f"({sum(1 for r in all_rows if r['raw'] is not None) / len(all_rows):.1%})")
    for k, v in kinds.most_common():
        print(f"[CLASSIFY] {k:32} {v:5}  ({v / len(all_rows):.1%})")

    mirror_bad = [r for r in all_rows if not r["mirror_ok"]]
    print(f"[CROSSCHECK] parity_eval_harness.parity_cap disagrees with production on "
          f"{len(mirror_bad)}/{len(all_rows)} ideas")
    for r in mirror_bad[:5]:
        print(f"             {r['name']} parity={r['parity'][:40]!r} mirror={r['mirror_cap']} "
              f"c_all={r['c_all']} c_non={r['c_non']}")

    # ---- the imputation, fitted on the ideas where v is observed ----------------------------
    fit = [r["stored"] - r["raw"] for r in all_rows
           if r["kind"] == "unbound_by_parity" and r["raw"] is not None
           and isinstance(r["stored"], (int, float))]
    delta = statistics.median(fit) if fit else 0.0
    print(f"\n[IMPUTE] critic delta (stored - raw) on {len(fit)} ideas where no cap binds: "
          f"median {delta:+.3f}  mean {statistics.fmean(fit):+.3f}  "
          f"IQR [{statistics.quantiles(fit, n=4)[0]:+.2f}, {statistics.quantiles(fit, n=4)[2]:+.2f}]"
          if len(fit) > 3 else f"[IMPUTE] too few fit points ({len(fit)})")

    bound = [r for r in all_rows if r["kind"] == "parity_bound"]
    bound_raw = sum(1 for r in bound if r["raw"] is not None)
    print(f"[BOUND] parity is the binding ceiling on {len(bound)} rows / "
          f"{len({r['name'] for r in bound})} distinct names / {len({r['run'] for r in bound})} runs"
          f" | raw available on {bound_raw}/{len(bound)}")
    print("[BOUND] by class: " + ", ".join(
        f"{k}={v}" for k, v in collections.Counter(r["parity_class"] for r in bound).most_common()))
    print("[BOUND] headroom (c_non - stored): " + ", ".join(
        f"{k}={v}" for k, v in collections.Counter(
            round(r["c_non"] - r["stored"], 2) for r in bound).most_common()))

    # ---- the "bound" detector's own false-positive rate ------------------------------------
    # A parity-free idea whose critic score happens to land exactly on a parity constant would be
    # misread as bound if it HAD carried a stamp. Measure that coincidence rate on the parity-free
    # population: it is the precision limit of the classification above.
    free = [r for r in all_rows
            if (not r["parity_class"] or r["parity_class"] == "none")
            and r["kind"] == "unbound_by_parity" and isinstance(r["stored"], (int, float))]
    coin = {}
    for cls, key in (("shipped", "parity_shipped_market_fit_cap"),
                     ("partial", "parity_partial_market_fit_cap"),
                     ("substitute", "parity_substitute_market_fit_cap"),
                     ("substitute/weak", "parity_substitute_weak_wallet_cap"),
                     ("bundled_free", "parity_bundled_free_cap")):
        k = getattr(settings, key)
        # denominator: parity-free ideas that COULD have shown stored == k (their own non-parity
        # ceiling leaves room). numerator: those whose critic score landed exactly on k anyway.
        elig = [r for r in free if r["c_non"] > k + TOL]
        hits = [r for r in elig if abs(r["stored"] - k) <= TOL]
        coin[cls] = {"cap": k, "hits": len(hits), "of": len(elig),
                     "rate": len(hits) / max(1, len(elig))}
        print(f"[DETECTOR] {cls:16} cap {k:.2f}: parity-FREE ideas landing exactly on it "
              f"{len(hits)}/{len(elig)} ({len(hits) / max(1, len(elig)):.1%}) — the coincidence "
              f"rate that inflates the '{cls}' bound count")
    hist = collections.Counter(round(r["stored"], 2) for r in free)
    print("[DETECTOR] critic market_fit histogram (parity-free, uncapped): " + ", ".join(
        f"{v:.2f}:{c}" for v, c in sorted(hist.items()) if c >= 25))

    # ---- blast radius ----------------------------------------------------------------------
    bar = settings.demotion_market_fit_max
    weak = settings.parity_substitute_weak_wallet_cap
    undemote = [r for r in bound if r["stored"] < bar and r["c_non"] >= bar]
    print(f"\n[BLAST] demotion bar {bar}; substitute weak-wallet cap {weak} sits below it")
    print(f"[BLAST] parity-bound ideas currently BELOW the bar: "
          f"{sum(1 for r in bound if r['stored'] < bar)}  "
          f"of which un-demoted when parity goes advisory (c_non >= bar): {len(undemote)} rows / "
          f"{len({r['name'] for r in undemote})} distinct names / {len({r['run'] for r in undemote})} runs")
    for r in undemote[:12]:
        print(f"         + {r['name'][:38]:38} {r['parity_class']:12} "
              f"stored {r['stored']:.2f} -> ceiling {r['c_non']:.2f}  status={r['status']}  run={r['run']}")

    # ---- what actually demotes ideas (attribution over the demoted population) --------------
    dem = [r for r in all_rows if r["status"] == "demoted"]
    dem_below = [r for r in dem if isinstance(r["stored"], (int, float)) and r["stored"] < bar]
    dem_parity = [r for r in dem_below if r["kind"] == "parity_bound"]
    print(f"[BLAST] demoted rows: {len(dem)} ({len({r['name'] for r in dem})} distinct); below the "
          f"bar: {len(dem_below)}; of those with parity as the binding ceiling: {len(dem_parity)}")
    print("[BLAST] bundled_free cap sits AT 0.40 and the bar is strict (mf < bar), so "
          f"{sum(1 for r in bound if r['parity_class'] == 'bundled_free')} bundled_free-bound "
          "ideas are capped but never demoted by it")

    if args.guards:
        arms = ["A", "GUARD-placebo#7", "GUARD-nocaps"]
    else:
        # 12 placebo seeds = the empirical NULL for "raise this many ideas by these amounts in
        # these runs, chosen without reference to parity". Arm B is only evidence about parity to
        # the extent it falls OUTSIDE this band. Note the design can never make a pick RISE
        # (arm B only ever raises other ideas), so "every pick fell" is not evidence on its own —
        # the placebo band is the sole valid comparator.
        seeds = (7, 11, 23, 31, 37, 41, 53, 59, 61, 67, 71, 73)
        arms = (["A", "B-lo", "B-imp", "B-hi"]
                + [f"GUARD-placebo#{s}" for s in seeds]
                + [f"GUARD-placeboimp#{s}" for s in seeds]
                + ["GUARD-nocaps"])

    picks, negs, ordered = oracle_labels()
    print(f"\n[ORACLE] labelled positives available: {len(picks)}  explicit negatives: {len(negs)}")
    results = {}
    for arm in arms:
        results[arm] = score_arm(runs, rows_by_run, arm, delta, picks, negs)

    base = results["A"]
    print(f"\n  {'arm':14} {'AUC':>7} {'pairs':>7} {'picks':>6} {'meanpct':>8}  "
          f"{'raised':>7} {'mass':>7} {'moved':>6} {'top1chg':>8} {'setchg':>7}")
    summary = {}
    for arm in arms:
        r = results[arm]
        pcts = [p["pct"] for p in r["picks"]]
        moved = top1 = setchg = 0
        for path, ordA in base["order"].items():
            ordB = r["order"].get(path)
            if ordB is None:
                continue
            ra = {n: i for i, (n, _) in enumerate(ordA)}
            rb = {n: i for i, (n, _) in enumerate(ordB)}
            moved += sum(1 for n in ra if n in rb and ra[n] != rb[n])
            if ordA and ordB and ordA[0][0] != ordB[0][0]:
                top1 += 1
            if set(ra) != set(rb):
                setchg += 1
        summary[arm] = {
            "auc": r["auc"], "pair_total": r["pair_total"], "n_picks": len(r["picks"]),
            "mean_pct": (statistics.fmean(pcts) if pcts else None),
            "ideas_moved": moved, "runs_top1_changed": top1, "runs_set_changed": setchg,
        }
        summary[arm]["ideas_raised"] = r["perturbed"]
        summary[arm]["perturbation_mass"] = r["mass"]
        auc_s = "-" if r["auc"] is None else f"{r['auc']:.3f}"
        pct_s = "-" if not pcts else f"{statistics.fmean(pcts):.3f}"
        print(f"  {arm:14} {auc_s:>7} {r['pair_total']:>7} {len(r['picks']):>6} "
              f"{pct_s:>8}  {r['perturbed']:>7} {r['mass']:>7.1f} {moved:>6} {top1:>8} {setchg:>7}")

    # ---- arm B vs the empirical null ---------------------------------------------------------
    nulls = {}
    for arm, prefix in (("B-hi", "GUARD-placebo#"), ("B-imp", "GUARD-placeboimp#")):
        null = [summary[a]["auc"] for a in arms if a.startswith(prefix)]
        if len(null) < 3 or summary.get(arm, {}).get("auc") is None:
            continue
        m, sd = statistics.fmean(null), statistics.stdev(null)
        nm = statistics.fmean([summary[a]["perturbation_mass"] for a in arms
                               if a.startswith(prefix)])
        a = summary[arm]["auc"]
        worse = sum(1 for x in null if x <= a)
        print(f"\n[NULL] {arm} (mass {summary[arm]['perturbation_mass']:.1f}) vs mass-matched "
              f"placebo (mass {nm:.1f}) over {len(null)} seeds: null mean {m:.3f} sd {sd:.3f} "
              f"range [{min(null):.3f}, {max(null):.3f}]  (arm A = {summary['A']['auc']:.3f})")
        print(f"[NULL] {arm}: AUC {a:.3f} = {(a - m) / sd:+.2f} sd; {worse}/{len(null)} placebo "
              f"seeds this low or lower -> {'OUTSIDE' if worse == 0 else 'INSIDE'} the null band")
        nulls[arm] = {"seeds": len(null), "mean": m, "sd": sd, "min": min(null), "max": max(null),
                      "placebo_mass": nm, "arm_auc": a, "seeds_at_or_below": worse}
    summary["_null"] = nulls

    # per-pick rank movement
    print(f"\n  {'idea':32} {'run':10} {'A':>8} {'B-imp':>8} {'B-hi':>8}")
    keyed = {}
    for arm in arms:
        for p in results[arm]["picks"] + results[arm]["negatives"]:
            keyed.setdefault((p["name"], p["run"]), {})[arm] = f"#{p['rank']}/{p['n']}"
    for (nm, run), v in sorted(keyed.items()):
        tag = "KILLED " if nm in negs else ""
        print(f"  {tag + nm:32} {str(run)[:10]:10} {v.get('A', '-'):>8} "
              f"{v.get('B-imp', '-'):>8} {v.get('B-hi', '-'):>8}")

    # ---- how circular is the oracle? ---------------------------------------------------------
    # The analyst read the stored idea fields, `incumbent_parity` among them. If the picks are
    # systematically the parity-FREE ideas, then "removing the parity clamp lowers pick ranks" is
    # close to restating the analyst's own use of the stamp, not independent evidence for it.
    pick_paths = set()
    pick_kinds = collections.Counter()
    pick_detail = []
    for run in runs:
        for r in rows_by_run[run["path"]]:
            if any(p in _norm(r["name"] or "") for p in picks):
                pick_paths.add(run["path"])
                pick_kinds[r["kind"]] += 1
                pick_detail.append({"name": r["name"], "run": r["run"], "kind": r["kind"],
                                    "parity": r["parity_class"], "stored": r["stored"]})
    pop = [r for run in runs if run["path"] in pick_paths for r in rows_by_run[run["path"]]]
    pop_kinds = collections.Counter(r["kind"] for r in pop)
    print("\n[CIRCULARITY] analyst picks by cap status: " + ", ".join(
        f"{k}={v}" for k, v in pick_kinds.most_common()))
    print("[CIRCULARITY] same-run population for comparison: " + ", ".join(
        f"{k}={v} ({v / len(pop):.0%})" for k, v in pop_kinds.most_common()))
    pb_pick = pick_kinds.get("parity_bound", 0) / max(1, sum(pick_kinds.values()))
    pb_pop = pop_kinds.get("parity_bound", 0) / max(1, len(pop))
    print(f"[CIRCULARITY] parity-bound share: picks {pb_pick:.1%} vs same-run population "
          f"{pb_pop:.1%} — the enrichment the oracle cannot separate from its own inputs")

    # ---- WHAT overtakes the analyst's picks: the direction that would kill the idea ---------
    print("\n[OVERTAKE] ideas that pass an analyst pick when parity goes advisory (B-hi)")
    overtakers = []
    by_name = {}
    for run in runs:
        for r in rows_by_run[run["path"]]:
            by_name[(run["path"], r["name"])] = r
    posA = {p: {n: i for i, (n, _) in enumerate(o)} for p, o in base["order"].items()}
    posB = {p: {n: i for i, (n, _) in enumerate(o)} for p, o in results["B-hi"]["order"].items()}
    for path, ordA in base["order"].items():
        pa, pb = posA[path], posB.get(path)
        if pb is None:
            continue
        for nm, _ in ordA:
            hit = next((p for p in picks if p in _norm(nm)), None)
            if hit is None:
                continue
            for other, _ in ordA:
                if other == nm or other not in pb or other not in pa:
                    continue
                if pa[other] > pa[nm] and pb[other] < pb[nm]:
                    r = by_name.get((path, other), {})
                    overtakers.append({
                        "pick": hit, "over": other, "run": r.get("run"),
                        "parity": r.get("parity_class"), "kind": r.get("kind"),
                        "stored": r.get("stored"), "new": r.get("c_non"),
                    })
    par_share = collections.Counter(o["kind"] for o in overtakers)
    print(f"[OVERTAKE] {len(overtakers)} (pick, overtaker) pairs; overtaker kinds: "
          + ", ".join(f"{k}={v}" for k, v in par_share.most_common()))
    print("[OVERTAKE] overtaker parity classes: " + ", ".join(
        f"{k}={v}" for k, v in collections.Counter(o["parity"] for o in overtakers).most_common()))
    for o in overtakers[:15]:
        print(f"           {o['pick'][:26]:26} <- {o['over'][:30]:30} "
              f"{str(o['parity']):12} {o['stored']} -> {o['new']}  run={o['run']}")

    OUT.write_text(json.dumps({
        "corpus": {
            "checkpoints": len(runs), "idea_rows": len(all_rows),
            "distinct_names": len({r["name"] for r in all_rows}),
            "distinct_run_keys": distinct_runs, "distinct_uuid_runs": distinct_uuid,
            "kinds": dict(kinds),
            "named_stamps_rows": len(stamped),
            "named_stamps_distinct": len({r["name"] for r in stamped}),
            "raw_present": sum(1 for r in all_rows if r["raw"] is not None),
        },
        "impute_delta_median": delta, "impute_fit_n": len(fit),
        "mirror_disagreements": len(mirror_bad),
        "detector_coincidence": coin,
        "overtakers": overtakers,
        "bound_rows": bound,
        "undemoted": undemote,
        "summary": summary,
        "picks": {a: results[a]["picks"] for a in arms},
        "negatives": {a: results[a]["negatives"] for a in arms},
    }, indent=1, default=str))
    print(f"\n  wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
