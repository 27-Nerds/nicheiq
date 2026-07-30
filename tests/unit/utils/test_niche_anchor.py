"""Unit tests for the niche-anchor matcher helper.

Uses the peptides regression scenario (the run that drifted) as fixtures, plus
word-boundary edge cases. The helper itself is niche-agnostic.
"""

from nicheiq.utils.validation.niche_anchor import (
    anchor_coverage,
    build_anchor_matchers,
    text_has_anchor,
)

PEPTIDE_ANCHORS = ["BPC-157", "TB-500", "ipamorelin", "CJC-1295", "reconstitution"]


def test_named_entity_quote_matches():
    m = build_anchor_matchers(PEPTIDE_ANCHORS)
    assert text_has_anchor("how much bac water for BPC-157 5mg", m) is True
    assert text_has_anchor("starting ipamorelin tonight, dosing question", m) is True


def test_generic_quote_does_not_match():
    m = build_anchor_matchers(PEPTIDE_ANCHORS)
    # Generic r/fitness training talk with zero niche vocabulary.
    assert text_has_anchor("run a deload every 5-6 weeks to manage fatigue", m) is False
    assert text_has_anchor("just stretch more and swim for recovery", m) is False


def test_word_boundary_no_substring_false_positive():
    # 'pro' must not match inside 'protein'; 'weight' not inside 'weightlifting'.
    m = build_anchor_matchers(["pro", "weight"])
    assert text_has_anchor("i eat a lot of protein daily", m) is False
    assert text_has_anchor("weightlifting every morning", m) is False
    # But a real whole-word occurrence matches.
    assert text_has_anchor("he went pro last year", m) is True
    assert text_has_anchor("my weight is stable", m) is True


def test_stem_match():
    # 'reconstitution' anchor should match 'reconstitute' via stemming.
    m = build_anchor_matchers(["reconstitute"])
    assert text_has_anchor("how do I reconstitute the vial", m) is True


def test_coverage_math():
    m = build_anchor_matchers(PEPTIDE_ANCHORS)
    texts = ["BPC-157 dosing schedule", "random deload talk", "TB-500 injection site"]
    assert abs(anchor_coverage(texts, m) - (2 / 3)) < 1e-9


def test_empty_matchers_is_noop():
    # Empty anchor list => fail-open: never reports a match, coverage 0.
    assert text_has_anchor("BPC-157", []) is False
    assert anchor_coverage(["BPC-157", "anything"], []) == 0.0


def test_build_skips_blank_terms():
    assert build_anchor_matchers(["", "  ", None]) == []  # type: ignore[list-item]


def test_coverage_empty_texts():
    m = build_anchor_matchers(PEPTIDE_ANCHORS)
    assert anchor_coverage([], m) == 0.0


class TestNicheAnchorQueryTerm:
    def test_prefers_community_search_terms(self):
        from types import SimpleNamespace
        from nicheiq.utils.validation.niche_anchor import niche_anchor_query_term
        ctx = SimpleNamespace(community_search_terms=["auto repair"],
                              audience_jargon=["RO (repair order)"])
        assert niche_anchor_query_term(ctx) == "auto repair"

    def test_falls_back_to_jargon_rejecting_parenthetical(self):
        from types import SimpleNamespace
        from nicheiq.utils.validation.niche_anchor import niche_anchor_query_term
        ctx = SimpleNamespace(community_search_terms=["RO (repair order)"],
                              audience_jargon=["month-end close"])
        assert niche_anchor_query_term(ctx) == "month-end close"

    def test_rejects_long_terms_and_empty_context(self):
        from types import SimpleNamespace
        from nicheiq.utils.validation.niche_anchor import niche_anchor_query_term
        ctx = SimpleNamespace(
            community_search_terms=["a very long five word phrase"],
            audience_jargon=["another overly long jargon phrase here"])
        assert niche_anchor_query_term(ctx) == ""
        assert niche_anchor_query_term(None) == ""
