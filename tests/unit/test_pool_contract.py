"""Pool-assembly contract (2026-07-03): one choke point over all four idea birth paths.
Every prior shape bug (bundle scores, prose data_access_model, free-text project_type
chips) was a per-birth-path escape — this retires the class."""

import inspect
from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.coverage_caveats = []
    return crew


def _idea(**kw):
    base = dict(solution_name="X", project_type="saas", data_access_model="public",
                technical_approach="", data_acquisition_notes="",
                winning_angle="distribution_seo", novelty_score=0.5,
                calibration_notes="market_fit: ok")
    base.update(kw)
    return SimpleNamespace(**base)


class TestProjectTypeNormalizer:
    def test_observed_malformed_strings_clamp(self):
        # the exact strings from the crashed astro run that broke the frontend chips
        crew = _crew()
        a = _idea(project_type="Desktop app + lightweight local agent (Windows/macOS)")
        b = _idea(project_type="Desktop app (with optional cloud fetch of model metadata)")
        crew._finalize_idea_pool([a, b])
        assert a.project_type == "saas" and b.project_type == "saas"
        assert "Desktop app + lightweight local agent" in a.technical_approach

    def test_keyword_mapping(self):
        crew = _crew()
        ideas = [_idea(project_type="Curated aggregator of benchmarks"),
                 _idea(project_type="A public directory site"),
                 _idea(project_type="Comparison engine"),
                 _idea(project_type="Niche marketplace platform")]
        crew._finalize_idea_pool(ideas)
        assert [i.project_type for i in ideas] == [
            "aggregator", "directory", "comparison-tool", "marketplace"]

    def test_valid_types_untouched(self):
        crew = _crew()
        i = _idea(project_type="comparison-tool", technical_approach="orig")
        crew._finalize_idea_pool([i])
        assert i.project_type == "comparison-tool" and i.technical_approach == "orig"


class TestWellKnownSourceUpgrade:
    """Only tournament winners pass the web route-verifier; bundles/salvaged carry the
    critic's model-knowledge label — observed wrong on famous sources (run-2: a bundle
    shipped SAM.gov as 'paywalled'). Two-step (retrieval + LLM confirm), upgrade-only,
    all-sources-must-match."""

    def _confirm(self, monkeypatch, answer):
        import nicheiq.utils.public_data_sources as pds
        if answer:
            monkeypatch.setattr(pds, "llm_confirm_known_route",
                                lambda m, **kw: ", ".join(dict.fromkeys(n for _, n in m)))
        else:
            monkeypatch.setattr(pds, "llm_confirm_known_route", lambda m, **kw: None)

    def test_famous_sources_lift_restrictive_label(self, monkeypatch):
        self._confirm(monkeypatch, True)
        crew = _crew()
        i = _idea(data_access_model="paywalled",
                  data_sources=["SAM.gov opportunity notices", "SEC EDGAR full-text search API"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "public"
        assert "SAM.gov" in i.data_acquisition_notes

    def test_confirm_rejection_keeps_label(self, monkeypatch):
        self._confirm(monkeypatch, False)
        crew = _crew()
        i = _idea(data_access_model="paywalled", data_sources=["SAM.gov opportunity notices"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "paywalled"   # LLM said the match is superficial

    def test_mixed_sources_do_not_upgrade(self, monkeypatch):
        def _no_confirm(*a, **kw):
            raise AssertionError("confirm must not run when retrieval fails")
        import nicheiq.utils.public_data_sources as pds
        monkeypatch.setattr(pds, "llm_confirm_known_route", _no_confirm)
        crew = _crew()
        i = _idea(data_access_model="restricted",
                  data_sources=["GitHub Issues API", "VendorMetrics partner feed"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "restricted"

    def test_public_label_untouched_and_no_sources_noop(self, monkeypatch):
        self._confirm(monkeypatch, True)
        crew = _crew()
        a = _idea(data_access_model="public", data_sources=["SAM.gov"],
                  data_acquisition_notes="rich note")
        b = _idea(data_access_model="unverified", data_sources=[])
        crew._finalize_idea_pool([a, b])
        assert a.data_acquisition_notes == "rich note"   # upgrade path never ran
        assert b.data_access_model == "unverified"


class TestDataAccessAndCompleteness:
    def test_prose_data_access_moved_to_notes(self):
        crew = _crew()
        i = _idea(data_access_model="Read-only aggregation from GitHub issues")
        crew._finalize_idea_pool([i])
        assert i.data_access_model is None
        assert "GitHub issues" in i.data_acquisition_notes

    def test_legacy_labels_alias_onto_the_canonical_vocab(self):
        # The screen used to run against a 10-value SUPERSET, so these passed the pool
        # contract intact and were nulled much later by utils.idea_tags._valid().
        crew = _crew()
        ideas = [_idea(data_access_model="none"),
                 _idea(data_access_model="official"),
                 _idea(data_access_model="not-data-dependent"),
                 _idea(data_access_model="licensed"),
                 _idea(data_access_model="  Public  ")]
        crew._finalize_idea_pool(ideas)
        assert [i.data_access_model for i in ideas] == [
            "public", "public", "public", "paywalled", "public"]

    def test_aliased_none_skips_the_well_known_source_upgrade(self, monkeypatch):
        # 'none' folded to 'public' must NOT enter the restrictive-label upgrade branch
        # (that branch costs an LLM confirm call).
        import nicheiq.utils.public_data_sources as pds
        monkeypatch.setattr(pds, "retrieve_known_sources",
                            lambda *a, **kw: (_ for _ in ()).throw(
                                AssertionError("upgrade branch must not run for an aliased label")))
        crew = _crew()
        i = _idea(data_access_model="none", data_sources=["SAM.gov"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "public"

    def test_canonical_blocked_and_unverified_survive(self):
        crew = _crew()
        ideas = [_idea(data_access_model="blocked"), _idea(data_access_model="unverified")]
        crew._finalize_idea_pool(ideas)
        assert [i.data_access_model for i in ideas] == ["blocked", "unverified"]

    def test_under_evaluated_ideas_get_one_caveat(self):
        crew = _crew()
        ideas = [_idea(),
                 _idea(solution_name="Ghost1", winning_angle=None, novelty_score=None,
                       calibration_notes=None)]
        crew._account_evaluation_completeness(ideas)
        assert len(crew.coverage_caveats) == 1
        assert "Ghost1" in crew.coverage_caveats[0]
        assert "generator self-assessment" in crew.coverage_caveats[0]

    def test_fully_evaluated_pool_no_caveat(self):
        crew = _crew()
        crew._account_evaluation_completeness([_idea(), _idea(solution_name="Y")])
        assert crew.coverage_caveats == []

    def test_pool_contract_emits_no_caveat(self):
        # the accounting moved OUT of _finalize_idea_pool (it ran before the straggler
        # calibration/angle passes and the pivot+merge wave, flagging ideas the catch-up
        # evaluators were about to cover) — the contract now only normalizes fields
        crew = _crew()
        crew._finalize_idea_pool([_idea(solution_name="Ghost1", winning_angle=None,
                                        novelty_score=None, calibration_notes=None)])
        assert crew.coverage_caveats == []


class TestBatchProvenanceReset:
    """D5 (live audit 2026-08): a first-run job with zero regenerations rendered "1 new idea
    from your last request". `generation_batch_ordinal` lives on BaseSolutionIdea — the model
    handed to generator LLMs as structured output — so they fill it in. Only the worker may
    stamp it, and it does so AFTER this contract."""

    def _llm_emitted_idea(self, **kw):
        # Exactly what a generator returns through structured output: a full model payload
        # with the batch-provenance fields fabricated.
        from nicheiq.models.solution_idea import BaseSolutionIdea
        base = dict(
            solution_name="Fabricated", description="d", value_proposition="v",
            pain_points_addressed=["Pain"], core_features=["Feature"],
            target_personas=["Persona"], market_fit_score=0.7,
            technical_feasibility_score=0.8,
            generation_operation_id="op-the-llm-invented",
            generation_batch_ordinal=1,
        )
        base.update(kw)
        return BaseSolutionIdea.model_validate(base)

    def test_first_run_pool_is_null_even_when_the_llm_emits_a_value(self):
        ideas = [self._llm_emitted_idea(),
                 self._llm_emitted_idea(solution_name="Second", generation_batch_ordinal=3)]
        # sanity: the model accepts the fabricated values (ge=1 passes) — the reset is the
        # only thing standing between them and the "NEW IN THIS BATCH" chip.
        assert ideas[0].generation_batch_ordinal == 1
        _crew()._finalize_idea_pool(ideas)
        assert all(i.generation_batch_ordinal is None for i in ideas)
        assert all(i.generation_operation_id is None for i in ideas)

    def test_reset_precedes_the_worker_stamp_in_both_paid_paths(self):
        # Order pin: the worker owns these fields, and both paid paths must stamp AFTER the
        # crew ran (execute_pipeline / execute_seed_pipeline both call the pool contract).
        # Read as text — importing worker.tasks drags the whole runtime into a unit test.
        from pathlib import Path
        src = (Path(__file__).resolve().parents[2] / "worker" / "tasks.py").read_text()
        for name in ("\ndef run_regenerate_ideas", "\ndef run_seed_idea"):
            start = src.index(name)
            body = src[start:src.index("\ndef ", start + 1)]
            assert body.index("execute_") < body.index("generation_batch_ordinal =")


def test_contract_runs_after_reinjection():
    # order pin: the contract must cover coverage-net re-injections (they join LAST)
    src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
    assert src.index("enforce_pain_coverage(") < src.index("_finalize_idea_pool(")


def test_completeness_accounting_runs_after_red_team():
    # order pin: the caveat must be computed AFTER every catch-up evaluator — the straggler
    # calibration/angle passes, the pivot+merge wave, and red-team revisions.
    # `_finalize_evaluator_passes` is the shared tail (extracted from execute_pipeline so it
    # can also compose into `_finalize_seed_tail`) — red-team and the completeness accounting
    # both live there now; the pivot+merge wave stays inside `_backfill_and_demote`, which
    # execute_pipeline calls before handing off to `_finalize_evaluator_passes`.
    tail_src = inspect.getsource(UnifiedSolutionCrew._finalize_evaluator_passes)
    assert tail_src.index("run_red_team_review(") < tail_src.index("_account_evaluation_completeness(")
    pipeline_src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
    assert pipeline_src.index("_backfill_and_demote(") < pipeline_src.index("_finalize_evaluator_passes(")


def test_finalize_seed_tail_never_calls_backfill_and_demote():
    # `_finalize_seed_tail` is the (currently unused) seed entry point: `_sweep_demote` +
    # `_finalize_evaluator_passes`, NOTHING else. `_backfill_and_demote` is portfolio
    # maintenance — it births up to 3 unrelated backfill cells AND its floor guard RESTORES
    # demoted ideas + DELETES their ruled-out entries when <3 remain, so a weak seed's
    # honest demotion must never be routed through it (backfill/pivot/merge/floor-restore
    # all live inside that one method — never calling it rules out all four).
    src = inspect.getsource(UnifiedSolutionCrew._finalize_seed_tail)
    assert "self._backfill_and_demote(" not in src

    crew = _crew()
    calls = []
    crew._sweep_demote = lambda ideas: calls.append(("sweep_demote", ideas))
    crew._finalize_evaluator_passes = (
        lambda refined_solutions, **kw: calls.append(("finalize_evaluator_passes", refined_solutions, kw)))
    crew._backfill_and_demote = lambda *a, **kw: calls.append(("backfill_and_demote", a, kw))

    seed = [_idea(solution_name="Seed")]
    crew._finalize_seed_tail(seed)

    names = [c[0] for c in calls]
    assert names == ["sweep_demote", "finalize_evaluator_passes"]  # backfill_and_demote absent
    assert calls[0][1] is seed
    passed_container, kwargs = calls[1][1], calls[1][2]
    assert list(passed_container.solution_ideas) == seed
    assert kwargs == {"skip_selection": True, "solution_selection": None}
