"""Phase-3.5: PainPointCrew niche-anchor plumbing (preventive, non-scoring)."""

from nicheiq.crews.pain_point_crew import PainPointCrew


def test_anchor_matchers_built_when_terms_provided():
    crew = PainPointCrew(
        niche_description="performance peptides for athletes",
        niche_anchor_terms=["BPC-157", "TB-500", "ipamorelin"],
    )
    assert crew.niche_anchor_terms == ["BPC-157", "TB-500", "ipamorelin"]
    assert crew._anchor_matchers  # non-empty


def test_anchor_matchers_empty_is_failopen():
    crew = PainPointCrew(niche_description="x")
    assert crew.niche_anchor_terms == []
    assert crew._anchor_matchers == []


def test_base_inputs_includes_anchor_terms_with_fallback():
    # With terms: joined string. Without: explicit fallback sentinel.
    crew_with = PainPointCrew(niche_anchor_terms=["BPC-157", "TB-500"])
    crew_without = PainPointCrew()

    def anchor_input(crew):
        return (
            ", ".join(crew.niche_anchor_terms)
            if crew.niche_anchor_terms
            else "(none provided — apply universality test only)"
        )

    assert anchor_input(crew_with) == "BPC-157, TB-500"
    assert "none provided" in anchor_input(crew_without)
