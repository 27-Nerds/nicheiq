"""D1 — the monetisation licenses in the PROMPT CORPUS, adjudicated file by file.

Round 14 withdrew the license from `utils/prompts/niche_difficulty_verdict.yaml` and searched that
one file. Round 15 found three more copies and searched two files. Round 16's blind critic named
the pattern in one line: *"Did r15 repeat r14's mistake? Yes, one level up. r14 searched one file;
r15 searched two."* Every round removed the license from wherever it had last been seen, and every
round the same license turned up in a file nobody had opened.

So this test does not read a list of files. It runs the project's OWN detector
(`_paying_wallet_copy_rule_labels`, which itself calls the polarity-blind
`has_zero_price_prescription`) over EVERY prompt in `crews/config/` and `utils/prompts/`, and
requires each hit to be adjudicated in `_ALLOWLIST` below with a written reason. A license added
tomorrow to a file this test has never heard of fails it, which is the property rounds 12-15 all
lacked.

Legitimate hits are real and numerous — enum values, output-field specs, balanced model menus, the
worked example that sits UNDER the wallet gate, and the remit paragraphs that forbid the shape by
naming it. Each is listed with the reason it is not a license. The reason is the review artifact:
an entry with no reason is not an allowlist, it is a mute.

The targeted assertions at the bottom are round 15's, kept: they pin the specific deletions and
gates that round made, which the corpus scan alone would not notice being reverted (the reverted
text would simply become another adjudicated-looking hit).
"""

import re
from pathlib import Path

import pytest

import nicheiq
from nicheiq.utils import niche_difficulty as nd

_PACKAGE = Path(nicheiq.__file__).parent
_CORPUS_ROOTS = (_PACKAGE / "crews" / "config", _PACKAGE / "utils" / "prompts")

_CONFIG = _PACKAGE / "crews" / "config"
_SOLUTION_TASKS = (_CONFIG / "unified_solution_tasks.yaml").read_text(encoding="utf-8")
_PRICING_TASKS = (_CONFIG / "pricing_strategy_tasks.yaml").read_text(encoding="utf-8")
_PRICING_AGENTS = (_CONFIG / "pricing_strategy_agents.yaml").read_text(encoding="utf-8")


def _corpus() -> dict[str, str]:
    """Every prompt file the crews and the LLM helpers load, keyed by file name."""
    return {
        path.name: path.read_text(encoding="utf-8")
        for root in _CORPUS_ROOTS
        for path in sorted(root.rglob("*.yaml"))
    }


# A prompt is markdown inside YAML block scalars, so `_commercial_sentences` alone would glue a
# whole bullet list into one "sentence" and the detector would report the list, not the line. A
# new unit starts at a blank line or at any line that opens a list item, table row, heading or
# YAML key; everything else is a continuation of the wrapped line above it.
_NEW_UNIT_RE = re.compile(
    r"^\s*(?:[-*+]\s|\|\s|#|\d+[.)]\s|\*\*|>\s|[✗✓❌✅→•]"
    r"|\w[\w .'/()-]{0,60}:\s*[>|]\s*$)"
)


def _prompt_sentences(text: str) -> list[str]:
    units: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            if current:
                units.append(" ".join(current))
                current = []
            continue
        if _NEW_UNIT_RE.match(line) and current:
            units.append(" ".join(current))
            current = []
        current.append(line.strip())
    if current:
        units.append(" ".join(current))

    sentences: list[str] = []
    for unit in units:
        sentences.extend(nd._commercial_sentences(nd._normalized_commercial_copy(unit)))
    return [sentence for sentence in sentences if sentence.strip()]


def _license_hits(sources: dict[str, str]) -> list[tuple[str, str, list[str]]]:
    """Every (file, sentence, rule labels) the project's own commercial-copy rules reject."""
    hits = []
    for name, text in sources.items():
        for sentence in _prompt_sentences(text):
            labels = nd._paying_wallet_copy_rule_labels(sentence)
            if labels:
                hits.append((name, sentence, labels))
    return hits


# --------------------------------------------------------------------------------------------
# The adjudication. `file name -> ((fragment, why this is not a license), ...)`.
#
# A fragment is matched case-sensitively against the NORMALIZED sentence (long dashes are already
# rewritten to ": " by `_normalized_commercial_copy`, so write fragments in that form). Rewording
# an adjudicated line makes its entry stale, which `test_the_allowlist_has_no_stale_entries`
# fails — deliberately: a reworded license has to be re-read by a human, not inherited.
# --------------------------------------------------------------------------------------------
_ALLOWLIST: dict[str, tuple[tuple[str, str], ...]] = {
    "data_source_tasks.yaml": (
        (
            "low/free cost",
            "The COST OF A DATA SOURCE to the builder, not the price of the product to the buyer. "
            "Different object; nothing here says what the product charges.",
        ),
    ),
    "pricing_strategy_agents.yaml": (
        (
            "whether that means subscription tiers, ad-supported free tools",
            "The agent GOAL, enumerating the full model space in one balanced list. It selects "
            "nothing and states no rule that maps a signal onto a shape.",
        ),
        (
            "from SaaS subscriptions to ad-supported free tools",
            "Backstory experience list. Same balanced menu, in the past tense, about the agent's "
            "history rather than about this niche.",
        ),
        (
            "are absent from this list ON PURPOSE",
            "The remit paragraph that FORBIDS the two zero-price models here, and says why: no "
            "backstory can see the wallet evidence, so no backstory may license them. It names "
            "the shapes in order to withhold them.",
        ),
        (
            "Always consider whether a hybrid",
            "A hybrid keeps a PAID tier by definition (freemium + affiliate, subscription + "
            "usage). This audience still pays; it is a mix question, not a zero-price one.",
        ),
        (
            "For ad-supported: Estimated traffic must justify",
            "A verification standard applied AFTER a model has been chosen — it makes the "
            "zero-price model harder to justify, never easier.",
        ),
        (
            "For affiliate: CTR and conversion assumptions",
            "Same: an evidence bar the affiliate model has to clear once selected elsewhere.",
        ),
    ),
    "pricing_strategy_tasks.yaml": (
        (
            "The two models in which THIS AUDIENCE NEVER PAYS",
            "The paragraph explaining why Ad-Supported-Free and Affiliate-Only are NOT rows in "
            "the model table. It names them to keep them out of an ungated table.",
        ),
        (
            "They are wallet-gated and live under",
            "Continuation of the same paragraph: it points at the gate rather than restating the "
            "models as options.",
        ),
        (
            "An absent probe reading is not evidence",
            "The fail-closed clause added for the absent-wallet hole. It FORBIDS the zero-price "
            "branch on a missing reading.",
        ),
        (
            "low WTP favors ad/affiliate/free models",
            "Explicitly gated in the same parenthesis: 'unless the wallet gate above applies, in "
            "which case the market's verified prices win'.",
        ),
        (
            "Where the MARKET REALITY wallet signal above shows, as a POSITIVE finding",
            "The permitted branch of the wallet gate. Its trigger is a positive, verified finding "
            "that nobody in this market pays — the one condition under which a zero-price model "
            "contradicts nothing.",
        ),
        (
            'Free tool monetized by display ads (target: $5-15 CPM)',
            "The worked example INSIDE that permitted branch. It is unreachable without the "
            "gate's condition holding.",
        ),
        (
            "This branch fails CLOSED",
            "The absent-reading branch, which forbids selecting either zero-price model.",
        ),
        (
            "Only recommend tier structure",
            "'Free/Starter/Pro/Enterprise' is the NAME of a subscription tier ladder. The free "
            "tier of a freemium product sits above paid tiers, not instead of them.",
        ),
        (
            "**For Traffic-Based Models (Ad-Supported-Free, Affiliate-Only):**",
            "Heading of the unit-economics checks a traffic model must pass once chosen. "
            "Validation of a decision, not the decision.",
        ),
        (
            "Freemium-lite or aggressive free tier",
            "A freemium free tier with paid tiers above it — this audience pays.",
        ),
        (
            "Free/Near-Free **only where the wallet gate above does not apply**",
            "The WTP-translation row whose own text carries the gate three times, including the "
            "UNAVAILABLE case.",
        ),
        (
            "Reasoning shape: Ad-Supported Free Tool",
            "A worked arithmetic example, explicitly labelled reachable only through the wallet "
            "gate.",
        ),
        (
            "Low WTP band (Free/Near-Free) AND no verified prices",
            "The example's own trigger line, and the conjunct that gates it is the wallet signal.",
        ),
        (
            "AD/AFFILIATE MONETIZATION GUIDELINES",
            "Execution detail (CPM bands, networks) for a model the gate has already permitted; "
            "the heading now says so.",
        ),
        (
            "RPM x estimated monthly pageviews",
            "An ARPU FORMULA for a chosen traffic model. Arithmetic carries no recommendation.",
        ),
        (
            "null for ad/affiliate models",
            "Output-field spec: which fields are null under which model. A schema note.",
        ),
        (
            '**pricing_model:** One of:',
            "The ENUM of `PricingStrategyResult.pricing_model`. The field's value space, which "
            "the model must be told in full or it cannot emit the paid values either.",
        ),
        (
            "FOR AD/AFFILIATE MODELS",
            "Output-shape section for the zero-price models, labelled as reachable only once the "
            "gate has permitted one.",
        ),
        (
            "null (Free tool)",
            "Output-field spec: tier prices are null on a zero-price model.",
        ),
        (
            '**pricing_model:** "Ad-Supported-Free" or "Affiliate-Only"',
            "The value to emit in that output shape — a field spec inside the gated section.",
        ),
        (
            'pricing_rationale: "100% free tool',
            "The JSON EXAMPLE of the gated output shape. It demonstrates the schema; the gate "
            "above decides whether this branch is ever entered.",
        ),
        (
            "affiliate links add",
            "Continuation of the same JSON example: the revenue formula in its rationale field.",
        ),
        (
            "low WTP + directory points to ad/affiliate ONLY where",
            "The critical-rules reminder, now carrying the gate itself: the wallet signal "
            "outranks both WTP and project type, and on paying/priced-mixed/UNAVAILABLE a priced "
            "model is required.",
        ),
        (
            "For ad/affiliate models (Ad-Supported-Free, Affiliate-Only)",
            "Heading of the closing field-format reminder, marked wallet-gated.",
        ),
    ),
    "traffic_monetization_agents.yaml": (
        (
            "Affiliate works best with purchase-intent traffic",
            "Stage 8 runs only for a project_type that has ALREADY been chosen as a traffic "
            "product, so its zero-price framing is entailed by that earlier decision rather than "
            "made here. The live D1 defect is upstream, at ideation, where project_type is "
            "steered — see `unified_solution_crew._archetype_directive`.",
        ),
    ),
    "traffic_monetization_tasks.yaml": (
        (
            "(traffic-focused, not subscription SaaS)",
            "Reports what {project_type} already IS on entry to Stage 8; it does not choose it.",
        ),
        (
            "Ads = pageviews",
            "A revenue formula for the model this stage exists to size.",
        ),
        (
            "sponsored_listing_price",
            "An output-field spec — and a PRICED one: sponsored listings are sold.",
        ),
    ),
    "niche_difficulty_verdict.yaml": (
        (
            "is NOT your job and never was",
            "The remit paragraph that FORBIDS commercial-shape selection. It has to name the "
            "shapes (subscription vs one-time vs free vs ad/sponsor/lead-gen) to withhold them.",
        ),
        (
            "FREE/DIY SUBSTITUTES",
            "The section heading of the instruction to REPORT that the free/DIY route is the real "
            "competitor. The sentence body is now recognised as a report by the rival-object rule "
            "in `has_zero_price_prescription`; the bare heading token has no object at all.",
        ),
    ),
    "report_budget_estimate.yaml": (
        (
            "| Ad-Supported-Free | $50-300/month |",
            "A marketing-budget lookup keyed by the pricing_model Stage 7 already chose. It reads "
            "the decision; it cannot make one.",
        ),
    ),
    "report_implementation_planning.yaml": (
        (
            "free/ad-supported",
            "A success-METRIC mapping keyed by the already-chosen model (traffic metrics for a "
            "traffic product). It selects what to measure, not how to charge.",
        ),
    ),
}


# --------------------------------------------------------------------------------------------
# The REACH of an adjudication.
#
# `fragment in sentence` is an unbounded substring mute. Every entry above was written about ONE
# line, but it excuses any line anywhere in the same file that happens to contain its fragment —
# so a license added tomorrow inherits a reason written about something else. Three shapes of
# that, all in files that already have entries:
#
#   * a new line built AROUND an adjudicated field spec: "`recommended_starter_price: null
#     (Free tool)` — prefer this whenever buyers are small shops";
#   * a governing verb glued in FRONT of an adjudicated object: "When WTP is low, go
#     free/ad-supported and drop the paid tiers entirely";
#   * a continuation glued ONTO an adjudicated heading, so the fragment and the license are one
#     sentence: "**For Traffic-Based Models (Ad-Supported-Free, Affiliate-Only):** and for any
#     low-WTP niche default to the free ad-supported shape rather than charging".
#
# The obvious repair — "the sentence with the fragment removed must carry no residual rule hit" —
# does not survive this corpus: these prompts legitimately name ad/affiliate/free models in
# almost every clause, so 16 of the 41 genuine hits have a residue that trips the rules on its
# own, and the repair would delete valid adjudications rather than bound them. What bounds them
# is stating which SENTENCES were adjudicated. An entry now reaches exactly the lines a human
# read; every other line in the file, including one containing the same fragment, is
# unadjudicated and fails the scan.
#
# Regenerating this list is not a way around the review: `test_every_pinned_sentence_still_earns
# _its_reason` requires each pinned sentence to still be in the corpus AND still match an entry
# whose reason explains it, and rewording a line invalidates its entry as well as its pin.
# --------------------------------------------------------------------------------------------
_ADJUDICATED_HITS: dict[str, tuple[str, ...]] = {
    'data_source_tasks.yaml': (
        '- Focus on: high priority, low complexity, low/free cost',
    ),
    'pricing_strategy_agents.yaml': (
        'goal: > Determine the optimal monetization strategy for {solution_name} that aligns '
        'pricing model with willingness-to-pay data, project type, audience behavior, and '
        'competitive landscape: whether that means subscription tiers, ad-supported free tools, '
        'affiliate monetization, usage-based billing, or a hybrid approach',
        "You've helped hundreds of startups determine their optimal revenue strategy: from SaaS "
        'subscriptions to ad-supported free tools to affiliate-driven comparison sites.',
        '- The two models in which THIS AUDIENCE NEVER PAYS: Ad-Supported-Free and '
        'Affiliate-Only: are absent from this list ON PURPOSE.',
        '- Always consider whether a hybrid (e.g., freemium + affiliate, subscription + usage) '
        'fits better',
        '- For ad-supported: Estimated traffic must justify CPM-based revenue projections',
        '- For affiliate: CTR and conversion assumptions must be realistic for the niche',
    ),
    'pricing_strategy_tasks.yaml': (
        'The two models in which THIS AUDIENCE NEVER PAYS: **Ad-Supported-Free** and',
        'They are wallet-gated and live under "For directories/aggregators/comparison-tools" '
        'below; a row here would have been readable without ever consulting the MARKET REALITY '
        'wallet signal, which is exactly how this prompt kept recommending a free product in '
        'niches whose own prices it had just quoted.',
        'An absent probe reading is not evidence that this niche does not pay, and a probe '
        'failure must never be the reason a paying niche is handed a free product.',
        'WTP signals from pain point analysis (low WTP favors ad/affiliate/free models: unless '
        "the wallet gate above applies, in which case the market's verified prices win)",
        '- Where the MARKET REALITY wallet signal above shows, as a POSITIVE finding, that no '
        'verified prices exist (`free-culture`, or a `mixed` reading that quotes no price '
        'figure): Ad-Supported-Free, Affiliate-Only and Hybrid are strong candidates, and such a '
        'tool can be 100% FREE to users with SEO-driven traffic monetization.',
        'Example: "Free tool monetized by display ads (target: $5-15 CPM) and affiliate links"',
        'This branch fails CLOSED: do not select Ad-Supported-Free or Affiliate-Only on an absent '
        'wallet reading.',
        '- Only recommend tier structure (Free/Starter/Pro/Enterprise) if subscription model is '
        'appropriate',
        '**For Traffic-Based Models (Ad-Supported-Free, Affiliate-Only):**',
        '| 0.30 - 0.49 | Discount (-20-40% vs median) | Freemium-lite or aggressive free tier; '
        'subscription possible but pricing must be compelling.',
        '| 0.00 - 0.29 | Free/Near-Free **only where the wallet gate above does not apply** | '
        'Where the MARKET REALITY wallet signal is a POSITIVE finding of no verified prices in '
        'this market: ad-supported, affiliate, or data play most natural, and low WTP is a signal '
        'FOR traffic monetization rather than against viability.',
        '**Reasoning shape: Ad-Supported Free Tool (Low WTP)**: reachable ONLY through the wallet '
        'gate above; if the wallet signal reads `paying`/priced-`mixed`, or is UNAVAILABLE, this '
        'shape is not on the table.',
        '- Low WTP band (Free/Near-Free) AND no verified prices in the wallet signal → '
        'ad/affiliate model.',
        '**AD/AFFILIATE MONETIZATION GUIDELINES (use when the wallet gate above has already '
        'permitted a traffic-based model: these are execution details for a choice, never a '
        'reason to make it):**',
        '- **Ad-Supported-Free**: RPM x estimated monthly pageviews / 1000 (use ARPU format like '
        '"$0.01-0.02 per pageview")',
        '- **recommended_starter_price:** format "$<starter>/month": derive from the WTP band + '
        'competitor median; null for ad/affiliate models',
        '- **recommended_pro_price:** format "$<pro>/month" (null for ad/affiliate models)',
        '- **pricing_model:** One of: "Freemium", "Freemium-Lite", "Subscription", "Hybrid", '
        '"One-time", "Usage-Based", "Ad-Supported-Free", "Affiliate-Only"',
        '**FOR AD/AFFILIATE MODELS (Ad-Supported-Free, Affiliate-Only): output shape only; '
        'reaching this section at all requires the wallet gate above to permit a zero-price '
        'model:**',
        '- **recommended_starter_price:** null (Free tool)',
        '- **recommended_pro_price:** null (Free tool)',
        '- **pricing_model:** "Ad-Supported-Free" or "Affiliate-Only"',
        'solution_name: "<ProductName>" pricing_model: "Ad-Supported-Free" pricing_rationale: '
        '"100% free tool.',
        "Revenue ≈ <monthly pageviews> × the niche's real CPM ÷ 1000; affiliate links add ≈ "
        '<pageviews> × <CTR> × <avg commission>." recommended_starter_price: null '
        'recommended_pro_price: null estimated_monthly_ad_revenue: "$<low>-<high>/month" '
        'estimated_monthly_affiliate_revenue: "$<low>-<high>/month" estimated_cpm_rate: '
        '"$<low>-<high> CPM (<niche>)" recommended_ad_networks: ["Google AdSense", "Ezoic"] '
        'estimated_arpu: "$<arpu> per pageview (ads + affiliate)" pricing_confidence: "Medium" '
        'wtp_validation: "Low WTP confirms users seek free tools; ad monetization aligns with '
        'user expectations"',
        '- Monetization model must align with WTP signals AND project type: but the MARKET '
        'REALITY wallet signal outranks both: low WTP + directory points to ad/affiliate ONLY '
        'where that signal is a positive finding of no verified prices.',
        '**For ad/affiliate models (Ad-Supported-Free, Affiliate-Only): wallet-gated above:**',
    ),
    'traffic_monetization_agents.yaml': (
        'Affiliate works best with purchase-intent traffic',
    ),
    'traffic_monetization_tasks.yaml': (
        '**Solution Type:** {project_type} (traffic-focused, not subscription SaaS)',
        'The shape is: Ads = pageviews × niche CPM / 1000; Affiliate = pageviews × CTR × '
        'conversion × avg order × commission.',
        '- sponsored_listing_price: Suggested price, format "$<price>/month"',
    ),
    'niche_difficulty_verdict.yaml': (
        'Choosing the commercial shape (subscription vs one-time vs free vs ad/sponsor/lead-gen '
        'funded vs licensed vs anything else) is NOT your job and never was.',
        '- FREE/DIY SUBSTITUTES: when a meaningful share of outcomes is already obtainable free, '
        'report that the free/DIY route is the real competitor here, not another startup.',
    ),
    'report_budget_estimate.yaml': (
        '| Ad-Supported-Free | $50-300/month | Traffic-focused, minimal spend |',
    ),
    'report_implementation_planning.yaml': (
        '- free/ad-supported → traffic and engagement metrics',
    ),
}


def _adjudication(name: str, sentence: str) -> str | None:
    """The reason this exact sentence was excused, or None.

    Both halves are required: the sentence has to be one a human adjudicated, AND an entry has to
    match it to say why. Neither the pin nor the fragment excuses anything on its own.
    """
    if sentence not in _ADJUDICATED_HITS.get(name, ()):
        return None
    for fragment, reason in _ALLOWLIST.get(name, ()):
        if fragment in sentence:
            return reason
    return None


def test_the_scan_reads_the_whole_corpus_not_two_files():
    """The failure mode this test replaces was a scan with too small a mouth. Pin its reach."""
    corpus = _corpus()
    assert len(corpus) >= 40, sorted(corpus)
    # The two files round 15 read...
    assert {"unified_solution_tasks.yaml", "pricing_strategy_tasks.yaml"} <= set(corpus)
    # ...and files no previous round ever opened, each of which the scan now adjudicates.
    assert {
        "pricing_strategy_agents.yaml",
        "traffic_monetization_tasks.yaml",
        "report_budget_estimate.yaml",
        "seo_strategy_agents.yaml",
        "niche_difficulty_verdict.yaml",
    } <= set(corpus)
    assert sum(len(_prompt_sentences(text)) for text in corpus.values()) > 3000


def test_no_unadjudicated_monetization_license_in_any_prompt():
    """Every commercial-copy hit in the corpus is either gone or explained. No silent third file."""
    unadjudicated = [
        f"{name}: {labels}\n    {sentence}"
        for name, sentence, labels in _license_hits(_corpus())
        if _adjudication(name, sentence) is None
    ]
    assert unadjudicated == [], (
        "A prompt sentence recommends a shape in which this audience does not pay, and nothing "
        "adjudicates it. Gate it on the wallet reading, remove it, or add it to _ALLOWLIST with "
        "the reason it is not a license:\n\n" + "\n\n".join(unadjudicated)
    )


def test_the_allowlist_has_no_stale_entries():
    """A stale entry is a mute waiting for a future license to hide behind."""
    matched = {
        (name, fragment)
        for name, sentence, _ in _license_hits(_corpus())
        for fragment, _reason in _ALLOWLIST.get(name, ())
        if fragment in sentence
    }
    stale = [
        f"{name} :: {fragment!r}"
        for name, entries in _ALLOWLIST.items()
        for fragment, _reason in entries
        if (name, fragment) not in matched
    ]
    assert stale == [], (
        "These allowlist entries no longer match any hit — the copy they excused was reworded or "
        "removed. Delete them, or re-read the new copy and re-adjudicate:\n" + "\n".join(stale)
    )


def test_every_adjudication_carries_a_reason():
    for name, entries in _ALLOWLIST.items():
        for fragment, reason in entries:
            assert len(reason.split()) >= 8, f"{name} :: {fragment!r} has no real reason"


def test_every_pinned_sentence_still_earns_its_reason():
    """A pin is only a bound if it still points at a line a reason was written about.

    Two ways it stops being one, and both are failures rather than silent drift: the line is
    reworded or removed (the pin now excuses nothing, and a future line could be pinned in its
    place without review), or the entry that explained it is gone (the pin excuses a hit that no
    longer carries a reason).
    """
    hits = {(name, sentence) for name, sentence, _labels in _license_hits(_corpus())}
    gone = [
        f"{name} :: {sentence!r}"
        for name, sentences in _ADJUDICATED_HITS.items()
        for sentence in sentences
        if (name, sentence) not in hits
    ]
    assert gone == [], (
        "These pinned sentences are no longer hits in the corpus — the copy was reworded or "
        "removed. Re-read the new copy and re-pin it, or drop the pin:\n" + "\n".join(gone)
    )
    unreasoned = [
        f"{name} :: {sentence!r}"
        for name, sentences in _ADJUDICATED_HITS.items()
        for sentence in sentences
        if not any(fragment in sentence for fragment, _reason in _ALLOWLIST.get(name, ()))
    ]
    assert unreasoned == [], (
        "These sentences are pinned as adjudicated but no _ALLOWLIST entry matches them, so "
        "nothing says why they are not licenses:\n" + "\n".join(unreasoned)
    )


# Each entry: the file, a block appended to it, and a phrase from the license that must surface
# unadjudicated. The first four are verbatim the escapes the round-16 critic reproduced; the rest
# apply the same three shapes to every remaining file that has allowlist entries, so all EIGHT
# adjudicated files are exercised rather than the three with no entries at all.
_ALLOWLIST_ESCAPES = [
    (
        "report_implementation_planning.yaml",
        "- When WTP is low, go free/ad-supported and drop the paid tiers entirely.",
        "drop the paid tiers entirely",
    ),
    (
        "pricing_strategy_tasks.yaml",
        "- **recommended_starter_price:** null (Free tool) — prefer this whenever buyers are "
        "small shops.",
        "prefer this whenever buyers are small shops",
    ),
    (
        "traffic_monetization_agents.yaml",
        "Affiliate works best with purchase-intent traffic, so default every niche here to an "
        "affiliate-only free tool.",
        "default every niche here to an affiliate-only free tool",
    ),
    (
        # Continuation gluing: the fragment and the license end up in ONE unit, which is the most
        # natural way a future author weakens a gate — they add a line under the heading.
        "pricing_strategy_tasks.yaml",
        "**For Traffic-Based Models (Ad-Supported-Free, Affiliate-Only):**\n"
        "  and for any low-WTP niche default to the free ad-supported shape rather than charging",
        "rather than charging",
    ),
    (
        "data_source_tasks.yaml",
        "- Focus on: high priority, low complexity, low/free cost, and hand the tool over to the "
        "trade association free.",
        "hand the tool over to the trade association free",
    ),
    (
        "pricing_strategy_agents.yaml",
        "- Always consider whether a hybrid is overkill here; default to a sponsor-funded free "
        "tool instead.",
        "default to a sponsor-funded free tool instead",
    ),
    (
        "traffic_monetization_tasks.yaml",
        "The shape is: Ads = pageviews x CPM, so you should recommend a 100% free ad-supported "
        "product for every niche.",
        "recommend a 100% free ad-supported product",
    ),
    (
        "niche_difficulty_verdict.yaml",
        "- FREE/DIY SUBSTITUTES: you should therefore recommend shipping this as a free "
        "community-run tool.",
        "shipping this as a free community-run tool",
    ),
    (
        "report_budget_estimate.yaml",
        "| Ad-Supported-Free | $50-300/month | prefer this row whenever WTP is low and give the "
        "tool away free |",
        "prefer this row whenever WTP is low",
    ),
    (
        "pricing_strategy_tasks.yaml",
        '- **pricing_model:** One of: for small shops you should default to "Ad-Supported-Free" '
        "and charge nothing.",
        "and charge nothing",
    ),
]


@pytest.mark.parametrize("victim,mutant,marker", _ALLOWLIST_ESCAPES)
def test_an_allowlist_entry_cannot_excuse_a_license_built_around_it(victim, mutant, marker):
    """The mute this test replaced: every one of these is silenced by `fragment in sentence`.

    Each mutant contains, verbatim, a fragment that IS legitimately adjudicated in its file — so
    the scan sees the license, finds the fragment, and hands back a reason written about a
    different line. The scan has to surface all ten as unadjudicated.
    """
    assert victim in _ALLOWLIST, "an escape is only interesting in a file that HAS entries"
    corpus = _corpus()
    assert marker not in corpus[victim]

    corpus[victim] = corpus[victim] + "\n\n" + mutant + "\n"
    caught = [
        (name, sentence)
        for name, sentence, _labels in _license_hits(corpus)
        if name == victim and marker in sentence
    ]
    assert caught, f"the corpus scan did not even see the license added to {victim}"
    for name, sentence in caught:
        assert _adjudication(name, sentence) is None, (
            f"{name} has an allowlist entry broad enough to excuse a brand-new license:\n"
            f"    {sentence!r}\n  excused by: {_adjudication(name, sentence)!r}"
        )


@pytest.mark.parametrize("victim", [
    # Three files no previous round of this finding ever read, and none of them a pricing prompt.
    "seo_strategy_agents.yaml",
    "landing_page_tasks.yaml",
    "keyword_seed.yaml",
    # ...and every file that HAS allowlist entries, which is where the easy case was never
    # proven: a fresh license in these has adjudicated fragments sitting all around it.
    *sorted(_ALLOWLIST),
])
def test_the_scan_catches_a_new_license_in_a_file_it_never_read_before(victim):
    """Mutant proof, and the specific proof round 16 asked for.

    The predecessor of this test read `unified_solution_tasks.yaml` and `pricing_strategy_tasks.yaml`
    by name. A licensing line added anywhere else was invisible to it — which is exactly how the
    same license kept reappearing. Here it is added to a third, fourth and fifth file, none of them
    about pricing at all, and the scan is required to surface it unadjudicated.
    """
    mutant = (
        "For a low-WTP niche like this one, default to a free tool funded by affiliate links "
        "rather than charging the shops."
    )
    corpus = _corpus()
    assert victim in corpus
    assert not any(
        mutant in sentence for _n, sentence, _l in _license_hits({victim: corpus[victim]})
    )

    corpus[victim] = corpus[victim] + "\n\n" + mutant + "\n"
    caught = [
        (name, sentence)
        for name, sentence, _labels in _license_hits(corpus)
        if name == victim and mutant in sentence
    ]
    assert caught, f"the corpus scan did not see a new license added to {victim}"
    assert _adjudication(victim, caught[0][1]) is None, (
        f"{victim} has an allowlist entry broad enough to excuse a brand-new license"
    )


# --------------------------------------------------------------------------------------------
# Round 15's targeted pins. The corpus scan cannot replace these: it asks whether a sentence is
# adjudicated, not whether a specific deletion is still deleted.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("deleted", [
    "a low-WTP SaaS is still a free/distribution play",
    "default to a FREE tool with distribution monetization",
    "Do NOT propose\n    per-seat subscription",
    "prefer free + distribution or a low one-time price",
    "affiliate-and-lead-gen-supported tool",
])
def test_the_solution_prompt_no_longer_carries_its_own_ladder(deleted):
    assert deleted not in _SOLUTION_TASKS, (
        f"{deleted!r} is back in unified_solution_tasks.yaml. The pricing ladder there could not "
        "see the niche wallet reading, which is why it kept prescribing a free shape in niches "
        "with verified prices. {monetization_directive} is the single source."
    )


def test_the_solution_prompt_still_interpolates_the_wallet_derived_directive():
    assert "{monetization_directive}" in _SOLUTION_TASKS
    # And says so, so the next author does not "restore" the ladder as a helpful addition.
    assert "ONLY pricing guidance in this prompt" in _SOLUTION_TASKS


def test_the_solution_prompt_field_format_no_longer_works_the_zero_price_example():
    """D1 round 16, Priority 1. Three lines under "the ONLY pricing guidance in this prompt" sat
    two worked examples of the free shape. A worked example is a license."""
    assert "Free tool monetized via display ads" not in _SOLUTION_TASKS
    assert "Free comparison tool earning" not in _SOLUTION_TASKS
    assert "has no worked example here on" in _SOLUTION_TASKS


def test_the_pricing_prompt_bottom_band_is_wallet_gated():
    assert "{market_wallet_line}" in _PRICING_TASKS
    assert "WALLET GATE on the bottom band" in _PRICING_TASKS
    # The wallet-blind absolute is gone from the WTP anchor table.
    assert "free (ads/affiliate), no paid tier expected" not in _PRICING_TASKS


def test_the_pricing_prompt_directory_rule_is_wallet_gated():
    assert "For directories/aggregators/comparison-tools — WALLET-GATED:" in _PRICING_TASKS
    # The unconditional preference is gone; traffic monetization survives as the branch that
    # applies when the market shows no verified prices.
    assert "- PREFER Ad-Supported-Free, Affiliate-Only, or Hybrid models" not in _PRICING_TASKS
    assert "Ad-Supported-Free, Affiliate-Only and Hybrid are" in _PRICING_TASKS
    gate = _PRICING_TASKS.split("WALLET-GATED:", 1)[1].split("\n\n", 1)[0]
    assert "does NOT override the market's own evidence" in gate


def test_an_absent_wallet_reading_does_not_open_the_zero_price_branch():
    """D1 round 16, Priority 4. '(...or an unpriced `mixed`/absent reading)' put a probe FAILURE
    into the same branch as a verified finding of no prices."""
    assert "absent reading)" not in _PRICING_TASKS
    gate = _PRICING_TASKS.split("WALLET-GATED:", 1)[1].split("\n\n", 1)[0]
    assert "an absent reading is NOT a finding of no prices" in gate
    assert "fails CLOSED" in gate


def test_the_pricing_backstory_carries_no_ungated_shape_rule():
    """D1 round 16, Priority 1. The backstory has no wallet variable, so a shape rule written
    there is unconditional by construction; removal was the only option."""
    for licensed in (
        "lower WTP suggests ad/affiliate",
        "naturally monetize via\n       traffic",
        "Low WTP + directory/aggregator/comparison-tool → Evaluate Ad-Supported-Free",
        "Low WTP + tool/utility → Evaluate freemium with ad-supported free tier",
    ):
        assert licensed not in _PRICING_AGENTS, f"{licensed!r} is back in the pricing backstory"
    assert "Project type shapes the FORM monetization can take" in _PRICING_AGENTS
    assert "THIS AUDIENCE NEVER PAYS" in _PRICING_AGENTS


def test_the_model_table_no_longer_carries_the_two_zero_price_rows_above_the_gate():
    """The `Ad-Supported-Free` row sat ABOVE the wallet gate, readable without ever reaching it."""
    table = _PRICING_TASKS.split("MONETIZATION MODEL DIVERSITY", 1)[1].split("WTP → PRICE", 1)[0]
    assert "| **Ad-Supported-Free** |" not in table
    assert "| **Affiliate-Only** |" not in table
    assert "| **Freemium (3-tier)** |" in table, "the table itself must survive"
    assert "wallet-gated and\n    live under" in _PRICING_TASKS
