"""Round 0c-share (2026-08-13) — the stated audience gets a proportional SHARE of generator
cells, not a guaranteed minimum of one.

Live defect (run bab9f696, audience "local businesses in London"): the stated audience's segment
took 1 of 8 cells while a non-target segment took 4. `divergent_stated_audience_floor_count` is a
MINIMUM, so once its one cell is claimed the rest of the budget is allocated audience-blind —
and raising that constant 1 -> 2 -> 3 measurably changed that run's distribution by NOTHING.

The share: `per_seg_cap` (ceil(target / distinct_segments)) is already every segment's
proportional entitlement; the allocator just spends it as a ceiling only. For the ONE segment the
stated audience resolved to, it becomes a floor as well.

These tests assert the PROPERTY (a share that scales with the budget and the segment count),
never a per-run number. Fixtures mirror the real producers: `audience_segments[].segment_name`
verbatim strings, `PainPoint.evidence_segments` / `.affected_segments` holding those same verbatim
segment names, and a stated audience equal to a segment name — which is exactly what
`research_flow._resolve_primary_audience` writes to `resolved_primary_audience` when the user's
audience fuzzy-matched a discovered segment (it falls back to the RAW user string otherwise).
"""

import math
from types import SimpleNamespace

import pytest

from nicheiq.crews.unified_solution_crew import _assign_generator_cells

# Verbatim segment names, shaped like the ones Stage 4 actually emits.
TARGET_SEG = "London Local Service Businesses Managing AI Reputation"
LOUD_SEGS = [
    "Multi-Location Franchises and Central Marketing Teams Auditing Local AI Recommendations",
    "Professional-Service Firms and Their Marketing Teams Auditing AI Brand Sentiment",
    "E-commerce Retailers Preparing Product Catalogs for AI Shopping Assistants",
    "Independent Hotels, Inns, Hostels, and Tourism Operators Reducing OTA Dependence",
]
# A stated audience that did NOT resolve to any segment — `_resolve_primary_audience`'s
# raw-string fallback. This is the real shape of the 2026-08-12 contrast run e1b42702.
UNRESOLVED_AUDIENCE = ("people who want to build their own products, websites, and apps to earn "
                       "additional income on the side")

# LEGACY CONTROL. The stated-audience string with one extra token appended that appears in NO
# segment name. `_tokens()` is a set, so every `_tokens(segment_name) & aud_tokens` intersection
# the legacy Round-0c matcher computes is bit-for-bit unchanged by the addition — the legacy path
# therefore behaves identically — while `_resolved_audience_segment` (exact normalized equality
# against a segment name) now returns None, switching the SHARE off. Anything asserted equal
# between TARGET_SEG and CONTROL_AUDIENCE is a genuine no-op claim about the share alone.
CONTROL_AUDIENCE = TARGET_SEG + " zzqqwxv"


def _seg(name):
    return SimpleNamespace(segment_name=name, pain_point_alignment=[],
                           expertise_level="Intermediate", budget_sensitivity="Medium",
                           motivation_drivers=["x"])


def _pain(title, sev, opp, *, theme, affected=None, evidence=None, ci=0.0):
    return SimpleNamespace(
        title=title, description=f"desc {title}", severity_score=sev, commercial_intent=ci,
        opportunity_level=opp, mention_count=10,
        affected_segments=list(affected) if affected is not None else None,
        evidence_segments=list(evidence) if evidence is not None else None,
        representative_quotes=["q"], parent_theme_id=theme,
    )


def _segs(n):
    """`n` segments with the stated-audience one FIRST (as Stage 4 orders the primary)."""
    return [_seg(TARGET_SEG)] + [_seg(s) for s in LOUD_SEGS[: n - 1]]


def _pool(n_segs, target=6):
    """A pain pool shaped like the live defect: the high-opportunity / high-severity pains all
    carry provenance to the LOUD segments, and the stated audience's pains sit in the low tail.
    That is what makes the audience-blind ranking starve it.

    The loud pool is sized to the budget (`target` + 2) on purpose — with fewer loud pains than
    cells the ordinary rounds run out of them and reach the tail on their own, which would make
    the starvation the defect depends on disappear and leave a test that passes either way."""
    loud = LOUD_SEGS[: max(1, n_segs - 1)]
    pains = []
    for i in range(target + 2):
        s = loud[i % len(loud)]
        pains.append(_pain(f"loud-{i}", 0.90 - i * 0.01, "high", theme=f"loudtheme-{i}",
                           affected=[s], evidence=[s]))
    for i in range(4):
        pains.append(_pain(f"target-{i}", 0.45 - i * 0.02, "low", theme=f"targettheme-{i}",
                           affected=[TARGET_SEG], evidence=[TARGET_SEG]))
    return pains


def _seg_counts(cells):
    out = {}
    for c in cells:
        name = getattr(c["segment"], "segment_name", None) or ""
        out[name] = out.get(name, 0) + 1
    return out


def _shape(cells):
    """Full identity of an allocation: ordered (pain title, segment name) pairs."""
    return [(getattr(c["pain"], "title", None),
             getattr(c["segment"], "segment_name", None)) for c in cells]


def _expected_share(target, n_segs):
    return math.ceil(target / n_segs)


class TestProportionalShare:
    @pytest.mark.parametrize("target,n_segs", [(6, 5), (6, 3), (4, 4), (8, 4), (9, 3)])
    def test_stated_audience_receives_its_proportional_share(self, target, n_segs):
        """PROPERTY: the resolved stated-audience segment holds at least its proportional share
        ceil(target / distinct_segments) — the same number every segment is CAPPED at."""
        segs = _segs(n_segs)
        cells = _assign_generator_cells(
            _pool(n_segs, target), segs, target=target, max_gen=target,
            severity_floor=1, commercial_floor=1, commercial_min_intent=0.4,
            stated_audience_floor=1, stated_audience=TARGET_SEG)
        share = _expected_share(target, n_segs)
        assert _seg_counts(cells).get(TARGET_SEG, 0) >= share

    def test_share_shrinks_as_the_run_finds_more_segments(self):
        """PROPERTY: it is a SHARE, not a constant — the same pain pool and budget yield a
        smaller entitlement when the run discovered more segments to spread across.

        Both arms use segment counts production actually emits. Over the 190-checkpoint corpus
        Stage 4 emits 3 segments on 94 runs, 4 on 55 and 5 on 41, and NEVER 2 — the shape this
        test used to compare against. `target=9` (not the default 6) because ceil(6/3) and
        ceil(6/5) are both 2: at that budget the entitlement is genuinely flat across the range,
        so 6 could not distinguish a share from a constant at all."""
        got = {}
        for n in (3, 5):
            cells = _assign_generator_cells(
                _pool(n, 9), _segs(n), target=9, max_gen=9, severity_floor=1,
                stated_audience_floor=1, stated_audience=TARGET_SEG)
            got[n] = _seg_counts(cells).get(TARGET_SEG, 0)
        assert got[3] == _expected_share(9, 3) > got[5] >= _expected_share(9, 5)

    def test_share_grows_with_the_generator_budget(self):
        """PROPERTY: the entitlement scales with `target`, which an enumerated floor cannot do."""
        small = _assign_generator_cells(
            _pool(3, 3), _segs(3), target=3, max_gen=3, severity_floor=1,
            stated_audience_floor=1, stated_audience=TARGET_SEG)
        big = _assign_generator_cells(
            _pool(3, 9), _segs(3), target=9, max_gen=9, severity_floor=1,
            stated_audience_floor=1, stated_audience=TARGET_SEG)
        assert (_seg_counts(big).get(TARGET_SEG, 0)
                > _seg_counts(small).get(TARGET_SEG, 0))


class TestBoundedness:
    def test_audience_blind_allocation_that_already_over_delivers_is_untouched(self):
        """The audience-blind rounds can hand the stated audience MORE than its share on their
        own (cap relaxation puts every otherwise-unplaceable pain there). Claiming share cells up
        front in that situation stacks on top of that instead of correcting anything — measured on
        the 2026-08-08 small-landlords checkpoint the stated audience went 4 -> 5 of 8 cells while
        a one-cell segment was zeroed. The whole allocation must be identical to legacy here."""
        segs = _segs(5)
        # The stated audience owns the long tail (its pains name no other segment), so relaxation
        # hands it cells well past the share; two loud segments hold the high-opportunity pains.
        pains = [_pain(f"loud-{i}", 0.90 - i * 0.01, "high", theme=f"l{i}",
                       affected=[LOUD_SEGS[i % 2]], evidence=[LOUD_SEGS[i % 2]])
                 for i in range(2)]
        pains += [_pain(f"target-{i}", 0.60 - i * 0.01, "low", theme=f"t{i}",
                        affected=[TARGET_SEG], evidence=[TARGET_SEG]) for i in range(6)]
        kw = dict(target=6, max_gen=6, severity_floor=1, commercial_floor=1,
                  commercial_min_intent=0.4, stated_audience_floor=1)
        blind = _assign_generator_cells(pains, segs, stated_audience=CONTROL_AUDIENCE, **kw)
        assert _seg_counts(blind).get(TARGET_SEG, 0) > _expected_share(6, 5), \
            "fixture guard: the blind allocation must already over-deliver here"
        assert _shape(_assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw)) == \
            _shape(blind)

    def test_already_at_share_gains_nothing(self):
        """Over-serving is as much a defect as under-serving. When earlier rounds already put the
        stated audience at its share, the share round must contribute NOTHING — proven against
        the legacy control, so any residual difference would be the share round's doing."""
        segs = _segs(4)
        # Top-severity + top-commercial pains BOTH sit on the target segment, so the severity and
        # commercial floors alone put it at the share (ceil(6/4) == 2) before Round 0c runs.
        pains = [
            _pain("target-hero", 0.99, "high", ci=0.99, theme="a",
                  affected=[TARGET_SEG], evidence=[TARGET_SEG]),
            _pain("target-money", 0.95, "high", ci=0.95, theme="b",
                  affected=[TARGET_SEG], evidence=[TARGET_SEG]),
            _pain("target-tail", 0.30, "low", theme="c",
                  affected=[TARGET_SEG], evidence=[TARGET_SEG]),
        ] + [_pain(f"loud-{i}", 0.80 - i * 0.01, "high", theme=f"l{i}",
                   affected=[s], evidence=[s]) for i, s in enumerate(LOUD_SEGS[:3])]
        kw = dict(target=6, max_gen=6, severity_floor=1, commercial_floor=1,
                  commercial_min_intent=0.4, stated_audience_floor=1)
        assert _seg_counts(_assign_generator_cells(
            pains, segs, stated_audience=TARGET_SEG, **kw)).get(TARGET_SEG, 0) \
            >= _expected_share(6, 4)
        assert _shape(_assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw)) == \
            _shape(_assign_generator_cells(pains, segs, stated_audience=CONTROL_AUDIENCE, **kw))

    def test_evidenced_segments_are_not_starved(self):
        """The loud, well-evidenced segments must keep cells — the share tops the stated audience
        up to parity, it does not sweep the board."""
        segs = _segs(5)
        cells = _assign_generator_cells(_pool(5), segs, target=6, max_gen=6, severity_floor=1,
                                        stated_audience_floor=1, stated_audience=TARGET_SEG)
        counts = _seg_counts(cells)
        evidenced = [s for s in LOUD_SEGS[:4] if counts.get(s, 0) > 0]
        assert len(evidenced) >= 2
        assert sum(counts.get(s, 0) for s in LOUD_SEGS[:4]) > counts.get(TARGET_SEG, 0)


class TestNoOpCases:
    """A REAL overlap is required: no stated audience, an audience that resolved to no segment,
    or a segment with no provenance edge must all leave allocation exactly as it was."""

    def test_no_stated_audience_at_all(self):
        """Both upstream fields empty collapses to stated_audience=None — the whole round is
        gated off, identical to disabling the setting."""
        segs, pains = _segs(5), _pool(5)
        kw = dict(target=6, max_gen=6, severity_floor=1)
        assert _shape(_assign_generator_cells(
            pains, segs, stated_audience=None, stated_audience_floor=1, **kw)) == \
            _shape(_assign_generator_cells(
                pains, segs, stated_audience=None, stated_audience_floor=0, **kw))

    def test_stated_audience_does_not_name_a_segment(self):
        """`resolved_primary_audience` fell back to the raw user string (the real shape of the
        contrast run e1b42702): there is no segment to give a share TO, so the stated audience is
        NOT topped up — allocation keeps whatever the audience-blind ranking gave it."""
        segs, pains = _segs(5), _pool(5)
        cells = _assign_generator_cells(pains, segs, target=6, max_gen=6, severity_floor=1,
                                        stated_audience_floor=1,
                                        stated_audience=UNRESOLVED_AUDIENCE)
        assert _seg_counts(cells).get(TARGET_SEG, 0) < _expected_share(6, 5)

    def test_resolved_segment_with_no_provenance_edge(self):
        """The audience resolves to a real segment, but NO pain names it in evidence_segments or
        affected_segments — nothing may be manufactured."""
        segs = _segs(5)
        pains = [p for p in _pool(5) if not p.title.startswith("target-")]
        kw = dict(target=6, max_gen=6, severity_floor=1, stated_audience_floor=1)
        assert _shape(_assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw)) == \
            _shape(_assign_generator_cells(pains, segs, stated_audience=CONTROL_AUDIENCE, **kw))

    def test_share_bounded_by_the_edges_that_exist(self):
        """One provenance-linked pain => one cell. The share is an entitlement, not a quota that
        invents placements."""
        segs = _segs(5)
        pains = [p for p in _pool(5) if not p.title.startswith("target-")]
        pains.append(_pain("target-only", 0.30, "low", theme="tt",
                           affected=[TARGET_SEG], evidence=[TARGET_SEG]))
        cells = _assign_generator_cells(pains, segs, target=6, max_gen=6, severity_floor=1,
                                        stated_audience_floor=1, stated_audience=TARGET_SEG)
        assert _seg_counts(cells).get(TARGET_SEG, 0) == 1

    def test_floor_zero_still_disables_everything(self):
        """`divergent_stated_audience_floor_count=0` is documented as byte-identical legacy — the
        share must not resurrect the round behind that switch."""
        segs, pains = _segs(5), _pool(5)
        kw = dict(target=6, max_gen=6, severity_floor=1, stated_audience_floor=0)
        assert _shape(_assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw)) == \
            _shape(_assign_generator_cells(pains, segs, stated_audience=None, **kw))

    def test_legacy_control_string_is_a_true_legacy_equivalent(self):
        """Guard for the control itself: CONTROL_AUDIENCE must differ from TARGET_SEG ONLY in
        switching the share off. If the extra token ever started matching a segment name, every
        no-op assertion above would silently become vacuous."""
        from nicheiq.utils.segment_matching import _tokens
        segs = _segs(5)
        for s in segs:
            name = s.segment_name
            assert (_tokens(name) & _tokens(TARGET_SEG)) == \
                (_tokens(name) & _tokens(CONTROL_AUDIENCE))
            assert name.strip().lower() != CONTROL_AUDIENCE.strip().lower()


class TestPriorGuaranteesIntact:
    def test_severity_and_commercial_floor_pains_keep_their_cells(self):
        """The severity and commercial floors run BEFORE the share and are prior PASSes — the
        share may never displace them."""
        segs = _segs(5)
        pains = _pool(5)
        hero = _pain("hero-severity", 0.99, "low", theme="hero",
                     affected=[LOUD_SEGS[0]], evidence=[LOUD_SEGS[0]])
        money = _pain("hero-commercial", 0.50, "low", ci=0.95, theme="money",
                      affected=[LOUD_SEGS[1]], evidence=[LOUD_SEGS[1]])
        pains = [hero, money] + pains
        cells = _assign_generator_cells(pains, segs, target=6, max_gen=6, severity_floor=1,
                                        commercial_floor=1, commercial_min_intent=0.4,
                                        stated_audience_floor=1, stated_audience=TARGET_SEG)
        titles = [c["pain"].title for c in cells]
        assert "hero-severity" in titles
        assert "hero-commercial" in titles

    def test_allocation_stays_deterministic(self):
        segs, pains = _segs(5), _pool(5)
        kw = dict(target=6, max_gen=6, severity_floor=1, commercial_floor=1,
                  stated_audience_floor=1, stated_audience=TARGET_SEG)
        runs = [_shape(_assign_generator_cells(pains, segs, **kw)) for _ in range(5)]
        assert all(r == runs[0] for r in runs)

    def test_no_pain_is_placed_on_a_segment_it_has_no_edge_to(self):
        """Provenance discipline: every cell the share round creates must sit on a segment the
        pain actually names."""
        segs = _segs(5)
        cells = _assign_generator_cells(_pool(5), segs, target=6, max_gen=6, severity_floor=1,
                                        stated_audience_floor=1, stated_audience=TARGET_SEG)
        for c in cells:
            if getattr(c["segment"], "segment_name", None) != TARGET_SEG:
                continue
            named = set(c["pain"].evidence_segments or []) | set(c["pain"].affected_segments or [])
            assert TARGET_SEG in named, f"{c['pain'].title} placed on the target with no edge"


# ---------------------------------------------------------------------------------------------
# Round 2 (2026-08-13): the share must not be paid for out of the rounds it sits next to.
# ---------------------------------------------------------------------------------------------
# Round 1 placed the share UPSTREAM of the pinned-title round (0d) and the buyer-job family round
# (0e) and spent cells they were going to place. Nothing below existed then: not one of round 1's
# 19 tests passed `family_of` or `pinned_titles` at all.

import random  # noqa: E402  (kept next to the round-2 fixtures it belongs to)


def _families(pains, n_families=3):
    """``id(pain) -> family_id``, the exact shape `_build_partition_cells` passes to the allocator
    (`BuyerJobPartition.family_for_pain` resolved over the same pain objects). Round-robin so
    several families hold SEVERAL pains — a partition where every family has exactly one pain
    cannot exercise the guarantee, because no family ever has a cell to spare."""
    return {id(p): f"fam-{i % n_families}" for i, p in enumerate(pains)}


def _overlapping_pool(n_segs, target, n_target_pains=4):
    """`_pool`, except every pain names TWO segments.

    That is the production shape and `_pool` misses it: `affected_segments` / `evidence_segments`
    are LISTS, and a pain naming exactly one segment gives the allocator no placement choice, so
    `_pick`'s cap relaxation — the mechanism that let the stated audience overshoot its share in
    production — can never fire on it. Every defect this round fixes needed this axis to
    reproduce; on the single-segment `_pool` the round-1 allocator looks clean."""
    loud = LOUD_SEGS[: max(1, n_segs - 1)]
    pains = []
    for i in range(target + 2):
        segs_i = [loud[i % len(loud)]] + ([loud[(i + 1) % len(loud)]] if len(loud) > 1 else [])
        pains.append(_pain(f"loud-{i}", round(0.90 - i * 0.01, 3), "high", ci=0.5,
                           theme=f"loudtheme-{i}", affected=segs_i, evidence=segs_i))
    for i in range(n_target_pains):
        segs_i = [TARGET_SEG, loud[i % len(loud)]]
        pains.append(_pain(f"target-{i}", round(0.45 - i * 0.02, 3), "low", ci=0.5,
                           theme=f"targettheme-{i}", affected=segs_i, evidence=segs_i))
    return pains


def _theme_set(cells):
    return {getattr(c["pain"], "parent_theme_id", None) for c in cells}


def _family_set(cells):
    return {c.get("family_id") for c in cells if c.get("family_id")}


def _arms(pains, segs, target, **extra):
    """The same inputs allocated twice, differing ONLY in whether the share is switched on, so
    every difference is attributable to the share and to nothing else."""
    kw = dict(target=target, max_gen=target, severity_floor=1, commercial_floor=1,
              commercial_min_intent=0.4, stated_audience_floor=1, **extra)
    return (_assign_generator_cells(pains, segs, stated_audience=CONTROL_AUDIENCE, **kw),
            _assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw))


class TestPriorRoundsAreNotSpent:
    """Rounds 0d (`pinned_titles`, the UNCONDITIONAL G2 guided-mode pin) and 0e (`family_of`, the
    round docs/DIVERSITY_DECISION_2026-08.md calls load-bearing) are prior guarantees. The share
    is an entitlement. When the budget cannot satisfy both, the guarantee wins and the share stops
    short."""

    @pytest.mark.parametrize("target", [4, 6])
    def test_a_pinned_pain_is_never_evicted_by_the_share(self, target):
        """PROPERTY: a pinned title the audience-blind allocation placed is still placed.

        `target=4` on 3 segments is the narrow budget the census found the eviction at: the
        severity floor, the commercial floor and a share of 2 consume the whole budget before the
        pin round is reached, so round 1's `len(cells) >= limit` guard silently dropped the pin —
        75 of 463 census pin probes across 9 runs. `target=6` is the shipped budget, where round 1
        happened not to evict; both are asserted so the guarantee is not budget-conditional."""
        segs = _segs(3)
        # A LOW-severity, LOW-opportunity pin on a loud segment: the pain the ordinary ranking
        # would never place on its own, which is the only kind the pin round exists for.
        pin = _pain("pinned-user-choice", 0.10, "low", theme="pinnedtheme",
                    affected=[LOUD_SEGS[0]], evidence=[LOUD_SEGS[0]])
        pains = _pool(3, target) + [pin]
        legacy, share = _arms(pains, segs, target, pinned_titles={"pinned-user-choice"})
        assert "pinned-user-choice" in [c["pain"].title for c in legacy], \
            "fixture guard: the pin round must place the pin when the share is off"
        assert _seg_counts(legacy).get(TARGET_SEG, 0) < _expected_share(target, 3), \
            "fixture guard: the share must be under pressure, or nothing is being tested"
        assert "pinned-user-choice" in [c["pain"].title for c in share]

    def test_a_family_covered_without_the_share_is_still_covered_with_it(self):
        """PROPERTY: the share may not cost the run a buyer-job family — neither the COUNT of
        covered families nor their identity. Trading family A's only cell for family B keeps the
        count and still silently drops a validated buyer job; `families(output) <=
        families(cells)` is a structural bound, so a family with no cell can never come back."""
        segs, target = _segs(3), 4
        pains = _overlapping_pool(3, target, n_target_pains=2)
        legacy, share = _arms(pains, segs, target, family_of=_families(pains))
        assert len(_family_set(legacy)) >= 3, "fixture guard: several families must be covered"
        assert _seg_counts(legacy).get(TARGET_SEG, 0) < _expected_share(target, 3), \
            "fixture guard: the share must be under pressure, or nothing is being tested"
        assert _family_set(legacy) - _family_set(share) == set()
        assert len(_family_set(share)) >= len(_family_set(legacy))

    def test_no_segment_the_blind_allocation_reached_is_zeroed(self):
        """PROPERTY: topping the stated audience up must not silently delete another audience.
        Measured in production on youth-soccer run f7863089: the stated audience went 1 -> 3 and
        'Youth Baseball' went to 0. Five of the 30 census runs zeroed a segment this way."""
        segs, target = _segs(4), 6
        pains = _overlapping_pool(4, target, n_target_pains=3)
        legacy, share = _arms(pains, segs, target, family_of=_families(pains))
        lc, sc = _seg_counts(legacy), _seg_counts(share)
        assert _seg_counts(legacy).get(TARGET_SEG, 0) < _expected_share(target, 4), \
            "fixture guard: the share must be under pressure, or nothing is being tested"
        assert [n for n, v in lc.items() if v > 0 and sc.get(n, 0) == 0] == []

    def test_pins_and_families_hold_together_under_share_pressure(self):
        """Both prior rounds at once — the guided-mode shape: a pinned pain AND a buyer-job
        partition, with the stated audience starved by the audience-blind ranking."""
        segs, target = _segs(3), 4
        pin = _pain("pinned-user-choice", 0.10, "low", theme="pinnedtheme",
                    affected=[LOUD_SEGS[0]], evidence=[LOUD_SEGS[0]])
        pains = _overlapping_pool(3, target, n_target_pains=2) + [pin]
        legacy, share = _arms(pains, segs, target, pinned_titles={"pinned-user-choice"},
                              family_of=_families(pains))
        assert "pinned-user-choice" in [c["pain"].title for c in legacy]
        assert "pinned-user-choice" in [c["pain"].title for c in share]
        assert _family_set(legacy) - _family_set(share) == set()
        assert len(share) == len(legacy)


def _provenance_linked(pain, seg_name=TARGET_SEG) -> bool:
    """The PRECEDENCE rule, restated independently of the implementation under test:
    `evidence_segments` when the pain HAS them, `affected_segments` only when it does not.
    Deliberately NOT imported from `unified_solution_crew` — a test that reuses the production
    predicate cannot detect the production predicate widening back into a union."""
    segs = getattr(pain, "evidence_segments", None) or getattr(pain, "affected_segments", None) or []
    return seg_name in segs


def _draw_evidence(rnd, affected, all_segs):
    """`evidence_segments` for a pain whose lexical `affected_segments` is `affected`, drawn
    INDEPENDENTLY of it in the proportions production actually exhibits.

    Re-derived for round 3 over every cached checkpoint carrying stage_3 pain points — 2737 pains
    across 195 runs:

        evidence_segments is None ............................ 2291 (83.7%)
        non-None, overlapping `affected` but not equal ........  240  (8.8%)
        non-None, DISJOINT from `affected` ...................  145  (5.3%)
        non-None and equal to `affected` as a set ............   61  (2.2%)
        (never [] — the field is either absent or 1-2 names: len 1 on 126, len 2 on 320)

    Rounds 1 and 2 built every fixture with `evidence=affected` on every pain, which is the ONE
    shape (2.2% of production) where the precedence rule and the union it replaced are
    indistinguishable. Under those fixtures the sweep below would pass either implementation, so
    the round-2 correctness change rested entirely on two hand-written point tests. Hence this."""
    if rnd.random() < 0.84:                                  # 83.7% — provenance never computed
        return None
    others = [s for s in all_segs if s not in affected]
    r = rnd.random()
    if r < 0.14 or not others:                               # 2.2/16.3 of the non-None tail
        return list(affected)
    if r < 0.68:                                             # 8.8/16.3 — overlaps, but differs
        return [rnd.choice(list(affected)), rnd.choice(others)]
    return rnd.sample(others, min(len(others), rnd.choice([1, 2])))   # 5.3/16.3 — disjoint


def _generated_shapes(n=400, seed=20260813):
    """Deterministic sweep of production-shaped allocator inputs.

    Fixed seed, so the suite is reproducible and a failure names one concrete counterexample; the
    axes are the ones the real data varies and the hand-built fixtures above cannot cover at once
    — 3-5 segments (the corpus emits 3 on 94 runs, 4 on 55, 5 on 41 and never fewer), pains naming
    one or two segments, mixed opportunity levels, mixed commercial intent, themes shared between
    pains, 2-4 buyer-job families, and (round 3) `evidence_segments` drawn independently of
    `affected_segments` — see `_draw_evidence` for the measured distribution."""
    rnd = random.Random(seed)
    for _ in range(n):
        n_segs = rnd.choice([3, 4, 5])
        target = rnd.choice([4, 5, 6, 8, 9])
        loud = LOUD_SEGS[: n_segs - 1]
        all_segs = [TARGET_SEG] + loud
        pains = []
        n_loud = rnd.randint(1, 10)
        for i in range(n_loud):
            segs_i = rnd.sample(loud, rnd.randint(1, min(2, len(loud))))
            pains.append(_pain(f"loud-{i}", round(rnd.uniform(0.4, 0.99), 3),
                               rnd.choice(["high", "medium", "low"]),
                               theme=f"lt-{rnd.randint(0, n_loud)}", affected=segs_i,
                               evidence=_draw_evidence(rnd, segs_i, all_segs),
                               ci=round(rnd.uniform(0, 1), 2)))
        n_tgt = rnd.randint(1, 6)
        for i in range(n_tgt):
            segs_i = [TARGET_SEG] + ([rnd.choice(loud)] if rnd.random() < 0.35 else [])
            pains.append(_pain(f"target-{i}", round(rnd.uniform(0.1, 0.6), 3),
                               rnd.choice(["high", "medium", "low"]),
                               theme=f"tt-{rnd.randint(0, n_tgt)}", affected=segs_i,
                               evidence=_draw_evidence(rnd, segs_i, all_segs),
                               ci=round(rnd.uniform(0, 1), 2)))
        yield n_segs, target, pains, _families(pains, rnd.choice([2, 3, 4]))


class TestGeneratedShapesAreProductionShaped:
    """Guards for the sweep itself. Every invariant in the class below is only as strong as the
    inputs it runs on, and round 2's inputs were degenerate on the one axis round 2 changed."""

    def test_the_sweep_varies_evidence_independently_of_affected(self):
        """If `evidence_segments` ever collapses back onto `affected_segments`, the precedence
        rule stops being tested by the sweep and nothing else notices. Bands, not pinned counts:
        the point is that all four production shapes are present in usable quantity."""
        kinds = {"none": 0, "equal": 0, "overlapping": 0, "disjoint": 0}
        for _n_segs, _target, pains, _fam in _generated_shapes():
            for p in pains:
                ev, af = p.evidence_segments, set(p.affected_segments or [])
                if ev is None:
                    kinds["none"] += 1
                elif set(ev) == af:
                    kinds["equal"] += 1
                elif set(ev) & af:
                    kinds["overlapping"] += 1
                else:
                    kinds["disjoint"] += 1
        total = sum(kinds.values())
        assert 0.75 <= kinds["none"] / total <= 0.92, kinds       # production: 83.7%
        assert kinds["equal"] / total <= 0.10, kinds              # production: 2.2%
        # The two shapes that make precedence differ from a union at all.
        assert kinds["overlapping"] >= 50 and kinds["disjoint"] >= 50, kinds

    def test_the_sweep_contains_pains_that_precedence_and_a_union_disagree_about(self):
        """The concrete discriminator: a pain lexically naming the stated audience whose COMPUTED
        provenance points elsewhere. A union reads it as evidence for the stated segment;
        precedence does not. Round 2's fixtures contained zero of these."""
        n = sum(1 for _s, _t, pains, _f in _generated_shapes() for p in pains
                if TARGET_SEG in (p.affected_segments or [])
                and p.evidence_segments is not None
                and TARGET_SEG not in p.evidence_segments)
        assert n >= 20, n

    def test_the_sweep_contains_pains_whose_only_edge_is_the_lexical_field(self):
        """The other half of precedence: `evidence_segments=None` (83.7% of production) means the
        provenance pass never ran, so `affected_segments` is the best edge that exists. Dropping
        that fallback must not be invisible to the sweep."""
        n = sum(1 for _s, _t, pains, _f in _generated_shapes() for p in pains
                if p.evidence_segments is None and TARGET_SEG in (p.affected_segments or []))
        assert n >= 100, n


class TestInvariantsOverGeneratedShapes:
    def test_every_generated_shape_keeps_the_prior_rounds_whole_and_the_share_bounded(self):
        """All of the round-2 invariants at once, over 400 generated allocations.

        Each is a PROPERTY of the pair (allocation without the share, allocation with it), never a
        pinned number, and each failure message names the shape that broke it. The share ceiling
        is in here rather than in its own fixture because over-serving needs a specific collision
        — the stated audience below its share in the blind arm AND cap relaxation reaching it
        afterwards — that no readable hand-built pool produced, while the sweep finds it.

        ROUND-3 FINDING — the cell-count invariant was too strong and the round-2 fixtures hid it.
        Round 2 asserted `len(share) == len(legacy)`, from the block comment's claim that the share
        is a pure swap. It is not: `_top_up_stated_share` runs a SPARE-BUDGET loop first, which
        APPENDS while `len(cells) < limit`. Under `evidence == affected` that loop can never fire
        after a full allocation (a pain linked to the stated segment also has it in
        `_candidate_segments_for_pain`, so the ordinary rounds already spent that pairing), which
        is why round 2 never saw it. With evidence drawn independently a loud pain can carry
        provenance to the stated segment while its lexical field does not, the base allocator
        structurally cannot place it there, and the spare loop legitimately does: 6 of the 400
        shapes gain a cell, e.g. shape#51 (n_segs=3 target=8) 6 -> 7 cells, stated 2 -> 3 against
        a share of 3. Zero shapes LOSE a cell. The equality was therefore weakened to the true
        bound — never fewer cells than legacy, never more than the budget — and the direction that
        actually matters (a starved round) is still asserted exactly."""
        broken: list[str] = []
        for i, (n_segs, target, pains, fam) in enumerate(_generated_shapes()):
            legacy, share = _arms(pains, _segs(n_segs), target, family_of=fam)
            lc, sc = _seg_counts(legacy), _seg_counts(share)
            want = _expected_share(target, n_segs)
            tag = f"shape#{i} n_segs={n_segs} target={target} stated {lc.get(TARGET_SEG, 0)}" \
                  f"->{sc.get(TARGET_SEG, 0)} share={want}"
            if len(share) < len(legacy):
                broken.append(f"{tag}: cell count LOST {len(legacy)} -> {len(share)}")
            if len(share) > target:                  # `_arms` passes max_gen=target, so limit=target
                broken.append(f"{tag}: cell count {len(share)} OVERSHOT the budget {target}")
            if sc.get(TARGET_SEG, 0) < lc.get(TARGET_SEG, 0):
                broken.append(f"{tag}: the stated audience LOST cells")
            if lc.get(TARGET_SEG, 0) < want and sc.get(TARGET_SEG, 0) > want:
                broken.append(f"{tag}: overshot its share")
            if _family_set(legacy) - _family_set(share):
                broken.append(f"{tag}: dropped famil(ies) "
                              f"{sorted(_family_set(legacy) - _family_set(share))}")
            if len(_theme_set(share)) < len(_theme_set(legacy)):
                broken.append(f"{tag}: theme coverage {len(_theme_set(legacy))} -> "
                              f"{len(_theme_set(share))}")
            zeroed = [s for s, v in lc.items() if v > 0 and sc.get(s, 0) == 0]
            if zeroed:
                broken.append(f"{tag}: zeroed {[s[:34] for s in zeroed]}")
        assert not broken, "\n".join(broken[:20]) + f"\n({len(broken)} violation(s) total)"

    def test_every_cell_the_share_creates_carries_a_real_provenance_edge(self):
        """PROPERTY (round 3): every (pain × stated segment) pairing that exists WITH the share and
        not without it must be backed by the pain's own provenance under PRECEDENCE —
        `evidence_segments` when computed, `affected_segments` only when it was not.

        This is the invariant round 2's central change actually made, and the one no sweep covered.
        A UNION of the two fields places pains whose computed provenance points at a DIFFERENT
        segment (5 such self-contradicting placements existed across the 30-run census), and every
        other invariant in this class is blind to that: a contradicting placement costs no cell, no
        family, no theme and no segment. Only the delta is examined — a pain the audience-BLIND
        arm already put on the stated segment is the base allocator's doing, not the share's."""
        broken: list[str] = []
        for i, (n_segs, target, pains, fam) in enumerate(_generated_shapes()):
            legacy, share = _arms(pains, _segs(n_segs), target, family_of=fam)
            by_title = {p.title: p for p in pains}
            on_target = lambda cs: {c["pain"].title for c in cs                    # noqa: E731
                                    if getattr(c["segment"], "segment_name", None) == TARGET_SEG}
            for t in sorted(on_target(share) - on_target(legacy)):
                if not _provenance_linked(by_title[t]):
                    p = by_title[t]
                    broken.append(f"shape#{i} n_segs={n_segs} target={target}: '{t}' placed on the "
                                  f"stated segment with evidence={p.evidence_segments} "
                                  f"affected={p.affected_segments}")
        assert not broken, "\n".join(broken[:20]) + f"\n({len(broken)} violation(s) total)"

    def test_the_share_reaches_a_linked_pain_whenever_the_budget_is_spare(self):
        """PROPERTY (round 3): when the ordinary rounds finished UNDER budget, the stated audience
        is under its share, and a provenance-linked pain is not yet placed on it, the share's
        spare-budget loop must take it — nothing has to be given up, so there is no guarantee to
        lose the tie to. This is the path that carries the `evidence_segments=None` majority: drop
        the `or affected_segments` fallback and the linked pain stops being a recipient at all."""
        broken, exercised = [], 0
        for i, (n_segs, target, pains, fam) in enumerate(_generated_shapes()):
            legacy, share = _arms(pains, _segs(n_segs), target, family_of=fam)
            lc, sc = _seg_counts(legacy), _seg_counts(share)
            placed = {c["pain"].title for c in legacy
                      if getattr(c["segment"], "segment_name", None) == TARGET_SEG}
            if len(legacy) >= target or lc.get(TARGET_SEG, 0) >= _expected_share(target, n_segs):
                continue
            if not [p for p in pains if _provenance_linked(p) and p.title not in placed]:
                continue
            exercised += 1
            if sc.get(TARGET_SEG, 0) <= lc.get(TARGET_SEG, 0):
                broken.append(f"shape#{i} n_segs={n_segs} target={target}: {len(legacy)} cells of "
                              f"{target}, stated {lc.get(TARGET_SEG, 0)} unchanged with a linked "
                              f"pain unplaced")
        assert exercised >= 3, f"fixture guard: the spare-budget path was never reached ({exercised})"
        assert not broken, "\n".join(broken[:20])

    def test_the_share_delivers_through_both_halves_of_the_precedence_rule(self):
        """Fixture guard and the `or affected_segments` fallback's teeth, in one measurement.

        Every invariant above is vacuously satisfied by a share round that never moves a cell, so
        the sweep must be shown to deliver — and separately through each half of the precedence
        rule, because the two halves fail independently:

          * shapes whose only pains linked to the stated segment have `evidence_segments=None`
            (production's 83.7% majority) are reachable ONLY through the lexical fallback. 35 of
            183 such shapes gain a stated-audience cell. Drop the fallback and it is exactly 0 —
            those shapes have no recipient at all — while the whole-sweep gain rate only falls
            122 -> 77, which is why an undifferentiated count cannot detect the loss.
          * shapes carrying an evidence-grounded linked pain: 87 of 216.

        Thresholds sit well under both measurements so ordinary drift does not trip them, and far
        above the zero either half collapses to when its half of the rule is removed."""
        lexical_gain = lexical_n = evidence_gain = evidence_n = 0
        for n_segs, target, pains, fam in _generated_shapes():
            linked = [p for p in pains if _provenance_linked(p)]
            if not linked:
                continue
            legacy, share = _arms(pains, _segs(n_segs), target, family_of=fam)
            gained = _seg_counts(share).get(TARGET_SEG, 0) > _seg_counts(legacy).get(TARGET_SEG, 0)
            if all(p.evidence_segments is None for p in linked):
                lexical_n, lexical_gain = lexical_n + 1, lexical_gain + gained
            else:
                evidence_n, evidence_gain = evidence_n + 1, evidence_gain + gained
        assert lexical_gain >= 12, f"lexical-fallback-only shapes: {lexical_gain}/{lexical_n}"
        assert evidence_gain >= 30, f"evidence-grounded shapes: {evidence_gain}/{evidence_n}"


class TestProvenancePrecedence:
    """`_pains_evidencing_segment` promises a REAL provenance edge, and `pain_point.py` documents
    `evidence_segments` as provenance-grounded, `affected_segments` as lexical, and `None` as
    "not computed". Round 1 read the UNION of the two, which let a pain whose provenance WAS
    computed and points at a DIFFERENT segment be placed as evidence for this one — 5 such
    self-contradicting placements existed across the 30-run census, of 18 cells the share created.
    """

    def test_a_pain_whose_provenance_points_elsewhere_is_not_evidence_here(self):
        """The only pain lexically naming the target has computed provenance for a LOUD segment.
        Under the union it is the share's recipient; under precedence it is not evidence for the
        target at all, so the whole allocation must equal the share-off control."""
        segs = _segs(5)
        pains = [p for p in _pool(5) if not p.title.startswith("target-")]
        pains.append(_pain("contradicts-its-own-provenance", 0.30, "low", theme="tt",
                           affected=[TARGET_SEG], evidence=[LOUD_SEGS[0]]))
        kw = dict(target=6, max_gen=6, severity_floor=1, commercial_floor=1,
                  commercial_min_intent=0.4, stated_audience_floor=1)
        assert _shape(_assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw)) == \
            _shape(_assign_generator_cells(pains, segs, stated_audience=CONTROL_AUDIENCE, **kw))

    def test_a_pain_with_no_provenance_computed_still_uses_the_lexical_field(self):
        """Precedence, not evidence-only: `evidence_segments=None` means the provenance pass never
        ran for that pain (legacy rows — and 5 of the 13 cells the share gains across the census),
        so its lexical `affected_segments` is the best edge that exists and must still count."""
        segs = _segs(5)
        pains = [p for p in _pool(5) if not p.title.startswith("target-")]
        pains.append(_pain("lexical-only", 0.30, "low", theme="tt",
                           affected=[TARGET_SEG], evidence=None))
        kw = dict(target=6, max_gen=6, severity_floor=1, commercial_floor=1,
                  commercial_min_intent=0.4, stated_audience_floor=1)
        cells = _assign_generator_cells(pains, segs, stated_audience=TARGET_SEG, **kw)
        assert "lexical-only" in [c["pain"].title for c in cells
                                  if getattr(c["segment"], "segment_name", None) == TARGET_SEG]
