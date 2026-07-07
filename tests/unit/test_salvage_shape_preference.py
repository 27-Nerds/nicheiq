"""Unit tests for the salvage diversity PREFERENCE (project_type-anchored shape tie-breaker).

The preference reorders already-qualifying salvage close-seconds toward a product SHAPE absent from
the winners — it never changes the promotion bar or count, and is a no-op on a mono-shape pool.
"""
from __future__ import annotations

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import _idea_shape, _salvage_preference_sort


def _c(pt):
    return SimpleNamespace(project_type=pt)


# ---------------------------------------------------------------- _idea_shape

def test_aggregate_family_maps_to_one_shape():
    for pt in ("aggregator", "directory", "comparison-tool", "AGGREGATOR tool",
               "vendor comparison", "peptide vs peptide"):
        assert _idea_shape(_c(pt)) == "aggregate-index"


def test_marketplace_maps_to_match():
    assert _idea_shape(_c("marketplace")) == "match"


def test_saas_and_blank_are_alternative_buckets():
    assert _idea_shape(_c("saas")) == "saas"        # non-aggregate → distinct from the monoculture
    assert _idea_shape(_c("")) == "other"
    assert _idea_shape(SimpleNamespace(project_type=None)) == "other"


# ---------------------------------------------------------------- preference sort

def test_prefers_absent_shape_on_near_tie():
    win_shapes = {"aggregate-index"}
    agg, alt = _c("aggregator"), _c("saas")
    promoted = [(0.70, agg, {}), (0.68, alt, {})]     # within the 0.05 margin
    out = _salvage_preference_sort(promoted, win_shapes, 0.05)
    assert out[0][1] is alt   # 0.68 + 0.05 = 0.73 > 0.70 → the absent (saas) shape wins the slot


def test_real_quality_gap_still_wins():
    win_shapes = {"aggregate-index"}
    agg, alt = _c("aggregator"), _c("saas")
    promoted = [(0.85, agg, {}), (0.60, alt, {})]     # gap > margin
    out = _salvage_preference_sort(promoted, win_shapes, 0.05)
    assert out[0][1] is agg   # 0.60 + 0.05 = 0.65 < 0.85 → quality dominates, not diversity


def test_noop_on_mono_shape_pool():
    # winners + both candidates all aggregate-index → nothing absent → byte-identical to plain sort.
    win_shapes = {"aggregate-index"}
    a, b = _c("aggregator"), _c("directory")
    promoted = [(0.70, a, {}), (0.68, b, {})]
    out = _salvage_preference_sort(promoted, win_shapes, 0.05)
    assert [t[0] for t in out] == [0.70, 0.68]        # unchanged composite order


def test_does_not_change_membership_only_order():
    win_shapes = {"aggregate-index"}
    items = [(0.70, _c("aggregator"), {}), (0.68, _c("saas"), {}), (0.66, _c("marketplace"), {})]
    out = _salvage_preference_sort(items, win_shapes, 0.05)
    assert {id(t[1]) for t in out} == {id(t[1]) for t in items}  # same set, reordered only
    assert len(out) == len(items)
