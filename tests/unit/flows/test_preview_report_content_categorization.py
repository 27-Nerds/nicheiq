"""
Test that _materialize_preview_report serializes pain_point_analysis.content_categorization.

Guards Phase 1 (catalog content_categorization persistence): the preview report
is the asset the backend reads to extract CatalogResearchContext fields, and the
catalog ideas worker rehydrates the categorization to feed UnifiedSolutionCrew.
If this stops being persisted, both downstreams silently degrade — the worker
logs "No user segments available from pain point analysis" and category landing
pages lose the Themes & Audience Segments section.
"""

from __future__ import annotations

import json
from pathlib import Path

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.pain_point import (
    ContentCategorizationReport,
    OpportunityLevel,
    PainPoint,
    PainPointAnalysisResult,
    ThemeCategory,
    UserSegment,
)


NICHE = "AI productivity tools for indie hackers"


def _build_categorization() -> ContentCategorizationReport:
    return ContentCategorizationReport(
        executive_summary="Five themes emerged across the discussions.",
        theme_categories=[
            ThemeCategory(
                category_name=f"Theme {i}",
                definition=f"Definition for theme {i}",
                frequency="High",
                mention_count=10 + i,
                primary_user_segments=["Hobbyists"],
                anchor_keywords=[f"phrase-{i}-a", f"phrase-{i}-b", f"phrase-{i}-c"],
            )
            for i in range(4)
        ],
        user_segments=[
            UserSegment(
                segment_name=f"Segment {i}",
                primary_concerns=["concern-a", "concern-b"],
                mention_frequency="High",
            )
            for i in range(3)
        ],
        overall_quality="High",
    )


def _build_pain_analysis(
    content_cat: ContentCategorizationReport | None,
) -> PainPointAnalysisResult:
    return PainPointAnalysisResult(
        niche=NICHE,
        pain_points=[
            PainPoint(
                title="Pain 1",
                description="desc",
                mention_count=5,
                severity_score=0.6,
                commercial_intent=0.5,
                opportunity_level=OpportunityLevel.MEDIUM,
                representative_quotes=["q1"],
            )
        ],
        total_mentions=5,
        top_categories=[],
        analysis_summary="summary",
        content_categorization=content_cat,
    )


def _read_preview(tmp_path: Path) -> dict:
    files = list(tmp_path.glob("preview_report_*.json"))
    assert len(files) == 1, f"expected one preview report, got {files}"
    return json.loads(files[0].read_text())


class TestContentCategorizationInPreview:
    def test_populated_categorization_appears_in_preview(self, tmp_path):
        flow = ResearchFlow(niche_description=NICHE, job_id="test-job-1")
        flow.state.pain_point_analysis = _build_pain_analysis(_build_categorization())

        path = flow._materialize_preview_report(str(tmp_path))
        assert path is not None

        report = _read_preview(tmp_path)
        cc = report["content_categorization"]
        assert cc is not None
        assert cc["executive_summary"] == "Five themes emerged across the discussions."
        assert len(cc["theme_categories"]) == 4
        assert cc["theme_categories"][0]["category_name"] == "Theme 0"
        assert "phrase-0-a" in cc["theme_categories"][0]["anchor_keywords"]
        assert len(cc["user_segments"]) == 3
        assert cc["user_segments"][0]["segment_name"] == "Segment 0"

    def test_missing_categorization_yields_null(self, tmp_path):
        flow = ResearchFlow(niche_description=NICHE, job_id="test-job-2")
        flow.state.pain_point_analysis = _build_pain_analysis(content_cat=None)

        path = flow._materialize_preview_report(str(tmp_path))
        assert path is not None

        report = _read_preview(tmp_path)
        assert report["content_categorization"] is None

    def test_no_pain_analysis_yields_null(self, tmp_path):
        flow = ResearchFlow(niche_description=NICHE, job_id="test-job-3")
        flow.state.pain_point_analysis = None

        path = flow._materialize_preview_report(str(tmp_path))
        assert path is not None

        report = _read_preview(tmp_path)
        assert report["content_categorization"] is None


class TestAngleFieldsInPreview:
    """Guards the angle-aware fields through the preview-report materializer — the hand-built
    `alt` dict must carry winning_angle/angle_rationale/novelty_rationale, else the Phase-1 locked
    report-preview shows no angle badge/comment (the _materialize_preview_report trap CLAUDE.md warns of)."""

    def _idea(self, name, **over):
        from nicheiq.models.solution_idea import BaseSolutionIdea
        base = dict(
            solution_name=name, description="d" * 30, value_proposition="v",
            pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
            market_fit_score=0.6, technical_feasibility_score=0.7, novelty_score=0.4,
            seo_scalability_score=0.5, project_type="directory",
            winning_angle="distribution_seo", angle_rationale="A catalog play; edge is freshness.",
            novelty_rationale="Low mechanism-novelty is normal for a directory.",
        )
        base.update(over)
        return BaseSolutionIdea(**base)

    def test_angle_fields_appear_on_preview_alternatives(self, tmp_path):
        from nicheiq.models.solution_idea import IdeaGenerationResult
        flow = ResearchFlow(niche_description=NICHE, job_id="test-job-angle")
        flow.state.idea_generation = IdeaGenerationResult(
            solution_ideas=[
                self._idea("Cat", winning_angle="distribution_seo"),
                self._idea("Tool", winning_angle="novel_differentiation",
                           angle_rationale="Novel mechanism.", project_type="saas"),
                self._idea("Flow", winning_angle="vertical_workflow",
                           angle_rationale="Owns a workflow.", project_type="saas"),
            ]
        )

        path = flow._materialize_preview_report(str(tmp_path))
        assert path is not None

        alts = _read_preview(tmp_path)["alternative_solutions"]
        assert alts and len(alts) == 3
        by_name = {a["solution_name"]: a for a in alts}
        assert by_name["Cat"]["winning_angle"] == "distribution_seo"
        assert "freshness" in by_name["Cat"]["angle_rationale"]
        assert by_name["Cat"]["novelty_rationale"]
        assert by_name["Tool"]["winning_angle"] == "novel_differentiation"

    def test_delivery_format_appears_on_preview_alternatives(self, tmp_path):
        from nicheiq.models.solution_idea import IdeaGenerationResult

        flow = ResearchFlow(niche_description=NICHE, job_id="test-job-format")
        flow.state.idea_generation = IdeaGenerationResult(
            solution_ideas=[
                self._idea("Extension", delivery_format="browser-extension"),
                self._idea("API", delivery_format="api"),
                self._idea("Legacy"),
            ]
        )

        path = flow._materialize_preview_report(str(tmp_path))
        assert path is not None

        alternatives = _read_preview(tmp_path)["alternative_solutions"]
        by_name = {alternative["solution_name"]: alternative for alternative in alternatives}
        assert by_name["Extension"]["delivery_format"] == "browser-extension"
        assert by_name["API"]["delivery_format"] == "api"
        assert by_name["Legacy"]["delivery_format"] is None
