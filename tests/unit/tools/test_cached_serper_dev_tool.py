"""Tests for CachedSerperDevTool.batch_run — the Serper batch-query endpoint wrapper."""

from unittest.mock import MagicMock, patch

from nicheiq.tools.cached_serper_dev_tool import CachedSerperDevTool


def _tool() -> CachedSerperDevTool:
    return CachedSerperDevTool()


def _fake_response(payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


class TestBatchRun:
    def test_cache_hit_served_without_http(self):
        tool = _tool()
        tool._cache["cached query"] = {"organic": [{"title": "t", "link": "l", "snippet": "s"}]}
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post") as mock_post:
            out = tool.batch_run(["  Cached Query  "])
        mock_post.assert_not_called()
        assert out == {"  Cached Query  ": str(tool._cache["cached query"])}
        assert tool._hits == 1
        assert tool._misses == 0

    def test_miss_posts_only_misses(self):
        tool = _tool()
        tool._cache["already cached"] = "cached result"
        raw_response = [
            {"searchParameters": {"q": "new query"},
             "organic": [{"title": "T", "link": "https://example.com", "snippet": "S"}],
             "credits": 1},
        ]
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(raw_response)) as mock_post:
            out = tool.batch_run(["already cached", "new query"])
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == [{"q": "new query"}]  # only the miss was sent
        assert out["already cached"] == "cached result"
        assert "new query" in out["new query"]
        assert "example.com" in out["new query"]
        assert tool._hits == 1
        assert tool._misses == 1
        # The fetched result is now cached under its normalized key.
        assert "new query" in tool._cache

    def test_per_query_failure_returns_empty_string(self):
        tool = _tool()
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   side_effect=RuntimeError("boom")):
            out = tool.batch_run(["q1", "q2"])
        assert out == {"q1": "", "q2": ""}

    def test_response_mapped_by_order(self):
        tool = _tool()
        raw_response = [
            {"searchParameters": {"q": "alpha"}, "organic": [{"title": "A", "link": "a", "snippet": "sa"}]},
            {"searchParameters": {"q": "beta"}, "organic": [{"title": "B", "link": "b", "snippet": "sb"}]},
        ]
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(raw_response)):
            out = tool.batch_run(["alpha", "beta"])
        assert "A" in out["alpha"] and "B" not in out["alpha"]
        assert "B" in out["beta"] and "A" not in out["beta"]

    def test_duplicate_queries_all_returned(self):
        tool = _tool()
        raw_response = [
            {"searchParameters": {"q": "dup"}, "organic": [{"title": "D", "link": "d", "snippet": "sd"}]},
        ]
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(raw_response)) as mock_post:
            out = tool.batch_run(["dup", "DUP", " dup "])
        # Only one network call for the deduped query, but every original string resolves.
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == [{"q": "dup"}]
        assert out["dup"] == out["DUP"] == out[" dup "]
        assert "D" in out["dup"]


class TestBatchRunRaw:
    def test_cache_hit_served_without_http(self):
        tool = _tool()
        tool._raw_cache["cached query"] = {"organic": [{"title": "t", "link": "l", "snippet": "s"}]}
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post") as mock_post:
            out = tool.batch_run_raw(["  Cached Query  "])
        mock_post.assert_not_called()
        assert out == {"  Cached Query  ": tool._raw_cache["cached query"]}
        assert isinstance(out["  Cached Query  "], dict)
        assert tool._hits == 1
        assert tool._misses == 0

    def test_miss_returns_raw_dict_not_string(self):
        tool = _tool()
        raw_response = [
            {"searchParameters": {"q": "new query"},
             "organic": [{"title": "T", "link": "https://example.com", "snippet": "S"}],
             "credits": 1},
        ]
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(raw_response)) as mock_post:
            out = tool.batch_run_raw(["new query"])
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == [{"q": "new query"}]  # no tbs when not provided
        assert isinstance(out["new query"], dict)
        assert out["new query"]["organic"][0]["link"] == "https://example.com"
        assert "new query" in tool._raw_cache

    def test_per_query_failure_returns_empty_dict(self):
        """Fail-soft parity with the sequential per-query exception path: a request-level
        failure resolves every unresolved query to {}, which extract_results_from_serper
        treats as an empty search (no exception raised)."""
        tool = _tool()
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   side_effect=RuntimeError("boom")):
            out = tool.batch_run_raw(["q1", "q2"])
        assert out == {"q1": {}, "q2": {}}

        from nicheiq.utils.search_helpers import SearchHelper
        assert SearchHelper.extract_results_from_serper(out["q1"], "reddit.com") == []

    def test_tbs_included_in_payload_and_cache_key(self):
        tool = _tool()
        raw_response = [
            {"searchParameters": {"q": "fresh query"},
             "organic": [{"title": "Fresh", "link": "https://example.com/fresh", "snippet": "S"}]},
        ]
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(raw_response)) as mock_post:
            out = tool.batch_run_raw(["fresh query"], tbs="qdr:d")
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == [{"q": "fresh query", "tbs": "qdr:d"}]
        assert out["fresh query"]["organic"][0]["link"] == "https://example.com/fresh"

    def test_tbs_does_not_collide_with_untagged_cache_entry(self):
        """A date-filtered pass over the same query text must not serve a stale cache
        hit from an earlier unfiltered pass (or vice versa) — the two are different
        searches and must be keyed distinctly."""
        tool = _tool()
        untagged_response = [
            {"searchParameters": {"q": "same text"},
             "organic": [{"title": "Old", "link": "https://example.com/old", "snippet": "S"}]},
        ]
        tagged_response = [
            {"searchParameters": {"q": "same text"},
             "organic": [{"title": "New", "link": "https://example.com/new", "snippet": "S"}]},
        ]
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(untagged_response)):
            tool.batch_run_raw(["same text"])
        with patch("nicheiq.tools.cached_serper_dev_tool.requests.post",
                   return_value=_fake_response(tagged_response)) as mock_post:
            out = tool.batch_run_raw(["same text"], tbs="qdr:d")
        mock_post.assert_called_once()  # tagged call was a fresh miss, not a cache hit
        assert out["same text"]["organic"][0]["link"] == "https://example.com/new"
