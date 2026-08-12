"""The ONE data-provenance vocabulary (`DataAccessTag`) across every slim-schema write site.

Regression cover for the 2026-07 fix: four slim-schema paths (bundles, variant merge, parity
pivot, red-team revision) shared an accept-list that took the legacy 'none' but REJECTED the
canonical 'blocked'/'unverified' — silently nulling the two labels that drive the feasibility
cap, the market-fit rule-b cap and the pre-rank filter. Off-vocab now ABSTAINS to 'unverified'
instead of dropping to None (a null label reads downstream as "no data barrier").
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.data_access import (
    DATA_ACCESS_ALIASES,
    DATA_ACCESS_VOCAB,
    normalize_data_access,
    note_route_label,
    route_label_summary,
)


class TestNormalizeDataAccess:
    def test_vocab_is_the_canonical_literal(self):
        assert DATA_ACCESS_VOCAB == {
            "public", "freemium", "paywalled", "unofficial", "restricted", "blocked", "unverified"}
        # aliases must never shadow a canonical value
        assert not (set(DATA_ACCESS_ALIASES) & DATA_ACCESS_VOCAB)

    @pytest.mark.parametrize("raw,expected", [
        ("none", "public"),                 # pure computation / user-supplied input
        ("not-data-dependent", "public"),
        ("official", "public"),
        ("licensed", "paywalled"),
        ("  Public  ", "public"),
        ("BLOCKED", "blocked"),
        ("unverified", "unverified"),
    ])
    def test_aliases_and_canonicals(self, raw, expected):
        assert normalize_data_access(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "   ", "Read-only aggregation from GitHub"])
    def test_empty_and_prose_return_none(self, raw):
        assert normalize_data_access(raw) is None


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="cottage food bakers")
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.cost_tracker = None
    crew._expand_bundle = lambda b: None      # fail-soft path: slim composition ships as-is
    crew._record_divergent_usage = lambda u: None
    return crew


def _llm(dump):
    """Patch target for a slim-schema call returning `dump` verbatim."""
    return patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                 return_value=(SimpleNamespace(model_dump=lambda: dict(dump)), None))


_SLIM = {
    "solution_name": "MergedThing", "value_proposition": "does the merged thing",
    "description": "a description", "core_features": ["f"], "target_personas": ["p"],
    "conventional_approach": "", "innovation_angle": "", "why_it_works": "",
    "technical_approach": "", "market_fit_score": 0.7, "technical_feasibility_score": 0.7,
    "build_feasibility_score": 0.8, "data_feasibility_score": 0.8,
    "programmatic_seo_opportunity": "",
}


def _bundle_dump(**kw):
    d = dict(_SLIM)
    d.update({"project_type": "saas", "pain_points_addressed": ["Cannot calculate COGS"],
              "requires_data_aggregation": False, "content_generation_model": "",
              "estimated_indexable_pages": 50})
    d.update(kw)
    return d


def _variant(name="V1"):
    return SimpleNamespace(solution_name=name, value_proposition="vp", technical_approach="ta",
                           core_features=["f"], innovation_angle="ia",
                           pain_points_addressed=["Cannot calculate COGS"],
                           source_pain="Cannot calculate COGS", source_segment="Seg",
                           source_frame="pain")


def _orig(name="Orig"):
    return SimpleNamespace(solution_name=name, value_proposition="vp", technical_approach="ta",
                           incumbent_parity="shipped by Etsy: templates",
                           pain_points_addressed=["Cannot calculate COGS"],
                           target_personas=["bakers"], source_pain="Cannot calculate COGS",
                           source_segment="Seg", source_frame="pain", idea_tier="single")


# Every case below is asserted on ALL FOUR slim-schema paths.
_CASES = [
    ("blocked", "blocked"),          # was silently nulled -> feasibility caps escaped
    ("unverified", "unverified"),    # was silently nulled
    ("none", "public"),              # legacy label, aliased
    ("official", "public"),
    ("licensed", "paywalled"),
    ("public", "public"),
    ("Read-only scrape of a partner portal", "unverified"),   # off-vocab ABSTAINS
]


@pytest.mark.parametrize("raw,expected", _CASES)
class TestSlimSchemaPathsPreserveVocab:
    def test_synthesize_bundles(self, raw, expected):
        crew = _crew()
        crew.pain_point_analysis = SimpleNamespace(pain_points=[
            SimpleNamespace(title="Cannot calculate COGS", severity_score=0.7,
                            commercial_intent=0.45)])
        d = _bundle_dump(data_access_model=raw)
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([SimpleNamespace(
                solution_name="W1", value_proposition="w")])
        assert out[0].data_access_model == expected
        assert crew._route_label_counts["labels"] == 1  # emission-rate tally wired

    def test_synthesize_variant_merge(self, raw, expected):
        crew = _crew()
        with _llm(dict(_SLIM, project_type="saas", data_access_model=raw)):
            merged = crew._synthesize_variant_merge([_variant("V1"), _variant("V2")], "shared")
        assert merged is not None
        assert merged.data_access_model == expected
        assert crew._route_label_counts["labels"] == 1

    def test_generate_pivot_revision(self, raw, expected):
        crew = _crew()
        with _llm(dict(_SLIM, data_access_model=raw)):
            rev = crew._generate_pivot_revision(_orig(), {})
        assert rev is not None
        assert rev.data_access_model == expected
        assert crew._route_label_counts["labels"] == 1

    def test_red_team_revision(self, raw, expected):
        from nicheiq.models.solution_idea import RedTeamFinding
        from nicheiq.utils.red_team_review import _RedTeamVerdict, _attempt_red_team_revision

        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.cost_tracker = None
        # `_score_wave` stamps a complete, winning score vector so the accept-guard passes and
        # the revision actually lands in the pool (that is where the label has to survive).
        def _stamp(wave, **kw):
            for i in wave:
                i.market_fit_score = 0.9
                i.technical_feasibility_score = 0.9
                i.novelty_score = 0.8
                i.seo_scalability_score = 0.8
                i.incumbent_parity = "none found"
        crew._score_wave = MagicMock(side_effect=_stamp)

        orig = _orig()
        orig.market_fit_score = 0.2
        orig.technical_feasibility_score = 0.2
        orig.novelty_score = 0.1
        orig.seo_scalability_score = 0.1
        orig.winning_angle = None
        refined = SimpleNamespace(solution_ideas=[orig])
        with patch("nicheiq.utils.llm_service.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(
                       model_dump=lambda: dict(_SLIM, data_access_model=raw)),
                       SimpleNamespace(to_dict=lambda: {}))):
            # Real verdict model, not a namespace: RT-1 retyped `caveats` -> typed `findings`,
            # and a hand-rolled double silently took the fail-soft path instead of revising.
            assert _attempt_red_team_revision(
                crew, refined, orig,
                _RedTeamVerdict(verdict="killed", uplift=None, findings=[RedTeamFinding(
                    claim="free in Etsy", kind="verified_free_or_bundled_alternative")]),
                "evidence") is True
        assert refined.solution_ideas[0].data_access_model == expected
        assert crew._route_label_counts["labels"] == 1


class TestBundleProseStillDivertsToNotes:
    """The bundle path keeps its prose -> data_acquisition_notes divert; only the LABEL
    changed (None -> abstain 'unverified')."""

    def test_prose_kept_in_notes(self):
        crew = _crew()
        crew.pain_point_analysis = SimpleNamespace(pain_points=[
            SimpleNamespace(title="Cannot calculate COGS", severity_score=0.7,
                            commercial_intent=0.45)])
        d = _bundle_dump(data_access_model="Read-only aggregation from Hugging Face Hub")
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([SimpleNamespace(
                solution_name="W1", value_proposition="w")])
        assert out[0].data_access_model == "unverified"
        assert "Hugging Face Hub" in (out[0].data_acquisition_notes or "")


class TestSlimSchemaPromptsDoNotSolicitNone:
    """`none` was live because four slim schemas ASKED for it. Every data_access_model field
    description must offer the canonical vocab (incl. blocked/unverified) and never 'none'."""

    def test_no_slim_schema_offers_none(self):
        import inspect

        import nicheiq.utils.red_team_review as rtr

        for src in (inspect.getsource(UnifiedSolutionCrew._synthesize_bundles),
                    inspect.getsource(UnifiedSolutionCrew._synthesize_variant_merge),
                    inspect.getsource(UnifiedSolutionCrew._generate_pivot_revision),
                    inspect.getsource(rtr._attempt_red_team_revision)):
            assert "unofficial | restricted | none" not in src
            assert "blocked | unverified" in src


class TestRouteLabelCounter:
    """Emission-rate tally (2026-07-27): the four generator paths logged a warning per
    off-vocab abstention, but nothing recorded how often 'blocked'/off-vocab actually occurs —
    the rate could only be estimated. `note_route_label` counts it; `route_label_summary`
    emits ONE line per run."""

    def test_counts_only_blocked_and_off_vocab(self):
        owner = SimpleNamespace()
        note_route_label(owner, "bundle", "public")       # benign — total only
        note_route_label(owner, "bundle", "blocked")      # generator self-report
        note_route_label(owner, "red-team", None)         # off-vocab -> abstains
        assert owner._route_label_counts == {
            "labels": 3, "blocked:bundle": 1, "off-vocab:red-team": 1}

    def test_summary_is_one_line_and_none_when_nothing_recorded(self):
        assert route_label_summary(SimpleNamespace()) is None
        owner = SimpleNamespace()
        note_route_label(owner, "parity-pivot", "blocked")
        summary = route_label_summary(owner)
        assert "\n" not in summary
        assert summary == "1 generator-emitted data_access_model label(s); blocked:parity-pivot=1"

    def test_never_raises_on_a_counterless_owner(self):
        note_route_label(object(), "bundle", "blocked")  # __slots__-like owner: must not raise
