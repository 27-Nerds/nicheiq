"""Tests for the run-level idea-portfolio summary: the deterministic digest builder
(no LLM/IO) and the name-coverage guardrail around the single grounded LLM call.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nicheiq.utils.idea_portfolio_summary import (
    build_idea_portfolio_digest,
    generate_idea_portfolio_summary,
    idea_portfolio_fingerprint,
)

# The cross-language fingerprint table lives in ONE file, read by this suite, by
# backend/src/routes/__tests__/discoveryShares.portfolioSummary.test.ts and by
# frontend/src/lib/selection/__tests__/ideaPortfolioFingerprint.test.ts. Python WRITES the
# stored fingerprint and was previously held to none of these cases, so a Python-side rule
# change could not fail any suite that mattered.
_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "ideaPortfolioFingerprintCases.json"
)
_CONTRACT = json.loads(_CONTRACT_PATH.read_text())


def _idea(name, *, status="active", source_frame=None, market_fit=0.6, market_fit_raw=None,
          risk_flags=None, pricing_shape_note=None, red_team_verdict=None, red_team_caveats=None,
          red_team_revised=None, idea_id=None, idea_revision=1):
    return SimpleNamespace(
        solution_name=name,
        candidate_status=status,
        source_frame=source_frame,
        market_fit_score=market_fit,
        market_fit_score_raw=market_fit_raw,
        seo_scalability_score=0.5,
        source_segment_payability=0.4,
        source_segment_payability_class="mixed",
        incumbent_parity=None,
        adjacent_market_parity=None,
        estimated_development_time="6-10 weeks",
        tags=SimpleNamespace(
            risk_flags=risk_flags or [], pricing_shape_note=pricing_shape_note
        ),
        red_team_verdict=red_team_verdict,
        red_team_caveats=red_team_caveats,
        red_team_revised=red_team_revised,
        idea_id=idea_id,
        idea_revision=idea_revision,
    )


def _typed_idea(
    name: str,
    *,
    headline: str,
    product: str,
    mechanism: str | None,
    market_fit: float = 0.6,
    source_frame: str | None = "pain",
    generation_operation_id: str | None = None,
):
    from nicheiq.models.solution_idea import BaseSolutionIdea

    return BaseSolutionIdea.model_construct(
        solution_name=name,
        headline=headline,
        short_description=product,
        description=product,
        core_features=[] if mechanism is None else [mechanism],
        technical_approach=mechanism,
        market_fit_score=market_fit,
        estimated_development_time="6-10 weeks",
        source_frame=source_frame,
        generation_operation_id=generation_operation_id,
    )


class TestPortfolioFingerprintContract:
    """The shared cross-language table. Same file, same cases, three implementations."""

    @pytest.mark.parametrize(
        "case", _CONTRACT["shared"], ids=[c["name"] for c in _CONTRACT["shared"]]
    )
    def test_shared_case(self, case):
        assert idea_portfolio_fingerprint(case["candidates"]) == case["fingerprint"]

    @pytest.mark.parametrize(
        "case",
        _CONTRACT["divergences"],
        ids=[c["name"] for c in _CONTRACT["divergences"]],
    )
    def test_known_divergence_from_typescript(self, case):
        """Documented, non-blocking, pinned — see each case's `verdict` in the file."""
        assert idea_portfolio_fingerprint(case["candidates"]) == case["fingerprint"]["python"]

    def test_the_float_revision_case_is_still_a_float_on_disk(self):
        """The float divergence only exists because json.load keeps 2.0 a float while
        JSON.parse collapses it to 2. Reformatting the source literal to `2` would make
        this suite agree with TypeScript for the wrong reason."""
        case = next(
            c for c in _CONTRACT["divergences"] if c["name"] == "a float revision that is integral"
        )
        revision = case["candidates"][0]["idea_revision"]
        assert isinstance(revision, float) and not isinstance(revision, int)

    def test_the_suite_reads_the_whole_table(self):
        assert len(_CONTRACT["shared"]) >= 11
        assert len(_CONTRACT["divergences"]) >= 2


class TestPortfolioFingerprint:
    def test_is_order_independent_and_excludes_hidden_ideas(self):
        alpha = _idea("Alpha", idea_id="idea-a", idea_revision=1)
        beta = _idea("Beta", idea_id="idea-b", idea_revision=2)
        hidden = _idea("Hidden", status="demoted", idea_id="idea-hidden")

        expected = '{"version":1,"ideas":[["idea-a",1],["idea-b",2]]}'
        assert idea_portfolio_fingerprint([alpha, hidden, beta]) == expected
        assert idea_portfolio_fingerprint([beta, alpha, hidden]) == expected

    def test_addition_and_revision_change_invalidate(self):
        alpha = _idea("Alpha", idea_id="idea-a", idea_revision=1)
        beta = _idea("Beta", idea_id="idea-b", idea_revision=1)
        original = idea_portfolio_fingerprint([alpha, beta])

        assert idea_portfolio_fingerprint([
            alpha, beta, _idea("Gamma", idea_id="idea-c", idea_revision=1)
        ]) != original
        beta.idea_revision = 2
        assert idea_portfolio_fingerprint([alpha, beta]) != original

    def test_missing_identity_fails_closed_without_job_id(self):
        assert idea_portfolio_fingerprint([_idea("Legacy")]) is None

    def test_initial_derivation_matches_the_phase1_identity_stamp(self):
        from nicheiq.utils.idea_identity import stamp_new_idea_identities

        ideas = [_idea("Alpha"), _idea("Hidden", status="absorbed"), _idea("Beta")]
        derived = idea_portfolio_fingerprint(ideas, job_id="job-1")
        stamp_new_idea_identities(
            "job-1", ideas, origin="phase1", operation_key="initial", force=True
        )
        assert idea_portfolio_fingerprint(ideas) == derived


class TestDigestBuilder:
    def test_includes_only_visible_ideas(self):
        ideas = [
            _idea("VisibleOne"),
            _idea("DemotedOne", status="demoted"),
            _idea("AbsorbedOne", status="absorbed"),
        ]
        digest = build_idea_portfolio_digest(ideas)
        assert "VisibleOne" in digest
        assert "DemotedOne" not in digest
        assert "AbsorbedOne" not in digest

    def test_excludes_source_frame(self):
        idea = _idea("Solo", source_frame="UNIQUE_FRAME_MARKER_XYZ")
        digest = build_idea_portfolio_digest([idea])
        assert "UNIQUE_FRAME_MARKER_XYZ" not in digest

    def test_includes_ruled_out_names_and_reasons(self):
        digest = build_idea_portfolio_digest(
            [_idea("Survivor")],
            ruled_out=[{"idea_name": "RuledOutIdea", "reason": "thin wallet"}],
        )
        assert "RuledOutIdea" in digest
        assert "thin wallet" in digest

    def test_self_score_correction_noted(self):
        idea = _idea("CorrectedIdea", market_fit=0.4, market_fit_raw=0.6)
        digest = build_idea_portfolio_digest([idea])
        assert "self-score corrected down" in digest

    def test_no_correction_note_under_threshold(self):
        idea = _idea("StableIdea", market_fit=0.5, market_fit_raw=0.55)
        digest = build_idea_portfolio_digest([idea])
        assert "self-score corrected down" not in digest

    def test_no_decimal_scores_leak(self):
        idea = _idea("BandedIdea", market_fit=0.6)
        digest = build_idea_portfolio_digest([idea])
        assert "0.6" not in digest

    def test_empty_visible_pool_returns_empty_string(self):
        assert build_idea_portfolio_digest([_idea("Gone", status="demoted")]) == ""

    def test_funnel_counts_and_wallet_included(self):
        digest = build_idea_portfolio_digest(
            [_idea("Solo")],
            funnel_counts={"winners": 3, "demoted": 1},
            niche_wallet_brief={"wallet_class": "mixed", "evidence": "priced tools exist"},
        )
        assert "winners=3" in digest
        assert "mixed" in digest
        assert "priced tools exist" in digest

    def test_includes_red_team_verdict_and_first_caveat(self):
        idea = _idea("KilledIdea", red_team_verdict="killed",
                      red_team_caveats=["free in Truckstop"])
        digest = build_idea_portfolio_digest([idea])
        assert "red-team verdict: killed" in digest
        assert "free in Truckstop" in digest

    def test_revised_clause_supersedes_stale_verdict(self):
        idea = _idea("RevisedIdea", red_team_verdict="killed",
                      red_team_caveats=["free in Truckstop"], red_team_revised=True)
        digest = build_idea_portfolio_digest([idea])
        assert "revised after red-team review" in digest
        assert "red-team verdict: killed" not in digest

    def test_weakened_verdict_still_shown_without_revision(self):
        idea = _idea("WeakenedIdea", red_team_verdict="weakened",
                      red_team_caveats=["minor overlap noted"])
        digest = build_idea_portfolio_digest([idea])
        assert "red-team verdict: weakened (minor overlap noted)" in digest


class TestGenerateSummary:
    def test_typed_candidates_publish_only_current_record_facts(self, monkeypatch):
        from nicheiq.utils import llm_service

        def _boom(**kw):
            raise AssertionError("typed production candidates must not call a prose model")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))
        ideas = [
            _typed_idea(
                "TraumaTap",
                headline="Emergency Charge Reconciliation Layer",
                product="Captures trauma-bay actions before billing close.",
                mechanism="A treatment-event ledger reconciles performed actions to charges",
                market_fit=0.7,
            ),
            _typed_idea(
                "VetAuditMatch",
                headline="Controlled Medication Audit Matcher",
                product="Flags inventory and administration mismatches.",
                mechanism="Compares current inventory exports with medication logs",
                market_fit=0.6,
            ),
        ]

        summary, usage = generate_idea_portfolio_summary(ideas)

        assert usage is None
        assert summary is not None
        assert "Emergency Charge Reconciliation Layer" in summary
        assert "A treatment-event ledger reconciles performed actions to charges" in summary
        assert "Controlled Medication Audit Matcher" in summary
        assert "Compares current inventory exports with medication logs" in summary
        assert "TraumaTap" not in summary
        assert "VetAuditMatch" not in summary
        assert "corporate budgeting" not in summary.lower()

    def test_typed_validate_seed_uses_the_same_title_as_the_ui(self):
        idea = _typed_idea(
            "SubmittedStockCheck",
            headline="Generated Search Headline",
            product="Reconciles the clinic's controlled-medication inventory.",
            mechanism="Matches inventory exports to administration records",
            source_frame="user_seed",
            generation_operation_id="validate",
        )

        summary, _ = generate_idea_portfolio_summary([idea])

        assert summary is not None
        assert "SubmittedStockCheck" in summary
        assert "Generated Search Headline" not in summary

    def test_assigned_gap_only_kill_remains_the_grounded_recommendation(self):
        gap = _typed_idea(
            "Gap",
            headline="Gap Candidate",
            product="Reconciles public records for buyers.",
            mechanism="Matches public records to buyer workflows",
            market_fit=0.8,
        )
        gap.red_team_verdict = "killed"
        gap.red_team_findings = [{
            "kind": "evidence_gap", "claim": "Search did not establish a buyer",
        }]
        clean = _typed_idea(
            "Clean",
            headline="Clean Candidate",
            product="Tracks a smaller operational workflow.",
            mechanism="Tracks workflow events",
            market_fit=0.6,
        )

        summary, usage = generate_idea_portfolio_summary([gap, clean])

        assert usage is None
        assert summary is not None
        assert "validate Gap Candidate first" in summary

    def test_typed_candidate_without_mechanism_fails_closed_without_llm(self, monkeypatch):
        from nicheiq.utils import llm_service

        called = False

        def _boom(**kw):
            nonlocal called
            called = True
            raise AssertionError("an incomplete record must not be retried into prose")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))
        summary, usage = generate_idea_portfolio_summary([
            _typed_idea(
                "ThinRecord",
                headline="Thin Current Record",
                product="A recorded product fact.",
                mechanism=None,
            )
        ])

        assert summary is None
        assert usage is None
        assert called is False

    def test_commercial_copy_guard_still_rejects_a_bad_deterministic_renderer(
        self, monkeypatch
    ):
        from nicheiq.utils import idea_portfolio_summary as portfolio

        monkeypatch.setattr(
            portfolio,
            "_grounded_candidate_sentence",
            lambda idea: (
                "Current Display Title: Recorded product. Recorded mechanism: ledger. "
                "Give the product away and monetise referrals."
            ),
        )
        summary, _ = generate_idea_portfolio_summary(
            [
                _typed_idea(
                    "InternalCode",
                    headline="Current Display Title",
                    product="Recorded product.",
                    mechanism="ledger",
                )
            ],
            niche_wallet_brief={
                "wallet_class": "paying",
                "evidence": "$99-399/mo incumbent software",
            },
        )

        assert summary is None

    def test_empty_pool_skips_llm(self, monkeypatch):
        from nicheiq.utils import llm_service

        called = False

        def _boom(**kw):
            nonlocal called
            called = True
            raise AssertionError("should not be called")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))
        summary, usage = generate_idea_portfolio_summary([_idea("X", status="demoted")])
        assert summary is None and usage is None and called is False

    def test_success_on_first_attempt(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        text = "AlphaTool and BetaTracker both show moderate market fit. Validate AlphaTool first."
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary=text), SimpleNamespace(to_dict=lambda: {}))),
        )
        summary, usage = generate_idea_portfolio_summary(ideas)
        assert summary == text
        assert usage is not None

    def test_missing_name_retries_then_succeeds(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            if len(calls) == 1:
                return SimpleNamespace(summary="Only AlphaTool is discussed here."), None
            return SimpleNamespace(
                summary="AlphaTool and BetaTracker are both covered in this rewrite."
            ), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert len(calls) == 2
        assert "DID NOT MENTION" not in calls[0]  # first prompt is the base prompt
        assert "DID NOT MENTION" in calls[1]
        assert "BetaTracker" in calls[1]  # the reminder names the missing idea
        assert summary is not None
        assert "AlphaTool" in summary and "BetaTracker" in summary

    def test_missing_name_after_retry_gives_up(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary="Only AlphaTool is discussed here."), None)),
        )
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert summary is None

    def test_fail_soft_on_exception(self, monkeypatch):
        from nicheiq.utils import llm_service

        def _boom(**kw):
            raise RuntimeError("no live llm in tests")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))
        ideas = [_idea("AlphaTool")]
        summary, usage = generate_idea_portfolio_summary(ideas)
        assert summary is None and usage is None


class TestCommercialCopyGuard:
    _EVIDENCE = (
        "$99-399/mo DaySmart Vet, $299/mo single-vet, $290/mo IDEXX Neo, $300/mo VetSnap"
    )

    @staticmethod
    def _paying_brief(evidence=_EVIDENCE):
        return {"wallet_class": "paying", "evidence": evidence, "free_density": "low"}

    def test_live_vet_contradiction_retries_with_exact_contract_then_passes(
        self, monkeypatch
    ):
        from nicheiq.utils import idea_portfolio_summary as portfolio
        from nicheiq.utils import llm_service
        from nicheiq.utils.niche_difficulty import paying_wallet_commercial_contract_copy

        ideas = [_idea("VetMargin Monitor"), _idea("ClinicFlow Audit")]
        before = (
            "VetMargin Monitor and ClinicFlow Audit have been restructured away from "
            "subscription pricing. Validate VetMargin Monitor first."
        )
        contract_copy = paying_wallet_commercial_contract_copy("paying", self._EVIDENCE)
        after = (
            "VetMargin Monitor and ClinicFlow Audit both warrant deeper validation. "
            f"{contract_copy} Validate VetMargin Monitor first."
        )
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary=before if len(calls) == 1 else after), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        warnings = []
        sink_id = portfolio.logger.add(
            lambda message: warnings.append(str(message)), level="WARNING"
        )
        try:
            summary, _ = generate_idea_portfolio_summary(
                ideas,
                niche="independent veterinary clinics managing medication",
                niche_wallet_brief=self._paying_brief(),
            )
        finally:
            portfolio.logger.remove(sink_id)

        assert summary == after
        assert len(calls) == 2
        assert "NICHE SPEND NORM: paying" in calls[0]
        assert self._EVIDENCE in calls[0]
        assert before not in summary
        assert "VIOLATED THE PAYING-WALLET COMMERCIAL COPY CONTRACT" in calls[1]
        assert contract_copy in calls[1]
        assert any("commercial invariant rejected" in warning for warning in warnings)

    def test_paraphrase_outside_positive_contract_fails_soft(self, monkeypatch):
        from nicheiq.utils import idea_portfolio_summary as portfolio
        from nicheiq.utils import llm_service
        from nicheiq.utils.niche_difficulty import (
            _paying_wallet_copy_rule_labels,
            paying_wallet_commercial_contract_copy,
            paying_wallet_commercial_copy_violations,
        )

        paraphrase = (
            "VetMargin Monitor and ClinicFlow Audit are worth comparing, but monthly recurring "
            "billing will not work here; give the product away and monetise referrals."
        )
        contract_copy = paying_wallet_commercial_contract_copy("paying", self._EVIDENCE)
        # "give the product away and monetise referrals" is an imperative with a
        # determiner object naming a zero-price shape — the polarity-blind prescription
        # rule catches it even though the paraphrase carries no negative word.
        assert _paying_wallet_copy_rule_labels(paraphrase) == [
            "zero-price shape prescribed for a paying niche"
        ]
        assert paying_wallet_commercial_copy_violations(
            paraphrase,
            wallet_class="paying",
            wallet_evidence=self._EVIDENCE,
            expected_copy=contract_copy,
            allow_surrounding_copy=True,
        ) == [
            "outside positive paying-wallet contract",
            "commercial copy outside sanctioned paying-wallet statement",
            "zero-price shape prescribed for a paying niche",
        ]
        assert "commercial copy outside sanctioned paying-wallet statement" in (
            paying_wallet_commercial_copy_violations(
                f"{contract_copy} {paraphrase}",
                wallet_class="paying",
                wallet_evidence=self._EVIDENCE,
                expected_copy=contract_copy,
                allow_surrounding_copy=True,
            )
        )

        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary=paraphrase), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        warnings = []
        sink_id = portfolio.logger.add(
            lambda message: warnings.append(str(message)), level="WARNING"
        )
        try:
            summary, _ = generate_idea_portfolio_summary(
                [_idea("VetMargin Monitor"), _idea("ClinicFlow Audit")],
                niche_wallet_brief=self._paying_brief(),
            )
        finally:
            portfolio.logger.remove(sink_id)

        assert summary is None
        assert len(calls) == 2
        assert sum("commercial invariant rejected" in warning for warning in warnings) == 2
        assert any("dropping summary" in warning for warning in warnings)

    def test_exact_contract_plus_euphemistic_contradiction_fails_soft(self, monkeypatch):
        from nicheiq.utils import llm_service
        from nicheiq.utils.niche_difficulty import (
            paying_wallet_commercial_contract_copy,
            paying_wallet_commercial_copy_violations,
        )

        contract_copy = paying_wallet_commercial_contract_copy("paying", self._EVIDENCE)
        contradiction = "The business should charge nothing and avoid ongoing fees."
        text = (
            "VetMargin Monitor and ClinicFlow Audit are worth comparing. "
            f"{contract_copy} {contradiction}"
        )
        assert paying_wallet_commercial_copy_violations(
            text,
            wallet_class="paying",
            wallet_evidence=self._EVIDENCE,
            expected_copy=contract_copy,
            allow_surrounding_copy=True,
        ) == [
            "commercial copy outside sanctioned paying-wallet statement",
            "anti-subscription prescription",
            "zero-price prescription",
        ]

        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary=text), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(
            [_idea("VetMargin Monitor"), _idea("ClinicFlow Audit")],
            niche_wallet_brief=self._paying_brief(),
        )

        assert summary is None
        assert len(calls) == 2

    @staticmethod
    def _inactive_wallet_briefs():
        return [
            {"wallet_class": "free-culture", "evidence": "buyers favor free tools"},
            {"wallet_class": "mixed", "evidence": "some buyers pay and some do not"},
            {"wallet_class": "paying", "evidence": ""},
            None,
        ]

    def test_non_paying_free_tool_recommendation_passes_untouched(self, monkeypatch):
        from nicheiq.utils import llm_service

        text = (
            "AlphaTool and BetaTracker fit a free-tool recommendation. Validate AlphaTool first."
        )
        for brief in self._inactive_wallet_briefs():
            calls = []

            def _fake(**kw):
                calls.append(kw["prompt"])
                return SimpleNamespace(summary=text), None

            monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
            summary, _ = generate_idea_portfolio_summary(
                [_idea("AlphaTool"), _idea("BetaTracker")],
                niche_wallet_brief=brief,
            )

            assert summary == text
            assert len(calls) == 1
            assert "COMMERCIAL COPY CONTRACT" not in calls[0]


class TestExclusionGuard:
    """Codex dual-review fix: describing a RANKED, SELECTABLE idea with exclusion
    vocabulary is state misinformation — clause-scoped, whole-word, proximity-8 guard
    with one combined retry."""

    def test_live_phrase_triggers_retry_then_clean_rewrite_passes(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool", red_team_verdict="killed"), _idea("BetaTracker")]
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            if len(calls) == 1:
                return SimpleNamespace(summary=(
                    "AlphaTool and BetaTracker were reviewed. AlphaTool was ultimately "
                    "excluded from further consideration.")), None
            return SimpleNamespace(summary=(
                "AlphaTool stays ranked and selectable, but the adversarial review "
                "refuted its premise; resolve that caveat first. BetaTracker deserves "
                "validation next.")), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert len(calls) == 2
        assert "MISSTATED THE VISIBILITY" in calls[1]
        assert "AlphaTool" in calls[1]
        assert summary is not None and "stays ranked and selectable" in summary

    def test_conflict_on_both_attempts_returns_none(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        bad = "AlphaTool and BetaTracker were graded. AlphaTool was removed from the list."
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary=bad), None)),
        )
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert summary is None

    def test_exclusion_of_non_idea_subject_in_other_clause_passes(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        text = ("We excluded pricing data from consideration. AlphaTool remains "
                "selectable and BetaTracker leads the pool.")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary=text), None)),
        )
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert summary == text

    def test_exclusion_language_about_ruled_out_idea_passes(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        ruled_out = [{"idea_name": "GammaLedger", "reason": "thin wallet"}]
        text = ("GammaLedger was excluded by the market screen. AlphaTool and "
                "BetaTracker both merit validation.")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary=text), None)),
        )
        summary, _ = generate_idea_portfolio_summary(ideas, ruled_out=ruled_out)
        assert summary == text

    def test_missing_and_exclusion_share_the_single_retry(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker"), _idea("GammaDesk")]
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            if len(calls) == 1:
                # misses GammaDesk AND misstates AlphaTool
                return SimpleNamespace(summary=(
                    "AlphaTool was dropped from the pool. BetaTracker looks strong.")), None
            return SimpleNamespace(summary=(
                "AlphaTool stays listed with an unresolved caveat. BetaTracker looks "
                "strong. GammaDesk rounds out the pool.")), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert len(calls) == 2
        assert "DID NOT MENTION" in calls[1] and "GammaDesk" in calls[1]
        assert "MISSTATED THE VISIBILITY" in calls[1] and "AlphaTool" in calls[1]
        assert summary is not None

    def test_killed_digest_line_names_visibility_state(self):
        ideas = [_idea("AlphaTool", red_team_verdict="killed",
                       red_team_caveats=["premise unproven"])]
        digest = build_idea_portfolio_digest(ideas)
        assert "killed for nomination only (premise unproven)" in digest
        assert "remains ranked and selectable" in digest
        assert "resolve the caveat before choosing" in digest


class TestCommercialShapeRemit:
    """ROUND 14 — the license to prescribe a commercial shape is withdrawn at generation.

    Six successive filters on the OUTPUT text hit a measured ceiling (a blind critic published
    13 of 14 novel non-paying shapes past the last one), because there is no closed structural
    property in surface text. The fix is that the generator was never allowed to state the
    contradiction: monetization is rendered deterministically instead.
    """

    _PAYING = {"wallet_class": "paying", "evidence": "$99-399/mo DaySmart Vet"}
    _MIXED_PRICED = {
        "wallet_class": "mixed",
        "evidence": "DaySmart Vet $116–$565/mo; quote-based pricing common",
        "free_density": "VetSoftwareHub free comparison tools",
    }
    # The live sentence from output/checkpoints/…0c9b6f29…, a MIXED run that had no contract.
    _MIXED_LIVE_PRESCRIPTION = (
        "Given these constraints, the most logical path forward is to pivot away from "
        "subscription SaaS and toward free, lead-generation tools that seed a data corpus."
    )

    @staticmethod
    def _prompt_for(monkeypatch, brief):
        from nicheiq.utils import llm_service

        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary="AlphaTool and BetaTracker both look plausible."), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        generate_idea_portfolio_summary(
            [_idea("AlphaTool"), _idea("BetaTracker")], niche_wallet_brief=brief
        )
        return " ".join(calls[0].split())

    @pytest.mark.parametrize(
        "brief",
        [
            None,
            {"wallet_class": "paying", "evidence": "$99-399/mo DaySmart Vet"},
            {"wallet_class": "mixed", "evidence": "quote-based pricing common"},
            {"wallet_class": "free-culture", "evidence": "every route here is free"},
        ],
    )
    def test_remit_paragraph_reaches_every_wallet_class(self, monkeypatch, brief):
        """The withdrawal is unconditional — a `mixed` or unknown wallet is not a licence."""
        prompt = self._prompt_for(monkeypatch, brief)
        assert "OUT OF YOUR REMIT — HOW THE PRODUCT MAKES MONEY" in prompt
        assert "Reporting is not prescribing" in prompt
        assert "MUST NOT recommend, select, rule out, or pivot" in prompt
        assert "MONETIZATION GUIDANCE" in prompt

    @pytest.mark.parametrize(
        "brief,marker",
        [
            ({"wallet_class": "paying", "evidence": "$99/mo"}, "already pay for tooling"),
            ({"wallet_class": "mixed", "evidence": "$116–$565/mo"}, "part of this niche already pays"),
            ({"wallet_class": "mixed", "evidence": "quotes only"}, "segment holding budget authority"),
            # Reports the free routes and what a product competes on; it does not tell the
            # builder to adopt a free shape (D1 round 15, Priority 1).
            ({"wallet_class": "free-culture", "evidence": "all free"},
             "convenience, completeness and trust"),
            (None, "only monetization guidance the reader gets"),
        ],
    )
    def test_monetization_guidance_is_deterministic_per_wallet_reading(self, brief, marker):
        from nicheiq.utils.idea_portfolio_summary import monetization_guidance

        line = monetization_guidance(brief)
        assert marker in line
        assert monetization_guidance(brief) == line  # no LLM, no randomness

    def test_priced_mixed_wallet_rejects_the_live_prescription_and_fails_soft(self, monkeypatch):
        """SCOPE GAP: `mixed` had no contract at all, so the identical contradiction shipped."""
        from nicheiq.utils import idea_portfolio_summary as portfolio
        from nicheiq.utils import llm_service

        text = (
            "AlphaTool and BetaTracker both face entrenched incumbents. "
            f"{self._MIXED_LIVE_PRESCRIPTION}"
        )
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary=text), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        warnings = []
        sink_id = portfolio.logger.add(
            lambda message: warnings.append(str(message)), level="WARNING"
        )
        try:
            summary, _ = generate_idea_portfolio_summary(
                [_idea("AlphaTool"), _idea("BetaTracker")],
                niche_wallet_brief=self._MIXED_PRICED,
            )
        finally:
            portfolio.logger.remove(sink_id)

        assert summary is None
        assert len(calls) == 2
        assert "RECOMMENDED A COMMERCIAL SHAPE" in calls[1]
        assert "out of your remit entirely" in calls[1]
        assert any("zero-price shape prescribed for a priced niche" in w for w in warnings)

    def test_priced_mixed_wallet_still_publishes_honest_negative_analysis(self, monkeypatch):
        """A mixed niche may report that half its buyers will not pay. Only prescribing is out."""
        from nicheiq.utils import llm_service

        text = (
            "AlphaTool and BetaTracker face well-defended incumbents, and willingness to pay "
            "for new standalone tools in these categories is quite low. AlphaTool still "
            "deserves validation first."
        )
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary=text), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(
            [_idea("AlphaTool"), _idea("BetaTracker")],
            niche_wallet_brief=self._MIXED_PRICED,
        )
        assert summary == text
        assert len(calls) == 1

    def test_unpriced_mixed_wallet_is_left_alone(self, monkeypatch):
        """The trigger is the evidence's own prices, not the classifier's bucket."""
        from nicheiq.utils import llm_service

        text = (
            "AlphaTool and BetaTracker are worth comparing. "
            f"{self._MIXED_LIVE_PRESCRIPTION}"
        )
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            return SimpleNamespace(summary=text), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(
            [_idea("AlphaTool"), _idea("BetaTracker")],
            niche_wallet_brief={"wallet_class": "mixed", "evidence": "quote-based pricing common"},
        )
        assert summary == text
        assert len(calls) == 1
