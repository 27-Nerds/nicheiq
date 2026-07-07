"""Mechanism-parity probe (A/B-validated, always on) — web-verify whether incumbents already
SHIP each idea's core mechanism, then re-score ALL ideas with the evidence in critic context.

Probe-all (2026-07-06, was top-K): a second evidence-informed critic pass for some ideas but not
others polluted the relative ranking. After the re-score, caps are re-asserted and the classifier
outputs cleared so _classify_idea_angles re-derives every idea's rationale against final scores.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews.unified_solution_crew import _CRITIC_BATCH, UnifiedSolutionCrew

_CLASSIFIER_FIELDS = ("winning_angle", "angle_rationale", "novelty_rationale",
                      "differentiation_locus")


def _idea(name, mf, vp="route optimization for mobile groomers", mech="route-optimizer"):
    return SimpleNamespace(
        solution_name=name, market_fit_score=mf, technical_feasibility_score=mf,
        novelty_score=mf, seo_scalability_score=mf, value_proposition=vp,
        technical_approach="deterministic routing engine", mechanism_tag=mech,
        incumbent_parity=None,
        # in-cell classifier outputs that the probe must clear for re-derivation
        winning_angle="novel_differentiation", angle_rationale="old angle rationale",
        novelty_rationale="Low mechanism-novelty (0.45) is expected here.",
        differentiation_locus="old locus")


def _crew(with_search=True):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="mobile dog groomers")
    crew.search_tool = (SimpleNamespace(run=lambda search_query: "MoeGo Smart Schedule route optimization")
                        if with_search else None)
    crew.cost_tracker = None
    crew._incumbent_probe_text = "### Web-probed incumbent products..."   # cached
    crew._incumbent_rows = [{"name": "MoeGo", "pricing": "$50/mo",
                             "focus": "grooming scheduling and route optimization", "gap": ""}]
    crew._recalibrated = []
    crew._calibrate_batch = lambda **kw: crew._recalibrated.append(kw) or (len(kw["batch"]), None)
    return crew


def _finding(idea_name, parity="shipped", covered_by="MoeGo",
             evidence="Smart Schedule route optimization"):
    return SimpleNamespace(idea_name=idea_name, covered_by=covered_by,
                           evidence=evidence, parity=parity)


class TestParityProbe:
    # probe is unconditional since the 2026-07-02 A/B (flag removed; groomers mean
    # panel-distance 0.083 -> 0.047); probe-all since 2026-07-06 (top-K tunable removed)

    def test_all_ideas_probed_and_rescored_with_evidence(self):
        crew = _crew()
        ideas = [_idea("Top1", 0.75), _idea("Top2", 0.70), _idea("Low", 0.30)]
        fake = SimpleNamespace(findings=[_finding("Top1"),
                                         _finding("Top2", parity="none", covered_by=""),
                                         _finding("Low", parity="none", covered_by="")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        assert ideas[0].incumbent_parity == "shipped by MoeGo: Smart Schedule route optimization"
        assert ideas[1].incumbent_parity == "none found"
        assert ideas[2].incumbent_parity == "none found"   # no idea left below a top-K cut
        # EVERY idea re-calibrated (uniform pass), with the parity evidence in context
        recal = [i.solution_name for kw in crew._recalibrated for i in kw["batch"]]
        assert sorted(recal) == ["Low", "Top1", "Top2"]
        for kw in crew._recalibrated:
            assert "MECHANISM PARITY CHECK" in kw["extra_context"]
            assert "never raise scores on absence of evidence" in kw["extra_context"]
        assert "shipped by MoeGo" in crew._recalibrated[0]["extra_context"]

    def test_recalibration_batched_by_critic_batch(self):
        crew = _crew()
        n = _CRITIC_BATCH + 2
        ideas = [_idea(f"I{k}", 0.5) for k in range(n)]
        fake = SimpleNamespace(findings=[_finding(f"I{k}", parity="none", covered_by="")
                                         for k in range(n)])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        assert len(crew._recalibrated) == 2   # ceil((B+2)/B)
        sizes = sorted(len(kw["batch"]) for kw in crew._recalibrated)
        assert sizes == [2, _CRITIC_BATCH]

    def test_caps_run_on_every_idea_before_clearing(self):
        crew = _crew()
        seen = []
        crew._validate_idea_caps = lambda idea: seen.append(
            (idea.solution_name, idea.winning_angle)) or []
        ideas = [_idea("A", 0.7), _idea("B", 0.4)]
        fake = SimpleNamespace(findings=[_finding("A"), _finding("B", parity="none", covered_by="")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        # caps ran on every probed idea, BEFORE the classifier fields were cleared
        assert sorted(n for n, _ in seen) == ["A", "B"]
        assert all(angle == "novel_differentiation" for _, angle in seen)

    def test_classifier_fields_cleared_parity_kept(self):
        crew = _crew()
        ideas = [_idea("A", 0.7), _idea("B", 0.4)]
        fake = SimpleNamespace(findings=[_finding("A"), _finding("B", parity="none", covered_by="")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        for idea in ideas:
            for f in _CLASSIFIER_FIELDS:
                assert getattr(idea, f) is None, f"{f} must be cleared for re-classification"
            assert idea.incumbent_parity is not None

    def test_recalibration_batch_failure_still_clears(self):
        # _run_parallel is fail-open: a raising batch keeps its prior scores but the ideas are
        # still cleared -> re-classified against those scores (consistent, just missing parity).
        crew = _crew()

        def _boom(**kw):
            raise RuntimeError("critic down")
        crew._calibrate_batch = _boom
        ideas = [_idea("A", 0.7)]
        fake = SimpleNamespace(findings=[_finding("A")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)   # must not raise
        for f in _CLASSIFIER_FIELDS:
            assert getattr(ideas[0], f) is None

    def test_fail_soft_no_search_tool(self):
        crew = _crew(with_search=False)
        ideas = [_idea("A", 0.7)]
        crew._probe_mechanism_parity(ideas)
        assert ideas[0].incumbent_parity is None and crew._recalibrated == []
        assert ideas[0].winning_angle == "novel_differentiation"   # nothing cleared

    def test_fail_soft_llm_error(self):
        crew = _crew()
        ideas = [_idea("A", 0.7)]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            crew._probe_mechanism_parity(ideas)   # must not raise
        assert ideas[0].incumbent_parity is None and crew._recalibrated == []
        # error precedes the re-score: the in-cell rationale (still score-consistent) survives
        assert ideas[0].novelty_rationale is not None

    def test_substitute_finding_feeds_display_and_critic(self):
        # Gate-validated 2026-07-06 (flag removed): substitute findings feed BOTH the display
        # note and the recal critic, with the never-raise rubric attached.
        crew = _crew()
        ideas = [_idea("A", 0.7)]
        fake = SimpleNamespace(findings=[_finding(
            "A", parity="substitute", covered_by="census.gov", evidence="raw data is free")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        assert ideas[0].incumbent_parity == "substitute (census.gov): raw data is free"
        extra = crew._recalibrated[0]["extra_context"]
        assert "- A: substitute (census.gov): raw data is free" in extra
        assert "never raise scores for a substitute" in extra

    def test_tripwire_fires_on_near_universal_none(self):
        crew = _crew()
        ideas = [_idea(f"I{k}", 0.5) for k in range(6)]
        fake = SimpleNamespace(findings=[_finding(f"I{k}", parity="none", covered_by="")
                                         for k in range(6)])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        caveats = getattr(crew, "coverage_caveats", [])
        assert len(caveats) == 1
        assert "6 of 6 ideas" in caveats[0] and "not a green light" in caveats[0]

    def test_tripwire_quiet_below_ratio_or_count(self):
        # 3/8 none -> no caveat; 4/4 none (below 5 probed) -> no caveat.
        crew = _crew()
        ideas = [_idea(f"I{k}", 0.5) for k in range(8)]
        findings = [_finding(f"I{k}", parity="none", covered_by="") for k in range(3)]
        findings += [_finding(f"I{k}") for k in range(3, 8)]
        fake = SimpleNamespace(findings=findings)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        assert getattr(crew, "coverage_caveats", []) == []

        crew2 = _crew()
        ideas2 = [_idea(f"J{k}", 0.5) for k in range(4)]
        fake2 = SimpleNamespace(findings=[_finding(f"J{k}", parity="none", covered_by="")
                                          for k in range(4)])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake2, None)):
            crew2._probe_mechanism_parity(ideas2)
        assert getattr(crew2, "coverage_caveats", []) == []

    def test_substitute_counts_as_coverage_not_none(self):
        # 6 probed: 4 none + 2 substitute = 67% none -> tripwire quiet.
        crew = _crew()
        ideas = [_idea(f"I{k}", 0.5) for k in range(6)]
        findings = [_finding(f"I{k}", parity="none", covered_by="") for k in range(4)]
        findings += [_finding(f"I{k}", parity="substitute", covered_by="a spreadsheet")
                     for k in range(4, 6)]
        fake = SimpleNamespace(findings=findings)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        assert getattr(crew, "coverage_caveats", []) == []

    def test_incumbent_overlap_drives_query(self):
        crew = _crew()
        queries = []
        crew.search_tool = SimpleNamespace(
            run=lambda search_query: queries.append(search_query) or "results")
        fake = SimpleNamespace(findings=[])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity([_idea("A", 0.7)])
        # idea text overlaps MoeGo's focus ("route", "optimization", "grooming") → quoted-name query
        assert any('"MoeGo"' in q for q in queries)


def _adjacent_llm(markets=None, findings=None, parity_findings=None):
    """side_effect for invoke_structured that answers by output-model shape: the direct-parity
    judge, the adjacent reformulation, and the adjacent judge each get a matching fake."""
    def _invoke(**kw):
        model = kw.get("output_model")
        name = getattr(model, "__name__", "")
        if name == "_AdjacentMarkets":
            return SimpleNamespace(markets=markets or []), None
        if name == "_AdjacentIncumbentFindings":
            return SimpleNamespace(findings=findings or []), None
        return SimpleNamespace(findings=parity_findings or []), None  # direct parity judge
    return _invoke


def _market(key, cats):
    return SimpleNamespace(family_key=key, categories=cats, budget_line="ops budget")


def _adj_finding(key, incumbent="HigherGov", category="govcon market intelligence",
                 evidence="ships procurement award feeds"):
    return SimpleNamespace(family_key=key, incumbent=incumbent, category=category,
                           evidence=evidence)


class TestAdjacentMarketProbe:
    def _idea(self, name, mech="procurement-mining", data="government-open-data"):
        i = _idea(name, 0.6)
        i.mechanism_tag = mech
        i.data_source_tag = data
        i.adjacent_market_parity = None
        i.technical_approach = "ETL over USAspending"
        i.project_type = "aggregator"
        return i

    def test_family_grouping_and_stamping(self):
        crew = _crew()
        crew.search_tool = SimpleNamespace(run=lambda search_query: "HigherGov pricing and features")
        ideas = [self._idea("A"), self._idea("B"),                       # same family
                 self._idea("C", mech="case-study-scraping", data="reddit")]  # other family
        key = "procurement mining|government open data"
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data intelligence"])],
                                             findings=[_adj_finding(key)])):
            lines, covered = crew._probe_adjacent_markets(ideas)
        assert covered == 2   # both family members stamped, other family untouched
        assert ideas[0].adjacent_market_parity == (
            "HigherGov (govcon market intelligence): ships procurement award feeds")
        assert ideas[1].adjacent_market_parity == ideas[0].adjacent_market_parity
        assert ideas[2].adjacent_market_parity is None
        assert any("- A: HigherGov" in l for l in lines)

    def test_hallucinated_incumbent_dropped(self):
        # incumbent name absent from the search snippets -> finding discarded
        crew = _crew()
        crew.search_tool = SimpleNamespace(run=lambda search_query: "generic results, nothing relevant")
        ideas = [self._idea("A")]
        key = "procurement mining|government open data"
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data"])],
                                             findings=[_adj_finding(key, incumbent="MadeUpCo")])):
            lines, covered = crew._probe_adjacent_markets(ideas)
        assert covered == 0 and lines == []
        assert ideas[0].adjacent_market_parity is None

    def test_reformulation_failure_fail_soft(self):
        crew = _crew()
        crew.search_tool = SimpleNamespace(run=lambda search_query: "results")
        ideas = [self._idea("A")]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            lines, covered = crew._probe_adjacent_markets(ideas)
        assert (lines, covered) == ([], 0)

    def test_snippets_fenced_and_prompt_audience_independent(self):
        crew = _crew()
        crew.search_tool = SimpleNamespace(run=lambda search_query: "HigherGov results")
        ideas = [self._idea("A")]
        key = "procurement mining|government open data"
        prompts = []

        def _cap(**kw):
            prompts.append(kw.get("prompt"))
            return _adjacent_llm(markets=[_market(key, ["procurement data"])],
                                 findings=[_adj_finding(key)])(**kw)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_cap):
            crew._probe_adjacent_markets(ideas)
        reformulation, judge = prompts[0], prompts[1]
        assert "IGNORE the stated audience" in reformulation
        assert "UNTRUSTED IDEAS" in reformulation
        assert "UNTRUSTED WEB RESULTS" in judge
        assert "never invent" in judge

    def test_adjacent_findings_feed_recal(self):
        key = "procurement mining|government open data"
        crew = _crew()
        crew.search_tool = SimpleNamespace(run=lambda search_query: "HigherGov results")
        ideas = [self._idea(f"I{k}") for k in range(5)]
        nones = [_finding(f"I{k}", parity="none", covered_by="") for k in range(5)]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(
                       markets=[_market(key, ["procurement data"])],
                       findings=[_adj_finding(key)],
                       parity_findings=nones)):
            crew._probe_mechanism_parity(ideas)
        extra = crew._recalibrated[0]["extra_context"]
        assert "ADJACENT-MARKET INCUMBENTS" in extra and "HigherGov" in extra
        assert ideas[0].adjacent_market_parity is not None   # display stamped

    def test_tripwire_suppressed_when_adjacent_covers_half(self):
        key = "procurement mining|government open data"
        crew = _crew()
        crew.search_tool = SimpleNamespace(run=lambda search_query: "HigherGov results")
        # 6 ideas, all direct-parity NONE (would fire the tripwire) but all covered by an
        # adjacent finding -> caveat suppressed.
        ideas = [self._idea(f"I{k}") for k in range(6)]
        nones = [_finding(f"I{k}", parity="none", covered_by="") for k in range(6)]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data"])],
                                             findings=[_adj_finding(key)],
                                             parity_findings=nones)):
            crew._probe_mechanism_parity(ideas)
        assert all(i.incumbent_parity == "none found" for i in ideas)
        assert all(i.adjacent_market_parity is not None for i in ideas)
        assert getattr(crew, "coverage_caveats", []) == []   # suppressed by adjacent coverage


class TestExtraContextByteIdentity:
    def test_default_prompt_unchanged(self):
        # extra_context='' must not alter the calibration prompt (regression anchor)
        import inspect
        src = inspect.getsource(UnifiedSolutionCrew._calibrate_batch)
        assert 'extra_context: str = ""' in src
        assert 'if extra_context else ""' in src


def test_mechanism_keywords():
    kw = UnifiedSolutionCrew._mechanism_keywords(SimpleNamespace(
        mechanism_tag="route-optimizer",
        value_proposition="Plan the most efficient daily route for your grooming van"))
    assert "route" in kw and "optimizer" in kw
    assert "the" not in kw.split() and "for" not in kw.split()
