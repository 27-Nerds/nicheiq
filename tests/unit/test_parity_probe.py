"""Mechanism-parity probe (A/B-validated, always on) — web-verify whether incumbents already
SHIP each idea's core mechanism, then re-score ALL ideas with the evidence in critic context.

Probe-all (2026-07-06, was top-K): a second evidence-informed critic pass for some ideas but not
others polluted the relative ranking. After the re-score, caps are re-asserted and the classifier
outputs cleared so _classify_idea_angles re-derives every idea's rationale against final scores.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
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
    crew.search_tool = (_search_stub("MoeGo Smart Schedule route optimization")
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


def _search_stub(text):
    """search_tool stand-in supporting both `.run` (single) and `.batch_run` (the
    _probe_adjacent_markets union batch calls) — always answers with the same fixed text."""
    return SimpleNamespace(
        run=lambda search_query: text,
        batch_run=lambda queries: {q: text for q in queries})


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
        crew.search_tool = _search_stub("HigherGov pricing and features")
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

    def _niche_finding(self, key, niche_parity="shipped", niche_covered_by="HigherGov",
                       niche_evidence="ships a dedicated niche feed",
                       covered_idea_names=("A",)):
        return SimpleNamespace(
            family_key=key, incumbent="", category="", evidence="",
            niche_parity=niche_parity, niche_covered_by=niche_covered_by,
            niche_evidence=niche_evidence, covered_idea_names=list(covered_idea_names))

    def test_niche_backfill_stronger_cap_overwrites_weaker(self, monkeypatch):
        # cap-strictness upgrade (codex-review MAJOR): a stronger 'shipped' niche finding (cap
        # 0.45) must overwrite an existing weaker 'partial' finding (cap 0.55) — a plain
        # not-yet-'none' check would have rejected this since the idea already had a finding.
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.45)
        monkeypatch.setattr(settings, "parity_partial_market_fit_cap", 0.55)
        crew = _crew()
        crew.search_tool = _search_stub("HigherGov results")
        idea = self._idea("A")
        idea.incumbent_parity = "partial by OldCo: limited overlap"
        key = "procurement mining|government open data"
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data"])],
                                             findings=[self._niche_finding(key)])):
            crew._probe_adjacent_markets([idea])
        assert idea.incumbent_parity == "shipped by HigherGov: ships a dedicated niche feed"

    def test_niche_backfill_weaker_cap_does_not_overwrite_stronger(self, monkeypatch):
        # inverse: a 'substitute' niche finding (cap 0.50) must NOT overwrite an existing
        # 'shipped' finding (cap 0.45, stricter) — the existing finding is stronger.
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.45)
        monkeypatch.setattr(settings, "parity_substitute_market_fit_cap", 0.50)
        crew = _crew()
        crew.search_tool = _search_stub("HigherGov results")
        idea = self._idea("A")
        idea.incumbent_parity = "shipped by Acme: already ships it"
        key = "procurement mining|government open data"
        finding = self._niche_finding(key, niche_parity="substitute", niche_covered_by="FreeGovData",
                                      niche_evidence="free DIY route exists")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data"])],
                                             findings=[finding])):
            crew._probe_adjacent_markets([idea])
        assert idea.incumbent_parity == "shipped by Acme: already ships it"   # untouched

    def test_niche_backfill_overwrites_empty_finding(self):
        # no cap (empty/'none') = no ceiling = always overwritable.
        crew = _crew()
        crew.search_tool = _search_stub("HigherGov results")
        idea = self._idea("A")
        idea.incumbent_parity = None
        key = "procurement mining|government open data"
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data"])],
                                             findings=[self._niche_finding(key)])):
            crew._probe_adjacent_markets([idea])
        assert idea.incumbent_parity == "shipped by HigherGov: ships a dedicated niche feed"

    def test_niche_frame_queries_include_outcome_query(self):
        # Fix 1 (2026-07-10, live-motivated): incumbent NAMES often share no vocabulary with the
        # idea's mechanism/category framing ("parity: none found" on ideas killed by The Wedding
        # Report and the Berkeley Function-Calling Leaderboard) — an outcome-framed query
        # (preferring the family's reformulated budget_line) is now added per family, and the
        # setting's default/le were raised to 3 so it fires alongside the existing two.
        assert settings.parity_niche_frame_queries_per_family == 3
        crew = _crew()
        crew.niche_context = SimpleNamespace(niche_description="wedding photographers")
        queries: list[str] = []
        crew.search_tool = SimpleNamespace(
            run=lambda search_query: "results",
            batch_run=lambda qs: (queries.extend(qs), {q: "results" for q in qs})[1])
        ideas = [self._idea("A")]
        key = "procurement mining|government open data"
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(markets=[_market(key, ["procurement data"])],
                                             findings=[_adj_finding(key)])):
            crew._probe_adjacent_markets(ideas)
        # _market() stamps budget_line="ops budget" — used verbatim as the outcome query.
        assert "ops budget" in queries
        assert "procurement data for wedding photographers" in queries
        assert "free wedding photographers procurement data" in queries

    def test_hallucinated_incumbent_dropped(self):
        # incumbent name absent from the search snippets -> finding discarded
        crew = _crew()
        crew.search_tool = _search_stub("generic results, nothing relevant")
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
        crew.search_tool = _search_stub("results")
        ideas = [self._idea("A")]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            lines, covered = crew._probe_adjacent_markets(ideas)
        assert (lines, covered) == ([], 0)

    def test_snippets_fenced_and_prompt_audience_independent(self):
        crew = _crew()
        crew.search_tool = _search_stub("HigherGov results")
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
        crew.search_tool = _search_stub("HigherGov results")
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

    def test_backfill_reflected_in_recal_extra_not_stale(self):
        # codex-review MAJOR: the MECHANISM PARITY CHECK block fed to the recal critic must
        # reflect each idea's FINAL (post-niche-backfill) finding, not the pre-backfill
        # 'none found' line assembled before the adjacent probe ran.
        key = "procurement mining|government open data"
        crew = _crew()
        crew.search_tool = _search_stub("HigherGov results")
        ideas = [self._idea("A")]
        nones = [_finding("A", parity="none", covered_by="")]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_adjacent_llm(
                       markets=[_market(key, ["procurement data"])],
                       findings=[self._niche_finding(key)],
                       parity_findings=nones)):
            crew._probe_mechanism_parity(ideas)
        extra = crew._recalibrated[0]["extra_context"]
        assert "- A: shipped by HigherGov: ships a dedicated niche feed" in extra
        assert "- A: none found" not in extra
        assert ideas[0].incumbent_parity == "shipped by HigherGov: ships a dedicated niche feed"

    def test_tripwire_suppressed_when_adjacent_covers_half(self):
        key = "procurement mining|government open data"
        crew = _crew()
        crew.search_tool = _search_stub("HigherGov results")
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


# ── 2026-08 parity fix (plan Step 1, corrections 2+3): verify_text split, bundled_free
# evidence conditions, wallet reclassify, downgrade-not-drop, reset-then-stamp ────────────

def _toolbelt_crew(res_for_query, tools=("VetSnap",), incumbent_rows=None):
    """Crew stub for `_probe_toolbelt_free_bundle`: `res_for_query(q)` -> result text."""
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="veterinary clinics")
    crew.search_tool = SimpleNamespace()   # probe only checks truthiness
    crew.cost_tracker = None
    crew.audience_mapping = SimpleNamespace(tools_currently_used=list(tools))
    crew._incumbent_rows = list(incumbent_rows or [])
    crew._ma_search_batch = lambda queries: {q: res_for_query(q) for q in queries}
    return crew


def _tb_finding(idea_name, route="VetSnap", evidence="controlled drug logs",
                outcome="bundled_free"):
    return SimpleNamespace(idea_name=idea_name, tool_or_route=route,
                           evidence=evidence, outcome=outcome)


def _tb_idea(name, kw_word):
    """Idea whose _mechanism_keywords output starts with `kw_word` — used to key which
    queries the res stub answers, i.e. which idea 'owns' the evidencing snippet."""
    return SimpleNamespace(
        solution_name=name, value_proposition=f"{kw_word} reconciliation for clinics",
        mechanism_tag=kw_word, incumbent_parity=None)


class TestToolbeltFreeBundleProbe:
    def test_route_only_in_query_never_verifies(self):
        # THE dead-guard bug: the old check ran against snippets that embedded the query
        # text, so a toolbelt vendor named in the QUERY always "verified". Route absent
        # from all RESULT text -> finding dropped, no stamp.
        crew = _toolbelt_crew(lambda q: "generic results, free tools mentioned, no vendor")
        issued: list[str] = []
        inner = crew._ma_search_batch
        crew._ma_search_batch = lambda queries: issued.extend(queries) or inner(queries)
        idea = _tb_idea("A", "alphasync")
        fake = SimpleNamespace(findings=[_tb_finding("A")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            lines, covered = crew._probe_toolbelt_free_bundle([idea])
        assert (lines, covered) == ([], 0)
        assert idea.incumbent_parity is None
        # sanity: the vendor name really WAS embedded in the issued queries — under the old
        # query-embedding snippets this finding would have (wrongly) verified
        assert any("VetSnap" in q for q in issued)

    def test_priced_wallet_vendor_reclassified_to_shipped(self):
        # correction 2: incumbent map prices VetSnap at $300/mo with no free tier -> the
        # "free" claim contradicts wallet data; parity stands as `shipped`, never voided.
        crew = _toolbelt_crew(
            lambda q: "VetSnap ships controlled drug logging free with every plan",
            incumbent_rows=[{"name": "VetSnap", "pricing": "$300/mo",
                             "focus": "vet practice mgmt", "gap": ""}])
        idea = _tb_idea("A", "alphasync")
        fake = SimpleNamespace(findings=[_tb_finding("A")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            lines, covered = crew._probe_toolbelt_free_bundle([idea])
        assert idea.incumbent_parity == "shipped by VetSnap: controlled drug logs"
        assert covered == 1 and lines == ["- A: shipped by VetSnap: controlled drug logs"]

    def test_free_priced_vendor_keeps_bundled_free(self):
        # Liquipedia-shaped row (pricing contains "free") stays eligible for bundled_free.
        crew = _toolbelt_crew(
            lambda q: "Liquipedia offers live brackets free for every tournament",
            tools=("Liquipedia",),
            incumbent_rows=[{"name": "Liquipedia", "pricing": "free",
                             "focus": "esports wiki", "gap": ""}])
        idea = _tb_idea("A", "alphasync")
        fake = SimpleNamespace(findings=[_tb_finding("A", route="Liquipedia",
                                                     evidence="live brackets")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_toolbelt_free_bundle([idea])
        assert idea.incumbent_parity == "bundled_free (Liquipedia): live brackets"

    def test_no_free_token_colocated_downgrades_not_drops(self):
        # Vendor verified in results but no free/included/no-cost token co-located with it
        # -> DOWNGRADE (unpriced vendor -> partial), never emit bundled_free, never drop.
        crew = _toolbelt_crew(lambda q: "VetSnap ships a controlled drug logging module")
        idea = _tb_idea("A", "alphasync")
        fake = SimpleNamespace(findings=[_tb_finding("A")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            lines, covered = crew._probe_toolbelt_free_bundle([idea])
        assert idea.incumbent_parity == "partial by VetSnap: controlled drug logs"
        assert covered == 1

    def test_other_ideas_evidence_downgrades(self):
        # correction 3: the evidencing snippet's query must derive from THIS idea's own
        # keyword. B's finding is evidenced only by A's query result -> downgraded class.
        def res(q):
            return ("Liquipedia offers live brackets free for everyone"
                    if "alphasync" in q else "nothing relevant here")
        crew = _toolbelt_crew(res, tools=("Liquipedia",))
        a, b = _tb_idea("A", "alphasync"), _tb_idea("B", "betametrics")
        fake = SimpleNamespace(findings=[
            _tb_finding("B", route="Liquipedia", evidence="live brackets")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_toolbelt_free_bundle([a, b])
        assert b.incumbent_parity == "partial by Liquipedia: live brackets"
        assert a.incumbent_parity is None

    def test_other_ideas_evidence_with_priced_vendor_downgrades_to_shipped(self):
        # downgrade target rule: vendor named AND priced in the wallet -> shipped (0.45),
        # not partial (0.55).
        def res(q):
            return ("VetSnap logging is included free on all plans"
                    if "alphasync" in q else "nothing relevant here")
        crew = _toolbelt_crew(
            res, incumbent_rows=[{"name": "VetSnap", "pricing": "$300/mo",
                                  "focus": "", "gap": ""}])
        a, b = _tb_idea("A", "alphasync"), _tb_idea("B", "betametrics")
        fake = SimpleNamespace(findings=[_tb_finding("B")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_toolbelt_free_bundle([a, b])
        assert b.incumbent_parity == "shipped by VetSnap: controlled drug logs"

    def test_downgraded_finding_never_loosens_existing_cap(self, monkeypatch):
        # strictness-upgrade-only guard applies to the DOWNGRADED class: a partial (0.55)
        # downgrade must not overwrite an existing shipped (0.45) finding.
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.45)
        monkeypatch.setattr(settings, "parity_partial_market_fit_cap", 0.55)
        crew = _toolbelt_crew(lambda q: "VetSnap ships a logging module")   # no free token
        idea = _tb_idea("A", "alphasync")
        idea.incumbent_parity = "shipped by Acme: already ships it"
        fake = SimpleNamespace(findings=[_tb_finding("A")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            lines, covered = crew._probe_toolbelt_free_bundle([idea])
        assert idea.incumbent_parity == "shipped by Acme: already ships it"
        assert (lines, covered) == ([], 0)

    def test_stamp_string_shapes_preserved(self):
        # >=7 consumers parse the prefix — the three shapes this probe can emit must stay
        # byte-compatible: "bundled_free (V): e" / "shipped by V: e" / "partial by V: e".
        crew = _toolbelt_crew(
            lambda q: "Liquipedia offers live brackets free for everyone",
            tools=("Liquipedia",))
        idea = _tb_idea("A", "alphasync")
        fake = SimpleNamespace(findings=[_tb_finding("A", route="Liquipedia",
                                                     evidence="live brackets")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_toolbelt_free_bundle([idea])
        from nicheiq.validators.report_consistency import parse_stamp_vendor
        assert parse_stamp_vendor(idea.incumbent_parity) == ("bundled_free", "Liquipedia")


class TestResetThenStamp:
    def test_reprobe_weaker_finding_wins(self):
        # RESET-FIRST: a second probe's weaker finding replaces the first probe's stronger
        # one for the probed idea — the probe is evidence-of-record, not a ratchet.
        crew = _crew()
        a, b = _idea("A", 0.7), _idea("B", 0.6)
        first = SimpleNamespace(findings=[_finding("A"), _finding("B")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(first, None)):
            crew._probe_mechanism_parity([a, b])
        assert a.incumbent_parity == "shipped by MoeGo: Smart Schedule route optimization"
        second = SimpleNamespace(findings=[_finding(
            "A", parity="partial", covered_by="NewCo", evidence="limited overlap")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(second, None)):
            crew._probe_mechanism_parity([a])
        assert a.incumbent_parity == "partial by NewCo: limited overlap"
        # B was NOT in the second probed set — its wave-1 finding must survive the reset
        assert b.incumbent_parity == "shipped by MoeGo: Smart Schedule route optimization"

    def test_reset_scoped_to_probed_set_only(self):
        crew = _crew()
        a, b, c = _idea("A", 0.7), _idea("B", 0.6), _idea("C", 0.5)
        first = SimpleNamespace(findings=[_finding("A"), _finding("B")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(first, None)):
            crew._probe_mechanism_parity([a, b])
        # second wave probes A + C; the judge returns a finding only for C
        second = SimpleNamespace(findings=[_finding("C")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(second, None)):
            crew._probe_mechanism_parity([a, c])
        assert a.incumbent_parity is None            # probed, no finding -> reset stands
        assert b.incumbent_parity == "shipped by MoeGo: Smart Schedule route optimization"
        assert c.incumbent_parity == "shipped by MoeGo: Smart Schedule route optimization"

    def test_fabricated_birth_stamp_cleared(self):
        # incumbent_parity sits on BaseSolutionIdea — generator LLMs can fabricate it
        # (same disease _stamp_payability's RESET-FIRST fixes). A probe pass must clear it.
        crew = _crew()
        idea = _idea("A", 0.7)
        idea.incumbent_parity = "bundled_free (MadeUpCo): fabricated at birth"
        fake = SimpleNamespace(findings=[_finding("A", parity="none", covered_by="")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity([idea])
        assert idea.incumbent_parity == "none found"

    def test_fail_soft_keeps_prior_findings(self):
        # an LLM failure precedes the per-idea loop — prior stamps survive (fail-soft).
        crew = _crew()
        idea = _idea("A", 0.7)
        idea.incumbent_parity = "shipped by Acme: prior wave finding"
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            crew._probe_mechanism_parity([idea])
        assert idea.incumbent_parity == "shipped by Acme: prior wave finding"


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


# ── §6(a) vocabulary fix (2026-07-30): buyer-vocabulary capability phrases, a vendor-free
# discovery arm, and the truncated-fallback bug ──────────────────────────────────────────

def _recording_crew(niche_description="mobile dog groomers", incumbent_focus="grooming scheduling"):
    """Crew stub whose search_tool RECORDS every query issued."""
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description=niche_description)
    crew.queries = []

    def _run(search_query):
        crew.queries.append(search_query)
        return "some web result"
    crew.search_tool = SimpleNamespace(run=_run, batch_run=lambda queries: {q: "r" for q in queries})
    crew.cost_tracker = None
    crew._incumbent_probe_text = "cached"
    crew._incumbent_rows = [{"name": "MoeGo", "pricing": "$50/mo", "focus": incumbent_focus, "gap": ""}]
    crew._calibrate_batch = lambda **kw: (len(kw["batch"]), None)
    return crew


def _capability_llm(phrase="payout deposit reconciliation", findings=None):
    """invoke_structured mock: answers the capability call with `phrase`, the parity call with
    `findings`. Branches on the prompt (only the capability prompt says 'BUYER would type')."""
    def _invoke(**kw):
        if "BUYER would type" in kw.get("prompt", ""):
            return (SimpleNamespace(items=[SimpleNamespace(idea_name="A", phrase=phrase)]),
                    None)
        return SimpleNamespace(findings=findings or []), None
    return _invoke


class TestCapabilityPhraseQueries:
    def test_capability_phrase_replaces_shape_words_in_queries(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 12)
        crew = _recording_crew()
        # mechanism_tag is the shape noise the fix exists to eliminate
        idea = _idea("A", 0.6, vp="Stop manually hunting for the sales that make up a deposit",
                     mech="parametric-calculator")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity([idea])

        assert crew.queries, "probe issued no queries"
        assert all("payout deposit reconciliation" in q for q in crew.queries)
        assert not any("parametric" in q for q in crew.queries)

    def test_vendor_free_discovery_query_present_and_capability_first(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 12)
        crew = _recording_crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity([_idea("A", 0.6)])

        vendor_free = [q for q in crew.queries if "MoeGo" not in q]
        assert vendor_free, "no vendor-free discovery query issued"
        # Capability leads so it survives the 120-char cap.
        assert vendor_free[0].startswith("payout deposit reconciliation")

    def test_discovery_arm_disabled_by_zero(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 0)
        # Overlapping incumbent focus so the name-anchored path is taken (an idea with NO
        # overlapping incumbent still gets the vendor-free FALLBACK query — that is the
        # pre-existing contract, not the discovery arm).
        crew = _recording_crew(incumbent_focus="route optimization scheduling")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity([_idea("A", 0.6)])

        assert crew.queries  # name-anchored queries still issued
        assert all("MoeGo" in q for q in crew.queries)

    def test_discovery_budget_capped_per_run(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 2)
        crew = _recording_crew(incumbent_focus="route optimization scheduling")
        ideas = [_idea(f"I{n}", 0.6) for n in range(5)]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity(ideas)

        # 5 ideas each have an overlapping incumbent, so every vendor-free query is a
        # discovery query — and the per-run cap bounds them at 2.
        assert len([q for q in crew.queries if "MoeGo" not in q]) == 2
        assert len([q for q in crew.queries if "MoeGo" in q]) == 5

    def test_fallback_query_still_issued_after_discovery_budget_exhausted(self, monkeypatch):
        """An idea with no overlapping incumbent must never end up with ZERO queries, even once
        the discovery arm is spent — the fallback is a separate, uncapped contract."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 0)
        crew = _recording_crew(incumbent_focus="zzz unrelated")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity([_idea("A", 0.6)])

        assert len(crew.queries) == 1
        assert "payout deposit reconciliation" in crew.queries[0]

    def test_long_niche_description_no_longer_truncates_mechanism_away(self, monkeypatch):
        """THE BUG: the old fallback was f"{niche} software {kw}"[:120] with `niche` = the full
        ~400-char niche_description, so the mechanism words never reached the query at all."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 12)
        long_niche = ("The professional bookkeeping and outsourced accounting services market "
                      "encompasses the systems, software, and workflows used to manage financial "
                      "records, regulatory compliance, and periodic financial reporting.")
        # incumbent focus shares no words with the idea -> the fallback path is taken
        crew = _recording_crew(niche_description=long_niche, incumbent_focus="zzz unrelated")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity([_idea("A", 0.6)])

        assert crew.queries
        assert all("payout deposit reconciliation" in q for q in crew.queries), crew.queries
        assert all(len(q) <= 120 for q in crew.queries)

    def test_fail_soft_falls_back_to_mechanism_keywords(self, monkeypatch):
        """A raising capability call must leave the probe working on the previous behavior."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 12)
        crew = _recording_crew()

        def _invoke(**kw):
            if "BUYER would type" in kw.get("prompt", ""):
                raise RuntimeError("capability call down")
            return SimpleNamespace(findings=[]), None
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_invoke)):
            crew._probe_mechanism_parity([_idea("A", 0.6, mech="route-optimizer")])

        assert crew.queries
        assert any("route" in q for q in crew.queries)  # _mechanism_keywords vocabulary

    def test_discovery_budget_is_per_run_not_per_call(self, monkeypatch):
        """The probe runs once over the full set AND again per _score_wave (a live
        regenerate_ideas job called it 4×), so a per-CALL counter would spend 4× the
        documented per-run cap."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 2)
        crew = _recording_crew(incumbent_focus="route optimization scheduling")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_capability_llm())):
            crew._probe_mechanism_parity([_idea("A", 0.6), _idea("B", 0.6)])
            crew._probe_mechanism_parity([_idea("C", 0.6), _idea("D", 0.6)])

        assert len([q for q in crew.queries if "MoeGo" not in q]) == 2

    def test_phrase_map_cached_across_calls(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 12)
        crew = _recording_crew()
        calls = []

        def _invoke(**kw):
            if "BUYER would type" in kw.get("prompt", ""):
                calls.append(1)
                return (SimpleNamespace(items=[SimpleNamespace(idea_name="A", phrase="x y z")]),
                        None)
            return SimpleNamespace(findings=[]), None
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   staticmethod(_invoke)):
            crew._probe_mechanism_parity([_idea("A", 0.6)])
            crew._probe_mechanism_parity([_idea("A", 0.6)])

        assert len(calls) == 1, "capability phrases must be cached per run"
