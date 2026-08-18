"""Step 0 (search-arm attribution ledger) + Step 1 (overlap-group membership maintenance).

Step 0 is instrumentation with ZERO behaviour change: the new ledger records
{idea -> queries -> snippet ids -> finding} for the arms that write `incumbent_parity`, but
deliberately never touches `_ma_serper_calls`, the counter that GATES search spend. The
`TestGatingCounterUntouched` class pins that separation, and
`TestRoutingIntoTheGatingCounterWouldChangeBehaviour` demonstrates WHY the gating counter was
left alone rather than reused.

Step 1 fixes a live defect: an in-place idea replacement renamed the idea but left
`self.overlap_groups` naming the dead predecessor, and every consumer hides a group with a
non-visible member. `TestReplacementSiteProperty` asserts the PROPERTY ("no stored group names
an idea absent from the pool") over the SET of replacement sites, and
`test_every_in_place_replacement_site_is_accounted_for` scans the source so a replacement site
added later fails here.
"""

import ast
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import (
    _NICHE_LABEL_CATEGORY_NOUNS,
    _NICHE_LABEL_DETERMINERS,
    UnifiedSolutionCrew,
    _capability_discovery_query,
    _niche_query_label,
)
from nicheiq.models.solution_idea import BaseSolutionIdea

CREW_SRC = Path(UnifiedSolutionCrew.__module__.replace(".", "/") + ".py")
CREW_PATH = Path(__file__).resolve().parents[3] / "src" / CREW_SRC
RED_TEAM_PATH = (Path(__file__).resolve().parents[3] / "src" / "nicheiq" / "utils"
                 / "red_team_review.py")


def _crew(**extra):
    """Bare crew, mirroring test_market_awareness._crew — the instrumentation helpers are
    getattr-defensive precisely so they work on an instance that never ran __init__."""
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.checkpoint_mgr = None
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _idea(name="Idea", mf=0.5, **kw):
    base = dict(
        solution_name=name, market_fit_score=mf, technical_feasibility_score=0.6,
        novelty_score=0.5, seo_scalability_score=0.5, build_feasibility_score=0.8,
        solo_dev_feasibility=0.7, incumbent_parity=None, winning_angle=None,
        candidate_status="active", source_pain=None, source_segment=None,
        source_frame="pain", mechanism_tag=None, data_source_tag=None, project_type=None,
        value_proposition="does a thing", target_personas=None, idea_id=None,
        idea_revision=1, pain_points_addressed=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _real_idea(name, **kw):
    """A REAL BaseSolutionIdea — the red-team path runs `carry_forward_idea_fields` and
    `BaseSolutionIdea.model_validate` over it, which a SimpleNamespace cannot survive."""
    base = dict(
        solution_name=name, description="d", value_proposition="vp",
        pain_points_addressed=["p"], core_features=["f"], target_personas=["persona"],
        market_fit_score=0.4, technical_feasibility_score=0.5, novelty_score=0.5,
        seo_scalability_score=0.5, build_feasibility_score=0.7, solo_dev_feasibility=0.7,
        source_frame="pain",
    )
    base.update(kw)
    return BaseSolutionIdea(**base)


def _group(*names, shared="one product"):
    return {"idea_names": list(names), "shared_product": shared}


def _pool_names(ideas):
    return {(getattr(i, "solution_name", "") or "").strip().lower() for i in ideas}


def assert_no_dead_group_member(crew, ideas):
    """THE Step-1 PROPERTY: no stored group names an idea absent from the pool."""
    pool = _pool_names(ideas)
    for g in (getattr(crew, "overlap_groups", None) or []):
        for member in g.get("idea_names") or []:
            assert (member or "").strip().lower() in pool, (
                f"overlap group {g!r} names '{member}', absent from pool {sorted(pool)}")


# ===========================================================================
# Step 1 — group membership maintenance
# ===========================================================================

class TestRenameHelper:
    def test_renames_member_and_records_successor(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
        assert crew._rename_overlap_group_member("Beta", "Beta Prime",
                                                 origin="red_team_revision") == 1
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta Prime", "Gamma"]
        assert crew.overlap_group_successors["Beta"] == {
            "successor": "Beta Prime", "rebuild_origin": "red_team_revision",
            "groups_updated": 1}

    def test_match_is_case_and_whitespace_insensitive(self):
        crew = _crew(overlap_groups=[_group("Alpha", "  bEtA  ")])
        assert crew._rename_overlap_group_member("Beta", "Beta Prime", origin="o") == 1
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta Prime"]

    def test_renames_the_same_member_in_every_group(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta"), _group("Beta", "Gamma")])
        assert crew._rename_overlap_group_member("Beta", "Beta Prime", origin="o") == 2
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta Prime"]
        assert crew.overlap_groups[1]["idea_names"] == ["Beta Prime", "Gamma"]

    def test_unchanged_name_is_a_noop(self):
        """Makes the helper safe to call from a pure name-collision dedup."""
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        assert crew._rename_overlap_group_member("Beta", "Beta", origin="o") == 0
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta"]
        assert getattr(crew, "overlap_group_successors", {}) == {}

    def test_missing_names_are_noops(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        assert crew._rename_overlap_group_member(None, "X", origin="o") == 0
        assert crew._rename_overlap_group_member("Alpha", "", origin="o") == 0
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta"]

    def test_rename_colliding_with_existing_member_dissolves_the_group(self):
        """A group needs 2+ SEPARATE visible ideas to mean anything — same <2 rule as the
        pivot-precedence resolution in _backfill_and_demote."""
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        assert crew._rename_overlap_group_member("Beta", "Alpha", origin="o") == 1
        assert crew.overlap_groups == []

    def test_collision_in_a_larger_group_keeps_it_with_fewer_members(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
        assert crew._rename_overlap_group_member("Beta", "Gamma", origin="o") == 1
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Gamma"]

    def test_groups_without_the_member_are_untouched(self):
        other = _group("Delta", "Epsilon")
        crew = _crew(overlap_groups=[_group("Alpha", "Beta"), other])
        crew._rename_overlap_group_member("Beta", "Beta Prime", origin="o")
        assert crew.overlap_groups[1] is other

    def test_never_raises_on_a_malformed_group(self):
        crew = _crew(overlap_groups=[{"shared_product": "x"}, _group("Alpha", "Beta")])
        assert crew._rename_overlap_group_member("Beta", "Beta Prime", origin="o") == 1

    def test_successor_recorded_even_when_no_group_holds_the_member(self):
        """The successor map is also the reposition-vs-refine measurement, so it records
        every replacement, not only the group-affecting ones."""
        crew = _crew(overlap_groups=[])
        assert crew._rename_overlap_group_member("A", "B", origin="parity_pivot") == 0
        assert crew.overlap_group_successors["A"]["rebuild_origin"] == "parity_pivot"
        assert crew.overlap_group_successors["A"]["groups_updated"] == 0


class TestTheFourStates:
    """The brief's enumeration: replaced / dropped / demoted / unchanged."""

    def test_replaced_renames_membership_and_preserves_cardinality(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        ideas = [_idea("Alpha"), _idea("Beta")]
        crew._commit_idea_replacement(ideas[1], _idea("Beta Prime"), origin="o")
        ideas[1] = _idea("Beta Prime")
        assert len(crew.overlap_groups[0]["idea_names"]) == 2
        assert_no_dead_group_member(crew, ideas)

    def test_dropped_member_is_not_resurrected_and_stays_prunable(self):
        """A genuinely gone member must NOT be renamed into existence — the consumers'
        visibility filter is the correct response, and the group stays prunable."""
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        ideas = [_idea("Alpha")]  # Beta dropped outright, no successor
        assert getattr(crew, "overlap_group_successors", {}) == {}
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta"]
        # Still prunable by the caller / renderer:
        crew.overlap_groups = [
            g for g in crew.overlap_groups
            if all((m or "").strip().lower() in _pool_names(ideas)
                   for m in g["idea_names"])]
        assert crew.overlap_groups == []

    def test_demoted_member_keeps_its_membership(self):
        """A demoted/absorbed idea is still IN the pool; the variant-merge path depends on
        membership surviving so it can remove the group itself."""
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        ideas = [_idea("Alpha"), _idea("Beta", candidate_status="absorbed")]
        assert crew.overlap_groups[0]["idea_names"] == ["Alpha", "Beta"]
        assert_no_dead_group_member(crew, ideas)

    def test_unchanged_is_a_noop(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta")])
        before = [dict(g) for g in crew.overlap_groups]
        crew._commit_idea_replacement(_idea("Beta"), _idea("Beta"), origin="o")
        assert crew.overlap_groups == before


# ---------------------------------------------------------------------------
# The property, enumerated over the SET of replacement sites
# ---------------------------------------------------------------------------

def _stub_score_wave_clearing_parity(crew):
    def _stamp(wave):
        for rev in wave:
            rev.incumbent_parity = "none found"
            rev.novelty_score = 0.9
            rev.seo_scalability_score = 0.9
            rev.market_fit_score = 0.9
            rev.technical_feasibility_score = 0.9
    crew._score_wave = _stamp


class _FakeRevision:
    def __init__(self, **kw):
        self._d = kw

    def model_dump(self):
        return dict(self._d)


def _revision_fields(name):
    return dict(
        solution_name=name, value_proposition="a repositioned wedge",
        description="attacks the finding", core_features=["gap workflow"],
        conventional_approach="", innovation_angle="", why_it_works="",
        technical_approach="", data_access_model="public",
        market_fit_score=0.9, technical_feasibility_score=0.9,
        build_feasibility_score=0.8, data_feasibility_score=0.8,
        programmatic_seo_opportunity="",
    )


def _run_red_team_replacement(crew, ideas, new_name="Beta Prime"):
    """Drive the REAL red-team replacement site end to end (LLM + scoring stubbed)."""
    from nicheiq.utils import red_team_review as rt

    orig = ideas[1]
    refined = SimpleNamespace(solution_ideas=ideas)
    _stub_score_wave_clearing_parity(crew)
    crew._repair_blank_idea_fields = lambda *a, **k: None
    result = SimpleNamespace(verdict="weakened", uplift="", findings=[])
    # `LLMService` is imported INSIDE the function, so the patch target is its home module.
    with patch("nicheiq.utils.llm_service.LLMService.invoke_structured",
               return_value=(_FakeRevision(**_revision_fields(new_name)), None)):
        return rt._attempt_red_team_revision(crew, refined, orig, result, "evidence")


def _run_pivot_replacement(crew, ideas, new_name="Beta Prime"):
    """Drive the REAL `_parity_pivot_revisions` replacement site end to end."""
    refined = SimpleNamespace(solution_ideas=ideas)
    _stub_score_wave_clearing_parity(crew)
    crew._incumbent_rows = []
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(_FakeRevision(**_revision_fields(new_name)), None)):
        return crew._parity_pivot_revisions(refined)


class TestReplacementSiteProperty:
    """The property is asserted per replacement SITE, driving the real production code."""

    def test_red_team_revision_site_keeps_groups_alive(self):
        """The live defect: run 8500b97d's group still names 'Reclaim Timeline Forensics'
        after this site replaced it with 'Reclaim Packet QA'."""
        ideas = [_real_idea("Search-to-Profile Alignment Sentinel"),
                 _real_idea("Reclaim Timeline Forensics"),
                 _real_idea("CitationGap Camden")]
        crew = _crew(overlap_groups=[_group("Search-to-Profile Alignment Sentinel",
                                            "CitationGap Camden",
                                            "Reclaim Timeline Forensics",
                                            shared="GBP repair & ownership recovery suite")])
        assert _run_red_team_replacement(crew, ideas, "Reclaim Packet QA") is True
        assert ideas[1].solution_name == "Reclaim Packet QA"
        assert ideas[1].rebuild_origin == "red_team_revision"
        assert_no_dead_group_member(crew, ideas)
        assert "Reclaim Packet QA" in crew.overlap_groups[0]["idea_names"]
        assert "Reclaim Timeline Forensics" not in crew.overlap_groups[0]["idea_names"]
        # The group still describes 3 separate visible ideas, so it is still showable.
        assert len(crew.overlap_groups[0]["idea_names"]) == 3

    def test_parity_pivot_site_keeps_groups_alive(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 3)
        ideas = [_idea("Alpha"), _idea("Beta", incumbent_parity="shipped by Acme"),
                 _idea("Gamma")]
        crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
        attempted, accepted = _run_pivot_replacement(crew, ideas)
        assert (attempted, accepted) == (1, 1)
        assert ideas[1].solution_name == "Beta Prime"
        assert_no_dead_group_member(crew, ideas)

    def test_backfill_pivot_site_keeps_groups_alive(self):
        """`_backfill_and_demote`'s pivot accept already strips pivot candidates from every
        group via pivot precedence, so the property holds there for a second reason. Asserted
        anyway: the site now maintains membership itself instead of depending on a rule 100
        lines away."""
        ideas = [_idea("Alpha"), _idea("Beta"), _idea("Gamma")]
        crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
        rev = _idea("Beta Prime")
        crew._commit_idea_replacement(ideas[1], rev, origin="parity_pivot")
        ideas[1] = rev
        assert_no_dead_group_member(crew, ideas)

    def test_property_holds_for_every_wired_site(self):
        """One assertion over the SET, so a site that stops maintaining membership fails
        here even if its own dedicated test above is deleted."""
        cases = []

        def _red_team_case():
            ideas = [_real_idea("Alpha"), _real_idea("Beta"), _real_idea("Gamma")]
            crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
            _run_red_team_replacement(crew, ideas)
            return crew, ideas

        def _pivot_case():
            ideas = [_idea("Alpha"), _idea("Beta", incumbent_parity="shipped by Acme"),
                     _idea("Gamma")]
            crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
            with patch.object(settings, "parity_pivot_max_revisions", 3):
                _run_pivot_replacement(crew, ideas)
            return crew, ideas

        def _backfill_case():
            ideas = [_idea("Alpha"), _idea("Beta"), _idea("Gamma")]
            crew = _crew(overlap_groups=[_group("Alpha", "Beta", "Gamma")])
            rev = _idea("Beta Prime")
            crew._commit_idea_replacement(ideas[1], rev, origin="parity_pivot")
            ideas[1] = rev
            return crew, ideas

        cases = [("red_team_review.py:_attempt_red_team_revision", _red_team_case),
                 ("unified_solution_crew.py:_parity_pivot_revisions", _pivot_case),
                 ("unified_solution_crew.py:_backfill_and_demote", _backfill_case)]
        for label, build in cases:
            crew, ideas = build()
            pool = _pool_names(ideas)
            for g in (crew.overlap_groups or []):
                for m in g["idea_names"]:
                    assert (m or "").strip().lower() in pool, (
                        f"{label}: group {g!r} names '{m}' absent from pool {sorted(pool)}")


# ---------------------------------------------------------------------------
# Source scan: a NEW replacement site must fail something
# ---------------------------------------------------------------------------

# In-place pool assignment: `<something>[<index-ish>] = <name>`.
_INPLACE_RE = re.compile(r"^\s*(?:ideas|solution_ideas)\[[^\]]+\]\s*=\s*\S")

# Sites that provably need no membership maintenance, each with the reason it is exempt.
_EXEMPT_SITES = {
    "_dedup_tournament_winners": (
        "Replaces an idea with a NAME-COLLIDING duplicate, so old == new and the rename is a "
        "no-op by construction; it is also a @staticmethod (no `self`) that runs during the "
        "tournament-winner union, strictly BEFORE `_group_variant_overlaps` first stamps "
        "`overlap_groups` inside `_backfill_and_demote`, so there are provably no groups yet."),
    "_enforce_diversity_caps": (
        "DROPS ideas (`ideas[:] = <filtered>`), never renames one. The DROPPED state must stay "
        "prunable rather than renamed — resurrecting a gone member would fabricate a group."),
}


def _owning_functions(path):
    """{lineno -> owning function name} for every line, where "owning" means the function or
    METHOD that contains it, not a nested closure.

    Resolved with `ast` rather than an indentation walk: `ideas[idx] = rev` in
    `_backfill_and_demote` sits after a `_merge_gen` closure and
    `_attempt_red_team_revision`'s site sits after a `_comp` closure, and both a
    nearest-`def` and an outermost-`def` regex walk blame the wrong scope for one of them."""
    tree = ast.parse(path.read_text())
    owner: dict[int, str] = {}

    def _claim(node, name):
        for lineno in range(node.lineno, (node.end_lineno or node.lineno) + 1):
            owner.setdefault(lineno, name)

    def _walk(node, name=None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # A method/function claims its whole span; nested closures inherit the name
                # via setdefault, so the OUTER function stays the owner.
                _claim(child, name or child.name)
                _walk(child, name or child.name)
            elif isinstance(child, ast.ClassDef):
                _walk(child, None)          # methods below become owners themselves
            else:
                _walk(child, name)

    _walk(tree)
    return owner


def _find_inplace_sites(path):
    lines = path.read_text().splitlines()
    owner = _owning_functions(path)
    return [(i + 1, owner.get(i + 1, "<module>"), lines[i].strip())
            for i, line in enumerate(lines) if _INPLACE_RE.match(line)]


class TestReplacementSiteInventory:
    def test_the_scanner_finds_the_known_sites(self):
        """Guards the scanner itself: a regex that matches nothing would make the test below
        vacuously green."""
        found = {fn for _, fn, _ in _find_inplace_sites(CREW_PATH)}
        assert {"_dedup_tournament_winners", "_parity_pivot_revisions",
                "_backfill_and_demote", "_enforce_diversity_caps"} <= found, found
        rt_found = {fn for _, fn, _ in _find_inplace_sites(RED_TEAM_PATH)}
        assert "_attempt_red_team_revision" in rt_found, rt_found

    @pytest.mark.parametrize("path", [CREW_PATH, RED_TEAM_PATH],
                             ids=["unified_solution_crew", "red_team_review"])
    def test_every_in_place_replacement_site_is_accounted_for(self, path):
        """Every in-place pool replacement must either maintain overlap-group membership via
        `_commit_idea_replacement` or be on `_EXEMPT_SITES` with a stated reason.

        A replacement site added later fails HERE, which is the point: the behavioural tests
        above can only cover sites someone remembered to add."""
        lines = path.read_text().splitlines()
        offenders = []
        for lineno, fn, text in _find_inplace_sites(path):
            if fn in _EXEMPT_SITES:
                continue
            window = "\n".join(lines[max(0, lineno - 4): lineno + 12])
            if "_commit_idea_replacement" not in window:
                offenders.append(f"{path.name}:{lineno} in {fn}(): {text}")
        assert not offenders, (
            "in-place idea replacement without overlap-group membership maintenance "
            "(call `_commit_idea_replacement(orig, rev, origin=...)`, or add the site to "
            "_EXEMPT_SITES with the reason it needs none):\n" + "\n".join(offenders))


# ===========================================================================
# Step 0 — search-arm attribution ledger
# ===========================================================================

class TestSearchArmLedger:
    def test_records_arm_idea_query_and_snippet_identity(self):
        crew = _crew()
        crew._record_search_arm("parity_direct", "acme invoice audit", "RESULT TEXT",
                                idea="Alpha", counted=False)
        row, = crew.search_arm_log
        assert row["arm"] == "parity_direct"
        assert row["idea"] == "Alpha"
        assert row["query"] == "acme invoice audit"
        assert row["counted"] is False
        assert row["empty"] is False
        assert row["snippet"]["chars"] == len("RESULT TEXT")
        assert row["snippet"]["excerpt"] == "RESULT TEXT"
        assert len(row["snippet"]["sha256"]) == 16
        assert crew.search_arm_spend == {"parity_direct": 1}

    def test_snippet_text_is_hashed_not_stored(self):
        """Storage decision: identity + bounded excerpt, never the full snippet."""
        crew = _crew()
        big = "x" * 5000
        crew._record_search_arm("parity_direct", "q", big)
        snip = crew.search_arm_log[0]["snippet"]
        assert snip["chars"] == 5000
        assert len(snip["excerpt"]) == UnifiedSolutionCrew._SNIPPET_EXCERPT_CHARS
        assert big not in repr(crew.search_arm_log)

    def test_identical_snippets_share_a_fingerprint(self):
        """What makes cache/arm overlap derivable from the ledger."""
        crew = _crew()
        crew._record_search_arm("parity_direct", "q1", "SAME")
        crew._record_search_arm("toolbelt", "q2", "SAME")
        crew._record_search_arm("toolbelt", "q3", "OTHER")
        a, b, c = crew.search_arm_log
        assert a["snippet"]["sha256"] == b["snippet"]["sha256"]
        assert c["snippet"]["sha256"] != a["snippet"]["sha256"]

    def test_empty_result_is_recorded_as_spend_with_no_snippet(self):
        crew = _crew()
        crew._record_search_arm("adjacent_base", "q", "")
        row, = crew.search_arm_log
        assert row["empty"] is True and "snippet" not in row
        assert crew.search_arm_spend == {"adjacent_base": 1}

    def test_findings_close_the_query_to_finding_chain(self):
        crew = _crew()
        crew._record_search_arm_finding("parity_direct", "Alpha", "shipped by Acme: x")
        assert crew.search_arm_findings == [
            {"arm": "parity_direct", "idea": "Alpha", "finding": "shipped by Acme: x"}]

    def test_instrumentation_never_raises(self):
        crew = _crew()
        crew._record_search_arm("arm", "q", object())          # unhashable-ish result
        crew._record_search_arm_finding("arm", object(), object())
        assert len(crew.search_arm_log) == 1

    def test_reset_clears_every_ledger(self):
        crew = _crew()
        crew._record_search_arm("a", "q", "r")
        crew._record_search_arm_finding("a", "i", "f")
        crew.idea_revision_log = [{"x": 1}]
        crew.overlap_group_successors = {"a": {}}
        crew._reset_search_arm_instrumentation()
        assert crew.search_arm_log == [] and crew.search_arm_spend == {}
        assert crew.search_arm_findings == [] and crew.idea_revision_log == []
        assert crew.overlap_group_successors == {}


class TestPerArmAttributionIsDerivable:
    def test_parity_probe_ledger_attributes_each_query_and_finding_to_its_idea(self,
                                                                              monkeypatch):
        """The wall Step 0 exists to close: run the REAL parity probe with a stubbed search
        tool and recover {idea -> queries -> snippet ids -> finding} from the artifact."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 0)
        ideas = [_idea("Alpha", mf=0.7), _idea("Beta", mf=0.6)]

        class _Tool:
            def __init__(self):
                self._cache = {}

            def run(self, search_query):
                return f"RESULTS FOR {search_query}"

        crew = _crew(
            search_tool=_Tool(),
            niche_context=SimpleNamespace(niche_description="london plumbers"),
            _incumbent_rows=[],
            audience_mapping=None,
            coverage_caveats=[],
        )
        crew._probe_incumbents = lambda: ""
        crew._capability_phrases = lambda top: {}
        crew._mechanism_keywords = lambda idea, **kw: "invoice audit"
        crew._probe_adjacent_markets = lambda top: ([], 0)
        crew._probe_toolbelt_free_bundle = lambda top: ([], 0)
        crew._run_parallel = lambda *a, **k: []
        crew._record_divergent_usage = lambda u: None
        crew._validate_idea_caps = lambda idea: []

        findings = SimpleNamespace(findings=[
            SimpleNamespace(idea_name="Alpha", covered_by="Acme", evidence="ships it",
                            parity="shipped"),
            SimpleNamespace(idea_name="Beta", covered_by="", evidence="", parity="none"),
        ])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(findings, None)):
            crew._probe_mechanism_parity(ideas)

        # Spend is now visible for an arm that reported nothing before.
        assert crew.search_arm_spend["parity_direct"] == 2
        by_idea = {}
        for row in crew.search_arm_log:
            assert row["arm"] == "parity_direct"
            by_idea.setdefault(row["idea"], []).append(row)
        assert set(by_idea) == {"Alpha", "Beta"}
        # Attribution: the query text and the snippet that came back for THAT idea.
        alpha_row, = by_idea["Alpha"]
        assert "invoice audit" in alpha_row["query"]
        assert alpha_row["snippet"]["excerpt"].startswith("RESULTS FOR")
        # ...through to the finding the arm produced for it.
        finding_by_idea = {f["idea"]: f["finding"] for f in crew.search_arm_findings}
        assert finding_by_idea["Alpha"].startswith("shipped by Acme")
        assert finding_by_idea["Beta"] == "none found"
        assert ideas[0].incumbent_parity == finding_by_idea["Alpha"]

    def test_uncounted_arms_are_marked_uncounted(self, monkeypatch):
        """`counted` is what makes the under-report visible: gated_spend < total_spend."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 0)
        crew = _crew()
        crew._record_search_arm("parity_direct", "q", "r", counted=False)
        crew._record_search_arm("adjacent_base", "q2", "r", counted=False)
        crew._record_search_arm("toolbelt", "q3", "r", counted=True)
        payload = crew.search_debug_payload()
        assert payload["total_spend"] == 3
        assert payload["gated_spend"] == 1


class TestDebugPayload:
    def test_payload_carries_every_ledger(self):
        crew = _crew(overlap_groups=[_group("Alpha", "Beta Prime")])
        crew._record_search_arm("parity_direct", "q", "r", idea="Beta", counted=False)
        crew._record_search_arm_finding("parity_direct", "Beta", "shipped by Acme")
        crew._commit_idea_replacement(_idea("Beta"), _idea("Beta Prime"),
                                      origin="red_team_revision")
        p = crew.search_debug_payload()
        assert p["search_arm_spend"] == {"parity_direct": 1}
        assert p["ma_serper_calls"] == 0
        assert len(p["search_arm_log"]) == 1
        assert len(p["search_arm_findings"]) == 1
        assert len(p["idea_revisions"]) == 1
        assert p["overlap_group_successors"]["Beta"]["successor"] == "Beta Prime"
        assert p["overlap_group_successors_by_origin"]["red_team_revision"][0][
            "predecessor"] == "Beta"
        assert p["overlap_groups_final"] == [_group("Alpha", "Beta Prime")]

    def test_payload_is_json_serializable(self):
        import json
        crew = _crew(overlap_groups=[_group("A", "B")])
        crew._record_search_arm("parity_direct", "q", "r", idea="A")
        crew._commit_idea_replacement(_idea("B"), _idea("B2"), origin="parity_pivot")
        json.dumps(crew.search_debug_payload())

    def test_artifact_is_saved_through_the_crews_own_checkpoint_manager(self):
        saved = {}

        class _Mgr:
            def save_stage(self, name, data):
                saved[name] = data
                return True

        crew = _crew()
        crew.checkpoint_mgr = _Mgr()
        crew._record_search_arm("parity_direct", "q", "r", idea="A")
        crew._save_search_debug_payload()
        assert "stage_5_search_arm_debug" in saved
        assert saved["stage_5_search_arm_debug"]["search_arm_spend"] == {"parity_direct": 1}

    def test_save_is_a_noop_without_a_checkpoint_manager(self):
        crew = _crew()
        crew._save_search_debug_payload()  # must not raise

    def test_save_survives_a_failing_checkpoint_manager(self):
        class _Boom:
            def save_stage(self, name, data):
                raise RuntimeError("disk full")

        crew = _crew()
        crew.checkpoint_mgr = _Boom()
        crew._save_search_debug_payload()  # fail-soft: diagnostics never abort a run


class TestPreRevisionIdeaSnapshot:
    def test_snapshot_captures_the_reposition_axes(self):
        crew = _crew()
        orig = _idea("Beta", value_proposition="audits invoices for plumbers",
                     target_personas=["plumber"], mechanism_tag="diff",
                     project_type="saas", incumbent_parity="shipped by Acme")
        rev = _idea("Beta Prime", value_proposition="scores brokers for freight brokers",
                    target_personas=["freight broker"], mechanism_tag="score",
                    project_type="directory")
        crew._commit_idea_replacement(orig, rev, origin="red_team_revision")
        row, = crew.idea_revision_log
        assert row["rebuild_origin"] == "red_team_revision"
        assert row["renamed"] is True
        assert row["before"]["value_proposition"] == "audits invoices for plumbers"
        assert row["before"]["target_personas"] == ["plumber"]
        assert row["before"]["incumbent_parity"] == "shipped by Acme"
        assert row["after"]["target_personas"] == ["freight broker"]
        # The measurement the reviewer could not make: audience+mechanism both moved.
        assert row["before"]["mechanism_tag"] != row["after"]["mechanism_tag"]
        assert row["before"]["target_personas"] != row["after"]["target_personas"]

    def test_refine_without_rename_is_still_logged(self):
        crew = _crew()
        crew._commit_idea_replacement(_idea("Beta"), _idea("Beta"), origin="parity_pivot")
        row, = crew.idea_revision_log
        assert row["renamed"] is False

    def test_snapshot_is_bounded(self):
        crew = _crew()
        crew._commit_idea_replacement(
            _idea("B", value_proposition="v" * 5000), _idea("B2"), origin="o")
        assert len(crew.idea_revision_log[0]["before"]["value_proposition"]) == 400

    def test_red_team_site_records_the_pre_revision_idea(self):
        ideas = [_real_idea("Alpha"), _real_idea("Beta", value_proposition="original vp"),
                 _real_idea("Gamma")]
        crew = _crew(overlap_groups=[])
        assert _run_red_team_replacement(crew, ideas, "Beta Prime") is True
        row, = crew.idea_revision_log
        assert row["rebuild_origin"] == "red_team_revision"
        assert row["before"]["solution_name"] == "Beta"
        assert row["before"]["value_proposition"] == "original vp"
        assert row["after"]["solution_name"] == "Beta Prime"


# ===========================================================================
# Step 0 — proof of ZERO behaviour change
# ===========================================================================

class TestGatingCounterUntouched:
    def test_recording_a_query_does_not_move_the_gating_counter(self):
        crew = _crew(_ma_serper_calls=7)
        for _ in range(20):
            crew._record_search_arm("parity_direct", "q", "r", counted=False)
        assert crew._ma_serper_calls == 7

    def test_parity_probe_leaves_the_gating_counter_where_it_found_it(self, monkeypatch):
        """The direct-parity arm is now fully instrumented and still spends nothing from the
        market-awareness budget — so no arm running after it loses a query."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 0)
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 60)
        ideas = [_idea("Alpha"), _idea("Beta")]

        class _Tool:
            def __init__(self):
                self._cache = {}

            def run(self, search_query):
                return "R"

        crew = _crew(search_tool=_Tool(), _ma_serper_calls=11,
                     niche_context=SimpleNamespace(niche_description="n"),
                     _incumbent_rows=[], audience_mapping=None, coverage_caveats=[])
        crew._probe_incumbents = lambda: ""
        crew._capability_phrases = lambda top: {}
        crew._mechanism_keywords = lambda idea, **kw: "kw"
        crew._probe_adjacent_markets = lambda top: ([], 0)
        crew._probe_toolbelt_free_bundle = lambda top: ([], 0)
        crew._run_parallel = lambda *a, **k: []
        crew._record_divergent_usage = lambda u: None
        crew._validate_idea_caps = lambda idea: []
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(findings=[]), None)):
            crew._probe_mechanism_parity(ideas)
        assert crew._ma_serper_calls == 11
        assert crew.search_arm_spend["parity_direct"] == 2

    def test_parity_probe_still_issues_exactly_the_same_queries(self, monkeypatch):
        """Instrumentation must not add, drop, or reword a query."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 0)
        seen = []

        class _Tool:
            def __init__(self):
                self._cache = {}

            def run(self, search_query):
                seen.append(search_query)
                return "R"

        ideas = [_idea("Alpha"), _idea("Beta")]
        crew = _crew(search_tool=_Tool(),
                     niche_context=SimpleNamespace(niche_description="london plumbers ltd"),
                     _incumbent_rows=[], audience_mapping=None, coverage_caveats=[])
        crew._probe_incumbents = lambda: ""
        crew._capability_phrases = lambda top: {}
        crew._mechanism_keywords = lambda idea, **kw: "invoice audit"
        crew._probe_adjacent_markets = lambda top: ([], 0)
        crew._probe_toolbelt_free_bundle = lambda top: ([], 0)
        crew._run_parallel = lambda *a, **k: []
        crew._record_divergent_usage = lambda u: None
        crew._validate_idea_caps = lambda idea: []
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(findings=[]), None)):
            crew._probe_mechanism_parity(ideas)
        # niche_label = first 6 words of niche_description, capped at 60 chars.
        assert seen == ["invoice audit software london plumbers ltd"] * 2
        assert [r["query"] for r in crew.search_arm_log] == seen

    def test_a_failing_search_is_still_skipped_not_recorded_as_a_snippet(self):
        """The probe's per-query `except: continue` must keep its meaning."""
        class _Tool:
            def __init__(self):
                self._cache = {}
                self.n = 0

            def run(self, search_query):
                self.n += 1
                if self.n == 1:
                    raise RuntimeError("serper 500")
                return "R"

        ideas = [_idea("Alpha"), _idea("Beta")]
        crew = _crew(search_tool=_Tool(),
                     niche_context=SimpleNamespace(niche_description="n"),
                     _incumbent_rows=[], audience_mapping=None, coverage_caveats=[])
        crew._probe_incumbents = lambda: ""
        crew._capability_phrases = lambda top: {}
        crew._mechanism_keywords = lambda idea, **kw: "kw"
        crew._probe_adjacent_markets = lambda top: ([], 0)
        crew._probe_toolbelt_free_bundle = lambda top: ([], 0)
        crew._run_parallel = lambda *a, **k: []
        crew._record_divergent_usage = lambda u: None
        crew._validate_idea_caps = lambda idea: []
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(findings=[]), None)) as m:
            crew._probe_mechanism_parity(ideas)
        # Only the surviving query produced a snippet, and only it was recorded.
        assert crew.search_arm_spend["parity_direct"] == 1
        assert m.call_count == 1


class TestRoutingIntoTheGatingCounterWouldChangeBehaviour:
    """WHY the gating counter was left alone (Step 0's stop condition).

    `_probe_mechanism_parity` issues its own uncounted queries BEFORE calling the adjacent
    niche-frame and toolbelt arms, both of which DO go through `_ma_search_batch`. That method
    truncates its cache-miss list to `budget - _ma_serper_calls`. So counting the direct-parity
    arm would starve the arms that run after it — and those arms write `incumbent_parity`,
    whose prefix selects a `market_fit` cap. Instrumentation may not do that.
    """

    def _batch_crew(self, used):
        sent = []

        class _Tool:
            def __init__(self):
                self._cache = {}

            def batch_run(self, queries):
                sent.extend(queries)
                return {q: "R" for q in queries}

        crew = _crew(search_tool=_Tool(), _ma_serper_calls=used)
        return crew, sent

    def test_a_pre_inflated_gating_counter_starves_a_downstream_arm(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 6)
        queries = [f"q{i}" for i in range(6)]

        crew_a, sent_a = self._batch_crew(used=0)     # today: parity spends nothing
        crew_a._ma_search_batch(list(queries))
        crew_b, sent_b = self._batch_crew(used=4)     # routed: parity charged 4 queries
        crew_b._ma_search_batch(list(queries))

        assert len(sent_a) == 6, "all downstream queries are sent today"
        assert len(sent_b) == 2, "routing the parity arm truncates them"
        assert sent_b != sent_a
        # The starved queries resolve to '' — their snippets never reach the judge that
        # writes incumbent_parity.
        assert crew_b._ma_search_batch.__self__ is crew_b

    def test_starved_queries_return_empty_so_the_judge_loses_evidence(self, monkeypatch):
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 6)
        crew, _sent = self._batch_crew(used=5)
        out = crew._ma_search_batch([f"q{i}" for i in range(6)])
        assert out["q0"] == "R"
        assert [out[f"q{i}"] for i in range(1, 6)] == [""] * 5

    def test_budget_exempt_does_not_escape_the_problem(self, monkeypatch):
        """`budget_exempt=True` lifts the gate for its OWN call but still increments the
        shared counter, so it would starve every later non-exempt arm just the same."""
        monkeypatch.setattr(settings, "market_awareness_serper_budget", 6)
        crew, _sent = self._batch_crew(used=0)
        crew._ma_search_batch(["a", "b", "c", "d"], budget_exempt=True)
        assert crew._ma_serper_calls == 4
        out = crew._ma_search_batch([f"q{i}" for i in range(6)])
        assert sum(1 for v in out.values() if v == "") == 4


# ---------------------------------------------------------------------------
# The two arms the ledger could not see (2026-08-17). Run 4bc9c406's persisted ledger
# recorded parity_direct 44 / adjacent_niche_frame 30 / adjacent_base 20 / toolbelt 17 and
# NOTHING for `_probe_incumbents` or `_probe_seed_brief_parity`. The incumbent probe is the
# arm every other parity query anchors on — each name-anchored query is
# f'"{incumbent}" {kw}' — so the queries behind a demonstrably wrong incumbent map were
# unrecoverable after the run.
# ---------------------------------------------------------------------------

class TestIncumbentProbeIsAttributed:
    def _crew(self, run_return="Acme is a tool", **extra):
        crew = _crew(search_tool=SimpleNamespace(run=lambda search_query: run_return),
                     niche_context=SimpleNamespace(niche_description="wedding photography"),
                     audience_mapping=None, competitor_mentions_text="", **extra)
        crew._ma_search = lambda q: None
        return crew

    def _run(self, crew):
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(incumbents=[]), None)):
            crew._probe_incumbents()

    def test_all_three_discovery_queries_land_in_the_ledger(self):
        crew = self._crew()
        self._run(crew)
        rows = [r for r in crew.search_arm_log if r["arm"] == "incumbent_probe"]
        assert crew.search_arm_spend["incumbent_probe"] == 3
        assert [r["query"] for r in rows] == [
            "best software tools for wedding photography",
            "wedding photography app pricing per month",
            "best apps and tools for wedding photography",
        ]

    def test_rows_are_marked_uncounted_and_the_gating_counter_is_untouched(self):
        """`counted` means "`_ma_serper_calls` already saw this". These are raw
        `search_tool.run` calls, so marking them counted would inflate `gated_spend` past
        `ma_serper_calls` and corrupt the diagnostic."""
        crew = self._crew(_ma_serper_calls=7)
        self._run(crew)
        rows = [r for r in crew.search_arm_log if r["arm"] == "incumbent_probe"]
        assert all(r["counted"] is False for r in rows)
        assert crew._ma_serper_calls == 7
        payload = crew.search_debug_payload()
        assert payload["gated_spend"] == 0
        assert payload["gated_spend"] <= payload["ma_serper_calls"]

    def test_snippet_identity_is_recorded_so_a_bad_map_is_traceable(self):
        crew = self._crew(run_return="Acme ($29/mo) does scheduling")
        self._run(crew)
        row = next(r for r in crew.search_arm_log if r["arm"] == "incumbent_probe")
        assert row["empty"] is False
        assert "Acme" in row["snippet"]["excerpt"]

    def test_a_failing_search_is_not_recorded_as_an_issued_query(self):
        calls = {"n": 0}

        def _run(search_query):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("serper 500")
            return "Acme is a tool"

        crew = self._crew()
        crew.search_tool = SimpleNamespace(run=_run)
        self._run(crew)
        assert crew.search_arm_spend["incumbent_probe"] == 2

    def test_the_verify_query_is_attributed_when_it_returns_a_result(self):
        crew = self._crew(run_return="no tool names here")
        crew.audience_mapping = SimpleNamespace(tools_currently_used=["PhotoPills"])
        crew._ma_search = lambda q: "PhotoPills costs $10"
        self._run(crew)
        queries = [r["query"] for r in crew.search_arm_log
                   if r["arm"] == "incumbent_probe"]
        assert "PhotoPills pricing" in queries
        assert crew.search_arm_spend["incumbent_probe"] == 4

    def test_a_budget_refused_verify_query_is_not_recorded_as_spend(self):
        """`_ma_search` returns None when the market-awareness budget refused the call.
        `search_arm_spend` means "queries ISSUED" — logging that would invent spend."""
        crew = self._crew(run_return="no tool names here")
        crew.audience_mapping = SimpleNamespace(tools_currently_used=["PhotoPills"])
        crew._ma_search = lambda q: None
        self._run(crew)
        assert crew.search_arm_spend["incumbent_probe"] == 3


class TestSeedBriefParityIsAttributed:
    def _crew(self):
        crew = _crew(search_tool=SimpleNamespace(run=lambda search_query: "SERP: Okara"),
                     niche_context=SimpleNamespace(
                         niche_description="Community-management tooling for B2B SaaS teams"))
        return crew

    def _run(self, crew):
        finding = SimpleNamespace(parity="shipped", covered_by="Okara",
                                  evidence="reply automation agents")
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(finding, None)):
            return crew._probe_seed_brief_parity(
                SimpleNamespace(solution_name="PitchedIdea"), ["drafts Reddit replies"])

    def test_all_three_query_angles_land_in_the_ledger_against_the_seed(self):
        crew = self._crew()
        note, calls = self._run(crew)
        rows = [r for r in crew.search_arm_log if r["arm"] == "seed_brief_parity"]
        assert note == "shipped by Okara: reply automation agents"
        assert crew.search_arm_spend["seed_brief_parity"] == calls == 3
        assert {r["idea"] for r in rows} == {"PitchedIdea"}
        assert rows[0]["query"] == "drafts Reddit replies tool"
        assert rows[1]["query"] == "best drafts Reddit replies tools"

    def test_rows_are_uncounted_and_never_reach_the_gating_counter(self):
        crew = self._crew()
        crew._ma_serper_calls = 3
        self._run(crew)
        rows = [r for r in crew.search_arm_log if r["arm"] == "seed_brief_parity"]
        assert all(r["counted"] is False for r in rows)
        assert crew._ma_serper_calls == 3
        payload = crew.search_debug_payload()
        assert payload["gated_spend"] <= payload["ma_serper_calls"]

    def test_the_ledger_survives_a_probe_that_fails_soft(self):
        """Display-only probe: a total search failure still returns None, and the ledger
        must record nothing rather than invent rows."""
        def _boom(search_query):
            raise RuntimeError("serper down")

        crew = self._crew()
        crew.search_tool = SimpleNamespace(run=_boom)
        note, calls = self._run(crew)
        assert note is None and calls == 3
        assert "seed_brief_parity" not in (getattr(crew, "search_arm_spend", None) or {})


# ---------------------------------------------------------------------------
# The malformed vendor-free discovery query (2026-08-17). Run 4bc9c406's persisted ledger
# recorded this query verbatim, 10 times:
#   "NPI taxonomy reconciliation software software The dental revenue cycle management market"
# "software" twice (the capability phrase already ended in it) and a niche label that is the
# first 6 words of the niche DESCRIPTION — prose, not a search term. Many ideas get ONLY this
# query, so a malformed one means a parity finding built on evidence no buyer would ever see.
# ---------------------------------------------------------------------------

# The real Stage-1 description from run 4bc9c406 (stage_1_niche_context.json), verbatim.
DENTAL_NICHE_DESCRIPTION = (
    "The dental revenue cycle management market encompasses the software, services, and "
    "workflows used by dental offices to manage patient billing, insurance claims "
    "processing, and reimbursement recovery."
)


def _all_niche_descriptions():
    """Every distinct Stage-1 niche description persisted under output/checkpoints.

    Real data, never a hand-written fixture: the defect is a property of how the Stage-1
    LLM writes descriptions, so the rule has to hold over the ones it actually wrote.
    """
    import json

    root = Path(__file__).resolve().parents[3] / "output" / "checkpoints"
    out = set()
    for path in sorted(root.glob("*/stage_1_niche_context.json")):
        try:
            desc = (json.loads(path.read_text()).get("niche_description") or "").strip()
        except Exception:
            continue
        if desc:
            out.add(desc)
    return sorted(out)


class TestNicheQueryLabel:
    """Property over the REAL corpus of niche descriptions, not a pinned example."""

    def test_the_live_malformed_query_is_no_longer_producible(self):
        q = _capability_discovery_query(
            "NPI taxonomy reconciliation software",
            _niche_query_label(DENTAL_NICHE_DESCRIPTION))
        assert q == "NPI taxonomy reconciliation software dental revenue cycle management"
        assert "software software" not in q
        assert not q.lower().endswith("market")

    @pytest.mark.parametrize("desc", _all_niche_descriptions())
    def test_label_is_never_longer_than_the_first_six_words_it_replaces(self, desc):
        """The old label was `" ".join(desc.split()[:6])[:60]`. A shorter, well-formed
        query is strictly better, so the fix must never lengthen one."""
        old = " ".join(desc.split()[:6])[:60]
        assert len(_niche_query_label(desc)) <= len(old)

    @pytest.mark.parametrize("desc", _all_niche_descriptions())
    def test_label_never_opens_with_a_determiner_or_closes_on_a_category_noun(self, desc):
        words = _niche_query_label(desc).split()
        if not words:
            return
        assert words[0].lower() not in _NICHE_LABEL_DETERMINERS
        assert words[-1].lower() not in _NICHE_LABEL_CATEGORY_NOUNS

    @pytest.mark.parametrize("desc,expected", [
        # The shapes the Stage-1 LLM actually writes, all present in the corpus above.
        ("The dental revenue cycle management market encompasses the software",
         "dental revenue cycle management"),
        ("The sim-racing hardware market encompasses the physical", "sim-racing hardware"),
        ("The open-source AI model ecosystem encompasses tools", "open-source AI model"),
        ("The ecosystem of competitive esports fans spans", "competitive esports fans"),
        ("The AI Agent Builders niche focuses on", "AI Agent Builders"),
        ("The LLM Developer Tools niche encompasses frameworks", "LLM Developer Tools"),
    ])
    def test_framing_boilerplate_is_stripped(self, desc, expected):
        assert _niche_query_label(desc) == expected

    def test_a_description_with_no_framing_is_left_alone(self):
        assert _niche_query_label("london plumbers ltd invoicing") == \
            "london plumbers ltd invoicing"


class TestCapabilityDiscoveryQuery:
    """`_capability_phrases` is asked for buyer/market vocabulary and its own prompt example
    is "multi-entity consolidation software", so the word arrives inside the phrase about as
    often as not. The template must not stutter — and must still add it when it is missing."""

    @pytest.mark.parametrize("capability", [
        "NPI taxonomy reconciliation software",
        "multi-entity consolidation software",
        "dental claims software tools",
        "SOFTWARE for payout reconciliation",
    ])
    def test_software_is_never_doubled_for_a_phrase_that_already_carries_it(self, capability):
        q = _capability_discovery_query(capability, "dental revenue cycle management")
        assert q.lower().count("software") == 1, q
        assert q.startswith(capability)

    @pytest.mark.parametrize("capability", [
        "payout deposit reconciliation",
        "dental claim status tracking",
        "denial appeal analytics",
    ])
    def test_software_is_still_added_when_the_phrase_lacks_it(self, capability):
        q = _capability_discovery_query(capability, "dental revenue cycle management")
        assert q == f"{capability} software dental revenue cycle management"

    def test_capability_survives_the_120_char_cap(self):
        q = _capability_discovery_query("payout deposit reconciliation", "x" * 200)
        assert len(q) == 120
        assert q.startswith("payout deposit reconciliation software")

    def test_an_empty_niche_label_leaves_no_trailing_whitespace(self):
        assert _capability_discovery_query("denial appeal analytics", "") == \
            "denial appeal analytics software"


class TestParityProbeEmitsTheFixedQuery:
    def test_the_probe_issues_the_well_formed_discovery_query(self, monkeypatch):
        """End-to-end through `_probe_mechanism_parity` with the real dental description and
        a capability phrase that already ends in "software"."""
        monkeypatch.setattr(settings, "parity_discovery_queries_per_run", 5)
        seen = []

        class _Tool:
            def __init__(self):
                self._cache = {}

            def run(self, search_query):
                seen.append(search_query)
                return "R"

        crew = _crew(search_tool=_Tool(),
                     niche_context=SimpleNamespace(
                         niche_description=DENTAL_NICHE_DESCRIPTION),
                     _incumbent_rows=[], audience_mapping=None, coverage_caveats=[])
        crew._probe_incumbents = lambda: ""
        crew._capability_phrases = lambda top: {
            "Alpha": "NPI taxonomy reconciliation software"}
        crew._mechanism_keywords = lambda idea, **kw: "kw"
        crew._probe_adjacent_markets = lambda top: ([], 0)
        crew._probe_toolbelt_free_bundle = lambda top: ([], 0)
        crew._run_parallel = lambda *a, **k: []
        crew._record_divergent_usage = lambda u: None
        crew._validate_idea_caps = lambda idea: []
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(SimpleNamespace(findings=[]), None)):
            crew._probe_mechanism_parity([_idea("Alpha")])
        assert seen == [
            "NPI taxonomy reconciliation software dental revenue cycle management"]
