"""A rejected reasoning_effort is a naming mismatch, not a capability gap.

OpenAI's gpt-5.x generation calls the bottom rung `minimal`; gpt-5.6-luna calls it `none`
and 400s on `minimal`. Every Stage-7 probe passes `minimal`, so that one difference made a
perfectly capable model look unusable for the whole probe workload — and would have
silently disabled every parity/incumbent finding had the tier been repointed (verified
live 2026-08-03, scripts/probe_model_ab.py: 0/6 before this fix, 6/6 after).

The endpoint names what it accepts, so the retry reads the error instead of consulting a
per-model capability table that would go stale as models are renamed.
"""

import pytest

from nicheiq.utils.llm_service import nearest_supported_effort, parse_unsupported_effort

LUNA_400 = (
    "Error code: 400 - {'error': {'message': \"Unsupported value: 'minimal' is not "
    "supported with the 'gpt-5.6-luna' model. Supported values are: 'none', 'low', "
    "'medium', 'high', 'xhigh', and 'max'.\", 'type': 'invalid_request_error', "
    "'param': 'reasoning.effort', 'code': 'unsupported_value'}}"
)


class TestParseUnsupportedEffort:
    def test_parses_the_real_luna_400(self):
        rejected, supported = parse_unsupported_effort(Exception(LUNA_400))
        assert rejected == "minimal"
        assert supported == {"none", "low", "medium", "high", "xhigh", "max"}

    @pytest.mark.parametrize("message", [
        "429 rate limit exceeded",
        "Connection timed out",
        "context_length_exceeded: too many tokens",
    ])
    def test_ignores_unrelated_errors(self, message):
        """Must not hijack the retry path for failures a retry cannot fix."""
        assert parse_unsupported_effort(Exception(message)) is None

    def test_ignores_a_rejection_that_names_no_alternatives(self):
        """Without a supported list there is nothing to fall back TO — fail honestly."""
        assert parse_unsupported_effort(Exception("effort 'x' is not supported")) is None


class TestNearestSupportedEffort:
    def test_minimal_falls_to_none_not_low(self):
        """DOWN the ladder first: a caller asking for the floor must never be silently
        upgraded into paying for more reasoning than it asked for."""
        supported = {"none", "low", "medium", "high", "xhigh", "max"}
        assert nearest_supported_effort("minimal", supported) == "none"

    def test_none_falls_up_only_when_nothing_lower_exists(self):
        assert nearest_supported_effort("none", {"minimal", "low", "high"}) == "minimal"
        assert nearest_supported_effort("none", {"low", "high"}) == "low"

    def test_supported_value_is_returned_unchanged(self):
        assert nearest_supported_effort("medium", {"low", "medium", "high"}) == "medium"

    def test_unknown_effort_has_no_mapping(self):
        assert nearest_supported_effort("turbo", {"low", "high"}) is None

    def test_no_overlap_yields_none(self):
        assert nearest_supported_effort("minimal", {"banana"}) is None

    def test_every_ladder_rung_resolves_against_the_luna_set(self):
        """No tier in this repo may be left unmappable on a model we actually use."""
        _rejected, supported = parse_unsupported_effort(Exception(LUNA_400))
        for effort in ("none", "minimal", "low", "medium", "high", "xhigh", "max"):
            assert nearest_supported_effort(effort, supported) is not None, effort


class TestNoCallSiteUsesTheAmbiguousSpelling:
    """`minimal` and `none` mean the same thing, but only `none` is portable.

    On OpenRouter both resolve to the identical `{"reasoning": {"enabled": False}}`, so
    switching costs nothing there; on direct OpenAI, `minimal` is the gpt-5.x spelling that
    gpt-5.6-luna rejects outright. Standardising on `none` means the retry above stays a
    SAFETY NET rather than a routine round-trip on every probe call.
    """

    def test_no_call_site_passes_minimal(self):
        """AST, not grep: the docstrings that EXPLAIN this history legitimately contain the
        word, and a text match would flag them forever. Only a real keyword argument counts.
        """
        import ast
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3] / "src" / "nicheiq"
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:  # pragma: no cover - not our concern here
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if (
                        kw.arg == "reasoning_effort"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value == "minimal"
                    ):
                        offenders.append(f"{path.relative_to(root)}:{node.lineno}")
        assert offenders == [], (
            "use reasoning_effort='none' — 'minimal' 400s on gpt-5.6-luna and turns the "
            f"fallback retry into a routine extra round-trip: {offenders}"
        )

    def test_both_spellings_disable_reasoning_identically_on_openrouter(self):
        """The equivalence that makes the swap free."""
        from nicheiq.utils.llm_service import openrouter_reasoning_body

        grok = "openrouter/x-ai/grok-4.3"
        assert openrouter_reasoning_body("minimal", grok) == openrouter_reasoning_body("none", grok)
        assert openrouter_reasoning_body("none", grok) == {"reasoning": {"enabled": False}}
