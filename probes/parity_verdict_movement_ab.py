"""parity_verdict_movement_ab — does peer evidence / group framing MOVE the parity verdict?

WHY THIS EXISTS
---------------
A design proposes to fix `incumbent_parity` inconsistency by clustering ideas semantically and
then SHARING search evidence across a cluster, so the parity judge sees peers' findings. Every
metric that design offers (cluster stability, absorption, reach) is a GROUP-FORMATION metric.
The money-bearing artifact is the judge's verdict. This probe measures the verdict.

THE ARMS ARE FROZEN BEFORE MEASUREMENT (this docstring was written and committed to disk before
the first LLM call; no arm was tuned against the flagship pair).

Population — `source_pain` keying (the honest key; `pain_points_addressed` is the idea's
self-authored list and inflates the pair count ~8x):
  * SUBJECT = an idea stamped `incumbent_parity == "none found"`.
  * PEER    = an idea in the SAME `source_pain` group stamped with a named incumbent
              (`shipped by X: ev` / `partial by X: ev` / `substitute (X): ev`).

Arms (all at temperature 0, reps >= 3, replaying the REAL parity-judge prompt template lifted
verbatim from `UnifiedSolutionCrew._probe_mechanism_parity`):

  A  CO-JUDGE RECONSTRUCTION — the production condition. Both SUBJECT and PEER are listed under
     "IDEAS under evaluation"; the evidence block carries the peer's finding attributed to the
     peer (`[for idea: <peer>]`). This is what production actually did: the full post-union pool
     is judged in ONE call, so the peer's snippet was already in the subject's prompt.
  B  PEER EVIDENCE (the design's mechanism) — only the SUBJECT is listed; the peer's finding is
     re-attributed to the SUBJECT (`[for idea: <subject>]`), i.e. shared as if it were the
     subject's own search result.
  C  GROUP FRAMING — B plus an explicit sentence stating a buyer would see the subject and the
     peer as variants of one product, so evidence about one bears on the other.
  D  DECOY CONTROL (mandatory) — B, but the finding comes from an UNRELATED run's incumbent
     (different checkpoint, vendor absent from the subject's run, low lexical overlap with the
     subject's value proposition). If D flips at a rate near B, the judge is reacting to the mere
     presence of a named vendor, and B's flips carry no information.
  E  SAME-NICHE NON-PEER CONTROL — ADDED AFTER SEEING B/D (declared, not retro-fitted into the
     frozen set; A-D were untouched and are NOT re-measured). B, but the finding comes from a
     named-stamped idea in the SAME run whose `source_pain` DIFFERS from the subject's and whose
     value proposition has low lexical overlap with it — i.e. a same-niche vendor for a DIFFERENT
     mechanism. D only excludes "the judge reacts to any named vendor". E excludes the failure D
     cannot see: "the judge reacts to any TOPICALLY PLAUSIBLE named vendor". If E flips at a rate
     near B, then B's flips are not evidence of mechanism parity and the grouping step buys
     nothing that "name any same-niche incumbent" would not.
     Pre-stated threshold T5: flip_rate(B) - flip_rate(E) >= 20 pp, else DISQUALIFIED.

FLIP = the replayed verdict for the SUBJECT is anything other than "none found", using
production's own note-rendering logic.

DISQUALIFYING THRESHOLD (stated before running; the mechanism is NOT built unless ALL hold):
  T1 unanimity : >= 90% of B's flipped subjects flip in ALL reps (3/3). A 3/7-style split
                 disqualifies regardless of the mean.
  T2 decoy gap : flip_rate(B) - flip_rate(D) >= 20 percentage points.
  T3 precision : >= 70% of hand-labelled B flips are correct (peer's incumbent genuinely ships
                 the SUBJECT's core mechanism, not merely the peer's).
  T4 allow-case: >= 80% of hand-labelled correctly-none subjects still stamp none under B.

WHAT COULD NOT BE RECOVERED (stated rather than substituted):
  * Per-run search snippets are function-local in `_probe_mechanism_parity` and are NOT
    persisted. The SUBJECT's own original snippets are therefore unavailable in every arm. They
    are absent identically across A/B/C/D, so they cannot confound the A-vs-B contrast, but they
    do mean no arm reproduces production's full evidence context byte-for-byte.
  * The peer's evidence is recovered from the PEER'S STAMP (`covered_by` + `evidence`, <=20
    words by schema), re-rendered in a search-result shape. Identical shape in all arms.
  * "Known incumbents" is recovered faithfully from each run's `metadata.json`
    `niche_incumbent_map` (this IS `_incumbent_rows`), with the arm's evidence vendor appended
    if absent, symmetrically for B and D.

Usage:
  python probes/parity_verdict_movement_ab.py --derive          # population + frozen subjects
  python probes/parity_verdict_movement_ab.py --smoke            # 4 calls, one subject
  python probes/parity_verdict_movement_ab.py --run --reps 3
  python probes/parity_verdict_movement_ab.py --summarize
  python probes/parity_verdict_movement_ab.py --label-sheet      # hand-labelling worksheet
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pydantic import BaseModel, Field as _F  # noqa: E402

PROBE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PROBE_DIR)
CKPT = os.path.join(REPO, "output", "checkpoints")
SUBJECTS_JSON = os.path.join(PROBE_DIR, "parity_verdict_movement_ab_subjects.json")
RESULTS_JSON = os.path.join(PROBE_DIR, "parity_verdict_movement_ab_results.json")
LABELS_JSON = os.path.join(PROBE_DIR, "parity_verdict_movement_ab_labels.json")

ARMS = ("A", "B", "C", "D", "E")


# ---------------------------------------------------------------- schema (production's)
class _ParityFinding(BaseModel):
    idea_name: str = ""
    covered_by: str = _F("", description="incumbent product name, '' if none")
    evidence: str = _F("", description="what the incumbent ships, <=20 words")
    parity: str = _F("none", description="shipped | partial | substitute | none")


class _ParityFindings(BaseModel):
    findings: list[_ParityFinding] = _F(default_factory=list)


def render_note(f: _ParityFinding) -> str:
    """Production's exact note-rendering (unified_solution_crew.py ~:3273-3280)."""
    if f.parity in ("shipped", "partial") and f.covered_by:
        return f"{f.parity} by {f.covered_by}: {f.evidence or 'n/a'}"
    if f.parity == "substitute":
        return f"substitute ({f.covered_by or 'DIY'}): {f.evidence or 'free/DIY route exists'}"
    return "none found"


# ---------------------------------------------------------------- population derivation
def norm(s) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def parse_stamp(p):
    """-> (kind, covered_by, evidence) with kind in none|shipped|partial|substitute|other."""
    if not p:
        return None
    s = str(p).strip()
    if norm(s) == "none found":
        return ("none", "", "")
    m = re.match(r"^(shipped|partial)\s+by\s+(.+?):\s*(.*)$", s, re.I | re.S)
    if m:
        return (m.group(1).lower(), m.group(2).strip(), m.group(3).strip())
    m = re.match(r"^substitute\s*\((.*?)\):\s*(.*)$", s, re.I | re.S)
    if m:
        return ("substitute", m.group(1).strip(), m.group(2).strip())
    return ("other", "", s)


def _run_meta(run_dir: str) -> dict:
    try:
        with open(os.path.join(CKPT, run_dir, "metadata.json")) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _toks(s: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", (s or "").lower())}


def derive(verbose=True):
    files = sorted(glob.glob(os.path.join(CKPT, "*", "stage_5_3_refinement.json")))
    denom_all = denom_stamped2 = contra = 0
    n_pairs_brief = 0          # brief's keying: any non-"none found" counts as named
    subjects = []              # eligible: peer stamp parses to a named incumbent + evidence
    other_forms = Counter()
    runs_contra = set()
    all_named = []             # decoy pool

    for f in files:
        try:
            with open(f) as fh:
                d = json.load(fh)
        except Exception:
            continue
        run = os.path.basename(os.path.dirname(f))
        ideas = d.get("solution_ideas") or []
        for i in ideas:
            ps = parse_stamp(i.get("incumbent_parity"))
            if ps and ps[0] in ("shipped", "partial", "substitute") and ps[1] and ps[2]:
                all_named.append(dict(run=run, kind=ps[0], covered_by=ps[1], evidence=ps[2],
                                      vp=(i.get("value_proposition") or ""),
                                      pain=norm(i.get("source_pain")),
                                      name=(i.get("solution_name") or "")))
        buckets = defaultdict(list)
        for i in ideas:
            k = norm(i.get("source_pain"))
            if k:
                buckets[k].append(i)
        for pain, grp in buckets.items():
            if len(grp) < 2:
                continue
            denom_all += 1
            parsed = [(i, parse_stamp(i.get("incumbent_parity"))) for i in grp]
            stamped = [(i, p) for i, p in parsed if p]
            if len(stamped) < 2:
                continue
            denom_stamped2 += 1
            nones = [i for i, p in stamped if p[0] == "none"]
            named_any = [(i, p) for i, p in stamped if p[0] != "none"]
            for _i, p in stamped:
                if p[0] == "other":
                    other_forms[p[2][:60]] += 1
            if not (nones and named_any):
                continue
            contra += 1
            runs_contra.add(run)
            n_pairs_brief += len(nones) * len(named_any)
            named_ok = [(i, p) for i, p in named_any
                        if p[0] in ("shipped", "partial", "substitute") and p[1] and p[2]]
            for s in nones:
                for pi, pp in named_ok:
                    subjects.append(dict(
                        # Stable + unique. NOT `hash()` (PYTHONHASHSEED-randomized) and NOT a
                        # truncated run name: the first cut of this probe used both and 111
                        # subjects collapsed into 39 colliding ids, silently mixing records
                        # from different subjects into one "per-subject" unanimity bucket.
                        pair_id=hashlib.sha1(
                            f"{run}|{pain}|{s.get('solution_name')}|{pi.get('solution_name')}"
                            .encode()).hexdigest()[:16],
                        run=run,
                        niche=_run_meta(run).get("niche_description", ""),
                        source_pain=pain,
                        subject_name=s.get("solution_name") or "?",
                        subject_vp=(s.get("value_proposition") or ""),
                        subject_tech=(s.get("technical_approach") or ""),
                        subject_stamp=s.get("incumbent_parity"),
                        peer_name=pi.get("solution_name") or "?",
                        peer_vp=(pi.get("value_proposition") or ""),
                        peer_stamp=pi.get("incumbent_parity"),
                        peer_kind=pp[0], peer_covered_by=pp[1], peer_evidence=pp[2],
                    ))

    # deterministic decoy assignment
    rng = random.Random(20260817)
    rng_np = random.Random(77002026)   # separate stream: arm E must not shift arm D picks
    all_named.sort(key=lambda r: (r["run"], r["covered_by"], r["evidence"]))
    for s in subjects:
        run_vendors = {norm(x["covered_by"]) for x in all_named if x["run"] == s["run"]}
        subj_t = _toks(s["subject_vp"] + " " + s["subject_tech"])
        cands = [x for x in all_named
                 if x["run"] != s["run"]
                 and norm(x["covered_by"]) not in run_vendors
                 and norm(x["covered_by"]) not in norm(s["niche"])
                 and len(_toks(x["evidence"]) & subj_t) <= 1]
        if not cands:
            cands = [x for x in all_named if x["run"] != s["run"]]
        pick = cands[rng.randrange(len(cands))]
        s["decoy_kind"] = pick["kind"]
        s["decoy_covered_by"] = pick["covered_by"]
        s["decoy_evidence"] = pick["evidence"]
        s["decoy_run"] = pick["run"]

        # arm E: same run, DIFFERENT source_pain, low lexical overlap with the subject.
        np_c = [x for x in all_named
                if x["run"] == s["run"] and x["pain"] and x["pain"] != s["source_pain"]
                and norm(x["covered_by"]) != norm(s["peer_covered_by"])
                and len(_toks(x["vp"]) & subj_t) <= 3]
        if not np_c:
            np_c = [x for x in all_named
                    if x["run"] == s["run"] and x["pain"] != s["source_pain"]
                    and norm(x["covered_by"]) != norm(s["peer_covered_by"])]
        if np_c:
            q = np_c[rng_np.randrange(len(np_c))]
            s["nonpeer_kind"] = q["kind"]; s["nonpeer_covered_by"] = q["covered_by"]
            s["nonpeer_evidence"] = q["evidence"]; s["nonpeer_idea"] = q["name"]
            s["nonpeer_pain"] = q["pain"]
        else:
            s["nonpeer_kind"] = ""; s["nonpeer_covered_by"] = ""
            s["nonpeer_evidence"] = ""; s["nonpeer_idea"] = ""; s["nonpeer_pain"] = ""

    out = dict(
        derived_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        refinement_files=len(files),
        denom_multi_idea_pains_all=denom_all,
        denom_multi_idea_pains_ge2_stamped=denom_stamped2,
        contradictory_pains=contra,
        contradictory_rate_on_stamped_denom=round(100 * contra / max(1, denom_stamped2), 1),
        pairs_brief_keying=n_pairs_brief,
        pairs_eligible=len(subjects),
        runs_with_contradiction=len(runs_contra),
        unparsed_named_stamp_forms=dict(other_forms),
        decoy_pool_size=len(all_named),
        subjects=subjects,
    )
    with open(SUBJECTS_JSON, "w") as fh:
        json.dump(out, fh, indent=1)
    if verbose:
        print(f"refinement files                  : {len(files)}")
        print(f"multi-idea source_pains (all)     : {denom_all}")
        print(f"multi-idea source_pains (>=2 stamped, the honest denominator): {denom_stamped2}")
        print(f"contradictory pains               : {contra} "
              f"({100*contra/max(1,denom_stamped2):.1f}% of stamped denominator)")
        print(f"pairs (brief keying)              : {n_pairs_brief}")
        print(f"pairs ELIGIBLE (peer stamp parses to named vendor + evidence): {len(subjects)}"
              f"  = {100*len(subjects)/max(1,n_pairs_brief):.1f}% of pairs")
        print(f"runs with >=1 contradiction       : {len(runs_contra)}")
        print(f"unparsed named stamp forms        : {dict(other_forms)}")
        print(f"decoy pool                        : {len(all_named)} named findings")
        print(f"-> wrote {SUBJECTS_JSON}")
    return out


# ---------------------------------------------------------------- prompt construction
INSTR = ("For EACH idea, judge from the search results ONLY whether an incumbent "
         "already SHIPS the idea's core mechanism: parity=shipped (a COMMERCIAL "
         "product or first-party feature ships it), partial (adjacent/limited "
         "commercial version), substitute (NO commercial product, but a free/DIY "
         "route already delivers the core outcome today — a free official data "
         "source, a spreadsheet template, a manual workflow; name it in covered_by), "
         "none (no evidence of either). Cite only what the "
         "results actually show — never invent features. Return JSON.")

FRAMING = ("NOTE: a buyer would see the two ideas above as variants of ONE product — they address "
           "the same underlying pain with the same core mechanism. Evidence that an incumbent "
           "covers one of them therefore bears directly on the other.")


def _evidence_block(idea_label: str, covered_by: str, evidence: str) -> str:
    return (f"[for idea: {idea_label}]\n"
            f"1. {covered_by}\n"
            f"   {evidence}")


def build_prompt(s: dict, arm: str) -> str:
    meta_names = [r.get("name") for r in (_run_meta(s["run"]).get("niche_incumbent_map") or [])
                  if r.get("name")]
    if arm == "D":
        vendor, ev, label = s["decoy_covered_by"], s["decoy_evidence"], s["subject_name"]
    elif arm == "E":
        vendor, ev, label = s["nonpeer_covered_by"], s["nonpeer_evidence"], s["subject_name"]
    else:
        vendor, ev = s["peer_covered_by"], s["peer_evidence"]
        label = s["peer_name"] if arm == "A" else s["subject_name"]
    if vendor not in meta_names:
        meta_names = meta_names + [vendor]

    if arm == "A":
        ideas = [(s["subject_name"], s["subject_vp"]), (s["peer_name"], s["peer_vp"])]
    else:
        ideas = [(s["subject_name"], s["subject_vp"])]
    idea_lines = "\n".join(f"- {n}: {(vp or '')[:160]}" for n, vp in ideas)
    if arm == "C":
        idea_lines = (f"- {s['subject_name']}: {(s['subject_vp'] or '')[:160]}\n"
                      f"- (peer variant, not under evaluation) {s['peer_name']}: "
                      f"{(s['peer_vp'] or '')[:160]}\n\n{FRAMING}")

    snippets = [_evidence_block(label, vendor, ev)]
    return (f"Niche: {s['niche']}\n\nIDEAS under evaluation:\n{idea_lines}\n\n"
            f"Known incumbents: {', '.join(meta_names) or 'none'}\n\n"
            f"Web search results:\n{chr(10).join(snippets)}\n\n" + INSTR)


# ---------------------------------------------------------------- runner
_lock = threading.Lock()
_usage = {"calls": 0, "prompt": 0, "completion": 0, "errors": 0}


def one_call(s: dict, arm: str, rep: int) -> dict:
    from nicheiq.utils.llm_service import LLMService
    from nicheiq.config.settings import settings
    prompt = build_prompt(s, arm)
    rec = dict(pair_id=s["pair_id"], run=s["run"], subject_name=s["subject_name"],
               peer_name=s["peer_name"], arm=arm, rep=rep, note=None, error=None,
               raw=None, cost=0.0, prompt_chars=len(prompt))
    try:
        r, usage = LLMService.invoke_structured(
            prompt=prompt, output_model=_ParityFindings, temperature=0, timeout=120,
            model_name=settings.report_structured_llm, reasoning_effort="none")
        by = {(f.idea_name or "").strip().lower(): f for f in (r.findings or [])}
        f = by.get(s["subject_name"].strip().lower())
        if f is None and len(r.findings or []) == 1:
            f = r.findings[0]          # single-idea arms: accept the lone finding
        rec["note"] = render_note(f) if f is not None else "none found"
        rec["matched"] = f is not None
        rec["raw"] = [x.model_dump() for x in (r.findings or [])]
        with _lock:
            _usage["calls"] += 1
            if usage is not None:
                d = usage.to_dict() if hasattr(usage, "to_dict") else {}
                _usage["prompt"] += d.get("prompt_tokens", 0) or 0
                _usage["completion"] += d.get("completion_tokens", 0) or 0
                c = d.get("cost") or d.get("total_cost") or 0.0
                rec["cost"] = float(c or 0.0)
                _usage["cost"] = _usage.get("cost", 0.0) + float(c or 0.0)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        with _lock:
            _usage["errors"] += 1
    return rec


def run(reps: int, limit: int | None, workers: int, arms=ARMS, append=False):
    with open(SUBJECTS_JSON) as fh:
        data = json.load(fh)
    subs = data["subjects"][:limit] if limit else data["subjects"]
    jobs = [(s, a, r) for s in subs for a in arms for r in range(reps)]
    print(f"subjects={len(subs)} arms={list(arms)} reps={reps} -> {len(jobs)} calls")
    out = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one_call, s, a, r) for s, a, r in jobs]
        for n, fu in enumerate(as_completed(futs), 1):
            out.append(fu.result())
            if n % 50 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s  errors={_usage['errors']}",
                      flush=True)
    prev = {}
    if append and os.path.exists(RESULTS_JSON):
        with open(RESULTS_JSON) as fh:
            prev = json.load(fh)
        out = [r for r in prev.get("records", []) if r["arm"] not in arms] + out
        u = dict(prev.get("usage", {}))
        for k, v in _usage.items():
            u[k] = (u.get(k, 0) or 0) + v
        merged_arms = [a for a in ARMS
                       if a in set(prev.get("arms", [])) | set(arms)]
        with open(RESULTS_JSON, "w") as fh:
            json.dump(dict(reps=reps, arms=merged_arms, n_subjects=max(
                len(subs), prev.get("n_subjects", 0)), usage=u,
                elapsed_s=round(prev.get("elapsed_s", 0) + time.time() - t0, 1),
                records=out), fh, indent=1)
        print(f"-> appended; arms now {merged_arms}; usage={u}")
        return
    with open(RESULTS_JSON, "w") as fh:
        json.dump(dict(reps=reps, arms=list(arms), n_subjects=len(subs),
                       usage=_usage, elapsed_s=round(time.time() - t0, 1),
                       records=out), fh, indent=1)
    print(f"-> wrote {RESULTS_JSON}  usage={_usage}  {time.time()-t0:.0f}s")


# ---------------------------------------------------------------- summary
def summarize():
    with open(SUBJECTS_JSON) as fh:
        subs = {s["pair_id"]: s for s in json.load(fh)["subjects"]}
    with open(RESULTS_JSON) as fh:
        res = json.load(fh)
    reps = res["reps"]
    by = defaultdict(dict)        # pair -> arm -> [notes]
    for r in res["records"]:
        by[r["pair_id"]].setdefault(r["arm"], []).append(r)

    print(f"=== reps={reps}  subjects={res['n_subjects']}  calls={res['usage']['calls']}"
          f"  errors={res['usage']['errors']}  elapsed={res['elapsed_s']}s")
    print(f"    tokens prompt={res['usage']['prompt']} completion={res['usage']['completion']}")
    print()
    print(f"{'arm':<4}{'n':>5}{'flips':>7}{'flip%':>8}{'unan-flip':>11}{'unan-none':>11}{'split':>7}")
    per_arm = {}
    for arm in res["arms"]:
        n = flips = unan_f = unan_n = split = 0
        flipped_pairs, split_pairs = [], []
        for pid, d in by.items():
            recs = [x for x in d.get(arm, []) if x["error"] is None]
            if len(recs) < reps:
                continue
            n += 1
            fl = [x["note"] != "none found" for x in recs]
            if all(fl):
                unan_f += 1
                flips += 1
                flipped_pairs.append(pid)
            elif not any(fl):
                unan_n += 1
            else:
                split += 1
                split_pairs.append(pid)
                flips += 1   # counted as a flip for the aggregate rate (any-rep flip)
        per_arm[arm] = dict(n=n, flips=flips, unan_flip=unan_f, unan_none=unan_n, split=split,
                            flipped_pairs=flipped_pairs, split_pairs=split_pairs)
        print(f"{arm:<4}{n:>5}{flips:>7}{100*flips/max(1,n):>7.1f}%{unan_f:>11}{unan_n:>11}"
              f"{split:>7}")
    print("\nflip% = any-rep flip / n.  unan-flip = flipped in ALL reps.  "
          "split = flipped in some reps only (non-repeatable).")

    # decoy gap + unanimity gate
    fb = 100 * per_arm["B"]["flips"] / max(1, per_arm["B"]["n"])
    fd = 100 * per_arm["D"]["flips"] / max(1, per_arm["D"]["n"])
    fa = 100 * per_arm["A"]["flips"] / max(1, per_arm["A"]["n"])
    fc = 100 * per_arm["C"]["flips"] / max(1, per_arm["C"]["n"])
    fe = (100 * per_arm["E"]["flips"] / max(1, per_arm["E"]["n"])) if "E" in per_arm else None
    unan_share = (per_arm["B"]["unan_flip"] / max(1, per_arm["B"]["flips"]))
    print(f"\nT1 unanimity  : {100*unan_share:.1f}% of B flips are unanimous "
          f"(threshold >=90%)  -> {'PASS' if unan_share>=0.90 else 'FAIL'}")
    print(f"T2 decoy gap  : B {fb:.1f}% - D {fd:.1f}% = {fb-fd:.1f} pp "
          f"(threshold >=20pp) -> {'PASS' if fb-fd>=20 else 'FAIL'}")
    print(f"   A (co-judge / production condition) = {fa:.1f}%   C (group framing) = {fc:.1f}%")
    if fe is not None:
        print(f"T5 same-niche non-peer gap : B {fb:.1f}% - E {fe:.1f}% = {fb-fe:.1f} pp "
              f"(threshold >=20pp) -> {'PASS' if fb-fe>=20 else 'FAIL'}")

    # per-arm verdict-kind distribution
    print("\nverdict kinds (rep-0 only):")
    for arm in res["arms"]:
        c = Counter(parse_stamp(x["note"])[0]
                    for d in by.values() for x in d.get(arm, [])
                    if x["error"] is None and x["rep"] == 0)
        print(f"  {arm}: {dict(c)}")

    # flagship
    print("\nflagship (run 8500b97d):")
    for pid, d in by.items():
        s = subs.get(pid)
        if not s or "8500b97d" not in s["run"]:
            continue
        print(f"  subject={s['subject_name']!r}  peer={s['peer_name']!r} "
              f"({s['peer_kind']} by {s['peer_covered_by']})")
        for arm in res["arms"]:
            notes = [x["note"] or x["error"] for x in sorted(d.get(arm, []),
                                                             key=lambda y: y["rep"])]
            kinds = {parse_stamp(x["note"])[0] if x["note"] else "err"
                     for x in d.get(arm, [])}
            uu = "UNANIMOUS" if len(kinds) == 1 else "SPLIT"
            print(f"    {arm} [{uu}] " + " | ".join((x or "?")[:64] for x in notes))

    # labels: precision / allow-case are scored PER DISTINCT CASE, not per pair (the pair
    # population is 66.7% duplicates of two cases). See `--score`.
    print("\nT3 (precision) and T4 (allow-case) are scored per DISTINCT CASE by `--score`, "
          "not here:\n  python probes/parity_verdict_movement_ab.py --score")


def label_sheet(n: int):
    """Emit a hand-labelling worksheet: subjects that flipped in ANY arm, plus held-none ones."""
    with open(SUBJECTS_JSON) as fh:
        subs = {s["pair_id"]: s for s in json.load(fh)["subjects"]}
    with open(RESULTS_JSON) as fh:
        res = json.load(fh)
    by = defaultdict(lambda: defaultdict(list))
    for r in res["records"]:
        by[r["pair_id"]][r["arm"]].append(r)
    rows = []
    for pid, s in subs.items():
        arms_flipped = [a for a in res["arms"]
                        if any(x["note"] not in (None, "none found") for x in by[pid].get(a, []))]
        rows.append((pid, s, arms_flipped))
    rng = random.Random(4242)
    flipped = [r for r in rows if "B" in r[2]]
    held = [r for r in rows if "B" not in r[2]]
    rng.shuffle(flipped)
    rng.shuffle(held)
    take = flipped[: max(n // 2, min(len(flipped), n))] + held[: n // 2]
    out = {"instructions": "label = should_flip | should_stay_none", "labels": {}}
    for pid, s, af in take:
        out["labels"][pid] = dict(
            label="TODO", arms_flipped=af, niche=s["niche"], source_pain=s["source_pain"],
            subject=s["subject_name"], subject_vp=s["subject_vp"],
            subject_tech=s["subject_tech"][:400],
            peer=s["peer_name"], peer_vp=s["peer_vp"], peer_stamp=s["peer_stamp"],
            b_notes=[x["note"] for x in sorted(by[pid].get("B", []), key=lambda y: y["rep"])],
        )
    path = LABELS_JSON.replace(".json", "_sheet.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"-> wrote {path} with {len(out['labels'])} rows to label")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--label-sheet", type=int, default=0)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--show-prompts", action="store_true")
    ap.add_argument("--arms", type=str, default=None, help="comma list, e.g. E")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.derive:
        derive()
    if a.show_prompts:
        with open(SUBJECTS_JSON) as fh:
            s = json.load(fh)["subjects"][0]
        for arm in ARMS:
            print(f"\n{'='*30} ARM {arm} {'='*30}\n{build_prompt(s, arm)}")
    if a.smoke:
        with open(SUBJECTS_JSON) as fh:
            s = json.load(fh)["subjects"][0]
        for arm in ARMS:
            r = one_call(s, arm, 0)
            print(arm, "->", r["note"], r["error"] or "")
        print("usage:", _usage)
    if a.run:
        sel = tuple(a.arms.split(",")) if a.arms else ARMS
        run(a.reps, a.limit, a.workers, arms=sel, append=a.append)
    if a.label_sheet:
        label_sheet(a.label_sheet)
    if a.score:
        score()
    if a.summarize:
        summarize()
