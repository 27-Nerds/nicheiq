"""Family-first cell allocation + allocation telemetry (docs/DIVERSITY_DECISION_2026-08.md).

Mirrors the severity/commercial/audience floor-cell tests: the buyer-job family is the spreading
key the allocator was missing, and these lock (a) one cell per family before any family's second,
(b) the pre-existing floors still hold, (c) frame cells yield to the family floor, (d) the
allocator never manufactures a family, and (e) the telemetry record.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew, _assign_generator_cells
from nicheiq.utils.buyer_jobs import BuyerJobFamily, BuyerJobPartition
from nicheiq.utils.frames import FrameFocus


def _seg(name):
    return SimpleNamespace(segment_name=name, pain_point_alignment=[],
                           expertise_level="Intermediate", budget_sensitivity="Medium",
                           motivation_drivers=["x"])


def _pain(title, segs, opp="high", sev=0.8, ci=0.0, theme=None):
    return SimpleNamespace(
        title=title, description=f"desc {title}", severity_score=sev, commercial_intent=ci,
        opportunity_level=opp, mention_count=10, affected_segments=list(segs),
        representative_quotes=["q"], parent_theme_id=theme)


def _partition(groups: dict) -> BuyerJobPartition:
    """{family_id: [pain_title, ...]} -> a partition, no LLM."""
    families = tuple(
        BuyerJobFamily(family_id=fid, buyer="b", triggering_job="j", economic_outcome="e",
                       member_pain_ids=tuple(titles), display_label=fid)
        for fid, titles in groups.items())
    return BuyerJobPartition(
        families=families,
        by_pain={t: f.family_id for f in families for t in f.member_pain_ids},
        source="llm")


def _crew(pains, segments, partition=None):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=pains, content_categorization=None)
    crew.audience_mapping = SimpleNamespace(audience_segments=segments,
                                            tools_currently_used=[], frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    crew._data_menu_text = ""
    crew._payability_map = {}
    crew.ruled_out_pains = []
    crew.cell_allocation_telemetry = {}
    crew._buyer_job_partition = partition
    crew._seed_workflow_focuses = lambda: []
    return crew


SEGS = [_seg("Solo"), _seg("Team")]


def _pains_three_families():
    # Family "ledger" owns 3 near-identical pains that dominate the ranking; "billing" and
    # "ordering" each own one lower-ranked pain. Legacy allocation at target=3 spends its budget
    # inside the dominant family (they carry DIFFERENT themes, so the theme cap does not save it).
    return [
        _pain("ledger A", SEGS, sev=0.95, theme="t1"),
        _pain("ledger B", SEGS, sev=0.94, theme="t2"),
        _pain("ledger C", SEGS, sev=0.93, theme="t3"),
        _pain("billing", SEGS, sev=0.50, theme="t4"),
        _pain("ordering", SEGS, sev=0.45, theme="t5"),
    ]


FAMILIES = {"ledger": ["ledger A", "ledger B", "ledger C"],
            "billing": ["billing"], "ordering": ["ordering"]}


class TestFamilyFirstRound:
    def test_one_cell_per_family_before_any_family_takes_a_second(self):
        pains = _pains_three_families()
        family_of = {id(p): next(f for f, t in FAMILIES.items() if p.title in t) for p in pains}
        cells = _assign_generator_cells(pains, SEGS, target=3, max_gen=3, severity_floor=0,
                                        commercial_floor=0, family_of=family_of)

        assert {c["family_id"] for c in cells} == {"ledger", "billing", "ordering"}

    def test_legacy_allocation_is_unchanged_without_a_partition(self):
        pains = _pains_three_families()
        legacy = _assign_generator_cells(pains, SEGS, target=3, max_gen=3, severity_floor=0,
                                         commercial_floor=0)

        assert all("family_id" not in c for c in legacy)
        # The motivating failure: without the family key all 3 cells sit in one buyer job.
        assert {c["pain"].title for c in legacy} <= set(FAMILIES["ledger"])

    def test_never_manufactures_a_family_that_does_not_exist(self):
        pains = _pains_three_families()
        family_of = {id(p): "only-one" for p in pains}
        cells = _assign_generator_cells(pains, SEGS, target=4, max_gen=4, severity_floor=0,
                                        commercial_floor=0, family_of=family_of)

        assert {c["family_id"] for c in cells} == {"only-one"}
        assert len(cells) == 4  # budget still fully spent, just inside the one real family

    def test_severity_floor_survives_family_first_allocation(self):
        # The floored pain is the LOWEST-ranked member of the dominant family — family coverage
        # would never pick it, so only the Round-0 floor can place it.
        pains = _pains_three_families()
        floored = _pain("floored", SEGS, opp="low", sev=0.99, theme="t9")
        pains.append(floored)
        groups = dict(FAMILIES)
        groups["ledger"] = groups["ledger"] + ["floored"]
        family_of = {id(p): next(f for f, t in groups.items() if p.title in t) for p in pains}
        cells = _assign_generator_cells(pains, SEGS, target=3, max_gen=3, severity_floor=1,
                                        commercial_floor=0, family_of=family_of)

        titles = {c["pain"].title for c in cells}
        assert "floored" in titles
        assert {c["family_id"] for c in cells} == {"ledger", "billing", "ordering"}


class TestReserveCarveAndTelemetry:
    def test_frame_cells_yield_to_the_family_floor(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 4)
        monkeypatch.setattr(settings, "divergent_max_generators", 5)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_stated_audience_floor_count", 0)
        pains = _pains_three_families()
        focus = FrameFocus(frame="gap", key="gap:x", payload={"incumbent_name": "X"},
                           anchor_pain_titles=[])
        budgets: list = []

        def _mint(p, s, budget):
            budgets.append(budget)  # the reserve budget the family floor left for frames
            return [{"frame": "gap", "focus": focus, "segment": SEGS[0], "pain": None}
                    for _ in range(budget)]

        crew = _crew(pains, SEGS, partition=_partition(FAMILIES))
        crew._mint_frame_cells = _mint
        cells = crew._build_partition_cells(pains, [])

        pain_cells = [c for c in cells if (c.get("frame") or "pain") == "pain"]
        # 3 families exist, so at least 3 pain cells are protected from the frame subtraction.
        assert budgets == [settings.divergent_max_generators - 3]
        assert len({c["family_id"] for c in pain_cells}) == 3
        assert len(cells) <= settings.divergent_max_generators

    def test_telemetry_records_coverage_reasons_and_degradation(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_stated_audience_floor_count", 0)
        pains = _pains_three_families()
        crew = _crew(pains, SEGS, partition=_partition(FAMILIES))
        crew._build_partition_cells(pains, [])

        t = crew.cell_allocation_telemetry
        assert t["family_source"] == "llm" and t["classifier_degraded"] is False
        assert t["families_available"] == 3
        assert t["families_covered"] == 2          # budget of 2 cannot cover 3 families
        assert [u["reason"] for u in t["families_uncovered"]] == ["budget_exhausted"]
        assert t["pain_cells"] == 2 and t["frame_cells"] == 0
        assert t["cells_allocated"] == 2
        assert all(c["family_id"] for c in t["per_cell"])
        assert t["stage"] == "allocation"

    def test_telemetry_flags_the_degraded_fallback(self):
        pains = _pains_three_families()
        degraded = BuyerJobPartition(
            families=_partition(FAMILIES).families,
            by_pain=_partition(FAMILIES).by_pain,
            source="theme_fallback", degraded=True, degradation_reason="labeler error: boom")
        crew = _crew(pains, SEGS, partition=degraded)
        crew._build_partition_cells(pains, [])

        t = crew.cell_allocation_telemetry
        assert t["classifier_degraded"] is True
        assert t["family_source"] == "theme_fallback"
        assert "boom" in t["degradation_reason"]

    def test_no_partition_reports_not_computed(self):
        pains = _pains_three_families()
        crew = _crew(pains, SEGS, partition=None)
        cells = crew._build_partition_cells(pains, [])

        t = crew.cell_allocation_telemetry
        assert t["family_source"] == "not_computed" and t["classifier_degraded"] is True
        assert t["families_available"] == 0
        assert all("family_id" not in c for c in cells)


class TestPartitionReuseAcrossBatches:
    """A regenerate/seed batch (or a resumed run) builds a FRESH crew. Re-labeling the same pains
    would stamp the batch's ideas with family ids from a DIFFERENT partition — one buyer job
    split across two theses. The persisted partition must win over a fresh labeler call."""

    def _fresh_crew(self, pains, persisted):
        crew = _crew(pains, [_seg("S")], partition=None)
        crew.checkpoint_mgr = SimpleNamespace(state=SimpleNamespace(
            buyer_job_partition=persisted))
        return crew

    def test_persisted_partition_is_reused_without_calling_the_labeler(self):
        pains = [_pain("A", ["S"]), _pain("B", ["S"])]
        persisted = _partition({"ledger": ["A", "B"]}).to_telemetry()
        crew = self._fresh_crew(pains, persisted)

        with patch("nicheiq.utils.buyer_jobs.classify_buyer_job_families") as labeler:
            crew._ensure_buyer_job_partition(pains)
        labeler.assert_not_called()
        assert crew._buyer_job_partition.family_for("A") == "ledger"
        assert crew._buyer_job_partition.family_for("B") == "ledger"

    def test_a_pain_new_to_this_batch_extends_rather_than_re_partitions(self):
        pains = [_pain("A", ["S"]), _pain("B", ["S"]), _pain("NEW", ["S"])]
        persisted = _partition({"ledger": ["A", "B"]}).to_telemetry()
        crew = self._fresh_crew(pains, persisted)

        with patch("nicheiq.utils.buyer_jobs.classify_buyer_job_families") as labeler:
            crew._ensure_buyer_job_partition(pains)
        labeler.assert_not_called()
        part = crew._buyer_job_partition
        assert part.family_for("A") == part.family_for("B") == "ledger"   # unmoved
        assert part.family_for("NEW") not in (None, "ledger")             # its own family

    def test_no_persisted_partition_still_calls_the_labeler_once(self):
        pains = [_pain("A", ["S"]), _pain("B", ["S"])]
        crew = self._fresh_crew(pains, {})
        sentinel = _partition({"ledger": ["A", "B"]})
        with patch("nicheiq.utils.buyer_jobs.classify_buyer_job_families",
                   return_value=sentinel) as labeler:
            crew._ensure_buyer_job_partition(pains)
        labeler.assert_called_once()
        assert crew._buyer_job_partition is sentinel
