"""Prompt-fidelity tests for the red-team pass (utils/red_team_review.py).

These assert a PROPERTY — "the whole model-authored field reaches the prompt", "every
query's evidence reaches the reviser", "a truncation that does happen is visible" — never
a particular limit or wording, so tightening the prompt prose cannot make them lie and a
re-introduced constant slice cannot make them pass.

Real `BaseSolutionIdea` instances throughout, deliberately: a MagicMock idea absorbs any
field name and has produced false greens here before.

Motivation (measured over 3,626 checkpoint JSONs, distinct values): `technical_approach`
has a median length of 522 chars, so the old `[:220]` kill-prompt slice discarded the tail
of 93.9% of real values — mid-word, unmarked — while the same prompt asked the attacker
whether the mechanism handles the MODAL case of the pain. That prompt's verdict is what
kills an idea.
"""

from types import SimpleNamespace

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.solution_idea import BaseSolutionIdea, RedTeamFinding
from nicheiq.utils import llm_service
from nicheiq.utils.red_team_review import (
    _RedTeamVerdict,
    _attempt_red_team_revision,
    run_red_team_review,
)

# Long enough to have been cut by the old kill-prompt slice, and short enough to sit well
# under the runaway backstop (so a pass proves the slice is gone, not that the backstop is
# generous). The tail sentinel is what a mid-word cut would have removed.
LONG_MECHANISM = (
    "Ingests the operator's existing dispatch exports over SFTP, normalizes each carrier's "
    "line-item vocabulary against a shared ledger schema, and reconciles accessorial "
    "charges against the rate confirmation on file. "
    + "It then diffs each reconciled line against the prior closed period and flags any "
      "retroactive edit for review by the controller. " * 4
    + "MODAL CASE TAIL SENTINEL: the common form of this pain is a single-truck operator "
      "with one broker portal, which this mechanism handles without any integration work."
)
LONG_VALUE_PROP = (
    "Gives small freight operators a defensible record of what changed after a period "
    "closed, so a broker's retroactive deduction can be contested with evidence. "
    + "The operator sees the before/after of every line without opening a spreadsheet. " * 3
    + "VALUE PROP TAIL SENTINEL."
)


def _idea(**kw) -> BaseSolutionIdea:
    """A REAL BaseSolutionIdea (never MagicMock — see module docstring)."""
    base = dict(
        solution_name="Closed Period Diff",
        description="Change monitoring for closed accounting periods",
        value_proposition=LONG_VALUE_PROP,
        technical_approach=LONG_MECHANISM,
        pain_points_addressed=["retroactive broker deductions"],
        core_features=["period diff"],
        target_personas=["single-truck operator"],
        mechanism_tag="period-diff",
        candidate_status="active",
        market_fit_score=0.8,
        technical_feasibility_score=0.6,
        build_feasibility_score=0.8,
    )
    base.update(kw)
    return BaseSolutionIdea(**base)


def _crew(search_map):
    """Plain stub, no MagicMock: the real keyword derivation, a canned search batch."""
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.niche_context = SimpleNamespace(niche_description="freight brokerage back office")
    crew.funnel_counts = {}
    crew._ma_search_batch = lambda queries, **kw: dict(search_map)
    crew._score_wave = lambda wave, **kw: None
    crew._mechanism_keywords = UnifiedSolutionCrew._mechanism_keywords
    return crew


def _refined(ideas):
    return SimpleNamespace(solution_ideas=ideas)


def _capture(monkeypatch, verdict):
    """Patch the LLM boundary and collect every prompt it is handed.

    The revision call is answered with an empty instance of the caller's OWN
    `output_model`, so the revision is rejected on its blank name and the test stays
    focused on what the prompt carried.
    """
    prompts: list[str] = []

    def _invoke(**kw):
        prompt = kw.get("prompt", "")
        prompts.append(prompt)
        if "ESCAPE" in prompt:  # the revision ideator prompt
            return kw["output_model"](), SimpleNamespace(to_dict=lambda: {})
        return verdict, SimpleNamespace(to_dict=lambda: {})

    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_invoke))
    return prompts


def _kill_prompt(prompts) -> str:
    hits = [p for p in prompts if "You are trying to KILL this idea" in p]
    assert len(hits) == 1, f"expected exactly one kill prompt, got {len(hits)}"
    return hits[0]


def _revision_prompt(prompts) -> str:
    hits = [p for p in prompts if "ESCAPE" in p]
    assert len(hits) == 1, f"expected exactly one revision prompt, got {len(hits)}"
    return hits[0]


@pytest.fixture
def red_team_settings(monkeypatch):
    monkeypatch.setattr(settings, "red_team_top_k", 1)
    monkeypatch.setattr(settings, "red_team_searches_per_idea", 6)


class TestKillPromptCarriesWholeFields:
    def test_full_technical_approach_and_value_prop_reach_the_kill_prompt(
            self, monkeypatch, red_team_settings):
        """The prompt that asks about the MODAL case must contain the whole mechanism."""
        prompts = _capture(monkeypatch, _RedTeamVerdict(verdict="survives"))
        idea = _idea()
        assert len(idea.technical_approach) > 600  # the regime the old [:220] cut

        run_red_team_review(_crew({"period diff freight": "a search result"}),
                            _refined([idea]))

        prompt = _kill_prompt(prompts)
        assert idea.technical_approach in prompt
        assert idea.value_proposition in prompt

    def test_backstop_truncation_is_visibly_marked(self, monkeypatch, red_team_settings):
        """A cut that DOES happen must announce itself, so the attacker can tell
        'the mechanism does not cover this' from 'the sentence saying so was cut'."""
        runaway = "reconciles a ledger line and re-checks it. " * 400
        prompts = _capture(monkeypatch, _RedTeamVerdict(verdict="survives"))
        idea = _idea(technical_approach=runaway)
        assert len(runaway) > 4000  # well past the runaway backstop

        run_red_team_review(_crew({"period diff freight": "a search result"}),
                            _refined([idea]))

        prompt = _kill_prompt(prompts)
        assert "…[truncated]" in prompt
        # And the backstop is a backstop, not a tight leash: an order of magnitude more
        # survives than any per-field character slice this prompt has ever carried.
        assert prompt.count("re-checks it.") > 20


class TestRevisionPromptCarriesWholeFields:
    def test_full_mechanism_reaches_the_revision_prompt(self, monkeypatch):
        """The reviser is asked to fix the mechanism, so it must see all of it."""
        prompts = _capture(monkeypatch, _RedTeamVerdict(verdict="survives"))
        idea = _idea()
        result = _RedTeamVerdict(
            verdict="killed",
            findings=[RedTeamFinding(kind="verified_modal_failure",
                                     claim="mechanism misses the modal case")])

        accepted = _attempt_red_team_revision(
            _crew({}), _refined([idea]), idea, result, "some evidence")

        assert accepted is False  # blank revision name -> rejected, as designed
        prompt = _revision_prompt(prompts)
        assert idea.technical_approach in prompt
        assert idea.value_proposition in prompt

    def test_every_query_evidence_reaches_the_revision_prompt(
            self, monkeypatch, red_team_settings):
        """The reviser must escape findings drawn from ALL the evidence the killer saw.

        Each canned result sits under `_evidence_block`'s per-result bulk-scrape bound, so
        nothing here is legitimately droppable; only a re-cut of the JOINED block could
        lose the later queries.
        """
        sentinels = ["SENTINELALPHA", "SENTINELBRAVO", "SENTINELCHARLIE"]
        search_map = {
            f"query {i}": f"{s} " + ("broker portal deduction result text. " * 20)
            for i, s in enumerate(sentinels)
        }
        joined_len = sum(len(v) for v in search_map.values())
        assert joined_len > 1500  # the regime where a joined-block re-cut would bite

        prompts = _capture(monkeypatch, _RedTeamVerdict(
            verdict="killed",
            findings=[RedTeamFinding(kind="verified_free_or_bundled_alternative",
                                     claim="bundled in the broker portal")]))
        idea = _idea()

        run_red_team_review(_crew(search_map), _refined([idea]))

        prompt = _revision_prompt(prompts)
        for s in sentinels:
            assert s in prompt, f"{s} missing — later queries' evidence never reached the reviser"
