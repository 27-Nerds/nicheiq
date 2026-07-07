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
        assert alt.adjacent_market_parity is None
        alt2 = AlternativeSolution(**base, demand_quotes=["q"], critic_concern="c",
                                   adjacent_market_parity="HigherGov (govcon intel): feeds")
        assert alt2.demand_quotes == ["q"] and alt2.critic_concern == "c"
        assert alt2.adjacent_market_parity == "HigherGov (govcon intel): feeds"


class TestScoreMentionSanitizer:
    """critic_concern is user-facing — the critic's raw 0-1 decimals become band words."""

    def test_decimals_become_band_words(self):
        from nicheiq.utils.calibration_notes import humanize_score_mentions
        assert humanize_score_mentions(
            "Addresses a validated 0.60-severity pain with a novel mechanism (0.45)"
        ) == "Addresses a validated moderate-severity pain with a novel mechanism (limited)"
        assert humanize_score_mentions("scores 0.85 on evidence") == "scores strong on evidence"

    def test_dollars_and_large_numbers_untouched(self):
        from nicheiq.utils.calibration_notes import humanize_score_mentions
        assert humanize_score_mentions("charges $0.99 and 3.5x more") == "charges $0.99 and 3.5x more"
        assert humanize_score_mentions("v1.5 of the API") == "v1.5 of the API"

    def test_extraction_is_band_clean(self):
        import re
        from nicheiq.utils.calibration_notes import extract_criterion_reason
        notes = "market_fit: Addresses a validated 0.60-severity pain (0.45 linkage) | tech: fine"
        out = extract_criterion_reason(notes, "market_fit")
        assert not re.search(r"\d\.\d", out)
        assert "moderate-severity" in out

    def test_wallet_class_tokens_become_plain_english(self):
        # observed leak (wedding-photographers run 2026-07-07): the critic echoed the
        # payability input line's enum token into a user-facing critic_concern
        from nicheiq.utils.calibration_notes import humanize_score_mentions
        assert humanize_score_mentions(
            "benchmarks appeal to hobbyists with personal-wallet payability (0.15)"
        ) == "benchmarks appeal to hobbyists with personal out-of-pocket payability (weak)"
        assert humanize_score_mentions("SMB-Budget buyers already pay for CRMs") == \
            "small-business budget buyers already pay for CRMs"

    def test_wallet_extraction_is_token_clean(self):
        from nicheiq.utils.calibration_notes import extract_criterion_reason
        notes = "market_fit: weak — corporate-budget rhetoric but prosumer-wallet reality | tech: ok"
        out = extract_criterion_reason(notes, "market_fit")
        assert "corporate-budget" not in out and "prosumer-wallet" not in out
        assert "corporate budget" in out and "prosumer out-of-pocket" in out
