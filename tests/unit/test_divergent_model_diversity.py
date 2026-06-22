"""
Tests for multi-model divergent ideation + embedding semantic dedup (Phase 6).

Covers:
- Settings.brainstorm_model_pool: parsing + fallback to brainstorm_llm
- _generate_divergent_pool: per-sample model round-robin across the pool
- _semantic_dedup: drops the more-obvious near-duplicate, keeps the most-novel,
  respects the MIN_KEEP floor, and is FAIL-OPEN (threshold<=0 / embedding error
  both return the input unchanged)
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.config.settings import Settings


def _raw(name, obv=-1.0, one_liner=None, why=None):
    """A RawConcept-shaped stub (semantic dedup only reads these four attrs)."""
    return SimpleNamespace(
        concept_name=name,
        one_liner=one_liner or f"{name} does a thing",
        why_non_obvious=why or "",
        obviousness_score=obv,
    )


# ----------------------------- Settings.brainstorm_model_pool -----------------------------

class TestBrainstormModelPool:
    def test_empty_falls_back_to_single_model(self):
        s = Settings(brainstorm_llm="gpt-5.2", brainstorm_llms="")
        assert s.brainstorm_model_pool == ["gpt-5.2"]

    def test_parses_and_strips_comma_list(self):
        s = Settings(brainstorm_llms="a, b ,c")
        assert s.brainstorm_model_pool == ["a", "b", "c"]

    def test_blank_entries_dropped(self):
        s = Settings(brainstorm_llm="x", brainstorm_llms=" , , ")
        assert s.brainstorm_model_pool == ["x"]


class TestBrainstormPoolResolved:
    """Per-model reasoning effort via inline '@effort' (e.g. '.../deepseek@none')."""

    def test_inline_effort_parsed_per_model(self):
        s = Settings(brainstorm_llms="openrouter/moonshotai/kimi-k2.6@medium,openrouter/deepseek/deepseek-v4-pro@none")
        assert s.brainstorm_pool_resolved == [
            ("openrouter/moonshotai/kimi-k2.6", "medium"),
            ("openrouter/deepseek/deepseek-v4-pro", "none"),
        ]
        # model-only pool strips the effort
        assert s.brainstorm_model_pool == [
            "openrouter/moonshotai/kimi-k2.6",
            "openrouter/deepseek/deepseek-v4-pro",
        ]

    def test_entries_without_effort_inherit_default(self):
        s = Settings(brainstorm_reasoning_effort="high", brainstorm_llms="a@low,b")
        assert s.brainstorm_pool_resolved == [("a", "low"), ("b", "high")]

    def test_free_suffix_not_split_as_effort(self):
        """Model ids use ':' (e.g. ':free'), never '@' — must not be parsed as effort."""
        s = Settings(brainstorm_reasoning_effort="medium",
                     brainstorm_llms="openrouter/google/gemma-4-31b-it:free")
        assert s.brainstorm_pool_resolved == [("openrouter/google/gemma-4-31b-it:free", "medium")]

    def test_empty_falls_back_to_single_model(self):
        s = Settings(brainstorm_llm="gpt-5.2", brainstorm_reasoning_effort="medium", brainstorm_llms="")
        assert s.brainstorm_pool_resolved == [("gpt-5.2", "medium")]


# ----------------------------- per-sample model round-robin -----------------------------

class TestDivergentModelRoundRobin:
    def test_samples_round_robin_over_pool(self, monkeypatch):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens, **kw: "PROMPT", raising=False)

        calls = []

        def fake_invoke(prompt, output_model, **kw):
            calls.append(kw["model_name"])
            return SimpleNamespace(concepts=[_raw("A")]), SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda batch, **kw: (True, None))
        monkeypatch.setattr(usc.settings, "brainstorm_llms", "m1,m2,m3")
        monkeypatch.setattr(usc.settings, "num_divergent_samples", 3)

        pooled, _usages = crew._generate_divergent_pool({})

        assert sorted(calls) == ["m1", "m2", "m3"]
        assert len(pooled) == 3

    def test_single_model_used_for_all_when_pool_unset(self, monkeypatch):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens, **kw: "PROMPT", raising=False)

        calls = []

        def fake_invoke(prompt, output_model, **kw):
            calls.append(kw["model_name"])
            return SimpleNamespace(concepts=[_raw("A")]), SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda batch, **kw: (True, None))
        monkeypatch.setattr(usc.settings, "brainstorm_llms", "")
        monkeypatch.setattr(usc.settings, "brainstorm_llm", "solo-model")
        monkeypatch.setattr(usc.settings, "num_divergent_samples", 2)

        crew._generate_divergent_pool({})
        assert calls == ["solo-model", "solo-model"]

    def test_deadline_abandons_hung_sample(self, monkeypatch):
        import time

        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens, **kw: "P", raising=False)

        def fake_invoke(prompt, output_model, **kw):
            if kw["model_name"] == "slow":
                time.sleep(5)  # exceeds the deadline -> must be abandoned
            return SimpleNamespace(concepts=[_raw("A")]), SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda b, **k: (True, None))
        monkeypatch.setattr(usc.settings, "brainstorm_llms", "fast1,slow,fast2")
        monkeypatch.setattr(usc.settings, "num_divergent_samples", 3)
        monkeypatch.setattr(usc.settings, "divergent_sample_deadline_seconds", 1)

        t = time.time()
        pooled, _usages = crew._generate_divergent_pool({})
        elapsed = time.time() - t

        assert elapsed < 4  # returned at the deadline, did NOT wait for the 5s sample
        assert len(pooled) == 2  # the two fast samples; the hung one was abandoned


# ----------------------------- embedding semantic dedup -----------------------------

def _fake_openai_factory(vectors, raise_exc=None):
    """Build a stand-in openai.OpenAI returning `vectors` (in input order)."""

    class _Emb:
        def create(self, model, input):
            if raise_exc:
                raise raise_exc
            data = [SimpleNamespace(embedding=vectors[i]) for i in range(len(input))]
            return SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=10))

    class _Client:
        def __init__(self, api_key=None):
            self.embeddings = _Emb()

    return _Client


class TestSemanticDedup:
    def _crew(self):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        crew.cost_tracker = None
        return crew

    def test_drops_more_obvious_near_duplicate(self, monkeypatch):
        crew = self._crew()
        # 0 and 1 are identical embeddings; 1 is the more-obvious one => dropped.
        concepts = [
            _raw("Keep", obv=0.1),     # 0
            _raw("DupObvious", obv=0.9),  # 1 (near-dup of 0, more obvious)
            _raw("C", obv=0.2),        # 2
            _raw("D", obv=0.3),        # 3
            _raw("E", obv=0.4),        # 4
            _raw("F", obv=0.5),        # 5
            _raw("G", obv=0.6),        # 6
        ]
        vectors = [
            [1, 0, 0, 0, 0, 0, 0],  # 0
            [1, 0, 0, 0, 0, 0, 0],  # 1 (cos=1.0 vs 0)
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
        ]
        monkeypatch.setattr("openai.OpenAI", _fake_openai_factory(vectors))

        out = crew._semantic_dedup(concepts, 0.85)
        names = {c.concept_name for c in out}
        assert "Keep" in names
        assert "DupObvious" not in names
        assert len(out) == 6

    def test_threshold_zero_is_noop(self, monkeypatch):
        crew = self._crew()
        concepts = [_raw(f"c{i}", obv=0.1 * i) for i in range(7)]
        # Should never even call embeddings.
        monkeypatch.setattr(
            "openai.OpenAI",
            _fake_openai_factory([], raise_exc=AssertionError("should not embed")),
        )
        assert crew._semantic_dedup(concepts, 0.0) is concepts

    def test_skips_when_at_or_below_floor(self, monkeypatch):
        crew = self._crew()
        concepts = [_raw(f"c{i}") for i in range(6)]  # == MIN_KEEP
        monkeypatch.setattr(
            "openai.OpenAI",
            _fake_openai_factory([], raise_exc=AssertionError("should not embed")),
        )
        assert crew._semantic_dedup(concepts, 0.85) is concepts

    def test_fail_open_on_embedding_error(self, monkeypatch):
        crew = self._crew()
        concepts = [_raw(f"c{i}", obv=0.1 * i) for i in range(7)]
        monkeypatch.setattr(
            "openai.OpenAI",
            _fake_openai_factory([], raise_exc=RuntimeError("boom")),
        )
        assert crew._semantic_dedup(concepts, 0.85) is concepts

    def test_floor_guard_refills_when_overcollapsed(self, monkeypatch):
        crew = self._crew()
        # 8 concepts, all identical embeddings => greedy keeps only 1, floor refills to 6.
        concepts = [_raw(f"c{i}", obv=0.1 * i) for i in range(8)]
        vectors = [[1, 0, 0] for _ in range(8)]
        monkeypatch.setattr("openai.OpenAI", _fake_openai_factory(vectors))
        out = crew._semantic_dedup(concepts, 0.85)
        assert len(out) == 6  # MIN_KEEP floor respected, not collapsed to 1


# ----------------------------- pain-partitioned divergent (v1) -----------------------------

def _pain(title):
    return SimpleNamespace(
        title=title, description=f"desc {title}", severity_score=0.8,
        willingness_to_pay=0.7, opportunity_level="high", mention_count=10,
        affected_segments=["Seg"], representative_quotes=["q1", "q2"],
    )


class TestPartitionedDivergent:
    def _crew(self):
        return usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)

    def test_flag_off_render_is_identical(self):
        """partitioned_mode_block='' must leave the task starting with **TASK 1, no stray var."""
        import yaml
        tmpl = yaml.safe_load(open("src/nicheiq/crews/config/unified_solution_tasks.yaml"))[
            "divergent_exploration"]["description"]
        off = usc._interpolate_template(tmpl, {"partitioned_mode_block": ""})
        assert "{partitioned_mode_block}" not in off
        assert off.lstrip().startswith("**TASK 1")

    def test_one_generator_per_pain_with_distinct_briefs(self, monkeypatch):
        crew = self._crew()
        # render returns the per-agent block so we can inspect each agent's brief
        monkeypatch.setattr(crew, "_render_divergent_prompt",
                            lambda inputs, lens, **kw: kw.get("partitioned_mode_block", ""), raising=False)
        prompts = []

        def fake_invoke(prompt, output_model, **kw):
            prompts.append(prompt)
            return SimpleNamespace(concepts=[_raw("A"), _raw("B"), _raw("C")]), SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda b, **k: (True, None))
        monkeypatch.setattr(usc.settings, "enable_pain_partitioned_divergent", True)
        monkeypatch.setattr(usc.settings, "brainstorm_llms", "m1,m2,m3")
        monkeypatch.setattr(usc.settings, "divergent_max_generators", 8)
        monkeypatch.setattr(usc.settings, "divergent_target_generators", 6)
        monkeypatch.setattr(usc.settings, "divergent_target_pool", 15)
        monkeypatch.setattr(usc.settings, "divergent_max_workers", 8)
        monkeypatch.setattr(usc.settings, "divergent_sample_deadline_seconds", 30)

        pains = [_pain(f"Pain {c}") for c in "ABCDEF"]
        cells = crew._build_partition_cells(pains, [])  # no audience_mapping -> 1 cell/pain (segment=None)
        pooled, _u = crew._generate_divergent_pool({}, partition_cells=cells)

        assert len(prompts) == 6  # 6 cells (target=6, <= max 8); per_cell=clamp(round(15/6),3,4)=3
        # each pain appears in exactly one brief
        for p in pains:
            assert sum(p.title in pr for pr in prompts) == 1
        # info-products are NOT discouraged — the archetype steer must present them as valid
        assert all("programmatic-SEO" in pr or "directory" in pr for pr in prompts)
        # personas rotate (>=2 distinct persona lines present across briefs)
        personas_seen = {persona for persona in usc._DIVERGENT_PERSONAS
                         if any(persona in pr for pr in prompts)}
        assert len(personas_seen) >= 2
        assert len(pooled) == 18  # 6 cells x 3 each, no top-up

    def test_allow_zero_does_not_retry(self, monkeypatch):
        crew = self._crew()
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens, **kw: "P", raising=False)
        calls = {"n": 0}

        def fake_invoke(prompt, output_model, **kw):
            calls["n"] += 1
            return SimpleNamespace(concepts=[]), SimpleNamespace()  # legitimate empty

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda b, **k: (True, None))

        valid, _u = crew._one_sample({}, idx=0, lens="L", model="m", effort=None,
                                     partitioned_block="b", min_concepts=0, allow_zero=True, timeout=5)
        assert valid == []
        assert calls["n"] == 1  # no re-prompt on a legitimate no-fit empty batch

    def test_persona_uses_real_research_segment_when_available(self):
        crew = self._crew()
        seg = SimpleNamespace(
            segment_name="Powerlifters", expertise_level="Advanced",
            budget_sensitivity="Low", motivation_drivers=["joint healing", "longevity"],
            pain_point_alignment=["tendon recovery"],
        )
        crew.audience_mapping = SimpleNamespace(audience_segments=[seg])
        pain = _pain("tendon recovery failure")
        pain.affected_segments = ["Powerlifters"]
        persona = crew._persona_for_pain(pain, 0)
        assert "Powerlifters" in persona          # real niche segment, not a generic archetype
        assert "joint healing" in persona          # carries its motivation drivers

    def test_persona_falls_back_to_archetypes_without_audience_mapping(self):
        crew = self._crew()  # __new__ -> no audience_mapping attribute at all
        persona = crew._persona_for_pain(_pain("X"), 1)
        assert persona in usc._DIVERGENT_PERSONAS

    def test_archetype_directive_respects_allowed_types(self):
        d = usc._archetype_directive(["saas", "marketplace"])
        assert "saas / marketplace" in d and "Use ONLY an allowed type" in d
        assert "directory" not in d  # restricted set -> info-product types not offered
        d2 = usc._archetype_directive(None)  # unrestricted
        assert "directory" in d2 and "programmatic-SEO" in d2  # info-products presented as first-class

    def test_partitioned_brief_respects_allowed_project_types(self, monkeypatch):
        crew = self._crew()
        crew.allowed_project_types = ["saas", "marketplace"]  # UI restriction
        monkeypatch.setattr(crew, "_render_divergent_prompt",
                            lambda inputs, lens, **kw: kw.get("partitioned_mode_block", ""), raising=False)
        prompts = []

        def fake_invoke(prompt, output_model, **kw):
            prompts.append(prompt)
            return SimpleNamespace(concepts=[_raw("A"), _raw("B"), _raw("C")]), SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda b, **k: (True, None))
        monkeypatch.setattr(usc.settings, "enable_pain_partitioned_divergent", True)
        monkeypatch.setattr(usc.settings, "brainstorm_llms", "m1,m2")
        monkeypatch.setattr(usc.settings, "divergent_max_generators", 8)
        monkeypatch.setattr(usc.settings, "divergent_target_generators", 6)
        monkeypatch.setattr(usc.settings, "divergent_target_pool", 15)
        monkeypatch.setattr(usc.settings, "divergent_max_workers", 8)
        monkeypatch.setattr(usc.settings, "divergent_sample_deadline_seconds", 30)

        cells = crew._build_partition_cells([_pain(f"Pain {c}") for c in "ABC"], [])
        crew._generate_divergent_pool({}, partition_cells=cells)
        assert prompts and all("saas / marketplace" in pr for pr in prompts)
        assert all("directory" not in pr for pr in prompts)  # restriction honored per generator

    def test_below_two_cells_uses_legacy(self, monkeypatch):
        """partition_cells=None (caller's floor) -> legacy broad path, not partitioned."""
        crew = self._crew()
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens, **kw: "P", raising=False)

        def fake_invoke(prompt, output_model, **kw):
            return SimpleNamespace(concepts=[_raw("A")]), SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(fake_invoke))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda b, **k: (True, None))
        monkeypatch.setattr(usc.settings, "enable_pain_partitioned_divergent", True)
        monkeypatch.setattr(usc.settings, "brainstorm_llms", "m1,m2")
        monkeypatch.setattr(usc.settings, "num_divergent_samples", 2)
        # partition_cells=None => legacy path even with the flag on
        pooled, _u = crew._generate_divergent_pool({}, partition_cells=None)
        assert len(pooled) == 2  # num_divergent_samples broad samples


# ----------------------------- (pain × segment) cell assignment + provenance -----------------------------

def _seg(name, align=None):
    return SimpleNamespace(segment_name=name, pain_point_alignment=align or [],
                           expertise_level="Intermediate", budget_sensitivity="Medium",
                           motivation_drivers=["x"])


def _pain_seg(title, segs, opp="high", sev=0.8):
    p = _pain(title)
    p.affected_segments = list(segs)
    p.opportunity_level = opp
    p.severity_score = sev
    return p


class TestCellAssignment:
    def test_one_cell_per_edge_spread_and_coverage(self):
        segs = [_seg("Novice"), _seg("Performance"), _seg("Rehab")]
        A = _pain_seg("verify purity", ["Novice", "Performance", "Rehab"], "high", 0.9)
        B = _pain_seg("predict effects", ["Novice", "Performance"], "medium", 0.7)
        C = _pain_seg("no clinical data", ["Novice", "Performance"], "medium", 0.6)
        cells = usc._assign_generator_cells([A, B, C], segs, target=6, max_gen=8)
        assert len(cells) == 6
        assert {c["pain"].title for c in cells} == {"verify purity", "predict effects", "no clinical data"}
        names = [c["segment"].segment_name for c in cells]
        assert set(names) == {"Novice", "Performance", "Rehab"}  # all segments exercised
        share = max(names.count(n) for n in set(names)) / len(names)
        assert share <= 0.5  # per-segment cap de-clusters (was 1.0 = 3x Novice)
        pairs = {(c["pain"].title, c["segment"].segment_name) for c in cells}
        assert len(pairs) == len(cells)  # distinct (pain, segment) cells

    def test_fallback_no_segments_one_cell_per_pain(self):
        pains = [_pain(f"P{i}") for i in range(4)]
        cells = usc._assign_generator_cells(pains, [], target=6, max_gen=8)
        assert len(cells) == 4 and all(c["segment"] is None for c in cells)

    def test_cap_respected_and_coverage_when_edges_exceed_cap(self):
        segs = [_seg(f"S{i}") for i in range(5)]
        pains = [_pain_seg(f"P{i}", [s.segment_name for s in segs]) for i in range(5)]  # 25 edges
        cells = usc._assign_generator_cells(pains, segs, target=8, max_gen=8)
        assert len(cells) == 8
        assert len({c["pain"].title for c in cells}) == 5  # >=1 per pain preserved under the cap

    def test_widening_adds_pains_to_reach_target(self, monkeypatch):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        crew.audience_mapping = SimpleNamespace(audience_segments=[_seg("Solo")])
        monkeypatch.setattr(usc.settings, "divergent_target_generators", 6)
        monkeypatch.setattr(usc.settings, "divergent_max_generators", 8)
        high = [_pain_seg("H", ["Solo"])]                              # 1 edge only
        extra = [_pain_seg(f"E{i}", ["Solo"]) for i in range(6)]
        cells = crew._build_partition_cells(high, extra)
        assert len(cells) >= 6  # widened from 1 cell toward the target

    def test_grounded_pains_for_uses_validated_titles(self):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        crew.pain_point_analysis = SimpleNamespace(pain_points=[
            SimpleNamespace(title="Pain A", affected_segments=["Solo"]),
            SimpleNamespace(title="Pain B", affected_segments=["Solo", "Other"]),
            SimpleNamespace(title="Pain C", affected_segments=["Other"]),
        ])
        out = crew._grounded_pains_for("Pain A", "Solo")
        assert out[0] == "Pain A"      # generating cell pain first
        assert "Pain B" in out         # other validated pain that shares the segment
        assert "Pain C" not in out     # different segment -> excluded

    def test_one_sample_stamps_provenance(self, monkeypatch):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens, **kw: "P", raising=False)
        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(
            lambda prompt, output_model, **kw: (SimpleNamespace(concepts=[_raw("A"), _raw("B")]), SimpleNamespace())))
        monkeypatch.setattr(usc, "raw_concept_quality_error", lambda c: None)
        monkeypatch.setattr(usc, "validate_raw_concept_list", lambda b, **k: (True, None))
        valid, _u = crew._one_sample({}, idx=0, lens="L", model="m", effort=None,
                                     partitioned_block="b", min_concepts=1, allow_zero=False, timeout=5,
                                     source_pain="Pain X", source_segment="Seg Y")
        assert valid and all(c.source_pain == "Pain X" and c.source_segment == "Seg Y" for c in valid)
