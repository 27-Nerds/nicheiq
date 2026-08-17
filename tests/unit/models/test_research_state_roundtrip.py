"""`ResearchState` must survive its own serialization — proven on a real captured run.

WHY THIS FILE. `tests/unit/test_checkpoint_field_survival.py` round-trips individual
sub-models, each built by hand, each carrying only the fields its author remembered. That
misses the defect class where a field's DECLARED type disagrees with what the producer
actually writes, because a hand-built state is populated by the same author who read the
annotation. The live run does not read annotations.

The defect this pins: `SocialContentValidator.validate_quality` writes
`avg_engagement_per_source=round(avg, 1)` — a float, 49.7 on this run — into a dict declared
`Optional[dict[str, int]]`. Nothing validates on assignment, so the state carried the float
happily for the whole run; `model_validate(model_dump(mode="json"))` then raised
`int_from_float`. That is the shape of a mid-run resume, and of every consumer that reloads
a dumped state.

Fixed on the ANNOTATION side, not the producer side: the value is a mean, so a float is the
honest number (`research_flow`'s methodology block and the backend's
`avgEngagementPerSource` projection both consume it as a real number, and the flow itself
recomputes it with `round(..., 1)` when HN posts are excluded). The counters that share the
dict are genuinely ints, so the annotation is a union rather than `dict[str, float]` —
widening to float would have rewritten `116` as `116.0` in every checkpoint and report
payload to fix a bug in one key.
"""

from __future__ import annotations

import json
import warnings

import pytest

from nicheiq.models.research_state import ResearchState

from ..report.report_run_8f35ea6b import load_state


@pytest.fixture(scope="module")
def captured_state() -> ResearchState:
    return load_state()


def test_a_real_state_round_trips_through_its_own_json(captured_state):
    """The whole state, not one sub-model. `model_dump(mode="json")` is what the checkpoint
    writer and every state-forwarding consumer emit; `model_validate` is what reads it back.
    """
    dumped = json.loads(json.dumps(captured_state.model_dump(mode="json")))
    ResearchState.model_validate(dumped)  # raises on any field whose type is a lie


def test_dumping_a_real_state_emits_no_pydantic_serializer_warnings(captured_state):
    """The quieter half of the same defect.

    A declared type the value does not match makes `model_dump` emit
    `PydanticSerializationUnexpectedValue` — a WARNING, not an error, so the dump succeeds
    and the mismatch only surfaces later at the `model_validate` on the other side. This run
    emitted exactly one such warning (`Expected int ... input_value=49.7`) before the fix.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        captured_state.model_dump(mode="json")
    serializer_warnings = [
        str(w.message) for w in caught
        if "PydanticSerializationUnexpectedValue" in str(w.message)
    ]
    assert serializer_warnings == [], (
        "a field's declared type disagrees with the value a real run put in it; "
        "the dump succeeded anyway and will fail on the model_validate at the other end"
    )


def test_social_content_metrics_keeps_counters_int_and_the_average_float(captured_state):
    """Guards the fix against being 'simplified' to `dict[str, float]`.

    `avg_engagement_per_source` is a mean and must stay fractional; the six counters sharing
    the dict must stay ints, because they are serialized straight into checkpoint metadata,
    the preview report's `data_quality_summary`, and the backend's engagement-metric tile.
    """
    metrics = captured_state.social_content_metrics
    assert metrics is not None and metrics["avg_engagement_per_source"] == 49.7

    restored = ResearchState.model_validate(
        captured_state.model_dump(mode="json")
    ).social_content_metrics

    assert isinstance(restored["avg_engagement_per_source"], float)
    assert restored["avg_engagement_per_source"] == 49.7
    for counter in (
        "reddit_posts", "twitter_threads", "generic_posts",
        "total_sources", "total_interactions", "total_engagement",
    ):
        assert isinstance(restored[counter], int), (
            f"{counter} widened to float — the union collapsed to `dict[str, float]` and "
            f"every count now serializes as e.g. 116.0"
        )
    assert restored["total_sources"] == 116
