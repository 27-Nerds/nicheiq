"""
Tests for report templates, specifically the CAC breakdown and extract_midpoint logic.

Regression test for: ValueError: could not convert string to float: '.'
Root cause: regex r'[\\d.]+' matched standalone '.' from LLM-generated cac_paid strings.
"""

import pytest
from unittest.mock import MagicMock

from nicheiq.report.templates.report_templates import ReportTemplates


def _make_solution(**overrides):
    """Create a mock SolutionIdea with sensible defaults."""
    sol = MagicMock()
    sol.solution_name = "TestTool"
    sol.estimated_cac_organic = "$5-10"
    sol.estimated_cac_paid = "$100-300"
    sol.estimated_indexable_pages = 5000
    sol.seo_scalability_score = 0.85
    sol.core_features = ["Feature A", "Feature B"]
    sol.project_type = "directory"
    sol.value_proposition = "test value prop"
    for key, val in overrides.items():
        setattr(sol, key, val)
    return sol


# ---------------------------------------------------------------------------
# extract_midpoint regression tests (via _compute_cac_advantage)
# ---------------------------------------------------------------------------

class TestComputeCacAdvantage:
    """Tests for ReportTemplates._compute_cac_advantage."""

    def test_normal_range_values(self):
        """Normal case: '$5-10' organic, '$100-300' paid -> ratio computed."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("$5-10", "$100-300", sol)
        assert "CAC Advantage" in result
        # Midpoints: organic=7.5, paid=200 -> ratio ≈ 27
        assert "approximately" in result

    def test_single_dollar_values(self):
        """Single values like '$10' and '$200'."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("$10", "$200", sol)
        assert "approximately 20x" in result

    def test_decimal_values(self):
        """Decimal values like '$5.50' and '$150.00'."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("$5.50", "$150.00", sol)
        assert "CAC Advantage" in result
        assert "approximately" in result

    def test_standalone_dot_does_not_crash(self):
        """Regression: cac_paid with standalone '.' must not raise ValueError."""
        sol = _make_solution()
        # This was the exact crash scenario
        result = ReportTemplates._compute_cac_advantage("$5-10", "$.", sol)
        assert "CAC Advantage" in result

    def test_ellipsis_does_not_crash(self):
        """Regression: strings containing '...' must not crash."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("$5-10", "$...", sol)
        assert "CAC Advantage" in result

    def test_text_with_dots_does_not_crash(self):
        """Regression: descriptive text with periods must not crash."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage(
            "$5-10", "Varies by market. Approx. $100-200.", sol
        )
        assert "CAC Advantage" in result
        assert "approximately" in result

    def test_na_values_fallback(self):
        """N/A values should return fallback text."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("N/A", "N/A", sol)
        assert "CAC Advantage" in result
        assert "5,000+" in result  # falls back to page-count message

    def test_empty_string_fallback(self):
        """Empty strings should return fallback text."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("", "", sol)
        assert "CAC Advantage" in result

    def test_no_numbers_at_all(self):
        """Strings with no numbers at all should return fallback."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("free", "expensive", sol)
        assert "CAC Advantage" in result

    def test_no_indexable_pages_fallback(self):
        """Without indexable pages, uses generic organic message."""
        sol = _make_solution(estimated_indexable_pages=None)
        result = ReportTemplates._compute_cac_advantage("N/A", "N/A", sol)
        assert "reduces customer acquisition costs" in result

    def test_leading_dot_number(self):
        """Values like '$.50' should parse correctly as 0.5."""
        sol = _make_solution()
        result = ReportTemplates._compute_cac_advantage("$.50", "$100", sol)
        assert "approximately 200x" in result

    def test_unparseable_regex_match_does_not_crash(self):
        """Hardening: if re.findall returns something float() can't parse,
        extract_midpoint skips it gracefully instead of raising ValueError."""
        from unittest.mock import patch
        sol = _make_solution()
        # Simulate a regex returning a bare '.' (the original bug's root cause)
        with patch("re.findall", return_value=[".", "100"]):
            result = ReportTemplates._compute_cac_advantage("$5-10", "$100", sol)
            assert "CAC Advantage" in result

    def test_all_unparseable_regex_matches_returns_fallback(self):
        """Hardening: if every regex match is unparseable, falls back to
        generic message instead of crashing."""
        from unittest.mock import patch
        sol = _make_solution()
        with patch("re.findall", return_value=[".", "..", "abc"]):
            result = ReportTemplates._compute_cac_advantage("$5-10", "$bad", sol)
            assert "CAC Advantage" in result


# ---------------------------------------------------------------------------
# cac_breakdown integration tests
# ---------------------------------------------------------------------------

class TestCacBreakdown:
    """Tests for ReportTemplates.cac_breakdown."""

    def test_none_solution_returns_none(self):
        assert ReportTemplates.cac_breakdown(None) is None

    def test_normal_solution_produces_table(self):
        sol = _make_solution()
        result = ReportTemplates.cac_breakdown(sol)
        assert "## CAC Breakdown" in result
        assert "Organic (SEO)" in result
        assert "Paid (SEM)" in result

    def test_cac_breakdown_with_dot_in_paid(self):
        """Regression: cac_paid containing dots must not crash cac_breakdown."""
        sol = _make_solution(estimated_cac_paid="$.")
        result = ReportTemplates.cac_breakdown(sol)
        assert "## CAC Breakdown" in result

    def test_cac_breakdown_seo_scalability_ratings(self):
        """SEO scalability rating thresholds."""
        sol_excellent = _make_solution(seo_scalability_score=0.9)
        assert "Excellent" in ReportTemplates.cac_breakdown(sol_excellent)

        sol_good = _make_solution(seo_scalability_score=0.7)
        assert "Good" in ReportTemplates.cac_breakdown(sol_good)

        sol_moderate = _make_solution(seo_scalability_score=0.4)
        assert "Moderate" in ReportTemplates.cac_breakdown(sol_moderate)

    def test_cac_breakdown_seo_scalability_score_scaled(self):
        """SEO scalability score should be displayed as X.Y/10 (multiplied by 10)."""
        sol = _make_solution(seo_scalability_score=0.85)
        result = ReportTemplates.cac_breakdown(sol)
        assert "8.5/10" in result  # 0.85 * 10 = 8.5
        assert "0.8/10" not in result  # must not show raw 0-1 value

    def test_cac_breakdown_no_seo_score(self):
        """No SEO scalability section when score is None."""
        sol = _make_solution(seo_scalability_score=None)
        result = ReportTemplates.cac_breakdown(sol)
        assert "SEO Scalability" not in result

    def test_cac_breakdown_no_indexable_pages(self):
        """Without indexable pages, rationale says analysis required."""
        sol = _make_solution(estimated_indexable_pages=None)
        result = ReportTemplates.cac_breakdown(sol)
        assert "technical analysis" in result
