"""P2 — N-sample critic median (_median_calibrations) + usage merge (_merge_usages)."""

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import _median_calibrations, _merge_usages


def _cal(name, mf, tech, nov, seo, obv, solo, reason="r"):
    return SimpleNamespace(
        name=name,
        market_fit_score=mf, market_fit_reason=f"mf-{reason}",
        technical_feasibility_score=tech, technical_feasibility_reason=f"tf-{reason}",
        novelty_score=nov, novelty_reason=f"nov-{reason}",
        seo_scalability_score=seo, seo_scalability_reason=f"seo-{reason}",
        obviousness_score=obv, obviousness_reason=f"obv-{reason}",
        solo_dev_feasibility_score=solo, solo_dev_feasibility_reason=f"solo-{reason}",
    )


class TestMedianCalibrations:
    def test_odd_sample_median_per_criterion(self):
        maps = [
            {"idea a": _cal("Idea A", 0.4, 0.5, 0.6, 0.3, 0.7, 0.5, "s1")},
            {"idea a": _cal("Idea A", 0.6, 0.5, 0.2, 0.9, 0.7, 0.5, "s2")},
            {"idea a": _cal("Idea A", 0.5, 0.5, 0.4, 0.6, 0.7, 0.5, "s3")},
        ]
        out = _median_calibrations(maps)["idea a"]
        assert out.market_fit_score == 0.5   # median(0.4,0.6,0.5)
        assert out.novelty_score == 0.4      # median(0.6,0.2,0.4)
        assert out.seo_scalability_score == 0.6  # median(0.3,0.9,0.6)

    def test_even_sample_median_is_mean_of_middle(self):
        maps = [
            {"x": _cal("X", 0.4, 0.5, 0.5, 0.5, 0.5, 0.5)},
            {"x": _cal("X", 0.6, 0.5, 0.5, 0.5, 0.5, 0.5)},
        ]
        assert _median_calibrations(maps)["x"].market_fit_score == 0.5  # (0.4+0.6)/2

    def test_abstention_drops_out(self):
        # one sample abstains (-1.0) on market_fit → median over the two PRESENT values
        maps = [
            {"x": _cal("X", -1.0, 0.5, 0.5, 0.5, 0.5, 0.5)},
            {"x": _cal("X", 0.4, 0.5, 0.5, 0.5, 0.5, 0.5)},
            {"x": _cal("X", 0.6, 0.5, 0.5, 0.5, 0.5, 0.5)},
        ]
        assert _median_calibrations(maps)["x"].market_fit_score == 0.5

    def test_all_abstain_stays_sentinel(self):
        maps = [{"x": _cal("X", -1.0, 0.5, 0.5, 0.5, 0.5, 0.5)},
                {"x": _cal("X", -1.0, 0.5, 0.5, 0.5, 0.5, 0.5)}]
        assert _median_calibrations(maps)["x"].market_fit_score == -1.0

    def test_reason_from_closest_sample(self):
        maps = [
            {"x": _cal("X", 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, "lo")},
            {"x": _cal("X", 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, "mid")},
            {"x": _cal("X", 0.9, 0.5, 0.5, 0.5, 0.5, 0.5, "hi")},
        ]
        out = _median_calibrations(maps)["x"]
        assert out.market_fit_score == 0.5 and out.market_fit_reason == "mf-mid"


class TestMergeUsages:
    def test_single_returns_original_object(self):
        u = SimpleNamespace(to_dict=lambda: {"cost": 0.01})
        assert _merge_usages([u]) is u  # N=1 byte-identical path

    def test_multi_sums_numeric_fields(self):
        us = [SimpleNamespace(to_dict=lambda: {"cost": 0.01, "tokens": 100, "model": "q"}),
              SimpleNamespace(to_dict=lambda: {"cost": 0.02, "tokens": 150, "model": "q"})]
        m = _merge_usages(us)
        assert m["cost"] == 0.03 and m["tokens"] == 250 and m["model"] == "q"

    def test_all_none_returns_none(self):
        assert _merge_usages([None, None]) is None


def test_default_is_three_after_gate_validation():
    # 2026-07-02 gate: N=3 beat N=1 (kappa 0.19->0.256, exact 37->40, MAE down everywhere)
    from nicheiq.config.settings import Settings
    assert Settings.model_fields["score_calibration_samples"].default == 3
