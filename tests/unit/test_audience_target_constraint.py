"""Codex-review fix (2026-07-02): the audience-mapping crew never received the user's stated
target audience, so the LLM's WTP-driven primary pick drifted ("small dev teams" → "Solo SaaS
Developers"). The crew now carries user_target_audience into the prompt with a containment rule."""

from types import SimpleNamespace


def test_constructor_stores_and_strips():
    from nicheiq.crews.audience_mapping_crew import AudienceMappingCrew
    crew = AudienceMappingCrew(niche_description="n", user_target_audience="  small dev teams ")
    assert crew.user_target_audience == "small dev teams"
    crew2 = AudienceMappingCrew(niche_description="n")
    assert crew2.user_target_audience == ""


def test_yaml_carries_variable_and_containment_rule():
    import yaml
    cfg = yaml.safe_load(open("src/nicheiq/crews/config/audience_mapping_tasks.yaml"))
    text = str(cfg)
    assert "{user_target_audience}" in text
    assert "MUST be a segment WITHIN this audience" in text


def test_inputs_default_when_absent():
    # the template variable must always render (CrewAI KeyErrors on missing vars) —
    # verify the default sentinel exists in the inputs-assembly source
    import inspect

    from nicheiq.crews.audience_mapping_crew import AudienceMappingCrew
    src = inspect.getsource(AudienceMappingCrew.analyze)
    assert '"user_target_audience"' in src
    assert "Not specified" in src
