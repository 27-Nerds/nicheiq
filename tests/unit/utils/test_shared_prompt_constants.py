"""One figure, one source.

The live 2026-08-03 report told the reader to "Conduct 10 structured interviews" in the
Brief and "Conduct 5" in the Plan: `report_next_steps.yaml` had no anchor so the model
invented a number, while the playbook copied its own hardcoded example. Pinning both to
the literal "5-10" fixed that instance and left the real hazard — one figure written twice
in two independently-edited files, with each file's prose asserting the other agreed.
"""

import re

import pytest

from nicheiq.utils.prompts import (
    INTERVIEW_COUNT_RANGE,
    SHARED_PROMPT_CONSTANTS,
    load_prompt,
    safe_format,
)

# Every template that states the interview count.
TEMPLATES_USING_INTERVIEW_COUNT = (
    "report_next_steps",
    "report_first_30_days_playbook",
)


def _render(name: str) -> str:
    """Render with every placeholder stubbed EXCEPT the shared constants."""
    template = load_prompt(name)
    keys = {k for k in re.findall(r"{([a-z][a-z0-9_]*)}", template)}
    stub = {k: "X" for k in keys - set(SHARED_PROMPT_CONSTANTS)}
    return safe_format(template, **stub)


@pytest.mark.parametrize("name", TEMPLATES_USING_INTERVIEW_COUNT)
def test_template_reads_the_constant_not_a_literal(name):
    template = load_prompt(name)
    assert "{interview_count_range}" in template
    # A stray literal would silently diverge the next time the constant changes.
    stripped = template.replace("{interview_count_range}", "")
    assert INTERVIEW_COUNT_RANGE not in stripped, (
        f"{name} still hardcodes {INTERVIEW_COUNT_RANGE!r} somewhere — use the placeholder"
    )


@pytest.mark.parametrize("name", TEMPLATES_USING_INTERVIEW_COUNT)
def test_constant_fills_without_the_caller_passing_it(name):
    """Call sites must not have to remember a cross-prompt figure — that is the bug."""
    rendered = _render(name)
    assert "{interview_count_range}" not in rendered
    assert INTERVIEW_COUNT_RANGE in rendered


def test_every_template_renders_the_same_value():
    counts = {name: _render(name).count(INTERVIEW_COUNT_RANGE)
              for name in TEMPLATES_USING_INTERVIEW_COUNT}
    assert all(n >= 1 for n in counts.values()), counts


def test_an_explicit_kwarg_still_wins():
    """A one-off override must not require editing the shared constant."""
    out = safe_format("interviews: {interview_count_range}", interview_count_range="3")
    assert out == "interviews: 3"


def test_changing_the_constant_changes_every_template():
    """The whole point: one edit, every prompt. Guards against a literal creeping back."""
    import nicheiq.utils.prompts as prompts

    original = prompts.SHARED_PROMPT_CONSTANTS["interview_count_range"]
    try:
        prompts.SHARED_PROMPT_CONSTANTS["interview_count_range"] = "7-9"
        for name in TEMPLATES_USING_INTERVIEW_COUNT:
            template = load_prompt(name)
            keys = {k for k in re.findall(r"{([a-z][a-z0-9_]*)}", template)}
            stub = {k: "X" for k in keys - set(prompts.SHARED_PROMPT_CONSTANTS)}
            assert "7-9" in safe_format(template, **stub), name
    finally:
        prompts.SHARED_PROMPT_CONSTANTS["interview_count_range"] = original
