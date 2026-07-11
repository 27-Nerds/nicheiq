"""Tests for diversity-aware final selection:
- `_enforce_diversity_caps` (drop-only, floor-protected, bold/sole-coverage protected, greedy mechanism families)
- the (pain × data_source) dedup stage in `_pool_and_dedup_raw_concepts`
"""
from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc


def _idea(name, seg, pt, mech, nov=0.4, mf=0.7):
    return SimpleNamespace(
        solution_name=name, source_segment=seg, project_type=pt, mechanism_tag=mech,
        novelty_score=nov, market_fit_score=mf, technical_feasibility_score=0.7,
        seo_scalability_score=0.7, pain_points_addressed=[], value_proposition="", headline="",
    )


def _crew(monkeypatch, **caps):
    monkeypatch.setattr(usc.settings, "enable_diversity_caps", True)
    monkeypatch.setattr(usc.settings, "diversity_max_final_ideas", caps.get("max_final", 10))
    monkeypatch.setattr(usc.settings, "diversity_min_final_ideas", caps.get("min_final", 5))
    monkeypatch.setattr(usc.settings, "diversity_max_per_segment", caps.get("seg", 2))
    monkeypatch.setattr(usc.settings, "diversity_max_per_mechanism", caps.get("mech", 2))
    monkeypatch.setattr(usc.settings, "diversity_max_per_project_type", caps.get("ptype", 3))
    c = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
    c.pain_point_analysis = SimpleNamespace(pain_points=[])
    return c


class TestDiversityCaps:
    def test_segment_cap_drops_weakest_excess(self, monkeypatch):
        crew = _crew(monkeypatch)
        ideas = [
            _idea("A", "RCB", "aggregator", "m1", mf=0.9),
            _idea("B", "RCB", "aggregator", "m2", mf=0.85),
            _idea("C", "RCB", "aggregator", "m3", mf=0.8),   # 3rd RCB -> dropped (weakest)
            _idea("D", "Body", "saas", "m4", mf=0.75),
            _idea("E", "Injury", "aggregator", "m5", mf=0.7),
            _idea("F", "Body", "comparison-tool", "m6", mf=0.65),
        ]
        crew._enforce_diversity_caps(ideas)
        names = [i.solution_name for i in ideas]
        assert "C" not in names               # weakest 3rd RCB dropped
        assert sum(i.source_segment == "RCB" for i in ideas) == 2  # segment cap held

    def test_floor_readmits_below_min(self, monkeypatch):
        # max_per_segment=1 would cut hard; floor=4 forces re-admission of best dropped.
        crew = _crew(monkeypatch, seg=1, min_final=4)
        ideas = [_idea(n, "RCB", "aggregator", f"m{i}", mf=0.9 - i * 0.1)
                 for i, n in enumerate("ABCDE")]
        crew._enforce_diversity_caps(ideas)
        assert len(ideas) == 4   # seg cap=1 would give 1; floor re-admits to 4

    def test_protects_only_top_novel_idea(self, monkeypatch):
        # Single most-novel idea is protected even when it's the weakest by fit; a SECOND
        # high-novelty idea is not auto-protected (so caps still bite when novelty is inflated).
        crew = _crew(monkeypatch, seg=1, min_final=2, max_final=10)
        ideas = [
            _idea("Strong", "RCB", "saas", "m1", nov=0.7, mf=0.95),    # bold-ish, strongest fit
            _idea("TopNovel", "RCB", "saas", "m2", nov=0.95, mf=0.4),  # most novel, weak fit
            _idea("Filler", "RCB", "saas", "m3", nov=0.2, mf=0.6),
        ]
        crew._enforce_diversity_caps(ideas)
        names = [i.solution_name for i in ideas]
        assert "TopNovel" in names   # single most-novel protected despite weak fit + seg cap=1
        assert "Filler" not in names  # cap still drops the excess (protection isn't blanket)

    def test_protects_sole_pain_coverage(self, monkeypatch):
        crew = _crew(monkeypatch, seg=1)
        crew.pain_point_analysis = SimpleNamespace(pain_points=[
            SimpleNamespace(title="vial stability degradation", categories=[], severity_score=0.9, mention_count=20),
        ])
        weak = _idea("Solo", "RCB", "saas", "m2", nov=0.2, mf=0.5)
        weak.value_proposition = "keep your vial stable and prevent degradation"
        strong = _idea("Other", "RCB", "aggregator", "m1", nov=0.2, mf=0.95)
        ideas = [strong, weak]
        crew._enforce_diversity_caps(ideas)
        # 'Solo' is the only idea covering the high-sev pain -> protected despite seg cap + low score
        assert "Solo" in [i.solution_name for i in ideas]

    def test_greedy_mechanism_family_cap(self, monkeypatch):
        crew = _crew(monkeypatch, seg=10, ptype=10, mech=2)  # only mechanism cap binds
        ideas = [
            _idea("A", "S1", "saas", "aggregates public lab logs", mf=0.9),
            _idea("B", "S2", "saas", "aggregates public lab records", mf=0.85),  # same family as A
            _idea("C", "S3", "saas", "aggregates public lab data", mf=0.8),      # 3rd in family -> dropped
            _idea("D", "S4", "saas", "visual dose calculator", mf=0.75),
            _idea("E", "S5", "saas", "scam signal tracker", mf=0.7),
            _idea("F", "S6", "saas", "regulatory alert feed", mf=0.6),
        ]
        crew._enforce_diversity_caps(ideas)
        assert "C" not in [i.solution_name for i in ideas]  # 3rd "aggregates public lab*" dropped

    def test_noop_when_disabled_or_small(self, monkeypatch):
        crew = _crew(monkeypatch, min_final=5)
        monkeypatch.setattr(usc.settings, "enable_diversity_caps", False)
        ideas = [_idea(n, "RCB", "aggregator", "m") for n in "ABCDEFG"]
        crew._enforce_diversity_caps(ideas)
        assert len(ideas) == 7  # disabled -> untouched

    def test_equal_composite_tiebreak_by_name_regardless_of_input_order(self, monkeypatch):
        # 2026-07-10 audit: completion-order tie-breaking made cap results depend on network
        # latency. Two ideas tied on composite (same segment, mechanism cap disabled) must
        # resolve the segment-cap slot the SAME way regardless of which one is first in the
        # input list — normalized solution_name breaks the tie.
        crew = _crew(monkeypatch, seg=1, mech=10, ptype=10, min_final=1, max_final=10)
        alpha_first = [
            _idea("Alpha", "RCB", "saas", "m1", nov=0.4, mf=0.7),
            _idea("Zebra", "RCB", "saas", "m2", nov=0.4, mf=0.7),
        ]
        zebra_first = [
            _idea("Zebra", "RCB", "saas", "m2", nov=0.4, mf=0.7),
            _idea("Alpha", "RCB", "saas", "m1", nov=0.4, mf=0.7),
        ]
        for ideas in (alpha_first, zebra_first):
            crew._enforce_diversity_caps(ideas)
            assert [i.solution_name for i in ideas] == ["Alpha"]


class TestPainSourceDedup:
    def _rc(self, name, pain, source):
        from nicheiq.models.solution_idea import RawConcept
        return RawConcept(
            concept_name=name, one_liner=f"{name} does a thing", ideation_technique="atomic_feature",
            project_type="aggregator", target_keywords=["a", "b"], source_pain=pain, data_source_tag=source,
        )

    def test_collapses_same_pain_same_source(self, monkeypatch):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_semantic_dedup", lambda c, t: c, raising=False)
        monkeypatch.setattr(usc.settings, "enable_pain_source_dedup", True)
        monkeypatch.setattr(usc.settings, "divergent_pool_cap", 15)
        monkeypatch.setattr(usc.settings, "divergent_keep_fraction", 0.9)
        # Two share (pain, source); enough others to clear the MIN_KEEP=6 floor.
        concepts = [
            self._rc("PurityRouter", "verify purity", "janoshik-coa"),
            self._rc("VendorAudit", "verify purity", "janoshik-coa"),  # dup of PurityRouter
            self._rc("D", "predict effects", "pubmed"),
            self._rc("E", "no clinical data", "pubmed"),
            self._rc("F", "dosing", "calculator"),
            self._rc("G", "policy", "fda-csv"),
            self._rc("H", "recovery", "user-submitted"),
        ]
        out = crew._pool_and_dedup_raw_concepts(concepts)
        names = [c.concept_name for c in out]
        assert not ("PurityRouter" in names and "VendorAudit" in names)  # one collapsed

    def test_noop_when_source_pain_none(self, monkeypatch):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_semantic_dedup", lambda c, t: c, raising=False)
        monkeypatch.setattr(usc.settings, "enable_pain_source_dedup", True)
        monkeypatch.setattr(usc.settings, "divergent_pool_cap", 15)
        monkeypatch.setattr(usc.settings, "divergent_keep_fraction", 0.9)
        # All source_pain None (legacy path) + distinct M/D/J -> must NOT collapse on the None bucket.
        concepts = []
        from nicheiq.models.solution_idea import RawConcept
        for i, n in enumerate("ABCDEFG"):
            concepts.append(RawConcept(
                concept_name=n, one_liner=f"{n} x", ideation_technique="atomic_feature",
                project_type="saas", target_keywords=["a", "b"],
                mechanism_tag=f"mech-{i}", data_source_tag=f"src-{i}", journey_tag=f"j-{i}"))
        out = crew._pool_and_dedup_raw_concepts(concepts)
        assert len(out) == 7  # nothing collapsed despite all source_pain=None


class TestValidateIdeaScores:
    """Deterministic downgrade-only score backstop (wired after calibration in execute_pipeline):
    novelty ≤ 1−obviousness, market_fit ≤ 0.4 on unverified data, per-pain concentration caveat.
    Never inflates; zero false positives on clean ideas.
    """
    def _crew(self):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        crew.coverage_caveats = []
        return crew

    def _i(self, name, nov=0.4, obv=0.6, mf=0.3, dam=None, bf=0.8, pain="P"):
        return SimpleNamespace(solution_name=name, novelty_score=nov, obviousness_score=obv,
                               market_fit_score=mf, data_access_model=dam,
                               build_feasibility_score=bf, source_pain=pain)

    def test_caps_novelty_to_one_minus_obviousness(self):
        crew = self._crew()
        idea = self._i("Over", nov=0.8, obv=0.5)   # originality 0.5, novelty overstates by 0.3 (>0.25)
        flags = crew._validate_idea_scores([idea])
        assert idea.novelty_score == 0.5 and "Over" in flags

    def test_caps_market_fit_on_unverified_data(self):
        crew = self._crew()
        idea = self._i("Gray", mf=0.85, dam="unofficial")
        crew._validate_idea_scores([idea])
        assert idea.market_fit_score == 0.4

    def test_caps_market_fit_on_low_build_feasibility(self):
        crew = self._crew()
        idea = self._i("Hard", mf=0.7, dam="official", bf=0.3)   # buildable route but bf<0.5
        crew._validate_idea_scores([idea])
        assert idea.market_fit_score == 0.4

    def test_clean_idea_untouched_no_false_positive(self):
        crew = self._crew()
        idea = self._i("Clean", nov=0.4, obv=0.6, mf=0.4, dam="official", bf=0.8)
        flags = crew._validate_idea_scores([idea])
        assert flags == {} and idea.novelty_score == 0.4 and idea.market_fit_score == 0.4

    def test_never_inflates(self):
        crew = self._crew()
        idea = self._i("Low", nov=0.2, obv=0.1, mf=0.3, dam="official")  # 1−obv=0.9 but nov stays 0.2
        crew._validate_idea_scores([idea])
        assert idea.novelty_score == 0.2

    def test_per_pain_concentration_caveat(self):
        crew = self._crew()
        cap = usc.settings.diversity_max_per_segment
        ideas = [self._i(f"id{i}", pain="same pain") for i in range(cap + 1)]
        crew._validate_idea_scores(ideas)
        assert any("share" not in c and "address one pain" in c for c in crew.coverage_caveats)


class TestCarryProvenance:
    def _rc(self, name, **kw):
        from nicheiq.models.solution_idea import RawConcept
        defaults = dict(one_liner=f"{name} concept", ideation_technique="atomic_feature",
                        project_type="saas", target_keywords=["alpha", "beta"])
        defaults.update(kw)
        return RawConcept(concept_name=name, **defaults)

    def _crew_pc(self, monkeypatch, grounded=None):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_grounded_pains_for", lambda p, s, cap=5: (grounded or []),
                            raising=False)
        # Fix #3b: _carry_provenance no longer copies the concept's (load-balanced) source_segment;
        # on a successful join it RE-DERIVES honest provenance from the pain. Stub it here so these
        # join tests observe "re-derivation fired" without wiring the full segment matcher (that
        # logic is covered in test_ideation_quality_fixes.py).
        monkeypatch.setattr(crew, "_provenance_segment_for_pain", lambda p: "REDERIVED",
                            raising=False)
        return crew

    def test_exact_name_carries_provenance(self, monkeypatch):
        crew = self._crew_pc(monkeypatch, grounded=["the real pain"])
        rc = self._rc("PurityRouter", mechanism_tag="aggregates-coa", data_source_tag="janoshik",
                      journey_tag="verifies-purity", obviousness_score=0.2,
                      source_pain="verify purity", source_segment="Skincare Enthusiasts")
        raw = SimpleNamespace(concepts=[rc])
        sol = SimpleNamespace(solution_name="PurityRouter", value_proposition="", headline="",
                              pain_points_addressed=[], source_segment=None, source_pain=None,
                              mechanism_tag=None, data_source_tag=None, journey_tag=None,
                              obviousness_score=None)
        refined = SimpleNamespace(solution_ideas=[sol])
        hits = crew._carry_provenance(refined, raw)
        assert hits == 0  # exact match, not fuzzy
        assert sol.source_segment == "REDERIVED"  # Fix #3b: re-derived on join, not carried
        assert sol.mechanism_tag == "aggregates-coa"
        assert sol.pain_points_addressed == ["the real pain"]  # code-filled

    def test_filter_paraphrase_of_source_pain_is_restored(self, monkeypatch):
        # Regression: the Stage-5_2 filter LLM PARAPHRASES source_pain ("...overwhelm grassroots
        # organizers" -> "LAN party infrastructure logistics"), which alone would break the title-
        # keyed joins (coverage / keyword-seed / report_consistency). _carry_provenance re-asserts
        # the CANONICAL concept title via exact name match, so the refined idea rejoins Stage-3.
        # Verified on run 947eb269: 7/7 restored, 0 fuzzy — the audit's "ideas join to no title"
        # was an artifact of inspecting the pre-carry stage_5_3 checkpoint (saved before this runs).
        canonical = "LAN party infrastructure and logistics overwhelm grassroots organizers"
        crew = self._crew_pc(monkeypatch, grounded=[canonical])
        rc = self._rc("CircuitStrike", source_pain=canonical, source_segment="Casual Community Builders")
        raw = SimpleNamespace(concepts=[rc])
        sol = SimpleNamespace(solution_name="CircuitStrike", value_proposition="", headline="",
                              pain_points_addressed=[],
                              source_pain="LAN party infrastructure logistics",  # the filter paraphrase
                              source_segment="Casual Community Builders",
                              mechanism_tag=None, data_source_tag=None, journey_tag=None,
                              obviousness_score=None)
        refined = SimpleNamespace(solution_ideas=[sol])
        hits = crew._carry_provenance(refined, raw)
        assert hits == 0                          # exact name match (no fuzzy needed)
        assert sol.source_pain == canonical       # paraphrase overwritten with the canonical title

    def test_renamed_idea_fuzzy_matches(self, monkeypatch):
        crew = self._crew_pc(monkeypatch, grounded=["purity pain"])
        # strong overlap target
        match = self._rc("VendorCoAComparator",
                         one_liner="compare peptide vendor certificate analysis lab purity results",
                         target_keywords=["vendor coa comparison", "peptide lab purity"],
                         mechanism_tag="curated-comparison-pages", source_pain="verify purity",
                         source_segment="Experienced Buyers")
        distractor = self._rc("DoseTitrationPlanner",
                              one_liner="weekly glp1 dose escalation schedule generator",
                              target_keywords=["glp1 dose", "titration schedule"],
                              source_pain="dosing", source_segment="Tirzepatide Users")
        raw = SimpleNamespace(concepts=[match, distractor])
        sol = SimpleNamespace(  # refiner RENAMED it; blob still overlaps the comparator concept
            solution_name="PeptideVendorTrustScore",
            value_proposition="compare peptide vendor certificate analysis lab purity results",
            headline="vendor coa comparison", pain_points_addressed=[],
            source_segment="Generic Guess", source_pain=None,
            mechanism_tag=None, data_source_tag=None, journey_tag=None, obviousness_score=None)
        refined = SimpleNamespace(solution_ideas=[sol])
        hits = crew._carry_provenance(refined, raw)
        assert hits == 1
        assert sol.source_segment == "REDERIVED"   # Fix #3b: re-derived on join, overrides the guess
        assert sol.mechanism_tag == "curated-comparison-pages"

    def test_ambiguous_match_leaves_value(self, monkeypatch):
        crew = self._crew_pc(monkeypatch)
        # two identical-blob concepts -> best ties runner-up -> margin fails -> no assignment
        a = self._rc("TwinA", one_liner="peptide purity lab verification tool",
                     target_keywords=["peptide purity", "lab verification"],
                     source_segment="Seg A", source_pain="purity")
        b = self._rc("TwinB", one_liner="peptide purity lab verification tool",
                     target_keywords=["peptide purity", "lab verification"],
                     source_segment="Seg B", source_pain="purity")
        raw = SimpleNamespace(concepts=[a, b])
        sol = SimpleNamespace(solution_name="SomethingRenamed",
                              value_proposition="peptide purity lab verification tool",
                              headline="", pain_points_addressed=[],
                              source_segment="Kept Guess", source_pain=None,
                              mechanism_tag=None, data_source_tag=None, journey_tag=None,
                              obviousness_score=None)
        refined = SimpleNamespace(solution_ideas=[sol])
        hits = crew._carry_provenance(refined, raw)
        assert hits == 0
        assert sol.source_segment == "Kept Guess"   # ambiguous -> unchanged

    def test_renamed_idea_cannot_steal_claimed_concept(self, monkeypatch):
        # A renamed idea whose best blob match is a concept ALREADY exact-claimed by another
        # idea must NOT take that concept's provenance; the only unclaimed concept is unrelated
        # (low overlap) -> renamed idea keeps its own value.
        crew = self._crew_pc(monkeypatch)
        purity = self._rc("PurityDB", one_liner="peptide purity contamination lab verification",
                          target_keywords=["peptide purity", "contamination lab"],
                          source_segment="Seg-Claimed", source_pain="purity")
        dosing = self._rc("DosingCalc", one_liner="weekly glp1 dose titration escalation schedule",
                          target_keywords=["glp1 dose", "titration"],
                          source_segment="Seg-Free", source_pain="dosing")
        raw = SimpleNamespace(concepts=[purity, dosing])
        exact = SimpleNamespace(solution_name="PurityDB", value_proposition="", headline="",
                                pain_points_addressed=[], source_segment=None, source_pain=None,
                                mechanism_tag=None, data_source_tag=None, journey_tag=None,
                                obviousness_score=None)
        renamed = SimpleNamespace(  # blob overlaps PurityDB strongly, DosingCalc not at all
            solution_name="PeptidePurityChecker",
            value_proposition="peptide purity contamination lab verification",
            headline="", pain_points_addressed=[], source_segment="Own Guess", source_pain=None,
            mechanism_tag=None, data_source_tag=None, journey_tag=None, obviousness_score=None)
        refined = SimpleNamespace(solution_ideas=[exact, renamed])
        hits = crew._carry_provenance(refined, raw)
        assert exact.source_segment == "REDERIVED"       # Fix #3b: re-derived on the exact-match join
        assert renamed.source_segment == "Own Guess"     # could not steal the claimed sibling → untouched
        assert hits == 0

    def test_no_raw_concepts_noop(self, monkeypatch):
        crew = self._crew_pc(monkeypatch)
        sol = SimpleNamespace(solution_name="X", value_proposition="", headline="",
                              pain_points_addressed=[], source_segment="keep")
        refined = SimpleNamespace(solution_ideas=[sol])
        assert crew._carry_provenance(refined, None) == 0
        assert sol.source_segment == "keep"


class TestPainCoverageSummary:
    def _pain(self, title, level="high"):
        return SimpleNamespace(title=title, opportunity_level=SimpleNamespace(value=level))

    def _crew(self, pains, existing_caveats=None):
        c = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        c.pain_point_analysis = SimpleNamespace(pain_points=pains)
        c.coverage_caveats = list(existing_caveats or [])
        return c

    def test_flags_concentration(self):
        pains = [self._pain("Purity"), self._pain("Dosing"), self._pain("Injection")]
        crew = self._crew(pains)
        ideas = [SimpleNamespace(source_pain=p) for p in
                 ("Purity", "Purity", "Purity", "Purity", "Dosing", "Injection")]
        crew._pain_coverage_summary(ideas)
        assert any("4 of 6 ideas address" in c and "Purity" in c for c in crew.coverage_caveats)

    def test_lists_uncovered_validated_pains(self):
        pains = [self._pain("Purity"), self._pain("Dosing"), self._pain("Oral collagen", "medium"),
                 self._pain("Low priority", "low")]
        crew = self._crew(pains)
        ideas = [SimpleNamespace(source_pain="Purity"), SimpleNamespace(source_pain="Dosing")]
        crew._pain_coverage_summary(ideas)
        note = " ".join(crew.coverage_caveats)
        assert "Oral collagen" in note          # uncovered medium pain surfaced
        assert "Low priority" not in note        # low-opportunity pains not nagged

    def test_noop_when_balanced_and_covered(self):
        pains = [self._pain("Purity"), self._pain("Dosing"), self._pain("Injection")]
        crew = self._crew(pains)
        ideas = [SimpleNamespace(source_pain=p) for p in ("Purity", "Dosing", "Injection")]
        crew._pain_coverage_summary(ideas)
        assert crew.coverage_caveats == []       # no concentration, no uncovered -> silent

    def test_appends_not_overwrites(self):
        pains = [self._pain("Purity"), self._pain("Dosing")]
        crew = self._crew(pains, existing_caveats=["pre-existing caveat"])
        ideas = [SimpleNamespace(source_pain="Purity")] * 3
        crew._pain_coverage_summary(ideas)
        assert "pre-existing caveat" in crew.coverage_caveats
        assert len(crew.coverage_caveats) == 2   # original + the new note
