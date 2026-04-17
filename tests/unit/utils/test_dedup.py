"""Tests for hybrid deduplication utility."""

import pytest
from datetime import datetime
from nicheiq.utils.validation.dedup import (
    normalize_text,
    get_ngrams,
    jaccard_similarity,
    token_jaccard,
    hybrid_similarity,
    deduplicate_posts,
)
from nicheiq.models.social_content import SocialPost


def _make_post(title: str, body: str = "", score: int = 10, platform: str = "hackernews") -> SocialPost:
    return SocialPost(
        post_id=f"p_{hash(title) % 10000}",
        platform=platform,
        title=title,
        body=body,
        author="testuser",
        url="https://example.com",
        score=score,
        num_responses=5,
        created_utc=datetime(2025, 1, 1),
    )


class TestNormalizeText:
    def test_lowercase_and_strip(self):
        assert normalize_text("Hello, World!") == "hello world"

    def test_collapse_whitespace(self):
        assert normalize_text("  too   many   spaces  ") == "too many spaces"

    def test_empty(self):
        assert normalize_text("") == ""


class TestGetNgrams:
    def test_basic(self):
        ngrams = get_ngrams("hello")
        assert "hel" in ngrams
        assert "ell" in ngrams
        assert "llo" in ngrams

    def test_short_text(self):
        assert get_ngrams("ab") == {"ab"}

    def test_empty(self):
        assert get_ngrams("") == set()


class TestJaccardSimilarity:
    def test_identical(self):
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0

    def test_disjoint(self):
        assert jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_partial(self):
        assert jaccard_similarity({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_empty(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0

    def test_symmetric(self):
        a, b = {"x", "y"}, {"y", "z"}
        assert jaccard_similarity(a, b) == jaccard_similarity(b, a)


class TestTokenJaccard:
    def test_stopword_removal(self):
        # "the cat sat" vs "a cat sat" — stopwords removed, "cat" and "sat" overlap
        score = token_jaccard("the cat sat on the mat", "a cat sat on a mat")
        assert score > 0.5

    def test_completely_different(self):
        assert token_jaccard("python programming", "cooking recipes") == 0.0


class TestHybridSimilarity:
    def test_is_max(self):
        a, b = "python web framework", "python web frameworks"
        ngram_score = jaccard_similarity(get_ngrams(a), get_ngrams(b))
        tok_score = token_jaccard(a, b)
        assert hybrid_similarity(a, b) == max(ngram_score, tok_score)

    def test_similar_texts(self):
        assert hybrid_similarity(
            "I can't find reliable contractors",
            "Finding reliable contractors is impossible",
        ) > 0.3

    def test_different_texts(self):
        assert hybrid_similarity(
            "SaaS pricing strategy",
            "How to bake sourdough bread",
        ) < 0.15


class TestDeduplicatePosts:
    def test_empty_list(self):
        assert deduplicate_posts([]) == []

    def test_single_item(self):
        p = _make_post("only one")
        assert deduplicate_posts([p]) == [p]

    def test_keeps_higher_engagement(self):
        low = _make_post("finding freelancers is hard", score=10)
        high = _make_post("finding freelancers is really hard", score=100)
        result = deduplicate_posts([low, high], threshold=0.5)
        assert len(result) == 1
        assert result[0].score == 100

    def test_keeps_different_posts(self):
        a = _make_post("python web framework comparison")
        b = _make_post("best hiking trails in colorado")
        result = deduplicate_posts([a, b], threshold=0.6)
        assert len(result) == 2

    def test_threshold_boundary(self):
        # Two very similar posts should be deduped at 0.6
        a = _make_post("struggling to find good SaaS pricing", score=5)
        b = _make_post("struggling to find good SaaS pricing strategy", score=15)
        result_strict = deduplicate_posts([a, b], threshold=0.3)
        result_loose = deduplicate_posts([a, b], threshold=0.99)
        assert len(result_strict) <= len(result_loose)
