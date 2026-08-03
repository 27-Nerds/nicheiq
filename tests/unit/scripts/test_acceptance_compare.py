"""scripts/acceptance_compare.py — the measurement harness itself, over synthetic checkpoints.

Guards the three defects docs/CODEX_REVIEW_2026-08.md section 4(a) found:
  1. stale stage-6 demand floats counted for ideas with zero validated keywords
  2. cap-pinning counted (identical finals) instead of attributed (raw x stamp join)
  3. source_pain "coverage" asserted as semantic binding when it only tests non-nullness

Offline: writes tiny JSON checkpoint dirs to tmp_path. No LLM, no real run artifacts.
"""
import importlib.util
import json
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "acceptance_compare", _ROOT / "scripts" / "acceptance_compare.py")
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

CAPS = dict(ac._CAP_DEFAULTS)  # frozen catalog so tests don't drift with .env


# --------------------------------------------------------------------------- fixtures
def _write(d, name, obj):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(obj))


def _idea(name, **kw):
    base = {
        "solution_name": name,
        "candidate_status": "active",
        "source_frame": "pain",
        "market_fit_score": 0.45,
        "market_fit_score_raw": 0.85,
        "incumbent_parity": "none found",
        "data_access_model": "public",
        "build_feasibility_score": 0.8,
        "source_segment_payability": 0.8,
        "value_proposition": "",
        "description": "",
        "source_pain": None,
    }
    base.update(kw)
    return base


def _ckpt(tmp_path, ideas=(), pains=(), selection=None, stage6=None, name="ck"):
    d = tmp_path / name
    _write(d, "stage_5_3_refinement.json", {"solution_ideas": list(ideas)})
    _write(d, "stage_3_pain_points.json", {"pain_points": list(pains)})
    if selection is not None:
        _write(d, "stage_5_6_selection.json", {"all_solution_scores": selection})
    if stage6 is not None:
        _write(d, "stage_6_keyword_validation.json", stage6)
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


# =========================================================== 1. unmeasured exclusion
def test_unmeasured_row_excluded_from_spread_and_max(tmp_path):
    """demand_unmeasured=True rows never enter spread/max, and are counted separately."""
    sel = [
        {"solution_name": "A", "keyword_demand_score": 0.70, "demand_unmeasured": False},
        {"solution_name": "B", "keyword_demand_score": 0.75, "demand_unmeasured": False},
        # the hotfix marker: stale float stays in stage-6, selection says unmeasured
        {"solution_name": "C", "keyword_demand_score": None, "demand_unmeasured": True},
    ]
    st6 = [
        {"solution_name": "A", "keyword_demand_score": 0.70, "validated_keywords": ["k"]},
        {"solution_name": "B", "keyword_demand_score": 0.75, "validated_keywords": ["k"]},
        {"solution_name": "C", "keyword_demand_score": 0.98, "validated_keywords": []},
    ]
    p = ac.demand_panel(_ckpt(tmp_path, selection=sel, stage6=st6))
    assert "authoritative" in p["demand_source"]
    assert p["demand_measured_n"] == 2
    assert p["demand_unmeasured_n"] == 1
    assert p["demand_max"] == pytest.approx(0.75)          # NOT the stale 0.98
    assert p["demand_spread"] == pytest.approx(0.05)


def test_stale_stage6_value_reported_as_divergence(tmp_path):
    sel = [{"solution_name": "C", "keyword_demand_score": None, "demand_unmeasured": True}]
    st6 = [{"solution_name": "C", "keyword_demand_score": 0.98, "validated_keywords": []}]
    p = ac.demand_panel(_ckpt(tmp_path, selection=sel, stage6=st6))
    assert p["demand_stage6_divergence"] == [("C", None, 0.98, 0)]


def test_never_attempted_is_not_unmeasured(tmp_path):
    """score None + flag False = never keyword-validated; a distinct bucket from unmeasured."""
    sel = [
        {"solution_name": "A", "keyword_demand_score": 0.7, "demand_unmeasured": False},
        {"solution_name": "B", "keyword_demand_score": None, "demand_unmeasured": True},
        {"solution_name": "C", "keyword_demand_score": None, "demand_unmeasured": False},
    ]
    p = ac.demand_panel(_ckpt(tmp_path, selection=sel))
    assert (p["demand_measured_n"], p["demand_unmeasured_n"], p["demand_not_attempted_n"]) == (1, 1, 1)


def test_baseline_without_demand_unmeasured_field_degrades_gracefully(tmp_path):
    """The E4 baseline predates the field: nulls are unclassifiable, not silently 'measured'."""
    sel = [
        {"solution_name": "A", "keyword_demand_score": 0.93},
        {"solution_name": "B", "keyword_demand_score": 0.97},
        {"solution_name": "C", "keyword_demand_score": None},
    ]
    p = ac.demand_panel(_ckpt(tmp_path, selection=sel))
    assert p["demand_unmeasured_field_present"] is False
    assert p["demand_unclassifiable_n"] == 1
    assert p["demand_unmeasured_n"] == 0
    assert p["demand_max"] == pytest.approx(0.97)


def test_stage6_fallback_is_labelled_and_drops_zero_keyword_rows(tmp_path):
    """No selection scores -> fall back, SAY SO, and still refuse the stale float."""
    st6 = [
        {"solution_name": "A", "keyword_demand_score": 0.70, "validated_keywords": ["k"]},
        {"solution_name": "C", "keyword_demand_score": 0.98, "validated_keywords": []},
    ]
    p = ac.demand_panel(_ckpt(tmp_path, stage6=st6))
    assert "FALLBACK" in p["demand_source"] and "STALE" in p["demand_source"]
    assert p["demand_measured_n"] == 1
    assert p["demand_unmeasured_n"] == 1
    assert p["demand_max"] == pytest.approx(0.70)


def test_single_measured_row_leaves_spread_unassessed(tmp_path):
    sel = [{"solution_name": "A", "keyword_demand_score": 0.7, "demand_unmeasured": False}]
    p = ac.demand_panel(_ckpt(tmp_path, selection=sel))
    assert "demand_spread" not in p
    assert ac._gate(p.get("demand_spread"), lambda v: v >= 0.06,
                    p.get("demand_measured_n", 0) >= 2) == ac.UNASSESSED


# =========================================================== 2. cap attribution
def test_parity_pin_attributed_to_the_parity_rule():
    vis = [_idea("A", market_fit_score=0.45, market_fit_score_raw=0.85,
                 incumbent_parity="shipped by VetSnap: does the same thing")]
    p = ac.cap_panel(vis, CAPS)
    assert p["cap_detail"][0]["class"] == "pinned@cap"
    assert p["cap_detail"][0]["rules"] == ["(e) parity:shipped"]
    assert p["cap_pin_share_attributed"] == 1.0


def test_coincidental_equality_is_not_a_pin():
    """Same 0.45 final, no parity finding, nothing else eligible -> not attributable."""
    vis = [_idea("A", market_fit_score=0.45, incumbent_parity="none found")]
    p = ac.cap_panel(vis, CAPS)
    assert p["cap_detail"][0]["class"] == "no-eligible-cap"
    assert p["cap_pin_share_attributed"] == 0.0


def test_shared_040_value_split_between_rule_b_and_bundled_free():
    """0.40 is both rule-(b) unverified-data and parity:bundled_free. Attribution must
    distinguish them instead of lumping every 0.40 into one bucket."""
    vis = [
        _idea("ruleB", market_fit_score=0.40, build_feasibility_score=0.3,
              incumbent_parity="none found"),
        _idea("bundled", market_fit_score=0.40,
              incumbent_parity="bundled_free (ezyVet)"),
    ]
    p = ac.cap_panel(vis, CAPS)
    rules = {d["name"]: d["rules"] for d in p["cap_detail"]}
    assert rules["ruleB"] == ["(b) unverified data/mechanism"]
    assert rules["bundled"] == ["(e) parity:bundled_free"]
    assert p["cap_rule_dist"] == {"(b) unverified data/mechanism": 1,
                                  "(e) parity:bundled_free": 1}
    assert p["mf_modal_share"] == 1.0  # the OLD metric can't tell these apart


def test_below_cap_is_not_pinned():
    """Parity cap 0.45 but the critic landed 0.40 -> the cap never bound."""
    vis = [_idea("A", market_fit_score=0.40,
                 incumbent_parity="shipped by VetSnap: same")]
    p = ac.cap_panel(vis, CAPS)
    assert p["cap_detail"][0]["class"] == "below-cap (not binding)"


def test_raw_at_or_below_cap_is_unconfirmed_not_pinned():
    """raw is the GENERATOR self-score, not the pre-cap value; it can only corroborate."""
    vis = [_idea("A", market_fit_score=0.45, market_fit_score_raw=0.45,
                 incumbent_parity="shipped by VetSnap: same")]
    p = ac.cap_panel(vis, CAPS)
    assert p["cap_detail"][0]["class"] == "at-cap-unconfirmed"
    assert p["cap_pin_share_attributed"] == 0.0


def test_weak_wallet_substitute_uses_the_weak_wallet_cap():
    vis = [_idea("A", market_fit_score=0.35, source_segment_payability=0.1,
                 incumbent_parity="substitute (spreadsheet)")]
    elig = ac.eligible_caps(vis[0], CAPS)
    assert elig["(e) parity:substitute/weak-wallet"] == CAPS["parity_substitute_weak_wallet"]
    assert "(d) low payability" in elig


def test_disabled_cap_never_attributes():
    caps = dict(CAPS, selfissued_trust=0.0)
    idea = _idea("A", value_proposition="issue a verified badge", market_fit_score=0.0)
    assert "(f) self-issued trust" not in ac.eligible_caps(idea, caps)


def test_modal_share_and_attributed_share_can_disagree():
    """The headline the old script printed vs. the one that is actually attributable."""
    vis = [
        _idea("pinned", market_fit_score=0.45, market_fit_score_raw=0.9,
              incumbent_parity="shipped by VetSnap: same"),
        _idea("coincidence", market_fit_score=0.45, incumbent_parity="none found"),
    ]
    p = ac.cap_panel(vis, CAPS)
    assert p["mf_modal_share"] == 1.0
    assert p["cap_pin_share_attributed"] == 0.5


# =========================================================== 3. provenance flag
_PAINS = [{"title": "Clinics discover medication stockouts only when items are needed"},
          {"title": "PIMS migration corrupts medication prices and inventory counts"}]


def test_presence_metric_counts_a_mismatched_pain_as_covered():
    """The documented RxNormPIMSMismatch case: presence says 100%, binding is wrong."""
    ideas = [_idea("RxNormPIMSMismatch",
                   source_pain=_PAINS[0]["title"],
                   value_proposition=("Prevent veterinary PIMS migrations and inventory audits "
                                      "from being undermined by inconsistent drug names, "
                                      "strengths, forms and packaging identities"))]
    p = ac.provenance_panel(ideas, _PAINS)
    assert p["source_pain_presence"] == 1.0          # presence: fully "covered"
    assert p["provenance_flag_n"] == 1               # flag: possible false provenance
    assert p["provenance_flags"][0][0] == "RxNormPIMSMismatch"
    assert p["provenance_flags"][0][1] < ac.PROVENANCE_FLAG_THRESHOLD


def test_well_bound_pain_is_not_flagged():
    ideas = [_idea("Mapper", source_pain=_PAINS[1]["title"],
                   value_proposition=("Prevent medication prices and inventory counts from being "
                                      "corrupted during a PIMS migration"))]
    p = ac.provenance_panel(ideas, _PAINS)
    assert p["provenance_flag_n"] == 0


def test_threshold_is_a_parameter_not_a_verdict():
    ideas = [_idea("Edge", source_pain="alpha beta gamma delta",
                   value_proposition="alpha beta only")]
    assert ac.provenance_panel(ideas, [], threshold=0.9)["provenance_flag_n"] == 1
    assert ac.provenance_panel(ideas, [], threshold=0.4)["provenance_flag_n"] == 0


def test_null_source_pain_is_absent_not_flagged():
    """A missing source_pain lowers PRESENCE; it must not silently become a provenance flag."""
    ideas = [_idea("NoPain", source_pain=None),
             _idea("HasPain", source_pain=_PAINS[1]["title"],
                   value_proposition="prices and inventory counts corrupted by PIMS migration")]
    p = ac.provenance_panel(ideas, _PAINS)
    assert p["source_pain_presence"] == 0.5
    assert p["provenance_scored_n"] == 1
    assert p["provenance_flag_n"] == 0


def test_frame_born_ideas_are_out_of_scope_for_presence():
    ideas = [_idea("Frame", source_frame="data_asset", source_pain=None),
             _idea("Cell", source_pain=_PAINS[0]["title"], value_proposition="stockouts")]
    p = ac.provenance_panel(ideas, _PAINS)
    assert p["n_pain_cell_ideas"] == 1
    assert p["source_pain_presence"] == 1.0


def test_source_pain_not_matching_any_stage3_title_is_reported():
    ideas = [_idea("Drift", source_pain="a pain nobody extracted", value_proposition="x")]
    p = ac.provenance_panel(ideas, _PAINS)
    assert p["source_pain_unmatched_n"] == 1


# =========================================================== amplification / vendors
def test_unnamed_vendor_stamp_does_not_become_a_vendor():
    """'shipped by evidence:' names no product; the old '?' bucket could win the max."""
    vis = [_idea("A", incumbent_parity="shipped by evidence: the search results show incumbents"),
           _idea("B", incumbent_parity="shipped by evidence: same"),
           _idea("C", incumbent_parity="shipped by evidence: same"),
           _idea("D", incumbent_parity="shipped by VetSnap: same")]
    p = ac.parity_panel(vis)
    assert p["parity_vendors"] == {"VetSnap": 1}
    assert p["parity_unattributed_n"] == 3
    assert p["amplification"] == pytest.approx(0.25)


def test_partial_by_vendor_is_attributed():
    vis = [_idea("A", incumbent_parity="partial by ezyVet: dashboard covers part of it")]
    assert ac.parity_panel(vis)["parity_vendors"] == {"ezyVet": 1}


def test_none_found_is_not_a_parity_class():
    vis = [_idea("A", incumbent_parity="none found")]
    p = ac.parity_panel(vis)
    assert p["parity_classes"] == {} and p["amplification"] == 0.0


# =========================================================== gate states
@pytest.mark.parametrize("value,guard,expected", [
    (0.20, None, ac.PASS),
    (0.80, None, ac.FAIL),
    (None, None, ac.UNASSESSED),
    (0.80, False, ac.UNASSESSED),
])
def test_gate_states(value, guard, expected):
    assert ac._gate(value, lambda v: v <= 0.35, guard) == expected
