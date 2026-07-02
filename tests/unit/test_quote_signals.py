"""Incumbent-dissatisfaction quote signals (A/B-validated 2026-07-02, always on)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew, _build_partitioned_block
from nicheiq.utils.quote_signals import (
    detect_incumbent_dissatisfaction,
    format_dissatisfaction_block,
)


def _texts(*texts, source="r/test"):
    return [(t, source) for t in texts]


class TestDetector:
    def test_cakecost_live_case(self):
        # the exact post wholesale-fetched from r/CottageFoodBusiness
        out = detect_incumbent_dissatisfaction(
            _texts("Do you use anything for pricing? I don't like CakeCost.",
                   source="r/CottageFoodBusiness"),
            ["CakeCost", "CakeBoss"])
        assert len(out) == 1 and out[0].startswith("CakeCost — ")
        assert "don't like CakeCost" in out[0] and "r/CottageFoodBusiness" in out[0]

    def test_sentence_scoped_cooccurrence(self):
        # name and marker in DIFFERENT sentences → no signal
        out = detect_incumbent_dissatisfaction(
            _texts("I use CakeCost for pricing. I hate driving in traffic though."),
            ["CakeCost"])
        assert out == []

    def test_name_without_negativity_ignored(self):
        assert detect_incumbent_dissatisfaction(
            _texts("I use CakeCost every week and it's fine."), ["CakeCost"]) == []

    def test_negativity_without_name_ignored(self):
        assert detect_incumbent_dissatisfaction(
            _texts("I hate doing my pricing by hand."), ["CakeCost"]) == []

    def test_generic_tools_and_short_names_skipped(self):
        out = detect_incumbent_dissatisfaction(
            _texts("I hate Excel for this", "Google is too expensive somehow", "I hate X1"),
            ["Excel", "Google", "X1", "Frequently mentioned (3+ posts):"])
        assert out == []

    def test_word_boundary_no_substring_hits(self):
        assert detect_incumbent_dissatisfaction(
            _texts("I hate concatenation errors"), ["cat"]) == []

    def test_dedup_and_cap(self):
        q = "switched from MoeGo because it was too expensive"
        texts = _texts(q, q, *[f"gave up on MoeGo attempt {i}" for i in range(9)])
        out = detect_incumbent_dissatisfaction(texts, ["MoeGo"], max_signals=4)
        assert len(out) == 4
        assert len(set(out)) == 4  # all distinct

    def test_block_formatting(self):
        assert format_dissatisfaction_block([]) == ""
        b = format_dissatisfaction_block(['CakeCost — "I don\'t like CakeCost"'])
        assert "INCUMBENT DISSATISFACTION" in b and "CakeCost" in b


class TestCorpusIteration:
    def test_reddit_posts_comments_replies_and_generic(self):
        from nicheiq.utils.quote_signals import iter_corpus_texts
        sc = SimpleNamespace(
            reddit_posts=[SimpleNamespace(
                title="T", selftext="body", subreddit="CottageFoodBusiness",
                comments=[SimpleNamespace(body="c1", replies=[SimpleNamespace(body="r1")])])],
            generic_posts=[SimpleNamespace(content="hn text", platform="hackernews")])
        texts = iter_corpus_texts(sc)
        joined = " | ".join(t for t, _ in texts)
        assert "T. body" in joined and "c1" in joined and "r1" in joined and "hn text" in joined
        assert ("hn text", "hackernews") in texts

    def test_none_safe(self):
        from nicheiq.utils.quote_signals import iter_corpus_texts
        assert iter_corpus_texts(None) == []


class TestCrewIntegration:
    def _crew(self):
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.niche_context = SimpleNamespace(
            niche_description="cottage bakers",
            anchor_entities=["CakeBoss"])
        crew.social_content = SimpleNamespace(
            reddit_posts=[SimpleNamespace(
                title="Do you use anything for pricing?", subreddit="CottageFoodBusiness",
                selftext="I don't like CakeCost.", comments=[])],
            generic_posts=[])
        crew.competitor_mentions_text = "- **CakeCost**: mentioned twice"
        crew._incumbent_probe_text = ""      # probe cached-empty (no live call)
        crew._incumbent_rows = []
        return crew

    def test_detects_gates_and_caches(self):
        crew = self._crew()
        fake = SimpleNamespace(keep_indices=[0])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)) as m:
            block = crew._build_dissatisfaction_block()
            block2 = crew._build_dissatisfaction_block()
        assert "CakeCost" in block and "INCUMBENT DISSATISFACTION" in block
        assert m.call_count == 1 and block == block2  # cached after first build

    def test_precision_gate_drops_rejected_candidates(self):
        crew = self._crew()
        fake = SimpleNamespace(keep_indices=[])   # gate rejects everything
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            assert crew._build_dissatisfaction_block() == ""

    def test_gate_llm_failure_fails_closed(self):
        crew = self._crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            assert crew._build_dissatisfaction_block() == ""   # noisy evidence never injected

    def test_partitioned_block_byte_identical_when_empty(self):
        base = _build_partitioned_block("PAIN", "persona", 3, False)
        with_empty = _build_partitioned_block("PAIN", "persona", 3, False, dissatisfaction="")
        assert base == with_empty
        with_block = _build_partitioned_block("PAIN", "persona", 3, False,
                                              dissatisfaction="### INCUMBENT DISSATISFACTION\n- x")
        assert "INCUMBENT DISSATISFACTION" in with_block
