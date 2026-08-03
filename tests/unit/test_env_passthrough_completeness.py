"""
Guards S0.1 (docs/FLOW_WEAKNESS_FIX_PLAN_2026-08.md, Step 0): every downgrade-only
score-capping / kill-switch setting declared in settings.py must be piped through as an
env-var passthrough on the WORKER service in docker-compose.prod.yml. Without this, a
prod deploy silently falls back to the Python default in settings.py regardless of what
the host's .env sets — exactly the class of bug this plan's config work is closing.

Keyed off settings.py (the source of truth for what a setting IS and its default),
NOT .env.example — .env.example carries ~14 dead ENABLE_* keys for settings that no
longer exist in code, so parsing it would produce false "missing" and false "present"
results.

Plain text parsing only (regex over the two files) — no new deps, no import of
nicheiq.config.settings (importing it requires all required API keys to be present).
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / "src" / "nicheiq" / "config" / "settings.py"
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose.prod.yml"

# settings.py fields matching this pattern, plus every enable_* flag, plus the
# EXPLICIT_NAMES below, form the S0.1 "kill-switch-class" list. Matches Settings-class
# field declarations of the form `    <name>: <bool|float|int> = Field(`.
_FIELD_RE = re.compile(r"^ {4}([a-z][a-z0-9_]*): (?:bool|float|int) = Field\(", re.MULTILINE)

# Named in the plan text but not matched by the *_cap/_ceiling/_clamp/enable_ suffix
# patterns above (demotion_market_fit_max ends in _max; payability_low_threshold ends
# in _threshold; market_awareness_serper_budget/seo_fallback_prefilter/tournament_rounds
# don't follow the cap/ceiling/clamp naming at all).
_EXPLICIT_NAMES = {
    "demotion_market_fit_max",
    "payability_low_threshold",
    "market_awareness_serper_budget",
    "seo_fallback_prefilter",
    "tournament_rounds",
}

# Matched by *_cap but deliberately OUT of scope for this gate: not part of the
# downgrade-only score-capping family the plan is about.
_EXCLUDED_NAMES = {
    "divergent_pool_cap",  # concept-pool size ceiling, already passed through separately
    "token_soft_cap",  # cost-telemetry soft cap (token_soft_cap_enabled defaults False)
}


def _settings_source() -> str:
    return SETTINGS_PATH.read_text()


def _worker_block() -> str:
    """Return just the `worker:` service block from the prod compose file. Settings
    must be passed through THERE specifically — the `api` block is the Node backend
    and never reads these, so a var present only in `api` must still fail this check."""
    text = COMPOSE_PATH.read_text()
    start = text.index("\n  worker:\n")
    rest = text[start + 1:]
    # Next top-level (2-space-indented) service/volume/network key ends the block.
    end_match = re.search(r"\n {2}[a-zA-Z][\w-]*:\n", rest[1:])
    return rest[: end_match.start() + 1] if end_match else rest


def _kill_switch_names() -> list[str]:
    names = set(_FIELD_RE.findall(_settings_source()))
    matched = {
        name
        for name in names
        if name.endswith(("_cap", "_ceiling", "_clamp"))
        or name.startswith("enable_")
        or name in _EXPLICIT_NAMES
    }
    return sorted(matched - _EXCLUDED_NAMES)


def test_kill_switch_parser_found_expected_settings():
    """Sanity check the regex/exclusion logic still matches a reasonable set (guards
    against a settings.py refactor silently breaking the parser and emptying the
    parametrized test below)."""
    names = _kill_switch_names()
    assert len(names) >= 20
    assert "demotion_market_fit_max" in names
    assert "payability_low_threshold" in names
    assert "market_awareness_serper_budget" in names
    assert "seo_fallback_prefilter" in names
    assert "tournament_rounds" in names
    assert "enable_per_cell_tournament" in names
    assert "divergent_pool_cap" not in names
    assert "token_soft_cap" not in names


@pytest.mark.parametrize("name", _kill_switch_names())
def test_kill_switch_setting_passed_through_to_worker(name):
    env_var = name.upper()
    worker_block = _worker_block()
    assert f"{env_var}:" in worker_block, (
        f"settings.py field '{name}' (env {env_var}) is missing an env passthrough in "
        f"the worker service block of docker-compose.prod.yml — a prod deploy would "
        f"silently fall back to the Python default in settings.py regardless of what "
        f".env sets."
    )
