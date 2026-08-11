"""Stated-clause preservation for "Check my idea" seeds.

The evaluated project must BE the pitched product — a Chrome-extension pitch yields a
Chrome-extension project. Three layers under test: the generation-lens constraint block,
the post-birth enforcement gate, and the one-shot corrective rewrite.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews.unified_solution_crew import (
    UnifiedSolutionCrew,
    _stated_clause_lens_block,
)

TERMS = {
    "mechanism": ["drafts Reddit replies"],
    "audience": ["community managers", "small SaaS companies"],
    "problem": [],
    "delivery": ["Chrome extension"],
}


# ── lens constraint block ──

def test_lens_block_empty_without_terms():
    assert _stated_clause_lens_block(None) == ""
    assert _stated_clause_lens_block({}) == ""
    assert _stated_clause_lens_block({"mechanism": [], "audience": []}) == ""


def test_lens_block_lists_stated_clauses_only():
    block = _stated_clause_lens_block(TERMS)
    assert "STATED-IDENTITY CONSTRAINTS" in block
    assert "drafts Reddit replies" in block
    assert "Chrome extension" in block
    assert "community managers; small SaaS companies" in block
    assert "problem" not in block.split("Every variant")[0].lower().replace(
        "the pain it removes", "")  # empty clause emits no line
    assert "stays a Chrome extension" in block


# ── enforcement gate ──

def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    return crew


def _idea(**kw):
    base = dict(
        solution_name="ReplyBot",
        description="A Chrome extension that drafts Reddit replies automatically.",
        value_proposition="Drafts replies for community managers at small SaaS companies.",
        target_personas=["Small SaaS community manager"],
        core_features=[], why_it_works="", innovation_angle="",
        technical_approach="", mechanism_tag="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_faithful_winner_triggers_no_rewrite():
    crew = _crew()
    with patch.object(UnifiedSolutionCrew, "_restore_seed_clauses") as restore:
        crew._enforce_seed_identity(_idea(), TERMS, [])
    restore.assert_not_called()


def test_drifted_winner_gets_one_corrective_rewrite():
    crew = _crew()
    drifted_idea = _idea(
        description="An approved-answer retrieval desk for community managers at "
                    "small SaaS companies, shipped as a Chrome extension.",
        value_proposition="Retrieval instead of another AI reply writer.",
        technical_approach="Generates an escalation request rather than a draft.")

    calls = {}

    def fake_restore(self, idea, terms, drifted):
        calls["drifted"] = list(drifted)
        # Simulate a successful restore: put the stated mechanism back cleanly.
        idea.description = ("A Chrome extension that drafts Reddit replies with an "
                            "approval step, for community managers.")
        idea.value_proposition = "Drafts replies you approve before posting."
        idea.technical_approach = "Drafts a reply from approved answers."
        return True

    with patch.object(UnifiedSolutionCrew, "_restore_seed_clauses", fake_restore):
        crew._enforce_seed_identity(drifted_idea, TERMS, [])

    assert calls["drifted"] == ["mechanism"]
    assert "drafts Reddit replies" in drifted_idea.description


def test_restore_failure_is_fail_soft():
    crew = _crew()
    drifted_idea = _idea(
        solution_name="AnswerDesk",
        description="A retrieval desk for community managers of small SaaS companies, "
                    "as a Chrome extension.",
        value_proposition="Retrieval, not another reply writer.",
        technical_approach="Escalation rather than a draft.")
    with patch.object(UnifiedSolutionCrew, "_restore_seed_clauses",
                      return_value=False):
        crew._enforce_seed_identity(drifted_idea, TERMS, [])  # must not raise
    assert drifted_idea.solution_name == "AnswerDesk"  # untouched on failure


def test_residual_drift_rolls_back_corrective_rewrite():
    crew = _crew()
    drifted_idea = _idea(
        solution_name="AnswerDesk",
        description="A retrieval desk for community managers as a Chrome extension.",
        value_proposition="Retrieval rather than a reply writer.",
        technical_approach="Escalation instead of a draft.",
    )
    original = vars(drifted_idea).copy()

    def incomplete_restore(self, idea, terms, drifted):
        idea.solution_name = "EscalationDesk"
        idea.description = "A Chrome extension that routes repetitive questions to people."
        idea.value_proposition = "Escalate questions instead of drafting replies."
        idea.technical_approach = "Never draft a reply."
        return True

    with patch.object(UnifiedSolutionCrew, "_restore_seed_clauses", incomplete_restore):
        crew._enforce_seed_identity(drifted_idea, TERMS, [])

    assert vars(drifted_idea) == original


# ── corrective rewrite ──

def test_restore_applies_fields_in_place():
    crew = _crew()
    idea = _idea(solution_name="AnswerDesk")
    restored = SimpleNamespace(model_dump=lambda: {
        "solution_name": "ReplyDraft Assistant",
        "value_proposition": "Drafts Reddit replies you approve before posting.",
        "description": "A Chrome extension that drafts Reddit replies for community "
                       "managers at small SaaS companies.",
        "core_features": ["one-click draft", "approval step", ""],
        "why_it_works": "Keeps the human in the loop.",
        "innovation_angle": "Draft-first with policy safeguards.",
        "technical_approach": "Drafts from approved answers; flags low confidence.",
        "mechanism_tag": "reply-drafting-with-approval",
    })
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(restored, None)):
        ok = crew._restore_seed_clauses(idea, TERMS, ["mechanism"])

    assert ok is True
    assert idea.solution_name == "ReplyDraft Assistant"
    assert idea.core_features == ["one-click draft", "approval step"]
    assert idea.mechanism_tag == "reply-drafting-with-approval"


def test_restore_rejects_empty_core_copy():
    crew = _crew()
    idea = _idea(solution_name="AnswerDesk")
    hollow = SimpleNamespace(model_dump=lambda: {
        "solution_name": "X", "value_proposition": "", "description": "",
        "core_features": [], "why_it_works": "", "innovation_angle": "",
        "technical_approach": "", "mechanism_tag": "",
    })
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(hollow, None)):
        ok = crew._restore_seed_clauses(idea, TERMS, ["mechanism"])
    assert ok is False
    assert idea.solution_name == "AnswerDesk"


# ── brief-parity probe query construction ──

def test_brief_probe_runs_three_query_angles_including_listicle():
    """Run-to-run noise fix: the 'best … tools' roundup query is the discovery
    workhorse (the run that found the crowded category found it via a listicle;
    the plain two-query form missed it on the same pitch)."""
    crew = _crew()
    seen: list[str] = []

    class _Search:
        def run(self, search_query):
            seen.append(search_query)
            return "SERP: 8 Reddit reply automation tools tested, including Okara"

    crew.search_tool = _Search()
    crew.niche_context = SimpleNamespace(
        niche_description="Community-management tooling for B2B SaaS teams")
    finding = SimpleNamespace(
        parity="shipped", covered_by="Okara", evidence="reply automation agents")
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(finding, None)):
        note, calls = crew._probe_seed_brief_parity(
            SimpleNamespace(solution_name="X"), ["drafts Reddit replies"])

    assert calls == 3 and len(seen) == 3
    assert seen[0] == "drafts Reddit replies tool"
    assert seen[1] == "best drafts Reddit replies tools"
    assert "software" in seen[2]
    assert note == "shipped by Okara: reply automation agents"


def test_brief_probe_fail_soft_when_every_search_raises():
    crew = _crew()

    class _Broken:
        def run(self, search_query):
            raise RuntimeError("serper down")

    crew.search_tool = _Broken()
    crew.niche_context = SimpleNamespace(niche_description="market")
    note, calls = crew._probe_seed_brief_parity(
        SimpleNamespace(solution_name="X"), ["drafts replies"])
    assert note is None and calls == 3


def test_brief_probe_writer_stores_evidence_verbatim():
    """Post-audit revision: the writer stores the evidence sentence verbatim (echo
    kept); display humanizes (block-side _display_parity)."""
    crew = _crew()

    class _Search:
        def run(self, search_query):
            return "SERP result"

    crew.search_tool = _Search()
    crew.niche_context = SimpleNamespace(niche_description="market")
    finding = SimpleNamespace(
        parity="shipped", covered_by="Okara",
        evidence="Okara ships reply automation agents")
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(finding, None)):
        note, _calls = crew._probe_seed_brief_parity(
            SimpleNamespace(solution_name="X"), ["drafts Reddit replies"])
    assert note == "shipped by Okara: Okara ships reply automation agents"
