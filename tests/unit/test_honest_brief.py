"""Honest brief (2026-07-02): evidence quotes + critic bear-case on idea cards."""

from types import SimpleNamespace

from nicheiq.utils.calibration_notes import extract_criterion_reason
from nicheiq.utils.honest_brief import build_quotes_by_pain, demand_quotes_for


def _pain(title, quotes):
    return SimpleNamespace(title=title, representative_quotes=quotes)


class TestQuoteLookup:
    def test_round_robin_across_pains(self):
        by_pain = build_quotes_by_pain([
            _pain("Pain A", ["a1", "a2", "a3"]),
            _pain("Pain B", ["b1"]),
        ])
        # one quote-rich pain must not crowd out the other
        assert demand_quotes_for(["Pain A", "Pain B"], by_pain) == ["a1", "b1", "a2"]

    def test_case_insensitive_title_match(self):
        by_pain = build_quotes_by_pain([_pain("Under-Pricing Goods", ["q"])])
        assert demand_quotes_for(["under-pricing goods"], by_pain) == ["q"]

    def test_unknown_pain_and_empty(self):
        assert demand_quotes_for(["nope"], {}) == []
        assert demand_quotes_for(None, {}) == []

    def test_long_quote_truncated_at_word_boundary(self):
        q = "word " * 60
        by_pain = build_quotes_by_pain([_pain("P", [q])])
        out = demand_quotes_for(["P"], by_pain)
        assert len(out[0]) <= 221 and out[0].endswith("…") and not out[0][:-1].endswith(" ")

    def test_dedupes_identical_quotes(self):
        by_pain = build_quotes_by_pain([_pain("A", ["same"]), _pain("B", ["same"])])
        assert demand_quotes_for(["A", "B"], by_pain) == ["same"]


class TestCriterionReason:
    def test_word_boundary_ellipsis(self):
        notes = "market_fit: " + "alpha beta " * 40
        r = extract_criterion_reason(notes, max_len=50)
        assert r.endswith("…") and len(r) <= 51 and not r[:-1].endswith(" ")

    def test_full_reason_kept_when_short(self):
        assert extract_criterion_reason("market_fit: crowded market") == "crowded market"


class TestAlternativeSolutionFields:
    def test_model_accepts_and_defaults(self):
        from nicheiq.models.research_state import AlternativeSolution
        base = dict(solution_name="X", summary="s", key_differentiator="k",
                    best_suited_for="b", pivot_trigger="p")
        alt = AlternativeSolution(**base)
        assert alt.demand_quotes is None and alt.critic_concern is None  # legacy-safe
        alt2 = AlternativeSolution(**base, demand_quotes=["q"], critic_concern="c")
        assert alt2.demand_quotes == ["q"] and alt2.critic_concern == "c"
