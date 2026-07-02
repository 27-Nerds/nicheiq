"""Item 4 (2026-07-02 plan) — related_keywords third discovery arm (A/B-validated, always on).

get_related_keywords mirrors get_keyword_suggestions (payload shape, parsing, fail-soft); the flow
merge appends into the SAME suggestions list so the existing grading gate controls drift.
"""

from unittest.mock import MagicMock, patch

from nicheiq.config.settings import settings
from nicheiq.tools.dataforseo_tool import DataForSEOExpandTool


def _labs_response(keywords):
    return {"tasks": [{"status_code": 20000, "result": [{"items": [
        {"keyword_data": {"keyword": kw, "keyword_info": {"search_volume": 100, "competition": 0.2},
                          "search_intent_info": {"main_intent": "informational"}}}
        for kw in keywords]}]}]}


class TestGetRelatedKeywords:
    def test_payload_endpoint_depth_and_parsing(self):
        tool = DataForSEOExpandTool()
        with patch.object(tool, "_make_request_with_task_retry",
                          return_value=_labs_response(["selling baked goods from home texas"])) as mreq:
            out = tool.get_related_keywords("cottage food law texas", depth=2, limit=30)
        endpoint, post_data = mreq.call_args[0][0], mreq.call_args[0][1]
        assert endpoint == "/dataforseo_labs/google/related_keywords/live"
        assert post_data[0]["keyword"] == "cottage food law texas"
        assert post_data[0]["depth"] == 2
        assert post_data[0]["limit"] == 30
        assert out == [{"keyword": "selling baked goods from home texas", "search_volume": 100,
                        "competition": 0.2, "search_intent": "informational"}]

    def test_depth_clamped_1_to_3(self):
        tool = DataForSEOExpandTool()
        with patch.object(tool, "_make_request_with_task_retry",
                          return_value=_labs_response([])) as mreq:
            tool.get_related_keywords("x y", depth=9)
        assert mreq.call_args[0][1][0]["depth"] == 3

    def test_fail_soft_on_error(self):
        tool = DataForSEOExpandTool()
        with patch.object(tool, "_make_request_with_task_retry", side_effect=RuntimeError("api down")):
            assert tool.get_related_keywords("x y") == []

    def test_task_error_returns_empty(self):
        tool = DataForSEOExpandTool()
        bad = {"tasks": [{"status_code": 40000, "status_message": "bad"}]}
        with patch.object(tool, "_make_request_with_task_retry", return_value=bad):
            assert tool.get_related_keywords("x y") == []


def test_tunable_defaults():
    # arm is unconditional (flag removed after the 2026-07-02 A/B); only tunables remain
    assert settings.related_keywords_depth == 1
    assert settings.related_keywords_per_seed == 30
