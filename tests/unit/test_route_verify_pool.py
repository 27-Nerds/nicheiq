"""Verification parity (2026-07-03): only per-cell tournament winners get the search-grounded
verify_data_routes at birth — bundles/salvaged/re-injections shipped model-knowledge route
labels (live: a bundle shipped SAM.gov as 'paywalled'). _verify_pool_routes runs the SAME
verifier post-union on everything not birth-verified."""

import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.search_tool = None
    crew._run_parallel = lambda fn, jobs, *a, **k: [fn(**j) for j in jobs]
    return crew


def _idea(name):
    return SimpleNamespace(solution_name=name)


class TestVerifyPoolRoutes:
    def test_skips_birth_verified_winners(self):
        crew = _crew()
        crew._birth_verified_names = {"Winner1", "Winner2"}
        seen = []
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=lambda i, g, **kw: seen.append(i.solution_name)):
            crew._verify_pool_routes([_idea("Winner1"), _idea("Bundle1"),
                                      _idea("Winner2"), _idea("Salvaged1")])
        assert seen == ["Bundle1", "Salvaged1"]

    def test_no_tracking_means_verify_everything(self):
        # convergent path never birth-verifies — the parity pass covers the whole pool
        crew = _crew()
        seen = []
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=lambda i, g, **kw: seen.append(i.solution_name)):
            crew._verify_pool_routes([_idea("A"), _idea("B")])
        assert seen == ["A", "B"]

    def test_failsoft_per_idea(self):
        crew = _crew()
        crew._birth_verified_names = set()
        calls = []
        def _boomy(i, g, **kw):
            calls.append(i.solution_name)
            if i.solution_name == "A":
                raise RuntimeError("verifier down")
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=_boomy):
            crew._verify_pool_routes([_idea("A"), _idea("B")])  # must not raise
        assert calls == ["A", "B"]

    def test_all_verified_is_noop(self):
        crew = _crew()
        crew._birth_verified_names = {"A"}
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=AssertionError("must not run")):
            crew._verify_pool_routes([_idea("A")])


class TestPipelineWiring:
    def test_winners_tracked_before_salvage_and_bundles(self):
        src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
        assert src.index("_birth_verified_names") < src.index("_salvage_cell_losers(")

    def test_verify_runs_after_feasibility_before_dev_time(self):
        # 'blocked' caps build_feasibility (must not be overwritten by _finalize_feasibility);
        # dev-time and the calibration critic read the route label (must see the verified one).
        src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
        assert src.index("_finalize_feasibility(") < src.index("_verify_pool_routes(")
        assert src.index("_verify_pool_routes(") < src.index("_finalize_dev_time(")

    def test_score_wave_adjudicates_the_route_before_pricing_it(self):
        # Wave-born ideas (pivot revisions, variant merges, red-team revisions) carry a
        # GENERATOR SELF-REPORTED data_access_model, not a verifier verdict. The 'blocked'
        # feasibility cap is irreversible, so the verifier must adjudicate the label BEFORE
        # _finalize_feasibility prices it. (execute_pipeline keeps the opposite order for a
        # different reason — there _finalize_feasibility restores the critic's stash onto the
        # very concepts it scored; see test above.)
        src = inspect.getsource(UnifiedSolutionCrew._score_wave)
        assert src.index("_finalize_idea_pool(") < src.index("_verify_pool_routes(")
        assert src.index("_verify_pool_routes(") < src.index("_finalize_feasibility(")


# ---------------------------------------------------------------------------
# Regression (2026-07-27): a generator SELF-REPORTED 'blocked' arriving through _score_wave
# used to be priced by _finalize_feasibility before the verifier ever ran — data <= 0.2 ->
# build <= 0.2+margin -> market_fit rule (b) <= 0.40, with nothing downstream able to un-cap
# (the calibration critic re-scores market_fit/technical/novelty/seo/obviousness/solo_dev, not
# build or data feasibility). The caps are for the SEARCH-GROUNDED 'refuted' verdict only.
# ---------------------------------------------------------------------------

class TestScoreWaveBlockedSelfReportIsNotPermanent:
    @staticmethod
    def _wave_idea():
        return SimpleNamespace(
            solution_name="Pivoted Product",
            # the generator's own guess — never search-grounded
            data_access_model="blocked",
            data_acquisition_notes="",
            data_sources=["Acme Vendor Feed"],
            data_feasibility_score=0.9,
            build_feasibility_score=0.9,
            market_fit_score=0.8,
            technical_feasibility_score=0.7,
            solo_dev_feasibility=0.7,
            novelty_score=0.6,
            obviousness_score=0.3,
            winning_angle=None,
            source_segment_payability=None,
            source_segment_payability_class=None,
            source_frame="pain",
            project_type="saas",
            technical_approach="Pulls the feed nightly.",
            candidate_status=None,
            tags=None,
        )

    @staticmethod
    def _crew_with_real_route_steps():
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.search_tool = None
        crew._run_parallel = lambda fn, jobs, *a, **k: [fn(**j) for j in jobs]
        crew._birth_verified_names = set()
        crew._critic_feasibility = {}  # wave-born idea is a NEW product; critic never scored it
        # Everything except pool-contract / route-verify / feasibility / caps is out of scope.
        crew._filter_pain_relevance = lambda wave: None
        crew._stamp_payability = lambda w: None
        crew._finalize_dev_time = lambda wave: None
        crew._probe_mechanism_parity = lambda wave: None
        crew._calibrate_idea_scores = lambda wave: None
        crew._classify_idea_angles = lambda wave: None
        return crew

    def test_verifier_confirming_a_public_route_leaves_the_scores_uncapped(self):
        crew = self._crew_with_real_route_steps()
        idea = self._wave_idea()

        def _verifier_says_supported(i, g, **kw):
            i.data_access_model = "public"
            i.data_acquisition_notes = "Documented public API."

        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=_verifier_says_supported), \
                patch("nicheiq.utils.public_data_sources.llm_confirm_known_route",
                      return_value=None):
            crew._score_wave([idea])

        assert idea.data_access_model == "public"
        # No cap survived the self-report: the verifier adjudicated the label first.
        assert idea.data_feasibility_score == 0.9
        assert idea.build_feasibility_score == 0.9
        assert idea.market_fit_score == 0.8

    def test_verifier_refuting_the_route_still_caps(self):
        # The caps are NOT weakened — a search-grounded refutation still prices the idea.
        crew = self._crew_with_real_route_steps()
        idea = self._wave_idea()
        idea.data_access_model = "public"  # generator was optimistic this time

        def _verifier_says_refuted(i, g, **kw):
            i.data_access_model = "blocked"

        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=_verifier_says_refuted), \
                patch("nicheiq.utils.public_data_sources.llm_confirm_known_route",
                      return_value=None):
            crew._score_wave([idea])

        assert idea.data_access_model == "blocked"
        assert idea.data_feasibility_score == 0.2
        assert idea.build_feasibility_score == pytest.approx(0.35)
        assert idea.market_fit_score == 0.4
