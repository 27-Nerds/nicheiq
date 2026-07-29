"""Tests for nicheiq.utils.frames — registry completeness + verbatim regression lock.

The pain frame's focus_header/mf_anchor must reproduce the CURRENT strings VERBATIM. The
literals below are copied straight from source (not re-derived) so this test fails the moment
either prompt drifts:
  - focus_header source: unified_solution_crew.py::_build_partitioned_block, the line
    `+ "\\nTHE ONE PAIN TO SOLVE:\\n"` (~line 276)
  - mf_anchor source: idea_improvement_loop.py::_reviewer_system, the market_fit bullet
    "does it solve THE SOURCE PAIN BELOW for THIS audience?" (~line 142)
"""

import dataclasses

import pytest

from nicheiq.utils.frames import FRAME_REGISTRY, FrameFocus, FrameSpec

# Verbatim regression-lock literals (see module docstring for source pointers).
_VERBATIM_PAIN_FOCUS_HEADER = "THE ONE PAIN TO SOLVE:"
_VERBATIM_PAIN_MF_ANCHOR = "does it solve THE SOURCE PAIN BELOW for THIS audience?"

_ANCHOR_GROUNDING_LINE = (
    "Ground every concept in the ANCHOR PAINS listed — a concept serving none of them will be "
    "rejected."
)

_EXPECTED_FRAMES = {"pain", "gap", "data_asset", "workflow", "user_seed"}


def test_registry_has_exactly_five_frames():
    assert set(FRAME_REGISTRY.keys()) == _EXPECTED_FRAMES
    # spend_adjacent was deleted permanently 2026-07-10 (Multi-Frame A/B concluded).
    assert "spend_adjacent" not in FRAME_REGISTRY


@pytest.mark.parametrize("frame_key", sorted(_EXPECTED_FRAMES))
def test_spec_required_fields_non_empty(frame_key):
    spec = FRAME_REGISTRY[frame_key]
    assert spec.frame == frame_key
    assert callable(spec.brief_formatter)
    assert spec.focus_header
    assert spec.mf_anchor
    assert isinstance(spec.always_allow_zero, bool)


def test_pain_spec_header_and_anchor_match_verbatim_source_strings():
    spec = FRAME_REGISTRY["pain"]
    assert spec.focus_header == _VERBATIM_PAIN_FOCUS_HEADER
    assert spec.mf_anchor == _VERBATIM_PAIN_MF_ANCHOR
    assert spec.always_allow_zero is False


def test_pain_brief_formatter_passes_prerendered_text_through_unchanged():
    prerendered = "PAIN: Something\n  A description\n  (severity 7.0/10)"
    focus = FrameFocus(
        frame="pain",
        key="pain-1",
        payload={"pain_text": prerendered},
        anchor_pain_titles=["Something"],
    )
    assert FRAME_REGISTRY["pain"].brief_formatter(focus) == prerendered


@pytest.mark.parametrize("frame_key", ["gap", "data_asset", "workflow"])
def test_non_pain_specs_allow_zero(frame_key):
    assert FRAME_REGISTRY[frame_key].always_allow_zero is True


def test_user_seed_spec_never_allows_zero():
    # A paid user seed MUST return >=1 concept — unlike a research-derived focus, "no fit" is
    # not a valid outcome here.
    assert FRAME_REGISTRY["user_seed"].always_allow_zero is False
    assert FRAME_REGISTRY["user_seed"].focus_header == "THE IDEA THE USER WANTS BUILT:"


def test_gap_formatter_renders_payload_and_grounding_line():
    focus = FrameFocus(
        frame="gap",
        key="incumbent-x",
        payload={
            "incumbent_name": "Acme Scheduler",
            "pricing": "$49/mo",
            "gap": "no offline mode",
            "dissatisfaction_quote": 'Acme — "it dies the second wifi drops" (reddit)',
        },
        anchor_pain_titles=["Losing work when wifi drops"],
    )
    rendered = FRAME_REGISTRY["gap"].brief_formatter(focus)
    assert "Acme Scheduler" in rendered
    assert "$49/mo" in rendered
    assert "no offline mode" in rendered
    assert "it dies the second wifi drops" in rendered
    assert _ANCHOR_GROUNDING_LINE in rendered


def test_data_asset_formatter_renders_payload_and_grounding_line():
    focus = FrameFocus(
        frame="data_asset",
        key="route-1",
        payload={"route_text": "public permit records (city open-data portal) — filings, fees"},
        anchor_pain_titles=["Can't find permit status"],
    )
    rendered = FRAME_REGISTRY["data_asset"].brief_formatter(focus)
    assert "public permit records" in rendered
    assert _ANCHOR_GROUNDING_LINE in rendered


def test_workflow_formatter_renders_payload_and_grounding_line():
    focus = FrameFocus(
        frame="workflow",
        key="job-1",
        payload={
            "job_statement": "get the venue booked without double-paying deposits",
            "steps_text": "shortlist -> call -> compare -> deposit -> confirm",
            "tools_text": "spreadsheets, email, phone",
        },
        anchor_pain_titles=["Double deposits lost to slow vendor replies"],
    )
    rendered = FRAME_REGISTRY["workflow"].brief_formatter(focus)
    assert "get the venue booked" in rendered
    assert "shortlist -> call -> compare -> deposit -> confirm" in rendered
    assert "spreadsheets, email, phone" in rendered
    assert _ANCHOR_GROUNDING_LINE in rendered


def test_user_seed_formatter_renders_seed_text_as_primary_directive():
    focus = FrameFocus(
        frame="user_seed", key="seed-1",
        payload={"seed_text": "A tool that tracks late invoices for freelance plumbers"},
        anchor_pain_titles=[],
    )
    rendered = FRAME_REGISTRY["user_seed"].brief_formatter(focus)
    # The brief opens by naming the seed as the immutable core, then quotes it — the seed
    # still leads, ahead of the preservation clause that qualifies it.
    assert rendered.startswith("USER-PROVIDED PRODUCT BRIEF — IMMUTABLE CORE:")
    assert (
        rendered.index("A tool that tracks late invoices for freelance plumbers")
        < rendered.index("Preserve the product category")
    )
    assert "INCUMBENT/TOOL TO DISPLACE" not in rendered
    assert _ANCHOR_GROUNDING_LINE not in rendered  # unanchored: no anchor list to ground in


def test_user_seed_formatter_renders_optional_tool_ref():
    focus = FrameFocus(
        frame="user_seed", key="seed-2",
        payload={"seed_text": "A cheaper alternative to QuickBooks for solo landscapers",
                 "tool_ref": "QuickBooks"},
        anchor_pain_titles=[],
    )
    rendered = FRAME_REGISTRY["user_seed"].brief_formatter(focus)
    assert "INCUMBENT/TOOL TO DISPLACE: QuickBooks" in rendered


def test_user_seed_formatter_appends_grounding_line_only_when_anchored():
    focus = FrameFocus(
        frame="user_seed", key="seed-3",
        payload={"seed_text": "Automated late-invoice reminders for plumbers"},
        anchor_pain_titles=["Chasing unpaid invoices manually"],
    )
    rendered = FRAME_REGISTRY["user_seed"].brief_formatter(focus)
    assert _ANCHOR_GROUNDING_LINE in rendered


def test_framespec_is_frozen_and_hashable():
    spec = FRAME_REGISTRY["gap"]
    assert dataclasses.is_dataclass(spec)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.frame = "mutated"
    assert hash(spec) is not None


def test_framefocus_is_frozen_and_hashable():
    focus = FrameFocus(
        frame="gap", key="incumbent-x", payload={"a": 1}, anchor_pain_titles=["Some pain"]
    )
    assert dataclasses.is_dataclass(focus)
    with pytest.raises(dataclasses.FrozenInstanceError):
        focus.key = "mutated"
    # payload/anchor_pain_titles are compare=False (unhashable), so identity is (frame, key).
    assert hash(focus) == hash(FrameFocus(
        frame="gap", key="incumbent-x", payload={}, anchor_pain_titles=[]
    ))
