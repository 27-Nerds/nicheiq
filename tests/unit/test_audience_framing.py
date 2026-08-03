"""Tests for audience-aware framing (Part A): Stage-1 intent classifier (mocked LLM),
_resolve_primary_audience, and NicheContext serialization. Plus a skipped-by-default
calibration smoke test that hits the real classifier."""
import os
from types import SimpleNamespace

import pytest

import nicheiq.flows.research_flow as rf
from nicheiq.config.settings import settings
from nicheiq.models.research_state import NicheContext


def _nc(**over):
    base = dict(niche_input="x", niche_description="peptide supplements market",
                market_segments=["a", "b"], industry_boundaries="z")
    base.update(over)
    return NicheContext(**base)


# ---------------------------------------------------------------------------
# Stage-1 classifier (mocked LLM — no live equality, per the plan)
# ---------------------------------------------------------------------------
class TestStage1Classifier:
    def _flow(self, entry_mode=None):
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        flow.entry_mode = entry_mode
        flow._extract_niche_anchors = lambda *a, **k: None  # skip the 2nd LLM call
        return flow

    def _mock(self, monkeypatch, returned: NicheContext):
        captured = {}
        from nicheiq.utils.llm_service import LLMService

        def fake(*args, **kwargs):
            captured["prompt"] = kwargs.get("prompt", args[0] if args else None)
            captured["model_name"] = kwargs.get("model_name")
            return returned, SimpleNamespace(to_dict=lambda: {})

        monkeypatch.setattr(LLMService, "invoke_structured", fake)
        return captured

    def test_niche_guard_clears_fabricated_audience(self, monkeypatch):
        flow = self._flow("idea")
        self._mock(monkeypatch, _nc(audience_scope="niche", user_target_audience="peptide buyers"))
        ctx = flow._generate_niche_context("peptide supplements")
        assert ctx.audience_scope == "niche"
        assert ctx.user_target_audience is None  # do-NOT #1 enforced

    def test_segment_audience_preserved(self, monkeypatch):
        flow = self._flow("audience")
        self._mock(monkeypatch, _nc(audience_scope="segment_of_niche",
                                    user_target_audience="experienced tirzepatide users"))
        ctx = flow._generate_niche_context("experienced tirzepatide users")
        assert ctx.audience_scope == "segment_of_niche"
        assert ctx.user_target_audience == "experienced tirzepatide users"

    def test_focusable_scope_null_audience_falls_back_to_input(self, monkeypatch):
        # Real qwen failure mode: classifier sets a focusable scope but leaves
        # user_target_audience null (esp. when the whole input IS the audience).
        # The post-parse guard must backfill from the literal input so framing engages.
        flow = self._flow("audience")
        self._mock(monkeypatch, _nc(audience_scope="segment_of_niche", user_target_audience=None))
        ctx = flow._generate_niche_context("athletes and serious gym-goers interested in peptides")
        assert ctx.audience_scope == "segment_of_niche"
        assert ctx.user_target_audience == "athletes and serious gym-goers interested in peptides"

    def test_community_null_audience_falls_back_to_input(self, monkeypatch):
        flow = self._flow(None)
        self._mock(monkeypatch, _nc(audience_scope="community", user_target_audience="  "))
        ctx = flow._generate_niche_context("porsche owners")
        assert ctx.user_target_audience == "porsche owners"

    def test_empty_scope_and_blank_audience_default_to_niche(self, monkeypatch):
        flow = self._flow(None)
        self._mock(monkeypatch, _nc(audience_scope=None, user_target_audience="   "))
        ctx = flow._generate_niche_context("peptide supplements")
        assert ctx.audience_scope == "niche"
        assert ctx.user_target_audience is None

    def test_uses_niche_context_llm_model(self, monkeypatch):
        flow = self._flow(None)
        cap = self._mock(monkeypatch, _nc(audience_scope="niche"))
        flow._generate_niche_context("peptide supplements")
        assert cap["model_name"] == settings.niche_context_llm  # qwen, not openai_model_name

    def test_prompt_carries_classifier_contract_and_entry_hint(self, monkeypatch):
        flow = self._flow("audience")
        cap = self._mock(monkeypatch, _nc(audience_scope="segment_of_niche", user_target_audience="x"))
        flow._generate_niche_context("x")
        p = cap["prompt"]
        assert "audience_scope" in p and "user_target_audience" in p
        assert "segment_of_niche" in p and "community" in p and "too_broad" in p
        assert "audience" in p.lower()  # entry-mode hint present

    # --- mode-independence: the feature keys off audience_scope (input), not entry_mode ---
    @pytest.mark.parametrize(
        "mode", [None, "idea", "audience", "discovery", "pain_research", "deep_idea", "pain_remix",
                 "some_future_mode"])
    def test_audience_classification_is_mode_independent(self, monkeypatch, mode):
        """Same audience input → identical classification + populated audience under EVERY
        entry mode (incl. unknown/future). entry_mode is only a prior; the classifier decides."""
        flow = self._flow(mode)
        self._mock(monkeypatch, _nc(audience_scope="segment_of_niche",
                                    user_target_audience="athletes interested in peptides"))
        ctx = flow._generate_niche_context("athletes interested in peptides")
        assert ctx.audience_scope == "segment_of_niche"
        assert ctx.user_target_audience == "athletes interested in peptides"

    @pytest.mark.parametrize("mode", [None, "idea", "audience", "discovery", "some_future_mode"])
    def test_breadth_instructions_present_in_every_mode(self, monkeypatch, mode):
        """The broaden-the-market instruction + worked example are delivered regardless of mode,
        so an audience input can't silently narrow market_segments in any mode."""
        flow = self._flow(mode)
        cap = self._mock(monkeypatch, _nc(audience_scope="segment_of_niche", user_target_audience="x"))
        flow._generate_niche_context("x")
        p = cap["prompt"]
        assert "BROAD market" in p              # the breadth directive (STEP 2/4)
        assert "WORKED EXAMPLE" in p            # contrastive ✓/✗ example
        assert "WRONG" in p                     # the narrowing anti-example
        # never crashes on an unknown mode (degrades to the neutral prior)
        assert "audience_scope" in p

    @pytest.mark.parametrize("mode", [None, "idea", "audience", "discovery", "pain_research"])
    def test_null_audience_fallback_is_mode_independent(self, monkeypatch, mode):
        """The focusable-scope + null-audience fallback fires under every mode."""
        flow = self._flow(mode)
        self._mock(monkeypatch, _nc(audience_scope="segment_of_niche", user_target_audience=None))
        ctx = flow._generate_niche_context("athletes interested in peptides")
        assert ctx.user_target_audience == "athletes interested in peptides"


# ---------------------------------------------------------------------------
# _resolve_primary_audience
# ---------------------------------------------------------------------------
class TestResolvePrimaryAudience:
    def _run(self, scope, audience, segs=None, caveats=None, primary_target_segment=None,
             user_audience_scope=None):
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope=scope, user_target_audience=audience)
        am = (SimpleNamespace(audience_segments=[SimpleNamespace(segment_name=s) for s in segs],
                              primary_target_segment=primary_target_segment)
              if segs is not None else None)
        flow._state = SimpleNamespace(niche_context=nc, audience_mapping=am,
                                      idea_coverage_caveats=list(caveats or []),
                                      user_audience_scope=user_audience_scope)
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._resolve_primary_audience()
        return nc, flow._state.idea_coverage_caveats

    def test_segment_match_returns_segment_name(self):
        nc, _ = self._run("segment_of_niche", "experienced tirzepatide users",
                          ["Experimental Tirzepatide & Peptide Compound Users", "Skincare Enthusiasts"])
        assert nc.resolved_primary_audience == "Experimental Tirzepatide & Peptide Compound Users"

    def test_segment_no_match_falls_back_to_raw(self):
        nc, _ = self._run("segment_of_niche", "experienced tirzepatide users",
                          ["Totally Unrelated", "Other Thing"])
        assert nc.resolved_primary_audience == "experienced tirzepatide users"

    def test_community_no_resolution_no_caveat(self):
        nc, cav = self._run("community", "porsche owners", ["Track-day enthusiasts"])
        assert nc.resolved_primary_audience is None
        assert cav == []

    def test_too_broad_adds_breadth_caveat(self):
        nc, cav = self._run("too_broad", "older adults", None)
        assert nc.resolved_primary_audience is None
        assert any("broad" in c.lower() for c in cav)

    def test_niche_is_noop(self):
        nc, cav = self._run("niche", None, None)
        assert nc.resolved_primary_audience is None
        assert cav == []

    def test_refine_against_ideas_upgrades_to_matchable_segment(self):
        # Stage-4 guessed a persona label; post-generation refinement must re-point
        # resolved_primary_audience to the idea source_segment the frontend actually matches.
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="segment_of_niche", user_target_audience="GLP-1 users",
                 resolved_primary_audience="The Biohacker Optimizer")
        ideas = [SimpleNamespace(source_segment="Peptide buyers"),
                 SimpleNamespace(source_segment="GLP-1 users"),
                 SimpleNamespace(source_segment="PT-141 users")]
        flow._state = SimpleNamespace(niche_context=nc,
                                      idea_generation=SimpleNamespace(solution_ideas=ideas))
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._refine_audience_against_ideas()
        assert nc.resolved_primary_audience == "GLP-1 users"

    def test_refine_against_ideas_upgrades_to_dominant_peptide_segment(self):
        # The real peptides run: "...peptides supplements" overlaps "Peptide buyers" (0.5 >= 0.40
        # via overlap/min), so framing upgrades to that matchable segment → the grid can split.
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="segment_of_niche",
                 user_target_audience="athletes and serious gym-goers interested in peptides supplements",
                 resolved_primary_audience="athletes and serious gym-goers interested in peptides supplements")
        ideas = [SimpleNamespace(source_segment="Peptide buyers"),
                 SimpleNamespace(source_segment="PT-141 users")]
        flow._state = SimpleNamespace(niche_context=nc,
                                      idea_generation=SimpleNamespace(solution_ideas=ideas))
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._refine_audience_against_ideas()
        assert nc.resolved_primary_audience == "Peptide buyers"

    def test_refine_against_ideas_left_alone_when_no_overlap(self):
        # An audience sharing no stem-tokens with any idea segment → unchanged (raw), single eyebrow.
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="segment_of_niche", user_target_audience="left-handed guitarists",
                 resolved_primary_audience="left-handed guitarists")
        ideas = [SimpleNamespace(source_segment="Peptide buyers"),
                 SimpleNamespace(source_segment="PT-141 users")]
        flow._state = SimpleNamespace(niche_context=nc,
                                      idea_generation=SimpleNamespace(solution_ideas=ideas))
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._refine_audience_against_ideas()
        assert nc.resolved_primary_audience == "left-handed guitarists"

    def test_refine_g2_override_redirects_to_matching_idea_segment(self):
        # 1.2(c): a G2 primary override maps into the idea-segment namespace and wins.
        from nicheiq.models.research_state import AudienceScope
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="segment_of_niche", user_target_audience="GLP-1 users",
                 resolved_primary_audience="GLP-1 users")
        ideas = [SimpleNamespace(source_segment="Peptide buyers"),
                 SimpleNamespace(source_segment="GLP-1 users"),
                 SimpleNamespace(source_segment="PT-141 users")]
        flow._state = SimpleNamespace(
            niche_context=nc, idea_generation=SimpleNamespace(solution_ideas=ideas),
            user_audience_scope=AudienceScope(primary_target_segment="PT-141 users"),
            idea_coverage_caveats=[])
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._refine_audience_against_ideas()
        assert nc.resolved_primary_audience == "PT-141 users"
        assert flow._state.idea_coverage_caveats == []

    def test_refine_g2_override_mismatch_keeps_label_and_adds_caveat(self):
        # 1.2(c): an override with no matching idea segment must NOT overwrite the label —
        # keep it, log, and surface an idea_coverage_caveat.
        from nicheiq.models.research_state import AudienceScope
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="segment_of_niche", user_target_audience="GLP-1 users",
                 resolved_primary_audience="GLP-1 users")
        ideas = [SimpleNamespace(source_segment="Peptide buyers"),
                 SimpleNamespace(source_segment="GLP-1 users")]
        flow._state = SimpleNamespace(
            niche_context=nc, idea_generation=SimpleNamespace(solution_ideas=ideas),
            user_audience_scope=AudienceScope(primary_target_segment="Enterprise procurement teams"),
            idea_coverage_caveats=[])
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._refine_audience_against_ideas()
        assert nc.resolved_primary_audience == "GLP-1 users"
        assert any("Enterprise procurement teams" in c for c in flow._state.idea_coverage_caveats)

    def test_refine_against_ideas_noop_for_non_segment_scope(self):
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="community", user_target_audience="porsche owners",
                 resolved_primary_audience=None)
        flow._state = SimpleNamespace(niche_context=nc,
                                      idea_generation=SimpleNamespace(
                                          solution_ideas=[SimpleNamespace(source_segment="porsche owners")]))
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._refine_audience_against_ideas()
        assert nc.resolved_primary_audience is None

    def test_best_segment_match_threshold(self):
        f = rf._best_segment_match  # module-level (not a Flow method)
        assert f("GLP-1 users", ["Peptide buyers", "GLP-1 users", "PT-141 users"]) == "GLP-1 users"
        assert f("completely unrelated xyz topic", ["Peptide buyers"]) is None  # 0 overlap
        assert f("", ["x"]) is None and f("x", []) is None

    # --- 1.2(a): keyword-only `preferred` tie-break (eps=1e-9, raw intersection, stable-first) ---
    def test_preferred_breaks_exact_tie(self):
        f = rf._best_segment_match
        # Both score 0.5 ("users" overlaps, min token-set size 2) — preferred wins the tie.
        names = ["GLP-1 users", "PT-141 users"]
        assert f("peptide users", names) == "GLP-1 users"  # stable-first without preferred
        assert f("peptide users", names, preferred="PT-141 users") == "PT-141 users"

    def test_preferred_never_overrides_strictly_higher_score(self):
        f = rf._best_segment_match
        assert f("GLP-1 users", ["GLP-1 users", "PT-141 users"],
                 preferred="PT-141 users") == "GLP-1 users"

    def test_tie_prefers_higher_raw_intersection(self):
        f = rf._best_segment_match
        # Both score 1.0 (overlap/min) but the longer name shares MORE raw tokens.
        assert f("alpha beta gamma delta", ["alpha beta", "alpha beta gamma"]) == "alpha beta gamma"

    def test_tie_is_stable_first_without_preferred_or_intersection_edge(self):
        f = rf._best_segment_match
        assert f("alpha beta", ["alpha beta", "beta alpha"]) == "alpha beta"

    # --- 1.2(b): G2 override exact-first -> S4-preferred fuzzy -> raw ---
    def test_g2_override_exact_wins_over_fuzzy(self):
        from nicheiq.models.research_state import AudienceScope
        nc, _ = self._run("segment_of_niche", "experienced tirzepatide users",
                          ["Experimental Tirzepatide & Peptide Compound Users", "Skincare Enthusiasts"],
                          user_audience_scope=AudienceScope(
                              primary_target_segment="Skincare Enthusiasts"))
        assert nc.resolved_primary_audience == "Skincare Enthusiasts"

    def test_g2_override_unknown_name_falls_back_to_fuzzy(self):
        from nicheiq.models.research_state import AudienceScope
        nc, _ = self._run("segment_of_niche", "experienced tirzepatide users",
                          ["Experimental Tirzepatide & Peptide Compound Users", "Skincare Enthusiasts"],
                          user_audience_scope=AudienceScope(primary_target_segment="No Such Segment"))
        assert nc.resolved_primary_audience == "Experimental Tirzepatide & Peptide Compound Users"

    def test_s4_primary_breaks_fuzzy_tie(self):
        # "peptide users" ties (0.5) between the two segments; the Stage-4 primary wins.
        nc, _ = self._run("segment_of_niche", "peptide users",
                          ["GLP-1 users", "PT-141 users"],
                          primary_target_segment="PT-141 users")
        assert nc.resolved_primary_audience == "PT-141 users"

    def test_idempotent_no_duplicate_caveat(self):
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope="too_broad", user_target_audience="older adults")
        flow._state = SimpleNamespace(niche_context=nc, audience_mapping=None, idea_coverage_caveats=[])
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        flow._resolve_primary_audience()
        flow._resolve_primary_audience()
        breadth = [c for c in flow._state.idea_coverage_caveats if "broad" in c.lower()]
        assert len(breadth) == 1  # not duplicated on re-run


# ---------------------------------------------------------------------------
# _tag_audience_fit (semantic primary/adjacent signal; fail-open)
# ---------------------------------------------------------------------------
class TestTagAudienceFit:
    def _flow(self, scope="segment_of_niche", audience="athletes interested in peptides",
              names=("A", "B", "C")):
        flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
        nc = _nc(audience_scope=scope, user_target_audience=audience)
        ideas = [SimpleNamespace(solution_name=n, source_segment="Peptide buyers",
                                 target_personas=[f"{n} persona"], audience_fit=None)
                 for n in names]
        flow._state = SimpleNamespace(niche_context=nc,
                                      idea_generation=SimpleNamespace(solution_ideas=ideas))
        flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: None)
        return flow, ideas

    def _mock(self, monkeypatch, serves):
        from nicheiq.models.solution_idea import AudienceFitResult
        from nicheiq.utils.llm_service import LLMService
        monkeypatch.setattr(LLMService, "invoke_structured",
                            lambda **k: (AudienceFitResult(serves_audience=list(serves)), None))

    def test_tags_fit_true_false_by_name(self, monkeypatch):
        flow, ideas = self._flow(names=("A", "B", "C"))
        self._mock(monkeypatch, ["A", "C"])
        flow._tag_audience_fit()
        assert [i.audience_fit for i in ideas] == [True, False, True]

    def test_fail_open_leaves_none(self, monkeypatch):
        flow, ideas = self._flow()
        from nicheiq.utils.llm_service import LLMService
        def boom(**k): raise RuntimeError("llm down")
        monkeypatch.setattr(LLMService, "invoke_structured", boom)
        flow._tag_audience_fit()
        assert all(i.audience_fit is None for i in ideas)  # falls back to source_segment match

    def test_empty_result_is_inconclusive_none(self, monkeypatch):
        flow, ideas = self._flow()
        self._mock(monkeypatch, [])
        flow._tag_audience_fit()
        assert all(i.audience_fit is None for i in ideas)

    def test_noop_for_non_segment_scope(self, monkeypatch):
        flow, ideas = self._flow(scope="community")
        self._mock(monkeypatch, ["A"])  # would tag, but scope gates it out
        flow._tag_audience_fit()
        assert all(i.audience_fit is None for i in ideas)


# ---------------------------------------------------------------------------
# Serialization (no LLM) — new fields ride to the frontend as null by default
# ---------------------------------------------------------------------------
class TestNicheContextSerialization:
    def test_new_fields_default_none_in_model_dump(self):
        d = _nc().model_dump()
        for k in ("user_target_audience", "resolved_primary_audience", "audience_scope"):
            assert k in d and d[k] is None

    def test_legacy_payload_without_fields_loads(self):
        # extra='ignore' + defaults => old checkpoints/JSON deserialize unchanged
        nc = NicheContext.model_validate({
            "niche_input": "x", "niche_description": "y",
            "market_segments": ["a"], "industry_boundaries": "z",
        })
        assert nc.audience_scope is None and nc.user_target_audience is None


# ---------------------------------------------------------------------------
# Calibration smoke test (real LLM) — skipped by default; run with RUN_CLASSIFIER_SMOKE=1
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not os.getenv("RUN_CLASSIFIER_SMOKE"),
                    reason="calibration smoke test hits the real classifier; set RUN_CLASSIFIER_SMOKE=1")
def test_classifier_smoke_real_llm():
    cases = {
        "peptide supplements": "niche",
        "experienced tirzepatide users": "segment_of_niche",
        "left-handed guitarists": "segment_of_niche",
        "porsche owners": "community",
        "new parents": "community",
        "older adults": "too_broad",
    }
    flow = rf.ResearchFlow.__new__(rf.ResearchFlow)
    flow.entry_mode = None
    flow._extract_niche_anchors = lambda *a, **k: None
    wrong = []
    for text, expected in cases.items():
        ctx = flow._generate_niche_context(text)
        if (ctx.audience_scope or "") != expected:
            wrong.append((text, expected, ctx.audience_scope))
    assert len(wrong) <= 1, f"classifier drifted on >1 case: {wrong}"
