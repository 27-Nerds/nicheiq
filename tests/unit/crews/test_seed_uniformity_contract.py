"""Phase 9 (E2E) "uniformity contract" — plans/eager-meandering-feather.md Verification section:
"seed's model_dump().keys() == pool idea's; every score/tag/angle/dev/payability/route/red-team
field populated".

HONEST SCOPE NOTE: no fixture CHECKPOINT with a full real (LLM-mocked) pipeline run exists in
this repo (checked tests/fixtures/ and tests/unit/flows/ — nothing resembling a post-Stage-7
checkpoint with birthed pool ideas). Building one would mean actually running the 16-stage flow
end to end with every LLM call mocked, which is not "cheap" in the sense the task asked for. Per
the task's own explicit fallback ("if a suitable fixture doesn't exist, assert parity against a
constructed pool idea instead and say so"), this asserts parity against a CONSTRUCTED pool idea.

Both the "pool" reference and the "seed" idea below are generated from `BaseSolutionIdea`'s OWN
field schema (not a hand-curated subset like test_blank_field_repair.py's `_full_idea()`), so the
key-set/non-blank comparison can't silently drift out of sync with the model as fields are added.
Because both are instances of the SAME Pydantic class, `model_dump().keys()` equality is a
trivially-true fact about the type system, not a real regression guard by itself — the meaningful
assertions here are (a) the filler can actually populate every field the model defines without
tripping validation, and (b) `execute_seed_pipeline` hands back the birthed idea AS-IS (never a
stripped-down/partial stand-in), so a caller comparing a real seed output against a real pool idea
gets the same non-blank field profile.

This does NOT exercise the real LLM-touching birth/scoring passes (`_one_sample`,
`tournament_refine_cell_v4`, `_score_cell_winner`, `_score_wave`, `_finalize_seed_tail`) — those
already have dedicated wiring/behavior coverage in test_seed_pipeline.py, test_per_cell_tournament.py,
test_blank_field_repair.py, and test_backfill_demote.py. Whether those REAL passes leave a field
blank for some code path is exactly what that existing coverage guards; this file only guards the
orchestration-level contract that execute_seed_pipeline's return value is a full, unstripped idea.
"""
import typing
from types import SimpleNamespace

from pydantic import BaseModel

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import SeedRequest, UnifiedSolutionCrew
from nicheiq.models.solution_idea import BaseSolutionIdea


def _fill(annotation):
    """Generic non-None placeholder generator driven by the field's own type annotation —
    deliberately NOT a hand-curated field list, so coverage can't silently drift from the model
    as fields are added/renamed."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is typing.Union:  # Optional[X] == Union[X, None]
        non_none = [a for a in args if a is not type(None)]
        return _fill(non_none[0]) if non_none else None
    if origin in (list, typing.List):
        inner = args[0] if args else str
        return [_fill(inner)]
    if origin is dict or origin is typing.Dict:
        return {}
    if origin is typing.Literal:
        return args[0]
    if annotation is str:
        return "value"
    if annotation is int:
        return 1
    if annotation is float:
        return 0.5
    if annotation is bool:
        return True
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _full_instance(annotation)
    return None


def _full_instance(model_cls, **overrides):
    kwargs = {}
    for name, info in model_cls.model_fields.items():
        kwargs[name] = overrides[name] if name in overrides else _fill(info.annotation)
    return model_cls(**kwargs)


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew.allowed_project_types = None
    crew.search_tool = None
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    return crew


class TestSeedUniformityContract:
    def test_every_base_solution_idea_field_can_be_populated(self):
        # Sanity pin for the filler itself: a schema-driven instance passes the model's own
        # validation (nothing silently rejected) and has NOTHING left blank.
        idea = _full_instance(BaseSolutionIdea, solution_name="Pool Idea")
        for name in BaseSolutionIdea.model_fields:
            assert getattr(idea, name) is not None, f"{name} was left blank by the filler"

    def test_seed_idea_matches_pool_idea_key_set_and_execute_seed_pipeline_returns_it_unstripped(
        self, monkeypatch,
    ):
        pool_idea = _full_instance(BaseSolutionIdea, solution_name="Pool Idea")
        seed_idea = _full_instance(
            BaseSolutionIdea, solution_name="Seed Idea", source_frame="user_seed",
        )

        crew = _crew()
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **kw: seed_idea)
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                             lambda self, u: None, raising=False)

        result = crew.execute_seed_pipeline(SeedRequest(seed_text="an idea", dispatch_id="d1"))

        # Uniformity: same model, same full key set (both are BaseSolutionIdea instances).
        assert type(result) is type(pool_idea)
        assert set(result.model_dump().keys()) == set(pool_idea.model_dump().keys())
        # Every field the pool idea carries non-blank, the seed also carries non-blank.
        for name, pool_value in pool_idea.model_dump().items():
            if pool_value is not None:
                assert result.model_dump()[name] is not None, f"{name} is blank on the seed idea"
        # execute_seed_pipeline hands back the birthed idea AS-IS — never wraps/strips it.
        assert result is seed_idea
