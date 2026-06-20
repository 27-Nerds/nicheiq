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
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens: "PROMPT", raising=False)

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
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens: "PROMPT", raising=False)

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
        monkeypatch.setattr(crew, "_render_divergent_prompt", lambda inputs, lens: "P", raising=False)

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
