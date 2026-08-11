"""Per-clause drift detector for "Check my idea" seeds (quality pass Q4).

The load-bearing case is the LIVE one: the 056b2c68 seed kept the pitch's audience and
delivery but repositioned the mechanism, arguing AGAINST the pitch with the pitch's own
vocabulary ("… rather than a draft", "avoiding … generic AI-drafting"). A bare
shared-token check passes all clauses there; the detector must fire on mechanism only.
"""

from types import SimpleNamespace

from nicheiq.utils.seed_fidelity import seed_clause_drift

from ..report.fixture_056b2c68 import state_from_fixture

TERMS = {
    "mechanism": ["drafts", "replies"],
    "audience": ["community managers", "small SaaS companies"],
    "problem": ["repetitive questions"],
    "delivery": ["chrome extension"],
}


def _candidate(**kw):
    base = dict(
        solution_name="ReplyBot", description="", value_proposition="",
        target_personas=[], mechanism_tag="", why_it_works="",
        innovation_angle="", technical_approach="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_live_seed_fires_on_mechanism_only():
    state = state_from_fixture()
    seed = next(i for i in state.idea_generation.solution_ideas
                if getattr(i, "source_frame", None) == "user_seed"
                and getattr(i, "generation_operation_id", None) == "validate")
    assert seed_clause_drift(state.user_idea_identity_terms, seed,
                             state.user_idea_inferred_fields) == ["mechanism"]


def test_faithful_seed_no_drift():
    cand = _candidate(
        description="A Chrome extension that drafts Reddit replies automatically.",
        value_proposition="Drafts replies to repetitive questions for community "
                          "managers at small SaaS companies.",
        target_personas=["Small SaaS community manager"])
    assert seed_clause_drift(TERMS, cand) == []


def test_cross_niche_seed_fires_all_stated_clauses():
    # Vet-clinic pitch terms vs a coffee-market idea: zero presence on every clause.
    cand = _candidate(
        description="A green-lot marketplace dashboard for specialty coffee roasters.",
        value_proposition="Roasters see live lot availability and price history.",
        target_personas=["Specialty coffee roaster"])
    terms = {"mechanism": ["vaccination reminders"], "audience": ["veterinary clinics"],
             "problem": ["missed appointments"], "delivery": ["sms service"]}
    assert seed_clause_drift(terms, cand) == [
        "mechanism", "audience", "problem", "delivery"]


def test_repudiated_only_term_fires_clause():
    cand = _candidate(
        description="An approval ledger for community managers of small SaaS "
                    "companies, as a Chrome extension for repetitive questions.",
        technical_approach="It generates an escalation request rather than a draft, "
                          "and never posts a reply on its own.")
    # 'drafts' appears only behind a mid-sentence contrast cue -> mechanism drifted.
    assert seed_clause_drift(TERMS, cand) == ["mechanism"]


def test_sentence_initial_cue_spares_the_asserted_half():
    cand = _candidate(
        description="Rather than making you type each answer, ReplyBot drafts the "
                    "reply for you. Community managers at small SaaS companies "
                    "install it as a Chrome extension for repetitive questions.")
    assert seed_clause_drift(TERMS, cand) == []


def test_inferred_and_termless_clauses_are_skipped():
    cand = _candidate(description="Something entirely unrelated to the pitch.")
    terms = {"mechanism": [], "audience": ["veterinary clinics"],
             "problem": [], "delivery": []}
    # audience is inferred -> skipped; every other clause has no terms -> skipped.
    assert seed_clause_drift(terms, cand, inferred_fields=["audience"]) == []
    assert seed_clause_drift(None, cand) == []
