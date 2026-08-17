#!/usr/bin/env python3
"""A/B for R3 — delete the parity-clearance clause from the revision accept-gates.

    source .venv/bin/activate && python -m probes.revision_gate_ab

THE CLAUSE (`crews/unified_solution_crew.py:9208`, mirrored in `crews/red_team_review.py:279`):

    if _comp(rev) > _comp(orig) and rev_par.startswith("none"):

A red-team revision or parity pivot is admitted ONLY when its own parity says "none found".
Findings are ALREADY priced in through `_parity_cap` (:2473-2485), so requiring explicit
clearance double-counts them — and it guarantees that every revision-born idea in the pool is
one the probe failed to find an incumbent for. Measured: 7 of 7 revision-born ideas corpus-wide
carry "none found". That is not a correlation; the clause makes it true by construction.

WHY THIS IS A FREE, DETERMINISTIC A/B. The worker logs record both gate inputs on every
rejection:

    rejected 'X' (composite 0.590 vs 0.568, parity 'partial by profound: ...')

so the counterfactual needs no model, no search, and no re-run — the decision is a pure
function of two logged numbers and a logged string. ARM B recomputes it with the clause
removed. 419 real rejections are available.

WHAT THIS CANNOT TELL YOU. It measures which DECISIONS change, not whether the outcomes are
better. Judging "better" needs a preference oracle, and the only one available here (12 analyst
picks) is small and substantially circular. So the honest deliverable is the size and shape of
the behaviour change — the argument for R3 is structural (stop selecting for probe blindness),
not that these specific revisions were good.
"""
from __future__ import annotations

import glob
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# `rejected 'NAME' (composite REV vs ORIG, parity 'PARITY')`
_REJECT = re.compile(
    r"\[(?P<gate>RedTeamRevision|ParityPivot)\] rejected(?: pivot of)? "
    r"'(?P<name>[^']{1,120})' \(composite (?P<rev>[0-9.]+) vs (?P<orig>[0-9.]+), "
    r"parity '(?P<parity>[^']*)'"
)

# Unit-test fixtures pollute the worker logs; they are not production decisions.
_FIXTURE_NAMES = {"idea", "ideaa", "ideab", "revised idea", "revised ideaa", "revised ideab"}


def _klass(parity: str) -> str:
    p = (parity or "").strip().lower()
    if p.startswith("none"):
        return "none"
    for k in ("bundled_free", "substitute", "shipped", "partial"):
        if p.startswith(k):
            return k
    return "unstamped"


def main() -> int:
    rows = []
    for path in sorted(glob.glob(str(ROOT / "output/logs/*.log"))):
        try:
            text = open(path, errors="replace").read()
        except Exception:
            continue
        for m in _REJECT.finditer(text):
            if m.group("name").strip().lower() in _FIXTURE_NAMES:
                continue
            rows.append((m.group("gate"), m.group("name"),
                         float(m.group("rev")), float(m.group("orig")),
                         m.group("parity")))

    if not rows:
        print("  no rejection events parsed — check the log format")
        return 2

    # ARM A = today: every one of these was rejected.
    # ARM B = R3: admit on composite improvement alone; the parity clause is gone.
    flips = [r for r in rows if r[2] > r[3]]
    blocked_by_composite = len(rows) - len(flips)

    print("R3 A/B — delete the parity-clearance clause from the revision accept-gates\n")
    print(f"  rejection events parsed (production, fixtures excluded): {len(rows)}")
    print(f"  ARM A (today): all {len(rows)} rejected")
    print(f"  ARM B (clause deleted): {len(flips)} would now be ADMITTED"
          f"  ({100*len(flips)/len(rows):.1f}%)")
    print(f"  still rejected on composite alone: {blocked_by_composite}")
    print()
    print("  parity carried by the newly-admitted revisions:")
    for k, c in Counter(_klass(r[4]) for r in flips).most_common():
        note = "   <- would have been admitted today too" if k == "none" else ""
        print(f"    {k:14} {c:>4}{note}")
    print()
    gains = sorted((r[2] - r[3] for r in flips), reverse=True)
    if gains:
        print(f"  composite gain of newly-admitted: max {gains[0]:+.3f}  "
              f"median {gains[len(gains)//2]:+.3f}  min {gains[-1]:+.3f}")
    print()
    print("  largest-gain examples (these are the decisions that would change):")
    for gate, name, rev, orig, parity in sorted(flips, key=lambda r: r[3] - r[2])[:6]:
        print(f"    {gate:16} {name[:44]:46} {orig:.3f} -> {rev:.3f}  [{_klass(parity)}]")

    print("\n  NOTE: this measures which DECISIONS change, not whether outcomes improve.")
    print("  The case for R3 is structural — findings are already priced in via _parity_cap,")
    print("  so the clause double-counts them and guarantees revision winners are probe-blind.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
