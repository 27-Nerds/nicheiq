"""Model-authored text must reach its consumer whole.

Every assertion here is the SAME property, never the prose: a field the model wrote is
rendered into a prompt or into report JSON without a guessed char limit silently deleting
the end of it. The only permitted bound is `content_security.prompt_field`'s runaway
backstop, and when that fires it leaves a visible marker.

Real pydantic models throughout. MagicMock swallows field errors and has produced false
greens in this repo, so no test here builds its subject from one.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nicheiq.models.competitor import CompetitiveLandscape, Competitor, CompetitorType
from nicheiq.models.pain_point import OpportunityLevel, PainPoint
from nicheiq.models.research_state import CompetitiveAnalysisResult
from nicheiq.models.social_content import RedditPost, SocialContentCollection
from nicheiq.models.solution_idea import BaseSolutionIdea, RedTeamFinding
from nicheiq.utils.content_security import PROMPT_FIELD_MAX, prompt_field

# Long enough to blow past every limit this program removed (400, 300, 280, 200, 180,
# 160, 150, 120, 100, 60, 50) and still stay well under the runaway backstop.
_LONG = (
    "Operators reconcile the closed period by hand because the ledger export drops the "
    "adjustment memo, so the month-end variance they chase is an artifact of the export "
    "rather than of the books; the mechanism is a diff of two consecutive exports keyed on "
    "the immutable line id, surfaced as a review queue that names the changed field, the "
    "prior value, the new value, and the actor who changed it after close."
)


def assert_carried_whole(haystack: str, text: str, what: str) -> None:
    """`text` reached `haystack` intact, and nothing was cut without a marker."""
    assert text in haystack, (
        f"{what}: model-authored text was truncated before reaching its consumer. "
        f"len(source)={len(text)}, consumer text starts: {haystack[:200]!r}"
    )
    assert "…[truncated]" not in haystack, (
        f"{what}: runaway backstop fired on a {len(text)}-char value; it must bind only "
        f"above {PROMPT_FIELD_MAX}"
    )


def _pain(description: str = _LONG, title: str = "Closed-period edits go unnoticed") -> PainPoint:
    return PainPoint(
        title=title,
        description=description,
        mention_count=7,
        severity_score=0.8,
        commercial_intent=0.7,
        opportunity_level=OpportunityLevel.HIGH,
        representative_quotes=["we found it three weeks later"],
    )


def _idea(**over) -> BaseSolutionIdea:
    base = dict(
        solution_name="AuditLogDiff",
        description=_LONG,
        value_proposition=_LONG,
        pain_points_addressed=["Closed-period edits go unnoticed"],
        core_features=["export diff", "review queue"],
        target_personas=[_LONG],
    )
    base.update(over)
    return BaseSolutionIdea(**base)


def _landscape(desc: str = _LONG, name: str = "AuditLogDiff") -> CompetitiveAnalysisResult:
    return CompetitiveAnalysisResult(
        solution_landscapes=[
            CompetitiveLandscape(
                solution_name=name,
                competitors=[
                    Competitor(
                        name="LedgerWatch",
                        competitor_type=CompetitorType.DIRECT,
                        description=desc,
                        key_features=["diffing"],
                        pricing_model="$49/mo per entity",
                    )
                ],
                market_gaps=["no actor attribution", "no per-field diff"],
                differentiation_opportunities=["per-field diff"],
                competitive_intensity="MEDIUM",
                recommended_positioning="close-period control",
                pricing_insights="seat-priced",
            )
        ],
        top_opportunities=["per-field diff"],
        strategic_recommendations=(
            "Ship the per-field diff first and price it against the incumbent seat model."
        ),
    )


# ── the backstop itself ────────────────────────────────────────────────────────────────

def test_prompt_field_marks_the_only_cut_it_makes():
    """Every fix below leans on this: bounded, but never silently."""
    assert prompt_field(_LONG) == _LONG
    over = "x" * (PROMPT_FIELD_MAX + 50)
    assert prompt_field(over).endswith("…[truncated]")
    assert prompt_field(None) == ""


# ── prompt inputs ──────────────────────────────────────────────────────────────────────

def test_pain_description_reaches_the_pain_solution_mapper_whole():
    from nicheiq.report.utils.report_pre_compute import format_pain_point_with_scores

    out = format_pain_point_with_scores(_pain())
    assert_carried_whole(out, _LONG, "PainPoint.description -> pain_solution_mapping prompt")


def test_keyword_intent_prompt_carries_value_prop_and_niche_whole(monkeypatch):
    from nicheiq.utils.llm_service import LLMService
    from nicheiq.utils.validation import keyword_intent_validator as kiv

    seen: dict[str, str] = {}

    class _Resp:
        results: list = []

    def _capture(*, prompt, **kw):
        seen["prompt"] = prompt
        return _Resp(), None

    monkeypatch.setattr(LLMService, "invoke_structured", staticmethod(_capture))

    ctx = kiv.IdeaContext(value_proposition=_LONG, pains=["late reconciliation"], niche=_LONG)
    kiv.KeywordIntentRelevanceValidator()._grade_batch(ctx, ["audit log diff"])

    assert_carried_whole(seen["prompt"], _LONG, "IdeaContext.value_proposition/niche -> grader prompt")


def test_buyer_job_prompt_carries_pain_description_and_theme_definition_whole(monkeypatch):
    from nicheiq.utils import buyer_jobs
    from nicheiq.utils.llm_service import LLMService

    seen: dict[str, str] = {}

    def _capture(*, prompt, output_model, **kw):
        seen["prompt"] = prompt
        raise RuntimeError("stop after prompt capture")  # fail-soft path, partition unused

    monkeypatch.setattr(LLMService, "invoke_structured", staticmethod(_capture))

    theme_definition = _LONG.replace("Operators", "Reconciliation")

    class _Theme:
        category_name = "Reconciliation"
        definition = theme_definition

    buyer_jobs.classify_buyer_job_families(
        [_pain(title="a"), _pain(title="b", description=_LONG)],
        theme_categories=[_Theme()],
        niche="bookkeeping",
    )

    assert_carried_whole(seen["prompt"], _LONG, "PainPoint.description -> buyer-job prompt")
    assert_carried_whole(seen["prompt"], theme_definition, "theme definition -> buyer-job prompt")


def test_discussion_signals_carry_post_title_whole():
    from nicheiq.crews.trend_longevity_crew import TrendLongevityCrew

    title = _LONG[:280]  # a real Reddit title ceiling, far past the old 60
    posts = [
        RedditPost(
            post_id="t3_1",
            title=title,
            selftext="",
            author="u/a",
            subreddit="Accounting",
            score=120,
            num_comments=30,
            created_utc=datetime.now(timezone.utc),
            url="https://reddit.com/r/Accounting/comments/1",
        )
    ]
    signals = TrendLongevityCrew._format_discussion_trends(
        object(), SocialContentCollection(reddit_posts=posts), None
    )
    assert_carried_whole(signals, title, "RedditPost.title -> trend-longevity prompt")


def test_competitor_description_reaches_pricing_prompt_whole():
    from nicheiq.crews.pricing_strategy_crew import PricingStrategyCrew

    out = PricingStrategyCrew._extract_competitor_pricing(object(), _landscape(), "AuditLogDiff")
    assert_carried_whole(out, _LONG, "Competitor.description -> pricing prompt")


def test_competitor_description_reaches_traffic_monetization_prompt_whole():
    from nicheiq.crews.traffic_monetization_crew import TrafficMonetizationCrew

    out = TrafficMonetizationCrew._format_competitor_analysis(
        object(), _landscape(), "AuditLogDiff"
    )
    assert_carried_whole(out, _LONG, "Competitor.description -> traffic-monetization prompt")


def test_pricing_guardrail_quotes_the_models_own_rationale_whole():
    """The guardrail message is CrewAI retry feedback — the model must see what it wrote."""
    from nicheiq.crews.pricing_strategy_crew import PricingStrategyCrew

    rationale = (
        "Fund it through affiliate links instead of charging a subscription. " + _LONG
    )
    msg = PricingStrategyCrew._wallet_contract_violation(
        pricing_model="Freemium",
        pricing_rationale=rationale,
        wallet_class="paying",
        wallet_evidence="LedgerWatch $49/mo",
    )
    assert msg, "guardrail did not fire on a zero-price rationale against a verified wallet"
    assert_carried_whole(msg, rationale, "pricing_rationale -> guardrail retry feedback")


# ── report JSON / user-facing prose ────────────────────────────────────────────────────

def test_red_team_claim_reaches_the_verdict_rationale_whole():
    from nicheiq.validators.score_validators import VerdictValidator

    claim = "Verified incumbent overlap: " + _LONG
    _v, _r, _c, context = VerdictValidator().apply_red_team_downgrade(
        verdict="Go",
        risk_level="Low",
        primary_concern=None,
        red_team_verdict="killed",
        red_team_caveats=[],
        red_team_findings=[RedTeamFinding(claim=claim, kind="verified_incumbent_overlap")],
    )
    assert context, "red-team floor produced no context to render"
    assert_carried_whole(context, claim, "RedTeamFinding.claim -> go/no-go rationale")


def test_red_team_prose_caveat_reaches_the_verdict_rationale_whole():
    """Legacy prose-only checkpoints take the `caveats[0]` branch."""
    from nicheiq.validators.score_validators import VerdictValidator

    caveat = "Adversarial probe: " + _LONG
    _v, _r, _c, context = VerdictValidator().apply_red_team_downgrade(
        verdict="Go",
        risk_level="Low",
        primary_concern=None,
        red_team_verdict="weakened",
        red_team_caveats=[caveat],
        red_team_findings=None,
    )
    assert context, "red-team floor produced no context to render"
    assert_carried_whole(context, caveat, "red_team_caveats[0] -> go/no-go rationale")


def test_alternatives_one_liner_is_not_cut_at_a_guessed_width():
    from nicheiq.report.idea_validation_block import _alternatives

    out = _alternatives([_idea()])
    assert out["top"], "no alternatives rendered"
    assert_carried_whole(out["top"][0]["one_liner"], _LONG, "value_proposition -> alternatives.top")


def test_tier_strategy_survives_python_keyword_hydration():
    from nicheiq.crews.seo_strategy_crew import _hydrate_remaining_keywords

    rows = _hydrate_remaining_keywords(
        remaining=[{"keyword": "audit log diff"}],
        tier=3,
        tier_strategy=_LONG,
        lookup={"audit log diff": {"search_volume": 40, "competition": "LOW"}},
    )
    assert rows, "no keywords hydrated"
    assert_carried_whole(rows[0].strategy, _LONG, "tier strategy -> TieredKeyword.strategy")


def test_idea_tag_rationale_is_not_cut_at_a_guessed_width():
    from nicheiq.utils.idea_tags import derive_tag_facets

    tags = derive_tag_facets(_idea(), {"rationale": _LONG})
    assert_carried_whole(tags.rationale, _LONG, "IdeaTags.rationale -> 'Why these tags'")


@pytest.mark.parametrize("field_len", [PROMPT_FIELD_MAX + 1, PROMPT_FIELD_MAX + 4000])
def test_runaway_values_are_still_bounded_and_marked(field_len):
    """The fixes remove guessed limits, not the ceiling."""
    out = prompt_field("y" * field_len)
    assert len(out) <= PROMPT_FIELD_MAX + len(" …[truncated]")
    assert out.endswith("…[truncated]")


# ── the confirmed live defect: discovery_data_<job>.json, read straight by the frontend ──

def _flow_with(state):
    """A ResearchFlow whose only live part is `.state` — `_materialize_discovery_data` is a
    pure read of it, and Flow's `state` is a read-only property backed by `_state`."""
    from nicheiq.flows.research_flow import ResearchFlow

    flow = object.__new__(ResearchFlow)
    object.__setattr__(flow, "_state", state)
    flow.job_id = "job-under-test"
    return flow


def _discovery_state(*, title: str = "t", quote: str = "q", influencer_post_title: str = "i"):
    from nicheiq.models.research_state import (
        AudienceMappingResult,
        InfluencerProfile,
        InfluencerTopPost,
        PainPointAnalysisResult,
        ResearchState,
    )
    from nicheiq.models.social_content import SocialContentCollection

    state = ResearchState(niche_description="bookkeeping for small firms")
    state.audience_mapping = AudienceMappingResult(
        primary_target_segment="outsourced controllers",
        segment_prioritization_rationale="they own the close",
        community_hubs=["r/Accounting"],
        content_preferences="short checklists",
        messaging_frameworks=["close-control"],
        tools_currently_used=["QBO"],
        frustrations_with_existing=["no actor attribution"],
        recommended_channels=["reddit"],
        key_influencers=[
            InfluencerProfile(
                name="ControllerCo",
                platform="reddit",
                relevance_score=0.9,
                content_focus="month-end close",
                engagement_level="high",
                outreach_priority="high",
                top_posts=[
                    InfluencerTopPost(
                        title=influencer_post_title,
                        subreddit="Accounting",
                        score=90,
                        url="https://reddit.com/r/Accounting/comments/2",
                    )
                ],
            )
        ],
    )
    state.social_content = SocialContentCollection(
        reddit_posts=[
            RedditPost(
                post_id="t3_1",
                title=title,
                selftext="",
                author="u/a",
                subreddit="Accounting",
                score=120,
                num_comments=30,
                created_utc=datetime.now(timezone.utc),
                url="https://reddit.com/r/Accounting/comments/1",
            )
        ]
    )
    state.pain_point_analysis = PainPointAnalysisResult(
        pain_points=[
            PainPoint(
                title="Closed-period edits go unnoticed",
                description=_LONG,
                mention_count=5,
                severity_score=0.8,
                commercial_intent=0.7,
                opportunity_level=OpportunityLevel.HIGH,
                representative_quotes=[quote],
                source_post_ids=["t3_1"],
            )
        ],
        niche="bookkeeping",
        total_mentions=5,
        analysis_summary="Operators lose time reconciling edits made after the period closed.",
        top_categories=["workflow"],
    )
    return state


def _materialize(state, tmp_path):
    import json

    path = _flow_with(state)._materialize_discovery_data(str(tmp_path))
    assert path, "discovery data did not materialize"
    return json.loads(open(path).read())


def test_discovery_post_title_is_not_cut_before_the_frontend_sees_it(tmp_path):
    """`social_posts_sample[].title` is rendered verbatim in DiscoveryEvidence, which bounds
    layout in CSS. A producer-side char cut lands mid-word with no ellipsis at all."""
    title = "Anyone else reconciling " + "x" * 260 + " after close?"
    influencer_title = "Close checklist for " + "v" * 160 + " teams"
    data = _materialize(
        _discovery_state(title=title, influencer_post_title=influencer_title), tmp_path
    )

    sample = data["social_posts_sample"]
    assert sample, "no social posts sampled"
    assert_carried_whole(sample[0]["title"], title, "RedditPost.title -> discovery_data.json")

    top_posts = data["influencers"][0]["top_posts"]
    assert top_posts, "no influencer posts rendered"
    assert_carried_whole(top_posts[0]["title"], influencer_title,
                         "InfluencerTopPost.title -> discovery_data.json")


def test_discovery_quote_text_is_not_cut_before_the_frontend_sees_it(tmp_path):
    """The quote IS the evidence; half a testimonial with no marker reads as a whole one."""
    quote = "We only caught it because " + "y" * 400 + " three weeks later."
    data = _materialize(_discovery_state(quote=quote), tmp_path)

    quoted = [q for group in data["quotes"].values() for q in group]
    assert quoted, "no quotes rendered"
    assert_carried_whole(quoted[0]["text"], quote, "representative_quote -> discovery_data.json")
    assert_carried_whole(data["hero_quote"]["text"], quote, "hero quote -> discovery_data.json")


# ── report_generator -> technical blueprint crew ───────────────────────────────────────

def test_blueprint_crew_receives_the_value_proposition_whole(monkeypatch):
    """Two defects on one expression: `description[:200]` cut the fallback, and
    `A or B if C else ""` parsed as `(A or B) if C else ""` — so a solution carrying a
    value_proposition but no description handed the crew an empty string."""
    from nicheiq.crews import technical_blueprint_crew as tbc
    from nicheiq.report.report_generator import ReportGenerator

    seen: dict = {}

    class _FakeCrew:
        usage_metrics = None

        def generate(self, **kwargs):
            seen.update(kwargs)
            return None, None

    monkeypatch.setattr(tbc, "TechnicalBlueprintCrew", _FakeCrew)

    gen = object.__new__(ReportGenerator)

    # fallback path: no value_proposition, long description
    gen._generate_technical_blueprint(_idea(value_proposition=""))
    assert_carried_whole(seen["value_proposition"], _LONG,
                         "description -> blueprint crew value_proposition fallback")

    # precedence path: value_proposition present, description empty
    seen.clear()
    vp = "Names the actor behind every post-close edit."
    gen._generate_technical_blueprint(_idea(value_proposition=vp, description=""))
    assert seen["value_proposition"] == vp, (
        "a solution with a value_proposition but no description must still pass it through"
    )


# ── label slots: the bound stays, the silence does not ─────────────────────────────────

def test_buyer_job_label_slot_marks_its_cut():
    """`display_label` is a chip label AND the `family_labels` value the ideation crew reads.
    Its width is a slot bound and stays in the producer; what must not stay is a mid-word
    cut with no marker. The full title is never lost — it is `member_pain_ids`."""
    from nicheiq.utils.buyer_jobs import theme_fallback_partition

    title = "Operators cannot approve a substitute lot without re-running the whole tasting panel"
    partition = theme_fallback_partition([_pain(title=title), _pain(title="second pain")])
    family = next(f for f in partition.families if title in f.member_pain_ids)

    assert family.display_label.endswith("…"), (
        f"label slot cut without a marker: {family.display_label!r}"
    )
    assert not family.display_label.rstrip("…").endswith(" ")
    assert title.startswith(family.display_label.rstrip("…").rstrip())
    assert title in family.member_pain_ids  # the full text survives where it belongs


def test_buyer_job_label_slot_leaves_short_titles_alone():
    from nicheiq.utils.buyer_jobs import theme_fallback_partition

    title = "Substitute lot approval"
    partition = theme_fallback_partition([_pain(title=title), _pain(title="second pain")])
    family = next(f for f in partition.families if title in f.member_pain_ids)
    assert family.display_label == title
