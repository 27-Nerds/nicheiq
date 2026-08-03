"""4.3 — keyword-validation prompt context: {pains}/{angle} placeholders, list→string
joins, and removal of the blanket software-keyword exception."""

from nicheiq.utils.prompts import load_prompt
from nicheiq.utils.validation.keyword_validator import KeywordRelevanceValidator


def _prompt(**kw):
    base = dict(
        keywords_text="[0] some keyword",
        batch_size=1,
        niche_description="freight brokers",
        solution_name="QuickPayKit",
        solution_description="demand-letter generator for unpaid freight invoices",
        project_type="saas",
    )
    base.update(kw)
    return KeywordRelevanceValidator()._build_validation_prompt(**base)


class TestPromptContext:
    def test_pains_and_angle_rendered(self):
        p = _prompt(
            pain_points_addressed=["carriers unpaid for 90 days", "broker bond claims stall"],
            winning_angle="workflow",
        )
        assert "Problems it solves: carriers unpaid for 90 days, broker bond claims stall" in p
        assert "Go-to-market angle: workflow" in p

    def test_lists_joined_before_safe_format(self):
        """safe_format raises KeyError on unfilled placeholders — a list value would also
        break its brace-escaping; the join must happen before formatting."""
        p = _prompt(pain_points_addressed=["a", "b", "c"], winning_angle="distribution_seo")
        assert "['a'" not in p and "a, b, c" in p

    def test_defaults_fill_placeholders_without_error(self):
        # Existing callers pass no context: placeholders must still be filled (KeyError-free)
        p = _prompt()
        assert "Problems it solves: (not specified)" in p
        assert "Go-to-market angle: (not specified)" in p

    def test_empty_list_and_blank_angle_fall_back(self):
        p = _prompt(pain_points_addressed=[], winning_angle="   ")
        assert "Problems it solves: (not specified)" in p
        assert "Go-to-market angle: (not specified)" in p


class TestSoftwareExceptionRemoved:
    def test_blanket_software_exception_carved_out(self):
        template = load_prompt("keyword_validation")
        assert "IMPORTANT EXCEPTION" not in template
        assert "npm, react, terraform" not in template
        # rejection rules themselves remain
        assert "AUTOMATIC REJECTION RULES" in template

    def test_template_declares_new_placeholders(self):
        template = load_prompt("keyword_validation")
        assert "{pains}" in template and "{angle}" in template
