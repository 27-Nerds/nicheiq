"""Loader for tests/fixtures/idea_check_056b2c68.json — the first live "Check my idea"
run, trimmed into a committed regression oracle for the idea_validation block.

`state_from_fixture` rebuilds the same SimpleNamespace state shape the block tests use,
so `build_idea_validation_block(state, "validate_idea")` reconstructs the live block.
`expected_block_v1` is the block exactly as the live run shipped it (pre-quality-pass).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "idea_check_056b2c68.json"
)

_CACHE: dict | None = None


def load_fixture() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(FIXTURE_PATH.read_text())
    return deepcopy(_CACHE)


def state_from_fixture(fx: dict | None = None) -> SimpleNamespace:
    fx = fx or load_fixture()
    m = fx["metadata"]
    return SimpleNamespace(
        user_idea_text=m["user_idea_text"],
        user_idea_brief=m["user_idea_brief"],
        user_idea_inferred_fields=m["user_idea_inferred_fields"],
        user_idea_pivot=m["user_idea_pivot"],
        user_idea_identity_terms=m["user_idea_identity_terms"],
        user_idea_brief_parity=None,
        idea_generation=SimpleNamespace(
            solution_ideas=[SimpleNamespace(**i) for i in fx["ideas"]]),
        pain_point_analysis=SimpleNamespace(
            pain_points=[SimpleNamespace(**p) for p in fx["pains"]]),
        social_content=SimpleNamespace(
            reddit_posts=[SimpleNamespace(**p) for p in fx["posts_reddit"]],
            generic_posts=[SimpleNamespace(**p) for p in fx["posts_generic"]]),
        niche_context=SimpleNamespace(**fx["niche_context"]),
        niche_incumbent_map=m["niche_incumbent_map"],
        idea_ruled_out=m["idea_ruled_out"],
    )


def expected_block_v1() -> dict:
    return load_fixture()["expected_block_v1"]
