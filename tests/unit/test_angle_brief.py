"""build_angle_brief — the Stage-2 angle brief that front-loads each angle's kill-question."""

import pytest

from nicheiq.utils.angle_brief import build_angle_brief, _ANGLE_BRIEF


@pytest.mark.parametrize("angle", list(_ANGLE_BRIEF))
def test_each_angle_yields_a_brief_with_its_kill_question(angle):
    b = build_angle_brief({"winning_angle": angle})
    assert b["winning_angle"] == angle
    assert b["angle_primary_question"] == _ANGLE_BRIEF[angle]["kill"]
    assert b["angle_primary_question"] in b["angle_brief"]
    assert "ANSWER THIS FIRST" in b["angle_brief"]


def test_unset_angle_is_a_noop():
    for sol in ({"winning_angle": None}, {"winning_angle": "  "}, {}, {"winning_angle": "bogus"}):
        assert build_angle_brief(sol) == {"winning_angle": "", "angle_brief": "", "angle_primary_question": ""}


def test_includes_differentiation_locus_when_present():
    b = build_angle_brief({"winning_angle": "distribution_seo",
                           "differentiation_locus": "freshness of a community-scored slice"})
    assert "freshness of a community-scored slice" in b["angle_brief"]


def test_never_instructs_suppression_of_off_angle_critique():
    # The brief should ADD the kill-question, not tell the crew to ignore off-angle weakness.
    b = build_angle_brief({"winning_angle": "distribution_seo"})
    assert "suppress" not in b["angle_brief"].lower()
    assert "ignore" not in b["angle_brief"].lower()


def test_reads_model_attrs_not_just_dict():
    from types import SimpleNamespace
    b = build_angle_brief(SimpleNamespace(winning_angle="vertical_workflow", differentiation_locus="x"))
    assert b["winning_angle"] == "vertical_workflow"


def test_seo_crew_angle_vars_gated(monkeypatch):
    """The SEO crew's _angle_vars: empty (no-op) when the flag is off, real brief when on."""
    from types import SimpleNamespace
    import nicheiq.crews.seo_strategy_crew as sc
    from nicheiq.config.settings import settings
    crew = sc.SEOStrategyCrew.__new__(sc.SEOStrategyCrew)
    crew.selected_solution = SimpleNamespace(winning_angle="distribution_seo", differentiation_locus="x")

    monkeypatch.setattr(settings, "enable_angle_conditioned_research", False)
    assert crew._angle_vars() == {"winning_angle": "", "angle_brief": "", "angle_primary_question": ""}

    monkeypatch.setattr(settings, "enable_angle_conditioned_research", True)
    on = crew._angle_vars()
    assert on["winning_angle"] == "distribution_seo" and on["angle_brief"]
