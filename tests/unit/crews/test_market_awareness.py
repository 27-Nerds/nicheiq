"""Market-awareness code (2026-07-09): incumbent-parity market_fit caps (rule (e) in
_validate_idea_caps), owned-SERP SEO cap (seo_helpers Rule D), the shared budgeted search
(_ma_search), the SERP-composition probe, the niche-wallet probe + its prompt/market-reality
text builders, and the parity wedge-pivot revision loop.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.seo_helpers import cap_seo_realism_score


def _crew(**extra):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _idea(name="Idea", mf=0.5, incumbent_parity=None, source_segment_payability=None,
          data_access_model=None, build_feasibility_score=0.8, novelty_score=None,
          obviousness_score=None, solo_dev_feasibility=None, technical_feasibility_score=0.6,
          seo_scalability_score=None, winning_angle=None, status="active", **kw):
    base = dict(
        solution_name=name, market_fit_score=mf, incumbent_parity=incumbent_parity,
        source_segment_payability=source_segment_payability,
        source_segment_payability_class=None,
        data_access_model=data_access_model, build_feasibility_score=build_feasibility_score,
        novelty_score=novelty_score, obviousness_score=obviousness_score,
        solo_dev_feasibility=solo_dev_feasibility,
        technical_feasibility_score=technical_feasibility_score,
        seo_scalability_score=seo_scalability_score,
        winning_angle=winning_angle, candidate_status=status,
        source_pain=None, source_segment=None, pain_points_addressed=None,
        target_personas=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# _validate_idea_caps — rule (e): incumbent-parity market_fit ceiling
# ---------------------------------------------------------------------------

class TestValidateIdeaCapsRuleE:
    def test_shipped_caps_075_to_045(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.45)
        crew = _crew()
        idea = _idea(mf=0.75, incumbent_parity="shipped by Acme: route optimization")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45
        assert any("incumbent parity" in x for x in f)

    def test_partial_caps_07_to_055(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_partial_market_fit_cap", 0.55)
        crew = _crew()
        idea = _idea(mf=0.7, incumbent_parity="partial by Beta: overlapping feature")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.55
        assert any("incumbent parity" in x for x in f)

    def test_substitute_caps_07_to_050(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_substitute_market_fit_cap", 0.50)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = _crew()
        idea = _idea(mf=0.7, incumbent_parity="substitute: DIY spreadsheet",
                     source_segment_payability=0.6)
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.50
        assert any("incumbent parity" in x for x in f)

    def test_substitute_weak_wallet_02_caps_to_035(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_substitute_market_fit_cap", 0.50)
        monkeypatch.setattr(settings, "parity_substitute_weak_wallet_cap", 0.35)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        monkeypatch.setattr(settings, "payability_market_fit_cap", 0.55)
        crew = _crew()
        idea = _idea(mf=0.7, incumbent_parity="substitute: DIY spreadsheet",
                     source_segment_payability=0.2)
        f = crew._validate_idea_caps(idea)
        # (d) payability cap fires to 0.55 first, then (e)'s weak-wallet substitute cap
        # tightens further to 0.35 — composed, not independent.
        assert idea.market_fit_score == 0.35
        assert len(f) == 2

    def test_none_found_untouched(self):
        crew = _crew()
        idea = _idea(mf=0.9, incumbent_parity="none found: no incumbent found")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.9
        assert f == []

    def test_cap_zero_disables_shipped_branch(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0)
        crew = _crew()
        idea = _idea(mf=0.75, incumbent_parity="shipped by Acme")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.75
        assert f == []

    def test_bundled_free_caps_075_to_040(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_bundled_free_cap", 0.40)
        crew = _crew()
        idea = _idea(mf=0.75, incumbent_parity="bundled_free (Truckstop): free broker credit scores")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.40
        assert any("incumbent parity" in x for x in f)

    def test_bundled_free_cap_zero_disables(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_bundled_free_cap", 0)
        crew = _crew()
        idea = _idea(mf=0.75, incumbent_parity="bundled_free (Truckstop): free broker credit scores")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.75
        assert f == []

    def test_min_composes_with_payability_cap_d(self, monkeypatch):
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        monkeypatch.setattr(settings, "payability_market_fit_cap", 0.55)
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.45)
        crew = _crew()
        idea = _idea(mf=0.75, incumbent_parity="shipped by Acme",
                     source_segment_payability=0.2)
        f = crew._validate_idea_caps(idea)
        # (d) caps to 0.55 first; (e)'s tighter shipped cap (0.45) wins the min-composition.
        assert idea.market_fit_score == 0.45
        assert len(f) == 2

    def test_idempotent_rerun(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.45)
        crew = _crew()
        idea = _idea(mf=0.75, incumbent_parity="shipped by Acme")
        f1 = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45
        assert f1
        f2 = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45
        assert f2 == []


# ---------------------------------------------------------------------------
# _validate_idea_caps — rule (f): self-issued trust artifact market_fit ceiling
# (2026-07-10: killed twice by web judgment — a self-issued "verified badge"/"trust seal" is a
# liability hazard, not a credibility product)
# ---------------------------------------------------------------------------

class TestValidateIdeaCapsRuleF:
    def test_self_issued_trust_badge_caps_06_to_035(self, monkeypatch):
        monkeypatch.setattr(settings, "selfissued_trust_market_fit_cap", 0.35)
        crew = _crew()
        idea = _idea(name="TrustBadge", mf=0.6,
                     value_proposition="Generate your verified badge in minutes")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.35
        assert any("self-issued trust artifact" in x for x in f)

    def test_third_party_verification_language_exempts(self, monkeypatch):
        monkeypatch.setattr(settings, "selfissued_trust_market_fit_cap", 0.35)
        crew = _crew()
        idea = _idea(name="TrustBadge", mf=0.6,
                     value_proposition="Generate your verified badge in minutes",
                     description="Backed by third-party, lab-tested certification")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.6
        assert f == []

    def test_cap_zero_disables(self, monkeypatch):
        monkeypatch.setattr(settings, "selfissued_trust_market_fit_cap", 0)
        crew = _crew()
        idea = _idea(name="TrustBadge", mf=0.6,
                     value_proposition="Generate your verified badge in minutes")
        f = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.6
        assert f == []


# ---------------------------------------------------------------------------
# seo_helpers.cap_seo_realism_score — Rule D (owned SERP)
# ---------------------------------------------------------------------------

class TestSeoHelpersRuleD:
    def _base_kwargs(self, **overrides):
        kw = dict(
            project_type="saas", data_access_model="public",
            estimated_indexable_pages=None, require_saas_for_gating=True,
            gated_saas_ceiling=0.5, thin_pages_threshold=10, thin_pages_ceiling=0.4,
            high_score_min_pages=300, moderate_pages_ceiling=0.7,
            serp_owned=False, serp_owned_ceiling=0.5,
        )
        kw.update(overrides)
        return kw

    def test_serp_owned_caps_09_to_ceiling(self):
        capped, note = cap_seo_realism_score(
            0.9, **self._base_kwargs(serp_owned=True, serp_owned_ceiling=0.5))
        assert capped == 0.5
        assert note and "owned" in note.lower()

    def test_not_owned_unchanged(self):
        capped, note = cap_seo_realism_score(
            0.9, **self._base_kwargs(serp_owned=False, serp_owned_ceiling=0.5))
        assert capped == 0.9
        assert note is None

    def test_ceiling_zero_disables(self):
        capped, note = cap_seo_realism_score(
            0.9, **self._base_kwargs(serp_owned=True, serp_owned_ceiling=0))
        assert capped == 0.9
        assert note is None

    def test_composes_with_rule_a_via_min(self):
        capped, note = cap_seo_realism_score(
            0.9, **self._base_kwargs(data_access_model="restricted", gated_saas_ceiling=0.6,
                                      serp_owned=True, serp_owned_ceiling=0.3))
        assert capped == 0.3
        assert "account-gated" in note
        assert "owned" in note.lower()


# ---------------------------------------------------------------------------
# _ma_search — shared budgeted Serper call
# ---------------------------------------------------------------------------

class TestMaSearch:
    def test_budget_zero_returns_none_no_call(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 0)
        crew = _crew()
        crew.search_tool = MagicMock()
        assert crew._ma_search("q") is None
        crew.search_tool.run.assert_not_called()

    def test_budget_two_third_call_returns_none_and_counts(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 2)
        crew = _crew()
        crew.search_tool = MagicMock()
        crew.search_tool.run.return_value = "result text"
        assert crew._ma_search("q1") == "result text"
        assert crew._ma_search("q2") == "result text"
        assert crew._ma_search("q3") is None
        assert crew.search_tool.run.call_count == 2
        assert crew._ma_serper_calls == 2

    def test_cache_hit_returns_without_consuming_budget(self, monkeypatch):
        # codex-review MAJOR: a session-cache hit (tool._cache, normalized query key) must
        # short-circuit BEFORE the budget gate and never increment it.
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 1)
        crew = _crew()
        crew.search_tool = MagicMock()
        crew.search_tool._cache = {"cached query": "cached result"}
        crew.search_tool.run.return_value = "fresh result"
        assert crew._ma_search("  Cached Query  ") == "cached result"   # normalized match
        crew.search_tool.run.assert_not_called()
        assert getattr(crew, "_ma_serper_calls", 0) == 0
        # budget still fully available for an actual miss
        assert crew._ma_search("new query") == "fresh result"
        crew.search_tool.run.assert_called_once()
        assert crew._ma_serper_calls == 1
        # budget now exhausted — a second miss returns None without touching the cache
        assert crew._ma_search("another query") is None


# ---------------------------------------------------------------------------
# _ma_search_batch — shared budgeted Serper call, batched
# ---------------------------------------------------------------------------

class TestMaSearchBatch:
    def test_budget_zero_returns_all_empty_no_call(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 0)
        crew = _crew()
        crew.search_tool = MagicMock()
        assert crew._ma_search_batch(["q1", "q2"]) == {"q1": "", "q2": ""}
        crew.search_tool.batch_run.assert_not_called()

    def test_budget_truncation_two_of_four(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 2)
        crew = _crew()
        crew.search_tool = MagicMock()
        crew.search_tool._cache = {}
        crew.search_tool.batch_run.return_value = {"q1": "r1", "q2": "r2"}
        out = crew._ma_search_batch(["q1", "q2", "q3", "q4"])
        assert out == {"q1": "r1", "q2": "r2", "q3": "", "q4": ""}
        crew.search_tool.batch_run.assert_called_once_with(["q1", "q2"])
        assert crew._ma_serper_calls == 2

    def test_cache_hits_dont_consume_budget(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 1)
        crew = _crew()
        crew.search_tool = MagicMock()
        crew.search_tool._cache = {"cached query": "cached result"}
        crew.search_tool.batch_run.return_value = {
            "  Cached Query  ": "cached result", "new query": "fresh result"}
        out = crew._ma_search_batch(["  Cached Query  ", "new query"])
        assert out == {"  Cached Query  ": "cached result", "new query": "fresh result"}
        # Only the actual miss ("new query") counted against the budget.
        assert crew._ma_serper_calls == 1

    def test_no_tool_returns_all_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 5)
        crew = _crew()
        assert crew._ma_search_batch(["q1"]) == {"q1": ""}

    def test_budget_exempt_bypasses_drained_budget(self, monkeypatch):
        # Live-caught 2026-07-10: red-team runs last, shared budget drained -> zero
        # evidence. budget_exempt callers carry their OWN cap and must still fetch.
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 2)
        crew = _crew()
        crew._ma_serper_calls = 2  # shared budget fully spent
        crew.search_tool = MagicMock()
        crew.search_tool._cache = {}
        crew.search_tool.batch_run.return_value = {"q1": "r1"}
        assert crew._ma_search_batch(["q1"]) == {"q1": ""}  # gated without exemption
        out = crew._ma_search_batch(["q1"], budget_exempt=True)
        assert out == {"q1": "r1"}


# ---------------------------------------------------------------------------
# _ma_search_batch — budget-lock thread safety (2026-07-10 parallelization audit)
# ---------------------------------------------------------------------------

class TestMaSearchBatchThreadSafety:
    def test_concurrent_calls_never_exceed_budget(self, monkeypatch):
        # The check-truncate-increment budget bookkeeping must be atomic under concurrent
        # callers, or `_ma_serper_calls` can overrun the shared budget.
        from concurrent.futures import ThreadPoolExecutor

        budget = 10
        monkeypatch.setattr(settings, "market_awareness_serper_budget", budget)
        crew = _crew()
        crew.search_tool = MagicMock()
        crew.search_tool._cache = {}
        crew.search_tool.batch_run.side_effect = lambda qs: {q: "r" for q in qs}
        crew._get_ma_search_lock()  # pre-create so the lazy-init race isn't part of this test

        def _worker(worker_id):
            queries = [f"w{worker_id}-q{i}" for i in range(5)]  # all unique -> all cache misses
            crew._ma_search_batch(queries)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_worker, range(8)))

        assert crew._ma_serper_calls == budget


# ---------------------------------------------------------------------------
# _probe_serp_composition
# ---------------------------------------------------------------------------

class TestProbeSerpComposition:
    def _serp_idea(self, **kw):
        base = dict(
            solution_name="PlumberDirectory", winning_angle="distribution_seo",
            seo_scalability_score_refined=None,
            programmatic_seo_opportunity="plumbing license guide directory pages per city",
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_non_distribution_seo_skipped(self):
        crew = _crew()
        crew._ma_search_batch = MagicMock()
        idea = self._serp_idea(winning_angle="community_hub")
        crew._probe_serp_composition([idea])
        crew._ma_search_batch.assert_not_called()
        assert getattr(idea, "_serp_owned", False) is False

    def test_refined_score_present_skipped(self):
        crew = _crew()
        crew._ma_search_batch = MagicMock()
        idea = self._serp_idea(seo_scalability_score_refined=0.6)
        crew._probe_serp_composition([idea])
        crew._ma_search_batch.assert_not_called()
        assert getattr(idea, "_serp_owned", False) is False

    def test_search_is_budget_exempt(self, monkeypatch):
        """Regression (2026-07-30): this probe runs LAST, so a drained shared budget silently
        returned '' for every query, `_serp_owned` was never stamped, and Rule D's provisional-SEO
        cap never fired — making an idea's SEO score depend on earlier probes' spend."""
        monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
        crew = _crew()
        crew._ma_search_batch = MagicMock(return_value={})
        crew._probe_serp_composition([self._serp_idea()])
        crew._ma_search_batch.assert_called_once()
        assert crew._ma_search_batch.call_args.kwargs.get("budget_exempt") is True

    def test_starvation_is_logged_not_silent(self, monkeypatch):
        """Empty results must be visible — 'budget starved' and 'no owned SERPs' were previously
        indistinguishable because the probe only logged on a POSITIVE finding."""
        from loguru import logger
        monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
        crew = _crew()
        crew._ma_search_batch = MagicMock(return_value={})
        messages = []
        capture_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
        try:
            crew._probe_serp_composition([self._serp_idea()])
        finally:
            logger.remove(capture_id)
        blob = " ".join(messages)
        assert "SerpProbe" in blob and "Rule D cannot fire" in blob, messages

    def test_owned_serp_stamps_true(self, monkeypatch):
        monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
        monkeypatch.setattr(settings, "serp_owned_domain_threshold", 7)
        crew = _crew()
        # 4 unique authority domains (.gov x2, wikipedia, .edu) + 3 commercial domains
        # repeated across both queries (entrenched, count >= 2) = 7 owned.
        result1 = (
            "1. https://www.irs.gov/businesses/plumbing-license - licensing guide\n"
            "2. https://en.wikipedia.org/wiki/Plumbing - overview\n"
            "3. https://www.bigcompetitor.com/services/plumbers - find plumbers\n"
            "4. https://www.otherleader.net/plumbing-directory - directory\n"
            "5. https://www.rivalexpert.io/local-plumbers - listing\n"
        )
        result2 = (
            "1. https://www.sec.gov/rules/plumbing-licensing - filing\n"
            "2. https://www.example.edu/plumbing-trade - program\n"
            "3. https://www.bigcompetitor.com/cities/austin - austin plumbers\n"
            "4. https://www.otherleader.net/cities/dallas - dallas plumbers\n"
            "5. https://www.rivalexpert.io/cities/houston - houston plumbers\n"
        )
        idea = self._serp_idea()
        base = idea.programmatic_seo_opportunity
        base_q = " ".join(base.split()[:8])
        crew._ma_search_batch = MagicMock(
            return_value={base_q: result1, f"{base_q} guide": result2})
        crew._probe_serp_composition([idea])
        assert idea._serp_owned is True

    def test_ugc_only_serp_not_stamped(self, monkeypatch):
        monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
        monkeypatch.setattr(settings, "serp_owned_domain_threshold", 7)
        crew = _crew()
        result = (
            "1. https://www.reddit.com/r/plumbing/comments/abc - thread\n"
            "2. https://www.pinterest.com/pin/12345 - pin board\n"
            "3. https://www.youtube.com/watch?v=xyz - video walkthrough\n"
        )
        idea = self._serp_idea()
        base = idea.programmatic_seo_opportunity
        base_q = " ".join(base.split()[:8])
        crew._ma_search_batch = MagicMock(
            return_value={base_q: result, f"{base_q} guide": result})
        crew._probe_serp_composition([idea])
        assert getattr(idea, "_serp_owned", False) is False

    def test_single_query_sampled_not_stamped(self, monkeypatch):
        monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
        monkeypatch.setattr(settings, "serp_owned_domain_threshold", 7)
        crew = _crew()
        result1 = "1. https://www.irs.gov/plumbing - licensing guide\n"
        idea = self._serp_idea()
        base = idea.programmatic_seo_opportunity
        base_q = " ".join(base.split()[:8])
        crew._ma_search_batch = MagicMock(
            return_value={base_q: result1, f"{base_q} guide": ""})
        crew._probe_serp_composition([idea])
        assert getattr(idea, "_serp_owned", False) is False


# ---------------------------------------------------------------------------
# _probe_niche_wallet
# ---------------------------------------------------------------------------

class TestProbeNicheWallet:
    def test_fail_soft_empty_when_ma_search_returns_none(self):
        crew = _crew()
        crew.niche_context = SimpleNamespace(niche_description="cottage food")
        crew._ma_search_batch = MagicMock(return_value={
            "cottage food software pricing": "",
            "site:reddit.com cottage food software cost": "",
            "free tools for cottage food": ""})
        out = crew._probe_niche_wallet()
        assert out == {}
        assert crew._niche_wallet_brief == {}

    def test_parses_wallet_class_via_invoke_structured(self):
        crew = _crew()
        crew.niche_context = SimpleNamespace(niche_description="cottage food")
        crew._ma_search_batch = MagicMock(return_value={
            "cottage food software pricing": "some search text",
            "site:reddit.com cottage food software cost": "some search text",
            "free tools for cottage food": "some search text"})
        fake = SimpleNamespace(wallet_class="mixed", evidence="priced tools exist",
                                free_density="a few free routes")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._probe_niche_wallet()
        assert out == {"wallet_class": "mixed", "evidence": "priced tools exist",
                        "free_density": "a few free routes"}

    def test_caches_second_call_no_new_searches(self):
        crew = _crew()
        crew.niche_context = SimpleNamespace(niche_description="cottage food")
        crew._ma_search_batch = MagicMock(return_value={
            "cottage food software pricing": "some search text",
            "site:reddit.com cottage food software cost": "some search text",
            "free tools for cottage food": "some search text"})
        fake = SimpleNamespace(wallet_class="paying", evidence="e", free_density="f")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)) as m:
            out1 = crew._probe_niche_wallet()
            out2 = crew._probe_niche_wallet()
        assert out1 == out2
        assert crew._ma_search_batch.call_count == 1  # only from the first (uncached) call
        assert m.call_count == 1

    def test_invalid_wallet_class_returns_empty(self):
        crew = _crew()
        crew.niche_context = SimpleNamespace(niche_description="cottage food")
        crew._ma_search_batch = MagicMock(return_value={
            "cottage food software pricing": "some search text",
            "site:reddit.com cottage food software cost": "some search text",
            "free tools for cottage food": "some search text"})
        fake = SimpleNamespace(wallet_class="unknown-class", evidence="e", free_density="f")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._probe_niche_wallet()
        assert out == {}


# ---------------------------------------------------------------------------
# _wallet_prompt_line / _build_market_reality_block
# ---------------------------------------------------------------------------

class TestWalletPromptLineAndMarketRealityBlock:
    def test_wallet_prompt_line_empty_when_no_wallet(self):
        crew = _crew()
        assert crew._wallet_prompt_line() == ""
        crew._niche_wallet_brief = {}
        assert crew._wallet_prompt_line() == ""

    def test_wallet_prompt_line_content_when_populated(self):
        crew = _crew(_niche_wallet_brief={
            "wallet_class": "mixed", "evidence": "priced tools exist",
            "free_density": "3 free tools"})
        line = crew._wallet_prompt_line()
        assert "mixed" in line
        assert "priced tools exist" in line
        assert "3 free tools" in line

    def test_market_reality_block_empty_when_no_incumbents(self):
        crew = _crew()
        assert crew._build_market_reality_block() == ""

    def test_market_reality_block_content_when_populated(self):
        crew = _crew(
            _incumbent_rows=[{"name": "Acme", "pricing": "$29/mo", "focus": "scheduling",
                               "gap": "no reporting"}],
            _niche_wallet_brief={"free_density": "3 free tools"})
        text = crew._build_market_reality_block()
        assert "Acme" in text
        assert "no reporting" in text
        assert "3 free tools" in text


# ---------------------------------------------------------------------------
# _probe_incumbents — niche-native-tool blind spot fix (2026-07-10; live-motivated by the
# wedding-photographers run + web-judge calibration: 2 enterprise-SaaS-framed queries missed
# the cheap niche-native tools the persona actually pays for, PhotoPills/Zenfolio/The LawTog)
# ---------------------------------------------------------------------------

class TestProbeIncumbents:
    def _crew_with_search(self, run_return="some incumbent Acme found here", **extra):
        crew = _crew(**extra)
        crew.search_tool = MagicMock()
        crew.search_tool.run.return_value = run_return
        crew.niche_context = SimpleNamespace(niche_description="wedding photography")
        return crew

    def test_third_query_issued_persona_toolbelt_framed(self):
        crew = self._crew_with_search()
        crew._ma_search = MagicMock(return_value=None)
        fake = SimpleNamespace(incumbents=[])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_incumbents()
        assert crew.search_tool.run.call_count == 3
        queries = [c.kwargs.get("search_query") for c in crew.search_tool.run.call_args_list]
        assert "best apps and tools for wedding photography" in queries

    def test_corpus_candidates_reach_extraction_prompt(self):
        crew = self._crew_with_search(run_return="no relevant tool names here")
        crew._ma_search = MagicMock(return_value=None)
        crew.audience_mapping = SimpleNamespace(tools_currently_used=["PhotoPills"])
        crew.competitor_mentions_text = "Photographers use **Zenfolio** for pricing."
        fake = SimpleNamespace(incumbents=[])
        captured = {}

        def _fake_invoke(prompt, **kw):
            captured["prompt"] = prompt
            return fake, None

        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_fake_invoke):
            crew._probe_incumbents()
        assert "PhotoPills" in captured["prompt"]
        assert "Zenfolio" in captured["prompt"]
        assert "CANDIDATE TOOLS" in captured["prompt"]

    def test_unconfirmed_candidate_not_in_rows(self):
        # extractor only confirms PhotoPills — GhostApp is a hint the mocked LLM chose not to
        # confirm, and must not appear in the rows just because it was a corpus candidate.
        crew = self._crew_with_search(run_return="no relevant tool names here")
        crew._ma_search = MagicMock(return_value=None)
        crew.audience_mapping = SimpleNamespace(tools_currently_used=["PhotoPills", "GhostApp"])
        crew.competitor_mentions_text = ""
        confirmed = SimpleNamespace(name="PhotoPills", pricing="$10 one-time",
                                     focus="exposure calculator", gap="no CRM")
        fake = SimpleNamespace(incumbents=[confirmed])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_incumbents()
        names = [r["name"] for r in crew._incumbent_rows]
        assert names == ["PhotoPills"]
        assert "GhostApp" not in names
        assert crew._incumbent_rows[0]["source"] == "corpus-confirmed"

    def test_web_only_row_tagged_source_web(self):
        crew = self._crew_with_search(run_return="Acme software mentioned here")
        crew._ma_search = MagicMock(return_value=None)
        crew.audience_mapping = None
        crew.competitor_mentions_text = ""
        found = SimpleNamespace(name="Acme", pricing="$29/mo", focus="scheduling", gap="no CRM")
        fake = SimpleNamespace(incumbents=[found])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_incumbents()
        assert crew._incumbent_rows[0]["source"] == "web"

    def test_verification_query_only_for_unfound_candidates_budgeted(self):
        crew = self._crew_with_search(run_return="PhotoPills is mentioned in these results")
        crew.audience_mapping = SimpleNamespace(
            tools_currently_used=["PhotoPills", "The LawTog"])
        crew.competitor_mentions_text = ""
        crew._ma_search = MagicMock(return_value="The LawTog $30 template pack")
        fake = SimpleNamespace(incumbents=[])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_incumbents()
        crew._ma_search.assert_called_once()
        (query,), _kw = crew._ma_search.call_args
        assert "The LawTog" in query
        assert "PhotoPills" not in query

    def test_no_verification_query_when_all_candidates_already_found(self):
        crew = self._crew_with_search(run_return="PhotoPills pricing info here")
        crew.audience_mapping = SimpleNamespace(tools_currently_used=["PhotoPills"])
        crew.competitor_mentions_text = ""
        crew._ma_search = MagicMock(return_value=None)
        fake = SimpleNamespace(incumbents=[])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_incumbents()
        crew._ma_search.assert_not_called()

    def test_extraction_cap_is_12(self):
        crew = self._crew_with_search(run_return="many tools mentioned")
        crew._ma_search = MagicMock(return_value=None)
        crew.audience_mapping = None
        crew.competitor_mentions_text = ""
        rows = [SimpleNamespace(name=f"Tool{i}", pricing="$1", focus="x", gap="y")
                for i in range(15)]
        fake = SimpleNamespace(incumbents=rows)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_incumbents()
        assert len(crew._incumbent_rows) == 12


# ---------------------------------------------------------------------------
# _parity_pivot_revisions
# ---------------------------------------------------------------------------

class _FakePivotResult:
    """Stand-in for the LLM-returned `_Pivot` pydantic model — only `.model_dump()` is used."""

    def __init__(self, **kw):
        self._data = kw

    def model_dump(self):
        return dict(self._data)


def _pivot_fields(**overrides):
    fields = dict(
        solution_name="PivotedApp", value_proposition="A repositioned wedge",
        description="Attacks the incumbent's known gap.", core_features=["gap-filling workflow"],
        conventional_approach="", innovation_angle="", why_it_works="",
        technical_approach="", data_access_model="public",
        market_fit_score=0.7, technical_feasibility_score=0.75,
        build_feasibility_score=0.7, data_feasibility_score=0.7,
        programmatic_seo_opportunity="",
    )
    fields.update(overrides)
    return fields


class TestParityPivotRevisions:
    def test_max_revisions_zero_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 0)
        crew = _crew()
        refined = SimpleNamespace(
            solution_ideas=[_idea(incumbent_parity="shipped by Acme")])
        assert crew._parity_pivot_revisions(refined) == (0, 0)

    def test_eligible_selection_only_active_shipped_or_partial(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 10)
        crew = _crew(_incumbent_rows=[])
        crew._score_wave = lambda wave: None
        ideas = [
            _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme", status="active"),
            _idea("Partial", mf=0.55, incumbent_parity="partial by Beta", status="active"),
            _idea("Substitute", mf=0.5, incumbent_parity="substitute: spreadsheets",
                  status="active"),
            _idea("NoneFound", mf=0.6, incumbent_parity="none found", status="active"),
            _idea("DemotedShipped", mf=0.45, incumbent_parity="shipped by Gamma",
                  status="demoted"),
        ]
        refined = SimpleNamespace(solution_ideas=ideas)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured") as m:
            m.return_value = (_FakePivotResult(solution_name="", value_proposition=""), None)
            attempted, accepted = crew._parity_pivot_revisions(refined)
        assert attempted == 2  # Shipped + Partial only
        assert m.call_count == 2
        assert accepted == 0

    def test_accepted_pivot_replaces_in_place(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 3)
        crew = _crew(_incumbent_rows=[])

        def _stamp_scored_cleared(wave):
            # mimics _score_wave's calibration critic (novelty/seo) + parity re-probe
            # (explicit clearance) — mocked here since the wave sequence itself isn't under
            # test in this class.
            for rev in wave:
                rev.incumbent_parity = "none found"
                rev.novelty_score = 0.6
                rev.seo_scalability_score = 0.6
        crew._score_wave = _stamp_scored_cleared
        orig = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme", status="active",
                     technical_feasibility_score=0.5, novelty_score=0.5,
                     seo_scalability_score=0.5)
        ideas = [orig]
        refined = SimpleNamespace(solution_ideas=ideas)
        fake = _FakePivotResult(**_pivot_fields(
            solution_name="PivotedApp", value_proposition="wedge into the gap",
            market_fit_score=0.75, technical_feasibility_score=0.8))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            attempted, accepted = crew._parity_pivot_revisions(refined)
        assert attempted == 1
        assert accepted == 1
        assert len(ideas) == 1
        assert orig not in ideas
        assert ideas[0].solution_name == "PivotedApp"

    def test_rejected_pivot_lower_composite_keeps_original(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 3)
        crew = _crew(_incumbent_rows=[])

        def _stamp_scored_cleared(wave):
            for rev in wave:
                rev.incumbent_parity = "none found"
                rev.novelty_score = 0.2
                rev.seo_scalability_score = 0.2
        crew._score_wave = _stamp_scored_cleared
        orig = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme", status="active",
                     technical_feasibility_score=0.5, novelty_score=0.5,
                     seo_scalability_score=0.5)
        ideas = [orig]
        refined = SimpleNamespace(solution_ideas=ideas)
        fake = _FakePivotResult(**_pivot_fields(
            solution_name="WeakPivot", value_proposition="a weaker wedge",
            market_fit_score=0.2, technical_feasibility_score=0.2))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            attempted, accepted = crew._parity_pivot_revisions(refined)
        assert attempted == 1
        assert accepted == 0
        assert ideas == [orig]

    def test_rejected_pivot_incomplete_score_vector_keeps_original(self, monkeypatch):
        # codex-review MAJOR: _Pivot's schema omits novelty/seo — a pivot revision that never
        # gets those dims stamped (e.g. _score_wave no-op / failure) must be rejected outright,
        # never compared on a partial composite.
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 3)
        crew = _crew(_incumbent_rows=[])
        crew._score_wave = lambda wave: None   # leaves novelty_score/seo_scalability_score None
        orig = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme", status="active",
                     technical_feasibility_score=0.5, novelty_score=0.5,
                     seo_scalability_score=0.5)
        ideas = [orig]
        refined = SimpleNamespace(solution_ideas=ideas)
        fake = _FakePivotResult(**_pivot_fields(
            solution_name="PivotedApp", value_proposition="wedge into the gap",
            market_fit_score=0.9, technical_feasibility_score=0.9))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            attempted, accepted = crew._parity_pivot_revisions(refined)
        assert attempted == 1
        assert accepted == 0
        assert ideas == [orig]

    def test_rejected_pivot_restamped_parity_keeps_original(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 3)
        crew = _crew(_incumbent_rows=[])

        def _restamp_shipped(wave):
            for rev in wave:
                rev.incumbent_parity = "shipped by Acme: same finding persists"
                rev.novelty_score = 0.6
                rev.seo_scalability_score = 0.6
        crew._score_wave = _restamp_shipped
        orig = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme", status="active",
                     technical_feasibility_score=0.5, novelty_score=0.5,
                     seo_scalability_score=0.5)
        ideas = [orig]
        refined = SimpleNamespace(solution_ideas=ideas)
        # High scores + a complete dim vector would beat the original's composite, but the
        # re-stamped parity finding (via the patched _score_wave side effect) is still
        # 'shipped', not an explicit 'none found' clearance — must still reject it.
        fake = _FakePivotResult(**_pivot_fields(
            solution_name="StrongButStillCovered", value_proposition="wedge attempt",
            market_fit_score=0.9, technical_feasibility_score=0.9))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            attempted, accepted = crew._parity_pivot_revisions(refined)
        assert attempted == 1
        assert accepted == 0
        assert ideas == [orig]


class TestCandidateStatusResetThenStamp:
    """Live-caught 2026-07-10: generator LLMs fabricated candidate_status 'ACCEPTED'/'ready'.
    _finalize_idea_pool must reset every birth-path idea to 'active' (reset-then-stamp doctrine);
    code stamps (demoted/absorbed/restored) happen AFTER this pass and are never wiped."""

    def test_fabricated_status_reset_to_active(self):
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.cost_tracker = None
        ideas = [
            SimpleNamespace(candidate_status="ACCEPTED", project_type="saas",
                            data_access_model="public", data_acquisition_notes=None,
                            solution_name="A", market_fit_score=0.5,
                            technical_feasibility_score=0.6, data_sources=None),
            SimpleNamespace(candidate_status="ready", project_type="saas",
                            data_access_model="public", data_acquisition_notes=None,
                            solution_name="B", market_fit_score=0.5,
                            technical_feasibility_score=0.6, data_sources=None),
        ]
        try:
            crew._finalize_idea_pool(ideas)
        except Exception:
            pass  # later vocab steps may need more attrs; the reset happens first
        assert all(i.candidate_status == "active" for i in ideas)

    def test_source_frame_normalized_to_closed_vocab(self):
        # Tournament-born ideas arrive with source_frame=None; generator LLMs can
        # fabricate values. Both normalize to 'pain'; real frame stamps are kept.
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.cost_tracker = None
        def _mk(name, frame):
            return SimpleNamespace(candidate_status="active", project_type="saas",
                                   data_access_model="public", data_acquisition_notes=None,
                                   solution_name=name, market_fit_score=0.5,
                                   technical_feasibility_score=0.6, data_sources=None,
                                   source_frame=frame)
        ideas = [_mk("A", None), _mk("B", "SPEND_ADJACENT"), _mk("C", "gap"),
                 _mk("D", "data_asset"), _mk("E", "workflow")]
        try:
            crew._finalize_idea_pool(ideas)
        except Exception:
            pass
        assert [i.source_frame for i in ideas] == ["pain", "pain", "gap", "data_asset", "workflow"]
