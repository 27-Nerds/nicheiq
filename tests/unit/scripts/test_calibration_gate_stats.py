"""S0.3 pure-stats functions of scripts/calibration_gate.py — synthetic arrays only.

Covers ONLY cluster_bootstrap_kappa_ci / mcnemar_pvalue / GT_RETEST_KAPPA. No LLM paths,
no checkpoints, no manifest.
"""
import importlib.util
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "calibration_gate", _ROOT / "scripts" / "calibration_gate.py")
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


# ─────────────────────────── GT_RETEST_KAPPA ───────────────────────────
def test_gt_retest_ceiling_constant():
    assert cg.GT_RETEST_KAPPA == 0.506


# ─────────────────────────── mcnemar_pvalue ───────────────────────────
def test_mcnemar_no_discordance_is_one():
    assert cg.mcnemar_pvalue(0, 0) == 1.0


def test_mcnemar_symmetric():
    assert cg.mcnemar_pvalue(3, 10) == cg.mcnemar_pvalue(10, 3)


def test_mcnemar_known_exact_values():
    # n=5, k=0: two-sided p = 2 * (1/32) = 0.0625
    assert cg.mcnemar_pvalue(0, 5) == pytest.approx(0.0625)
    # n=10, k=1: two-sided p = 2 * (1 + 10) / 1024 = 0.021484375
    assert cg.mcnemar_pvalue(1, 9) == pytest.approx(0.021484375)
    # n=2, k=1 (even split): tail = (1+2)/4, doubled = 1.5 -> capped at 1.0
    assert cg.mcnemar_pvalue(1, 1) == 1.0


def test_mcnemar_more_lopsided_is_smaller_p():
    assert cg.mcnemar_pvalue(0, 12) < cg.mcnemar_pvalue(2, 10) < cg.mcnemar_pvalue(5, 7)


def test_mcnemar_ship_rule_threshold_example():
    # 1-vs-8 discordance clears the plan's p<0.10 bar; 3-vs-6 does not.
    assert cg.mcnemar_pvalue(1, 8) < 0.10
    assert cg.mcnemar_pvalue(3, 6) >= 0.10


def test_mcnemar_negative_counts_raise():
    with pytest.raises(ValueError):
        cg.mcnemar_pvalue(-1, 3)
    with pytest.raises(ValueError):
        cg.mcnemar_pvalue(3, -1)


# ─────────────────────── cluster_bootstrap_kappa_ci ───────────────────────
def _mixed_pairs():
    """3 clusters x 4 ideas with mixed (dis)agreement — kappa strictly inside (0, 1)."""
    labels = ["Go", "Conditional", "No-Go"]
    pairs, clusters = [], []
    for ci, cluster in enumerate(("nicheA", "nicheB", "nicheC")):
        for i in range(4):
            a = labels[(ci + i) % 3]
            b = a if (i % 2 == 0) else labels[(ci + i + 1) % 3]
            pairs.append((a, b))
            clusters.append(cluster)
    return pairs, clusters


def test_ci_deterministic_for_seed():
    pairs, clusters = _mixed_pairs()
    ci1 = cg.cluster_bootstrap_kappa_ci(pairs, clusters, n_boot=300, seed=7)
    ci2 = cg.cluster_bootstrap_kappa_ci(pairs, clusters, n_boot=300, seed=7)
    assert ci1 == ci2


def test_ci_default_seed_is_deterministic_module_constant():
    pairs, clusters = _mixed_pairs()
    assert (cg.cluster_bootstrap_kappa_ci(pairs, clusters, n_boot=200)
            == cg.cluster_bootstrap_kappa_ci(pairs, clusters, n_boot=200,
                                             seed=cg.BOOTSTRAP_SEED))


def test_ci_bounds_ordered_and_in_kappa_range():
    pairs, clusters = _mixed_pairs()
    ci = cg.cluster_bootstrap_kappa_ci(pairs, clusters, n_boot=500, seed=1)
    assert ci is not None
    lo, hi = ci
    assert lo <= hi
    assert -1.0 <= lo and hi <= 1.0


def test_ci_perfect_agreement_degenerates_to_unity():
    pairs = [("Go", "Go")] * 4 + [("No-Go", "No-Go")] * 4
    clusters = ["a"] * 4 + ["b"] * 4
    assert cg.cluster_bootstrap_kappa_ci(pairs, clusters, n_boot=100, seed=3) == (1.0, 1.0)


def test_ci_single_cluster_returns_none():
    pairs = [("Go", "Go"), ("Go", "No-Go"), ("No-Go", "No-Go")]
    assert cg.cluster_bootstrap_kappa_ci(pairs, ["only"] * 3, n_boot=50) is None


def test_ci_empty_input_returns_none():
    assert cg.cluster_bootstrap_kappa_ci([], [], n_boot=50) is None


def test_ci_length_mismatch_raises():
    with pytest.raises(ValueError):
        cg.cluster_bootstrap_kappa_ci([("Go", "Go")], ["a", "b"])
