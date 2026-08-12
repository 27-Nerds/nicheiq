"""idea_validation block (plan P5.22) + evidence breadth helper (P5.23).

The block is a pure reshape of state, marker-selected, enum-driven. Copy assertions are
against the module's fixed constants — never re-derived prose.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from nicheiq.models.solution_idea import BaseSolutionIdea, RedTeamFinding
from nicheiq.report.idea_validation_block import (
    DEMAND_NOT_MEASURED,
    NONE_FOUND_NOTE,
    THIN_EVIDENCE_NOTE,
    UNANCHORED_NOTE,
    build_idea_validation_block,
)
from nicheiq.utils.validation.evidence_breadth import (
    compute_evidence_breadth,
    compute_evidence_confidence,
)


def _idea(**kw):
    base = dict(
        solution_name="Green Lot Tracker", description="d", value_proposition="v",
        candidate_status="active", source_frame="pain", generation_operation_id=None,
        pain_points_addressed=[], target_personas=["roasters"], source_segment="Roasters",
        incumbent_parity="none found", unanchored_hypothesis=False,
        market_fit_score=0.7, technical_feasibility_score=0.8, novelty_score=0.5,
        seo_scalability_score=0.4, red_team_verdict=None, red_team_caveats=[],
        duplicate_of=None, existing_equivalent=None, idea_id="id-1", idea_revision=1,
    )
    base.update(kw)
    return BaseSolutionIdea.model_construct(**base)


def _post(pid, author, sub, when):
    return SimpleNamespace(post_id=pid, author=author, subreddit=sub,
                           created_utc=when, platform=None)


def _pain(title, ids, severity=0.7, quotes=("it hurts",)):
    return SimpleNamespace(title=title, source_post_ids=list(ids),
                           severity_score=severity,
                           representative_quotes=list(quotes))


def _state(ideas, pains=(), posts=(), **kw):
    social = SimpleNamespace(reddit_posts=list(posts), generic_posts=[])
    state = SimpleNamespace(
        user_idea_text="my pitch", user_idea_brief="my brief",
        user_idea_inferred_fields=["delivery"], user_idea_pivot=None,
        idea_generation=SimpleNamespace(solution_ideas=list(ideas)),
        pain_point_analysis=SimpleNamespace(pain_points=list(pains)),
        social_content=social,
        niche_context=SimpleNamespace(
            niche_description="the market", user_target_audience="roasters",
            resolved_primary_audience=None),
        niche_incumbent_map=[{"name": "RoasterTools", "pricing": "$49/mo",
                              "focus": "roast planning", "gap": "no lot tracking"}],
        idea_ruled_out=[],
    )
    for k, v in kw.items():
        setattr(state, k, v)
    return state


SEED_KW = dict(source_frame="user_seed", generation_operation_id="validate")


def test_non_validate_state_returns_none():
    state = _state([_idea()])
    state.user_idea_text = None
    assert build_idea_validation_block(state, "idea") is None


def test_marker_selection_ignores_chat_seeds():
    chat_seed = _idea(solution_name="ChatSeed", source_frame="user_seed",
                      generation_operation_id="uuid-123")
    seed = _idea(solution_name="MyIdea", **SEED_KW)
    block = build_idea_validation_block(_state([chat_seed, seed]), "validate_idea")
    assert block["idea_name"] == "MyIdea"


def test_worth_testing_with_supported_evidence():
    when = [datetime(2026, 1, 5, tzinfo=timezone.utc),
            datetime(2026, 4, 5, tzinfo=timezone.utc)]
    posts = [_post(f"p{i}", f"user{i}", f"sub{i % 2}", when[i % 2]) for i in range(4)]
    pains = [_pain("stale beans", ["p0", "p1", "p2", "p3"])]
    seed = _idea(pain_points_addressed=["stale beans"], **SEED_KW)
    block = build_idea_validation_block(
        _state([seed, _idea(solution_name="Alt")], pains=pains, posts=posts),
        "validate_idea")

    assert block["outcome"] == "worth_testing"
    parts = {p["key"]: p for p in block["parts"]}
    assert parts["problem_real"]["state"] == "supported"
    assert parts["space_occupied"]["state"] == "none_found"
    assert parts["space_occupied"]["detail"] == NONE_FOUND_NOTE
    assert parts["demand"]["state"] == "not_measured"
    assert parts["demand"]["detail"] == DEMAND_NOT_MEASURED
    assert block["breadth"]["posts"] == 4
    assert block["breadth"]["distinct_authors"] == 4
    assert block["breadth"]["distinct_communities"] == 2
    assert block["breadth"]["months_spanned"] == 4
    assert block["seed_purchasable"] is True
    assert block["alternatives"]["count"] == 1
    assert block["competitors"][0]["price_caveat"] == "snippet-derived, ±1 tier"


def test_thin_evidence_is_low_confidence_with_fixed_copy():
    posts = [_post("p0", "user0", "sub0", datetime(2026, 1, 5, tzinfo=timezone.utc))]
    pains = [_pain("stale beans", ["p0"])]
    seed = _idea(pain_points_addressed=["stale beans"], **SEED_KW)
    block = build_idea_validation_block(
        _state([seed], pains=pains, posts=posts), "validate_idea")

    parts = {p["key"]: p for p in block["parts"]}
    assert parts["problem_real"]["state"] == "thin"
    assert parts["problem_real"]["detail"] == THIN_EVIDENCE_NOTE
    assert block["evidence_confidence"] == "Low"


def test_unanchored_seed_uses_hypothesis_copy():
    seed = _idea(unanchored_hypothesis=True, **SEED_KW)
    block = build_idea_validation_block(_state([seed]), "validate_idea")
    assert block["outcome"] == "premise_unproven"
    parts = {p["key"]: p for p in block["parts"]}
    assert parts["problem_real"]["state"] == "not_found"
    assert parts["problem_real"]["detail"] == UNANCHORED_NOTE


def test_occupied_outcome_and_parity_raises_confidence():
    seed = _idea(incumbent_parity="shipped (RoasterTools): ships lot tracking", **SEED_KW)
    block = build_idea_validation_block(_state([seed]), "validate_idea")
    assert block["outcome"] == "occupied"
    parts = {p["key"]: p for p in block["parts"]}
    assert parts["space_occupied"]["state"] == "shipped"
    # No linked evidence => base Low, but a parity HIT raises one band (never lowers).
    assert block["evidence_confidence"] == "Moderate"


def test_red_team_kill_reconciles_blank_parity_with_verdict_summary():
    seed = _idea(
        incumbent_parity=None,
        red_team_verdict="killed",
        red_team_caveats=[
            "Gorgias and eDesk already cover category-adjacent order-aware drafts."
        ],
        **SEED_KW,
    )

    block = build_idea_validation_block(_state([seed]), "validate_idea")
    parts = {part["key"]: part for part in block["parts"]}

    assert block["outcome"] == "premise_unproven"
    assert "adversarial review could not confirm the premise" in block["headline"]
    assert "nothing we found ships" not in block["headline"]
    assert parts["space_occupied"] == {
        "key": "space_occupied",
        "state": "review_concerns",
        "answer": "Concerns found",
        "detail": (
            "The direct-equivalent probe did not produce a result, but adversarial "
            "review found material concerns. See What would kill it."
        ),
    }


def test_red_team_weakness_keeps_worth_testing_without_claiming_clear_lane():
    seed = _idea(
        incumbent_parity=None,
        red_team_verdict="weakened",
        red_team_caveats=["Existing suites may make a standalone layer difficult to sell."],
        **SEED_KW,
    )

    block = build_idea_validation_block(_state([seed]), "validate_idea")
    parts = {part["key"]: part for part in block["parts"]}

    assert block["outcome"] == "worth_testing"
    assert "adversarial review found material concerns" in block["headline"]
    assert "nothing we found ships" not in block["headline"]
    assert parts["space_occupied"]["state"] == "review_concerns"


def test_gap_only_typed_weakness_reports_incomplete_evidence():
    seed = _idea(
        incumbent_parity=None,
        red_team_verdict="weakened",
        red_team_findings=[RedTeamFinding(
            kind="evidence_gap",
            claim="Search did not establish a buyer.",
        )],
        red_team_caveats=["Search did not establish a buyer."],
        **SEED_KW,
    )

    block = build_idea_validation_block(_state([seed]), "validate_idea")

    assert block["outcome"] == "worth_testing"
    assert "returned incomplete evidence" in block["headline"]
    assert block["red_team_findings"] == [{
        "claim": "Search did not establish a buyer.",
        "kind": "evidence_gap",
    }]
    assert block["kill_risks"][0]["finding_kind"] == "evidence_gap"


def test_space_occupied_distinguishes_explicit_incomplete_from_verified_concerns():
    gap = {"kind": "evidence_gap", "claim": "Search did not establish a buyer."}
    affirmative = {
        "kind": "verified_payer_mismatch",
        "claim": "The observed user cannot authorize a purchase.",
    }
    cases = [
        ([], "evidence_incomplete", "Evidence incomplete", "incomplete evidence"),
        ([{"kind": "not_a_kind", "claim": "Unsupported raw row."}],
         "evidence_incomplete", "Evidence incomplete", "incomplete evidence"),
        ([gap], "evidence_incomplete", "Evidence incomplete", "incomplete evidence"),
        (None, "review_concerns", "Concerns found", "material concerns"),
        ([gap, affirmative], "review_concerns", "Concerns found", "material concerns"),
    ]

    for findings, state, answer, detail in cases:
        seed = _idea(
            incumbent_parity=None,
            red_team_verdict="weakened",
            red_team_findings=findings,
            red_team_caveats=["Legacy compatibility caveat."],
            **SEED_KW,
        )
        block = build_idea_validation_block(_state([seed]), "validate_idea")
        space = {part["key"]: part for part in block["parts"]}["space_occupied"]

        assert space["state"] == state, findings
        assert space["answer"] == answer, findings
        assert detail in space["detail"], findings
        if findings is not None and not any(
            row.get("kind") == "verified_payer_mismatch"
            for row in findings if isinstance(row, dict)
        ):
            assert "Concerns found" not in space["answer"]
            assert "material concerns" not in space["detail"]


def test_raw_gap_only_kill_materializes_as_weakened_incomplete_evidence():
    seed = _idea(
        incumbent_parity=None,
        red_team_verdict="killed",
        red_team_findings=[RedTeamFinding(
            kind="evidence_gap",
            claim="Search did not establish a buyer.",
        )],
        red_team_caveats=["Search did not establish a buyer."],
        **SEED_KW,
    )

    block = build_idea_validation_block(_state([seed]), "validate_idea")

    assert block["outcome"] == "worth_testing"
    assert block["red_team_verdict"] == "weakened"
    assert "incomplete evidence" in block["headline"]
    assert "counterevidence" not in block["headline"]


def test_affirmative_typed_kill_reports_verified_counterevidence():
    seed = _idea(
        incumbent_parity=None,
        red_team_verdict="killed",
        red_team_findings=[RedTeamFinding(
            kind="verified_payer_mismatch",
            claim="The observed user cannot authorize a purchase.",
        )],
        red_team_caveats=["The observed user cannot authorize a purchase."],
        **SEED_KW,
    )

    block = build_idea_validation_block(_state([seed]), "validate_idea")

    assert block["outcome"] == "premise_unproven"
    assert "verified counterevidence" in block["headline"]


def test_direct_parity_remains_authoritative_when_red_team_also_kills():
    seed = _idea(
        incumbent_parity="shipped by Gorgias: ships order-aware reply drafts",
        red_team_verdict="killed",
        red_team_caveats=["The category is crowded."],
        **SEED_KW,
    )

    block = build_idea_validation_block(_state([seed]), "validate_idea")
    parts = {part["key"]: part for part in block["parts"]}

    assert block["outcome"] == "occupied"
    assert parts["space_occupied"]["state"] == "shipped"
    assert parts["space_occupied"]["answer"] == "Already shipped"


def test_demoted_seed_ruled_out_not_purchasable_with_reason():
    seed = _idea(candidate_status="demoted", **SEED_KW)
    state = _state([seed])
    state.idea_ruled_out = [{"idea_id": "id-1", "reason": "no payability in this segment"}]
    block = build_idea_validation_block(state, "validate_idea")

    assert block["outcome"] == "ruled_out"
    assert block["seed_purchasable"] is False
    assert block["demotion_reason"] == "no payability in this segment"
    # Demoted seed is excluded from the alternatives pool too.
    assert block["alternatives"]["count"] == 0


def test_missing_seed_yields_not_evaluated_block():
    block = build_idea_validation_block(_state([_idea(solution_name="Alt")]),
                                        "validate_idea")
    assert block["outcome"] == "not_evaluated"
    assert block["seed_purchasable"] is False
    assert block["alternatives"]["count"] == 1


def test_pivot_record_and_refs_flow_through():
    seed = _idea(incumbent_parity="partial (X): overlap", **SEED_KW)
    pivot = _idea(solution_name="Wedge", source_frame="user_seed",
                  generation_operation_id="validate_pivot", idea_id="id-2")
    state = _state([seed, pivot])
    state.user_idea_pivot = {"attempted": True, "outcome": "accepted",
                             "trigger_finding": "partial (X): overlap",
                             "because": "gap", "keeps": "k", "changes": "c",
                             "reason_not_shown": None, "ries_label": "zoom-in",
                             "name": "Wedge"}
    block = build_idea_validation_block(state, "validate_idea")
    assert block["pivot"]["outcome"] == "accepted"
    assert block["pivot"]["idea_id"] == "id-2"
    # Pivot never counts as an alternative.
    assert block["alternatives"]["count"] == 0


def test_duplicate_of_resolves_pool_idea():
    alt = _idea(solution_name="Freshness Radar", idea_id="id-9")
    seed = _idea(duplicate_of="Freshness Radar", **SEED_KW)
    block = build_idea_validation_block(_state([seed, alt]), "validate_idea")
    assert block["duplicate_of"] == {"idea_id": "id-9", "name": "Freshness Radar"}


# ── kill-risk chain (Q2) ──

TERMS = {"mechanism": ["lot tracking", "freshness alerts"], "audience": [],
         "problem": ["stale beans"], "delivery": []}


def test_red_team_leads_and_market_signal_survives_cap():
    pains = [_pain("stale beans", [], severity=0.5),
             _pain("stale lot tracking data ruins roasts", [], severity=0.8)]
    seed = _idea(pain_points_addressed=["stale beans"],
                 red_team_caveats=["c1", "c2", "c3"], **SEED_KW)
    block = build_idea_validation_block(
        _state([seed], pains=pains, user_idea_identity_terms=TERMS), "validate_idea")
    assert [r["source"] for r in block["kill_risks"]] == [
        "adversarial_review", "adversarial_review", "market_signal"]
    assert block["kill_risks"][0]["claim"] == "c1"


def test_critic_note_without_concession_is_skipped():
    seed = _idea(calibration_notes="market_fit: Strong validated pain and clear buyer.",
                 **SEED_KW)
    block = build_idea_validation_block(_state([seed]), "validate_idea")
    assert block["kill_risks"] == []


def test_critic_concession_extracted_after_however():
    seed = _idea(calibration_notes=(
        "market_fit: Addresses a validated pain with a clear buyer; however, generic "
        "suites already bundle this and willingness to pay is unproven. | "
        "novelty: fine"), **SEED_KW)
    block = build_idea_validation_block(_state([seed]), "validate_idea")
    assert [r["source"] for r in block["kill_risks"]] == ["score_critic"]
    claim = block["kill_risks"][0]["claim"]
    assert claim.startswith("Generic suites already bundle")
    assert "validated pain" not in claim


def test_market_signal_gate_is_relative_to_anchored_severity():
    # The adverse pain (0.6) does NOT exceed the anchored pain's severity (0.7) → no entry.
    pains = [_pain("stale beans", [], severity=0.7),
             _pain("lot tracking spreadsheets go stale", [], severity=0.6)]
    seed = _idea(pain_points_addressed=["stale beans"], **SEED_KW)
    block = build_idea_validation_block(
        _state([seed], pains=pains, user_idea_identity_terms=TERMS), "validate_idea")
    assert block["kill_risks"] == []


# ── anchored-pain honesty (Q3) ──

def test_anchored_pains_sorted_by_severity_with_mention_count():
    pains = [_pain("stale beans", [], severity=0.4),
             _pain("lot chaos", [], severity=0.7)]
    pains[1].mention_count = 9
    seed = _idea(pain_points_addressed=["stale beans", "lot chaos"], **SEED_KW)
    block = build_idea_validation_block(_state([seed], pains=pains), "validate_idea")
    rows = block["anchored_pains"]
    assert [r["pain_title"] for r in rows] == ["lot chaos", "stale beans"]
    assert rows[0]["mention_count"] == 9


def test_quote_rerank_prefers_focus_overlap_and_dedupes():
    quotes = ["> the pricing rant nobody asked for",
              "the pricing rant nobody asked for",
              "my lot tracking spreadsheet misses freshness alerts"]
    pains = [_pain("stale beans", [], quotes=quotes)]
    seed = _idea(pain_points_addressed=["stale beans"], **SEED_KW)
    block = build_idea_validation_block(
        _state([seed], pains=pains, user_idea_identity_terms=TERMS), "validate_idea")
    rendered = block["anchored_pains"][0]["quotes"]
    assert rendered[0] == "my lot tracking spreadsheet misses freshness alerts"
    assert len(rendered) == 2  # twins collapsed, then top-2


def test_high_breadth_with_mild_anchor_caps_at_moderate_even_with_parity_hit():
    band, reason = compute_evidence_confidence(
        {"posts": 9, "distinct_authors": 6, "distinct_communities": 3,
         "months_spanned": 5, "label": "x"},
        "partial (SomeTool): overlaps", anchored_quality=False)
    assert band == "Moderate"  # cap is applied LAST — it beats the parity lift
    assert reason.endswith("Breadth is broad but the matched problem is mild.")


# ── refinement disclosure (Q6) ──

def test_faithful_seed_has_null_refinement_and_original_headline():
    seed = _idea(description="Lot tracking with freshness alerts for stale beans.",
                 **SEED_KW)
    block = build_idea_validation_block(
        _state([seed], user_idea_identity_terms=TERMS), "validate_idea")
    assert block["refinement"] is None
    assert block["headline"].endswith(
        "nothing we found ships your mechanism yet. Demand is still unmeasured.")
    assert block["evaluated_idea"]["name"] == "Green Lot Tracker"


def test_drifted_seed_renders_panel_with_null_because_when_no_pain_matches():
    seed = _idea(solution_name="RoastLab Analytics",
                 description="A completely different roast-profiling analytics suite.",
                 **SEED_KW)
    block = build_idea_validation_block(
        _state([seed], user_idea_identity_terms=TERMS), "validate_idea")
    assert block["refinement"] == {
        "kept": [], "changed": ["mechanism", "problem"], "because": None}
    assert "the mechanism we evaluated" in block["headline"]


def test_states_without_identity_terms_never_render_the_panel():
    # Legacy validate states (pre-quality-pass) have no terms — no drift check possible.
    block = build_idea_validation_block(_state([_idea(**SEED_KW)]), "validate_idea")
    assert block["refinement"] is None


def test_brief_parity_hit_without_refinement_scopes_the_headline():
    """Run-2 shape: detector passes (mechanism demoted, not repudiated) but the brief
    probe found the pitched category SHIPPED — the headline must not claim "nothing
    ships your mechanism", and the finding must be exposed for standalone render."""
    block = build_idea_validation_block(
        _state([_idea(**SEED_KW)],
               user_idea_brief_parity="shipped by Okara: reply automation tools"),
        "validate_idea")
    assert block["refinement"] is None
    assert block["original_mechanism_parity"] == "shipped by Okara: reply automation tools"
    assert "Tools already ship in your mechanism's category" in block["headline"]
    assert "nothing we found ships your mechanism" not in block["headline"]


def test_price_notes_normalized_in_competitor_rows():
    state = _state([_idea(**SEED_KW)])
    state.niche_incumbent_map = [
        {"name": "A", "pricing": "$49/mo", "focus": "f", "gap": "g"},
        {"name": "B", "pricing": "unknown", "focus": "f", "gap": "g"},
        {"name": "C", "pricing": "Enterprise", "focus": "f", "gap": "g"},
        {"name": "D", "pricing": "Freemium", "focus": "f", "gap": "g"},
        {"name": "E", "pricing": "Contact sales", "focus": "f", "gap": "g"},
        {"name": "F", "pricing": None, "focus": "f", "gap": "g"},
    ]
    block = build_idea_validation_block(state, "validate_idea")
    assert [c["price_note"] for c in block["competitors"]] == [
        "$49/mo", None, "enterprise tier", "Freemium", "Contact sales", None]


def test_brief_parity_none_found_is_not_exposed():
    """'none found' from the brief probe is state-side telemetry — rendering "Your
    original mechanism: none found" would be nonsense, and the frontend never sniffs."""
    block = build_idea_validation_block(
        _state([_idea(**SEED_KW)], user_idea_brief_parity="none found"),
        "validate_idea")
    assert block["original_mechanism_parity"] is None
    assert "original mechanism already has tools shipping" not in block["headline"]


# ── breadth helper directly ──

def test_breadth_none_when_no_linkage():
    social = SimpleNamespace(reddit_posts=[], generic_posts=[])
    assert compute_evidence_breadth([], social, ["stale beans"]) is None


def test_breadth_counts_generic_posts_too():
    posts = [SimpleNamespace(post_id="h1", author="hn_user", subreddit=None,
                             platform="hackernews",
                             created_utc=datetime(2026, 2, 1, tzinfo=timezone.utc))]
    social = SimpleNamespace(reddit_posts=[], generic_posts=posts)
    pains = [_pain("stale beans", ["h1"])]
    breadth = compute_evidence_breadth(pains, social, ["stale beans"])
    assert breadth["posts"] == 1
    assert breadth["distinct_communities"] == 1  # the platform counts as the community


def test_confidence_miss_never_lowers():
    breadth = {"posts": 9, "distinct_authors": 6, "distinct_communities": 3,
               "months_spanned": 5, "label": "x"}
    band_hit, _ = compute_evidence_confidence(breadth, "none found")
    band_none, _ = compute_evidence_confidence(breadth, None)
    assert band_hit == band_none == "High"


# ── verdict-trigger competitor row + de-stutter + stronger_pain_count (Maya pass) ──

def test_verdict_incumbent_promoted_from_full_map():
    """The old [:6] cap sliced off the very vendor the verdict named (run 6: Rentec
    Direct at index 6). Full map emits; the trigger row is promoted, keeping its
    real pricing/gap — never re-synthesized thinner."""
    seed = _idea(incumbent_parity="shipped by Rentec: Rentec offers RUBS billing",
                 **SEED_KW)
    state = _state([seed])
    state.niche_incumbent_map = (
        [{"name": f"Filler{i}", "pricing": "unknown", "focus": "f", "gap": None}
         for i in range(6)]
        + [{"name": "Rentec", "pricing": "$45/mo", "focus": "property mgmt suite",
            "gap": "no meter photos"}])
    block = build_idea_validation_block(state, "validate_idea")
    comp = block["competitors"]
    assert len(comp) == 7
    first = comp[0]
    assert first["name"] == "Rentec"
    assert first["verdict_trigger"] is True
    assert "synthesized" not in first
    assert first["price_note"] == "$45/mo"
    assert first["gap"] == "no meter photos"
    assert [c["name"] for c in comp[1:]] == [f"Filler{i}" for i in range(6)]


def test_verdict_incumbent_synthesized_when_truly_absent():
    """Vendor genuinely absent from the map → synthesized front row with de-echoed
    evidence and no fabricated price/gap/url."""
    seed = _idea(incumbent_parity="shipped by GhostCo: GhostCo ships the mechanism",
                 **SEED_KW)
    block = build_idea_validation_block(_state([seed]), "validate_idea")
    first = block["competitors"][0]
    assert first["name"] == "GhostCo"
    assert first["synthesized"] is True
    assert first["verdict_trigger"] is True
    assert first["what_they_ship"] == "ships the mechanism"
    assert first["price_note"] is None
    assert first["gap"] is None
    assert first["url"] is None
    # the map's own row is still there, after the synthesized one
    assert block["competitors"][1]["name"] == "RoasterTools"


def test_verdict_incumbent_fuzzy_match_promotes_not_duplicates():
    """Dext-commerce case: stamp vendor 'Dext Commerce' vs map row 'Dext' — promote
    the real row instead of synthesizing a near-duplicate."""
    seed = _idea(incumbent_parity="partial by Dext Commerce: reconciles orders",
                 **SEED_KW)
    state = _state([seed])
    state.niche_incumbent_map = [{"name": "Dext", "pricing": "$30/mo",
                                  "focus": "bookkeeping automation", "gap": "g"}]
    block = build_idea_validation_block(state, "validate_idea")
    comp = block["competitors"]
    assert len(comp) == 1
    assert comp[0]["name"] == "Dext"
    assert comp[0]["verdict_trigger"] is True
    assert "synthesized" not in comp[0]


def test_placeholder_vendors_never_make_rows():
    seed = _idea(incumbent_parity="substitute (DIY): spreadsheets cover it", **SEED_KW)
    block = build_idea_validation_block(_state([seed]), "validate_idea")
    assert not any(c.get("verdict_trigger") for c in block["competitors"])


def test_space_detail_and_demotion_reason_humanized_raw_stamp_kept():
    """Subject-echo stamps ('shipped by X: X offers …') display as the evidence
    sentence alone — the answer chip carries the class; 'shipped by X: offers …'
    read as a broken template stitch (two independent audits)."""
    stamp = "shipped by Rentec: Rentec offers RUBS billing"
    seed = _idea(incumbent_parity=stamp, candidate_status="demoted", **SEED_KW)
    state = _state([seed])
    state.idea_ruled_out = [{
        "idea_id": "id-1",
        "reason": f"Already well-served — {stamp}. A new entrant competes head-on."}]
    block = build_idea_validation_block(state, "validate_idea")
    parts = {p["key"]: p for p in block["parts"]}
    assert parts["space_occupied"]["detail"] == "Rentec offers RUBS billing"
    # embedded stamp humanized AND the stored lead's em-dash retired (rule 24)
    assert block["demotion_reason"] == ("Already well-served: Rentec offers RUBS "
                                        "billing. A new entrant competes head-on.")
    # the raw stamp stays raw for every prefix-parsing consumer
    assert block["incumbent_parity"] == stamp


def test_display_parity_label_comma_and_no_echo_forms():
    from nicheiq.report.idea_validation_block import _display_parity

    # label echo: duplicate label dropped, stamp form kept
    assert _display_parity("shipped by PepLab: PepLab: peptide database") == (
        "shipped by PepLab: peptide database")
    # comma appositive is a valid sentence, never treated as a label
    assert _display_parity("shipped by Dext: Dext, a bookkeeping suite, ships it") == (
        "Dext, a bookkeeping suite, ships it")
    # no echo: stamp verbatim
    assert _display_parity("shipped by MoeGo: Smart Schedule route optimization") == (
        "shipped by MoeGo: Smart Schedule route optimization")
    # a DIFFERENT vendor named mid-evidence never triggers humanization
    assert _display_parity("shipped by MoeGo: Gingr ships this too") == (
        "shipped by MoeGo: Gingr ships this too")
    # evidence that is ONLY the vendor name: stamp kept (never an empty display)
    assert _display_parity("shipped by PepLab Platform: PepLab Platform:") == (
        "shipped by PepLab Platform: PepLab Platform:")
    # nested-paren vendor, subject echo
    assert _display_parity(
        "bundled_free (Pep (pepdose.com)): Pep (pepdose.com) bundles it free") == (
        "Pep (pepdose.com) bundles it free")
    assert _display_parity("none found") == "none found"


def test_pivot_trigger_finding_humanized_without_mutating_state():
    seed = _idea(**SEED_KW)
    state = _state([seed])
    state.user_idea_pivot = {
        "attempted": True, "outcome": "rejected",
        "trigger_finding": "shipped by X: X ships it", "because": None,
        "keeps": None, "changes": None, "reason_not_shown": "r",
        "ries_label": None, "name": None, "trigger_incumbent": "X"}
    block = build_idea_validation_block(state, "validate_idea")
    assert block["pivot"]["trigger_finding"] == "X ships it"
    assert state.user_idea_pivot["trigger_finding"] == "shipped by X: X ships it"


def test_stronger_pain_count_counts_only_above_anchored_max():
    pains = [_pain("anchored pain", ["p1"], severity=0.3),
             _pain("stronger one", ["p2"], severity=0.5),
             _pain("stronger two", ["p3"], severity=0.9),
             _pain("weaker", ["p4"], severity=0.2)]
    seed = _idea(pain_points_addressed=["anchored pain"], **SEED_KW)
    block = build_idea_validation_block(_state([seed], pains=pains), "validate_idea")
    assert block["stronger_pain_count"] == 2


def test_stronger_pain_count_zero_for_unanchored_seed():
    """No anchored severities → 0, never 'every pain in the market'."""
    pains = [_pain("a", ["p1"], severity=0.9), _pain("b", ["p2"], severity=0.8)]
    seed = _idea(pain_points_addressed=[], unanchored_hypothesis=True, **SEED_KW)
    block = build_idea_validation_block(_state([seed], pains=pains), "validate_idea")
    assert block["stronger_pain_count"] == 0


def test_quote_leading_markers_stripped_for_display():
    """Reddit list/quote markers ('>', '*', '-') are presentation debris; mid-quote
    formatting stays verbatim."""
    pains = [_pain("anchored pain", ["p1"], severity=0.5,
                   quotes=("* Whole house duct cleaning $475 * Utility bills $79",
                           "> quoted complaint text"))]
    seed = _idea(pain_points_addressed=["anchored pain"], **SEED_KW)
    block = build_idea_validation_block(_state([seed], pains=pains), "validate_idea")
    quotes = block["anchored_pains"][0]["quotes"]
    assert quotes[0].startswith("Whole house duct cleaning")
    assert "* Utility bills $79" in quotes[0]  # mid-quote markers verbatim
    assert quotes[1] == "quoted complaint text"


def test_reorder_anchored_pain_quotes_puts_idea_relevant_first():
    from nicheiq.report.idea_validation_block import reorder_anchored_pain_quotes

    seed = _idea(pain_points_addressed=["anchored pain"], **SEED_KW)
    state = _state([seed])
    state.user_idea_identity_terms = {
        "mechanism": ["utility bill splitting"], "problem": ["move-out disputes"],
        "audience": [], "delivery": []}
    pain_dicts = [
        {"title": "anchored pain", "representative_quotes": [
            "I switched property software twice",
            "double entry accounting is essential",
            "late fees pile up",
            "landlord here, no idea how to handle it",
            "splitting the utility bill between tenants causes move-out disputes",
        ]},
        {"title": "other pain", "representative_quotes": ["b", "a"]},
    ]
    reorder_anchored_pain_quotes(state, pain_dicts)
    # The idea-relevant excerpt (was 5th, invisible behind the card's 3-slice) leads.
    assert pain_dicts[0]["representative_quotes"][0] == (
        "splitting the utility bill between tenants causes move-out disputes")
    # Non-anchored pains keep their own order.
    assert pain_dicts[1]["representative_quotes"] == ["b", "a"]


def test_reorder_anchored_pain_quotes_noop_without_validate_state():
    from nicheiq.report.idea_validation_block import reorder_anchored_pain_quotes

    state = _state([_idea()])
    state.user_idea_text = None
    pain_dicts = [{"title": "anchored pain",
                   "representative_quotes": ["z", "a"]}]
    reorder_anchored_pain_quotes(state, pain_dicts)
    assert pain_dicts[0]["representative_quotes"] == ["z", "a"]


def test_promoted_trigger_row_carries_verdict_evidence():
    """The map's focus is often broader than the killing capability — the promoted
    row must substantiate the verdict with the parity evidence itself."""
    seed = _idea(incumbent_parity="shipped by Rentec: Rentec ships RUBS billing and CAM",
                 **SEED_KW)
    state = _state([seed])
    state.niche_incumbent_map = [{"name": "Rentec", "pricing": "$45/mo",
                                  "focus": "property mgmt suite", "gap": None}]
    block = build_idea_validation_block(state, "validate_idea")
    row = block["competitors"][0]
    assert row["verdict_trigger"] is True
    assert row["verdict_evidence"] == "ships RUBS billing and CAM"
    assert row["what_they_ship"] == "property mgmt suite"  # map focus untouched


def test_verdict_evidence_keeps_comma_appositive_whole():
    from nicheiq.report.idea_validation_block import _verdict_evidence_fragment

    assert _verdict_evidence_fragment("Dext", "Dext, a bookkeeping suite, ships it") == (
        "Dext, a bookkeeping suite, ships it")
    assert _verdict_evidence_fragment("Rentec", "Rentec ships RUBS billing") == (
        "ships RUBS billing")
    assert _verdict_evidence_fragment("Rentec", "Gingr ships this") == "Gingr ships this"
    assert _verdict_evidence_fragment("Rentec", "") is None
