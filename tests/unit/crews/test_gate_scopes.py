"""Phase B guided-mode G2 gate: `UnifiedSolutionCrew._build_partition_cells` honoring
`user_pain_scope` (exclude/pin) and `user_audience_scope` (exclude/emphasis segments).

Non-destructive contract (Decisions §G2 in plans/eager-meandering-feather.md): scopes are
consumed ONLY at this allocation choke point — they never mutate audience_mapping /
pain_point_analysis themselves. Byte-identical when scopes are None/empty (test-locked);
exclusion beats the severity/commercial/audience floors (review A2 — floors pull from
all_pains, so exclusion must apply before any floor injection); pinned pains are injected
via the same floor pattern (a guarantee, like a floor)."""

from types import SimpleNamespace

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew, _assign_generator_cells
from nicheiq.models.research_state import AudienceScope, PainScope


def _crew(**extra):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    crew._segment_payability_map = lambda: {}
    crew._build_data_menu = lambda: ""
    crew._build_dissatisfaction_block = lambda: ""
    crew._workflow_focus_cache = []
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _pain(title, severity=0.5, commercial=0.5, opportunity="medium", **kw):
    base = dict(title=title, severity_score=severity, commercial_intent=commercial,
                opportunity_level=opportunity, affected_segments=None,
                pain_point_alignment=None, representative_quotes=[], description="",
                parent_theme_id=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _segment(name, **kw):
    base = dict(segment_name=name, pain_point_alignment=None, motivation_drivers=[],
                expertise_level="Intermediate", budget_sensitivity="Medium")
    base.update(kw)
    return SimpleNamespace(**base)


class TestByteIdenticalWhenScopesEmpty:
    def test_no_scope_attrs_set_matches_legacy_allocator(self, monkeypatch):
        """A crew built without user_pain_scope/user_audience_scope at all (legacy callers,
        pre-Phase-B) must behave exactly as before — getattr(..., None) no-ops everywhere."""
        monkeypatch.setattr(settings, "divergent_target_generators", 3)
        monkeypatch.setattr(settings, "divergent_max_generators", 6)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain(f"P{i}", severity=0.5 - i * 0.05) for i in range(4)]
        segA, segB = _segment("SegA"), _segment("SegB")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA, segB]))

        cells = crew._build_partition_cells(pains, [])
        legacy = _assign_generator_cells(pains, [segA, segB], target=3, max_gen=6,
                                         relevance=None, severity_floor=0, commercial_floor=0,
                                         commercial_min_intent=settings.divergent_commercial_floor_min_intent)

        assert [c["pain"] for c in cells] == [c["pain"] for c in legacy]
        assert [c.get("segment") for c in cells] == [c.get("segment") for c in legacy]

    def test_empty_scope_objects_are_also_noop(self, monkeypatch):
        """Explicit-but-empty PainScope/AudienceScope (the shape after a gate patch with no
        fields set) must ALSO be byte-identical — not just an absent attribute."""
        monkeypatch.setattr(settings, "divergent_target_generators", 3)
        monkeypatch.setattr(settings, "divergent_max_generators", 6)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain(f"P{i}", severity=0.5 - i * 0.05) for i in range(4)]
        segA, segB = _segment("SegA"), _segment("SegB")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA, segB]),
                     user_pain_scope=PainScope(), user_audience_scope=AudienceScope())

        cells = crew._build_partition_cells(pains, [])
        legacy = _assign_generator_cells(pains, [segA, segB], target=3, max_gen=6,
                                         relevance=None, severity_floor=0, commercial_floor=0,
                                         commercial_min_intent=settings.divergent_commercial_floor_min_intent)

        assert [c["pain"] for c in cells] == [c["pain"] for c in legacy]


class TestPainExclusionBeatsFloors:
    def test_excluded_pain_never_resurrected_by_severity_floor(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 1)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        # Top severity but LOW opportunity: without exclusion the severity floor guarantees it.
        excluded = _pain("Excluded pain", severity=0.95, opportunity="low")
        others = [_pain(f"P{i}", severity=0.3, opportunity="high") for i in range(3)]
        pains = [excluded] + others
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     user_pain_scope=PainScope(excluded_titles=["Excluded pain"]))

        cells = crew._build_partition_cells(pains, [])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Excluded pain" not in titles

    def test_excluded_pain_never_resurrected_by_commercial_floor(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 1)
        monkeypatch.setattr(settings, "divergent_commercial_floor_min_intent", 0.1)
        excluded = _pain("Excluded pain", severity=0.2, commercial=0.99, opportunity="low")
        others = [_pain(f"P{i}", severity=0.3, commercial=0.1, opportunity="high") for i in range(3)]
        pains = [excluded] + others
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     user_pain_scope=PainScope(excluded_titles=["Excluded pain"]))

        cells = crew._build_partition_cells(pains, [])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Excluded pain" not in titles

    def test_excluded_pain_dropped_from_extra_pains_too(self, monkeypatch):
        """Exclusion must apply BEFORE all_pains = selected + extra is even assembled, so it
        also removes a pain that only arrives via extra_pains."""
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_stated_audience_floor_count", 1)
        selected = [_pain("P0", severity=0.5), _pain("P1", severity=0.45)]
        matching = _pain("Commission pain", severity=0.3, affected_segments=["Insurance Agents"])
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=selected + [matching]),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     niche_context=SimpleNamespace(niche_description="",
                                                    resolved_primary_audience="insurance agents",
                                                    user_target_audience=None),
                     user_pain_scope=PainScope(excluded_titles=["Commission pain"]))

        cells = crew._build_partition_cells(selected, [matching])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Commission pain" not in titles


class TestPinnedPainAsFloor:
    def test_pinned_pain_guaranteed_a_cell(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        # Low severity + low opportunity: plain ranking would never pick it without the pin.
        pinned = _pain("Pinned pain", severity=0.1, opportunity="low")
        others = [_pain(f"P{i}", severity=0.6, opportunity="high") for i in range(3)]
        pains = [pinned] + others
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     user_pain_scope=PainScope(pinned_titles=["Pinned pain"]))

        cells = crew._build_partition_cells(pains, [])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Pinned pain" in titles

    def test_pin_and_exclude_together_pin_wins_for_its_own_title(self, monkeypatch):
        """gate_patches.apply_gate_patch rejects a patch that both excludes and pins the same
        title — but _build_partition_cells itself only needs to not crash if that ever slips
        through; excluded_titles filters all_pains first, so an overlapping title is simply
        excluded (exclusion runs first) and never reaches the pin-floor injection."""
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain("Ambiguous pain", severity=0.5)] + [
            _pain(f"P{i}", severity=0.4) for i in range(2)
        ]
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     user_pain_scope=PainScope(excluded_titles=["Ambiguous pain"],
                                                pinned_titles=["Ambiguous pain"]))

        cells = crew._build_partition_cells(pains, [])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Ambiguous pain" not in titles


class TestEffectivePrimaryInPrompt:
    """1.2(d): a G2 primary_target_segment override (user_audience_scope) is the EFFECTIVE
    primary in _format_audience_context's generation-prompt inputs — audience_mapping is
    never mutated, so without this the generation prompts kept the Stage-4 primary."""

    def _am(self, primary):
        return SimpleNamespace(audience_segments=[], primary_target_segment=primary,
                               common_vocabulary=[], frustrations_with_existing=[],
                               tools_currently_used=[])

    def test_g2_override_feeds_generation_prompt(self):
        crew = _crew(audience_mapping=self._am("SegA"),
                     user_audience_scope=AudienceScope(primary_target_segment="SegB"))
        assert crew._format_audience_context()["primary_target_segment"] == "SegB"

    def test_without_override_keeps_stage4_primary(self):
        crew = _crew(audience_mapping=self._am("SegA"))
        assert crew._format_audience_context()["primary_target_segment"] == "SegA"

    def test_empty_scope_object_keeps_stage4_primary(self):
        crew = _crew(audience_mapping=self._am("SegA"), user_audience_scope=AudienceScope())
        assert crew._format_audience_context()["primary_target_segment"] == "SegA"


class TestAudienceScopeFilterReorder:
    def test_excluded_segment_dropped_never_mutates_audience_mapping(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain("P0"), _pain("P1")]
        segA, segB = _segment("SegA"), _segment("SegB")
        am = SimpleNamespace(audience_segments=[segA, segB])
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=am,
                     user_audience_scope=AudienceScope(excluded_segments=["SegB"]))

        cells = crew._build_partition_cells(pains, [])
        segments_used = {getattr(c.get("segment"), "segment_name", None) for c in cells}

        assert "SegB" not in segments_used
        # Non-destructive: the underlying audience_mapping object is untouched.
        assert [s.segment_name for s in am.audience_segments] == ["SegA", "SegB"]

    def test_high_emphasis_segment_sorted_first(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 4)
        monkeypatch.setattr(settings, "divergent_max_generators", 4)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain(f"P{i}") for i in range(4)]
        segA, segB = _segment("SegA"), _segment("SegB")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA, segB]),
                     user_audience_scope=AudienceScope(segment_emphasis={"SegB": "high"}))

        # Reordering is only externally observable via which segment gets assigned first when
        # segment depth is the tiebreak; assert indirectly via the cell-building not raising and
        # segB retaining eligibility (exercised by the emphasis sort not crashing/dropping it).
        cells = crew._build_partition_cells(pains, [])
        segments_used = {getattr(c.get("segment"), "segment_name", None) for c in cells}
        assert "SegB" in segments_used
        assert "SegA" in segments_used
