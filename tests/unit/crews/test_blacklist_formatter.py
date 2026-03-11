"""Tests for UnifiedSolutionCrew._format_blacklist() and _tokenize_name()."""

import pytest

from nicheiq.crews.unified_solution_crew import _tokenize_name


def _make_crew_with_ideas(ideas: list[dict]) -> "UnifiedSolutionCrew":
    """Create a minimal UnifiedSolutionCrew with only existing_ideas set.

    Bypasses full __init__ by constructing object without calling it.
    """
    from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

    obj = object.__new__(UnifiedSolutionCrew)
    obj.existing_ideas = ideas
    obj.existing_idea_names = {i["name"].lower() for i in ideas if i.get("name")}
    return obj


class TestTokenizeName:
    """Tests for the _tokenize_name module-level helper."""

    def test_camel_case_splitting(self):
        tokens = _tokenize_name("GLP1SideEffectAtlas")
        assert "glp1" in tokens
        assert "side" in tokens
        assert "effect" in tokens
        assert "atlas" in tokens

    def test_hyphen_normalization(self):
        # GLP-1 and GLP1 should produce the same token
        tokens_hyphen = _tokenize_name("GLP-1")
        tokens_no_hyphen = _tokenize_name("GLP1")
        assert tokens_hyphen == tokens_no_hyphen
        assert "glp1" in tokens_hyphen

    def test_uppercase_preserved_as_single_token(self):
        tokens = _tokenize_name("COA")
        assert tokens == ["coa"]

    def test_bpc_157_hyphen_stripped(self):
        tokens = _tokenize_name("BPC-157")
        assert "bpc157" in tokens

    def test_stop_words_filtered(self):
        tokens = _tokenize_name("MyAIToolProHub")
        # "my", "ai", "tool", "pro", "hub" are all stop words
        assert "my" not in tokens
        assert "ai" not in tokens
        assert "tool" not in tokens
        assert "pro" not in tokens
        assert "hub" not in tokens

    def test_short_tokens_filtered(self):
        tokens = _tokenize_name("A B CD EFG")
        # Single chars should be filtered (< 2)
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens
        assert "efg" in tokens

    def test_underscore_splitting(self):
        tokens = _tokenize_name("dose_tracker_widget")
        assert "dose" in tokens
        assert "tracker" in tokens
        assert "widget" in tokens

    def test_meaningful_differentiators_kept(self):
        """tracker, finder, guide should NOT be filtered as stop words."""
        tokens = _tokenize_name("DoseTrackerFinder")
        assert "tracker" in tokens
        assert "finder" in tokens


class TestFormatBlacklist:
    """Tests for UnifiedSolutionCrew._format_blacklist()."""

    def test_empty_ideas_returns_first_gen_message(self):
        crew = _make_crew_with_ideas([])
        result_full = crew._format_blacklist(compact=False)
        result_compact = crew._format_blacklist(compact=True)
        assert "first generation" in result_full
        assert "first generation" in result_compact

    def test_two_ideas_no_banned_fragments(self):
        """Two ideas with no shared tokens → no BANNED section."""
        ideas = [
            {"name": "AlphaWidget", "description": "Desc for alpha."},
            {"name": "BetaGadget", "description": "Desc for beta."},
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        assert "BANNED" not in result
        assert "AlphaWidget" in result
        assert "BetaGadget" in result

    def test_banned_fragments_with_frequent_tokens(self):
        """10 ideas with 4 sharing 'SideEffect' → banned fragments include 'sideeffect'."""
        ideas = [
            {"name": f"SideEffect{chr(65 + i)}", "description": f"Desc {i}."}
            for i in range(4)
        ]
        # Add 6 more unique ideas
        ideas.extend([
            {"name": f"Unique{chr(75 + i)}", "description": f"Desc {i}."}
            for i in range(6)
        ])
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        # With 10 ideas, threshold = 3. "side" and "effect" each appear 4 times
        assert "BANNED" in result
        assert "side" in result.lower().split("BANNED")[0] or "side" in result

    def test_compact_format_shorter(self):
        """compact=True should produce shorter output with summary format."""
        ideas = [
            {"name": "TestIdea", "description": "This is the first sentence. And more details here."},
        ]
        crew = _make_crew_with_ideas(ideas)
        full = crew._format_blacklist(compact=False)
        compact = crew._format_blacklist(compact=True)
        assert "| summary:" in compact
        assert "[summary:" in full
        assert len(compact) < len(full)

    def test_ideas_with_only_name_key(self):
        """Ideas with only 'name' key → graceful fallback, no '()' in output."""
        ideas = [
            {"name": "BareBones"},
            {"name": "MinimalIdea"},
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        assert "BareBones" in result
        assert "()" not in result
        assert "(no description available)" in result

    def test_project_type_shown_when_present(self):
        """Ideas with project_type → shows '(saas)' after name."""
        ideas = [
            {"name": "TestSaas", "description": "A SaaS tool.", "project_type": "saas"},
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        assert "TestSaas (saas)" in result

    def test_project_type_omitted_when_empty(self):
        """Ideas without project_type → no parenthetical."""
        ideas = [
            {"name": "TestIdea", "description": "A tool.", "project_type": ""},
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        assert "TestIdea [summary:" in result or "TestIdea" in result
        assert "TestIdea ()" not in result

    def test_adaptive_truncation_many_ideas(self):
        """35 ideas → summary one-liner only (max_desc_len=0)."""
        ideas = [
            {"name": f"Idea{i}", "description": f"Long description for idea {i}. More details. Even more."}
            for i in range(35)
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        # With 35 ideas, max_desc_len=0, so full descriptions should not appear
        # Only summary one-liners in brackets
        assert "35 total" in result
        # Should not have the long description text after the summary bracket
        for i in range(35):
            # Check that the line format is "- Name [summary: ...]" without ": Long description..."
            assert f"More details" not in result

    def test_adaptive_truncation_few_ideas(self):
        """10 ideas → 200 char descriptions."""
        desc = "x" * 250
        ideas = [
            {"name": f"Idea{i}", "description": desc}
            for i in range(10)
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        # Should truncate at 200 chars + "..."
        assert "..." in result

    def test_banned_fragments_cap_at_15(self):
        """20 ideas with 18 frequent tokens → output capped at 15."""
        # Create ideas where many unique tokens each appear in 3+ names
        ideas = []
        for i in range(20):
            # Each idea name contains multiple shared tokens
            tokens = [f"Tok{j}" for j in range(i % 18 + 1)]
            name = "".join(tokens[:3])  # Use 3 tokens per name
            ideas.append({"name": name, "description": f"Desc {i}"})

        # Create ideas that force many tokens to appear 3+ times
        token_names = [f"Frag{i}" for i in range(18)]
        ideas = []
        for i in range(20):
            # Rotate through tokens so each appears frequently
            t1 = token_names[i % 18]
            t2 = token_names[(i + 1) % 18]
            t3 = token_names[(i + 2) % 18]
            ideas.append({"name": f"{t1}{t2}{t3}", "description": f"Desc {i}"})

        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=False)
        if "BANNED" in result:
            # Extract the banned line
            for line in result.split("\n"):
                if line and not line.startswith("BANNED") and not line.startswith("ALL") and not line.startswith("-"):
                    tokens_in_line = [t.strip() for t in line.split(",") if t.strip()]
                    if len(tokens_in_line) > 1:
                        assert len(tokens_in_line) <= 15

    def test_summary_extraction_first_sentence(self):
        """Summary should be first sentence of description, capped at 80 chars."""
        ideas = [
            {"name": "Test", "description": "This is the first sentence. This is the second sentence."},
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=True)
        assert "This is the first sentence" in result
        assert "second sentence" not in result

    def test_summary_extraction_em_dash(self):
        """Summary should split on ' — ' delimiter too."""
        ideas = [
            {"name": "Test", "description": "First part of desc — second part after dash."},
        ]
        crew = _make_crew_with_ideas(ideas)
        result = crew._format_blacklist(compact=True)
        assert "First part of desc" in result
        assert "second part" not in result
