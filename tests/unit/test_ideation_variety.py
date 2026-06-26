"""
Tests for the ideation variety & dedup contract (Phase 5 fixes).

Covers:
- build_crew_llm: reasoning models get a crewai.LLM with reasoning_effort
  (ChatOpenAI loses it in CrewAI's create_llm conversion — audit V1)
- detect_similarity: fuzzy signals 1/3 + single-strong-signal failure
- _tags_match: the M/D/J tag contract
- detect_catalog_duplicate: renamed structural duplicates are caught
- select_diverse_pain_points: severity + mentions + unrepresented-theme mix
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from nicheiq.utils.llm_service import build_crew_llm
from nicheiq.utils.pain_point_formatters import select_diverse_pain_points
from nicheiq.utils.validation.crew_guardrails import (
    _tags_match,
    detect_catalog_duplicate,
    detect_similarity,
)


class TestBuildCrewLlm:
    def test_reasoning_model_returns_crewai_llm_with_effort(self):
        # CrewAI's LLM() is a factory returning a provider-specific BaseLLM
        # subclass (e.g. OpenAICompletion); what matters is that the instance
        # is CrewAI-native (so create_llm() won't strip params) and carries
        # reasoning_effort through to the completion call.
        from crewai.llms.base_llm import BaseLLM

        llm = build_crew_llm("gpt-5.2", temperature=0.85, reasoning_effort="high")
        assert isinstance(llm, BaseLLM)
        assert llm.reasoning_effort == "high"

    def test_non_reasoning_model_returns_chatopenai_with_temperature(self):
        from langchain_openai import ChatOpenAI

        llm = build_crew_llm("gpt-4o", temperature=0.85)
        assert isinstance(llm, ChatOpenAI)
        assert llm.temperature == 0.85


def _idea(name="A", sources=None, vp="", personas=None):
    idea = MagicMock()
    idea.solution_name = name
    idea.data_sources = sources or []
    idea.value_proposition = vp
    idea.target_personas = personas or []
    return idea


class TestDetectSimilarityFuzzy:
    def test_reworded_sources_and_personas_still_match(self):
        """Exact set equality was defeated by rewording — fuzzy overlap is not."""
        a = _idea(
            "EvictionMap",
            sources=["county court eviction records"],
            vp="Aggregates eviction filings into neighborhood rental risk scores",
            personas=["renters researching neighborhoods"],
        )
        b = _idea(
            "RentalRiskAtlas",
            sources=["court eviction filing records"],  # reworded, same source
            vp="Aggregates eviction filings into neighborhood rental risk maps",
            personas=["renters researching a neighborhood"],  # reworded
        )
        assert detect_similarity(a, b) is True

    def test_single_strong_value_prop_overlap_fails_alone(self):
        a = _idea("ToolOne", vp="Tracks freelance project rates by skill and city benchmark")
        b = _idea("ToolTwo", vp="Tracks freelance project rates by skill and city benchmarks")
        # No source/persona signals at all — but the VP is near-identical
        assert detect_similarity(a, b) is True

    def test_genuinely_different_ideas_pass(self):
        a = _idea(
            "PermitFeed",
            sources=["municipal permit portals"],
            vp="Email digest of new building permits near a saved address",
            personas=["real estate developers"],
        )
        b = _idea(
            "RateCalc",
            sources=["self-reported freelancer rates"],
            vp="Calculator showing net earnings after platform fees",
            personas=["freelance designers"],
        )
        assert detect_similarity(a, b) is False


class TestTagsMatch:
    def test_canonical_vocabulary_matches(self):
        assert _tags_match("aggregates-public-records", "aggregates-public-records")

    def test_synonym_rewording_within_vocabulary_style(self):
        assert _tags_match("scheduled-automated-checks", "scheduled-automated-monitoring")

    def test_distinct_mechanisms_do_not_match(self):
        assert not _tags_match("parametric-calculator", "community-submitted-benchmarks")

    def test_none_never_matches(self):
        assert not _tags_match(None, "platform-api")


class TestDetectCatalogDuplicate:
    def _solution(self, name, vp="", personas=None, description=""):
        s = MagicMock()
        s.solution_name = name
        s.value_proposition = vp
        s.description = description
        s.target_personas = personas or []
        return s

    def test_renamed_structural_duplicate_caught(self):
        """The exact threat: same idea, new name — the old exact-name filter
        and the backend insert dedup both missed this."""
        new = self._solution(
            "RentalSafetyAtlas",
            vp="Aggregates county eviction court filings into neighborhood rental risk scores",
        )
        existing = {
            "name": "EvictionRiskMap",
            "description": "",
            "value_proposition": "Aggregates county eviction court filings into neighborhood rental risk score pages",
        }
        assert detect_catalog_duplicate(new, existing) is True

    def test_falls_back_to_description_text(self):
        new = self._solution(
            "PermitDigestPro",
            vp="Daily email digest of new building permits filed near saved addresses",
        )
        existing = {
            "name": "PermitTracker",
            "description": "Daily email digest of new building permit filings near saved addresses",
            # no value_proposition (legacy catalog row)
        }
        assert detect_catalog_duplicate(new, existing) is True

    def test_fuzzy_name_match_caught(self):
        new = self._solution("EvictionRiskMaps", vp="Completely different value proposition here")
        existing = {"name": "EvictionRiskMap", "description": ""}
        assert detect_catalog_duplicate(new, existing) is True

    def test_genuinely_new_idea_passes(self):
        new = self._solution(
            "FreelanceFeeCalc",
            vp="Calculator showing net freelancer earnings after platform fees and taxes",
            personas=["freelance developers"],
        )
        existing = {
            "name": "EvictionRiskMap",
            "description": "Neighborhood eviction risk scores",
            "value_proposition": "Aggregates eviction filings into rental risk scores",
            "target_personas": ["renters"],
        }
        assert detect_catalog_duplicate(new, existing) is False

    def _tagged(self, name, vp, m, d, j):
        return SimpleNamespace(
            solution_name=name, value_proposition=vp, description="",
            target_personas=[], mechanism_tag=m, data_source_tag=d, journey_tag=j,
        )

    def test_reworded_structural_duplicate_caught_via_mdj(self):
        """The 'generate more' threat: same mechanism+data+journey, totally reworded
        value prop (low text overlap) — text dedup misses it, M/D/J catches it."""
        new = self._tagged(
            "BPCLotMapper",
            "Turn COA trust from read-a-PDF-and-hope into an objective cross-vendor check",
            "llm-content-extraction", "scraped-web-pages", "search-lands-on-page",
        )
        existing = {
            "name": "COABatchChecker",
            "description": "Verify peptide COAs and spot reused batch IDs",
            "value_proposition": "Spot reused and tampered COA batch IDs across vendors",
            "mechanism_tag": "llm-content-extraction",
            "data_source_tag": "scraped-web-pages",
            "journey_tag": "search-lands-on-page",
        }
        assert detect_catalog_duplicate(new, existing) is True

    def test_one_shared_mdj_dim_not_duplicate(self):
        new = self._tagged("A", "alpha", "llm-content-extraction", "platform-api", "subscribes-gets-alerts")
        existing = {
            "name": "B", "description": "", "value_proposition": "wholly different idea",
            "mechanism_tag": "llm-content-extraction",  # only M matches
            "data_source_tag": "scraped-web-pages",
            "journey_tag": "search-lands-on-page",
        }
        assert detect_catalog_duplicate(new, existing) is False

    def test_mdj_skipped_when_existing_has_no_tags(self):
        """Backward compat: legacy catalog ideas without tags must not be affected."""
        new = self._tagged("A", "completely unique value prop here", "m1", "d1", "j1")
        existing = {"name": "B", "description": "", "value_proposition": "different idea entirely"}
        assert detect_catalog_duplicate(new, existing) is False


class TestRegenerationDirective:
    """The 'generate more' prompt should actively push NEW ANGLES, not just blacklist."""

    def _fn(self):
        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
        return UnifiedSolutionCrew._format_regeneration_directive

    def test_empty_on_first_generation(self):
        assert self._fn()(SimpleNamespace(existing_ideas=[])) == ""

    def test_angle_diversification_on_regeneration(self):
        out = self._fn()(SimpleNamespace(existing_ideas=[{"name": "A"}, {"name": "B"}]))
        assert "NEW ANGLES" in out and "ANGLE MAP" in out
        # mentions different dimensions to shift
        for dim in ("MECHANISM", "USER-JOURNEY", "PERSONA", "DATA SOURCE", "CONTRARIAN"):
            assert dim in out
        # safe for CrewAI single-pass .format() interpolation
        assert "{" not in out and "}" not in out


def _pain(title, severity, mentions, theme=None):
    pp = MagicMock()
    pp.title = title
    pp.severity_score = severity
    pp.mention_count = mentions
    pp.parent_theme_id = theme
    return pp


class TestSelectDiversePainPoints:
    def test_mixes_severity_mentions_and_themes(self):
        pains = (
            # 8 high-severity, low-mention pains in theme-a
            [_pain(f"sev{i}", 0.9 - i * 0.01, 5, "theme-a") for i in range(8)]
            # 3 lower-severity but heavily-discussed pains in theme-b
            + [_pain(f"hot{i}", 0.65, 40 + i, "theme-b") for i in range(3)]
            # 1 pain in an otherwise unrepresented theme
            + [_pain("longtail", 0.62, 3, "theme-c")]
        )
        selected = select_diverse_pain_points(pains)
        titles = {p.title for p in selected}
        # Top severity preserved
        assert "sev0" in titles
        # Evidence-grounded discussion volume earns slots
        assert any(t.startswith("hot") for t in titles)
        # Unrepresented theme reaches ideation as a full pain point
        assert "longtail" in titles
        assert len(selected) <= 12

    def test_pure_severity_when_no_diversity_exists(self):
        pains = [_pain(f"p{i}", 0.9 - i * 0.05, 10 - i, "theme-a") for i in range(5)]
        selected = select_diverse_pain_points(pains)
        assert [p.title for p in selected] == [f"p{i}" for i in range(5)]
