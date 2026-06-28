# Idea Scoring Methodology

How NicheIQ scores and ranks the solution ideas it generates — and the guardrails
that keep those scores honest. Written for the curious user: this is the reasoning
behind the numbers you see on each idea.

> For how a run is organized around a niche vs. a target audience, see
> **Niche or Audience: How NicheIQ Reads What You're After**.

## Table of Contents

- [Overview](#overview)
- [The eight scores](#the-eight-scores)
- [How a score is produced](#how-a-score-is-produced)
- [The honesty guardrails](#the-honesty-guardrails)
- [How ideas are ranked](#how-ideas-are-ranked)
- [The Go / No-Go verdict](#the-go--no-go-verdict)
- [Honest limitations](#honest-limitations)

## Overview

Every idea NicheIQ proposes is scored on eight dimensions covering **demand**,
**buildability**, **data availability**, and **differentiation**. Each score is a
number from 0 to 1.

The thing that makes these scores trustworthy is that **the model that proposes an
idea is not the model that scores it.** A creative generator dreams up concepts; a
separate, independent reviewer then re-scores them with a skeptical eye, at zero
"temperature" (no creative wandering — same input, same judgment). On top of that
reviewer sit a set of **downgrade-only guardrails**: rules that can *lower* an
over-optimistic score but can never *raise* one. The result is a deliberately
conservative number — closer to "what could actually go wrong" than to "how exciting
does this sound."

## The eight scores

| Score | Question it answers |
|---|---|
| **Market fit** | How strongly does this address a *validated* pain in the audience? |
| **Technical feasibility** | Can it be built at all with today's tech and obtainable data? |
| **Data feasibility** | Can a solo founder actually *get* the data it needs — legally, reliably, in bulk? |
| **Build feasibility** | Can a competent solo developer build *and operate* it? |
| **Solo-dev feasibility** | Could one person realistically ship and maintain it (including ongoing run cost)? |
| **SEO scalability** | Can it grow organic traffic through content at scale? |
| **Novelty** | How differentiated is it from what already exists? |
| **Obviousness** | How many builders would propose essentially the same thing? (lower is better) |

Higher is better for every score except **obviousness**, where lower means more original.

## How a score is produced

Ideas move through three steps, and different steps own different scores:

1. **Generation.** A creative pass proposes a batch of concepts. Each concept must
   declare, up front, the concrete **data route** it depends on — a downloadable
   dataset, an official API, a public index, or first-party user submissions — or
   mark itself as not data-dependent. Concepts that can only hand-wave at their data
   are flagged at birth. The generator is steered *away* from ideas that are hard to
   ship for non-obvious reasons: products whose core mechanism is publishing
   accusations about named people or businesses (legal exposure), and products that
   need a large content library hand-built before launch (the "cold-start" trap).

2. **Independent review.** A separate reviewer model re-scores each concept's
   originality and feasibility — crucially, it writes its reasoning *before* its
   numbers. The data route gets its own web-search check that rules three ways: a real
   public source is **supported** (no penalty); data that's removed, gated, or doesn't
   exist is **refuted** (scored down); and a route the search can neither confirm nor
   refute is left **unverified** — flagged for you to check, but *not* penalized on a
   guess. This is where most over-optimism is caught, without punishing a real idea just
   because a search came up thin.

3. **Refinement.** A final pass turns the surviving concepts into full ideas and
   scores market fit, technical feasibility, SEO scalability, novelty, and solo-dev
   feasibility — against rubrics that explicitly *demote* an idea when it has a real
   defect (a refuted/unobtainable data source, an ongoing moderation burden, a cold-start
   requirement), while leaving clean, simple ideas untouched.

## The honesty guardrails

These are deterministic rules — not model judgment — applied after the reviewer
scores. Every one can only lower a score:

- **A named source is a claim, not a fact.** If an idea's data is only reachable as a
  one-record-at-a-time lookup, sits behind a login, or has no nameable bulk route, the
  data is marked *restricted* and its data-feasibility score is capped. A real
  "scrapeable public list" requires an actual index of records, not the ability to look
  up one item you already know.
- **You can't build on data you can't get.** Build feasibility can never sit far above
  data feasibility. An idea that claims it's easy to build *on top of data it can't
  actually obtain* is automatically pulled back down.
- **A one-person product can't beat its own build difficulty.** Solo-dev feasibility is
  capped at build feasibility + a small margin — if an idea is hard to build at all, it
  can't be easy for one person to build *and run*. The realism critic now re-scores solo-dev
  too (weighing ongoing support, uptime, and moderation load first, since that — not the
  initial build — is what sinks most solo founders); this cap is the hard floor beneath that.
- **Access tiers have ceilings.** Data the search *refutes* (removed, gated, nonexistent) is
  floored to a low score; restricted / scraping routes are capped at a modest one. A route the
  search could neither confirm nor refute is left **uncapped** but flagged "unverified — verify
  before building", so an honest "we don't know" isn't treated as either a green light or a block.
- **Operating cost counts, not just build cost.** Ideas that need ongoing manual
  moderation, community management, or continuous hand-seeding are penalized on build
  and solo-dev feasibility — a maintenance-heavy product is not a one-person product.
- **Legal exposure lowers the score (it doesn't hide the idea).** Concepts built on
  publishing claims about named third parties are scored down for feasibility, while
  still being shown to you with the concern visible.
- **Originality must be earned.** The novelty score is held back unless the idea cites
  specific, real evidence for why it's different, and the generator is required to
  include genuinely non-obvious ideas in every batch rather than a wall of safe bets.
- **SEO potential must rest on a real content corpus.** The SEO-scalability score is
  pulled back when the "thousands of pages" story doesn't hold up: a SaaS whose data
  lives behind a login (its pages can't be indexed), a product whose realistic page
  count is too small to be a programmatic-SEO play, or one that grows content by hand
  (manual blogging, community seeding) rather than from structured data. The top
  "directory/aggregator" band is reserved for ideas with an actual enumerable corpus.
  This cap is applied *after* ranking is fixed, so it makes the *displayed* SEO number
  and the Go/No-Go verdict honest without reshuffling which ideas rank where. (The
  account-gating signal uses the project type plus the data-access tier — there is no
  separate "is it gated" flag — so it's a careful proxy, not a certainty.)

## How ideas are ranked

Ideas are ordered by a **composite score** — a blend of market fit, technical
feasibility, novelty, and SEO scalability.

One adjustment matters a lot for trust: the independent reviewer's **build-feasibility**
estimate is allowed to *lower* the technical feasibility used in ranking (never raise
it). Without this, a confident-sounding idea resting on data it can't actually get
could out-rank a genuinely shippable one. With it, "can you really build this?" pulls
fragile ideas down the list, so the top of the ranking is the part you can trust most —
not the part with the best marketing.

## How specific metrics are estimated

Most scores are an expert-style 0–1 judgment grounded in the gathered evidence, then held
in line by the guardrails above. A few use a more concrete technique:

**SEO scalability — an indexable-page-count estimate.** This score answers one question:
*how many distinct, indexable, non-thin pages can this realistically rank?* So it's built
on a **page-count estimate**, not a vibe, and it deliberately ignores *how* the data is
sourced — scraping vs. an official API doesn't change whether a page ranks (that's a
feasibility question, scored separately). It's estimated in two phases:

1. **Preview estimate.** When ideas are first generated, the model estimates the number of
   genuinely distinct, non-thin pages the content pattern would produce — excluding
   near-duplicate "combinatorial filler" and anything behind a login — and scores SEO from
   that count (roughly: a few dozen pages = low, a few hundred = moderate, low-thousands+ =
   high). This is **provisional** — a reasoned estimate, not a measurement.
2. **Keyword-grounded recount.** For the idea you choose to pursue, a later stage recomputes
   the page count from **real keyword data** (search volumes and the validated keyword set),
   and the SEO score is refined to match. This is the number to trust.

On top of both phases sit deterministic, downgrade-only realism checks: a page count too
small to be a programmatic-SEO play is pulled down, combinatorially-thin or duplicate page
sets don't earn the top band, and a product whose output pages sit behind a login (so they
can't be crawled) is capped — because un-indexable pages, however many, don't rank. These
checks only ever *lower* the score and never change the ranking order; they make the
displayed number and the verdict honest.

## Pain point scores (severity, commercial intent, opportunity)

Before any ideas exist, each **pain point** mined from the discussions carries its own small
set of scores. These describe the *problem*, not a product, and they feed which pains are worth
building for.

- **Severity (0–1) — does this block real work?** Severity measures **functional impact**: does
  the problem stop someone reaching a goal or finishing a workflow? It is deliberately **not** a
  measure of how *loudly* people complain. "I'm so frustrated with this" is emotional volume;
  "we lost three clients to invoicing delays" is severity. The score is read against
  behaviorally-anchored bands (a critical revenue/clients/time loss sits at the top; a minor
  annoyance near the bottom), which is the part of this with the most research behind it.

- **Commercial intent (0–1) — is there a buying signal?** This was previously labelled
  "willingness to pay," which over-claimed what text can tell us. It is an **ordinal buying-signal
  strength**, not a dollar figure: it reads how strongly the discussion shows commercial intent —
  people naming a paid tool they already use, mentioning a budget or current spend, or a pain that
  costs billable time. It is honest to use it to **rank** pains by buying signal; it is *not* a
  willingness-to-pay you could put a price on. A true willingness-to-pay needs a pricing study
  (people reacting to real prices), which self-selected public discussion simply cannot provide —
  and even careful surveys overstate what people will really pay. Treat a high score as "there's a
  buying signal here," not "users will pay $X."

- **Opportunity (High / Medium / Low) — the two combined.** Opportunity combines the two:
  **High** when both severity and commercial intent are strong, **Medium** when one is, **Low**
  when neither. The boundary (currently 0.6 on each) is a sensible **heuristic**, not a
  statistically optimised cutoff — we don't yet have outcome data (which ideas became revenue) to
  tune it against, and we'd rather tell you that than imply a precision we don't have.

**Honesty guardrails on pain scores (all downgrade-only, like the idea scores):**

- **No evidence → capped severity.** A pain whose supporting quotes are thin or missing can't keep
  a high severity score, regardless of how it was phrased.
- **Tool-addressability cap.** If a software product can't realistically move the needle on a pain
  (a lifestyle, cultural, or structural problem — "people prefer watching to playing"), its
  commercial-intent score is capped and it is held out of idea generation. There's no point pricing
  a problem software can't solve.
- **Universal-emotional and "every niche" caps.** Pains that are really generic emotional themes
  (burnout, stress) or would appear identically for *any* audience are capped down — they don't
  differentiate an opportunity.

Across all of these: the scores are **ordinal guides read from self-selected public discussion**,
not survey-calibrated instruments. They're best read as bands (High / Medium / Low), not precise
decimals — a "0.63" is not meaningfully different from a "0.61."

## What we show about the idea *set*

Beyond scoring each idea, we try to give you an honest read on the **batch as a whole**.

- **Variety is enforced where concentration means laziness.** The final set is
  de-concentrated across project type, target segment, and core mechanism — five
  near-identical aggregators for the same audience is a worse set than five different
  shapes, so the selection trims that kind of redundancy (always dropping the weakest of
  a cluster, never a uniquely strong or uniquely pain-covering idea).
- **But we do *not* force spread across pains.** Pain is the one axis where concentration
  often means the opportunity is *real*, not that the set is lazy — if the best ideas all
  attack the same high-value pain, capping them would trade quality for cosmetic variety.
  So pains are never quota'd.
- **Instead, we surface the coverage so you can judge it.** When the set leans heavily on
  one pain, or leaves a validated pain with no idea at all, that's stated plainly in the
  report's data-quality notes — e.g. *"4 of 6 ideas address product purity; validated
  pains with no idea: injection complexity, skin-health efficacy."* It's information for
  your call, not a verdict: heavy concentration can be exactly where you should focus.

## The Go / No-Go verdict

Each idea carries a Go / No-Go signal. Like the scores, the verdict logic is
**downgrade-only**: weak fundamentals (for example, technical feasibility below a set
floor) can turn a Go into a No-Go, but the verdict machinery never upgrades a weak idea
into a Go. It is designed to be a conservative gate, not a cheerleader.

## Honest limitations

These scores are **AI-assisted estimates with guardrails — not guarantees.** A few
things they deliberately do *not* claim to do:

- They do not give legal advice or formally vet whether a data source's terms permit
  your use. The "legal exposure" guardrail is a caution flag, not a clearance.
- The fast feasibility check reasons about whether a data source *should* be obtainable;
  it does not go fetch the data live to prove it. For an idea you choose to pursue, a
  deeper data-source verification step runs later in the research.
- Scores reflect the evidence gathered for *your* niche at the time of the run. More or
  better source discussions generally mean better-calibrated scores.
- **The SEO-scalability score is a preliminary estimate.** Early in the run it reflects a
  judgment about content potential, not a measured page count. The realistic number of
  pages a programmatic-SEO play can actually rank is only validated later, during the
  keyword-research stage, for the idea you choose to pursue — at which point the SEO score
  is refined. Treat the early SEO number as a directional estimate to be confirmed, not a
  measurement.

The goal isn't a perfect number — it's an *honest* one. We would rather show you a
conservative score with the reasoning behind it than an optimistic score that doesn't
survive contact with reality.
