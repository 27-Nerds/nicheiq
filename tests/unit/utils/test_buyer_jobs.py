"""Buyer-job family partition (docs/DIVERSITY_DECISION_2026-08.md).

Locks the contract the allocator depends on: a COMPLETE, validated partition over stable pain
ids (never free-text labels as equality keys), and an honest degradation flag whenever the
labeler could not run.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.utils.buyer_jobs import (
    MAX_FAMILIES, BuyerJobPartition, _validate_partition, classify_buyer_job_families,
    extend_partition, pain_id, partition_from_dict, theme_fallback_partition,
)


def _pain(title, theme=None, desc="desc"):
    return SimpleNamespace(title=title, description=desc, parent_theme_id=theme)


def _members(families):
    return [pid for f in families for pid in f.member_pain_ids]


class TestValidatePartition:
    def test_every_pain_lands_in_exactly_one_family(self):
        pains = [_pain("A"), _pain("B"), _pain("C")]
        families, repairs = _validate_partition(
            [{"display_label": "one", "member_pain_ids": ["A", "B"]},
             {"display_label": "two", "member_pain_ids": ["C"]}], pains)

        assert sorted(_members(families)) == ["A", "B", "C"]
        assert len(_members(families)) == 3  # no pain in two families
        assert repairs["unassigned_pains"] == 0

    def test_unknown_and_duplicate_ids_are_dropped_not_trusted(self):
        pains = [_pain("A"), _pain("B")]
        families, _ = _validate_partition(
            [{"display_label": "one", "member_pain_ids": ["A", "ghost"]},
             {"display_label": "two", "member_pain_ids": ["A", "B"]}], pains)

        assert sorted(_members(families)) == ["A", "B"]
        assert families[0].member_pain_ids == ("A",)   # first family keeps the duplicate
        assert families[1].member_pain_ids == ("B",)

    def test_pains_the_labeler_forgot_become_their_own_family(self):
        pains = [_pain("A"), _pain("B"), _pain("orphan")]
        families, repairs = _validate_partition(
            [{"display_label": "one", "member_pain_ids": ["A", "B"]}], pains)

        assert repairs["unassigned_pains"] == 1
        orphan = [f for f in families if f.member_pain_ids == ("orphan",)]
        assert orphan and orphan[0].inferred is True

    def test_overflow_is_merged_never_dropped(self):
        pains = [_pain(f"P{i}") for i in range(MAX_FAMILIES + 3)]
        families, repairs = _validate_partition(
            [{"display_label": f"g{i}", "member_pain_ids": [f"P{i}"]}
             for i in range(MAX_FAMILIES + 3)], pains)

        assert len(families) == MAX_FAMILIES
        assert repairs["overflow_merged"] > 0
        assert sorted(_members(families)) == sorted(pain_id(p) for p in pains)


class TestThemeFallback:
    def test_groups_by_theme_and_is_always_marked_degraded(self):
        pains = [_pain("A", theme="t1"), _pain("B", theme="t1"), _pain("C", theme="t2")]
        part = theme_fallback_partition(pains)

        assert part.degraded is True and part.source == "theme_fallback"
        assert part.family_for("A") == part.family_for("B") != part.family_for("C")

    def test_theme_less_pains_stand_alone(self):
        part = theme_fallback_partition([_pain("A"), _pain("B")])
        assert part.family_for("A") != part.family_for("B")


class TestClassify:
    def test_llm_failure_degrades_to_theme_key_and_says_so(self):
        pains = [_pain("A", theme="t1"), _pain("B", theme="t1"), _pain("C", theme="t2")]
        with patch("nicheiq.utils.llm_service.LLMService.invoke_structured",
                   side_effect=RuntimeError("boom")):
            part = classify_buyer_job_families(pains)

        assert part.degraded is True
        assert part.source == "theme_fallback"
        assert "boom" in (part.degradation_reason or "")
        assert part.family_for("A") == part.family_for("B")

    def test_successful_call_yields_an_llm_sourced_partition(self):
        pains = [_pain("A"), _pain("B"), _pain("C")]
        fake = SimpleNamespace(families=[
            SimpleNamespace(buyer="Owner", triggering_job="close the books",
                            economic_outcome="ops budget", display_label="Bookkeeping",
                            member_pain_ids=["A", "B"]),
            SimpleNamespace(buyer="Tech", triggering_job="fix the rig",
                            economic_outcome="tooling budget", display_label="Repair",
                            member_pain_ids=["C"]),
        ])
        with patch("nicheiq.utils.llm_service.LLMService.invoke_structured",
                   return_value=(fake, None)):
            part = classify_buyer_job_families(pains, niche="n")

        assert part.source == "llm" and part.degraded is False
        assert part.family_for("A") == part.family_for("B") != part.family_for("C")
        assert part.label_for(part.family_for("A")) == "Bookkeeping"
        assert isinstance(part, BuyerJobPartition)

    def test_too_few_pains_never_calls_the_labeler(self):
        with patch("nicheiq.utils.llm_service.LLMService.invoke_structured") as m:
            part = classify_buyer_job_families([_pain("A")])
        m.assert_not_called()
        assert part.degraded is True


class TestStableIdsAndReuse:
    """A `family_id` is persisted and reused by later regenerate/seed batches, so it must be
    derived from CONTENT — a positional id would rebind to a different buyer job the moment a
    batch produced a different number of families."""

    def test_family_ids_are_content_derived_not_positional(self):
        pains = [_pain("A"), _pain("B"), _pain("C")]
        first, _ = _validate_partition(
            [{"display_label": "Close the books", "member_pain_ids": ["A"]},
             {"display_label": "Fix the rig", "member_pain_ids": ["B", "C"]}], pains)
        # Same families, emitted in the OPPOSITE order: ids must not move.
        second, _ = _validate_partition(
            [{"display_label": "Fix the rig", "member_pain_ids": ["B", "C"]},
             {"display_label": "Close the books", "member_pain_ids": ["A"]}], pains)

        ids = {f.display_label: f.family_id for f in first}
        assert ids == {f.display_label: f.family_id for f in second}
        assert ids["Close the books"] == "close-the-books"

    def test_unlabeled_family_falls_back_to_a_member_digest_not_an_index(self):
        pains = [_pain("A"), _pain("B")]
        families, _ = _validate_partition(
            [{"display_label": "", "triggering_job": "", "member_pain_ids": ["A", "B"]}], pains)
        assert families[0].family_id.startswith("job-")
        # Deterministic across calls and independent of member ORDER.
        again, _ = _validate_partition(
            [{"display_label": "", "triggering_job": "", "member_pain_ids": ["B", "A"]}],
            [_pain("B"), _pain("A")])
        assert again[0].family_id == families[0].family_id

    def test_theme_fallback_ids_are_content_derived(self):
        part = theme_fallback_partition([_pain("A", theme="billing"), _pain("B", theme="billing")])
        assert part.family_for("A") == part.family_for("B") == "billing"

    def test_partition_from_dict_round_trips_and_refuses_degraded(self):
        pains = [_pain("A"), _pain("B"), _pain("C")]
        families, _ = _validate_partition(
            [{"buyer": "Owner", "triggering_job": "close the books", "economic_outcome": "ops",
              "display_label": "Bookkeeping", "member_pain_ids": ["A", "B"]},
             {"display_label": "Repair", "member_pain_ids": ["C"]}], pains)
        original = BuyerJobPartition(
            families=tuple(families),
            by_pain={p: f.family_id for f in families for p in f.member_pain_ids})

        restored = partition_from_dict(original.to_telemetry())
        assert restored is not None
        assert restored.by_pain == original.by_pain
        assert restored.families[0].buyer == "Owner"
        assert restored.families[0].triggering_job == "close the books"

        # A degraded (theme-fallback) partition is never rehydrated — a later batch deserves a
        # real labeler attempt instead of inheriting the degradation.
        assert partition_from_dict(theme_fallback_partition(pains).to_telemetry()) is None
        assert partition_from_dict(None) is None
        assert partition_from_dict({"families": []}) is None

    def test_extend_partition_adds_only_new_pains_and_never_moves_existing_ones(self):
        pains = [_pain("A"), _pain("B")]
        families, _ = _validate_partition(
            [{"display_label": "Bookkeeping", "member_pain_ids": ["A", "B"]}], pains)
        original = BuyerJobPartition(
            families=tuple(families),
            by_pain={p: f.family_id for f in families for p in f.member_pain_ids})

        extended = extend_partition(original, [_pain("A"), _pain("B"), _pain("NEW")])
        assert extended.family_for("A") == original.family_for("A")
        assert extended.family_for("B") == original.family_for("B")
        assert extended.family_for("NEW") not in (None, original.family_for("A"))
        assert len(extended.families) == len(original.families) + 1
        assert next(f for f in extended.families
                    if f.family_id == extended.family_for("NEW")).inferred is True

        # No new pains => the exact same object (never a silent re-partition).
        assert extend_partition(original, pains) is original
