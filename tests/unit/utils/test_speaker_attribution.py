from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.models.social_content import (
    RedditComment,
    RedditPost,
    SocialContentCollection,
)
from nicheiq.utils.speaker_attribution import (
    ATTRIBUTION_VERSION,
    ParsedScale,
    _compare_segment_scale,
    _explicitly_below_target_scale,
    _has_direct_operational_control,
    _identity_matches_target_context,
    _parse_scale,
    attribute_evidence_speakers,
    find_quote_contribution,
)


QUOTE = "I reconcile every controlled drug after it is dispensed."
COMMENT_BODY = (
    "As the owner of our clinic, I manage its medication inventory. "
    "I reconcile every controlled drug after it is dispensed."
)


def _corpus() -> SocialContentCollection:
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    comment = RedditComment(
        comment_id="comment-1",
        author="clinic-owner",
        body=COMMENT_BODY,
        score=12,
        created_utc=created,
        is_submitter=True,
    )
    post = RedditPost(
        post_id="post-1",
        title="Medication count trouble",
        selftext="We keep finding count differences.",
        author="clinic-owner",
        subreddit="Veterinary",
        score=20,
        num_comments=1,
        created_utc=created,
        url="https://reddit.com/r/Veterinary/comments/post-1/example",
        comments=[comment],
    )
    return SocialContentCollection(reddit_posts=[post], total_reddit_comments=1)


def _pain():
    return SimpleNamespace(
        title="Reconcile controlled medication counts",
        representative_quotes=[QUOTE],
        source_post_ids=["post-1"],
        speaker_attributions=[],
        evidence_segments=["Independent clinic owners"],
    )


def _audience(target: str = "Independent clinic owners"):
    segment = SimpleNamespace(
        segment_name=target,
        pain_point_alignment=["Medication inventory"],
        motivation_drivers=["Audit readiness"],
        discovery_channels=["r/Veterinary"],
    )
    return SimpleNamespace(
        primary_target_segment=target,
        audience_segments=[segment],
        community_hubs=["r/Veterinary"],
    )


def test_quote_resolution_preserves_comment_author_and_submitter_provenance():
    ref = find_quote_contribution(_corpus(), "post-1", QUOTE)

    assert ref is not None
    assert ref.key == "reddit_comment:comment-1"
    assert ref.author == "clinic-owner"
    assert ref.is_submitter is True
    assert ref.content_kind == "reddit_comment"
    assert ref.text == COMMENT_BODY


def test_scale_parser_handles_every_supported_numeric_form():
    assert _parse_scale("Operators with 5-20 technicians") == ParsedScale(
        unit="technician", minimum=5, maximum=20
    )
    assert _parse_scale("Operators with 5+ employees") == ParsedScale(
        unit="employee", minimum=5, maximum=None
    )
    assert _parse_scale("Operators under 10 staff") == ParsedScale(
        unit="staff", minimum=0, maximum=10, maximum_inclusive=False
    )
    assert _parse_scale("Operators with at least 4 vets") == ParsedScale(
        unit="vet", minimum=4, maximum=None
    )
    assert _parse_scale("Operators with fewer than 8 locations") == ParsedScale(
        unit="location", minimum=0, maximum=8, maximum_inclusive=False
    )
    assert _parse_scale("Operators with 12 seats") == ParsedScale(
        unit="seat", minimum=12, maximum=12
    )
    assert _parse_scale("Operators with at least $1m revenue") == ParsedScale(
        unit="revenue", minimum=1_000_000, maximum=None
    )


def test_scale_parser_returns_none_without_one_unambiguous_typed_scale():
    assert _parse_scale("Independent operators") is None
    assert _parse_scale("Operators with 5-20") is None
    assert _parse_scale("Operators with 5 trucks and 12 beds") is None


def test_scale_comparator_requires_grounded_same_unit_disjoint_intervals():
    target = "Established operators with 5-20 technicians"

    assert _compare_segment_scale(target, "I have zero technicians") == "contradicts"
    assert _compare_segment_scale(target, "We have fewer than 5 technicians") == "contradicts"
    assert _compare_segment_scale(target, "We have 12 technicians") == "fits"
    assert _compare_segment_scale(target, "We have at least 3 technicians") == "unknown"
    assert _compare_segment_scale(target, "I have no employees") == "unknown"
    assert _compare_segment_scale(target, "I run the operation") == "unknown"
    assert _compare_segment_scale("Independent operators", "I have no technicians") == "unknown"


def test_scale_comparator_is_unit_agnostic_for_locations_and_revenue():
    assert _compare_segment_scale(
        "Regional groups with at least 4 locations", "Our group has 2 locations"
    ) == "contradicts"
    assert _compare_segment_scale(
        "Regional groups with at least 4 locations", "Our group has 7 locations"
    ) == "fits"
    assert _compare_segment_scale(
        "Businesses with at least $1m revenue", "We make $750k revenue"
    ) == "contradicts"
    assert _compare_segment_scale(
        "Businesses with at least $1m revenue", "We have 12 employees"
    ) == "unknown"


def test_scale_comparator_does_not_demote_ambiguous_or_mixed_scope_speakers():
    target = "Groups with at least 5 locations"

    assert _compare_segment_scale(target, "It is just me and a couple of guys") == "unknown"
    assert _compare_segment_scale(
        target,
        "I manage 1 location inside a 12-location group.",
    ) == "unknown"
    assert _explicitly_below_target_scale(target, "Our group operates 2 locations") is True


def test_tool_selection_plus_staff_delegation_is_buyer_candidacy_evidence():
    assert _has_direct_operational_control(
        "I need to find a program, give a staff member the tablet, and receive the report."
    ) is True
    assert _has_direct_operational_control("I need to find a program for myself.") is False


def test_deterministic_promotion_requires_a_target_context_anchor():
    assert _identity_matches_target_context(
        "I work in an independent clinic",
        "Independent clinic owners",
        "segment=Independent clinic owners",
        [],
    ) is True
    assert _identity_matches_target_context(
        "I work in a healthcare facility",
        "Independent clinic owners",
        "segment=Independent clinic owners",
        [],
    ) is False


def test_batched_attribution_stamps_quote_and_authored_contributions():
    corpus = _corpus()
    pain = _pain()
    captured_prompts: list[str] = []

    def invoke(**kwargs):
        captured_prompts.append(kwargs["prompt"])
        if kwargs["output_model"].__name__ == "_BuyerReviewResponse":
            return SimpleNamespace(reviews=[
                SimpleNamespace(
                    index=1,
                    confirmed=True,
                    segment_fit="unknown",
                    corrected_role=None,
                    rationale="The full contribution directly establishes target-side ownership.",
                ),
            ]), None
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.74,
                rationale="The speaker directly owns the target workflow.",
                identity_evidence="owner of our clinic",
                authority_evidence=None,
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.25,
                rationale="The root text does not establish purchasing authority.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ) as mocked:
        run = attribute_evidence_speakers(corpus, [pain], _audience())

    assert run.candidate_count == 2  # quoted comment + top-level sampled post
    assert run.llm_calls == 2
    assert mocked.call_count == 2
    assert pain.speaker_attributions[0].role == "buyer"
    assert pain.speaker_attributions[0].confidence == 0.74
    assert pain.speaker_attributions[0].authority_evidence is None
    assert pain.speaker_attributions[0].contribution_id == "comment-1"
    assert corpus.reddit_posts[0].comments[0].speaker_attribution.role == "buyer"
    assert corpus.reddit_posts[0].speaker_attribution.role == "unknown"
    assert corpus.speaker_attribution_version == ATTRIBUTION_VERSION
    assert corpus.speaker_attribution_target == "Independent clinic owners"
    assert '"is_submitter": true' in captured_prompts[0]
    assert '"community_is_llm_hub_prior": true' in captured_prompts[0]
    assert '"pain_provenance_includes_target": true' in captured_prompts[0]
    assert "owner of our clinic" in captured_prompts[1]


def test_failed_or_missing_results_are_durable_unknown_not_buyer():
    corpus = _corpus()
    pain = _pain()

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=RuntimeError("provider unavailable"),
    ):
        run = attribute_evidence_speakers(corpus, [pain], _audience())

    assert run.failed_batches == 1
    assert run.unknown_count == 2
    assert pain.speaker_attributions[0].role == "unknown"
    assert pain.speaker_attributions[0].confidence == 0
    assert corpus.reddit_posts[0].speaker_attribution.role == "unknown"
    assert corpus.speaker_attribution_version == ATTRIBUTION_VERSION


def test_failed_buyer_review_demotes_tentative_buyer_to_unknown():
    corpus = _corpus()
    pain = _pain()
    calls = 0

    def invoke(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("review unavailable")
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.9,
                rationale="Tentative buyer.",
                identity_evidence="owner of our clinic",
                authority_evidence=None,
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        run = attribute_evidence_speakers(corpus, [pain], _audience())

    assert run.failed_batches == 1
    assert pain.speaker_attributions[0].role == "unknown"
    assert pain.speaker_attributions[0].confidence == 0


def test_adversarial_rejection_is_authoritative_for_lead_vet_tech_selecting_software():
    corpus = _corpus()
    corpus.reddit_posts[0].comments[0].body = (
        "I am the lead vet-tech at an independent clinic. I select our inventory software "
        "and delegate the medication counts to staff, then review their reports. " + QUOTE
    )
    pain = _pain()
    review_prompts: list[str] = []

    def invoke(**kwargs):
        if kwargs["output_model"].__name__ == "_BuyerReviewResponse":
            review_prompts.append(kwargs["prompt"])
            return SimpleNamespace(reviews=[SimpleNamespace(
                index=1,
                confirmed=False,
                segment_fit="unknown",
                corrected_role="adjacent_worker",
                rationale="The speaker is a lead technician, not the target-side buyer.",
            )]), None
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="adjacent_worker",
                confidence=0.9,
                rationale="The contribution identifies a lead technician.",
                identity_evidence="lead vet-tech at an independent clinic",
                authority_evidence=None,
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience())

    assert '"tool_selection_and_staff_delegation_signal": true' in review_prompts[0]
    assert pain.speaker_attributions[0].role == "adjacent_worker"
    assert pain.speaker_attributions[0].role != "buyer", (
        "adversarial_rejection_must_override_tool_selection_and_delegation_heuristic"
    )
    assert corpus.reddit_posts[0].comments[0].speaker_attribution.role == "adjacent_worker"


def test_zero_same_unit_solo_operator_is_not_buyer_for_five_to_twenty_target():
    corpus = _corpus()
    corpus.reddit_posts[0].title = "I started an appliance repair business"
    corpus.reddit_posts[0].selftext = (
        "I automated nearly everything and have zero technicians. "
        "This is a solo operation with no other humans."
    )
    corpus.reddit_posts[0].comments[0].body = (
        "I run my appliance repair business and choose every system for the business. "
        + QUOTE
    )
    pain = _pain()
    target = "Growth-stage appliance repair operators (5-20 technicians)"
    review_prompts: list[str] = []

    def invoke(**kwargs):
        if kwargs["output_model"].__name__ == "_BuyerReviewResponse":
            review_prompts.append(kwargs["prompt"])
            return SimpleNamespace(reviews=[SimpleNamespace(
                index=1,
                confirmed=True,
                segment_fit="unknown",
                corrected_role=None,
                rationale="The speaker operates the target-side business.",
            )]), None
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.95,
                rationale="The speaker operates and buys for the business.",
                identity_evidence="run my appliance repair business",
                authority_evidence="choose every system for the business",
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience(target))

    assert '"explicit_target_segment_contradiction": true' in review_prompts[0]
    assert pain.speaker_attributions[0].role == "adjacent_worker"
    assert pain.speaker_attributions[0].role != "buyer", (
        "explicit_zero_same_unit_solo_operator_must_not_be_target_segment_buyer"
    )


def test_zero_employee_solo_operator_uses_review_not_mismatched_unit_comparison():
    corpus = _corpus()
    corpus.reddit_posts[0].title = "I started an appliance repair business"
    corpus.reddit_posts[0].selftext = (
        "I automated nearly everything and have zero employees. "
        "This is a solo operation with no other humans."
    )
    corpus.reddit_posts[0].comments[0].body = (
        "I run my appliance repair business and choose every system for the business. "
        + QUOTE
    )
    pain = _pain()
    target = "Growth-stage appliance repair operators (5-20 technicians)"
    review_prompts: list[str] = []

    def invoke(**kwargs):
        if kwargs["output_model"].__name__ == "_BuyerReviewResponse":
            review_prompts.append(kwargs["prompt"])
            return SimpleNamespace(reviews=[SimpleNamespace(
                index=1,
                confirmed=False,
                segment_fit="unknown",
                corrected_role="adjacent_worker",
                rationale="The text explicitly describes a solo operation outside the target.",
            )]), None
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.95,
                rationale="The speaker operates and buys for the business.",
                identity_evidence="run my appliance repair business",
                authority_evidence="choose every system for the business",
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience(target))

    assert '"explicit_target_segment_contradiction": false' in review_prompts[0]
    assert pain.speaker_attributions[0].role == "adjacent_worker"


def test_unstated_size_does_not_demote_confirmed_target_operator():
    corpus = _corpus()
    corpus.reddit_posts[0].comments[0].body = (
        "I run my appliance repair business and choose every system for the business. "
        + QUOTE
    )
    pain = _pain()
    target = "Growth-stage appliance repair operators (5-20 technicians)"

    def invoke(**kwargs):
        if kwargs["output_model"].__name__ == "_BuyerReviewResponse":
            return SimpleNamespace(reviews=[SimpleNamespace(
                index=1,
                confirmed=True,
                segment_fit="unknown",
                corrected_role=None,
                rationale="Scale is unstated, not contradicted.",
            )]), None
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.95,
                rationale="The speaker operates and buys for the target-side business.",
                identity_evidence="run my appliance repair business",
                authority_evidence="choose every system for the business",
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience(target))

    assert pain.speaker_attributions[0].role == "buyer"
    assert pain.speaker_attributions[0].rationale == "The speaker operates and buys for the target-side business."


def test_mismatched_unit_review_cannot_invent_a_numeric_contradiction():
    corpus = _corpus()
    corpus.reddit_posts[0].comments[0].body = (
        "I run my appliance repair business across 2 locations and choose every system. "
        + QUOTE
    )
    pain = _pain()
    target = "Growth-stage appliance repair operators (5-20 technicians)"
    review_prompts: list[str] = []

    def invoke(**kwargs):
        if kwargs["output_model"].__name__ == "_BuyerReviewResponse":
            review_prompts.append(kwargs["prompt"])
            return SimpleNamespace(reviews=[SimpleNamespace(
                index=1,
                confirmed=True,
                segment_fit="contradicts",
                corrected_role=None,
                rationale="The reviewer incorrectly compared locations with technicians.",
            )]), None
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.95,
                rationale="The speaker operates and buys for the target-side business.",
                identity_evidence="run my appliance repair business",
                authority_evidence="choose every system",
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience(target))

    assert '"deterministic_segment_fit": "unknown"' in review_prompts[0]
    assert pain.speaker_attributions[0].role == "buyer"


def test_buyer_verdict_without_grounded_target_identity_is_never_promoted():
    corpus = _corpus()
    pain = _pain()

    def invoke(**kwargs):
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.99,
                rationale="Unsupported buyer claim.",
                identity_evidence="I own this practice",
                authority_evidence="I reconcile every controlled drug",
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience())

    assert pain.speaker_attributions[0].role == "unknown"
    assert pain.speaker_attributions[0].confidence == 0.69


def test_buyer_verdict_below_calibrated_floor_remains_adjacent_worker():
    corpus = _corpus()
    pain = _pain()

    def invoke(**kwargs):
        return SimpleNamespace(attributions=[
            SimpleNamespace(
                index=1,
                role="buyer",
                confidence=0.69,
                rationale="Target membership is grounded but confidence is below the floor.",
                identity_evidence="owner of our clinic",
                authority_evidence=None,
            ),
            SimpleNamespace(
                index=2,
                role="unknown",
                confidence=0.2,
                rationale="No role evidence.",
                identity_evidence=None,
                authority_evidence=None,
            ),
        ]), None

    with patch(
        "nicheiq.utils.speaker_attribution.LLMService.invoke_structured",
        side_effect=invoke,
    ):
        attribute_evidence_speakers(corpus, [pain], _audience())

    assert pain.speaker_attributions[0].role == "adjacent_worker"
    assert pain.speaker_attributions[0].confidence == 0.69


def test_matching_target_version_is_idempotent_and_cost_free():
    corpus = _corpus()
    pain = _pain()
    corpus.speaker_attribution_version = ATTRIBUTION_VERSION
    corpus.speaker_attribution_target = "Independent clinic owners"

    with patch("nicheiq.utils.speaker_attribution.LLMService.invoke_structured") as mocked:
        run = attribute_evidence_speakers(corpus, [pain], _audience())

    assert run.changed is False
    assert run.llm_calls == 0
    mocked.assert_not_called()


def test_legacy_corpus_loads_without_attribution_fields():
    legacy = _corpus().model_dump(mode="json")
    legacy.pop("speaker_attribution_version")
    legacy.pop("speaker_attribution_target")
    for post in legacy["reddit_posts"]:
        post.pop("speaker_attribution")
        for comment in post["comments"]:
            comment.pop("speaker_attribution")

    restored = SocialContentCollection.model_validate(legacy)

    assert restored.speaker_attribution_version is None
    assert restored.reddit_posts[0].speaker_attribution is None
    assert restored.reddit_posts[0].comments[0].speaker_attribution is None
