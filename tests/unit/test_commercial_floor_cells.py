"""Item 3 (2026-07-02 plan) — commercial-intent floor (Round 0b) + per-segment fill relaxation in
_assign_generator_cells. Mirrors the A/B-proven severity-floor pattern for commercial_intent, which
the allocation ranking never reads (live: the COGS/labor-pricing calculator cluster got zero cells)."""

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import _assign_generator_cells


def _seg(name, align=None):
    return SimpleNamespace(segment_name=name, pain_point_alignment=align or [],
                           expertise_level="Intermediate", budget_sensitivity="Medium",
                           motivation_drivers=["x"])


def _pain(title, segs, opp="high", sev=0.8, ci=0.0, theme=None):
    return SimpleNamespace(
        title=title, description=f"desc {title}", severity_score=sev,
        commercial_intent=ci, opportunity_level=opp, mention_count=10,
        affected_segments=list(segs), representative_quotes=["q"],
        parent_theme_id=theme,
    )


SEGS = [_seg("Hobbyist"), _seg("Seller")]


def _titles(cells):
    return [c["pain"].title for c in cells]


class TestCommercialFloor:
    def _pains(self):
        # 'pricing' is the monetizable pain (high CI) but LOW opportunity + low severity + a crowded
        # theme — the legacy ranking never gives it a cell at target=2.
        return [
            _pain("law A", SEGS[:1], "high", 0.9, ci=0.2, theme="law"),
            _pain("law B", SEGS[:1], "high", 0.85, ci=0.2, theme="law"),
            _pain("oven", SEGS[1:], "high", 0.8, ci=0.1, theme="ops"),
            _pain("pricing", SEGS[1:], "low", 0.4, ci=0.9, theme="money"),
        ]

    def test_floor_zero_excludes_monetizable_pain(self):
        cells = _assign_generator_cells(self._pains(), SEGS, target=2, max_gen=2,
                                        commercial_floor=0)
        assert "pricing" not in _titles(cells)  # the live failure mode

    def test_floor_guarantees_top_commercial_pain(self):
        cells = _assign_generator_cells(self._pains(), SEGS, target=2, max_gen=2,
                                        commercial_floor=1, commercial_min_intent=0.6)
        assert "pricing" in _titles(cells)

    def test_threshold_gates_weak_signals(self):
        pains = self._pains()
        pains[-1].commercial_intent = 0.4  # below min_intent → no manufactured cell
        cells = _assign_generator_cells(pains, SEGS, target=2, max_gen=2,
                                        commercial_floor=1, commercial_min_intent=0.6)
        assert "pricing" not in _titles(cells)

    def test_no_double_spend_on_severity_floored_pain(self):
        # top-severity pain is ALSO top-commercial: severity floor takes it; commercial floor must
        # spend its slot on the NEXT eligible pain, not duplicate.
        pains = [
            _pain("hero", SEGS, "high", 0.95, ci=0.95, theme="hero"),
            _pain("pricing", SEGS[1:], "low", 0.4, ci=0.8, theme="money"),
            _pain("law", SEGS[:1], "high", 0.9, ci=0.2, theme="law"),
        ]
        cells = _assign_generator_cells(pains, SEGS, target=3, max_gen=3,
                                        severity_floor=1, commercial_floor=1,
                                        commercial_min_intent=0.6)
        t = _titles(cells)
        assert t.count("hero") == 1 and "pricing" in t

    def test_floor_zero_byte_identical_to_legacy(self):
        pains = self._pains()
        legacy = _assign_generator_cells(pains, SEGS, target=4, max_gen=6, severity_floor=1)
        dark = _assign_generator_cells(pains, SEGS, target=4, max_gen=6, severity_floor=1,
                                       commercial_floor=0, commercial_min_intent=0.6)
        assert _titles(legacy) == _titles(dark)
        assert [(getattr(c["segment"], "segment_name", None)) for c in legacy] == \
               [(getattr(c["segment"], "segment_name", None)) for c in dark]
