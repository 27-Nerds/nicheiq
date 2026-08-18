"""The whole class, not the members we happened to find.

A 2026-08-18 audit found model-authored fields cut at guessed character limits before being
handed to an LLM. `technical_approach` (median 522 chars) was cut at 200 immediately before
the critic that *sets* an idea's calibrated scores, so the mechanism was absent from ~96% of
scoring decisions. Cuts landed mid-word with no ellipsis, leaving the model unable to tell
"the mechanism does not cover this" from "the sentence saying so was removed".

Fixing the sites found by hand would leave the next one to a future audit, so this test
enumerates the SET instead:

  * The field vocabulary is DERIVED from the pydantic models at runtime, never hand-typed.
    A hand-typed list is an enumerated vocabulary standing in for a semantic property -- the
    exact mistake that produced the guessed limits -- and every new model field would escape it.
  * The allowlist is keyed on (module, field, limit), not line numbers, so ordinary edits do
    not churn it, and every entry carries a written reason.
  * `test_no_stale_allowlist_entries` fails when an entry stops matching anything, so the list
    cannot rot into a green-forever rubber stamp.

Adding a new bounded slice on a model text field is a deliberate act: either use
`nicheiq.utils.content_security.prompt_field` (a 2000-char runaway backstop that marks what it
cuts) or add an allowlist entry stating why a real bound applies.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest
from pydantic import BaseModel

SRC = Path(__file__).resolve().parents[2] / "src" / "nicheiq"

# (module path relative to src/nicheiq, field, limit) -> why a real bound applies here.
# Every entry is a reason, not a parking space. Reasons fall into four kinds:
#   scraped   - bounding third-party text volume, not a model's own reasoning
#   log       - a logger/exception string; never reaches an LLM or a user
#   identity  - the value is a key; changing its length rebinds stored records
#   contract  - a bound the surrounding prompt or UI slot explicitly states
ALLOWED: dict[tuple[str, str, int], str] = {
    # -- scraped third-party text: volume bounds on other people's content ----------------
    ("tools/reddit_tool.py", "body", 30): "scraped: comment preview for relevance triage",
    ("tools/reddit_tool.py", "title", 50): "scraped: log/preview of a fetched post",
    ("tools/reddit_tool.py", "selftext", 300): "scraped: post-body volume bound",
    ("tools/twitter_tool.py", "text", 50): "scraped: tweet preview in a log line",
    ("tools/youtube_tool.py", "title", 60): "scraped: video title preview",
    ("tools/webshare_client.py", "text", 200): "scraped: proxy response excerpt",
    ("utils/reddit_cache.py", "title", 500): "scraped: cached post title",
    ("utils/reddit_cache.py", "selftext", 40000): "scraped: cache row volume ceiling",
    ("utils/reddit_cache.py", "text", 200): "scraped: cached comment body",
    ("utils/reddit_cache.py", "author", 100): "scraped: username column bound",
    ("utils/reddit_cache.py", "subreddit", 50): "scraped: subreddit column bound",
    ("crews/pain_point_crew.py", "title", 40): "scraped: post title in a log line",
    ("crews/pain_point_crew.py", "title", 50): "scraped: post title in a log line",
    ("utils/validation/thread_validator.py", "title", 50): "scraped: thread title in a log line",
    ("flows/research_flow.py", "title", 50): "scraped: post title in a log line",
    # -- logger / exception strings: never reach an LLM or a user -------------------------
    ("crews/safe_task.py", "name", 60): "log: task name in a degradation warning",
    ("utils/idea_tags.py", "data_access_model", 40): "log: rejected tag value in a warning",
    ("crews/landing_page_crew.py", "memorable_element", 100): "log: logger.info, marked '...'",
    ("crews/landing_page_crew.py", "section_selection_reasoning", 100):
        "log: logger.info, marked '...'",
    ("crews/unified_solution_crew.py", "rationale", 200): "log: seed-identity verdict line",
    ("flows/checkpoint_manager.py", "niche_description", 100):
        "log: niche mismatch error text, marked '...'",
    # -- identity: the value is a key; its length is part of the binding ------------------
    ("flows/checkpoint_manager.py", "niche_description", 50):
        "identity: filesystem slug for the checkpoint dir -- widening it orphans "
        "every existing checkpoint",
    # -- telemetry snapshot: _snapshot_idea_for_revision, read only by search_debug_payload
    ("crews/unified_solution_crew.py", "solution_name", 160): "telemetry: revision snapshot",
    ("crews/unified_solution_crew.py", "value_proposition", 400): "telemetry: revision snapshot",
    ("crews/unified_solution_crew.py", "mechanism_tag", 80):
        "telemetry: revision snapshot (also a controlled tag: 0.14% bind)",
    ("crews/unified_solution_crew.py", "data_source_tag", 80):
        "telemetry: revision snapshot (also a controlled tag: 0.00% bind)",
    ("crews/unified_solution_crew.py", "project_type", 80): "telemetry: controlled vocabulary",
    ("crews/unified_solution_crew.py", "source_pain", 200): "telemetry: revision snapshot",
    ("crews/unified_solution_crew.py", "incumbent_parity", 200): "telemetry: revision snapshot",
    # -- contract: a bound the surrounding prompt or UI slot states outright --------------
}


def _model_str_fields() -> set[str]:
    """Field vocabulary derived from the pydantic models, never hand-typed."""
    import nicheiq.models as models_pkg

    out: set[str] = set()
    for mod in pkgutil.iter_modules(models_pkg.__path__):
        try:
            m = importlib.import_module(f"nicheiq.models.{mod.name}")
        except Exception:  # a model module that cannot import is another test's problem
            continue
        for obj in vars(m).values():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                for name, field in getattr(obj, "model_fields", {}).items():
                    ann = str(field.annotation)
                    if "str" in ann and "ist[" not in ann:
                        out.add(name)
    return out


def _field_read(node: ast.AST) -> str | None:
    """The model field this expression reads, or None if it reads something else."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "getattr" and len(node.args) >= 2 \
                and isinstance(node.args[1], ast.Constant):
            return node.args[1].value
        if node.func.id in ("str", "sanitize_social_content") and node.args:
            return _field_read(node.args[0])
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.BoolOp):  # (getattr(...) or "")
        for v in node.values:
            if (f := _field_read(v)) is not None:
                return f
    return None


def _sites(root: Path | None = None) -> list[tuple[str, int, str, int]]:
    """Every `<model str field>[:CONST]` under `root` (the package by default)."""
    root = root or SRC
    fields = _model_str_fields()
    assert len(fields) > 100, f"model introspection collapsed to {len(fields)} fields"
    found = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for n in ast.walk(tree):
            if not isinstance(n, ast.Subscript) or not isinstance(n.slice, ast.Slice):
                continue
            s = n.slice
            if s.lower is not None or s.step is not None:
                continue
            if not isinstance(s.upper, ast.Constant) or not isinstance(s.upper.value, int):
                continue
            if (f := _field_read(n.value)) in fields:
                found.append((str(path.relative_to(root)), n.lineno, f, s.upper.value))

        # WRITE truncations: `idea.some_field = <expr>[:N]`. The field name is the ASSIGNMENT
        # TARGET, so nothing inside the slice names it and the read-side walk above is blind
        # to the entire class. These are the worse half: they store the cut value, so every
        # downstream reader inherits the damage and no read-side fix can recover it. Missing
        # this class let `idea.differentiation_locus = _hsm(dl)[:300]` (19.8% severed, and one
        # hop from a live prompt) survive a full pass over the read sites.
        for n in ast.walk(tree):
            if not isinstance(n, ast.Assign) or not isinstance(n.value, ast.Subscript):
                continue
            sl = n.value.slice
            if not isinstance(sl, ast.Slice) or sl.lower is not None or sl.step is not None:
                continue
            if not isinstance(sl.upper, ast.Constant) or not isinstance(sl.upper.value, int):
                continue
            for tgt in n.targets:
                if isinstance(tgt, ast.Attribute) and tgt.attr in fields:
                    found.append(
                        (str(path.relative_to(root)), n.lineno, tgt.attr, sl.upper.value))
    return found


def test_no_guessed_character_limits_on_model_text_fields(root: Path | None = None):
    """Every bounded slice on a model text field is justified, or it is a guess."""
    unlisted = [s for s in _sites(root) if (s[0], s[2], s[3]) not in ALLOWED]
    assert not unlisted, (
        "Character limits on model text fields that are not in ALLOWED.\n"
        "A guessed limit silently deletes the tail of a model's own reasoning before another "
        "model reads it. Use nicheiq.utils.content_security.prompt_field (a 2000-char runaway "
        "backstop that MARKS what it cuts), or add an ALLOWED entry saying why a real bound "
        "applies here:\n"
        + "\n".join(f"  {f}:{ln}  {fld}[:{lim}]" for f, ln, fld, lim in unlisted)
    )


def test_no_stale_allowlist_entries():
    """An allowlist that outlives its sites rots into a rubber stamp."""
    live = {(f, fld, lim) for f, _, fld, lim in _sites()}
    stale = sorted(k for k in ALLOWED if k not in live)
    assert not stale, (
        "ALLOWED entries matching nothing — the code moved on; delete them:\n"
        + "\n".join(f"  {f}  {fld}[:{lim}]  ({ALLOWED[(f, fld, lim)]})" for f, fld, lim in stale)
    )


@pytest.mark.parametrize("field,limit", [("technical_approach", 200), ("why_it_works", 240)])
def test_the_scanner_detects_a_newly_added_violation(tmp_path, field, limit):
    """The check must FAIL when a new violating member appears, not merely pass today.

    Enumerating a set is worthless if the enumerator cannot see a fresh member, so this
    synthesises one and asserts it is caught — the mechanical check that would have caught
    the whole 2026-08 class.
    """
    victim = tmp_path / "nicheiq" / "crews"
    victim.mkdir(parents=True)
    (victim / "regression.py").write_text(
        f'def build(idea):\n    return f"- mech: {{idea.{field}[:{limit}]}}"\n'
    )
    root = tmp_path / "nicheiq"

    assert ("crews/regression.py", 2, field, limit) in _sites(root), (
        "the scanner cannot see a newly added guessed limit — it would certify a "
        "regression it is blind to"
    )
    with pytest.raises(AssertionError, match="not in ALLOWED"):
        test_no_guessed_character_limits_on_model_text_fields(root=root)
