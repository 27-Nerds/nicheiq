"""Report-side `validated_count` contract (Codex review 2026-08 §4b).

The keyword-validation sections rendered "50/20 keywords validated" — the 50 was the
UNFILTERED expansion pool and the 20 was the seed count, so both the numerator and the
ratio were wrong. Both sections must count the semantically graded, on-idea set.
"""

from types import SimpleNamespace

from nicheiq.models.keyword_data import CrewKeywordValidationResult
from nicheiq.report.utils.state_accessors import StateAccessor, graded_keyword_count


def _validation(**overrides):
    defaults = dict(
        solution_name="VetMedAudit",
        validated_count=50,  # legacy shape: the unfiltered expansion pool
        total_volume=50000,
        avg_competition=40.0,
        keyword_demand_score=0.91,
        demand_signal="strong",
        validation_signals={"has_search_demand": True},
        attempts_made=1,
        best_relevance_score=0.7,
        niche_relevant_volume=90,
        validated_keywords=[{"keyword": "vet medication audit", "search_volume": 90}],
    )
    defaults.update(overrides)
    return CrewKeywordValidationResult(**defaults)


def _accessor(results):
    return StateAccessor(
        SimpleNamespace(seo_strategy_report=None, keyword_validation_results=results)
    )


class TestGradedKeywordCountHelper:
    def test_prefers_graded_list_over_stored_count(self):
        assert graded_keyword_count(_validation()) == 1

    def test_dict_input_from_raw_checkpoint(self):
        raw = {"validated_count": 50, "validated_keywords": [{"keyword": "a"}]}
        assert graded_keyword_count(raw) == 1

    def test_graded_and_empty_is_zero(self):
        assert graded_keyword_count({"validated_count": 50, "validated_keywords": []}) == 0

    def test_falls_back_when_list_never_persisted(self):
        assert graded_keyword_count({"validated_count": 7}) == 7


class TestKeywordValidationOverview:
    def test_reports_graded_count_not_expansion_pool(self):
        overview = _accessor([_validation()]).get_keyword_validation_overview()

        assert "1 keywords validated" in overview
        assert "50/20" not in overview
        assert "50 keywords validated" not in overview

    def test_graded_and_empty_reports_zero(self):
        overview = _accessor(
            [_validation(validated_keywords=[], niche_relevant_volume=0)]
        ).get_keyword_validation_overview()

        assert "0 keywords validated" in overview


class TestKeywordValidationComparison:
    def test_table_row_uses_graded_count(self):
        table = _accessor([_validation()]).get_keyword_validation_comparison()

        row = [line for line in table.split("\n") if "VetMedAudit" in line][0]
        assert "| VetMedAudit | 1 |" in row
