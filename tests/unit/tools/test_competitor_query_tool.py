"""CompetitorQueryTool input sanitization.

The tool takes a positional pipe-delimited string, so the tool-calling LLM can slide the
niche into the project_type slot. Live-caught 2026-08-03 (run 8ef396eb): project_type
arrived as "independent U.S. live music venues", which then rendered into every
"Project Type:" instruction in the query prompt.
"""

from unittest.mock import patch

from nicheiq.tools.competitor_query_tool import CompetitorQueryTool


def _run(input_str):
    tool = CompetitorQueryTool()
    with patch.object(
        tool._generator, "generate_competitor_queries", return_value=[]
    ) as gen:
        tool._run(input_str)
    return gen.call_args.kwargs


class TestProjectTypeSanitization:
    def test_niche_prose_in_project_type_slot_falls_back_to_saas(self):
        kwargs = _run("HouseNutIndex|independent U.S. live music venues|house nut")
        assert kwargs["project_type"] == "saas"
        assert kwargs["solution_name"] == "HouseNutIndex"
        assert kwargs["pain_points_addressed"] == ["house nut"]

    def test_known_project_type_is_preserved(self):
        assert _run("ShowClose|directory|settlement")["project_type"] == "directory"

    def test_case_insensitive_match_is_preserved(self):
        assert _run("ShowClose|SaaS")["project_type"] == "SaaS"

    def test_missing_project_type_defaults_to_saas(self):
        assert _run("ShowClose")["project_type"] == "saas"
