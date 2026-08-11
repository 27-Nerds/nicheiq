"""Per-clause drift detector for "Check my idea" seeds (quality pass Q4).

The load-bearing case is the LIVE one: the 056b2c68 seed kept the pitch's audience and
delivery but repositioned the mechanism, arguing AGAINST the pitch with the pitch's own
vocabulary ("… rather than a draft", "avoiding … generic AI-drafting"). A bare
shared-token check passes all clauses there; the detector must fire on mechanism only.
"""

from types import SimpleNamespace

import pytest

from nicheiq.utils.seed_fidelity import seed_clause_drift, unpitched_core_dependencies

from ..report.fixture_056b2c68 import state_from_fixture

TERMS = {
    "mechanism": ["drafts", "replies"],
    "audience": ["community managers", "small SaaS companies"],
    "problem": ["repetitive questions"],
    "delivery": ["chrome extension"],
}


def _candidate(**kw):
    base = dict(
        solution_name="ReplyBot", description="", value_proposition="",
        target_personas=[], mechanism_tag="", why_it_works="",
        innovation_angle="", technical_approach="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_live_seed_fires_on_mechanism_only():
    state = state_from_fixture()
    seed = next(i for i in state.idea_generation.solution_ideas
                if getattr(i, "source_frame", None) == "user_seed"
                and getattr(i, "generation_operation_id", None) == "validate")
    assert seed_clause_drift(state.user_idea_identity_terms, seed,
                             state.user_idea_inferred_fields) == ["mechanism"]


def test_faithful_seed_no_drift():
    cand = _candidate(
        description="A Chrome extension that drafts Reddit replies automatically.",
        value_proposition="Drafts replies to repetitive questions for community "
                          "managers at small SaaS companies.",
        target_personas=["Small SaaS community manager"])
    assert seed_clause_drift(TERMS, cand) == []


def test_additive_unpitched_core_route_is_mechanism_drift():
    """Keeping every pitch word does not permit a new external dependency to
    become the product's differentiator (live veterinary/APHIS failure)."""
    terms = {
        "mechanism": [
            "browser-based inventory reconciliation tool",
            "flags controlled-medication discrepancies",
            "generates audit-ready DEA logs",
        ],
        "audience": ["independent veterinary clinics"],
        "problem": ["controlled-medication discrepancies"],
        "delivery": ["browser-based"],
    }
    cand = _candidate(
        solution_name="AccreditedVetMapper",
        description=(
            "A browser-based inventory reconciliation tool for independent veterinary "
            "clinics that flags controlled-medication discrepancies, then maps every "
            "prescriber against the USDA APHIS accreditation directory."
        ),
        value_proposition="Generate audit-ready DEA logs with prescriber verification.",
        innovation_angle=(
            "USDA APHIS directory matching is the core differentiation and required "
            "verification step."
        ),
        data_sources=["USDA APHIS National Veterinary Accreditation Program directory"],
        market_fit_claimed_route="USDA APHIS National Veterinary Accreditation Program",
    )
    assert seed_clause_drift(terms, cand) == ["mechanism"]


def test_faithful_enrichment_and_optional_supporting_route_do_not_drift():
    terms = {
        "mechanism": ["inventory reconciliation", "flags medication discrepancies"],
        "audience": ["independent veterinary clinics"],
        "problem": ["medication discrepancies"],
        "delivery": ["browser-based"],
    }
    cand = _candidate(
        description=(
            "A browser-based inventory reconciliation workflow for independent veterinary "
            "clinics that flags medication discrepancies and keeps reviewer notes."
        ),
        value_proposition="Reconcile inventory and export a reviewable discrepancy log.",
        technical_approach=(
            "Use clinic-uploaded CSV files. An optional supporting FDA recall feed may "
            "annotate rows, but reconciliation works without it."
        ),
        data_sources=["Clinic-provided CSV files", "Optional FDA recall feed"],
    )
    assert seed_clause_drift(terms, cand) == []


def test_data_source_tag_and_single_token_vendor_cannot_hide_core_dependency():
    cand = _candidate(
        description="Reconcile uploaded invoices by matching every account through Plaid.",
        innovation_angle="Plaid is the required differentiator.",
        data_source_tag="Plaid",
    )
    assert unpitched_core_dependencies("Reconcile uploaded invoices", cand) == ["Plaid"]


def test_natural_requires_wording_preserves_a_pitched_required_route():
    cand = _candidate(
        technical_approach="Plaid API is required for every transaction match.",
        data_sources=["Plaid API"],
    )
    assert unpitched_core_dependencies(
        "A bank reconciler that requires Plaid API for every transaction match.",
        cand,
    ) == []


def test_required_external_route_cannot_hide_in_technical_copy_without_metadata():
    cand = _candidate(
        technical_approach="The product requires Plaid API for every transaction match.",
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_requires_in_supporting_copy_is_core_when_route_metadata_exists():
    cand = _candidate(
        technical_approach="The implementation requires Plaid API for every match.",
        data_sources=["Plaid API"],
        data_source_tag="Plaid",
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_negated_require_does_not_create_a_hidden_core_route():
    cand = _candidate(
        technical_approach=(
            "The product does not require Plaid API and works from uploaded CSV files."
        ),
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand) == []


@pytest.mark.parametrize("route_copy", [
    "Plaid API isn't required.",
    "The product doesn't require Plaid API.",
    "The product won't require Plaid API.",
    "The product mustn't use Plaid API.",
    "The product can work without Plaid API.",
    "The product doesn't depend on Plaid API.",
    "Plaid API is not the primary route.",
])
def test_contracted_and_near_negations_keep_external_route_optional(route_copy):
    cand = _candidate(
        technical_approach=route_copy,
        data_sources=["Plaid API"],
        data_source_tag="Plaid",
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand) == []


@pytest.mark.parametrize("route_copy", [
    "Plaid API is never required.",
    "No Plaid API is required.",
    "Plaid API is not mandatory.",
    "Plaid API is not essential.",
    "The product can operate without Plaid API.",
    "The product does not rely on Plaid API.",
    "The product is independent of Plaid API.",
    "Plaid API is secondary enrichment only.",
    "Plaid API ain’t required.",
])
def test_semantically_optional_route_wording_is_not_promoted(route_copy):
    cand = _candidate(
        technical_approach=route_copy,
        data_sources=["Plaid API"],
        data_source_tag="Plaid",
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand) == []


@pytest.mark.parametrize("route", [
    "Client-uploaded CSV",
    "Practice-uploaded CSV",
    "Owner-uploaded CSV",
    "Uploaded spreadsheet",
])
def test_general_uploaded_file_routes_are_first_party(route):
    cand = _candidate(
        technical_approach=f"Parse the {route} and reconcile rows locally.",
        data_sources=[route],
    )
    assert unpitched_core_dependencies("Reconcile uploaded records", cand) == []


def test_required_data_aggregation_must_name_a_route():
    cand = _candidate(
        technical_approach="Requires Plaid for every transaction match.",
        requires_data_aggregation=True,
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


@pytest.mark.parametrize("route", [
    "Plaid API", "TBD", "unknown", "N/A", "none", "optional", "-",
    "—", "--", "?", "T.B.D.", "N / A",
])
def test_required_data_aggregation_rejects_unpitched_or_placeholder_route(route):
    cand = _candidate(
        requires_data_aggregation=True,
        data_sources=[route],
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_route_roles_are_local_within_a_multi_route_clause():
    cand = _candidate(
        technical_approach="Plaid is optional, while Stripe is required.",
        data_sources=["Plaid API", "Stripe API"],
    )
    assert unpitched_core_dependencies("Reconcile invoices with required Stripe", cand) == []


def test_pitched_aggregation_route_does_not_need_required_wording():
    cand = _candidate(requires_data_aggregation=True, data_sources=["Plaid API"])
    assert unpitched_core_dependencies("A bank reconciler using Plaid API", cand) == []


def test_aggregation_flag_does_not_promote_an_explicitly_optional_secondary_route():
    cand = _candidate(
        requires_data_aggregation=True,
        technical_approach="Plaid API is required; Stripe API is optional enrichment.",
        data_sources=["Plaid API", "Stripe API"],
    )
    assert unpitched_core_dependencies("A bank reconciler requiring Plaid API", cand) == []


def test_group_required_quantifier_applies_to_every_named_route():
    cand = _candidate(
        technical_approach="Plaid API with Stripe API are both required.",
        data_sources=["Plaid API", "Stripe API"],
    )
    assert unpitched_core_dependencies("A bank reconciler requiring Stripe API", cand)


def test_required_aggregation_cannot_mark_every_external_route_optional():
    cand = _candidate(
        requires_data_aggregation=True,
        technical_approach="Plaid API is optional enrichment.",
        data_sources=["Plaid API"],
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


@pytest.mark.parametrize("route", ["0", "x", "id"])
def test_required_aggregation_rejects_routes_without_distinctive_identity(route):
    cand = _candidate(requires_data_aggregation=True, data_sources=[route])
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_bare_followup_role_continuation_is_attached_to_the_route():
    cand = _candidate(
        data_acquisition_notes="Plaid API is optional. Required in production.",
        data_sources=["Plaid API"],
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_followup_naming_another_route_does_not_contaminate_the_first():
    cand = _candidate(
        data_acquisition_notes="Plaid API is optional. Stripe API is required.",
        data_sources=["Plaid API", "Stripe API"],
    )
    assert unpitched_core_dependencies("A bank reconciler requiring Stripe API", cand) == []


def test_group_quantifier_stays_inside_its_adversative_segment():
    cand = _candidate(
        technical_approach=(
            "Plaid API is optional, but Stripe API and Square API are both required."
        ),
        data_sources=["Plaid API", "Stripe API", "Square API"],
    )
    seed = "A bank reconciler where Stripe API and Square API are both required."
    assert unpitched_core_dependencies(seed, cand) == []


def test_all_optional_group_cannot_satisfy_required_aggregation():
    cand = _candidate(
        requires_data_aggregation=True,
        technical_approach="Plaid API and Stripe API are both optional enrichment.",
        data_sources=["Plaid API", "Stripe API"],
    )
    seed = "Plaid API and Stripe API are both optional enrichment."
    assert unpitched_core_dependencies(seed, cand)


@pytest.mark.parametrize("route_copy", [
    "Plaid API is optional, and Stripe API and Square API are both required.",
    "Plaid API is required, and Stripe API and Square API are both optional.",
])
def test_comma_and_starts_a_new_group_scope(route_copy):
    cand = _candidate(
        technical_approach=route_copy,
        data_sources=["Plaid API", "Stripe API", "Square API"],
    )
    seed = (
        "Plaid API is optional; Stripe API and Square API are both required."
        if "Plaid API is optional" in route_copy
        else "Plaid API is required; Stripe API and Square API are both optional."
    )
    assert unpitched_core_dependencies(seed, cand) == []


def test_pitched_vendor_route_can_gain_a_descriptive_qualifier():
    cand = _candidate(
        technical_approach="Plaid Transactions API is required.",
        data_sources=["Plaid Transactions API"],
    )
    assert unpitched_core_dependencies("A bank reconciler requiring Plaid API", cand) == []


@pytest.mark.parametrize(("seed", "route"), [
    ("A safety monitor requiring the FDA recall feed.", "CPSC recall feed"),
    ("A compliance monitor requiring the SEC filings API.", "Court filings API"),
    ("A tax reconciler requiring the Stripe Tax API.", "Stripe Payments API"),
])
def test_required_route_alias_does_not_cross_product_identity(seed, route):
    cand = _candidate(
        technical_approach=f"{route} is required for every result.",
        data_sources=[route],
    )
    assert unpitched_core_dependencies(seed, cand) == [route]


@pytest.mark.parametrize(("seed", "route"), [
    (
        "A compliance monitor for CPSC teams requiring the FDA recall feed.",
        "CPSC recall feed",
    ),
    (
        "A Stripe tax reconciler requiring the Avalara payments API.",
        "Stripe Payments API",
    ),
])
def test_route_words_elsewhere_in_the_pitch_do_not_authorize_a_new_route(seed, route):
    cand = _candidate(
        technical_approach=f"{route} is also required for every result.",
        data_sources=[route],
    )
    assert unpitched_core_dependencies(seed, cand) == [route]


def test_multiword_vendor_route_can_gain_a_descriptive_qualifier():
    cand = _candidate(
        technical_approach="Google Maps Places API is required.",
        data_sources=["Google Maps Places API"],
    )
    assert unpitched_core_dependencies(
        "A territory planner requiring Google Maps API",
        cand,
    ) == []


@pytest.mark.parametrize(("seed", "route"), [
    ("A reconciler requiring Plaid API.", "Plaid + Stripe API"),
    ("A reconciler requiring Plaid API.", "Plaid/Stripe API"),
    ("A territory planner requiring Google Maps API.", "Google Maps + Mapbox API"),
])
def test_composite_route_cannot_inherit_one_provider_alias(seed, route):
    cand = _candidate(
        technical_approach=f"{route} is required.",
        data_sources=[route],
    )
    assert unpitched_core_dependencies(seed, cand) == [route]


@pytest.mark.parametrize("route", [
    "Plaid, Stripe API",
    "Plaid | Stripe API",
    "Plaid with Stripe API",
    "Plaid plus Stripe API",
])
def test_composite_route_connector_after_provider_prefix_is_rejected(route):
    cand = _candidate(
        technical_approach=f"{route} is required.",
        data_sources=[route],
    )
    assert unpitched_core_dependencies(
        "A reconciler requiring Plaid API.",
        cand,
    ) == [route]


@pytest.mark.parametrize(("seed", "route"), [
    ("A verifier requiring Dun & Bradstreet API.", "Dun & Bradstreet Direct+ API"),
    (
        "A monitor requiring S&P Global API.",
        "S&P Global Market Intelligence API",
    ),
])
def test_provider_punctuation_does_not_make_a_route_composite(seed, route):
    cand = _candidate(
        technical_approach=f"{route} is required.",
        data_sources=[route],
    )
    assert unpitched_core_dependencies(seed, cand) == []


def test_short_punctuated_provider_can_gain_a_descriptive_qualifier():
    cand = _candidate(
        technical_approach="AT&T Data API is required.",
        data_sources=["AT&T Data API"],
    )
    assert unpitched_core_dependencies(
        "A verifier requiring AT&T API.",
        cand,
    ) == []


def test_missing_comma_starts_new_group_when_prefix_has_a_role():
    cand = _candidate(
        technical_approach=(
            "Plaid API is optional and Stripe API and Square API are both required."
        ),
        data_sources=["Plaid API", "Stripe API", "Square API"],
    )
    seed = "Plaid API is optional; Stripe API and Square API are both required."
    assert unpitched_core_dependencies(seed, cand) == []


def test_aggregation_flag_cannot_promote_a_pitched_optional_route():
    cand = _candidate(requires_data_aggregation=True, data_sources=["Plaid API"])
    seed = "Optional Plaid API enrichment that works without it."
    assert unpitched_core_dependencies(seed, cand)


@pytest.mark.parametrize("route_copy", [
    "Plaid API is optional and Stripe API is required.",
    "Plaid API is optional yet Stripe API is required.",
    "Plaid API is optional though Stripe API is required.",
    "Plaid API is optional or Stripe API is required.",
    "Stripe API is required with Plaid API optional.",
])
def test_multi_route_conjunctions_keep_each_route_role_local(route_copy):
    cand = _candidate(
        technical_approach=route_copy,
        data_sources=["Plaid API", "Stripe API"],
    )
    assert unpitched_core_dependencies("Reconcile invoices with required Stripe API", cand) == []


@pytest.mark.parametrize(("seed", "route", "technical_approach"), [
    (
        "A reconciler where Plaid API is optional, but Stripe API is required.",
        "Plaid Transactions API",
        "Plaid Transactions API is required. Stripe API is required.",
    ),
    (
        "A dispatcher where Google Maps API is optional, but Mapbox API is required.",
        "Google Maps Places API",
        "Google Maps Places API is required. Mapbox API is required.",
    ),
])
def test_route_alias_does_not_borrow_required_role_from_another_seed_route(
    seed, route, technical_approach,
):
    cand = _candidate(
        technical_approach=technical_approach,
        data_sources=[route],
    )

    assert unpitched_core_dependencies(seed, cand) == [route]


@pytest.mark.parametrize("route_copy", [
    "Plaid API, required for every match.",
    "Plaid API is optional in theory but essential in production.",
    "Plaid API is optional. The integration is required.",
])
def test_detached_or_contradictory_required_role_is_still_required(route_copy):
    cand = _candidate(
        data_acquisition_notes=route_copy,
        data_sources=["Plaid API"],
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


@pytest.mark.parametrize("route_copy", [
    "Plaid API is not not required.",
    "Plaid API is never not required.",
    "Plaid API is anything but optional.",
    "Plaid API is far from optional.",
    "The product relies on Plaid API.",
    "Plaid API is essential.",
    "The product cannot operate without Plaid API.",
    "Plaid API is indispensable.",
    "The product is dependent on Plaid API.",
])
def test_required_role_variants_remain_required(route_copy):
    cand = _candidate(
        technical_approach=route_copy,
        data_sources=["Plaid API"],
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_required_route_cannot_hide_in_differentiation_factors():
    cand = _candidate(
        differentiation_factors=["Requires Plaid API for every transaction match."],
    )
    assert unpitched_core_dependencies("Reconcile uploaded bank transactions", cand)


def test_not_optional_overrides_optional_substring():
    cand = _candidate(
        description="A clinic ledger that uses the FDA recall feed for every result.",
        innovation_angle="The FDA recall feed is not optional; it is the core lookup.",
        data_sources=["Optional FDA recall feed"],
    )
    assert unpitched_core_dependencies("A clinic inventory ledger", cand) == [
        "Optional FDA recall feed",
    ]


def test_optional_role_in_surrounding_clause_is_supporting_not_core():
    cand = _candidate(
        description="A clinic-uploaded inventory reconciliation workflow.",
        innovation_angle=(
            "An optional supporting FDA recall feed may annotate results; the workflow "
            "works without it."
        ),
        data_sources=["FDA recall feed"],
    )
    assert unpitched_core_dependencies("Clinic-uploaded inventory reconciliation", cand) == []


def test_customer_supplied_credentials_do_not_make_external_route_first_party():
    cand = _candidate(
        description="Match every record through an external accreditation directory.",
        innovation_angle="The external directory API is the required mechanism.",
        data_sources=["Customer-supplied API key for external directory"],
    )
    assert unpitched_core_dependencies("Match uploaded clinic records", cand) == [
        "Customer-supplied API key for external directory",
    ]


def test_optional_pitched_route_cannot_be_promoted_to_required():
    cand = _candidate(
        innovation_angle="Plaid is now the required differentiator.",
        data_source_tag="Plaid",
    )
    assert unpitched_core_dependencies(
        "Reconcile invoices with an optional Plaid lookup", cand,
    ) == ["Plaid"]


def test_customer_supplied_vendor_token_is_still_an_external_dependency():
    cand = _candidate(
        innovation_angle="Plaid is required for every result.",
        data_sources=["Customer-supplied Plaid token"],
    )
    assert unpitched_core_dependencies("Reconcile uploaded invoices", cand) == [
        "Customer-supplied Plaid token",
    ]


def test_followup_pronoun_can_mark_route_optional():
    cand = _candidate(
        technical_approach="Annotate rows from an FDA recall feed. It is optional.",
        data_sources=["FDA recall feed"],
    )
    assert unpitched_core_dependencies("Reconcile clinic inventory", cand) == []


def test_negated_requirement_and_word_boundaries_do_not_create_core_route():
    cand = _candidate(
        technical_approach=(
            "The FDA feed scores risk. It must not depend on that feed for reconciliation."
        ),
        data_sources=["FDA feed"],
    )
    assert unpitched_core_dependencies("Reconcile clinic inventory", cand) == []


def test_natural_uploaded_clinic_csv_is_first_party():
    cand = _candidate(
        technical_approach="Parse the uploaded clinic CSV and reconcile rows locally.",
        data_sources=["Uploaded clinic CSV"],
    )
    assert unpitched_core_dependencies("Reconcile clinic inventory", cand) == []


def test_partial_mechanism_term_retention_is_drift():
    cand = _candidate(description="A Reddit replies analytics dashboard for moderators.")
    assert seed_clause_drift(
        {"mechanism": ["drafts Reddit replies automatically"]}, cand,
    ) == ["mechanism"]


def test_cross_niche_seed_fires_all_stated_clauses():
    # Vet-clinic pitch terms vs a coffee-market idea: zero presence on every clause.
    cand = _candidate(
        description="A green-lot marketplace dashboard for specialty coffee roasters.",
        value_proposition="Roasters see live lot availability and price history.",
        target_personas=["Specialty coffee roaster"])
    terms = {"mechanism": ["vaccination reminders"], "audience": ["veterinary clinics"],
             "problem": ["missed appointments"], "delivery": ["sms service"]}
    assert seed_clause_drift(terms, cand) == [
        "mechanism", "audience", "problem", "delivery"]


def test_repudiated_only_term_fires_clause():
    cand = _candidate(
        description="An approval ledger for community managers of small SaaS "
                    "companies, as a Chrome extension for repetitive questions.",
        technical_approach="It generates an escalation request rather than a draft, "
                          "and never posts a reply on its own.")
    # 'drafts' appears only behind a mid-sentence contrast cue -> mechanism drifted.
    assert seed_clause_drift(TERMS, cand) == ["mechanism"]


def test_sentence_initial_cue_spares_the_asserted_half():
    cand = _candidate(
        description="Rather than making you type each answer, ReplyBot drafts the "
                    "reply for you. Community managers at small SaaS companies "
                    "install it as a Chrome extension for repetitive questions.")
    assert seed_clause_drift(TERMS, cand) == []


def test_inferred_and_termless_clauses_are_skipped():
    cand = _candidate(description="Something entirely unrelated to the pitch.")
    terms = {"mechanism": [], "audience": ["veterinary clinics"],
             "problem": [], "delivery": []}
    # audience is inferred -> skipped; every other clause has no terms -> skipped.
    assert seed_clause_drift(terms, cand, inferred_fields=["audience"]) == []
    assert seed_clause_drift(None, cand) == []
