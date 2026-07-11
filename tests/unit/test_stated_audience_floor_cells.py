"""Workstream D (audience-rebalance plan, 2026-07-11) — stated-audience floor (Round 0c) in
_assign_generator_cells. Mirrors the A/B-proven severity/commercial floor pattern: cell allocation
ranks by opportunity/theme/severity/commercial and never reads the user's stated audience, so a
pain the user explicitly asked about can get zero ideation while the loudest sub-population fills
every cell (2026-07-11 insurance run: commission-reconciliation pains lost to Applied-Epic AMS
complaints)."""

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import _assign_generator_cells

STATED_AUDIENCE = "insurance agents"


def _seg(name, align=None):
    return SimpleNamespace(segment_name=name, pain_point_alignment=align or [],
                           expertise_level="Intermediate", budget_sensitivity="Medium",
                           motivation_drivers=["x"])


def _pain(title, sev=0.8, opp="high", ci=0.0, theme=None, affected=None, evidence=None):
    return SimpleNamespace(
        title=title, description=f"desc {title}", severity_score=sev,
        commercial_intent=ci, opportunity_level=opp, mention_count=10,
        affected_segments=list(affected) if affected is not None else None,
        evidence_segments=list(evidence) if evidence is not None else None,
        representative_quotes=["q"], parent_theme_id=theme,
    )


SEGS = [_seg("Hobbyist"), _seg("Seller")]


def _titles(cells):
    return [c["pain"].title for c in cells]


class TestStatedAudienceFloor:
    def _pains(self):
        # 'commission' matches the stated audience via affected_segments overlap, but is LOW
        # opportunity + low severity + a crowded theme — the legacy ranking never gives it a cell
        # at target=2.
        return [
            _pain("law A", 0.9, "high", theme="law"),
            _pain("law B", 0.85, "high", theme="law"),
            _pain("oven", 0.8, "high", theme="ops"),
            _pain("commission", 0.4, "low", theme="money", affected=["Insurance Agents"]),
        ]

    def test_floor_zero_excludes_matching_pain(self):
        cells = _assign_generator_cells(self._pains(), SEGS, target=2, max_gen=2,
                                        stated_audience_floor=0, stated_audience=STATED_AUDIENCE)
        assert "commission" not in _titles(cells)  # the live failure mode

    def test_floor_guarantees_top_matching_pain(self):
        cells = _assign_generator_cells(self._pains(), SEGS, target=2, max_gen=2,
                                        stated_audience_floor=1, stated_audience=STATED_AUDIENCE)
        assert "commission" in _titles(cells)

    def test_no_stated_audience_is_noop(self):
        # Both fields None upstream collapses to stated_audience=None here — floor=1 must still
        # no-op rather than guessing.
        cells = _assign_generator_cells(self._pains(), SEGS, target=2, max_gen=2,
                                        stated_audience_floor=1, stated_audience=None)
        assert "commission" not in _titles(cells)

    def test_no_matching_pain_is_noop(self):
        # No pain has a segment overlapping the stated audience — the floor must never manufacture
        # a cell for an unrelated pain (a wrong floor pick is worse than the status quo).
        pains = self._pains()
        pains[-1].affected_segments = ["Hobbyist"]  # no token overlap with "insurance agents"
        cells = _assign_generator_cells(pains, SEGS, target=2, max_gen=2,
                                        stated_audience_floor=1, stated_audience=STATED_AUDIENCE)
        assert "commission" not in _titles(cells)

    def test_evidence_segments_preferred_over_affected_segments(self):
        # affected_segments (lexical) does NOT overlap the stated audience, but evidence_segments
        # (provenance) does — the match must prefer evidence, never fall through to lexical when
        # evidence is present.
        pains = self._pains()
        pains[-1].affected_segments = ["Hobbyist"]
        pains[-1].evidence_segments = ["Insurance Agents"]
        cells = _assign_generator_cells(pains, SEGS, target=2, max_gen=2,
                                        stated_audience_floor=1, stated_audience=STATED_AUDIENCE)
        assert "commission" in _titles(cells)

    def test_no_double_spend_on_severity_floored_pain(self):
        # A pain that's ALSO the top-severity pain gets claimed by the severity floor first; the
        # audience floor must spend its slot elsewhere, never duplicate the cell.
        hero = _pain("hero", 0.95, "high", ci=0.95, theme="hero", affected=["Insurance Agents"])
        other = _pain("law", 0.9, "high", theme="law")
        cells = _assign_generator_cells([hero, other], SEGS, target=2, max_gen=2,
                                        severity_floor=1, stated_audience_floor=1,
                                        stated_audience=STATED_AUDIENCE)
        assert _titles(cells).count("hero") == 1

    def test_never_displaces_severity_or_commercial_floor_pains(self):
        # Tight budget where all three floors compete: severity claims 'hero', commercial claims
        # 'pricing', and the audience floor's own match ('commission') still fits without evicting
        # either already-floored pain.
        hero = _pain("hero", 0.95, "high", ci=0.95, theme="hero")
        pricing = _pain("pricing", 0.4, "low", ci=0.8, theme="money")
        commission = _pain("commission", 0.3, "low", ci=0.1, theme="ops",
                           affected=["Insurance Agents"])
        cells = _assign_generator_cells([hero, pricing, commission], SEGS, target=3, max_gen=3,
                                        severity_floor=1, commercial_floor=1,
                                        commercial_min_intent=0.6, stated_audience_floor=1,
                                        stated_audience=STATED_AUDIENCE)
        t = _titles(cells)
        assert t.count("hero") == 1 and t.count("pricing") == 1 and t.count("commission") == 1

    def test_audience_floor_cannot_claim_a_cell_once_budget_is_exhausted(self):
        # Budget only fits the severity + commercial floor pains — the audience floor's own match
        # must not manufacture an extra cell beyond max_gen, and neither prior floor is evicted.
        hero = _pain("hero", 0.95, "high", ci=0.95, theme="hero")
        pricing = _pain("pricing", 0.4, "low", ci=0.8, theme="money")
        other = _pain("other", 0.2, "low", ci=0.1, theme="ops", affected=["Insurance Agents"])
        cells = _assign_generator_cells([hero, pricing, other], SEGS, target=2, max_gen=2,
                                        severity_floor=1, commercial_floor=1,
                                        commercial_min_intent=0.6, stated_audience_floor=1,
                                        stated_audience=STATED_AUDIENCE)
        t = _titles(cells)
        assert t.count("hero") == 1 and t.count("pricing") == 1
        assert len(cells) == 2
        assert "other" not in t

    def test_floor_zero_byte_identical_to_legacy(self):
        pains = self._pains()
        legacy = _assign_generator_cells(pains, SEGS, target=4, max_gen=6, severity_floor=1)
        dark = _assign_generator_cells(pains, SEGS, target=4, max_gen=6, severity_floor=1,
                                       stated_audience_floor=0, stated_audience=STATED_AUDIENCE)
        assert _titles(legacy) == _titles(dark)
        assert [(getattr(c["segment"], "segment_name", None)) for c in legacy] == \
               [(getattr(c["segment"], "segment_name", None)) for c in dark]
