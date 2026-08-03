"""Field carry-over for ideas rebuilt from a narrow LLM schema.

Regression for run 8ef396eb: HouseNutIndex was the run's one accepted parity pivot
(`pivots_accepted: 1`) and the only one of 16 refined ideas with `project_type: None` —
26 fields came back null that all 15 peers carried. That null failed SolutionSnapshot
validation and silently deleted the finished report's go/no-go verdict. The same nulls
appear on red-team revisions and variant merges in five other audited runs.

The values below are verbatim from that run's `stage_5_3_refinement.json`.
"""

from unittest.mock import patch

import pytest

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils.idea_carryover import NEVER_CARRY, carry_forward_idea_fields

# --- Real pre-pivot idea (ShowClose Settlement Desk, run 8ef396eb) ---------------------
ORIGINAL = {
    "solution_name": "ShowClose Settlement Desk",
    "headline": "Shared Settlement Workspace for Independent Rooms",
    "short_description": "Lock the deal before the show, reconcile it after.",
    "description": "Append-only settlement ledger for independent venues.",
    "value_proposition": "Bilateral approval on every door split.",
    "pain_points_addressed": ["Cannot calculate artist payouts under a versus deal"],
    "source_pain": "Cannot calculate artist payouts under a versus deal",
    "source_segment": "Independent Multi-Room Venue Operators",
    "source_frame": "workflow",
    "core_features": ["Pre-show approval lock", "Append-only ledger"],
    "target_personas": ["Multi-Room Operator Maya"],
    "technical_approach": "Event-sourced ledger with bilateral sign-off.",
    "differentiation_factors": ["Connects pre-show approval to post-show payout"],
    "data_sources": ["User-entered deal terms", "Ticketing exports"],
    "data_access_model": "public",
    "data_acquisition_notes": "Core calculations use user-supplied settlement inputs.",
    "estimated_development_time": "3-6 weeks",
    "dev_time_rationale": "Ledger and approval flow dominate the build.",
    "pricing_strategy": "Subscription priced per room per month.",
    "project_type": "saas",
    "mechanism_tag": "immutable-settlement-ledger",
    "data_source_tag": "public-user-entered-settlement-data",
    "journey_tag": "pre-show-to-payout",
    "content_generation_model": "Programmatic educational pages per deal structure.",
    "organic_discovery_queries": ["versus deal settlement calculator"],
    "estimated_cac_organic": "$15-45 per customer",
    "estimated_cac_paid": "$120-260 per customer",
    "estimated_indexable_pages": 180,
    "market_fit_score": 0.7,
    "technical_feasibility_score": 0.8,
    "novelty_score": 0.4,
    "seo_scalability_score": 0.6,
    "solo_dev_feasibility": 0.8,
    "obviousness_score": 0.5,
    "winning_angle": "vertical_workflow",
    "angle_rationale": "The workflow is the wedge for multi-room operators.",
    "why_it_works_short": "Approval before the show removes the dispute.",
    "idea_id": "idea_f5b504b877b9874408c4fae5e0000000",
    "idea_revision": 1,
    "identity_origin": "phase1",
    "idea_tier": "single",
    "source_segment_payability": 0.68,
    "source_segment_payability_class": "medium",
    "audience_fit": False,
    "incumbent_parity": "shipped by Prism.fm: automated settlement from booking terms",
}

# --- The real _Pivot payload: exactly the fields that schema regenerates ---------------
PIVOT_PAYLOAD = {
    "solution_name": "HouseNutIndex — Pre-Show Settlement Benchmarks for Independent Rooms",
    "value_proposition": "Help independent venues model and defend house-nut ranges.",
    "description": "Versioned, explainable benchmark ranges for independent live-music rooms.",
    "core_features": ["Benchmark ranges by room size", "Versioned methodology"],
    "conventional_approach": "Spreadsheets copied between rooms.",
    "innovation_angle": "Public wage and business-cost data translated into room benchmarks.",
    "why_it_works": "Operators need a defensible number before the artist arrives.",
    "technical_approach": "Public data ingestion plus a versioned benchmark model.",
    "data_access_model": "public",
    "market_fit_score": 0.62,
    "technical_feasibility_score": 0.78,
    "build_feasibility_score": 0.7,
    "data_feasibility_score": 0.7,
    "programmatic_seo_opportunity": "One page per metro and room size.",
}

# Fields that shipped null on the real record and must now survive the pivot.
# The 13 fields the live pivot in run 8ef396eb dropped. They split into two contracts:
# a rebuild must CARRY what is still true of the new product, and must REGENERATE what
# described the old one.
#
# Carried: classification and durable facts that survive a repositioning. `project_type`
# is the one whose None deleted the report's go/no-go verdict.
CARRIED_ON_PIVOT = [
    "project_type", "mechanism_tag", "data_source_tag", "journey_tag",
    "data_sources", "estimated_indexable_pages",
]

# Regenerated: pricing, GTM economics, differentiation and discovery queries describe how
# a SPECIFIC product is sold, so they are only true of the product they were written for.
# `differentiation_factors` is the self-defeating case — a parity pivot exists because the
# original's differentiation collided with an incumbent, so carrying it preserves the exact
# claim the pivot was performed to escape.
REGENERATED_ON_PIVOT = [
    "differentiation_factors", "pricing_strategy", "data_acquisition_notes",
    "content_generation_model", "organic_discovery_queries",
    "estimated_cac_organic", "estimated_cac_paid",
]

LOST_IN_PRODUCTION = CARRIED_ON_PIVOT + REGENERATED_ON_PIVOT


# BaseSolutionIdea requires these three; they are irrelevant to carry-over.
_REQUIRED = {"pain_points_addressed": ["p"], "core_features": ["f"],
             "target_personas": ["t"]}


class _Result:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return dict(self._payload)


@pytest.fixture
def original():
    return BaseSolutionIdea.model_validate(ORIGINAL)


@pytest.fixture
def pivoted(original):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    with patch(
        "nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
        return_value=(_Result(PIVOT_PAYLOAD), None),
    ):
        return UnifiedSolutionCrew._generate_pivot_revision(crew, original, {})


class TestRealHouseNutIndexPivot:
    def test_durable_classification_survives_the_pivot(self, pivoted, original):
        assert pivoted is not None
        missing = [f for f in CARRIED_ON_PIVOT if getattr(pivoted, f, None) is None]
        assert missing == [], f"still dropped on pivot: {missing}"
        # project_type is the one whose None deleted the report's go/no-go verdict.
        assert pivoted.project_type == original.project_type == "saas"
        assert pivoted.mechanism_tag == "immutable-settlement-ledger"

    def test_old_positioning_is_cleared_for_regeneration(self, pivoted):
        """A pivot changes the product, so how the OLD one was priced, differentiated and
        discovered must not ride along — it would describe a product that no longer exists."""
        carried = [f for f in REGENERATED_ON_PIVOT if getattr(pivoted, f, None) is not None]
        assert carried == [], f"old positioning carried onto the pivoted product: {carried}"

    def test_everything_cleared_for_regeneration_can_actually_be_regenerated(self):
        """Clearing is only safe because the repair pass refills it. If a field were removed
        from the repairable set, clearing it would become silent data loss instead."""
        from nicheiq.crews.unified_solution_crew import (
            _REPAIRABLE_LIST_FIELDS,
            _REPAIRABLE_TEXT_FIELDS,
        )
        repairable = set(_REPAIRABLE_TEXT_FIELDS) | set(_REPAIRABLE_LIST_FIELDS)
        orphaned = [f for f in REGENERATED_ON_PIVOT if f not in repairable]
        assert orphaned == [], f"cleared but nothing can refill them: {orphaned}"

    def test_the_pivoted_product_fields_are_not_overwritten_by_carry_over(self, pivoted):
        assert pivoted.solution_name == PIVOT_PAYLOAD["solution_name"]
        assert pivoted.value_proposition == PIVOT_PAYLOAD["value_proposition"]
        assert pivoted.technical_approach == PIVOT_PAYLOAD["technical_approach"]
        assert pivoted.core_features == PIVOT_PAYLOAD["core_features"]

    def test_provenance_still_carried(self, pivoted):
        assert pivoted.source_pain == ORIGINAL["source_pain"]
        assert pivoted.source_segment == ORIGINAL["source_segment"]
        assert pivoted.source_frame == "workflow"  # Fix #6 unchanged
        assert pivoted.idea_tier == "single"

    def test_the_escaped_parity_finding_is_not_carried(self, pivoted):
        # `_pivot_acceptable` requires the revision's OWN parity to clear; carrying the
        # original's finding would hand the pivot the verdict it exists to escape.
        assert pivoted.incumbent_parity is None

    def test_angle_is_left_for_reclassification(self, pivoted):
        # `_classify_idea_angles` SKIPS ideas that already carry a winning_angle.
        assert pivoted.winning_angle is None
        assert pivoted.angle_rationale is None

    def test_stale_summary_copy_is_not_carried(self, pivoted):
        for field in ("headline", "short_description", "why_it_works_short"):
            assert getattr(pivoted, field) is None

    def test_minted_identity_is_not_carried(self, pivoted):
        assert pivoted.idea_id is None
        assert pivoted.identity_origin is None

    def test_old_scores_are_re_earned_not_inherited(self, pivoted):
        # Carrying these would let a pivot inherit the composite it is measured against.
        for field in ("novelty_score", "seo_scalability_score", "solo_dev_feasibility",
                      "obviousness_score"):
            assert getattr(pivoted, field) is None


class TestCarryForwardRules:
    def test_only_empty_fields_are_filled(self, original):
        rev = BaseSolutionIdea.model_validate({
            "solution_name": "Rev", "description": "d", "value_proposition": "v",
            "project_type": "directory", **_REQUIRED,
        })
        carried = carry_forward_idea_fields(original, rev)
        assert rev.project_type == "directory"  # revision's own value wins
        assert "project_type" not in carried
        assert rev.mechanism_tag == "immutable-settlement-ledger"

    def test_falsy_but_real_values_are_not_treated_as_empty(self):
        orig = BaseSolutionIdea.model_validate({
            "solution_name": "O", "description": "d", "value_proposition": "v",
            "market_fit_score": 0.9, "audience_fit": True, **_REQUIRED,
        })
        rev = BaseSolutionIdea.model_validate({
            "solution_name": "R", "description": "d", "value_proposition": "v",
            "market_fit_score": 0.0, "audience_fit": False, **_REQUIRED,
        })
        carry_forward_idea_fields(orig, rev)
        assert rev.market_fit_score == 0.0
        assert rev.audience_fit is False

    def test_never_carry_is_honoured_for_every_listed_field(self, original):
        rev = BaseSolutionIdea.model_validate(
            {"solution_name": "R", "description": "d", "value_proposition": "v", **_REQUIRED}
        )
        carried = carry_forward_idea_fields(original, rev)
        assert NEVER_CARRY.isdisjoint(carried)

    def test_missing_original_is_a_no_op(self):
        rev = BaseSolutionIdea.model_validate(
            {"solution_name": "R", "description": "d", "value_proposition": "v", **_REQUIRED}
        )
        assert carry_forward_idea_fields(None, rev) == []

    def test_no_populated_field_is_silently_reset(self, original):
        # The point of preserve-then-reset: a field nobody remembered to list still
        # survives. Anything the original carried and the rebuild did NOT rewrite must
        # come across, without being named anywhere in the carry-over code.
        rebuilt = {"solution_name": "R", "description": "d", "value_proposition": "v",
                   **_REQUIRED}
        rev = BaseSolutionIdea.model_validate(rebuilt)
        carry_forward_idea_fields(original, rev)

        dropped = [
            f for f in BaseSolutionIdea.model_fields
            if f not in NEVER_CARRY
            and f not in rebuilt                      # not rewritten by the rebuild
            and ORIGINAL.get(f) not in (None, "", [], {})
            and getattr(rev, f, None) != ORIGINAL.get(f)
        ]
        assert dropped == [], f"silently reset: {dropped}"


class TestRebuildRepairGroundedness:
    """A rebuild regenerates what it can ground and leaves blank what it cannot.

    Clearing the old product's positioning (rule 4) is only an improvement if what
    replaces it is better than what was carried. Prose that restates the product is —
    it is derived from the revision's own description. Acquisition cost is not: the
    repair has no audience payability and no competitive set, so anything it wrote
    would be a confident number with nothing behind it. Both CAC fields already render
    as "N/A" when absent, so a gap costs the reader nothing.
    """

    def _repair(self, *, rebuild):
        from unittest.mock import MagicMock, patch

        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
        from nicheiq.models.solution_idea import BaseSolutionIdea

        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.niche_context = None
        crew._monetization_directive = "Buyers pay per active hold."
        crew._record_divergent_usage = lambda usages: None
        pain = MagicMock()
        pain.title = "Cannot calculate payouts"
        pain.commercial_intent = 0.62
        crew.pain_point_analysis = MagicMock()
        crew.pain_point_analysis.pain_points = [pain]

        idea = BaseSolutionIdea(
            solution_name="HouseNutIndex",
            value_proposition="Defend deductions.",
            description="Benchmarks house-nut ranges.",
            source_pain="Cannot calculate payouts",
            pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
        )
        captured = {}

        def fake(**kwargs):
            captured["prompt"] = kwargs["prompt"]
            return MagicMock(spec=BaseSolutionIdea), MagicMock()

        with patch("nicheiq.utils.llm_service.LLMService.invoke_structured", side_effect=fake):
            crew._repair_blank_idea_fields(
                idea, escaped_parity="shipped by VenueArc: settlement module", rebuild=rebuild,
            )
        return captured["prompt"]

    def _requested(self, prompt):
        return next(l for l in prompt.splitlines() if l.startswith("FIELDS CURRENTLY BLANK"))

    def test_rebuild_does_not_invent_acquisition_cost(self):
        assert "estimated_cac" not in self._requested(self._repair(rebuild=True))

    def test_first_pass_repair_is_unchanged(self):
        # The tournament-winner path has market context; only a REBUILD is constrained.
        assert "estimated_cac" in self._requested(self._repair(rebuild=False))

    def test_pricing_repair_carries_real_willingness_to_pay(self):
        # Without it, pricing defaults to a $/mo subscription whatever the buyer would pay.
        assert "willingness to pay is 6.2/10" in self._repair(rebuild=True)

    def test_differentiation_repair_names_the_escaped_incumbent(self):
        prompt = self._repair(rebuild=True)
        assert "REPOSITIONED TO ESCAPE" in prompt
        assert "VenueArc" in prompt
