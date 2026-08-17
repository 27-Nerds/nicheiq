#!/usr/bin/env python3
"""The offline acceptance gate for the parity-LEDGER proposal, replayed over the corpus.

    source .venv/bin/activate && python -m probes.parity_ledger_ab --run          # spends money
    source .venv/bin/activate && python -m probes.parity_ledger_ab --report       # free, cached
    source .venv/bin/activate && python -m probes.parity_ledger_ab --label-sheet  # free, cached

Redirect to a file; never pipe (the shell wrapper rewrites piped output).

THE DEFECT. `incumbent_parity` gates real money: `_parity_cap`
(crews/unified_solution_crew.py:2473-2485) clamps market_fit to 0.55/0.45/0.50/0.40 for
partial/shipped/substitute/bundled_free, and the ruled-out reason text is stamped from the same
string. `_probe_mechanism_parity` (:3121) queries search with EACH IDEA'S OWN vocabulary, so two
ideas covering the same ground get opposite verdicts. Live case in run 8500b97d: 'Reinstatement
to Entity Continuity Dossier' was ruled out ("partial by Whitespark ... evidence gathering and
appeal steps") while 'Reclaim Packet QA' — same pain, same substance, no "reinstat" token in its
value prop — shipped as the #1 recommendation with "none found".

THE PROPOSAL UNDER TEST. Per run, build a LEDGER of every named finding already on disk
({incumbent, class, evidence} parsed from stamps starting partial|shipped|bundled_free), then
RE-ADJUDICATE each "none found" idea against it: does any ledger row already ship this idea's
core mechanism? Name the row, or keep none.

WHY THIS IS ALMOST FREE. The ledger is the run's own output; no search calls are needed. The
only cost is judge calls, reported below in calls and dollars.

DESIGN CONSTRAINTS (each one is a grave marker from a prior attempt):
  * Downgrade-only — candidates are exactly the "none found" ideas, the permissive end of the
    ladder, so no already-named stamp can be loosened. Asserted, not assumed (`_RANK`).
  * A flip must NAME a ledger row. The returned incumbent is matched back against the ledger and
    dropped when it does not resolve — the judge cannot invent an incumbent.
  * `substitute` rows are EXCLUDED from the ledger in v1. DIY substitutes ("Google Sheets",
    "DIY") are mechanism-specific and cross-applying them is the highest over-block risk for the
    least value.
  * Every flip must carry a one-line mechanism-match statement, which is what makes the
    precision hand-labelling in `--label-sheet` possible.

THE BLIND-METRIC GUARD (ARM C). A gate that only ever flips things is indistinguishable from a
gate that flips everything, so the flip rate alone proves nothing. ARM C re-runs the SAME judge
on the SAME candidates against a DECOY ledger lifted from an unrelated run (different niche
slug). A judge that scores mechanism coverage must flip near-zero there; a judge that scores
topic co-occurrence, or that just likes saying yes, flips at the ARM B rate. The B-minus-C gap
is the discriminator — it is the number that has to move.

ALLOW% is reported with equal prominence to the flip rate: of the candidates, what share KEEP
"none found"? A previous grouping scheme hit a great contradiction rate by collapsing allow% to
22.9% — strict because broken, not because right.

CALIBRATION RECORD (state it, because it weakens the oracles as a held-out test). The judge
prompt was revised four times against pilot runs that INCLUDED the two oracles:
  v1  verdict-first schema -> uniform 18-token no-op on every call (json_schema guided decoding
      with reasoning forced off). Fixed by putting analysis fields ahead of the boolean.
  v2  asked a `shipped`-grade question ("already ships the core mechanism") of `partial`-grade
      rows. Both oracles held, but the bar did not match what the stamps mean.
  v3  added the row's own class semantics and the same-outcome-different-means rule; added
      `pain_points_addressed`, the record's one controlled string, as an ATTENTION cue.
  v4  the judge was still restating each candidate's ARCHITECTURE as its "core job" ("a
      provenance-linked evidence packet", "a claim-to-evidence matrix"), which makes every
      candidate look unserved by construction. Forced an implementation-free END-STATE
      statement first.
Each step is defensible on its own terms, but the RPQA oracle only passes from v4. So the
oracles are a calibration set, not a held-out test, and they carry less weight than the two
control arms and the hand-labelled precision — neither of which was ever tuned toward.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = str(ROOT / "output/checkpoints/checkpoint_*/stage_5_3_refinement.json")
RESULTS = ROOT / "probes/parity_ledger_ab_results.json"

# Strictness ladder, ordered by how hard `_parity_cap` clamps market_fit. "none" is index 0 —
# the permissive end. The probe only ever moves ideas UP this ladder; see `_assert_downgrade`.
_RANK = {"none": 0, "partial": 1, "bundled_free": 2, "substitute": 3, "shipped": 4}
# The money the stamp gates (crews/unified_solution_crew.py:2473-2485, values from settings).
_CAP = {"partial": 0.55, "shipped": 0.45, "substitute": 0.50, "bundled_free": 0.40}

# Ledger classes. `substitute` is deliberately absent — see the v1 constraint above.
_LEDGER_CLASSES = ("partial", "shipped", "bundled_free")

# Both stamp shapes seen in the corpus: "partial by Whitespark: ..." and "substitute (DIY): ...".
_STAMP = re.compile(
    r"^(partial|shipped|bundled_free|substitute)\s*(?:by\s+([^:]{1,80})|\(([^)]{1,80})\))\s*:\s*(.+)$",
    re.I | re.S)


# ----------------------------------------------------------------------------- corpus loading

def _klass(parity) -> str | None:
    """The parity CLASS of a stamp, or None when unstamped/unclassifiable. Free text is
    EXCLUDED rather than silently scored as "none"."""
    if not parity or not str(parity).strip():
        return None
    p = str(parity).strip().lower()
    for k in ("bundled_free", "substitute", "shipped", "partial"):
        if p.startswith(k):
            return k
    return "none" if p.startswith("none") else None


def _parse_stamp(parity: str) -> tuple[str, str, str] | None:
    """(class, incumbent, evidence) from a named stamp, or None when it does not parse."""
    m = _STAMP.match(str(parity).strip())
    if not m:
        return None
    inc = (m.group(2) or m.group(3) or "").strip()
    ev = " ".join(m.group(4).split())
    return (m.group(1).lower(), inc, ev) if inc and ev else None


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _niche_slug(path: str) -> str:
    """The niche label baked into the checkpoint dir name, used to keep ARM C's decoy ledger
    from an unrelated subject."""
    d = os.path.basename(os.path.dirname(path))
    m = re.match(r"checkpoint_(.*?)_?[0-9a-f]{8}-[0-9a-f]{4}-", d)
    return (m.group(1) if m else d).strip("_")


def _idea_brief(idea: dict) -> str:
    """What the judge sees of the candidate.

    `pain_points_addressed` is included FIRST and deliberately. It is the one CONTROLLED string
    in the record — ideas select from the run's own pain list — where every other field is
    free-form LLM prose. The whole defect is a vocabulary lottery, and giving the judge the
    controlled axis is the cheapest way not to reproduce it inside the fix. It is stated to the
    judge as an ATTENTION cue, never as evidence: shared pain says which rows to look at hardest,
    it never establishes coverage (that would just be the topic-proxy failure with extra steps)."""
    feats = idea.get("core_features") or []
    feats = [str(f) for f in feats if isinstance(f, str)][:8]
    pains = [p for p in (idea.get("pain_points_addressed") or []) if isinstance(p, str)][:5]
    return (
        f"NAME: {idea.get('solution_name') or '?'}\n"
        f"BUYER PROBLEMS IT IS FOR:\n" + "".join(f"  - {p[:160]}\n" for p in pains) +
        f"WHAT IT DOES (value proposition): {(idea.get('value_proposition') or '')[:700]}\n"
        f"HOW IT WORKS (technical approach): {(idea.get('technical_approach') or '')[:900]}\n"
        f"CORE FEATURES:\n" + "".join(f"  - {f[:180]}\n" for f in feats) +
        f"HEADLINE: {(idea.get('headline') or '')[:160]}\n"
    )


def load_corpus() -> list[dict]:
    """One record per run file: its ledger rows and its "none found" candidates.

    ELIGIBILITY is recorded here, not assumed: a run contributes only when it has BOTH a
    non-empty ledger AND at least one candidate. Totals are kept so the denominator can be
    stated honestly rather than padded."""
    runs = []
    for path in sorted(glob.glob(CHECKPOINTS)):
        try:
            payload = json.load(open(path))
        except Exception:
            continue
        ideas = [i for i in (payload.get("solution_ideas") or []) if isinstance(i, dict)]
        ledger, candidates = [], []
        classes = defaultdict(int)
        for idea in ideas:
            kl = _klass(idea.get("incumbent_parity"))
            classes[kl or "<unstamped>"] += 1
            if kl == "none":
                candidates.append(idea)
            elif kl in _LEDGER_CLASSES:
                p = _parse_stamp(idea.get("incumbent_parity"))
                if p:
                    ledger.append({"class": p[0], "incumbent": p[1], "evidence": p[2],
                                   "from_idea": idea.get("solution_name") or "?"})
        # Dedupe by (incumbent, evidence) — the same finding is often stamped on several ideas.
        seen, uniq = set(), []
        for row in ledger:
            key = (_norm_name(row["incumbent"]), row["evidence"].lower())
            if key not in seen:
                seen.add(key)
                uniq.append(row)
        runs.append({"path": path, "run": os.path.basename(os.path.dirname(path)),
                     "niche": _niche_slug(path), "ledger": uniq, "candidates": candidates,
                     "n_ideas": len(ideas), "classes": dict(classes)})
    return runs


# ----------------------------------------------------------------------------------- the judge

_JUDGE_SYSTEM = """You decide whether an incumbent ALREADY FOUND in this market would also be \
recorded against a proposed product.

You are given a LEDGER of incumbent findings for one market. Each row names a vendor, a finding \
CLASS, and one line of evidence for what that vendor was found to do:
  partial      — the vendor already serves PART of that job.
  shipped      — the vendor ships that capability outright.
  bundled_free — the capability comes free inside that vendor's product.
You are also given ONE candidate product that currently has NO incumbent recorded against it.

Answer one question: per its evidence line, would a competent competitive analyst record any \
single ledger row's vendor against this candidate too — because that vendor already gets the \
buyer the candidate's OUTCOME, outright or in substantial part?

The test to apply: if a buyer described the candidate out loud, would someone who knows this \
market say "vendor X already does that, at least partly"? If yes, that is coverage.

RULES
1. Judge the JOB, not the topic. Serving the same customers, the same industry, or the same broad \
problem area is NOT coverage. "Both are about local search", "both serve restaurants", "both \
touch invoices" are NOT coverage.
2. A DIFFERENT job is not coverage, however adjacent: monitoring is not remediating, auditing is \
not producing the filing, tracking rankings is not fixing the listing, alerting is not resolving.
3. The same OUTCOME delivered by different means IS coverage. A done-for-you service, a manual \
consulting offer, or a free bundled feature that already gets the buyer that outcome counts — the \
buyer's real alternative is the outcome, not the implementation.
4. IMPLEMENTATION DETAIL IS NOT A DEFENCE, and this is the error to guard against hardest. \
First state the candidate's job as the END STATE the buyer is left in — what they GET. File \
formats, provenance graphs, matrices, dashboards, packets, automation and model choices are how \
the candidate gets there, not what the buyer is buying, and restating them as "the core job" \
makes every candidate look unserved. A vendor who already leaves the buyer in that same end \
state — even by hand, even as a service, even less thoroughly — is coverage.
5. Use ONLY the evidence text in the ledger row. Do not use outside knowledge about what the \
vendor might also sell. If the evidence line does not itself show it, answer none.
5b. The candidate's BUYER PROBLEMS tell you which rows deserve the hardest look — a row aimed at \
the same buyer problem is where coverage is most likely to hide behind different wording. Shared \
buyer problem is NOT itself coverage; the vendor's evidence still has to deliver the outcome.
6. You may not name a vendor that is not in the ledger. Nothing covering the candidate is the \
expected and correct answer for most candidates — say none.
7. When you do find coverage, state in ONE line what the vendor's evidence and the candidate both \
deliver, naming the concrete shared job. If you cannot write that line without restating the \
market or the audience, it is not coverage.

OUTPUT
covered: true only if a ledger row's vendor already serves the candidate's core job.
row_id: the ledger row number you are citing, or 0 when covered is false.
incumbent: the vendor name copied EXACTLY from that ledger row, or "" when covered is false.
mechanism_match: the one-line shared-job statement, or "" when covered is false."""


def _build_prompt(idea: dict, ledger: list[dict]) -> str:
    rows = "".join(
        f"[{n}] {r['incumbent']} ({r['class']}): {r['evidence'][:300]}\n"
        for n, r in enumerate(ledger, 1))
    return (f"LEDGER OF INCUMBENT FINDINGS FOR THIS MARKET\n{rows}\n"
            f"CANDIDATE PRODUCT\n{_idea_brief(idea)}\n"
            "Does any single ledger row already ship this candidate's core mechanism?")


def _verdict_model():
    """Schema field ORDER is load-bearing. Production's OpenRouter structured path runs
    json_schema guided decoding with reasoning forced OFF (llm_service.py:948-952), and a
    verdict-first schema makes the model emit the boolean before it has thought about
    anything: the first pilot returned a uniform 18-completion-token
    `covered=false/row_id=0/""/""` on EVERY call — the same no-op this program already hit
    once (judge emits 0 scores on json_schema + reasoning off). Putting two free-text
    analysis fields AHEAD of `covered` spends the reasoning inside the constrained decode,
    where it is also auditable in the results file."""
    from pydantic import BaseModel, Field
    class _V(BaseModel):
        candidate_core_mechanism: str = Field(
            description="At most 12 words: the END STATE the buyer is left in after using this. "
                        "State what the buyer GETS, not what the product builds. Name no file "
                        "format, data structure, document, dashboard, report or algorithm.")
        closest_row_id: int = Field(
            default=0, description="Ledger row number closest to that mechanism, 0 if none is close.")
        assessment: str = Field(
            description="One or two lines: does that row's EVIDENCE show the vendor already "
                        "serving that same job (outright or in substantial part), or only an "
                        "adjacent job / the same topic?")
        covered: bool = Field(description="true only if a ledger row covers the core mechanism")
        row_id: int = Field(default=0, description="cited ledger row number, 0 when not covered")
        incumbent: str = Field(default="", description="vendor name copied exactly from that row")
        mechanism_match: str = Field(default="", description="one-line shared-mechanism statement")
    return _V


_LOCK = threading.Lock()
_COST = {"calls": 0, "usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "errors": 0}


def _judge(idea: dict, ledger: list[dict], model: str) -> dict:
    """One judge call. Returns the raw verdict plus the ledger-name validation result."""
    from nicheiq.utils.llm_service import LLMService
    V = _verdict_model()
    user = _build_prompt(idea, ledger)
    try:
        r, usage = LLMService.invoke_structured(
            prompt=user, output_model=V, temperature=0.0, timeout=180,
            model_name=model, reasoning_effort="low",
            messages=[{"role": "system", "content": _JUDGE_SYSTEM},
                      {"role": "user", "content": user}])
    except Exception as e:
        with _LOCK:
            _COST["errors"] += 1
        return {"error": str(e)[:200], "covered": False, "flip": False}
    with _LOCK:
        _COST["calls"] += 1
        if usage is not None:
            _COST["usd"] += float(usage.cost or 0.0)
            _COST["prompt_tokens"] += int(usage.prompt_tokens or 0)
            _COST["completion_tokens"] += int(usage.completion_tokens or 0)

    # VALIDATION — a flip must resolve to a real ledger row. The judge cannot invent a vendor,
    # and it cannot cite a row whose name it did not actually copy.
    out = {"covered": bool(r.covered), "row_id": int(r.row_id or 0),
           "incumbent": (r.incumbent or "").strip(),
           "mechanism_match": (r.mechanism_match or "").strip(),
           "core_mechanism": (r.candidate_core_mechanism or "").strip(),
           "assessment": (r.assessment or "").strip(),
           "flip": False, "matched_row": None, "reject": None}
    if not out["covered"]:
        return out
    # Resolve by the CITED ROW first, then check the returned name matches that row. One vendor
    # can legitimately hold several ledger rows (a run stamped both "Profound Agent Analytics"
    # and "Profound FactCheck"); a name-first lookup collapsed those to the first index and
    # rejected a correct citation as a mismatch.
    want = _norm_name(out["incumbent"])
    row = None
    if 1 <= out["row_id"] <= len(ledger) and _norm_name(ledger[out["row_id"] - 1]["incumbent"]) == want:
        row = ledger[out["row_id"] - 1]
    else:
        by_name = [r for r in ledger if _norm_name(r["incumbent"]) == want]
        if by_name:
            row = by_name[0]  # name resolves in the ledger even if the index was sloppy
    if row is None:
        out["reject"] = "invented_incumbent"
        return out
    if not out["mechanism_match"]:
        out["reject"] = "no_mechanism_statement"
        return out
    out["flip"] = True
    out["matched_row"] = row
    out["new_class"] = row["class"]
    return out


def _assert_downgrade(rows: list[dict]) -> None:
    """Downgrade-only, checked rather than trusted: every flip must move strictly UP the
    strictness ladder from "none" (rank 0)."""
    for r in rows:
        if r.get("flip"):
            assert _RANK[r["new_class"]] > _RANK["none"], f"loosening flip: {r}"


# ------------------------------------------------------------------------------- the two arms

def _decoy_ledger(runs: list[dict], i: int) -> tuple[list[dict], str]:
    """ARM C's decoy: a whole ledger lifted from an unrelated run (different niche slug).
    Deterministic, so the control is reproducible.

    What it catches: a judge that flips on topic co-occurrence or that simply likes saying yes.
    What it CANNOT catch: a judge that flips on the vendor name being a plausible player in the
    candidate's market without reading the evidence — the decoy's vendors are implausible, so it
    is easy mode. That is ARM D's job."""
    n = len(runs)
    for step in range(1, n):
        d = runs[(i + step * (n // 2 + 1)) % n]
        if d["niche"] != runs[i]["niche"] and d["ledger"]:
            return d["ledger"], d["run"]
    return [], ""


def _ablated_ledger(runs: list[dict], i: int) -> list[dict]:
    """ARM D: the candidate's OWN ledger — right vendors, right classes, plausible market — with
    every EVIDENCE line replaced by an evidence line from an unrelated run.

    This is the hard control. ARM B and ARM D differ in exactly one thing: whether the evidence
    text actually describes the vendor doing something relevant. If D tracks B, the judge is
    flipping on "that vendor sounds like a player in this market", i.e. rule 5 is decorative and
    the flips are not grounded in the paid-for evidence at all."""
    donor, _ = _decoy_ledger(runs, i)
    own = runs[i]["ledger"]
    if not donor or not own:
        return []
    return [{**row, "evidence": donor[k % len(donor)]["evidence"]}
            for k, row in enumerate(own)]


def run_arms(limit: int, model: str, seed: int) -> dict:
    eligible = [r for r in load_corpus() if r["ledger"] and r["candidates"]]
    # Candidate list, anchored so the two oracle ideas are always measured.
    pool = []
    for i, run in enumerate(eligible):
        for idea in run["candidates"]:
            pool.append({"i": i, "run": run["run"], "niche": run["niche"],
                         "name": idea.get("solution_name") or "?", "idea": idea})
    rnd = random.Random(seed)
    anchors = [c for c in pool if "8500b97d" in c["run"]]
    rest = [c for c in pool if "8500b97d" not in c["run"]]
    rnd.shuffle(rest)
    # The two oracles ride at the head so a --limit run always measures them.
    ordered = anchors + rest
    chosen = ordered[:limit] if limit else ordered

    def work(c):
        led = eligible[c["i"]]["ledger"]
        real = _judge(c["idea"], led, model)
        decoy, donor = _decoy_ledger(eligible, c["i"])
        ctrl = _judge(c["idea"], decoy, model) if decoy else {"flip": False, "skipped": True}
        abl = _ablated_ledger(eligible, c["i"])
        ctrl2 = _judge(c["idea"], abl, model) if abl else {"flip": False, "skipped": True}
        return {"run": c["run"], "niche": c["niche"], "name": c["name"],
                "market_fit_score": c["idea"].get("market_fit_score"),
                "pain_points_addressed": c["idea"].get("pain_points_addressed") or [],
                "value_proposition": (c["idea"].get("value_proposition") or "")[:700],
                "technical_approach": (c["idea"].get("technical_approach") or "")[:900],
                "ledger_size": len(led), "decoy_donor": donor,
                "real": real, "decoy": ctrl, "ablated": ctrl2}

    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(work, chosen))

    for arm in ("real", "decoy", "ablated"):
        _assert_downgrade([r[arm] for r in rows])

    corpus = load_corpus()
    return {
        "model": model, "seed": seed, "limit": limit,
        "judge_system": _JUDGE_SYSTEM,  # frozen with the results so a re-read is auditable
        "cost": dict(_COST),
        "corpus": {
            "run_files": len(corpus),
            "ideas_total": sum(r["n_ideas"] for r in corpus),
            "candidates_total": sum(len(r["candidates"]) for r in corpus),
            "eligible_runs": len(eligible),
            "eligible_candidates": sum(len(r["candidates"]) for r in eligible),
            "avg_ledger_rows": round(
                sum(len(r["ledger"]) for r in eligible) / max(len(eligible), 1), 2),
        },
        "rows": rows,
    }


# ------------------------------------------------------------------------------------ scoring

# Hand labels for precision, keyed "<run-prefix>|<idea name>". Filled in by reading BOTH the
# idea's value proposition/mechanism AND the cited ledger evidence — never the judge's own
# one-liner, which is the thing under test. Values: True = genuinely covered, False = not.
# Produce the worksheet with `--label-sheet`.
_HAND_LABELS: dict[str, bool] = {}
try:  # labels live beside the results file so a re-run of --run cannot erase them
    _HAND_LABELS.update({k: v for k, v in
                         json.load(open(ROOT / "probes/parity_ledger_ab_labels.json")).items()
                         if isinstance(v, bool)})  # the file also carries prose rationales
except Exception:
    pass


def _key(row: dict) -> str:
    return f"{row['run'][:60]}|{row['name']}"


def report(data: dict) -> None:
    rows = data["rows"]
    c = data["corpus"]
    n = len(rows)
    flips = [r for r in rows if r["real"].get("flip")]
    decoy_flips = [r for r in rows if r["decoy"].get("flip")]
    rejects = defaultdict(int)
    for r in rows:
        if r["real"].get("reject"):
            rejects[r["real"]["reject"]] += 1
    kept = n - len(flips)
    allow = 100 * kept / max(n, 1)
    decoy_scored = [r for r in rows if not r["decoy"].get("skipped")]
    decoy_rate = 100 * len(decoy_flips) / max(len(decoy_scored), 1)
    abl_flips = [r for r in rows if r.get("ablated", {}).get("flip")]
    abl_scored = [r for r in rows if not r.get("ablated", {}).get("skipped")]
    abl_rate = 100 * len(abl_flips) / max(len(abl_scored), 1)

    print("=" * 78)
    print("PARITY-LEDGER RE-ADJUDICATION — offline acceptance gate")
    print("=" * 78)
    print(f"\njudge model : {data['model']}   (temperature 0.0, reasoning_effort=low)")
    print(f"judge calls : {data['cost']['calls']}  "
          f"(3 per candidate: ARM B real + ARM C decoy + ARM D evidence-ablated)")
    print(f"measured $  : ${data['cost']['usd']:.4f}  "
          f"({data['cost']['prompt_tokens']:,} prompt / "
          f"{data['cost']['completion_tokens']:,} completion tokens)")
    if data["cost"]["errors"]:
        print(f"call errors : {data['cost']['errors']}")

    print("\n-- DENOMINATOR (stated, not padded) " + "-" * 42)
    print(f"  run files on disk                     {c['run_files']}")
    print(f"  ideas in those runs                   {c['ideas_total']}")
    print(f"  'none found' candidates (all runs)    {c['candidates_total']}")
    print(f"  ELIGIBLE runs (ledger AND candidate)  {c['eligible_runs']}")
    print(f"  ELIGIBLE candidates                   {c['eligible_candidates']}"
          f"  = {100*c['eligible_candidates']/max(c['candidates_total'],1):.1f}% of candidates,"
          f" {100*c['eligible_candidates']/max(c['ideas_total'],1):.1f}% of the corpus")
    print(f"  avg ledger rows per eligible run      {c['avg_ledger_rows']}")
    print(f"  candidates JUDGED in this sample      {n}")

    b_rate = 100 * len(flips) / max(n, 1)
    print("\n-- ARM B vs CONTROLS — the discriminator " + "-" * 37)
    print(f"  ARM B  real ledger        flips {len(flips):>4}/{n:<4} = {b_rate:>5.1f}%")
    print(f"  ARM C  cross-niche decoy  flips {len(decoy_flips):>4}/{len(decoy_scored):<4} = "
          f"{decoy_rate:>5.1f}%   <- must be near zero")
    print(f"  ARM D  own ledger, evidence ABLATED "
          f"{len(abl_flips):>4}/{len(abl_scored):<4} = {abl_rate:>5.1f}%   <- must be near zero")
    print(f"  gap B-C {b_rate - decoy_rate:>5.1f} pp     gap B-D {b_rate - abl_rate:>5.1f} pp")
    print("  ARM C swaps in an unrelated run's whole ledger: catches a judge that flips on topic")
    print("  co-occurrence, or that just likes saying yes.")
    print("  ARM D keeps the candidate's OWN vendors and classes and replaces only the evidence")
    print("  lines with unrelated ones: catches a judge that flips because the vendor sounds like")
    print("  a plausible player, without reading the paid-for evidence. If either control tracks")
    print("  B, B's flip rate is not evidence of anything.")

    print("\n-- ALLOW% — the over-block guard " + "-" * 45)
    print(f"  candidates that KEEP 'none found'      {kept}/{n} = {allow:.1f}%")
    print("  (a scheme that drives this toward 0 is strict because broken, not because right)")

    print("\n-- flip validation (the judge may not invent an incumbent) " + "-" * 19)
    claimed = sum(1 for r in rows if r["real"].get("covered"))
    print(f"  judge claimed coverage                 {claimed}")
    print(f"  accepted (resolved to a ledger row)    {len(flips)}")
    for k, v in sorted(rejects.items()):
        print(f"  rejected: {k:<28} {v}")

    if flips:
        by_class = defaultdict(int)
        capped = 0
        for r in flips:
            by_class[r["real"]["new_class"]] += 1
            mf = r.get("market_fit_score")
            if isinstance(mf, (int, float)) and mf > _CAP[r["real"]["new_class"]]:
                capped += 1
        print("\n-- money the flips would move " + "-" * 48)
        print(f"  flips by class: " + ", ".join(f"{k}={v}" for k, v in sorted(by_class.items())))
        print(f"  flips whose market_fit EXCEEDS the cap it would inherit: {capped}/{len(flips)}"
              f"  (the rest are already below their cap — a stamp change with no score effect)")
        print(f"  flips inheriting `shipped` (cap {_CAP['shipped']}): {by_class.get('shipped', 0)}"
              "   <- class is inherited VERBATIM from the row, and a row earned `shipped`")
        print("     against the SIBLING idea, not against this candidate. Nothing in the design")
        print("     re-grades strictness, so a partial-strength match can inherit a shipped cap.")

    # Padded-denominator guard: the corpus is not 513 independent observations.
    names = defaultdict(set)
    for r in rows:
        names[r["name"]].add(r["run"])
    dup = sum(len(v) for v in names.values() if len(v) > 1)
    scratch = sum(1 for r in rows if re.search(r"checkpoint__|_ab-|abtour|probe-|dump|evalsolo",
                                               r["run"]))
    print("\n-- corpus hygiene (what the denominator is actually made of) " + "-" * 16)
    print(f"  judged candidates whose NAME also appears in another run: {dup}/{n}"
          "   (re-run / resumed jobs)")
    print(f"  judged candidates from scratch or A/B probe runs:         {scratch}/{n}")
    # Same headline numbers on one-row-per-distinct-idea. If they move, 513 was never 513.
    seen, dd = set(), []
    for r in rows:
        k = (r["name"], (r["value_proposition"] or "")[:200])
        if k not in seen:
            seen.add(k)
            dd.append(r)
    dd_flips = sum(1 for r in dd if r["real"].get("flip"))
    print(f"  DEDUPLICATED (one row per distinct idea): {len(dd)} candidates, "
          f"flip {100*dd_flips/max(len(dd),1):.1f}%, "
          f"allow {100*(len(dd)-dd_flips)/max(len(dd),1):.1f}%")

    labelled = [(r, _HAND_LABELS.get(_key(r))) for r in flips if _key(r) in _HAND_LABELS]
    print("\n-- PRECISION (hand-labelled flips) " + "-" * 43)
    if not labelled:
        print("  no labels yet — run --label-sheet, read each pair, fill")
        print("  probes/parity_ledger_ab_labels.json")
    else:
        good = sum(1 for _, v in labelled if v)
        print(f"  hand-labelled flips                    {len(labelled)}")
        print(f"  genuinely covered                      {good}"
              f"  = {100*good/len(labelled):.1f}% precision")
        wrong = [r for r, v in labelled if not v]
        if wrong:
            print("  false flips:")
            for r in wrong[:12]:
                print(f"    {r['name'][:44]:<46} -> {r['real']['incumbent'][:24]}")

    print("\n-- ORACLES (run 8500b97d) " + "-" * 52)
    for name, must_flip, want in (("Reclaim Packet QA", True, "whitespark"),
                                  ("ReceiptAsk", False, None)):
        hit = next((r for r in rows if r["name"] == name and "8500b97d" in r["run"]), None)
        if hit is None:
            print(f"  {name:<38} NOT IN SAMPLE (inconclusive)")
            continue
        got = hit["real"].get("flip")
        inc = hit["real"].get("incumbent", "")
        ok = (got == must_flip) and (want is None or _norm_name(inc) == want)
        verb = "flips -> " + (inc or "?") if got else "keeps 'none found'"
        print(f"  {name:<38} {verb:<34} {'PASS' if ok else 'FAIL'}")
        if got and hit["real"].get("mechanism_match"):
            print(f"      match: {hit['real']['mechanism_match'][:100]}")
    st = data.get("stability")
    if st:
        print(f"\n  READ THE ORACLE ROWS WITH THIS: over {st['reps']} independent judgements at "
              f"temperature 0.0,\n  {st['split']}/{st['subjects']} candidates gave a SPLIT verdict"
              f" — and {st['flip_capable_split']}/{st['flip_capable']} of the candidates that EVER"
              f"\n  flip are unstable. Per-candidate flip counts (out of {st['reps']}):")
        for k, v in sorted(st["per_candidate"].items(), key=lambda kv: -kv[1]):
            if v:
                print(f"    {k[:52]:<54} {v}/{st['reps']}")
        print("  A single-shot PASS/FAIL on an oracle is therefore a sample, not a verdict.")

    # ---- the gate itself. Thresholds are stated here so they can be argued with. ----
    o_rpqa = next((r for r in rows if r["name"] == "Reclaim Packet QA"), None)
    o_recv = next((r for r in rows if r["name"] == "ReceiptAsk"), None)
    rpqa_reps = (st or {}).get("per_candidate", {}).get("Reclaim Packet QA")
    gates = [
        ("oracle: Reclaim Packet QA flips to Whitespark",
         bool(o_rpqa and o_rpqa["real"].get("flip")
              and _norm_name(o_rpqa["real"].get("incumbent")) == "whitespark"),
         f"single-shot; over reps it flipped {rpqa_reps}/{(st or {}).get('reps','?')}"),
        ("oracle: ReceiptAsk keeps 'none found'",
         bool(o_recv and not o_recv["real"].get("flip")), "stable across all reps"),
        ("allow% >= 60 (over-block guard)", allow >= 60.0, f"{allow:.1f}%"),
        ("ARM C cross-niche decoy <= 1%", decoy_rate <= 1.0, f"{decoy_rate:.1f}%"),
        ("ARM D evidence-ablated <= 1%", abl_rate <= 1.0, f"{abl_rate:.1f}%"),
        ("hand-labelled precision >= 80%",
         bool(labelled) and 100 * sum(1 for _, v in labelled if v) / len(labelled) >= 80.0,
         f"{(100*sum(1 for _,v in labelled if v)/len(labelled)) if labelled else 0:.1f}%"
         f" on {len(labelled)} flips"),
        ("verdict is repeatable on flip-capable candidates",
         bool(st) and st.get("flip_capable_split", 1) == 0,
         f"{(st or {}).get('flip_capable_split','?')}/{(st or {}).get('flip_capable','?')}"
         " flip-capable candidates SPLIT"),
    ]
    print("\n-- GATE " + "-" * 69)
    for label, ok, note in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<48} {note}")
    print(f"\n  OVERALL: {'PASS' if all(g[1] for g in gates) else 'FAIL'}"
          f"  ({sum(1 for g in gates if g[1])}/{len(gates)} gates)")
    print()


def stability(reps: int, model: str, seed: int, sample: int, out: str) -> None:
    """How repeatable is one verdict? — the gate's own reliability.

    This exists because the RPQA oracle FLIPPED in a 40-candidate pilot and KEPT 'none found' in
    the 513-candidate full run, with the identical prompt, identical ledger and temperature 0.0.
    A gate whose answer on its own motivating case changes between runs is not measuring the
    thing it claims to measure, and a single-shot flip rate would have hidden that completely.
    Reported as: how many candidates are UNANIMOUS across `reps` independent judgements."""
    eligible = [r for r in load_corpus() if r["ledger"] and r["candidates"]]
    anchors = [(r, i) for r in eligible if "8500b97d" in r["run"] for i in r["candidates"]]
    rest = [(r, i) for r in eligible if "8500b97d" not in r["run"] for i in r["candidates"]]
    random.Random(seed).shuffle(rest)
    subjects = anchors + rest[:sample]

    def work(arg):
        run, idea = arg
        outs = [_judge(idea, run["ledger"], model) for _ in range(reps)]
        return (idea.get("solution_name") or "?", run["run"], outs)

    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(work, subjects))

    unanimous = split = 0
    print(f"JUDGE STABILITY — {reps} independent judgements per candidate, "
          f"temperature 0.0, model {model}\n")
    print(f"  {'candidate':<44} {'flips':>6}  verdict")
    for name, run, outs in rows:
        k = sum(1 for o in outs if o.get("flip"))
        tag = "UNANIMOUS" if k in (0, reps) else "SPLIT"
        if tag == "SPLIT":
            split += 1
        else:
            unanimous += 1
        inc = next((o.get("incumbent") for o in outs if o.get("flip")), "")
        mark = "  <-- anchor run" if "8500b97d" in run else ""
        print(f"  {name[:43]:<44} {k:>3}/{reps}  {tag}{(' -> ' + inc) if inc else ''}{mark}")
    print(f"\n  unanimous {unanimous}/{len(rows)} = {100*unanimous/max(len(rows),1):.1f}%"
          f"   SPLIT {split}/{len(rows)} = {100*split/max(len(rows),1):.1f}%")
    print(f"  judge calls {_COST['calls']}   measured ${_COST['usd']:.4f}")
    print("\n  Every SPLIT candidate is one whose market_fit cap depends on which run you did.")

    # Persist into the results file so `--report` can carry the caveat without anyone
    # hand-copying a number out of a terminal.
    ever = [(name, sum(1 for o in outs if o.get("flip"))) for name, _, outs in rows]
    block = {"reps": reps, "subjects": len(rows), "unanimous": unanimous, "split": split,
             "calls": _COST["calls"], "usd": round(_COST["usd"], 4),
             "per_candidate": {n: k for n, k in ever},
             "flip_capable": sum(1 for _, k in ever if k > 0),
             "flip_capable_split": sum(1 for _, k in ever if 0 < k < reps)}
    try:
        data = json.load(open(out))
        data["stability"] = block
        json.dump(data, open(out, "w"), indent=1)
        print(f"  (written to {out})")
    except Exception as e:
        print(f"  (not persisted: {str(e)[:80]})")


def label_sheet(data: dict, limit: int) -> None:
    """Worksheet for hand-labelling precision: the idea's own words next to the cited evidence.
    The judge's mechanism_match line is printed LAST and marked, so it can be read after the
    two primary sources rather than anchoring on them."""
    flips = [r for r in data["rows"] if r["real"].get("flip")]
    print(f"{len(flips)} flips; showing {min(limit, len(flips))}\n")
    for r in flips[:limit]:
        print("=" * 78)
        print(f"KEY  {_key(r)}")
        print(f"IDEA {r['name']}   (niche: {r['niche'][:50]})")
        print(f"  value prop : {r['value_proposition'][:600]}")
        print(f"  mechanism  : {r['technical_approach'][:600]}")
        row = r["real"]["matched_row"]
        print(f"CITED LEDGER ROW  {row['incumbent']} ({row['class']})")
        print(f"  evidence   : {row['evidence'][:400]}")
        print(f"  [judge said] {r['real']['mechanism_match'][:300]}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="spend judge calls and write results")
    ap.add_argument("--report", action="store_true", help="score the cached results (free)")
    ap.add_argument("--label-sheet", type=int, nargs="?", const=30, default=0,
                    help="print N flips for hand-labelling (free)")
    ap.add_argument("--stability", type=int, default=0,
                    help="re-judge N times per candidate and report unanimity (spends money)")
    ap.add_argument("--stability-sample", type=int, default=20,
                    help="non-anchor candidates included in --stability")
    ap.add_argument("--limit", type=int, default=0, help="candidates to judge (0 = all eligible)")
    ap.add_argument("--model", default=None, help="judge model (default: report_structured_llm)")
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--out", default=str(RESULTS))
    a = ap.parse_args()

    if a.stability:
        from nicheiq.config.settings import settings
        stability(a.stability, a.model or settings.report_structured_llm, a.seed,
                  a.stability_sample, a.out)
        return 0

    if a.run:
        from nicheiq.config.settings import settings
        model = a.model or settings.report_structured_llm
        data = run_arms(a.limit, model, a.seed)
        json.dump(data, open(a.out, "w"), indent=1)
        print(f"wrote {a.out}\n")
        report(data)
        return 0

    if not os.path.exists(a.out):
        print(f"no cached results at {a.out} — run with --run first")
        return 1
    data = json.load(open(a.out))
    if a.label_sheet:
        label_sheet(data, a.label_sheet)
    else:
        report(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
