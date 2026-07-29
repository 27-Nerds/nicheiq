"""Hermetic tests for the v4 data-route verifier (`verify_data_routes`).

The verifier makes the semantic call (self_sourced / obtainable / access_model) via structured LLM
output; the post-LLM logic is deterministic and regex-free. LLM + search are mocked — no live calls.
"""

from nicheiq.crews import idea_improvement_loop_v4 as v4
from nicheiq.crews.idea_improvement_loop_v4 import (
    DataRouteVerdict,
    verify_data_routes,
    _canonicalize_route,
    _relocate_needs_verify_flags,
)
from nicheiq.models.solution_idea import BaseSolutionIdea


def _idea(**fields):
    base = dict(
        solution_name="Test",
        description="A test idea.",
        value_proposition="Value.",
        pain_points_addressed=["pain"],
        core_features=["feature"],
        target_personas=["persona"],
    )
    base.update(fields)
    return BaseSolutionIdea(**base)


class _SpyLLM:
    """Records calls; returns a fixed (verdict, usage) tuple."""

    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.verdict, None


def _patch_llm(monkeypatch, verdict):
    spy = _SpyLLM(verdict)
    monkeypatch.setattr(v4.LLMService, "invoke_structured", staticmethod(spy))
    return spy


# --- canonicalization helper ----------------------------------------------

def test_canonicalize_official_gated_on_obtainable():
    assert _canonicalize_route("official", True) == "public"
    assert _canonicalize_route("official", False) == "blocked"
    assert _canonicalize_route("unofficial", True) == "unofficial"
    assert _canonicalize_route("blocked", True) == "blocked"


def test_canonicalize_rejects_off_vocab_label():
    # access_model is free text on the wire; anything outside DataAccessTag abstains
    # rather than shipping as a provenance label (it lands in tags.data_access too).
    assert _canonicalize_route("subscription", True) == "unverified"
    assert _canonicalize_route("licensed", True) == "unverified"
    assert _canonicalize_route("", True) == "blocked"
    # In-vocab labels still pass through untouched — 'freemium' is a real data tier.
    assert _canonicalize_route("freemium", True) == "freemium"
    assert _canonicalize_route("unverified", True) == "unverified"


# --- self_sourced drives public (the regex gate's robust replacement) -----

def test_self_sourced_verdict_maps_to_public(monkeypatch):
    spy = _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=True, obtainable=True, access_model="official", note="first-party submissions"))
    idea = _idea(data_sources=["User-submitted measurements"], data_access_model="restricted",
                 market_fit_score=0.85)
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert spy.calls == 1            # the LLM owns the judgment now (no pre-LLM regex skip)
    assert idea.data_access_model == "public"
    assert idea.market_fit_score == 0.85  # verifier doesn't touch market_fit upward


# --- canonicalization + obtainable gate on the (not-self-sourced) path -----

def test_refuted_maps_to_blocked(monkeypatch):
    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="refuted", access_model="", note="no open endpoint"))
    idea = _idea(data_sources=["SomeVendor API"], data_feasibility_score=0.9, build_feasibility_score=0.9)
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert idea.data_access_model == "blocked"  # refuted (evidence of non-access) keeps the cap
    assert idea.build_feasibility_score <= 0.3
    assert idea.data_feasibility_score <= 0.2   # B6 re-cap of stale data score


def test_supported_official_maps_to_public(monkeypatch):
    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="supported", access_model="official", note="public dataset"))
    idea = _idea(data_sources=["Public gov dataset portal"])
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert idea.data_access_model == "public"


def test_not_enough_info_abstains_to_unverified(monkeypatch):
    # The fix for over-blocking: an unconfirmed route is NOT penalized — flagged, not capped.
    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="not_enough_info", access_model="", note="evidence inconclusive"))
    idea = _idea(data_sources=["SomePlatform API"], data_access_model="public",
                 market_fit_score=0.8, data_feasibility_score=0.7, build_feasibility_score=0.7)
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert idea.data_access_model == "unverified"
    assert idea.market_fit_score == 0.8          # NOT capped (abstain, no penalty)
    assert idea.data_feasibility_score == 0.7    # NOT crushed
    assert idea.build_feasibility_score == 0.7
    assert "UNVERIFIED" in idea.data_acquisition_notes
    assert "evidence inconclusive" in idea.data_acquisition_notes


# --- notes reconcile on-action --------------------------------------------

def test_notes_overwritten_when_label_changes(monkeypatch):
    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="refuted", access_model="", note="search found no endpoint"))
    idea = _idea(data_sources=["SomeVendor API"], data_access_model="restricted",
                 data_acquisition_notes="stale critic note about per-id lookup")
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert idea.data_access_model == "blocked"
    assert idea.data_acquisition_notes == "search found no endpoint"


def test_notes_kept_when_label_unchanged(monkeypatch):
    # prior 'public' + verdict supported/official → canonical 'public' (unchanged) → keep critic note.
    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="supported", access_model="official", note="thin verdict note"))
    idea = _idea(data_sources=["Public gov dataset portal"], data_access_model="public",
                 data_acquisition_notes="rich critic note describing the route and cost")
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert idea.data_access_model == "public"
    assert idea.data_acquisition_notes == "rich critic note describing the route and cost"


# --- well-known-source pass (2026-07-03) ------------------------------------
# Famous free sources were getting misclassified by sparse search snippets (live: GitHub API
# -> 'restricted', SAM.gov -> 'paywalled'). Two steps: deterministic retrieval over the
# allowlist, then an LLM confirm over the retrieved entries; anything unrecognized or
# unconfirmed falls through to the web path untouched.

def _boom(_q):
    raise AssertionError("search must not run on the allowlist path")


def _confirm_yes(monkeypatch):
    monkeypatch.setattr(v4, "llm_confirm_known_route",
                        lambda matches, **kw: ", ".join(dict.fromkeys(n for _, n in matches)))


def _confirm_no(monkeypatch):
    monkeypatch.setattr(v4, "llm_confirm_known_route", lambda matches, **kw: None)


class TestWellKnownSourcePass:
    def test_github_api_short_circuits_to_public(self, monkeypatch):
        spy = _patch_llm(monkeypatch, DataRouteVerdict(
            self_sourced=False, verdict="refuted", note="sparse snippets"))  # would misclassify
        _confirm_yes(monkeypatch)
        idea = _idea(data_sources=["GitHub REST API"], data_access_model="restricted")
        v = verify_data_routes(idea, None, search=_boom, invoke=None)
        assert spy.calls == 0                       # verdict LLM never consulted
        assert idea.data_access_model == "public"
        assert "GitHub REST API" in idea.data_acquisition_notes
        assert v.verdict == "supported" and v.obtainable

    def test_sam_gov_short_circuits_to_public(self, monkeypatch):
        spy = _patch_llm(monkeypatch, DataRouteVerdict(self_sourced=False, verdict="refuted"))
        _confirm_yes(monkeypatch)
        idea = _idea(data_sources=["SAM.gov opportunity notices"], data_access_model="paywalled")
        verify_data_routes(idea, None, search=_boom, invoke=None)
        assert spy.calls == 0
        assert idea.data_access_model == "public"

    def test_confirm_rejection_falls_through_to_web_path(self, monkeypatch):
        # retrieval hits, but the LLM says the claim doesn't really refer to the matched
        # source (name coincidence / partner-gated data) -> full web verification runs.
        spy = _patch_llm(monkeypatch, DataRouteVerdict(
            self_sourced=False, verdict="not_enough_info", note=""))
        _confirm_no(monkeypatch)
        idea = _idea(data_sources=["GitHub REST API"], data_access_model="restricted")
        verify_data_routes(idea, None, search=lambda q: "", invoke=None)
        assert spy.calls == 1                       # web path taken
        assert idea.data_access_model == "unverified"

    def test_mixed_claim_falls_through_before_confirm(self, monkeypatch):
        # A famous source next to an unknown vendor feed must NOT even reach the confirm.
        spy = _patch_llm(monkeypatch, DataRouteVerdict(
            self_sourced=False, verdict="not_enough_info", note=""))
        def _no_confirm(*a, **kw):
            raise AssertionError("confirm must not run when retrieval fails")
        monkeypatch.setattr(v4, "llm_confirm_known_route", _no_confirm)
        idea = _idea(data_sources=["GitHub REST API", "VendorMetrics partner feed"])
        verify_data_routes(idea, None, search=lambda q: "", invoke=None)
        assert spy.calls == 1                       # web path taken
        assert idea.data_access_model == "unverified"

    def test_unrecognized_vendor_falls_through(self, monkeypatch):
        spy = _patch_llm(monkeypatch, DataRouteVerdict(
            self_sourced=False, verdict="refuted", note="no trace"))
        idea = _idea(data_sources=["ActBlue donor API"])
        verify_data_routes(idea, None, search=lambda q: "", invoke=None)
        assert spy.calls == 1
        assert idea.data_access_model == "blocked"  # fabrication rule untouched

    def test_prior_public_label_keeps_existing_notes(self, monkeypatch):
        spy = _patch_llm(monkeypatch, DataRouteVerdict(self_sourced=False, verdict="refuted"))
        _confirm_yes(monkeypatch)
        idea = _idea(data_sources=["SEC EDGAR filings"], data_access_model="public",
                     data_acquisition_notes="rich critic note")
        verify_data_routes(idea, None, search=_boom, invoke=None)
        assert spy.calls == 0
        assert idea.data_acquisition_notes == "rich critic note"  # label unchanged -> notes kept


class TestVerdictPromptPins:
    def _capture_prompt(self, monkeypatch):
        captured = {}

        def fake(*args, **kwargs):
            captured["prompt"] = kwargs.get("prompt") or (args[0] if args else "")
            return DataRouteVerdict(self_sourced=False, verdict="not_enough_info", note=""), None

        monkeypatch.setattr(v4.LLMService, "invoke_structured", staticmethod(fake))
        idea = _idea(data_sources=["SomePlatform API"])
        verify_data_routes(idea, None, search=lambda q: "", invoke=None)
        return captured["prompt"]

    def test_famous_source_exception_present(self, monkeypatch):
        prompt = self._capture_prompt(monkeypatch)
        assert "canonically famous sources" in prompt
        assert "must NOT downgrade a famous source" in prompt
        # the exception is scoped: unrecognized vendor APIs still need evidence
        assert "NEVER applies to" in prompt

    def test_fabrication_rule_retained(self, monkeypatch):
        prompt = self._capture_prompt(monkeypatch)
        assert "zero" in prompt and "corroboration is fabricated" in prompt


# --- NEEDS-VERIFY contamination: flags must never reach the search API ---------
# Regression for the serper.dev garbage-query bug: the ideator dumped [NEEDS-VERIFY: ...]
# tags into data_sources; the verifier didn't scan data_sources, so the tags were treated as
# literal source names and shipped to Serper as a duplicated, bracket-polluted query.

def test_relocate_strips_flags_from_data_sources_into_notes():
    idea = _idea(data_sources=[
        "Reddit (r/personalfinance, r/financialindependence)",
        "[NEEDS-VERIFY: does r/financialindependence expose 529 allocation threads?]",
        "[NEEDS-VERIFY: do state treasury sites expose a 529 deduction-cap API?]",
    ], data_acquisition_notes="existing note")
    _relocate_needs_verify_flags(idea)
    # data_sources holds clean source names only — no bracket flags remain
    assert idea.data_sources == ["Reddit (r/personalfinance, r/financialindependence)"]
    # both flags relocated into the free-text notes the verifier scans
    assert "NEEDS-VERIFY" in idea.data_acquisition_notes
    assert "529 allocation threads" in idea.data_acquisition_notes
    assert "state treasury" in idea.data_acquisition_notes
    # idempotent
    before = (list(idea.data_sources or []), idea.data_acquisition_notes)
    _relocate_needs_verify_flags(idea)
    assert (list(idea.data_sources or []), idea.data_acquisition_notes) == before


def test_verify_never_ships_brackets_or_duplicated_sources_to_search(monkeypatch):
    captured: list[str] = []

    def _search(q):
        captured.append(q)
        return ""

    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="not_enough_info", note="inconclusive"))
    idea = _idea(data_sources=[
        "Reddit (r/personalfinance, r/financialindependence)",
        "Bogleheads.org forum",
        "[NEEDS-VERIFY: does r/financialindependence expose 529 vs retirement threads?]",
        "[NEEDS-VERIFY: do state treasury sites expose a machine-readable 529 API?]",
    ])
    verify_data_routes(idea, None, search=_search, invoke=None)
    # no query carries the literal NEEDS-VERIFY bracket syntax to the search API
    assert all("[NEEDS-VERIFY" not in q for q in captured), captured
    # no query is the source list concatenated with itself (the original duplication bug)
    assert all(q.count("Reddit (r/personalfinance") <= 1 for q in captured), captured
    # data_sources is clean post-verify
    assert all("NEEDS-VERIFY" not in s for s in (idea.data_sources or [])), idea.data_sources
    # the verify questions (not the polluted source list) drove the availability query
    assert any("529" in q for q in captured), captured
    # at least one query was issued (web path ran — Reddit/Bogleheads aren't on the allowlist)
    assert captured, "expected the web-search path to run"


# --- combined-query recall fix (2026-07-09) --------------------------------------------------
# Live evidence: a 6-source combined query returned 9 EPA hits, 1 USDA, 0 for the other 4
# sources — the verdict LLM judged 4 sources on silence. Fix: per-source queries (capped at 3
# + 1 flags query), and self-sourced/non-web items (user input, internal, proprietary, ...)
# never enter a query at all (no Google query could verify them anyway).

def test_non_web_items_excluded_from_queries(monkeypatch):
    captured: list[str] = []

    def _search(q):
        captured.append(q)
        return ""

    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="not_enough_info", note="inconclusive"))
    idea = _idea(data_sources=[
        "VendorFeed XYZ API",
        "Internal Breed Digging Proprietary Table (curated in-house)",
        "Property Age Metadata (User input)",
    ])
    verify_data_routes(idea, None, search=_search, invoke=None)
    assert all("Internal Breed Digging" not in q for q in captured), captured
    assert all("Property Age Metadata" not in q for q in captured), captured
    assert any("VendorFeed XYZ API" in q for q in captured), captured


def test_per_source_query_cap_and_no_combined_blob(monkeypatch):
    captured: list[str] = []

    def _search(q):
        captured.append(q)
        return ""

    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="not_enough_info", note="inconclusive"))
    idea = _idea(data_sources=[
        "VendorFeedOne API", "VendorFeedTwo API", "VendorFeedThree API", "VendorFeedFour API",
    ])
    verify_data_routes(idea, None, search=_search, invoke=None)
    # no flags -> no availability query; capped at 3 per-source queries (4th source dropped)
    assert len(captured) == 3, captured
    assert any("VendorFeedOne" in q for q in captured), captured
    assert any("VendorFeedTwo" in q for q in captured), captured
    assert any("VendorFeedThree" in q for q in captured), captured
    assert all("VendorFeedFour" not in q for q in captured), captured
    # the old combined-sources query (all items joined into one blob) is gone
    assert all("VendorFeedOne" not in q or "VendorFeedTwo" not in q for q in captured), captured


def test_known_allowlist_source_items_skip_their_own_query(monkeypatch):
    # Live EPA case: sources individually recognized by the (now expanded) allowlist don't
    # need their own web query — only genuinely unknown items spend a query slot.
    captured: list[str] = []

    def _search(q):
        captured.append(q)
        return ""

    _patch_llm(monkeypatch, DataRouteVerdict(
        self_sourced=False, verdict="not_enough_info", note="inconclusive"))
    idea = _idea(data_sources=[
        "EPA Soil Screening Levels for residential exposure",
        "VendorMetrics partner feed",
    ])
    verify_data_routes(idea, None, search=_search, invoke=None)
    assert all("EPA Soil Screening" not in q for q in captured), captured
    assert any("VendorMetrics" in q for q in captured), captured
