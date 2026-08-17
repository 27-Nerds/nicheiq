#!/usr/bin/env python3
"""Measure how well the pipeline's own ranking agrees with the analyst's picks.

The target metric for "make the analytics rank like a good analyst": for each run, does
the composite put the ideas the analyst carried forward above the ones they rejected?

    python -m probes.analyst_agreement          # from the repo root, venv active

WHY THIS FILE EXISTS AS A TRACKED PROBE
---------------------------------------
The first two attempts at this measurement were wrong, in a way that was invisible to two
independent review passes because both used the same ad-hoc reconstruction. The preview
materializer writes the SEO score as `seo_growth_potential_score`; `BaseSolutionIdea` reads
`seo_scalability_score` and is `extra='ignore'`, so a naive `model_validate(alt)` silently
drops it and every composite becomes a 3-dimension mean wearing a 4-dimension label. That
artifact moved 4 of 9 picks and manufactured a BUILD-vs-KILLED inversion that never existed.

So: the field mapping is applied in ONE place (`_idea_from_preview`), and `_assert_harness_sane`
fails loudly if a reconstructed idea loses a score the source dict carried. A harness that can
silently drop a field again would repeat the whole error.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nicheiq.models.solution_idea import BaseSolutionIdea  # noqa: E402
from nicheiq.utils.score_helpers import compute_solution_scores  # noqa: E402

# The preview report renames this on the way out; the ranker reads the original name.
_PREVIEW_FIELD_ALIASES = {"seo_growth_potential_score": "seo_scalability_score"}

# Scores that must survive reconstruction. If a source dict carries one and the rebuilt model
# does not, the harness is lying and we stop.
_LOAD_BEARING_SCORES = (
    "market_fit_score",
    "technical_feasibility_score",
    "novelty_score",
    "seo_scalability_score",
    "build_feasibility_score",
)

# Ideas the analyst carried forward, from the IDEA-*.md specs written per shortlist round.
# SEO = judged a traffic/public-data asset rather than a subscription.
_SEO_PICKS = {"competitorriskfactorindex", "censusrentbenchmark", "roastyieldreftable"}
# Explicit negative: spec kept only as a probe-defect record.
_NEGATIVES = {"clearingcalc"}


def _norm(s: str | None) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum())


def _picks_from_specs() -> set[str]:
    """Positives = the ideas that earned a saved spec. KILLED specs are negatives."""
    out = set()
    for p in ROOT.glob("IDEA-*.md"):
        name = p.stem
        if name.startswith("IDEA-SHORTLIST"):
            continue
        if "KILLED" in name:
            continue
        out.add(_norm(re.sub(r"^IDEA-", "", name)))
    return out - _NEGATIVES


def _ordered_picks_from_shortlist() -> dict[str, tuple[str, int, str]]:
    """The 2026-08-16 round is the only one with ORDERED, run-attributed, typed lists:

        # List 1 — SEO-first        # List 2 — SaaS
        ### 1. Name (`runid`)       ### 1. Name (`runid`)

    That is an analyst *ranking*, not just a selection, so it supports a stronger question
    than "did the pick make the top": does the pipeline order them the way the analyst did?
    Returns {normalised_name: (kind, analyst_position, run_id)}.
    """
    doc = ROOT / "IDEA-SHORTLIST-2026-08-16.md"
    if not doc.exists():
        return {}
    out: dict[str, tuple[str, int, str]] = {}
    kind = None
    for line in doc.read_text().splitlines():
        if line.startswith("# List 1"):
            kind = "SEO"
        elif line.startswith("# List 2"):
            kind = "SaaS"
        elif line.startswith("#") and not line.startswith("###"):
            kind = None
        m = re.match(r"###\s*(\d+)\.\s*([A-Za-z][\w \-]*?)\s*[—(]", line)
        if kind and m:
            run = re.search(r"`([0-9a-f]{8})`", line)
            out[_norm(m.group(2))] = (kind, int(m.group(1)), run.group(1) if run else "?")
    return out


def _idea_from_preview(alt: dict) -> BaseSolutionIdea | None:
    d = dict(alt)
    for src, dst in _PREVIEW_FIELD_ALIASES.items():
        if src in d and d.get(dst) is None:
            d[dst] = d[src]
    try:
        return BaseSolutionIdea.model_validate(d)
    except Exception:
        return None


def _assert_harness_sane(alt: dict, idea: BaseSolutionIdea) -> None:
    for field in _LOAD_BEARING_SCORES:
        src = alt.get(field)
        if src is None:
            for a_src, a_dst in _PREVIEW_FIELD_ALIASES.items():
                if a_dst == field:
                    src = alt.get(a_src)
        if isinstance(src, (int, float)) and getattr(idea, field, None) is None:
            raise SystemExit(
                f"HARNESS BUG: '{field}' present in source ({src}) but None after reconstruction "
                f"on idea {alt.get('solution_name')!r}. A score is being silently dropped — fix "
                f"_PREVIEW_FIELD_ALIASES before trusting any number this probe prints."
            )


def _ranked_runs():
    for f in sorted(glob.glob(str(ROOT / "output/checkpoints/preview_report_*.json"))):
        try:
            payload = json.load(open(f))
        except Exception:
            continue
        alts = [a for a in (payload.get("alternative_solutions") or []) if isinstance(a, dict)]
        if len(alts) < 4:
            continue
        ideas, sources = [], []
        for alt in alts:
            idea = _idea_from_preview(alt)
            if idea is None:
                continue
            _assert_harness_sane(alt, idea)
            ideas.append(idea)
            sources.append(alt)
        if len(ideas) < 4:
            continue
        try:
            scores = compute_solution_scores(ideas)
        except Exception:
            continue
        yield Path(f).stem.replace("preview_report_", "")[:8], scores


def main() -> None:
    ordered = _ordered_picks_from_shortlist()
    picks = _picks_from_specs() | set(ordered)
    rows, pair_hits, pair_total = [], 0, 0
    by_type = {"SEO": [], "SaaS": []}

    for run_id, scores in _ranked_runs():
        n = len(scores)
        ranked = [(r, _norm(s.solution_name)) for r, s in enumerate(scores, 1)]
        hit_ranks = [(r, nm) for r, nm in ranked if any(p in nm for p in picks | _NEGATIVES)]
        for rank, nm in hit_ranks:
            matched = next((p for p in picks | _NEGATIVES if p in nm), nm)
            is_neg = matched in _NEGATIVES
            rows.append((rank, n, matched, run_id, is_neg))
            if not is_neg:
                kind = ordered[matched][0] if matched in ordered else (
                    "SEO" if matched in _SEO_PICKS else "SaaS")
                by_type[kind].append(rank / n)
                # pairwise: does this pick outrank a random non-pick in the same run?
                pair_hits += n - rank
                pair_total += n - 1

    rows.sort(key=lambda r: (r[4], r[0]))
    print(f"  {'rank':>8}  {'kind':6} {'analyst':>8}  {'idea':30} run")
    for rank, n, name, run_id, is_neg in rows:
        if is_neg:
            kind = "KILLED"
        else:
            kind = ordered[name][0] if name in ordered else (
                "SEO" if name in _SEO_PICKS else "SaaS")
        pos = f"#{ordered[name][1]}" if name in ordered else "-"
        print(f"  {f'#{rank}/{n}':>8}  {kind:6} {pos:>8}  {name:30} {run_id}")

    print()
    if pair_total:
        print(f"  pairwise AUC (pick outranks non-pick, within run): {pair_hits / pair_total:.3f}")
    for kind, fracs in by_type.items():
        if fracs:
            mean = sum(fracs) / len(fracs)
            print(f"  {kind:4} picks: n={len(fracs)}  mean rank percentile {mean:.2f} "
                  f"(lower is better; 0.5 = chance)")
    print(f"\n  labeled positives available: {len(picks)}  matched in corpus: "
          f"{len({r[2] for r in rows if not r[4]})}")


if __name__ == "__main__":
    main()
