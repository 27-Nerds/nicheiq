"""Hermetic tests for the S3.2 per-cell survival floor (reserve/restore around the pool-wide
culls). Covers _reserve_cell_best + _restore_reserved_cells against the real culls
(_finalize_critic_pool, _pool_and_dedup_raw_concepts with the semantic stage stubbed)."""

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    c = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    c._semantic_dedup = lambda kept, threshold: kept  # hermetic: no embedding calls
    return c


def _pain(title):
    return SimpleNamespace(title=title)


def _cells(*titles):
    return [{"pain": _pain(t), "segment": None} for t in titles]


def _concept(name, pain, obv=0.5, already_exists=False, no_route=False, mech="lookup",
             ds="ds", jt="jt"):
    return SimpleNamespace(
        concept_name=name, source_pain=pain, source_segment=None,
        obviousness_score=obv, critic_already_exists=already_exists, critic_no_route=no_route,
        data_feasibility_score=0.7, build_feasibility_score=0.8,
        data_access_model="public", data_acquisition_notes="",
        mechanism_tag=mech, data_source_tag=ds, journey_tag=jt,
        ideation_technique="t",
    )


def _fill(pain, n, prefix):
    # Distinct tags per concept so the structural/pain-source dedup stages keep them all.
    return [_concept(f"{prefix}{i}", pain, obv=0.1 + i * 0.01,
                     mech=f"m-{prefix}{i}", ds=f"d-{prefix}{i}", jt=f"j-{prefix}{i}")
            for i in range(n)]


def _cell_titles(groups):
    return [cell["pain"].title for cell, _ in groups]


def test_starved_cell_restored_through_real_culls():
    # Cell B's concepts are ALL flagged already_exists; the pool-wide MIN_KEEP floor is
    # satisfied by 20+ unflagged concepts from A/C, so the critic cull drops B entirely.
    crew = _crew()
    cells = _cells("Pain A", "Pain B", "Pain C")
    pool = (
        _fill("Pain A", 11, "a")
        + [_concept("B worst", "Pain B", obv=0.9, already_exists=True, mech="m-b1", ds="d-b1"),
           _concept("B best", "Pain B", obv=0.3, already_exists=True, mech="m-b2", ds="d-b2")]
        + _fill("Pain C", 11, "c")
    )
    reserved = UnifiedSolutionCrew._reserve_cell_best(pool, cells)
    assert len(reserved) == 3

    survivors = crew._finalize_critic_pool(list(pool))
    survivors = crew._pool_and_dedup_raw_concepts(survivors, keep_fraction=1.0)
    assert "Pain B" not in _cell_titles(UnifiedSolutionCrew._group_pool_by_cell(survivors, cells))

    restored = UnifiedSolutionCrew._restore_reserved_cells(survivors, reserved, cells)
    groups = UnifiedSolutionCrew._group_pool_by_cell(restored, cells)
    assert "Pain B" in _cell_titles(groups)
    b_concepts = [cs for cell, cs in groups if cell["pain"].title == "Pain B"][0]
    assert [c.concept_name for c in b_concepts] == ["B best"]  # least-bad already_exists
    assert len(restored) == len(survivors) + 1


def test_no_restore_when_cell_survived_naturally():
    cells = _cells("Pain A", "Pain B")
    pool = _fill("Pain A", 4, "a") + _fill("Pain B", 4, "b")
    reserved = UnifiedSolutionCrew._reserve_cell_best(pool, cells)
    restored = UnifiedSolutionCrew._restore_reserved_cells(list(pool), reserved, cells)
    assert restored == pool  # both cells represented — nothing appended


def test_noop_on_empty_cells():
    pool = _fill("Pain A", 3, "a")
    assert UnifiedSolutionCrew._reserve_cell_best(pool, []) == []
    # Fallback / legacy broad path: nothing reserved -> pool returned untouched.
    assert UnifiedSolutionCrew._restore_reserved_cells(pool, [], []) is pool


def test_reserve_precedence_least_bad():
    # unflagged > no_route > already_exists; within tier obviousness ascending.
    cells = _cells("Pain X", "Pain Y", "Pain Z")
    pool = [
        # X: unflagged (even at worse obv) beats flagged concepts.
        _concept("x-exists", "Pain X", obv=0.1, already_exists=True),
        _concept("x-noroute", "Pain X", obv=0.2, no_route=True),
        _concept("x-clean", "Pain X", obv=0.8),
        # Y: no_route beats already_exists; lowest-obv no_route wins; BOTH-flagged counts
        # as already_exists (mirrors _finalize_critic_pool's short-circuit).
        _concept("y-exists", "Pain Y", obv=0.05, already_exists=True),
        _concept("y-both", "Pain Y", obv=0.01, already_exists=True, no_route=True),
        _concept("y-noroute-worse", "Pain Y", obv=0.9, no_route=True),
        _concept("y-noroute-best", "Pain Y", obv=0.4, no_route=True),
        # Z: all already_exists -> still reserves its best (lowest obv).
        _concept("z-exists-worse", "Pain Z", obv=0.7, already_exists=True),
        _concept("z-exists-best", "Pain Z", obv=0.2, already_exists=True),
    ]
    reserved = {cell["pain"].title: best.concept_name
                for cell, best in UnifiedSolutionCrew._reserve_cell_best(pool, cells)}
    assert reserved == {"Pain X": "x-clean", "Pain Y": "y-noroute-best",
                        "Pain Z": "z-exists-best"}


def test_restore_guards_exact_name_duplicates():
    # The reserved concept's name survived under another cell's provenance (name dedup keeps
    # one copy) — restoring would duplicate the name downstream, so the cell stays out.
    cells = _cells("Pain A", "Pain B")
    reserved_b = _concept("Shared Name", "Pain B", obv=0.3, already_exists=True)
    survivor_a = _concept("shared name", "Pain A", obv=0.2)
    restored = UnifiedSolutionCrew._restore_reserved_cells(
        [survivor_a], [(cells[1], reserved_b)], cells)
    assert restored == [survivor_a]
