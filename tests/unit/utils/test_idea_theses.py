"""Thesis-level portfolio partition (utils/idea_theses.py, docs/DIVERSITY_DECISION_2026-08.md).

Guards the three properties that make this a PARTITION rather than a tagging pass: every visible
idea lands somewhere (a thesis or the explicit `unassigned` bucket), validated families with no
surviving concept are surfaced with a reason, and no rollup invents a signal (incumbent status,
fatal assumptions) the ideas do not already carry.
"""

import pytest

from nicheiq.utils.buyer_jobs import BuyerJobFamily, BuyerJobPartition
from nicheiq.utils.idea_theses import build_idea_theses

CTRL = "Controlled-drug balances cannot be maintained"
DEA = "Teams manage DEA Form 222 orders manually"
STOCK = "Clinics discover stockouts only when items are needed"
BILLING = "Staff manually enter medication use instead of linking to billing"


def _partition(source="llm", degraded=False):
    families = (
        BuyerJobFamily(
            family_id="controlled", buyer="Compliance officer",
            triggering_job="Keep a defensible controlled-drug record",
            economic_outcome="Clinic budget buys DEA-compliant inventory",
            member_pain_ids=(CTRL, DEA), display_label="Controlled-Substance Compliance"),
        BuyerJobFamily(
            family_id="stockout", buyer="Inventory coordinator",
            triggering_job="Prevent medication stockouts",
            economic_outcome="Clinic budget buys reorder signals",
            member_pain_ids=(STOCK,), display_label="Stockout Prevention"),
        BuyerJobFamily(
            family_id="billing", buyer="Practice manager",
            triggering_job="Link medication use to billing",
            economic_outcome="Clinic budget buys billing accuracy",
            member_pain_ids=(BILLING,), display_label="Billing-Consumption Linkage"),
    )
    return BuyerJobPartition(
        families=families,
        by_pain={p: f.family_id for f in families for p in f.member_pain_ids},
        source=source, degraded=degraded,
        degradation_reason="labeler unavailable" if degraded else None)


def _idea(name, **kw):
    idea = {
        "solution_name": name,
        "market_fit_score": 0.6,
        "technical_feasibility_score": 0.6,
        "novelty_score": 0.5,
        "seo_scalability_score": 0.5,
        "candidate_status": "active",
        "pain_points_addressed": [],
    }
    idea.update(kw)
    return idea


def test_every_visible_idea_lands_in_exactly_one_thesis():
    ideas = [
        _idea("NarcVault", source_pain=CTRL),
        _idea("Closebook", pain_points_addressed=[CTRL, DEA]),      # bundle: no source_pain
        _idea("ReorderGap", source_pain=STOCK),
        _idea("Absorbed", source_pain=STOCK, candidate_status="absorbed"),
        _idea("Demoted", source_pain=CTRL, candidate_status="demoted"),
    ]
    out = build_idea_theses(ideas, partition=_partition())

    by_id = {t["family_id"]: t for t in out["theses"]}
    assert sorted(by_id) == ["controlled", "stockout"]
    assert sorted(m["name"] for m in by_id["controlled"]["members"]) == ["Closebook", "NarcVault"]
    assert [m["name"] for m in by_id["stockout"]["members"]] == ["ReorderGap"]
    # Hidden ideas are not members of anything and are not "unassigned" either.
    assert out["unassigned"] == []
    placed = [m["name"] for t in out["theses"] for m in t["members"]]
    assert "Absorbed" not in placed and "Demoted" not in placed
    assert by_id["controlled"]["buyer"] == "Compliance officer"
    assert by_id["controlled"]["triggering_job"] == "Keep a defensible controlled-drug record"


def test_frame_born_and_merged_ideas_are_assigned_without_a_source_pain():
    ideas = [
        _idea("Variant A", source_pain=STOCK, candidate_status="absorbed"),
        _idea("Variant B", source_pain=STOCK, candidate_status="absorbed"),
        # merged synthesis: no source_pain, no usable pain list — inherits from its members
        _idea("Merged", idea_tier="merged", merged_from=["Variant A", "Variant B"],
              pain_points_addressed=["A pain nobody validated"]),
        # frame-born (data_asset): no source_pain, but claims a validated pain
        _idea("FrameBorn", source_frame="data_asset", pain_points_addressed=[BILLING]),
    ]
    out = build_idea_theses(ideas, partition=_partition())
    by_id = {t["family_id"]: [m["name"] for m in t["members"]] for t in out["theses"]}
    assert by_id["stockout"] == ["Merged"]
    assert by_id["billing"] == ["FrameBorn"]
    assert out["unassigned"] == []


def test_unassignable_idea_goes_to_an_explicit_bucket_not_a_new_family():
    ideas = [_idea("Orphan", pain_points_addressed=["A pain nobody validated"])]
    out = build_idea_theses(ideas, partition=_partition())
    assert out["theses"] == []
    assert [u["idea_name"] for u in out["unassigned"]] == ["Orphan"]
    assert "source_pain" in out["unassigned"][0]["reason"]


def test_lead_idea_is_the_best_member_by_the_existing_ranking():
    ideas = [
        _idea("Weak", source_pain=CTRL, market_fit_score=0.2, technical_feasibility_score=0.2),
        _idea("Strong", source_pain=DEA, market_fit_score=0.9, technical_feasibility_score=0.9),
    ]
    out = build_idea_theses(ideas, partition=_partition())
    thesis = out["theses"][0]
    assert thesis["lead_idea_name"] == "Strong"
    assert [m["name"] for m in thesis["members"]] == ["Strong", "Weak"]  # ranked, best first


def test_winning_angle_rides_at_variant_level_not_thesis_level():
    """The GTM lens is orthogonal to the buyer job: two variants of one thesis can differ."""
    ideas = [
        _idea("Workflow variant", source_pain=CTRL, winning_angle="vertical_workflow",
              market_fit_score=0.9, technical_feasibility_score=0.9, idea_tier="bundle"),
        _idea("SEO variant", source_pain=DEA, winning_angle="distribution_seo",
              market_fit_score=0.3, technical_feasibility_score=0.3, source_frame="data_asset"),
    ]
    thesis = build_idea_theses(ideas, partition=_partition())["theses"][0]
    assert thesis["members"] == [
        {"name": "Workflow variant", "winning_angle": "vertical_workflow",
         "idea_tier": "bundle", "source_frame": "pain"},
        {"name": "SEO variant", "winning_angle": "distribution_seo",
         "idea_tier": "single", "source_frame": "data_asset"},
    ]
    assert "winning_angle" not in thesis  # never rolled up to a fabricated consensus


@pytest.mark.parametrize("stamps,expected,vendors", [
    (["shipped by VetSnap: digital logbook"], "occupied", ["VetSnap"]),
    (["bundled_free (ezyVet): included in every plan"], "occupied", ["ezyVet"]),
    (["partial by ezyVet: low-stock alerts only"], "partial", ["ezyVet"]),
    (["none found", "none found"], "open", []),
    # "shipped by evidence" is a red-team ADVERSARIAL finding, not a parity claim naming a vendor
    (["shipped by evidence: the snippets describe adjacent tools"], "unknown", []),
    (["none found", "shipped by evidence: adjacent tools"], "unknown", []),
    ([None, None], "unknown", []),
    (["partial by ezyVet: alerts", "shipped by VetSnap: logbook"], "occupied",
     ["VetSnap", "ezyVet"]),
])
def test_incumbent_status_rolls_up_from_member_parity_stamps(stamps, expected, vendors):
    ideas = [_idea(f"Idea{i}", source_pain=CTRL, incumbent_parity=s)
             for i, s in enumerate(stamps)]
    out = build_idea_theses(ideas, partition=_partition())
    thesis = out["theses"][0]
    assert thesis["incumbent_status"] == expected
    assert thesis["incumbent_vendors"] == vendors


def test_fatal_assumptions_are_deterministic_rollups_with_their_source_field():
    ideas = [
        _idea("Killed", source_pain=CTRL, red_team_verdict="killed",
              red_team_caveats=["No buyer segment demands this."]),
        _idea("Unverified", source_pain=DEA, data_access_model="unverified",
              audience_fit=False, data_sources=["Clinic-supplied receipts", "FDA NDC Directory"],
              refine_binding_constraint="Sharpen the mechanism beyond outlier detection."),
    ]
    out = build_idea_theses(ideas, partition=_partition())
    rows = out["theses"][0]["fatal_assumptions"]
    by_field = {(r["source_field"], r["idea_name"]): r["assumption"] for r in rows}

    assert by_field[("red_team_verdict", "Killed")] == "No buyer segment demands this."
    assert "could not confirm" in by_field[("data_access_model", "Unverified")]
    assert "adjacent audience" in by_field[("audience_fit", "Unverified")]
    # Only the customer-supplied source is a cold-start signal; the public directory is not.
    cold = by_field[("data_sources", "Unverified")]
    assert "Clinic-supplied receipts" in cold and "FDA NDC Directory" not in cold
    assert by_field[("refine_binding_constraint", "Unverified")] == (
        "Sharpen the mechanism beyond outlier detection.")
    # Red-team kill leads the list (strongest signal first).
    assert rows[0]["source_field"] == "red_team_verdict"


def test_fatal_assumptions_carry_no_internal_enum_tokens_or_markdown():
    """D6: `source_field` is a machine key the frontend maps — the assumption itself must read
    as English, with no route enum ('unverified'/'blocked') and no unrendered markdown."""
    ideas = [
        _idea("Blocked", source_pain=CTRL, data_access_model="blocked",
              refine_binding_constraint="The comparison logic is *structurally* generic."),
    ]
    rows = build_idea_theses(ideas, partition=_partition())["theses"][0]["fatal_assumptions"]
    by_field = {r["source_field"]: r["assumption"] for r in rows}
    assert "blocked" not in by_field["data_access_model"]
    assert "'" not in by_field["data_access_model"]
    assert by_field["refine_binding_constraint"] == "The comparison logic is structurally generic."


def test_clean_idea_carries_no_fatal_assumptions():
    ideas = [_idea("Clean", source_pain=CTRL, data_access_model="public", audience_fit=True,
                   data_sources=["FDA NDC Directory"], red_team_verdict="survives")]
    out = build_idea_theses(ideas, partition=_partition())
    assert out["theses"][0]["fatal_assumptions"] == []


def test_uncovered_families_separate_no_cell_from_no_survivor():
    ideas = [_idea("NarcVault", source_pain=CTRL)]
    telemetry = {
        # a cell WAS spent on stockout — nothing survived it
        "cells_by_family": {"controlled": 2, "stockout": 1},
        "families_uncovered": [{"family_id": "billing", "label": "Billing-Consumption Linkage",
                                "reason": "frame_displacement"}],
    }
    out = build_idea_theses(ideas, partition=_partition(), cell_allocation=telemetry)
    by_id = {u["family_id"]: u for u in out["uncovered_families"]}
    assert sorted(by_id) == ["billing", "stockout"]
    assert by_id["stockout"]["reason"] == "no_surviving_idea"
    assert by_id["billing"]["reason"] == "no_cell_allocated"
    assert by_id["billing"]["member_pain_ids"] == [BILLING]
    # D6: `reason` carries the enum; `reason_detail` is prose with no pipeline vocabulary.
    for row in by_id.values():
        detail = row["reason_detail"]
        assert not any(word in detail for word in
                       ("allocator", "cell", "frame_displacement", "budget_exhausted",
                        "no_allocatable_pain", "demotion"))
    assert "idea budget" in by_id["billing"]["reason_detail"]


@pytest.mark.parametrize("raw_reason,expected", [
    ("budget_exhausted", "we ran out of idea budget before reaching this job"),
    ("frame_displacement", "the idea budget went to other angles"),
    ("no_allocatable_pain", "concrete enough to build an idea on"),
    ("some_future_token", "not reached before the idea budget ran out"),
])
def test_uncovered_reason_enum_maps_to_plain_english(raw_reason, expected):
    telemetry = {"cells_by_family": {"controlled": 1},
                 "families_uncovered": [{"family_id": "billing", "reason": raw_reason}]}
    out = build_idea_theses([_idea("NarcVault", source_pain=CTRL)],
                            partition=_partition(), cell_allocation=telemetry)
    billing = next(u for u in out["uncovered_families"] if u["family_id"] == "billing")
    assert expected in billing["reason_detail"]


def test_uncovered_reason_is_unknown_without_allocation_telemetry():
    out = build_idea_theses([_idea("NarcVault", source_pain=CTRL)], partition=_partition())
    assert {u["reason"] for u in out["uncovered_families"]} == {"unknown"}


def test_no_partition_or_degraded_partition_produces_nothing():
    ideas = [_idea("NarcVault", source_pain=CTRL)]
    assert build_idea_theses(ideas, partition=None) == {}
    assert build_idea_theses(ideas, partition=_partition(source="theme_fallback",
                                                         degraded=True)) == {}
