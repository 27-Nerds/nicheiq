"""
Tests for the ideation variety & dedup contract (Phase 5 fixes).

Covers:
- build_crew_llm: reasoning models get a crewai.LLM with reasoning_effort
  (ChatOpenAI loses it in CrewAI's create_llm conversion — audit V1)
- detect_similarity: fuzzy signals 1/3 + single-strong-signal failure
- _tags_match + validate_filtered_concepts: the M/D/J tag contract
- detect_catalog_duplicate: renamed structural duplicates are caught
- select_diverse_pain_points: severity + mentions + unrepresented-theme mix
"""

import json
from unittest.mock import MagicMock

from nicheiq.utils.llm_service import build_crew_llm
from nicheiq.utils.pain_point_formatters import select_diverse_pain_points
from nicheiq.utils.validation.crew_guardrails import (
    _tags_match,
    detect_catalog_duplicate,
    detect_similarity,
    validate_filtered_concepts,
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


def _filtered_concepts_output(concepts):
    output = MagicMock()
    output.pydantic = None
    output.raw = json.dumps({
        "concepts": concepts,
        "removed_concepts": [],
        "removal_reasons": [],
        "diversity_summary": "Three structurally distinct concepts across different data sources and journeys.",
    })
    return output


def _concept(name, mech, data, journey):
    return {
        "concept_name": name,
        "one_liner": f"{name} does something interesting with a unique angle on the problem.",
        "ideation_technique": "niche_drilling",
        "project_type": "aggregator",
        "target_keywords": ["keyword one", "keyword two"],
        "mechanism_tag": mech,
        "data_source_tag": data,
        "journey_tag": journey,
    }


class TestFilteredConceptsTagContract:
    def test_valid_diverse_tags_pass(self):
        output = _filtered_concepts_output([
            _concept("A", "aggregates-public-records", "government-open-data", "search-lands-on-page"),
            _concept("B", "parametric-calculator", "scraped-web-pages", "enters-inputs-gets-calculation"),
            _concept("C", "community-submitted-benchmarks", "self-reported-user-data", "submits-data-creates-value"),
        ])
        ok, _ = validate_filtered_concepts(output)
        assert ok

    def test_missing_tags_fail(self):
        concepts = [
            _concept("A", "aggregates-public-records", "government-open-data", "search-lands-on-page"),
            _concept("B", "parametric-calculator", "scraped-web-pages", "enters-inputs-gets-calculation"),
            _concept("C", "community-submitted-benchmarks", "self-reported-user-data", "submits-data-creates-value"),
        ]
        del concepts[1]["mechanism_tag"]
        ok, msg = validate_filtered_concepts(_filtered_concepts_output(concepts))
        assert not ok
        assert "mechanism_tag" in msg

    def test_structural_duplicates_rejected(self):
        """Two kept concepts sharing M+D dimensions fail the contract."""
        output = _filtered_concepts_output([
            _concept("A", "aggregates-public-records", "government-open-data", "search-lands-on-page"),
            _concept("B", "aggregates-public-records", "government-open-data", "subscribes-gets-alerts"),
            _concept("C", "parametric-calculator", "scraped-web-pages", "enters-inputs-gets-calculation"),
        ])
        ok, msg = validate_filtered_concepts(output)
        assert not ok
        assert "Structural duplicates" in msg


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
