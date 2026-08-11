"""D1 hardening round — the four holes the round-16 critic left on its own follow-up list.

D1 itself is closed. Nothing here reopens it: the corpus is still clean, the wallet-derived code
contract on `pricing_model` still holds, and the restored guidance is still restored. These are
the ways the *mechanisms* that close it could be walked around, each with the case that walks
around it and the case that must keep passing beside it.

  * The rival hatch (`_ZERO_PRICE_AS_RIVAL_RE`) over-suppressed. `more than` and `above` are
    degree adverbs far more often than competition markers, and the right-side predicate rule
    labelled a RECOMMENDATION as the competition.
  * The selection-verb branch of `_RECOMMENDATION_MOOD_RE` was anchored at `^` with no allowance
    for a leading clause, which the imperative branch beside it has always had. Any fronted
    clause defeated it.
  * `pricing_rationale` is rendered to the reader directly under `pricing_model` and nothing
    scanned it, so a run held to a priced model by the field contract could still tell the reader
    to give the product away in the paragraph beneath it.
  * `parse_market_wallet_line` partitioned on the em dash alone.
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.pricing_strategy_crew as psc
from nicheiq.crews.pricing_strategy_crew import PricingStrategyCrew
from nicheiq.utils import niche_difficulty as nd
from nicheiq.utils.market_brief import WALLET_LINE_PREFIX, parse_market_wallet_line

# --------------------------------------------------------------------------------------------
# The rival hatch: what it must stop suppressing, and what it must keep suppressing.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prescription", [
    # A degree adverb inside the 60-character governor window of "free". Nothing here is a
    # comparison with a rival; the sentence picks the free shape and says so.
    "More than anything, the best route is a free sponsor-funded tool.",
    "Above all, the sensible play is a free sponsor-funded tool.",
    # The right-side predicate rule reading the RECOMMENDATION as the competition: the sentence
    # calls the free shape the alternative and then hands it back as the thing to ship.
    "A free community edition is the real alternative you should ship.",
    "An ad-supported free tier is the real substitute here, so you should give it away.",
])
def test_the_rival_hatch_no_longer_suppresses_a_prescription(prescription):
    assert nd.has_zero_price_prescription(prescription), prescription


@pytest.mark.parametrize("report", [
    # The comparative with a real rival on the other side of it — the reason `more than` was in
    # the list at all. Deleting it outright would have cost this.
    "Any paid version should be worth more than the free DIY routine it replaces.",
    "A paid product here must beat that free route on convenience and completeness.",
    # The right-side role assignment, still doing its job: the free route is named as the
    # competition and the sentence stops there.
    "report that the free/DIY route is the real competitor here, not another startup.",
    "Open-source alternatives are the benchmark this has to clear, so the bar is completeness.",
])
def test_the_rival_hatch_still_lets_a_report_name_the_free_route(report):
    assert not nd.has_zero_price_prescription(report), report


def test_the_restored_guidance_is_still_publishable():
    """The whole point of the hatch. These four are guidance, not licenses, and stay restored."""
    for restored in (
        nd._SUBSTITUTE_CHALLENGE,
        nd._EPISODIC_CHALLENGE,
        nd._ADJACENT_MONEY_CHALLENGE,
        nd._BUYER_CLASS_NOTES["indie-hobbyist"],
    ):
        assert not nd.has_zero_price_prescription(restored), restored
        assert nd._paying_wallet_copy_rule_labels(restored) == [], restored


def test_a_governed_mention_still_cannot_license_an_ungoverned_one():
    assert nd.has_zero_price_prescription("You should beat the free route by giving it away.")


# --------------------------------------------------------------------------------------------
# The `^` anchor: a leading clause is not a licence to prescribe.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prescription", [
    "Subscriptions churn here; prefer a free community edition.",
    "Given the cadence, favor a free sponsor-funded tool.",
    "Because nobody renews, opt for an ad-supported free tool.",
])
def test_a_fronted_clause_no_longer_defeats_the_selection_verb(prescription):
    assert nd.has_zero_price_prescription(prescription), prescription


@pytest.mark.parametrize("report", [
    # A SUBJECT in front of the verb is still a report about the market, which is what the anchor
    # was there to protect. The allowance requires a punctuated clause, and a subject is not one.
    "Buyers favor free tools.",
    "In this niche, buyers favor free tools.",
    "Open-source alternatives already cover it.",
    "Most operators here prefer a free spreadsheet.",
])
def test_the_allowance_does_not_turn_a_market_report_into_advice(report):
    assert not nd.has_zero_price_prescription(report), report


@pytest.mark.parametrize("pricing_opinion", [
    # `one-time` is in the object list because a non-recurring price is a weaker wallet claim
    # than a subscription — but it is still a PRICE, and swapping one paid shape for another is a
    # pricing opinion. This is what `_EPISODIC_CHALLENGE` says, now that the fronted clause no
    # longer hides its mood.
    "Subscriptions churn in that shape; favor one-time purchases, credits, or usage-based pricing.",
    "Given the cadence, prefer a lifetime licence over per-seat billing pricing.",
])
def test_swapping_one_paid_shape_for_another_is_not_a_zero_price_prescription(pricing_opinion):
    assert not nd.has_zero_price_prescription(pricing_opinion), pricing_opinion


@pytest.mark.parametrize("prescription", [
    # ...and one genuinely unpriced object in the same list takes the exemption straight back.
    "Most products here are used episodically. Favor one-time purchases, credits, or a lead-gen "
    "tool.",
    "Perpetual licences suit these operators better than recurring billing.",
    "A one-time licence fits this audience better than a monthly plan.",
])
def test_the_paid_shape_exemption_does_not_cover_an_unpriced_object(prescription):
    assert nd.has_zero_price_prescription(prescription), prescription


# --------------------------------------------------------------------------------------------
# Stage 7's other report-visible money output: the rationale paragraph.
# --------------------------------------------------------------------------------------------

_PAYING = f"{WALLET_LINE_PREFIX}paying — $99-399/mo DaySmart Vet, $150/mo ezyVet"
_PRICED_MIXED = f"{WALLET_LINE_PREFIX}mixed — Truckstop $42-159/mo, many run on spreadsheets"
_FREE_CULTURE = f"{WALLET_LINE_PREFIX}free-culture — every established route here is free"

_PRESCRIBING_RATIONALE = (
    "WTP is thin across these clinics, so the honest play is a free tool funded by affiliate "
    "links rather than a monthly subscription."
)
_PRICED_RATIONALE = (
    "Incumbents publish $99-399/mo, so a $79/mo Starter undercuts them while keeping a price on "
    "every tier; the free tier exists only to qualify leads for the paid ones."
)


def _crew(wallet_line: str) -> PricingStrategyCrew:
    crew = PricingStrategyCrew.__new__(PricingStrategyCrew)
    crew._wallet_reading = psc.parse_market_wallet_line(wallet_line)
    return crew


def _output(model: str, rationale: str):
    return SimpleNamespace(
        pydantic=SimpleNamespace(
            pricing_model=model, pricing_rationale=rationale, solution_name="X"
        )
    )


@pytest.mark.parametrize("wallet_line", [_PAYING, _PRICED_MIXED])
def test_the_guardrail_refuses_a_rationale_that_gives_the_product_away(wallet_line):
    """A priced `pricing_model` is not a defence when the paragraph under it says otherwise."""
    payload = _output("Freemium", _PRESCRIBING_RATIONALE)
    ok, reason = _crew(wallet_line)._wallet_contract_guardrail(payload, payload)
    assert ok is False
    assert "pricing_rationale" in reason
    # A guardrail cannot repair output, so the refusal has to tell the model what to do instead.
    assert "verified prices" in reason


@pytest.mark.parametrize("wallet_line", [_PAYING, _PRICED_MIXED])
def test_the_guardrail_leaves_a_priced_rationale_alone(wallet_line):
    payload = _output("Freemium", _PRICED_RATIONALE)
    assert _crew(wallet_line)._wallet_contract_guardrail(payload, payload) == (True, payload)


def test_a_free_shape_rationale_survives_where_no_price_was_verified():
    """Symmetric with the `pricing_model` gate: a free-culture niche may say it is free."""
    payload = _output("Ad-Supported-Free", _PRESCRIBING_RATIONALE)
    assert _crew(_FREE_CULTURE)._wallet_contract_guardrail(payload, payload) == (True, payload)


def test_an_absent_wallet_reading_does_not_arm_the_rationale_check_either():
    payload = _output("Freemium", _PRESCRIBING_RATIONALE)
    assert _crew("")._wallet_contract_guardrail(payload, payload) == (True, payload)


def test_the_same_violation_backs_the_discard_path():
    """`analyze()` and the guardrail ask one function, so retry and discard cannot disagree."""
    violation = PricingStrategyCrew._wallet_contract_violation(
        "Freemium", _PRESCRIBING_RATIONALE, "paying", "$99-399/mo DaySmart Vet"
    )
    assert violation and "pricing_rationale" in violation
    assert PricingStrategyCrew._wallet_contract_violation(
        "Freemium", _PRICED_RATIONALE, "paying", "$99-399/mo DaySmart Vet"
    ) is None
    # A missing rationale is not a violation; the field contract still is.
    assert PricingStrategyCrew._wallet_contract_violation(
        "Freemium", None, "paying", "$99/mo"
    ) is None
    assert PricingStrategyCrew._wallet_contract_violation(
        "Ad-Supported-Free", None, "paying", "$99/mo"
    )


# --------------------------------------------------------------------------------------------
# ...and what that scan must NOT do: reject the modal legitimate outcome.
#
# The round that added the rationale scan armed it on token presence, so the FIELD half and the
# PROSE half of the one shared function disagreed: `Freemium` passes the field gate on a paying
# wallet and its paragraph then says "free tier", which the prose gate read as a prescription.
# `analyze()` drops a rejected result, so the solution silently lost its pricing section — 6 of
# the 44 `pricing_rationale` values in `output/final_report_*.json` fired that way, three of them
# on models that keep a price on every tier.
# --------------------------------------------------------------------------------------------

# Verbatim from shipped reports, with the `pricing_model` each was published under.
_SHIPPED_RATIONALES = [
    # output/final_report_20260121_002136.json — `\bfree\b` matched inside "ad-free browsing".
    (
        "Hybrid",
        "Make the core directory free to maximize SEO, capture long-tail task×hardware intent, "
        "and maintain parity with free competitors while monetizing power users and intent "
        "traffic. Offer a low-cost Pro subscription ($6/month) that bundles advanced exports, "
        "ad-free browsing, saved collections, and priority validation — a price positioned to "
        "convert a small share of high-intent users without blocking mass adoption. Complement "
        "subscription revenue with display ads and GPU/affiliate partnerships on free pages to "
        "monetize purchase-intent traffic.",
    ),
    # output/nicheiq_report_95b4671a-eaed-4716-9d8a-5e550485a9db.json — a free tier BESIDE a
    # priced one is what `Freemium-Lite` means.
    (
        "Freemium-Lite",
        "TechPayBenchmarks operates as a SaaS directory/aggregator hybrid targeting car repair "
        "shop managers with a strong market fit score (0.88) and moderate-to-high WTP scores "
        "(0.55-0.60) for key pain points related to compensation and turnover. Competitors like "
        "Indeed and Glassdoor monetize employer leads and enhanced profiles in the $49-$149/month "
        "range. To balance acquisition and value capture, a 2-tier Freemium-Lite model with a "
        "free tier and a paid Pro tier is optimal, pricing Starter below median competitor "
        "pricing to drive adoption while offering advanced features in Pro. Enterprise tier is "
        "not recommended due to lack of clear large-organization demand. This model aligns with "
        "WTP scores and competitive benchmarks, ensuring a viable LTV/CAC ratio.",
    ),
    # output/final_report_20260209_130409.json — the rationale for a $19/$49 subscription with NO
    # free tier, rejected for the sentence that says the free tier was left out.
    (
        "Freemium-Lite",
        "Given the moderate average WTP score of 0.42 with some high-value pain points around "
        "pricing strategy and churn management, a Freemium-Lite (2-tier) subscription model best "
        "aligns with the solo developer audience's budget sensitivity and product type. "
        "Competitors charge significantly higher prices ($149-$249/month), but those are full "
        "billing platforms, whereas SaaSPriceBumpSim offers a specialized, focused simulation and "
        "rollout planning tool. Pricing the Starter tier at $19/month (about 20% below competitor "
        "median) and Pro at $49/month provides an accessible entry point for solo founders while "
        "capturing upsell potential. The free tier is omitted to avoid devaluing the niche, but "
        "the model remains simple to reduce churn risk and acquisition friction. This model meets "
        "the mandatory LTV/CAC ratio and respects WTP signals.",
    ),
]


@pytest.mark.parametrize("model,rationale", _SHIPPED_RATIONALES)
def test_a_shipped_rationale_for_a_priced_model_is_accepted(model, rationale):
    assert PricingStrategyCrew._wallet_contract_violation(
        model, rationale, "paying", "$49-149/mo Indeed"
    ) is None, rationale


@pytest.mark.parametrize("model", sorted(
    {"Freemium", "Freemium-Lite", "Subscription", "Hybrid", "One-time", "Usage-Based"}
))
def test_the_prose_gate_never_rejects_what_the_field_gate_permits(model):
    """The two halves of one function may not disagree.

    Every model outside `ZERO_PRICE_PRICING_MODELS` keeps a price on some tier, so the paragraph
    beneath it is entitled to describe the unpriced tier of that same shape. Only prose that RULES
    OUT the audience paying contradicts the field the guardrail just let through.
    """
    assert model not in nd.ZERO_PRICE_PRICING_MODELS
    for rationale in (
        "Offer a free tier for discovery and a paid Pro tier at $29/month.",
        "The free tier is omitted to avoid devaluing the niche.",
        "Ship the directory free to everyone and monetize the traffic.",
    ):
        assert PricingStrategyCrew._wallet_contract_violation(
            model, rationale, "paying", "$99-399/mo DaySmart Vet"
        ) is None, (model, rationale)
    # ...and the rejection still is a violation, on every one of them.
    assert PricingStrategyCrew._wallet_contract_violation(
        model, _PRESCRIBING_RATIONALE, "paying", "$99-399/mo DaySmart Vet"
    )


@pytest.mark.parametrize("model", sorted(nd.ZERO_PRICE_PRICING_MODELS))
def test_a_zero_price_model_is_still_refused_on_a_paying_wallet(model):
    """The recall this narrowing rests on: the FIELD half catches the shape the prose half now
    lets through. All 11 genuine zero-price rationales in `output/final_report_*.json` were
    published under one of these two models."""
    assert PricingStrategyCrew._wallet_contract_violation(
        model,
        "An ad-supported free model monetized via display ads and affiliate links is optimal.",
        "paying",
        "$99-399/mo DaySmart Vet",
    )


# --------------------------------------------------------------------------------------------
# The two detector repairs underneath it.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("compound", [
    "Offer a Pro tier with ad-free browsing at $9/month.",
    "Ship the risk-free trial and charge from month two.",
    "Recommend a hassle-free onboarding flow, then bill for the seats.",
    "Position it as the commission-free alternative and charge a flat monthly fee.",
])
def test_an_x_free_compound_is_not_a_zero_price_object(compound):
    """`X-free` is the WITHOUT-X adjective. `\\bfree\\b` matched inside every one of them."""
    assert not nd.has_zero_price_prescription(compound), compound


@pytest.mark.parametrize("prescription", [
    # ...while the compounds whose left half is itself a price word still mean what they say.
    "Given the budgets here, default to a near-free tool funded by affiliate links.",
    "Since nobody pays, make it cost-free and monetize the traffic.",
])
def test_a_price_word_free_compound_still_reads_as_zero_price(prescription):
    assert nd.has_zero_price_prescription(prescription), prescription


@pytest.mark.parametrize("freemium", [
    "A Freemium model with a free tier and a paid Pro tier is optimal.",
    "The best route is a free community edition with a paid Pro plan at $49/month.",
])
@pytest.mark.parametrize("model", sorted(
    {"Freemium", "Freemium-Lite", "Subscription", "Hybrid", "One-time", "Usage-Based"}
))
def test_the_freemium_shape_is_accepted_where_it_is_actually_read(model, freemium):
    """The false positive round 2 chased, asserted on the path that has it.

    Round 2 answered it with an object-path exemption — any sentence whose recommended side
    carried an explicit price was excused — and that exemption re-opened D1, because the live
    defect quotes the run's own verified prices. It was never needed: the `Freemium` rationale is
    read by Stage 7, and Stage 7 asks the prose gate `rejection_only=True` for every model that
    reaches it. So this is asserted through `_wallet_contract_violation`, the only consumer that
    sees this prose, rather than through the object path no `pricing_rationale` ever takes.
    """
    assert PricingStrategyCrew._wallet_contract_violation(
        model, freemium, "paying", "$99-399/mo DaySmart Vet"
    ) is None, (model, freemium)


@pytest.mark.parametrize("prescription", [
    # A price the sentence DENIES is not a price...
    "Ship it as a permanently free tier with no paid plan behind it.",
    "Ship it as a free tool and drop the paid tiers entirely.",
    # ...and neither is one on the ruled-out side of the comparison.
    "Prefer a free sponsor-funded tool rather than a paid Pro tier at $49/month.",
    # ...and a tier is not a price: `_PAID_SHAPE_RECOMMENDED_RE` counts "tier" and "subscription",
    # so neither reading could ever have licensed these.
    "An ad-supported free tier is the real substitute here, so you should give it away.",
    "Subscriptions churn here; prefer a free community edition.",
])
def test_a_denied_or_rejected_price_never_licensed_a_prescription(prescription):
    assert nd.has_zero_price_prescription(prescription), prescription


@pytest.mark.parametrize("prescription", [
    "For a niche this price-sensitive, default to a free tool funded by affiliate links.",
    "Since WTP is thin here, open-source the whole thing.",
    "Subscriptions churn in this trade; give the tool away and monetize the traffic.",
    "With budgets this tight, hand it over to the trade association.",
])
def test_a_fronted_clause_no_longer_defeats_the_imperative_either(prescription):
    """The allowance the selection branch got in this same round, now on the branch beside it —
    six of the ten known backstop recall misses were this one shape."""
    assert nd.has_zero_price_prescription(prescription), prescription


# --------------------------------------------------------------------------------------------
# The walk-arounds a "price appears nearby" exemption bought, all ten of them.
#
# Every one of these was silent while `_priced_tier_recommended_alongside` stood. They are one
# sentence each, and each names a price that is EVIDENCE — an incumbent's, a budget, a
# competitor's, or one the sentence explicitly denies — beside a shape in which this audience
# pays nothing. They are pinned as a family because the exemption they defeat was added twice
# already, and the family is the argument against adding it a third time.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prescription", [
    # A price in a different clause is not the free thing's paid counterpart.
    "Give it away free; competitors charge $49/mo.",
    # A price in a fronted EVIDENCE clause is not the recommended price.
    "Incumbents are priced at $99/month, so the right move is a free ad-supported directory.",
    "The best route is a free lead-gen tool that undercuts the $199 incumbents.",
    "With 5000 USD of annual budget per shop, you should still open-source the whole thing.",
    "Competitors sell a paid version at $29; prefer a free community edition here.",
    "Shops already pay $129/month for scheduling, but the best route here is a free lead-gen tool.",
    "The right play is a donation-funded community tool, given that DaySmart charges $99/month.",
    # `paid for by vendor listings` is the adjacent-payer prescription, not a price.
    "For a trade this price-sensitive, the sensible shape is a free directory paid for by vendor "
    "listings.",
    # A DENIED price, which the negation window was too short to see.
    "There is no paid tier here at $49, so you should give it away free.",
    "You should give it away free, with no revenue at all from a paid plan priced at $10.",
])
def test_a_price_elsewhere_in_the_sentence_does_not_license_a_prescription(prescription):
    assert nd.has_zero_price_prescription(prescription), prescription


# --------------------------------------------------------------------------------------------
# The wallet line's own parser.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("dash", ["—", "–"])
def test_the_wallet_line_parses_either_dash(dash):
    """`build_market_brief` writes an em dash; an en dash is the substitution an editor makes
    without thinking, and partitioning on one of them put the whole line into `wallet_class`."""
    line = f"{WALLET_LINE_PREFIX}paying {dash} $99-399/mo DaySmart Vet"
    assert parse_market_wallet_line(line) == ("paying", "$99-399/mo DaySmart Vet")
