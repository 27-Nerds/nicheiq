#!/usr/bin/env python3
"""A/B for A5 — per-idea parity (A) vs per-family inheritance (B), replayed offline.

    source .venv/bin/activate && python -m probes.parity_family_ab

THE DEFECT (A5). `_probe_mechanism_parity` queries using each idea's OWN vocabulary, so two
ideas addressing the same pain with the same mechanism get independent verdicts. Measured on
the corpus: 51.3% of multi-idea pains carry a none-vs-covered contradiction. Worse,
`_pivot_acceptable` (crews/unified_solution_crew.py:9208) admits a red-team revision ONLY when
its parity `startswith("none")` — so revisions enter the pool precisely when the probe MISSES,
and they are probed alone, after the discovery-query budget is spent. The pipeline selects for
probe failures. Live instance: 'Reclaim Packet QA' shipped as the #1 recommendation with
"none found" while its own family sibling was ruled out as "partial by Whitespark".

ARM A  each idea's captured `incumbent_parity`, exactly as it shipped.
ARM B  group by production's own family key (`mechanism_tag|data_source_tag`, :2491), scoped
       within a run; every member inherits the family's STRICTEST finding.

WHY THIS IS FREE. Every verdict already exists on disk. Inheritance is a regrouping, not a
re-probe, so the counterfactual needs no search calls. What it CANNOT answer is whether a
family-level QUERY would discover incumbents that per-idea queries miss — that needs live
Serper and is a separate, second-order question.

THE METRIC MUST DETECT THE CHANGE GOING WRONG. Contradictions collapse to zero if you stamp
everything "covered" — which would over-cap every idea and starve the pipeline. So this reports
the ALLOW-CASE with equal weight: how many ideas legitimately KEEP "none found" under B. A
guard that is strict because it is broken looks identical to a guard that works, unless you
measure what it still permits.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Strictness ladder. "none found" is the permissive end; anything naming an incumbent is
# stricter, ordered by how hard `_parity_cap` clamps market_fit (crews:2478-2485).
_RANK = {"none": 0, "partial": 1, "bundled_free": 2, "substitute": 3, "shipped": 4}


def _klass(parity: str | None) -> str | None:
    """The parity CLASS of a stamp, or None when unstamped."""
    if not parity or not str(parity).strip():
        return None
    p = str(parity).strip().lower()
    for k in ("bundled_free", "substitute", "shipped", "partial"):
        if p.startswith(k):
            return k
    if p.startswith("none"):
        return "none"
    return None  # free text we cannot classify — excluded, never silently scored as "none"


def _family_key(idea: dict) -> str | None:
    """Production's own family key. No proxy: if the tags are absent, the idea is EXCLUDED
    rather than grouped on something that merely correlates."""
    mech = (idea.get("mechanism_tag") or "").strip().lower()
    src = (idea.get("data_source_tag") or "").strip().lower()
    return f"{mech}|{src}" if (mech or src) else None


def _keys_for(idea: dict, mode: str) -> list[str]:
    """Grouping key(s) for one idea under a given scheme.

    MEASURED 2026-08-16 — `mechanism_tag` is LLM-authored free text, not a controlled
    vocabulary, so it is itself a vocabulary lottery. The motivating case proves it:
        Reclaim Packet QA      -> mechanism_tag "reclaim-timeline-forensics"
        Reinstatement Dossier  -> mechanism_tag "evidence-backed entity continuity"
    Same pain, same mechanism in substance, different tags. Family grouping CANNOT catch the
    defect it was proposed to fix. `pain_points_addressed` is a shared controlled string
    (ideas select from the run's own pain list), which is why it groups where tags do not.
    """
    if mode == "family":
        k = _family_key(idea)
        return [k] if k else []
    pains = [p.strip().lower() for p in (idea.get("pain_points_addressed") or [])
             if isinstance(p, str) and p.strip()]
    if mode == "pain":
        return pains
    if mode == "pain_x_family":
        fk = _family_key(idea)
        return [f"{p}||{fk}" for p in pains] if fk else []
    raise ValueError(mode)


def _measure(runs: list[str], mode: str) -> dict:
    groups_multi = groups_contra = 0
    tightened = newly_capped = kept_none = 0
    for path in runs:
        try:
            payload = json.load(open(path))
        except Exception:
            continue
        ideas = payload.get("solution_ideas") or payload.get("ideas") or []
        g: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for idea in ideas:
            if not isinstance(idea, dict):
                continue
            kl = _klass(idea.get("incumbent_parity"))
            if kl is None:
                continue
            for k in _keys_for(idea, mode):
                g[k].append((idea.get("solution_name") or "?", kl))
        for members in g.values():
            if len(members) < 2:
                continue
            groups_multi += 1
            strictest = max(_RANK[k] for _, k in members)
            if strictest > 0 and any(_RANK[k] == 0 for _, k in members):
                groups_contra += 1
            for _, kl in members:
                if _RANK[kl] < strictest:
                    tightened += 1
                    if kl == "none":
                        newly_capped += 1
                elif kl == "none":
                    kept_none += 1
    allow = 100 * kept_none / max(kept_none + tightened, 1)
    return dict(multi=groups_multi, contra=groups_contra, tightened=tightened,
                newly_capped=newly_capped, kept_none=kept_none, allow=allow)


def main() -> int:
    runs = sorted(glob.glob(str(ROOT / "output/checkpoints/checkpoint_*/stage_5_3_refinement.json")))

    print("A5 A/B — which GROUPING KEY actually catches the defect?\n")
    print(f"  {'scheme':16} {'multi':>6} {'contra':>7} {'tighten':>8} {'none->cov':>10} {'keeps none':>11} {'allow%':>7}")
    for mode in ("family", "pain", "pain_x_family"):
        m = _measure(runs, mode)
        print(f"  {mode:16} {m['multi']:>6} {m['contra']:>7} {m['tightened']:>8} "
              f"{m['newly_capped']:>10} {m['kept_none']:>11} {m['allow']:>6.1f}%")
    print("\n  'allow%' = share of grouped members that KEEP 'none found'. A scheme that drives")
    print("  this toward 0 is over-blocking: strict because it is broken, not because it is right.\n")

    tot_ideas = eligible = 0
    fam_multi = fam_contra = 0
    changed = kept_none = newly_capped = 0
    revision_blocked = 0
    examples: list[str] = []

    for path in runs:
        try:
            payload = json.load(open(path))
        except Exception:
            continue
        ideas = payload.get("solution_ideas") or payload.get("ideas") or []
        fams: dict[str, list[tuple[str, str]]] = defaultdict(list)

        for idea in ideas:
            if not isinstance(idea, dict):
                continue
            tot_ideas += 1
            key = _family_key(idea)
            kl = _klass(idea.get("incumbent_parity"))
            if key is None or kl is None:
                continue
            eligible += 1
            fams[key].append((idea.get("solution_name") or "?", kl))

        for key, members in fams.items():
            if len(members) < 2:
                continue
            fam_multi += 1
            ranks = [_RANK[k] for _, k in members]
            strictest = max(ranks)
            has_none = any(r == 0 for r in ranks)
            if has_none and strictest > 0:
                fam_contra += 1
                if len(examples) < 6:
                    strict_name = next(n for n, k in members if _RANK[k] == strictest)
                    none_names = [n for n, k in members if k == "none"]
                    examples.append(
                        f"    {key[:44]}\n"
                        f"      strictest: {strict_name[:38]} ({[k for n,k in members if n==strict_name][0]})\n"
                        f"      inherits:  {', '.join(none_names)[:70]}"
                    )
            for _, kl in members:
                if _RANK[kl] < strictest:
                    changed += 1
                    if kl == "none":
                        newly_capped += 1
                        revision_blocked += 1  # would fail _pivot_acceptable's startswith("none")
                elif kl == "none":
                    kept_none += 1

    print("A5 A/B — per-idea parity (A) vs per-family inheritance (B)\n")
    print(f"  runs scanned:                  {len(runs)}")
    print(f"  ideas total:                   {tot_ideas}")
    print(f"  eligible (family key + parity):{eligible:>6}  "
          f"({100*eligible/max(tot_ideas,1):.1f}% — the rest lack tags or carry unclassifiable free text)")
    print()
    print(f"  multi-idea families:           {fam_multi}")
    print(f"  ...carrying a contradiction:   {fam_contra}"
          f"  ({100*fam_contra/max(fam_multi,1):.1f}%)")
    print()
    print("  ARM B effects:")
    print(f"    ideas whose parity tightens:   {changed}")
    print(f"    of those, none -> covered:     {newly_capped}   <- over-blocking risk")
    print(f"    ideas that KEEP 'none found':  {kept_none}   <- ALLOW-CASE (must stay large)")
    if changed + kept_none:
        share = 100 * kept_none / (changed + kept_none)
        print(f"    allow-case share:              {share:.1f}% of family members keep 'none'")
    print()
    print(f"  revisions that would newly FAIL _pivot_acceptable: {revision_blocked}")
    print("    (each is a candidate admitted today only because its solo probe missed)")
    if examples:
        print("\n  sample families that would inherit:")
        for e in examples:
            print(e)

    print("\n  NOT answered here: whether a family-level QUERY finds incumbents the per-idea")
    print("  queries miss. That needs live Serper and is a separate experiment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
