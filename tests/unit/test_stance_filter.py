"""
Unit tests for the pain-point quote stance gate (_stance_filter_quotes).

The stance gate keeps only quotes that genuinely express the pain — topical
vector matches that are off-stance (positive), neutral, or about a different
symptom must be dropped. On any LLM error the gate fails OPEN (keeps all).
"""

from unittest.mock import patch

from nicheiq.crews.pain_point_crew import PainPointCrew
from nicheiq.models.pain_point import (
    BatchStanceResponse,
    ExtractedQuote,
    StanceVerdict,
    UnvalidatedPainPoint,
)


def _crew():
    # Bypass heavy __init__; the stance gate only needs the method.
    return object.__new__(PainPointCrew)


def _pain():
    return UnvalidatedPainPoint(
        title="PT-141 causes debilitating nausea",
        description="Users report nausea severe enough to stop using PT-141",
        mention_count=3,
        anchor_keywords=["pt-141", "nausea"],
    )


def _quotes():
    return [
        ExtractedQuote(quote_text="This drug is very effective with no side effects", post_id="a"),
        ExtractedQuote(quote_text="Severe nausea made me stop using it completely", post_id="b"),
        ExtractedQuote(quote_text="You mix it with bacteriostatic water before injecting", post_id="c"),
    ]


def test_keeps_only_supports():
    verdicts = BatchStanceResponse(verdicts=[
        StanceVerdict(index=1, stance="CONTRADICTS", reason="positive"),
        StanceVerdict(index=2, stance="SUPPORTS", reason="reports nausea"),
        StanceVerdict(index=3, stance="NEUTRAL", reason="how-to"),
    ])
    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        return_value=(verdicts, None),
    ):
        kept = _crew()._stance_filter_quotes(_pain(), _quotes())
    assert [q.post_id for q in kept] == ["b"]


def test_empty_input_returns_empty_without_llm():
    with patch("nicheiq.utils.llm_service.LLMService.invoke_structured") as m:
        kept = _crew()._stance_filter_quotes(_pain(), [])
    assert kept == []
    m.assert_not_called()


def test_fail_open_on_llm_error():
    quotes = _quotes()
    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        side_effect=RuntimeError("boom"),
    ):
        kept = _crew()._stance_filter_quotes(_pain(), quotes)
    # Fail-open: all quotes retained rather than zeroing out the evidence.
    assert kept == quotes


def test_all_contradict_yields_empty():
    verdicts = BatchStanceResponse(verdicts=[
        StanceVerdict(index=1, stance="CONTRADICTS", reason="x"),
        StanceVerdict(index=2, stance="CONTRADICTS", reason="x"),
        StanceVerdict(index=3, stance="NEUTRAL", reason="x"),
    ])
    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        return_value=(verdicts, None),
    ):
        kept = _crew()._stance_filter_quotes(_pain(), _quotes())
    assert kept == []
