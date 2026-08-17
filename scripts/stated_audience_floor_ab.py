"""Offline A/B harness for Workstream D (audience-rebalance plan, `~/.claude/plans/
eager-meandering-feather.md`, "D. Stated-audience floor at allocation" + "Validation" section):
does `divergent_stated_audience_floor_count` (Round 0c in `_assign_generator_cells`, wired in
`UnifiedSolutionCrew._build_partition_cells`) actually lift a stated-audience pain into a
generator cell, WITHOUT ever displacing the severity/commercial floor pains, and is it a true
byte-identical no-op at 0?

Replays the REAL production allocator (`_build_partition_cells`) over every cached checkpoint
that has stage_1/3/4 JSON, twice per checkpoint — floor=0 vs floor=1 (the only two shipped
values; monkeypatches `settings.divergent_stated_audience_floor_count` directly, restored after
each checkpoint). Pattern mirrors `scripts/frame_alloc_ab.py` (`_ns()` namespace loader,
`UnifiedSolutionCrew.__new__` construction so no live LLM/search call can ever fire).

Per checkpoint reports:
  - has_stated_audience: does stage_1 carry `resolved_primary_audience` or `user_target_audience`?
  - floor_pain_lifted: at floor=1, is there a pain-cell title present at floor=1 that is ABSENT
    at floor=0 (i.e. Round 0c actually claimed a cell it wouldn't otherwise have)?
  - sev_com_floor_unchanged_0_vs_1: are the severity/commercial floor pains' cell titles IDENTICAL
    between floor=0 and floor=1 (Round 0c must never displace them)?

LIMITATIONS (offline replay, stated not hidden):
  - **floor=0 "byte-identical legacy" is NOT re-verified by a third replay here.** In
    `_build_partition_cells` (unified_solution_crew.py:2757) the Round-0c injection and reserve-math
    block are both gated `if aud_floor and stated_audience:` — at `aud_floor=0` that condition is
    always False regardless of `stated_audience`, so the code path is byte-for-byte the pre-D branch
    by construction (confirmed by code inspection, not a replay). The already-landed unit test
    `tests/unit/test_stated_audience_floor_cells.py::test_floor_zero_byte_identical_to_legacy`
    exercises this directly at the `_assign_generator_cells` level; re-deriving it here via a fake
    "setting absent" replay would be theatre (there is no unset state for a required `int` field).
  - **Plain-niche checkpoints are STRUCTURAL no-ops for this floor** (matches the plan's Risk section
    "D inert on plain-niche" — deliberate, not a bug): `_build_partition_cells` reads
    `resolved_primary_audience or user_target_audience`; when a checkpoint's stage_1 has neither set
    (audience_scope == "niche", i.e. no focusable audience was ever resolved), `stated_audience` is
    None/empty and the `if aud_floor and stated_audience:` gate never fires at ANY floor value — floor=1
    behaves identically to floor=0 on those checkpoints. Which checkpoints had usable stated-audience
    data (the only ones where floor=1 can possibly differ from floor=0) is printed in section 1 below
    and written to the results JSON per-row as `has_stated_audience`.
  - Frame-cell minting (gap/data_asset) still runs during each replay (unconditionally on since
    2026-07-10) but is unmintable from cached data on every checkpoint for the same reason
    `frame_alloc_ab.py` documents (incumbent_rows/data_menu are never persisted) — `workflow` is
    explicitly stubbed off (`_seed_workflow_focuses = lambda: []`) so no live LLM call ever fires.
    Frame cells contributing 0 on every checkpoint means the pain-cell budget arithmetic here is
    effectively the legacy pain-only allocator; noted for completeness, not asserted on.

Run:
    source .venv/bin/activate
    python scripts/stated_audience_floor_ab.py            # original floor=0 vs floor=1 A/B
    python scripts/stated_audience_floor_ab.py --share    # Round 0c-SHARE before/after (2026-08-13)

--------------------------------------------------------------------------------------------
2026-08-13 — WHY THE ORIGINAL MODE ABOVE DOES NOT MEASURE THE SHARE (`--share` added below)
--------------------------------------------------------------------------------------------
The share does not key on `divergent_stated_audience_floor_count`, so sweeping that setting
cannot see it: measured on run bab9f696 the sweep 0/1/2/3 produces the IDENTICAL per-segment
distribution (1/1/2/4) and only at 4 does anything move — and then the wrong way. The original
mode also drops two production inputs that materially change allocation, which made its numbers
unusable as a before/after baseline:
  - the buyer-job partition (`_buyer_job_partition`) is never set, so Round 0e never runs;
  - frame cells never mint offline, so the pain/frame budget arithmetic is the pain-only path.
`--share` restores both from the run's own `metadata.json` (`buyer_job_partition` verbatim, and
`idea_cell_allocation.per_cell` replayed as the frame cells the run actually minted). With both
restored the replay reproduces the two 2026-08-13 reference runs' per-segment distributions
EXACTLY, cell for cell — which is what makes its before/after trustworthy.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.config.settings import settings

_DESIGNATED_JOB_PREFIXES = {
    "f1bb9424": "cottage-food",
    "a3188ad4": "wedding",
    "db1d3f20": "self-hosted-LLM",
    "6a4600ca": "dota-fans (6a4600ca)",
    "4dd67ef2": "insurance (2026-07-11 rerun)",
}


def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**{k: (_ns(v) if isinstance(v, dict) else
                                  [_ns(x) if isinstance(x, dict) else x for x in v] if isinstance(v, list) else v)
                              for k, v in d.items()})


def _load_checkpoint(ck_dir: str) -> dict | None:
    """(pains, segments, niche, stated-audience fields) from a checkpoint dir. Requires
    stage_1_niche_context.json (for resolved_primary_audience/user_target_audience -- the exact
    fields `_build_partition_cells` reads) in addition to stage_3/stage_4 (frame_alloc_ab's
    requirement)."""
    pp = os.path.join(ck_dir, "stage_3_pain_points.json")
    am_path = os.path.join(ck_dir, "stage_4_audience_mapping.json")
    nc_path = os.path.join(ck_dir, "stage_1_niche_context.json")
    meta_path = os.path.join(ck_dir, "metadata.json")
    if not (os.path.exists(pp) and os.path.exists(am_path) and os.path.exists(nc_path)):
        return None
    pains_raw = json.load(open(pp)).get("pain_points") or []
    if not pains_raw:
        return None
    am_raw = json.load(open(am_path))
    segs_raw = am_raw.get("audience_segments") or []
    tools = [t for t in (am_raw.get("tools_currently_used") or []) if t]
    nc_raw = json.load(open(nc_path))
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    pains = [_ns(p) for p in pains_raw]
    for p in pains:  # production opportunity_level is an Enum (.value); JSON gives a str — shim it
        if isinstance(getattr(p, "opportunity_level", None), str):
            p.opportunity_level = SimpleNamespace(value=p.opportunity_level)
    segs = [_ns(s) for s in segs_raw]
    job_id = meta.get("job_id", "") or ""
    designated = next((label for prefix, label in _DESIGNATED_JOB_PREFIXES.items()
                       if job_id.startswith(prefix) or os.path.basename(os.path.dirname(ck_dir + "/")).find(prefix) >= 0),
                       None)
    return {
        "pains": pains, "segments": segs, "niche": nc_raw.get("niche_description") or "",
        "tools": tools,
        "audience_scope": nc_raw.get("audience_scope"),
        "resolved_primary_audience": nc_raw.get("resolved_primary_audience"),
        "user_target_audience": nc_raw.get("user_target_audience"),
        "designated": designated,
    }


def _make_crew(data: dict) -> "usc.UnifiedSolutionCrew":
    """Build a crew via `__new__` with every cache attribute the allocator seam touches
    pre-populated (mirrors `frame_alloc_ab._make_crew`) — no live LLM/search call can ever fire.
    `niche_context` additionally carries resolved_primary_audience/user_target_audience, the exact
    two fields `_build_partition_cells` reads for the stated-audience floor (research_flow.py
    :2755-2756)."""
    crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=data["pains"])
    crew.audience_mapping = SimpleNamespace(audience_segments=data["segments"],
                                            tools_currently_used=list(data["tools"] or []),
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(
        niche_description=data["niche"] or "",
        resolved_primary_audience=data["resolved_primary_audience"],
        user_target_audience=data["user_target_audience"],
    )
    crew.competitor_mentions_text = ""
    crew._incumbent_rows = None
    crew._incumbent_probe_text = ""
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    crew._dissatisfaction_text = ""
    crew._data_menu_text = ""
    crew._payability_map = {}
    crew.ruled_out_pains = []
    crew._seed_workflow_focuses = lambda: []  # never fire the live synthesis LLM call (OFFLINE)
    return crew


def _pain_titles(cells: list, frame: str = "pain") -> list:
    return [getattr(c["pain"], "title", None) for c in cells
            if c.get("pain") is not None and (c.get("frame") or "pain") == frame]


def _floor_titles(pains: list) -> set:
    sev_n = settings.divergent_severity_floor_count
    com_n = settings.divergent_commercial_floor_count
    com_min = settings.divergent_commercial_floor_min_intent

    def _ci(p):
        v = getattr(p, "commercial_intent", None)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0

    titles = {getattr(p, "title", None) for p in
              sorted(pains, key=lambda p: getattr(p, "severity_score", 0) or 0, reverse=True)[:sev_n]}
    titles |= {getattr(p, "title", None) for p in
              sorted([p for p in pains if _ci(p) >= com_min],
                     key=lambda p: (_ci(p), getattr(p, "severity_score", 0) or 0), reverse=True)[:com_n]}
    return titles - {None}


def _replay(data: dict, floor: int) -> list:
    old = settings.divergent_stated_audience_floor_count
    settings.divergent_stated_audience_floor_count = floor
    try:
        crew = _make_crew(data)
        cells = crew._build_partition_cells(data["pains"], [])
    finally:
        settings.divergent_stated_audience_floor_count = old
    return cells


def _row_for(ck_dir: str) -> dict | None:
    data = _load_checkpoint(ck_dir)
    if not data:
        return None
    base = os.path.basename(os.path.dirname(ck_dir + "/"))
    stated_audience = data["resolved_primary_audience"] or data["user_target_audience"]
    has_stated = bool((stated_audience or "").strip())

    cells0 = _replay(data, 0)
    cells1 = _replay(data, 1)
    titles0 = _pain_titles(cells0)
    titles1 = _pain_titles(cells1)
    floor_titles = _floor_titles(data["pains"])

    lifted = sorted(set(titles1) - set(titles0))
    sev_com_0 = floor_titles & set(titles0)
    sev_com_1 = floor_titles & set(titles1)

    return {
        "checkpoint": base, "designated": data["designated"],
        "niche": (data["niche"] or base)[:44],
        "audience_scope": data["audience_scope"],
        "n_pains": len(data["pains"]), "n_segments": len(data["segments"]),
        "has_stated_audience": has_stated,
        "stated_audience": (stated_audience or "")[:80],
        "cells_at_0": len(cells0), "cells_at_1": len(cells1),
        "floor_pain_lifted": lifted,
        "sev_com_floor_titles": sorted(floor_titles),
        "sev_com_floor_unchanged_0_vs_1": sev_com_0 == sev_com_1,
    }


def main():
    dirs = sorted(glob.glob("output/checkpoints/*/"), key=os.path.getmtime, reverse=True)
    rows: list[dict] = []
    for d in dirs:
        try:
            row = _row_for(d)
        except Exception as e:  # noqa: BLE001
            row = None
            print(f"  [error] {d}: {str(e)[:160]}")
        if row:
            rows.append(row)

    if not rows:
        print("No cached checkpoints with stage_1/3/4 JSON found under output/checkpoints/ — "
              "nothing to replay.")
        return

    n = len(rows)
    with_stated = [r for r in rows if r["has_stated_audience"]]
    plain_niche = [r for r in rows if not r["has_stated_audience"]]
    lifted_rows = [r for r in rows if r["floor_pain_lifted"]]
    violations = [r for r in rows if not r["sev_com_floor_unchanged_0_vs_1"]]

    print(f"Found {n} usable checkpoint(s) under output/checkpoints/ "
          f"(defaults: floor={settings.divergent_stated_audience_floor_count} "
          f"target={settings.divergent_target_generators} max_gen={settings.divergent_max_generators} "
          f"sev_floor={settings.divergent_severity_floor_count} "
          f"com_floor={settings.divergent_commercial_floor_count})\n")

    print("=== 1. Data-gap census (plan premise) ===")
    print(f"checkpoints WITH a usable stated audience (resolved_primary_audience or "
          f"user_target_audience non-empty): {len(with_stated)}/{n}")
    print(f"plain-niche checkpoints (structural no-ops for this floor, see LIMITATIONS): "
          f"{len(plain_niche)}/{n}")
    print("usable-stated-audience checkpoint list:")
    for r in with_stated:
        print(f"  - {r['checkpoint']:<70} scope={r['audience_scope']:<16} "
              f"audience={r['stated_audience'][:60]!r}")

    print("\n=== 2. Floor=1 lifts a pain, sev/com floor untouched ===")
    print(f"floor=1 lifted >=1 new pain-cell title vs floor=0: {len(lifted_rows)}/{len(with_stated)} "
          f"of the usable-stated-audience checkpoints "
          f"({len(lifted_rows)}/{n} of all checkpoints)")
    print(f"sev/com floor titles UNCHANGED between floor=0 and floor=1 (no displacement): "
          f"{n - len(violations)}/{n}" +
          (f"  BLOCKER: violations on {[r['checkpoint'] for r in violations]}" if violations else ""))

    print("\n=== 3. Sample of lifted pains (checkpoints where floor=1 actually claimed a cell) ===")
    for r in lifted_rows[:15]:
        print(f"  {r['checkpoint']:<70} audience={r['stated_audience'][:50]!r}")
        for t in r["floor_pain_lifted"]:
            print(f"      + {t}")

    print("\n=== detail: designated checkpoints (plan-named + 6a4600ca/insurance) ===")
    for r in rows:
        if not r["designated"]:
            continue
        print(f"\n-- {r['designated']} ({r['checkpoint']}) --")
        print(f"  audience_scope={r['audience_scope']} has_stated_audience={r['has_stated_audience']} "
              f"stated_audience={r['stated_audience']!r}")
        print(f"  cells_at_0={r['cells_at_0']} cells_at_1={r['cells_at_1']} "
              f"floor_pain_lifted={r['floor_pain_lifted']}")
        print(f"  sev_com_floor_titles={r['sev_com_floor_titles']} "
              f"unchanged_0_vs_1={r['sev_com_floor_unchanged_0_vs_1']}")

    json.dump(rows, open("scripts/stated_audience_floor_ab_results.json", "w"), indent=2, default=str)
    print("\nWrote scripts/stated_audience_floor_ab_results.json")


# ---------------------------------------------------------------------------------------------
# `--share` mode (2026-08-13): Round 0c-SHARE before/after, full production inputs restored.
# ---------------------------------------------------------------------------------------------

def _share_load(ck_dir: str) -> dict | None:
    """`_load_checkpoint` plus the two inputs it drops: the buyer-job partition and the frame
    cells the run actually minted (both persisted in metadata.json)."""
    from nicheiq.utils.buyer_jobs import BuyerJobFamily, BuyerJobPartition

    data = _load_checkpoint(ck_dir)
    if not data:
        return None
    meta_path = os.path.join(ck_dir, "metadata.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    bjp = meta.get("buyer_job_partition") or {}
    partition = None
    if bjp.get("families"):
        fams = tuple(BuyerJobFamily(
            family_id=f["family_id"], buyer=f.get("buyer", ""),
            triggering_job=f.get("triggering_job", ""),
            economic_outcome=f.get("economic_outcome", ""),
            display_label=f.get("display_label", f["family_id"]),
            member_pain_ids=tuple(f.get("member_pain_ids") or []),
            inferred=bool(f.get("inferred"))) for f in bjp["families"])
        by_pain = {(t or "").strip(): f.family_id for f in fams for t in f.member_pain_ids}
        partition = BuyerJobPartition(families=fams, by_pain=by_pain,
                                      source=bjp.get("source", "llm"),
                                      degraded=bool(bjp.get("degraded")))
    seg_by_name = {(getattr(s, "segment_name", "") or "").strip().lower(): s
                   for s in data["segments"]}
    per_cell = (meta.get("idea_cell_allocation") or {}).get("per_cell") or []
    data["partition"] = partition
    data["prod_per_cell"] = per_cell
    data["frames"] = [{"frame": c["frame"],
                       "seg_obj": seg_by_name.get((c.get("segment") or "").strip().lower())}
                      for c in per_cell if (c.get("frame") or "pain") != "pain"]
    return data


def _share_crew(data: dict):
    crew = _make_crew(data)
    crew._buyer_job_partition = data.get("partition")
    frames = list(data.get("frames") or [])

    def _mint(_pains, _segments, budget):
        # Frame seed inputs (incumbent rows / data menu / payability map) are NOT persisted, so
        # live minting is impossible offline. Replay the run's OWN frame cells instead, honoring
        # the caller's budget exactly as `_mint_frame_cells` does.
        if budget <= 0:
            return []
        return [{"frame": f["frame"], "focus": SimpleNamespace(payload={}, anchor_pain_titles=()),
                 "segment": f["seg_obj"], "pain": None} for f in frames[:budget]]
    crew._mint_frame_cells = _mint
    return crew


def _share_dist(cells: list) -> dict:
    out: dict = {}
    for c in cells:
        name = getattr(c.get("segment"), "segment_name", None) or "(no segment)"
        out[name] = out.get(name, 0) + 1
    return out


def share_main():
    """Per-segment cell distribution WITHOUT vs WITH the share, over every cached checkpoint
    whose stated audience resolved to one of its own audience segments.

    "Without" is produced by neutering `_resolved_audience_segment` to return None — which is
    precisely the gate the share sits behind (no resolved segment => legacy), so the OFF arm is
    the legacy code path itself and not a re-implementation of it.
    """
    import nicheiq.crews.unified_solution_crew as _usc

    real_resolver = _usc._resolved_audience_segment
    dirs = sorted(glob.glob("output/checkpoints/*/"), key=os.path.getmtime, reverse=True)
    shown = 0
    for d in dirs:
        try:
            data = _share_load(d)
        except Exception as e:  # noqa: BLE001
            print(f"  [error] {d}: {str(e)[:140]}")
            continue
        if not data:
            continue
        stated = data["resolved_primary_audience"] or data["user_target_audience"]
        if real_resolver(stated, data["segments"]) is None:
            continue  # no resolvable segment => structural no-op, nothing to show
        try:
            _usc._resolved_audience_segment = lambda *_a, **_k: None
            before = _share_dist(_share_crew(data)._build_partition_cells(data["pains"], []))
        finally:
            _usc._resolved_audience_segment = real_resolver
        after = _share_dist(_share_crew(data)._build_partition_cells(data["pains"], []))
        target = (stated or "").strip()
        shown += 1
        print(f"\n== {os.path.basename(os.path.dirname(d + '/'))}")
        print(f"   stated audience (resolved to a segment): {target!r}")
        prod = {}
        for c in data["prod_per_cell"]:
            prod[c.get("segment") or "(no segment)"] = prod.get(c.get("segment") or "(no segment)", 0) + 1
        for s in data["segments"]:
            n = getattr(s, "segment_name", "") or ""
            mark = "  <-- STATED" if n.strip().lower() == target.lower() else ""
            print(f"     prod={prod.get(n, 0)}  before={before.get(n, 0)}  after={after.get(n, 0)}"
                  f"   {n}{mark}")
        if prod and prod != before:
            print("     [warn] replay != production for this checkpoint — treat its "
                  "before/after as indicative only (see LIMITATIONS)")
    if not shown:
        print("No cached checkpoint has a stated audience that resolved to one of its own "
              "audience segments — the share is a structural no-op on all of them.")


def _dispatch():
    if "--census" in sys.argv:
        census_main()
    elif "--share" in sys.argv:
        share_main()
    else:
        main()


# ---------------------------------------------------------------------------------------------
# `--census` mode (2026-08-13, round 2): does the share round SPEND Rounds 0d/0e's budget?
# ---------------------------------------------------------------------------------------------
# `--share` above only prints per-segment distributions, which is blind to the two things the
# share sits directly upstream of: the G2 pinned-title guarantee (Round 0d) and the buyer-job
# family round (Round 0e, docs/DIVERSITY_DECISION_2026-08.md). This mode replays the SAME two
# arms (legacy = `_resolved_audience_segment` neutered to None; share = real) over every
# checkpoint whose stated audience resolves to one of its own segments, and reports per run:
#   family coverage · pain-theme coverage · segments zeroed · stated-segment count · total cells
#   · pin survival (one replay per pain title, pinned via user_pain_scope, both arms)
#   · provenance grounding of every cell the share ADDS to the stated segment
#   · widening steps taken in each arm (see `_prod_pain_split`).
# Budgets swept: the shipped target (6) and the narrow budget (4) the pin eviction was found at.
#
# INPUTS ARE PRODUCTION-SHAPED (round 3, 2026-08-13). Rounds 1-2 called
# `_build_partition_cells(data["pains"], [])`: EVERY pain as `selected_pains` and NOTHING as
# `extra_pains`. Production does neither (unified_solution_crew.py:10663 passes the diversified
# HIGH-priority slice as selected and medium+low as extras), and the difference is not cosmetic —
# with `extra_pains=[]` the widening loop has nothing to widen INTO, so it was structurally dead
# in every measurement rounds 1-2 made (`widened_pains=0` on all 60 rows). The widening loop
# re-runs the whole allocator, share round included, on each step, so it is precisely the path
# where a spare-budget append can change what the NEXT allocation sees. `_prod_pain_split` is
# now the only input path this mode has, and `widened_legacy`/`widened_share` are reported per
# row so a return to a widening-free measurement cannot pass unnoticed.

def _census_cells_metrics(cells: list) -> dict:
    pain_cells = [c for c in cells if c.get("pain") is not None]
    return {
        "n_cells": len(cells),
        "n_pain_cells": len(pain_cells),
        "families": sorted({str(c.get("family_id")) for c in cells if c.get("family_id")}),
        "themes": sorted({str(getattr(c["pain"], "parent_theme_id", None)) for c in pain_cells
                          if getattr(c["pain"], "parent_theme_id", None) is not None}),
        "dist": _share_dist(cells),
        "titles_by_seg": sorted(
            (getattr(c.get("segment"), "segment_name", None) or "", getattr(c["pain"], "title", ""))
            for c in pain_cells),
    }


def _census_grounding(cells: list, seg_name: str) -> dict:
    """Classify every stated-segment pain cell by the provenance that actually backs it."""
    out = {"evidence": 0, "contradicts": 0, "affected_only": 0, "none": 0}
    key = seg_name.strip().lower()
    for c in cells:
        if (getattr(c.get("segment"), "segment_name", "") or "").strip().lower() != key:
            continue
        p = c.get("pain")
        if p is None:
            continue
        ev = [str(s).strip().lower() for s in (getattr(p, "evidence_segments", None) or [])]
        af = [str(s).strip().lower() for s in (getattr(p, "affected_segments", None) or [])]
        if key in ev:
            out["evidence"] += 1
        elif key in af and ev:
            out["contradicts"] += 1      # HAS provenance, and it points somewhere else
        elif key in af:
            out["affected_only"] += 1    # lexical link only, no provenance computed at all
        else:
            out["none"] += 1
    return out


_SHARE_TRACE: list = []
_WIDENED: dict = {}


def _prod_pain_split(data: dict) -> tuple[list, list]:
    """The `(selected_pains, extra_pains)` split production actually hands
    `_build_partition_cells` — reproduced from its single call site,
    `UnifiedSolutionCrew._run_divergent_stage` (unified_solution_crew.py:10663):

        selected = select_diverse_pain_points(high_priority)      # top-7 severity + top-3
                                                                  # mentions + 2 unseen themes
        extras   = medium_priority + low_priority                 # what widening may pull in

    The addressability and evidence gates that sit between are NOT replayed: both are floor-
    protected filters over the same three lists, they need `tool_addressable` / `low_evidence`
    fields that older checkpoints do not carry, and they only ever REMOVE pains — so omitting
    them keeps the replay a superset of production's pain set rather than a different shape.
    """
    from nicheiq.utils.pain_point_formatters import (
        extract_pain_points_by_priority,
        select_diverse_pain_points,
    )
    high, med, low = extract_pain_points_by_priority(
        SimpleNamespace(pain_points=list(data["pains"])))
    return list(select_diverse_pain_points(high)), list(med) + list(low)


def _census_arms(data: dict, *, pinned: list | None = None):
    """(legacy_cells, share_cells) for one checkpoint at the current settings, over the
    production-shaped pain split. Widening steps taken by each arm land in `_WIDENED`."""
    import nicheiq.crews.unified_solution_crew as _usc
    real = _usc._resolved_audience_segment
    scope = SimpleNamespace(pinned_titles=list(pinned or []), excluded_titles=[]) if pinned else None
    selected, extras = _prod_pain_split(data)
    real_alloc = _usc._assign_generator_cells

    def _run(arm: str):
        crew = _share_crew(data)
        crew.user_pain_scope = scope
        calls = [0]

        def _counted(*a, **kw):
            calls[0] += 1
            return real_alloc(*a, **kw)
        try:
            # `_build_partition_cells` allocates once and then RE-allocates once per widening
            # step, so (calls - 1) is exactly the widening count it logs as `widened_pains`.
            _usc._assign_generator_cells = _counted
            cells = crew._build_partition_cells(list(selected), list(extras))
        finally:
            _usc._assign_generator_cells = real_alloc
        _WIDENED[arm] = max(0, calls[0] - 1)
        return cells
    real_topup = _usc._top_up_stated_share

    def _traced(cells, stated_seg, **kw):
        name = getattr(stated_seg, "segment_name", "") or ""
        before = kw["seg_count"].get(name, 0)
        real_topup(cells, stated_seg, **kw)
        _SHARE_TRACE.append({"share": kw["share"], "before": before,
                             "after": kw["seg_count"].get(name, 0),
                             "n_recipients": len(_usc._pains_evidencing_segment(kw["pains"],
                                                                                stated_seg))})
    try:
        _usc._resolved_audience_segment = lambda *_a, **_k: None
        legacy = _run("legacy")
    finally:
        _usc._resolved_audience_segment = real
    _SHARE_TRACE.clear()
    try:
        _usc._top_up_stated_share = _traced
        share_cells = _run("share")
    finally:
        _usc._top_up_stated_share = real_topup
    return legacy, share_cells


def _census_row(ck_dir: str, data: dict, seg_name: str, budget: int) -> dict:
    old_t = settings.divergent_target_generators
    settings.divergent_target_generators = budget
    try:
        legacy, share = _census_arms(data)
        trace = list(_SHARE_TRACE)
        widened = dict(_WIDENED)
        selected, extras = _prod_pain_split(data)
        m_leg, m_shr = _census_cells_metrics(legacy), _census_cells_metrics(share)
        # Pin probe: every pain title in turn, pinned through the real G2 seam.
        pin_evicted, pin_probed = [], 0
        for t in sorted({(getattr(p, "title", "") or "") for p in data["pains"]}):
            if not t:
                continue
            pin_probed += 1
            lg, sh = _census_arms(data, pinned=[t])
            in_lg = any(getattr(c.get("pain"), "title", None) == t for c in lg)
            in_sh = any(getattr(c.get("pain"), "title", None) == t for c in sh)
            if in_lg and not in_sh:
                pin_evicted.append(t)
    finally:
        settings.divergent_target_generators = old_t

    leg_titles = {t for s, t in m_leg["titles_by_seg"] if s == seg_name}
    added = [(s, t) for s, t in m_shr["titles_by_seg"] if s == seg_name and t not in leg_titles]
    zeroed = sorted(n for n, v in m_leg["dist"].items()
                    if v > 0 and m_shr["dist"].get(n, 0) == 0 and n != seg_name)
    return {
        "checkpoint": os.path.basename(os.path.dirname(ck_dir + "/")), "budget": budget,
        "stated_segment": seg_name,
        "n_segments": len(data["segments"]), "n_pains": len(data["pains"]),
        "n_selected": len(selected), "n_extras": len(extras),
        "widened_legacy": widened.get("legacy", 0), "widened_share": widened.get("share", 0),
        "cells_legacy": m_leg["n_cells"], "cells_share": m_shr["n_cells"],
        "stated_legacy": m_leg["dist"].get(seg_name, 0),
        "stated_share": m_shr["dist"].get(seg_name, 0),
        "families_legacy": len(m_leg["families"]), "families_share": len(m_shr["families"]),
        "themes_legacy": len(m_leg["themes"]), "themes_share": len(m_shr["themes"]),
        "segments_zeroed": zeroed,
        "families_dropped": sorted(set(m_leg["families"]) - set(m_shr["families"])),
        "themes_dropped": sorted(set(m_leg["themes"]) - set(m_shr["themes"])),
        "identical": m_leg["titles_by_seg"] == m_shr["titles_by_seg"],
        "added_titles": [t for _s, t in added],
        "grounding_added": _census_grounding(
            [c for c in _census_arms_cache_added(data, added, seg_name)], seg_name),
        "pins_probed": pin_probed, "pins_evicted": pin_evicted,
        "share_trace": trace,
    }


def _census_arms_cache_added(data: dict, added: list, seg_name: str) -> list:
    """Fake cell list holding just the ADDED (pain, stated segment) pairs, so `_census_grounding`
    can classify exactly the cells the share created (and nothing the legacy arm already had)."""
    by_title = {}
    for p in data["pains"]:
        by_title.setdefault(getattr(p, "title", "") or "", p)
    seg = next((s for s in data["segments"]
                if (getattr(s, "segment_name", "") or "") == seg_name), None)
    return [{"pain": by_title[t], "segment": seg} for _s, t in added if t in by_title]


def census_main(budgets=(6, 4)):
    import nicheiq.crews.unified_solution_crew as _usc
    real_resolver = _usc._resolved_audience_segment
    dirs = sorted(glob.glob("output/checkpoints/*/"), key=os.path.getmtime, reverse=True)
    rows: list[dict] = []
    for d in dirs:
        try:
            data = _share_load(d)
        except Exception as e:  # noqa: BLE001
            print(f"  [error] {d}: {str(e)[:140]}")
            continue
        if not data:
            continue
        stated = data["resolved_primary_audience"] or data["user_target_audience"]
        seg = real_resolver(stated, data["segments"])
        if seg is None:
            continue
        name = getattr(seg, "segment_name", "") or ""
        for b in budgets:
            try:
                rows.append(_census_row(d, data, name, b))
            except Exception as e:  # noqa: BLE001
                print(f"  [error] {d} budget={b}: {str(e)[:200]}")

    out = "scripts/stated_audience_share_census.json"
    json.dump(rows, open(out, "w"), indent=2, default=str)
    print(f"\n=== CENSUS: {len(rows)} (run × budget) rows over "
          f"{len({r['checkpoint'] for r in rows})} checkpoints ===")
    hdr = (f"{'checkpoint':<52} {'B':>2} {'cells':>7} {'stated':>7} {'fam':>7} {'theme':>7} "
           f"{'zeroed':>6} {'pinEvict':>8} {'widen':>7} {'sel/ext':>8}")
    print(hdr)
    for r in rows:
        print(f"{r['checkpoint'][:52]:<52} {r['budget']:>2} "
              f"{r['cells_legacy']:>3}->{r['cells_share']:<3} "
              f"{r['stated_legacy']:>3}->{r['stated_share']:<3} "
              f"{r['families_legacy']:>3}->{r['families_share']:<3} "
              f"{r['themes_legacy']:>3}->{r['themes_share']:<3} "
              f"{len(r['segments_zeroed']):>6} {len(r['pins_evicted']):>8} "
              f"{r['widened_legacy']:>3}->{r['widened_share']:<3} "
              f"{r['n_selected']:>3}/{r['n_extras']:<4}")
    for b in budgets:
        sub = [r for r in rows if r["budget"] == b]
        if not sub:
            continue
        g = {"evidence": 0, "contradicts": 0, "affected_only": 0, "none": 0}
        for r in sub:
            for k in g:
                g[k] += r["grounding_added"][k]
        print(f"\n-- budget={b} over {len(sub)} runs --")
        print(f"   INPUT SHAPE — rows with a non-empty extra_pains tail:  "
              f"{sum(1 for r in sub if r['n_extras'])}/{len(sub)}")
        print(f"   rows where the WIDENING loop actually ran (legacy/share): "
              f"{sum(1 for r in sub if r['widened_legacy'])}/{len(sub)} · "
              f"{sum(1 for r in sub if r['widened_share'])}/{len(sub)}"
              + ("   [BLIND SPOT: widening never ran — inputs are not production-shaped]"
                 if not any(r["widened_legacy"] or r["widened_share"] for r in sub) else ""))
        print(f"   rows where the two arms WIDENED a different number of times: "
              f"{sum(1 for r in sub if r['widened_legacy'] != r['widened_share'])}/{len(sub)}")
        print(f"   stated-audience cells gained (sum):     "
              f"{sum(r['stated_share'] - r['stated_legacy'] for r in sub):+d}")
        print(f"   runs where stated audience GAINED:      "
              f"{sum(1 for r in sub if r['stated_share'] > r['stated_legacy'])}/{len(sub)}")
        print(f"   runs where stated audience LOST cells:  "
              f"{sum(1 for r in sub if r['stated_share'] < r['stated_legacy'])}/{len(sub)}")
        print(f"   max gain in any one run:                "
              f"{max((r['stated_share'] - r['stated_legacy']) for r in sub):+d}")
        print(f"   runs where a well-served (>=2) audience gained: "
              f"{sum(1 for r in sub if r['stated_legacy'] >= 2 and r['stated_share'] > r['stated_legacy'])}")
        print(f"   FAMILY coverage regressions:            "
              f"{sum(1 for r in sub if r['families_share'] < r['families_legacy'])}/{len(sub)}")
        print(f"   THEME coverage regressions:             "
              f"{sum(1 for r in sub if r['themes_share'] < r['themes_legacy'])}/{len(sub)}")
        print(f"   total-cell losses:                      "
              f"{sum(1 for r in sub if r['cells_share'] < r['cells_legacy'])}/{len(sub)}")
        print(f"   runs zeroing another segment:           "
              f"{sum(1 for r in sub if r['segments_zeroed'])}/{len(sub)}")
        print(f"   runs where a covered FAMILY became uncovered: "
              f"{sum(1 for r in sub if r['families_dropped'])}/{len(sub)}")
        print(f"   runs where a covered THEME became uncovered:  "
              f"{sum(1 for r in sub if r['themes_dropped'])}/{len(sub)}")
        print(f"   PIN evictions (pain pinned, legacy places it, share drops it): "
              f"{sum(len(r['pins_evicted']) for r in sub)} over "
              f"{sum(r['pins_probed'] for r in sub)} pin probes "
              f"({sum(1 for r in sub if r['pins_evicted'])} runs affected)")
        print(f"   grounding of ADDED stated-segment cells: {g} (total {sum(g.values())})")
        ent_b = sum(1 for r in sub if r["share_trace"] and
                    r["share_trace"][-1]["before"] >= r["share_trace"][-1]["share"])
        ent_a = sum(1 for r in sub if r["share_trace"] and
                    r["share_trace"][-1]["after"] >= r["share_trace"][-1]["share"])
        short = [r for r in sub if r["share_trace"] and
                 r["share_trace"][-1]["after"] < r["share_trace"][-1]["share"]]
        print(f"   OWNER ASK — runs meeting the whole-budget entitlement (count >= share): "
              f"{ent_b}/{len(sub)} legacy -> {ent_a}/{len(sub)} with the share")
        print(f"   runs still short of the share: {len(short)} "
              f"(of which {sum(1 for r in short if r['share_trace'][-1]['n_recipients'] <= r['share_trace'][-1]['after'])}"
              f" have no unused provenance-linked pain left = hard ceiling)")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    _dispatch()
