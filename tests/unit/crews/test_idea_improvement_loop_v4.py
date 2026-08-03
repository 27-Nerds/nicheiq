"""S3.3 mentor-axis redirect (docs/TOURNAMENT_MENTOR_REDIRECT_SPEC.md) — dedicated v4 loop tests.

Covers the seven shipped-together pieces: the IdeaCritiqueV4 schema (Literal binding_constraint +
on_anchor_pain + convergence meets_bar), the boolean-primary on-pain gate with the widened
_ONPAIN_SLACK_V4, the rewritten mentor prompt (CHOOSING block, self-scores-ignore restored,
nonprofit example contamination gone), the full _review echo, and the ideator novelty addendum.
All LLM calls are mocked.
"""
import pytest
from pydantic import ValidationError

from nicheiq.crews import idea_improvement_loop_v4 as v4
from nicheiq.crews.idea_improvement_loop import CellGrounding
from nicheiq.crews.idea_improvement_loop_v4 import (
    _ONPAIN_SLACK_V4,
    IdeaCritiqueV4,
    _ideator_system,
    _review,
    _reviewer_system,
    tournament_refine_cell_v4,
)
from nicheiq.models.solution_idea import BaseSolutionIdea


def _grounding() -> CellGrounding:
    return CellGrounding(
        niche="test niche", audience_segment="testers", segment_profile="",
        pain_title="Test pain", pain_evidence="  - representative quote",
    )


def _idea(name: str = "IdeaA") -> BaseSolutionIdea:
    return BaseSolutionIdea(
        solution_name=name,
        description="Users arrive, enter their data, and get a result. " * 2,
        value_proposition="Saves testers time.",
        pain_points_addressed=["Test pain"],
        core_features=["feature one"],
        target_personas=["tester"],
    )


def _crit(mf, nov=0.5, clarity=0.5, *, on_pain=True, binding="novelty",
          meets_bar=False, directive="sharpen the mechanism", rationale="grounded call"):
    return IdeaCritiqueV4(
        market_fit=mf, novelty=nov, clarity=clarity, on_anchor_pain=on_pain,
        binding_constraint=binding, directive=directive, meets_bar=meets_bar,
        rationale=rationale,
    )


def _mock_invoke(crits, ideas=()):
    """Dispatch on output_model: critiques for the reviewer, ideas for the ideator."""
    crits, ideas = list(crits), list(ideas)
    calls = {"review": 0, "improve": 0}

    def invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
        if output_model is IdeaCritiqueV4:
            calls["review"] += 1
            return crits.pop(0), None
        calls["improve"] += 1
        return ideas.pop(0), None

    return invoke, calls


class TestSchema:
    def test_validates_literal_binding_and_on_anchor_pain(self):
        for binding in ("market_fit", "novelty", "clarity", "seo_surface"):
            c = _crit(0.6, binding=binding, on_pain=False)
            assert c.binding_constraint == binding
            assert c.on_anchor_pain is False

    def test_rejects_off_vocab_binding_constraint(self):
        with pytest.raises(ValidationError):
            _crit(0.6, binding="data_feasibility")

    def test_on_anchor_pain_is_required(self):
        with pytest.raises(ValidationError):
            IdeaCritiqueV4(market_fit=0.5, novelty=0.5, clarity=0.5,
                           binding_constraint="novelty", directive="x", meets_bar=False)

    def test_slack_is_local_and_widened_without_touching_v3(self):
        from nicheiq.crews.idea_improvement_loop import _ONPAIN_SLACK
        assert _ONPAIN_SLACK_V4 == 0.10
        assert _ONPAIN_SLACK == 0.05  # v3 module untouched


class TestMentorPrompt:
    def test_choosing_block_present(self):
        content = _reviewer_system(_grounding())["content"]
        assert "CHOOSING binding_constraint" in content
        assert "FIXED INPUTS" in content
        assert "re-aim the EXISTING mechanism" in content

    def test_self_scores_ignore_restored(self):
        content = _reviewer_system(_grounding())["content"]
        assert "Ignore the idea's own SELF-SCORES" in content

    def test_nonprofit_example_contamination_gone(self):
        content = _reviewer_system(_grounding())["content"]
        assert "nonprofit" not in content.lower()
        assert "duplicate-grant" not in content
        # the un-schematized flag emission is gone; the modal-case rule itself remains
        assert "NEEDS-VERIFY: modal-case" not in content
        assert "modal case" in content

    def test_novelty_mechanism_delta_rule(self):
        content = _reviewer_system(_grounding())["content"]
        assert "mechanism change that earns" in content
        assert "relabeling" in content

    def test_meets_bar_is_convergence(self):
        content = _reviewer_system(_grounding())["content"]
        assert "CONVERGENCE" in content
        assert "would NOT materially improve" in content

    def test_needs_verify_priced_as_cost(self):
        content = _reviewer_system(_grounding())["content"]
        assert "COST the novelty gain must justify" in content

    def test_ideator_novelty_addendum(self):
        content = _ideator_system(_grounding())["content"]
        assert "change what the product DOES" in content
        assert "is not a revision" in content


class TestReviewEcho:
    def test_echo_retains_anchor_binding_directive_and_rationale(self):
        crit = _crit(0.6, binding="novelty", directive="do the thing",
                     rationale="because reasons")
        invoke, _ = _mock_invoke([crit])
        thread = [_reviewer_system(_grounding())]
        _review(_idea(), thread, invoke=invoke, model="m", effort=None)
        echo = thread[-1]
        assert echo["role"] == "assistant"
        assert "on_anchor_pain=True" in echo["content"]
        assert "binding=novelty" in echo["content"]
        assert "directive=do the thing" in echo["content"]
        assert "rationale=because reasons" in echo["content"]


class TestLoopGate:
    @pytest.fixture(autouse=True)
    def _no_verify(self, monkeypatch):
        self.verified = []
        monkeypatch.setattr(v4, "verify_data_routes",
                            lambda idea, g, **kw: self.verified.append(idea))

    def test_off_anchor_revision_rejected_despite_higher_score(self):
        # r1 scores strictly higher on every axis AND passes the numeric mf slack —
        # only on_anchor_pain=False rejects it, proving the boolean is primary.
        crits = [_crit(0.6, nov=0.4, clarity=0.5),                      # comp 0.515
                 _crit(0.9, nov=0.9, clarity=0.9, on_pain=False)]       # comp 0.900
        invoke, calls = _mock_invoke(crits, [_idea("IdeaB")])
        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=2, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaA"
        assert calls == {"review": 2, "improve": 1}
        assert self.verified == [best]

    def test_mf_dip_within_widened_slack_keeps_on_anchor_revision(self):
        # mf 0.60 -> 0.52: a 0.08 dip (over the old 0.05, under the new 0.10) with
        # on_anchor_pain=True keeps the higher-composite revision.
        crits = [_crit(0.6, nov=0.4, clarity=0.5),                      # comp 0.515
                 _crit(0.52, nov=0.8, clarity=0.8)]                     # comp 0.674 < bar
        invoke, calls = _mock_invoke(crits, [_idea("IdeaB")])
        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=2, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaB"
        assert calls == {"review": 2, "improve": 1}

    def test_mf_dip_beyond_slack_rejected_even_on_anchor(self):
        crits = [_crit(0.6, nov=0.4, clarity=0.5),                      # comp 0.515
                 _crit(0.45, nov=0.9, clarity=0.9)]                     # dip 0.15 > 0.10
        invoke, _ = _mock_invoke(crits, [_idea("IdeaB")])
        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=2, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaA"

    def test_meets_bar_early_exits_without_improving(self):
        # composite 0.515 is below _QUALITY_BAR — the exit is purely the convergence flag.
        crits = [_crit(0.6, nov=0.4, clarity=0.5, meets_bar=True)]
        invoke, calls = _mock_invoke(crits)
        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=2, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaA"
        assert calls == {"review": 1, "improve": 0}


class TestBindingConstraintStamp:
    """S4.2: the winner carries the judge's DIRECTIVE (the bear case). The criterion token
    itself (`binding_constraint`) is internal and stays out of the user-facing string —
    live audit 2026-08 saw "novelty: The peer-benchmarking core…" rendered verbatim."""

    @pytest.fixture(autouse=True)
    def _no_verify(self, monkeypatch):
        monkeypatch.setattr(v4, "verify_data_routes", lambda idea, g, **kw: None)

    def test_stamp_is_the_round2_critique_on_meets_bar_exit(self):
        # r2 is on-pain, scores higher AND converges — the stamp must be r2's critique.
        crits = [_crit(0.6, nov=0.4, clarity=0.5, binding="novelty",
                       directive="round one fix"),
                 _crit(0.7, nov=0.8, clarity=0.8, binding="clarity", meets_bar=True,
                       directive="round two fix")]
        invoke, calls = _mock_invoke(crits, [_idea("IdeaB")])
        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=3, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaB"
        assert calls == {"review": 2, "improve": 1}
        assert best.refine_binding_constraint == "round two fix"

    def test_stamp_follows_the_winner_not_the_last_critique(self):
        # r2 is rejected by on_anchor_pain, so `best` stays r1 — and so must the stamp.
        crits = [_crit(0.6, nov=0.4, clarity=0.5, binding="novelty",
                       directive="round one fix"),
                 _crit(0.9, nov=0.9, clarity=0.9, on_pain=False, binding="market_fit",
                       directive="round two fix")]
        invoke, _ = _mock_invoke(crits, [_idea("IdeaB")])
        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=2, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaA"
        assert best.refine_binding_constraint == "round one fix"
        assert "round two fix" not in best.refine_binding_constraint

    def _stamp(self, directive):
        invoke, _ = _mock_invoke([_crit(0.6, nov=0.4, clarity=0.5, meets_bar=True,
                                        binding="novelty", directive=directive)])
        return tournament_refine_cell_v4(
            [_idea("IdeaA")], _grounding(), rounds=1, invoke=invoke,
            ideator_model="m", reviewer_model="m").refine_binding_constraint

    def test_stamp_never_carries_the_internal_criterion_key(self):
        stamp = self._stamp("The comparison logic is generic.")
        assert not stamp.startswith("novelty")
        assert stamp == "The comparison logic is generic."

    def test_the_live_defect_directive_now_survives_whole(self):
        # The live defect: a 200-char hard slice ended "...instead of generic anomaly" —
        # mid-clause, no ellipsis. The whole directive is 368 chars and now fits.
        directive = (
            "The peer-benchmarking core is solid but the comparison logic is generic — "
            "flag unusually high deductions is what any outlier detector does. "
            "Sharpen the mechanism: instead of generic anomaly scoring, rank each line "
            "against the filing history of the same payer so the buyer sees why it moved. "
            "Otherwise the product is an alerting toy that any spreadsheet already covers.")
        assert self._stamp(directive) == directive

    def test_over_budget_directive_is_cut_on_a_sentence_boundary(self):
        directive = ("First sentence that carries the whole concern and most of the budget "
                     "because the judge wrote a long one about the mechanism being generic "
                     "and the comparison logic adding nothing a spreadsheet cannot already "
                     "do for this buyer in this niche today, at length. " + "tail " * 40)
        stamp = self._stamp(directive)
        assert len(stamp) <= 400
        assert stamp.endswith(".")           # a complete thought, not a severed clause
        assert directive.startswith(stamp)   # a prefix — nothing was rewritten

    def test_unbroken_run_still_gets_an_ellipsis_and_no_dangling_word(self):
        stamp = self._stamp("word " * 200)
        assert stamp.endswith("…") and len(stamp) <= 401
        assert not stamp[:-1].rstrip().endswith(" the")

    def test_markdown_emphasis_is_stripped(self):
        assert self._stamp("The logic is *structurally* generic and `market_fit` suffers.") == (
            "The logic is structurally generic and market_fit suffers.")

    def test_no_stamp_when_the_review_never_returned_a_critique(self):
        def invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
            raise RuntimeError("reviewer down")

        best = tournament_refine_cell_v4([_idea("IdeaA")], _grounding(),
                                         rounds=2, invoke=invoke,
                                         ideator_model="m", reviewer_model="m")
        assert best.solution_name == "IdeaA"
        assert best.refine_binding_constraint is None
