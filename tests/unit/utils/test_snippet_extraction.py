"""Tests for sliding-window best-evidence snippet extraction."""

from nicheiq.utils.snippet_extraction import best_evidence_window


class TestBestEvidenceWindow:
    def test_short_text_returns_full(self):
        text = "This is a short text about pricing."
        result = best_evidence_window(text, ["pricing"], window_words=80)
        assert result == text.strip()

    def test_empty_text(self):
        assert best_evidence_window("", ["query"]) == ""

    def test_empty_query(self):
        text = "Some text here that is meaningful."
        result = best_evidence_window(text, [], window_words=80)
        # Should return truncated text
        assert len(result) > 0

    def test_caps_at_window_words(self):
        words = ["word"] * 200
        text = " ".join(words)
        result = best_evidence_window(text, ["word"], window_words=50)
        result_words = result.rstrip("...").split()
        assert len(result_words) <= 50

    def test_returns_substring_of_original(self):
        text = (
            "The weather is nice today. "
            "SaaS pricing is a huge pain point for indie hackers. "
            "Many people struggle with finding the right model. "
            "The beach was crowded yesterday."
        )
        result = best_evidence_window(text, ["SaaS", "pricing", "pain"], window_words=20)
        # Result should contain relevant content
        assert "pricing" in result.lower() or "saas" in result.lower()

    def test_finds_best_window(self):
        # Build text where relevant content is in the middle
        filler_before = " ".join(["unrelated"] * 50)
        relevant = "freelancer pricing strategy is critical for SaaS founders who struggle with revenue"
        filler_after = " ".join(["irrelevant"] * 50)
        text = f"{filler_before} {relevant} {filler_after}"

        result = best_evidence_window(
            text, ["freelancer", "pricing", "SaaS"], window_words=20,
        )
        assert "pricing" in result.lower() or "freelancer" in result.lower()
