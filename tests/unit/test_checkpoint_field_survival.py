"""Checkpoint round-trip survival for the 2026-07-06 payability/parity fields.

The checkpoint loader re-parses stage JSON through the typed state models
(checkpoint_manager stage_mapping); a field that isn't DECLARED on the model is silently
dropped on load (`extra='ignore'`). These tests pin the exact save->load path (model_dump
mode='json' -> json -> model_validate) for every new field, plus legacy-checkpoint tolerance.
"""

import json

from nicheiq.models.research_state import AudienceSegment, NicheDifficultyVerdict
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaGenerationResult, IdeaTags


def _idea(name):
    return BaseSolutionIdea(
        solution_name=name, description="d" * 30, value_proposition="v",
        pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
        market_fit_score=0.6, technical_feasibility_score=0.7, novelty_score=0.5,
        seo_scalability_score=0.5, solo_dev_feasibility=0.6,
        adjacent_market_parity="HigherGov (govcon intel): feeds",
        source_segment="Agency Owner",
        source_segment_payability=0.25, source_segment_payability_class="personal-wallet",
        incumbent_parity="substitute (census.gov): raw data free",
        tags=IdeaTags(usage_cadence="one-shot", pricing_shape_mismatch=True,
                      pricing_shape_note="one-shot usage but subscription pricing"),
    )


def _roundtrip(model_cls, obj):
    return model_cls.model_validate(json.loads(json.dumps(obj.model_dump(mode="json"))))


def test_stage_5_3_idea_and_tag_fields_survive():
    gen = IdeaGenerationResult(solution_ideas=[_idea("A"), _idea("B"), _idea("C")])
    b = _roundtrip(IdeaGenerationResult, gen).solution_ideas[0]
    assert b.adjacent_market_parity == "HigherGov (govcon intel): feeds"
    assert b.source_segment_payability == 0.25
    assert b.source_segment_payability_class == "personal-wallet"
    assert b.incumbent_parity.startswith("substitute")
    assert b.tags.usage_cadence == "one-shot"
    assert b.tags.pricing_shape_mismatch is True
    assert b.tags.pricing_shape_note.startswith("one-shot usage")


def test_delivery_format_survives_checkpoint_and_legacy_missing_stays_none():
    current = _idea("A")
    current.delivery_format = "browser-extension"
    restored = _roundtrip(BaseSolutionIdea, current)

    assert restored.delivery_format == "browser-extension"

    legacy = current.model_dump(mode="json")
    legacy.pop("delivery_format")
    assert BaseSolutionIdea.model_validate(legacy).delivery_format is None


def test_stage_5_niche_difficulty_buyer_class_survives():
    v = NicheDifficultyVerdict(difficulty_level="high", software_addressability=0.4,
                               headline="h", narrative_summary="n",
                               buyer_class="indie-hobbyist", buyer_class_note="note")
    vb = _roundtrip(NicheDifficultyVerdict, v)
    assert vb.buyer_class == "indie-hobbyist" and vb.buyer_class_note == "note"


def test_audience_segment_payability_survives():
    seg = AudienceSegment(segment_name="S", size_estimate="Small", pain_point_alignment=["p"],
                          motivation_drivers=["m"], expertise_level="Beginner",
                          budget_sensitivity="High", discovery_channels=["Reddit"],
                          payability_score=0.15, payability_class="personal-wallet",
                          payability_rationale="r")
    sb = _roundtrip(AudienceSegment, seg)
    assert (sb.payability_score, sb.payability_class, sb.payability_rationale) == (
        0.15, "personal-wallet", "r")


def test_legacy_checkpoints_without_new_fields_still_load():
    gen = IdeaGenerationResult(solution_ideas=[_idea("A"), _idea("B"), _idea("C")])
    legacy = gen.model_dump(mode="json")
    for k in ("adjacent_market_parity", "source_segment_payability",
              "source_segment_payability_class"):
        legacy["solution_ideas"][0].pop(k)
    for k in ("usage_cadence", "pricing_shape_mismatch", "pricing_shape_note"):
        legacy["solution_ideas"][0]["tags"].pop(k)
    b = IdeaGenerationResult.model_validate(legacy).solution_ideas[0]
    assert b.adjacent_market_parity is None
    assert b.source_segment_payability is None
    assert b.tags.usage_cadence is None and b.tags.pricing_shape_mismatch is False
