"""`_probe_incumbents` seeds its 3 discovery queries from the USER'S INPUT, not the
Stage-1-derived description.

WHY THIS FILE EXISTS
--------------------
`_incumbent_rows[:2]` anchors every name-anchored `incumbent_parity` query
(`f'"{incumbent}" {kw}'`), so the incumbent map these 3 queries build decides which vendors
can ever be searched, which decides which ideas get market_fit-capped. Seeding those
queries on the ~400-char Stage-1 `niche_description` paragraph truncated them mid-prose at
`[:120]` ("best software tools for The dental revenue cycle management market encompasses
the softw"), which is what built a medical-RCM map for a dental claim-denial run.

The substitution is unconditional and was chosen by measurement, not taste: a pre-registered
42-subject / 21-family / 6-rep campaign (probes/incumbent_arms_v2.py) scored the pitch arm
the winner on 20 of 25 decidable subjects vs 5 for production, p=0.00204, Holm 0.0347. Every
conditional gate tested scored at or below chance (best 6/25, p=0.998) and the merge arm was
measured and rejected. See `UnifiedSolutionCrew._incumbent_probe_seed` for the full record.

Nothing here pins a literal query STRING — the 3 templates may legitimately change. The
assertions are on the property: what the queries are SEEDED FROM.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews import unified_solution_crew as uc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew, _pitch_head

ROOT = Path(__file__).resolve().parents[3]
CKPT = ROOT / "output" / "checkpoints"
PROBE_SRC = ROOT / "probes" / "incumbent_source_ab.py"

# Run 4bc9c406 — dental insurance claim denial triage for small private practices. The
# concrete case the campaign was motivated by: production anchored 4 names (Eaglesoft x3
# reps, Open Dental, Curve, Dentrix); the pitch arm anchored 13 including Vyne Trellis,
# DentalXChange and eAssist, and the user's idea had been capped at market_fit 0.40 citing
# an Eaglesoft manual page.
DENTAL_RUN = "4bc9c406"


def _stage1_records() -> list[dict]:
    """Every distinct (niche_input, niche_description) pair persisted under
    output/checkpoints.

    Real Stage-1 artifacts, never a hand-written seed: a hand-written pitch would not
    exercise the multi-line / long-first-line shapes the head extraction exists for, and a
    hand-written seed value is by definition one production never produced.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for path in sorted(CKPT.glob("*/stage_1_niche_context.json")):
        try:
            raw = json.loads(path.read_text())
        except Exception:
            continue
        ni = (raw.get("niche_input") or "").strip()
        nd = (raw.get("niche_description") or "").strip()
        if not ni or not nd:
            continue
        key = (ni, nd)
        if key in seen:
            continue
        seen.add(key)
        out.append({"dir": path.parent.name, "niche_input": ni, "niche_description": nd})
    return out


STAGE1 = _stage1_records()


def _dental() -> dict:
    for rec in STAGE1:
        if DENTAL_RUN in rec["dir"]:
            return rec
    pytest.skip(f"no checkpoint for run {DENTAL_RUN} on disk")


def _crew(**extra):
    """Bare crew — mirrors tests/unit/crews/test_search_arm_attribution._crew. The probe's
    helpers are getattr-defensive precisely so they work without __init__."""
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.checkpoint_mgr = None
    crew.audience_mapping = None
    crew.competitor_mentions_text = ""
    crew._ma_search = lambda q: None
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _issued_queries(rec: dict) -> list[str]:
    """The 3 discovery queries `_probe_incumbents` actually issues, read back off the
    search-arm ledger rather than reconstructed from the templates."""
    crew = _crew(
        search_tool=SimpleNamespace(run=lambda search_query: "Acme is a tool"),
        niche_context=SimpleNamespace(
            niche_input=rec["niche_input"], niche_description=rec["niche_description"]),
    )
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(SimpleNamespace(incumbents=[]), None)):
        crew._probe_incumbents()
    return [r["query"] for r in crew.search_arm_log if r["arm"] == "incumbent_probe"]


@pytest.fixture
def seed_from_input():
    """The PITCH-HEAD layer: seed from the user's input, generator OFF.

    Both flags are pinned so an env override can't mask a regression, and both are
    restored. The generator layer is pinned OFF here on purpose — everything in the
    classes that use this fixture is about the seed the run falls back to, which is
    also what these tests must keep byte-identical. The generator has its own fixture
    (`generated_seed`) and its own classes below; it is never left on with a real
    `niche_input` and an unpatched `LLMService`, which would issue live calls.
    """
    prev = settings.incumbent_probe_seed_from_niche_input
    prev_gen = settings.incumbent_probe_seed_generated_description
    settings.incumbent_probe_seed_from_niche_input = True
    settings.incumbent_probe_seed_generated_description = False
    yield
    settings.incumbent_probe_seed_from_niche_input = prev
    settings.incumbent_probe_seed_generated_description = prev_gen


@pytest.fixture
def generated_seed():
    """The GENERATED layer (arm E2): both flags on."""
    prev = settings.incumbent_probe_seed_from_niche_input
    prev_gen = settings.incumbent_probe_seed_generated_description
    settings.incumbent_probe_seed_from_niche_input = True
    settings.incumbent_probe_seed_generated_description = True
    yield
    settings.incumbent_probe_seed_from_niche_input = prev
    settings.incumbent_probe_seed_generated_description = prev_gen


# ---------------------------------------------------------------------------
# The port. If `_pitch_head` drifts from the measured arm, everything below is measuring
# something the campaign never ran.
# ---------------------------------------------------------------------------

class TestHeadExtractionIsTheMeasuredOne:
    def test_default_is_on(self):
        """Owner's decision: unconditional replace. The flag is a rollback switch."""
        field = type(settings).model_fields["incumbent_probe_seed_from_niche_input"]
        assert field.default is True

    @pytest.mark.skipif(not PROBE_SRC.exists(), reason="probe source not present")
    def test_pitch_head_body_is_verbatim_from_the_measured_arm(self):
        """Byte-for-byte against `probes/incumbent_source_ab.pitch_head`, the arm-B2 subject
        string `probes/incumbent_arms_v2.py` reuses verbatim. A variant is an UNMEASURED
        variant — the raw pitch was measured separately and is weaker (an 877-char pitch
        produced 20% fabricated rows)."""
        src = PROBE_SRC.read_text()
        m = re.search(r"^def pitch_head\(niche_input: str\) -> str:\n(.*?)(?=\n\n\ndef )",
                      src, re.S | re.M)
        assert m, "pitch_head not found in the probe — cannot verify the port"
        probe_body = [ln for ln in m.group(1).splitlines()
                      if ln.strip() and not ln.lstrip().startswith(('"""', "than 110", "line."))]
        ours = inspect.getsource(_pitch_head)
        ours_body = ours.split('"""', 2)[2].splitlines()
        ours_body = [ln for ln in ours_body if ln.strip()]
        assert ours_body == probe_body


# ---------------------------------------------------------------------------
# The property, over every real Stage-1 artifact on disk.
# ---------------------------------------------------------------------------

class TestSeededFromUserInput:
    def test_the_corpus_is_not_empty(self):
        """A silently empty corpus would make every parametrized case below vacuous."""
        assert len(STAGE1) >= 100, f"only {len(STAGE1)} stage-1 records found under {CKPT}"

    @pytest.mark.parametrize("rec", STAGE1, ids=lambda r: r["dir"][:40])
    def test_seed_is_the_head_of_the_users_input(self, rec, seed_from_input):
        crew = _crew(niche_context=SimpleNamespace(
            niche_input=rec["niche_input"], niche_description=rec["niche_description"]))
        assert crew._incumbent_probe_seed() == _pitch_head(rec["niche_input"])

    @pytest.mark.parametrize("rec", STAGE1, ids=lambda r: r["dir"][:40])
    def test_every_issued_query_carries_the_users_words_and_not_the_description(
            self, rec, seed_from_input):
        """Property, not a pinned string: whatever the 3 templates are, they must be built
        on the user's input. `niche_input` is present and differs from `niche_description`
        on all 306 Stage-1 checkpoints, so this holds for 100% of real runs."""
        seed = _pitch_head(rec["niche_input"])
        queries = _issued_queries(rec)
        assert len(queries) == 3
        # Templates truncate at [:120] exactly as the winning arm was measured with, so a
        # long head can be cut — require the surviving prefix, not the whole seed.
        for q in queries:
            assert seed[:60] in q, f"{q!r} is not seeded from the user's input"
        if rec["niche_description"].startswith(seed):
            # A handful of on-disk descriptions are echo-prefixed with the input verbatim
            # ("AI & Machine Learning > AI Agent Builders: ..."), so the two arms coincide
            # on their first words and there is nothing to distinguish. The head bound
            # (tested separately) is what still protects these.
            return
        for q in queries:
            assert rec["niche_description"][:60] not in q

    @pytest.mark.parametrize("rec", STAGE1, ids=lambda r: r["dir"][:40])
    def test_head_is_bounded_so_the_templates_do_not_truncate_mid_paragraph(self, rec):
        """The whole defect was prose overflowing `[:120]`. The head is <=110 chars by
        construction; the description is not."""
        assert len(_pitch_head(rec["niche_input"])) <= 110


class TestDentalRegression:
    def test_the_live_medical_rcm_query_is_no_longer_producible(self, seed_from_input):
        rec = _dental()
        queries = _issued_queries(rec)
        assert all("market encompasses" not in q for q in queries), queries
        assert all("revenue cycle management market" not in q for q in queries), queries
        for q in queries:
            assert "Dental insurance claim denial triage" in q

    def test_production_seed_did_produce_it(self):
        """Anchors the regression to the real defect rather than to a phrasing quirk: with
        the flag off, the Stage-1 paragraph comes back and the templates truncate it
        mid-prose at the 120-char cap."""
        rec = _dental()
        prev = settings.incumbent_probe_seed_from_niche_input
        settings.incumbent_probe_seed_from_niche_input = False
        try:
            queries = _issued_queries(rec)
        finally:
            settings.incumbent_probe_seed_from_niche_input = prev
        assert all(len(q) == 120 for q in queries), [len(q) for q in queries]
        assert all("market encompasses" in q for q in queries), queries
        assert not any("claim denial" in q for q in queries), queries


# ---------------------------------------------------------------------------
# Three states.
# ---------------------------------------------------------------------------

class TestThreeStates:
    def test_input_present_seeds_the_head_of_the_input(self, seed_from_input):
        rec = _dental()
        crew = _crew(niche_context=SimpleNamespace(
            niche_input=rec["niche_input"], niche_description=rec["niche_description"]))
        assert crew._incumbent_probe_seed() == _pitch_head(rec["niche_input"])
        assert crew._incumbent_probe_seed() != rec["niche_description"]

    @pytest.mark.parametrize("empty", ["", "   ", "\n\n"])
    def test_input_empty_falls_back_to_the_description(self, empty, seed_from_input):
        """Unreachable via Stage 1 (`niche_input` is required and non-empty on all 306
        checkpoints); reachable via legacy or hand-built contexts, which must keep the
        pre-change behaviour byte-for-byte."""
        rec = _dental()
        crew = _crew(niche_context=SimpleNamespace(
            niche_input=empty, niche_description=rec["niche_description"]))
        assert crew._incumbent_probe_seed() == rec["niche_description"]

    def test_input_attribute_absent_falls_back_to_the_description(self, seed_from_input):
        rec = _dental()
        crew = _crew(niche_context=SimpleNamespace(
            niche_description=rec["niche_description"]))
        assert crew._incumbent_probe_seed() == rec["niche_description"]

    def test_no_niche_context_seeds_nothing_and_the_probe_fail_softs(self, seed_from_input):
        crew = _crew(
            niche_context=None,
            search_tool=SimpleNamespace(run=lambda search_query: "Acme is a tool"),
        )
        assert crew._incumbent_probe_seed() == ""
        assert crew._probe_incumbents() == ""
        assert not [r for r in getattr(crew, "search_arm_log", [])
                    if r["arm"] == "incumbent_probe"]


# ---------------------------------------------------------------------------
# The flag, in both directions.
# ---------------------------------------------------------------------------

class TestFlagFlipsBehaviourBothWays:
    def _seed(self, rec, flag, generated=False):
        prev = settings.incumbent_probe_seed_from_niche_input
        prev_gen = settings.incumbent_probe_seed_generated_description
        settings.incumbent_probe_seed_from_niche_input = flag
        settings.incumbent_probe_seed_generated_description = generated
        try:
            crew = _crew(niche_context=SimpleNamespace(
                niche_input=rec["niche_input"], niche_description=rec["niche_description"]))
            return crew._incumbent_probe_seed()
        finally:
            settings.incumbent_probe_seed_from_niche_input = prev
            settings.incumbent_probe_seed_generated_description = prev_gen

    @pytest.mark.parametrize("rec", STAGE1[:40], ids=lambda r: r["dir"][:40])
    def test_off_is_the_pre_change_description_and_on_is_the_input_head(self, rec):
        assert self._seed(rec, False) == rec["niche_description"]
        assert self._seed(rec, True) == _pitch_head(rec["niche_input"])
        assert self._seed(rec, False) != self._seed(rec, True)

    def test_flipping_back_and_forth_is_stable(self):
        rec = _dental()
        for flag in (True, False, True, False, True):
            expected = (_pitch_head(rec["niche_input"]) if flag
                        else rec["niche_description"])
            assert self._seed(rec, flag) == expected

    def test_off_reproduces_the_exact_expression_the_change_replaced(self):
        """The pre-change seed was
        `getattr(getattr(self, "niche_context", None), "niche_description", "") or ""` —
        unstripped. Rollback must be byte-identical, including for a whitespace-only
        description, so the flag is a true revert and not a second change."""
        for desc in ["  ", "\n", "", "wedding photography", "  padded  "]:
            crew = _crew(niche_context=SimpleNamespace(niche_input="pitch", niche_description=desc))
            prev = settings.incumbent_probe_seed_from_niche_input
            settings.incumbent_probe_seed_from_niche_input = False
            try:
                assert crew._incumbent_probe_seed() == (
                    getattr(getattr(crew, "niche_context", None), "niche_description", "") or "")
            finally:
                settings.incumbent_probe_seed_from_niche_input = prev


# ---------------------------------------------------------------------------
# ARM E2 — the SEPARATE-CALL generated short niche description (2026-08-18).
#
# THIS LAYER SHIPPED WITHOUT A WIN. E2 took 7 of 10 decidable subjects vs the pitch head
# (p=0.172, Holm 0.344, macro-mean M1 0.316 vs 0.270) on the 19 truncated-seed subjects —
# UNPROVEN — while the seed it displaces carries p=0.00204 / Holm 0.0347. What WAS
# significant is the isolation: asking a SEPARATE prompt rather than Stage 1 dropped the
# blinded judge's MARKET-register rate from 52.6% to 15.8% (paired exact McNemar, b=6/c=0,
# p=0.016); the ANCHOR RULE added nothing measurable on top of it (E1 vs E2 p=0.25). E2 was
# also the least replication-stable arm (name-set Jaccard 0.484 vs 0.523).
#
# So these tests pin two different things, for two different reasons:
#   * the PORT, byte-for-byte against probes/incumbent_arm_e.py — because an unmeasured
#     variant would leave a future round nothing to re-measure against;
#   * the FALLBACK, byte-for-byte against the pitch-head seed — because the rollback has to
#     be a true revert to the arm that actually won, not a second change.
# ---------------------------------------------------------------------------

PROBE_E = ROOT / "probes" / "incumbent_arm_e.py"


def _probe_e_literals() -> dict:
    """Module-level literals of `probes/incumbent_arm_e.py`, read with `ast` (never imported
    — importing the probe pulls in the campaign harness and would need API keys)."""
    import ast

    tree = ast.parse(PROBE_E.read_text())
    out: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                continue
        if isinstance(node, ast.ClassDef) and node.name == "_NicheSeed":
            fields = [(n.target.id, ast.unparse(n.value))
                      for n in node.body if isinstance(n, ast.AnnAssign)]
            out["_NicheSeed_fields"] = fields
    return out


def _probe_e_prompt(niche_input: str) -> str:
    """`probes/incumbent_arm_e.build_e_prompt(subject, "E2")`, rebuilt from the probe's own
    literals — the exact string the measured arm sent."""
    lit = _probe_e_literals()
    return lit["E_BASE_PROMPT"].format(
        niche_input=niche_input, max_chars=lit["MAX_SEED_CHARS"]) + lit["E2_ANCHOR"]


class _SeedLLM:
    """A stand-in for `LLMService.invoke_structured` that answers BOTH calls the probe makes:
    the seed generation (`_NicheSeed`) and the incumbent extraction (`_Incumbents`). Records
    every call so the test can assert on the kwargs the generator was measured with."""

    def __init__(self, seed="a generated niche description", raises=False):
        self.seed = seed
        self.raises = raises
        self.calls: list[dict] = []

    def __call__(self, **kw):
        self.calls.append(kw)
        model = kw.get("output_model")
        if model is uc._NicheSeed:
            if self.raises:
                raise RuntimeError("generator timed out")
            return SimpleNamespace(niche_description=self.seed), None
        return SimpleNamespace(incumbents=[]), None

    @property
    def seed_calls(self):
        return [c for c in self.calls if c.get("output_model") is uc._NicheSeed]


def _seeded_crew(rec, **extra):
    return _crew(niche_context=SimpleNamespace(
        niche_input=rec["niche_input"], niche_description=rec["niche_description"]), **extra)


def _seed_with(rec, llm, **extra):
    crew = _seeded_crew(rec, **extra)
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               side_effect=llm):
        return crew._incumbent_probe_seed(), crew


class TestTheGeneratorIsTheMeasuredArmE2:
    @pytest.mark.skipif(not PROBE_E.exists(), reason="arm E probe source not present")
    def test_prompt_and_anchor_are_byte_identical_to_the_probe(self):
        """`E_BASE_PROMPT` / `E2_ANCHOR`, verbatim. Reworded instructions are a different
        arm, and this arm was UNPROVEN at n=10 — a reworded one is unmeasured entirely."""
        lit = _probe_e_literals()
        assert uc._INCUMBENT_SEED_PROMPT == lit["E_BASE_PROMPT"]
        assert uc._INCUMBENT_SEED_ANCHOR == lit["E2_ANCHOR"]

    @pytest.mark.skipif(not PROBE_E.exists(), reason="arm E probe source not present")
    def test_length_budget_and_temperature_are_the_probes(self):
        lit = _probe_e_literals()
        assert uc._INCUMBENT_SEED_MAX_CHARS == lit["MAX_SEED_CHARS"] == 110
        assert uc._INCUMBENT_SEED_TEMPERATURE == lit["GEN_TEMPERATURE"] == 0.0

    @pytest.mark.skipif(not PROBE_E.exists(), reason="arm E probe source not present")
    def test_output_schema_matches_the_probes(self):
        """One field, named `niche_description`, with the probe's own description text —
        the field name and its description are part of the prompt the model actually saw."""
        lit = _probe_e_literals()
        assert [n for n, _ in lit["_NicheSeed_fields"]] == ["niche_description"]
        assert list(uc._NicheSeed.model_fields) == ["niche_description"]
        assert (uc._NicheSeed.model_fields["niche_description"].description
                == f"short niche description, at most {lit['MAX_SEED_CHARS']} characters")

    @pytest.mark.skipif(not PROBE_E.exists(), reason="arm E probe source not present")
    def test_the_call_reproduces_gen_one_exactly(self, generated_seed):
        """`gen_one`: prompt=build_e_prompt(subject, 'E2'), output_model=_NicheSeed,
        temperature=0, timeout=120, model_name=settings.niche_context_llm — and NO
        reasoning_effort (the probe passes none, and `minimal` is rejected outright by some
        configured models)."""
        rec = _dental()
        llm = _SeedLLM()
        seed, _ = _seed_with(rec, llm)
        assert seed == "a generated niche description"
        call, = llm.seed_calls
        assert call["prompt"] == _probe_e_prompt(rec["niche_input"])
        assert call["output_model"] is uc._NicheSeed
        assert call["temperature"] == 0.0
        assert call["timeout"] == 120
        assert call["model_name"] == settings.niche_context_llm
        assert "reasoning_effort" not in call

    def test_the_full_user_input_is_sent_not_the_head(self, generated_seed):
        """The probe fed the generator the WHOLE (stripped) `niche_input`; truncating it
        first would be a different arm. Checked on a subject the head demonstrably cuts."""
        rec = next((r for r in STAGE1 if len(r["niche_input"]) > 200), None)
        if rec is None:
            pytest.skip("no long-input Stage-1 record on disk")
        llm = _SeedLLM()
        _seed_with(rec, llm)
        assert rec["niche_input"] in llm.seed_calls[0]["prompt"]
        assert _pitch_head(rec["niche_input"]) != rec["niche_input"]


class TestGeneratorIsNotInsideStage1:
    """The ONLY thing this arm measured as significant is that the ask lives in its OWN
    prompt: inside Stage 1 the blinded judge called 52.6% of seeds MARKET-register, in a
    separate call 15.8% (p=0.016). A later refactor that folded the ask into
    `_generate_niche_context` would silently undo exactly that, and nothing else here would
    notice."""

    def test_stage_1_does_not_carry_the_seed_prompt(self):
        from nicheiq.flows.research_flow import ResearchFlow

        stage1 = inspect.getsource(ResearchFlow._generate_niche_context)
        assert "_INCUMBENT_SEED_PROMPT" not in stage1
        assert "ANCHOR RULE" not in stage1
        assert "_NicheSeed" not in stage1

    def test_the_seed_prompt_does_not_carry_stage_1(self, generated_seed):
        """...and the reverse direction: the generator's prompt is not Stage 1's prompt with
        an extra sentence. Stage 1's own instructions — 'STEP 2 — Name the BROAD market',
        HARD RULE 3 — are what pushed arm D into the market register."""
        rec = _dental()
        llm = _SeedLLM()
        _seed_with(rec, llm)
        prompt = llm.seed_calls[0]["prompt"]
        for marker in ("HARD RULES", "audience_scope", "market_segments",
                       "BROAD market", "industry_boundaries"):
            assert marker not in prompt

    def test_it_is_its_own_call(self, generated_seed):
        """A separate `invoke_structured`, made at probe time from the crew — not a field
        read off the Stage-1 context object."""
        rec = _dental()
        llm = _SeedLLM()
        seed, crew = _seed_with(rec, llm)
        assert len(llm.seed_calls) == 1
        assert seed != rec["niche_description"]
        assert seed != _pitch_head(rec["niche_input"])


class TestSeedSourceProperty:
    """The property, not a literal seed string: generated when the call succeeds, pitch head
    when it does not."""

    @pytest.mark.parametrize("rec", STAGE1[:40], ids=lambda r: r["dir"][:40])
    def test_generated_when_the_call_succeeds(self, rec, generated_seed):
        seed, crew = _seed_with(rec, _SeedLLM(seed="tools for tiny widget shops"))
        assert seed == "tools for tiny widget shops"
        assert crew._incumbent_seed_source == "generated"

    @pytest.mark.parametrize("rec", STAGE1[:40], ids=lambda r: r["dir"][:40])
    def test_pitch_head_when_the_call_raises(self, rec, generated_seed):
        seed, crew = _seed_with(rec, _SeedLLM(raises=True))
        assert seed == _pitch_head(rec["niche_input"])
        assert crew._incumbent_seed_source == "pitch_head"

    @pytest.mark.parametrize("empty", ["", "   ", "\n\t "])
    def test_pitch_head_when_the_call_returns_empty_or_whitespace(self, empty, generated_seed):
        rec = _dental()
        seed, crew = _seed_with(rec, _SeedLLM(seed=empty))
        assert seed == _pitch_head(rec["niche_input"])
        assert crew._incumbent_seed_source == "pitch_head"

    def test_the_generated_seed_is_stripped(self, generated_seed):
        rec = _dental()
        seed, _ = _seed_with(rec, _SeedLLM(seed="  padded description  "))
        assert seed == "padded description"

    def test_a_missing_field_is_a_failure_not_a_crash(self, generated_seed):
        """A model that returns an object without the field must fall back, not raise."""
        rec = _dental()
        crew = _seeded_crew(rec)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(), None)):
            assert crew._incumbent_probe_seed() == _pitch_head(rec["niche_input"])

    def test_no_niche_input_never_calls_the_generator(self, generated_seed):
        """Nothing to describe — and the run must not be charged for a call whose only
        input is empty."""
        rec = _dental()
        llm = _SeedLLM()
        crew = _crew(niche_context=SimpleNamespace(
            niche_input="   ", niche_description=rec["niche_description"]))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            assert crew._incumbent_probe_seed() == rec["niche_description"]
        assert llm.seed_calls == []
        assert crew._incumbent_seed_source == "description"

    def test_no_niche_context_never_calls_the_generator(self, generated_seed):
        llm = _SeedLLM()
        crew = _crew(niche_context=None)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            assert crew._incumbent_probe_seed() == ""
        assert llm.seed_calls == []


class TestOneCallPerRunAndFailSoft:
    def test_at_most_one_generation_per_run(self, generated_seed):
        """`_probe_incumbents` is cached, but the seed is also readable on its own. One LLM
        call per run is the whole cost story — a repeat read must not become a second."""
        rec = _dental()
        llm = _SeedLLM()
        crew = _seeded_crew(rec)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            seeds = [crew._incumbent_probe_seed() for _ in range(4)]
        assert len(set(seeds)) == 1
        assert len(llm.seed_calls) == 1

    def test_a_failure_is_not_retried_into_a_second_charge(self, generated_seed):
        rec = _dental()
        llm = _SeedLLM(raises=True)
        crew = _seeded_crew(rec)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            for _ in range(3):
                assert crew._incumbent_probe_seed() == _pitch_head(rec["niche_input"])
        assert len(llm.seed_calls) == 1

    def test_the_probe_still_runs_when_the_generator_dies(self, generated_seed):
        """The regression this fail-soft exists to prevent: the seed used to be a pure
        string operation that could not fail, so a raising generator must degrade to it —
        never abort `_probe_incumbents`."""
        rec = _dental()
        llm = _SeedLLM(raises=True)
        crew = _seeded_crew(
            rec, search_tool=SimpleNamespace(run=lambda search_query: "Acme is a tool"))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            crew._probe_incumbents()
        queries = [r["query"] for r in crew.search_arm_log if r["arm"] == "incumbent_probe"]
        assert len(queries) == 3
        assert all(_pitch_head(rec["niche_input"])[:60] in q for q in queries)

    def test_the_generated_seed_reaches_the_three_templates_unchanged(self, generated_seed):
        """The templates and their `[:120]` truncation are what EVERY arm was measured with;
        the seed is the only thing that moves."""
        rec = _dental()
        llm = _SeedLLM(seed="dental claim denial triage for small practices")
        crew = _seeded_crew(
            rec, search_tool=SimpleNamespace(run=lambda search_query: "Acme is a tool"))
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            crew._probe_incumbents()
        queries = [r["query"] for r in crew.search_arm_log if r["arm"] == "incumbent_probe"]
        assert queries == [
            "best software tools for dental claim denial triage for small practices",
            "dental claim denial triage for small practices app pricing per month",
            "best apps and tools for dental claim denial triage for small practices",
        ]


class TestSeedSourceIsVisibleInTheLedger:
    """A silent fallback is an invisible fallback. `stage_5_search_arm_debug.json` has to
    show which seed a run actually used, or a later round cannot tell an E2 run from a
    pitch-head run after the fact."""

    def _probe(self, rec, llm, **extra):
        crew = _seeded_crew(
            rec, search_tool=SimpleNamespace(run=lambda search_query: "Acme is a tool"),
            **extra)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=llm):
            crew._probe_incumbents()
        return crew

    def test_a_generated_seed_is_recorded_with_its_source(self, generated_seed):
        rec = _dental()
        crew = self._probe(rec, _SeedLLM(seed="dental denial triage"))
        row, = [r for r in crew.search_arm_log if r["arm"].startswith("incumbent_probe_seed")]
        assert row["arm"] == "incumbent_probe_seed:generated"
        assert row["query"] == "dental denial triage"
        assert row["counted"] is False

    def test_a_fallback_is_recorded_as_a_fallback(self, generated_seed):
        rec = _dental()
        crew = self._probe(rec, _SeedLLM(raises=True))
        row, = [r for r in crew.search_arm_log if r["arm"].startswith("incumbent_probe_seed")]
        assert row["arm"] == "incumbent_probe_seed:pitch_head"
        assert row["query"] == _pitch_head(rec["niche_input"])

    def test_the_pre_change_description_seed_is_recorded_too(self):
        rec = _dental()
        prev = settings.incumbent_probe_seed_from_niche_input
        settings.incumbent_probe_seed_from_niche_input = False
        try:
            crew = self._probe(rec, _SeedLLM())
        finally:
            settings.incumbent_probe_seed_from_niche_input = prev
        row, = [r for r in crew.search_arm_log if r["arm"].startswith("incumbent_probe_seed")]
        assert row["arm"] == "incumbent_probe_seed:description"

    def test_it_never_enters_the_gating_counter_or_the_query_counts(self, generated_seed):
        """A prior round proved arithmetically that charging an uncounted arm to
        `_ma_serper_calls` starves the downstream `_ma_search_batch` arms and changes which
        caps apply. The seed row is not a query at all, so it is `counted=False` AND carries
        a distinct arm name — `incumbent_probe` still counts exactly its 3 queries."""
        rec = _dental()
        crew = self._probe(rec, _SeedLLM(seed="dental denial triage"), _ma_serper_calls=7)
        assert crew.search_arm_spend["incumbent_probe"] == 3
        assert crew.search_arm_spend["incumbent_probe_seed:generated"] == 1
        assert crew._ma_serper_calls == 7
        payload = crew.search_debug_payload()
        assert payload["gated_spend"] == 0
        assert payload["gated_spend"] <= payload["ma_serper_calls"]

    def test_no_seed_row_when_the_probe_never_runs(self, generated_seed):
        crew = _crew(niche_context=None,
                     search_tool=SimpleNamespace(run=lambda search_query: "Acme"))
        assert crew._probe_incumbents() == ""
        assert not [r for r in (getattr(crew, "search_arm_log", None) or [])
                    if r["arm"].startswith("incumbent_probe")]


class TestBothFlagsFlipBothWays:
    """Two flags, nested: the generator's prompt is built FROM `niche_input`, so switching
    off "seed from the user's input" has to switch it off too — otherwise the documented
    rollback would still be seeding from the input, one indirection later."""

    def _seed(self, rec, from_input, generated, llm=None):
        prev = settings.incumbent_probe_seed_from_niche_input
        prev_gen = settings.incumbent_probe_seed_generated_description
        settings.incumbent_probe_seed_from_niche_input = from_input
        settings.incumbent_probe_seed_generated_description = generated
        llm = llm or _SeedLLM(seed="GEN")
        try:
            crew = _seeded_crew(rec)
            with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                       side_effect=llm):
                return crew._incumbent_probe_seed(), llm
        finally:
            settings.incumbent_probe_seed_from_niche_input = prev
            settings.incumbent_probe_seed_generated_description = prev_gen

    def test_new_flag_defaults_on(self):
        """Owner's decision: use it. It is a rollback switch, not a gate — and it is a
        switch precisely because the arm is UNPROVEN (7/10, p=0.172)."""
        field = type(settings).model_fields["incumbent_probe_seed_generated_description"]
        assert field.default is True

    @pytest.mark.parametrize("rec", STAGE1[:20], ids=lambda r: r["dir"][:40])
    def test_the_four_reachable_states(self, rec):
        assert self._seed(rec, True, True)[0] == "GEN"
        assert self._seed(rec, True, False)[0] == _pitch_head(rec["niche_input"])
        assert self._seed(rec, False, True)[0] == rec["niche_description"]
        assert self._seed(rec, False, False)[0] == rec["niche_description"]

    def test_off_reproduces_todays_shipped_seed_byte_for_byte(self):
        """The rollback must be a true revert, not a second change: with the generator off,
        the seed is the pitch head the 42-subject campaign measured — the same string, for
        every real Stage-1 artifact on disk."""
        for rec in STAGE1:
            assert self._seed(rec, True, False)[0] == _pitch_head(rec["niche_input"])

    def test_the_niche_input_flag_switches_the_generator_off_too(self):
        """`incumbent_probe_seed_from_niche_input=False` is documented as the full revert to
        the pre-2026-08 `niche_description` seed. A generator call built from `niche_input`
        must not survive it — and must not be paid for either."""
        rec = _dental()
        seed, llm = self._seed(rec, False, True)
        assert seed == rec["niche_description"]
        assert llm.seed_calls == []

    def test_flipping_back_and_forth_is_stable(self):
        rec = _dental()
        for from_input, generated, expected in [
            (True, True, "GEN"),
            (True, False, _pitch_head(rec["niche_input"])),
            (True, True, "GEN"),
            (False, True, rec["niche_description"]),
            (True, True, "GEN"),
            (False, False, rec["niche_description"]),
        ]:
            assert self._seed(rec, from_input, generated)[0] == expected
