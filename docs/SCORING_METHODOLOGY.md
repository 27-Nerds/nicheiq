# Idea Scoring Methodology

How NicheIQ scores and ranks the solution ideas it generates — and the guardrails
that keep those scores honest. Written for the curious user: this is the reasoning
behind the numbers you see on each idea.

> For how a run is organized around a niche vs. a target audience, see
> **Niche or Audience: How NicheIQ Reads What You're After**.

## Table of Contents

- [Overview](#overview)
- [Where an idea starts: the uniformity contract](#where-an-idea-starts-the-uniformity-contract)
- [The eight scores](#the-eight-scores)
- [How a score is produced](#how-a-score-is-produced)
- [The honesty guardrails](#the-honesty-guardrails)
- [Who pays: buyer payability and pricing shape](#who-pays-buyer-payability-and-pricing-shape-2026-07-06)
- [Competition checks: direct, substitute, and adjacent-market](#competition-checks-direct-substitute-and-adjacent-market-2026-07-06)
- [Angle-aware evaluation](#angle-aware-evaluation)
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

## Where an idea starts: the uniformity contract

Ideas don't all begin the same way. Most start from the **pain-point lens** (primary,
unchanged): a validated pain paired with the audience that feels it. Since 2026-07-10,
three more **generation lenses** feed the same idea set, each seeded from evidence the
pipeline has already verified elsewhere in the run rather than re-deriving it:
**competitor-gap** (one cell from the incumbent probe's per-tool gap findings),
**data-asset** (one cell from the verified public-data menu — what dataset could be
assembled and who pays for what it reveals), and **workflow** (one cell from a
synthesized job-map of pains, motivation drivers, and tool frustrations). Bundles remain
the cross-pain synthesis peer. Which lens an idea started from is stamped as
`source_frame` and shown as a "generation lens" chip on the idea.

The uniformity contract this document describes applies identically regardless of
origin: every idea — pain-point or lens-born — passes through the same independent
reviewer, the same downgrade-only guardrails, the same data-route verification, the
same payability and competition checks, and the same calibration critic described
below. A lens-born idea must also anchor to a validated pain from the discussion or the
cell is dropped; a lens supplies the seed evidence for a concept, never a shortcut
around scoring it. Pain-point cells keep reserve priority in the run's cell budget —
the highest-severity, best-evidenced pains are always covered first, and the other
three lenses draw from what's left.

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

The product presents one user-facing **Distinctiveness** rating. For current reports it is
`1 − obviousness_score`, using the independent obviousness review; legacy reports without that
field fall back to `novelty_score`. Research ranking separately uses the calibrated
`novelty_score`. The two signals are related, but the displayed Distinctiveness rating does not
directly determine the Research score.

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
   obviousness and feasibility — crucially, it writes its reasoning *before* its
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
- **Distinctiveness must be earned.** The internal novelty score is held back unless the idea cites
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

## Who pays: buyer payability and pricing shape (2026-07-06)

Pain intensity alone can't make a market — the buyer also needs a wallet. Three signals cover
this, all downgrade-only or informational:

- **Usage cadence + pricing-shape check** (always on): every idea is tagged with how often the
  buyer actually *uses* it (`continuous | periodic | episodic | one-shot`), and a deterministic
  check flags `episodic`/`one-shot` usage sold as a subscription — buyers churn between events,
  so the note recommends usage-based/credit-pack or one-time pricing instead. Never a score
  change; rendered as a "Pricing-shape mismatch" watch-out (see `docs/IDEA_TAGS.md`).
- **Niche buyer class** (always on): the Research Reality Check classifies who actually pays in
  the niche (`budgeted-business | smb-operator | prosumer | indie-hobbyist | consumer | mixed`)
  from the Stage-4 segments' budget sensitivity + the pains' buying signals. Low-payability
  classes surface a "Who pays here" warning — e.g. indie/hobbyist builders spending personal
  money episodically are a documented low-willingness-to-pay class regardless of how loud the
  pain reads.
- **Segment payability** (permanent — flag removed after the 2026-07-06 calibration-gate pass:
  market_fit signed error vs a neutral Fable panel went +0.051 → −0.006 with MAE not worse and
  verdict kappa 0.142 → 0.248): each audience segment gets a 0-1
  payability score from budget authority (`budget_sensitivity`), existing-spend evidence
  (web-probed incumbent pricing, money-language quotes, pain commercial-intent joined via
  `affected_segments`), and a closed wallet-class vocabulary
  (`corporate-budget .85 | smb-budget .60 | prosumer-wallet .40 | personal-wallet .25` priors,
  averaged with the LLM's score and clamped — a single optimistic draw can't flip a
  personal-wallet segment). Ideas inherit it via `source_segment` (unmatched segments fall back
  to the niche mean — a join failure can never silently create scoring asymmetry). It
  caps market_fit at `payability_market_fit_cap` (default 0.55) when payability is below
  `payability_low_threshold` (default 0.35), and can hold a Go verdict to Conditional for
  direct-paid ideas (Phase-5 floor; ads/affiliate/commission plays are exempt — they don't need
  the buyer's wallet).

  **Payability de-dup (2026-07-30):** the signal originally ALSO fed the calibration critic as
  a per-idea evidence line + rubric ("pain without a wallet is not a market") and a niche-wallet
  willingness-to-pay ceiling. The 2026-07-30 run-quality audit found the composed system applied
  the same wallet evidence up to six times (observed market_fit landed at 0.40-0.45 — *below*
  the 0.55 cap, proving the prompt stages double-applied it), so the prompt-side applications
  were removed: **the critic now scores payability-blind**, and the segment wallet reaches
  market_fit through exactly one auditable path — the deterministic cap (plus its downstream
  demotion/verdict consumers). Practical effect: thin-wallet (<0.35) ideas land AT the 0.55 cap
  instead of 0.40-0.45; ideas in the 0.35-0.55 payability band carry no market_fit wallet
  discount (raise `payability_low_threshold` if that band over-scores).
  Validation path: `scripts/calibration_gate.py gate --candidate dedup` (pre-de-dup prompt
  replay vs shipped blind prompt, both reported with the post-cap composed view; the old
  `--candidate payability` mode is a no-op since both arms now render identical prompts).
  **Gate-validated 2026-07-30** (67 ideas / 7 niches / N=3 vs the neutral-Opus panel, composed
  view): market_fit signed error −0.031 → **+0.002**, MAE 0.075 → **0.056**, verdict kappa
  0.385 → **0.419**. The double-count was directly observable: pre-de-dup only 8/67 ideas ever
  reached cap (d) (the prompt had already pushed market_fit below the cap); post-de-dup 18/67
  hit it — one application, more accurate.

## Competition checks: direct, substitute, and adjacent-market (2026-07-06)

The mechanism-parity probe web-verifies every idea (not just the top few) and now reports four
levels: `shipped` / `partial` (a commercial product ships the mechanism), `substitute` (no
commercial product, but a free/DIY route — a free official data source, a spreadsheet, a manual
workflow — already delivers the outcome; a willingness-to-pay drag, sometimes a distribution
wedge), and `none found`. Because the probe searches by each idea's own audience framing, a
second **adjacent-market probe** groups ideas into mechanism families, asks which commercial
categories the mechanism already belongs to *ignoring the stated audience*, and searches those —
catching incumbents like a govcon-intelligence vendor behind a "failed-RFP digest for founders".
Findings are name-verified against the search snippets (a hallucinated incumbent is dropped) and
shown as an "Adjacent market check" card. When ≥80% of ideas come back `none found` with no
adjacent coverage, a probe-coverage caveat warns that "none found" means low search coverage,
not a green light. Substitute + adjacent evidence also reaches the scoring critic (permanent —
flag removed after the 2026-07-06 calibration-gate replay vs a neutral Fable panel: market_fit
MAE unchanged, optimism +0.022 → +0.013 with no deflation, verdict kappa 0.197 → 0.256) — and
the critic is instructed to never *raise* a score on this evidence, only ground it.

## Angle-aware evaluation

Not every good idea wins the same way, so we don't score every idea on the same axis.
A small classifier assigns each generated idea a **winning angle** — the go-to-market
angle that gives it its best real chance — and then judges it on executing *that* angle:

- **distribution_seo** — wins by being **found**: programmatic / SEO pages plus owned
  distribution. Its differentiation lives in the **data representation** (format,
  coverage, freshness), not a clever mechanism. A familiar mechanism is **expected**
  here and isn't a flaw; the real weakness is a me-too directory with no unique data slice.
- **novel_differentiation** — wins on a **distinct mechanism** rivals can't easily copy.
- **vertical_workflow** — wins by **owning a deep workflow** for one specific user: a
  workflow step rivals miss, plus switching cost.

Every idea should be differentiated — but in the dimension its angle rewards. The internal
novelty signal therefore reflects a different kind of edge per angle: a distinct mechanism, a
better data representation, or a deeper workflow step. A familiar off-axis mechanism for a
catalog whose edge is its data is **explained**, not held against the idea. Each idea carries a
short `angle_rationale` (naming the angle, the nearest competitor, and where its
differentiation lives) and a `novelty_rationale` (one line tying the novelty score to the
idea's project type — why it reads as expected, low, or high there).

Ranking is **angle-aware** too: each idea is ranked by its own angle's weights — a
distribution idea upweights SEO and market fit (with a small, non-zero novelty weight); a
novel-differentiation idea upweights novelty; a workflow idea upweights feasibility. So a
strong catalog isn't out-ranked by a flashier idea just because it scores lower on a
dimension its angle never relied on.

**You can steer the emphasis.** An **Idea focus** control (per run, also available when you
ask for more ideas) sets the tilt: **Auto** lets the classifier decide each idea's angle
unbiased; **Differentiation** or **Distribution** tilts *both* what gets generated *and* the
ranking emphasis toward that angle. The stable internal value for the Differentiation option
remains `novelty`; it is an API/persistence contract, not the user-facing label. The control
steers emphasis, not honesty — each idea's winning-angle label stays truthful regardless of the
setting.

## How ideas are ranked

Ideas are ordered by a **composite score** — a blend of market fit, technical
feasibility, novelty, and SEO scalability, weighted by each idea's winning angle.

One adjustment matters a lot for trust: the independent reviewer's **build-feasibility**
estimate is allowed to *lower* the technical feasibility used in ranking (never raise
it). Without this, a confident-sounding idea resting on data it can't actually get
could out-rank a genuinely shippable one. With it, "can you really build this?" pulls
fragile ideas down the list, so the top of the ranking is the part you can trust most —
not the part with the best marketing.

**Adjacent-audience tie-breaker (2026-08).** If you named a target audience, each idea is
also judged on whether it primarily serves *that* audience or an adjacent one. Ideas judged
adjacent take a small fixed deduction from their **composite** — enough to break a tie in
favor of the people you asked about, not enough to bury a genuinely stronger idea. It applies
only when nearly every idea in the pool carries a verdict (otherwise the untagged ones would
be quietly promoted), and it never touches a displayed score: market fit and the rest stay
exactly as judged.

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

The verdict is read through the idea's **winning angle**. Averaging is *lift-only*: an
idea is scored on the better of its equal-weight and angle-weighted average, so a strong
distribution-first idea isn't punished for using a familiar mechanism — but a misread angle can
never demote a deserving idea. One angle-specific gate matters for distribution-first ideas:
if the search opportunity looks great on paper but there's no realistic set of pages you
could rank for (the "SEO kill-question"), the verdict is tempered toward Conditional. That
check keys off ranking winnability, which the SEO score itself deliberately leaves out — so
it adds a missing caution rather than penalizing the same weakness twice.

The verdict's written explanation speaks in plain terms — strong demand, weak distribution,
crowded field — and never quotes the raw internal scores, because the reasoning travels
better than the decimals.

### Phase-5 payability floor and the No-Go reclassification

A Go verdict for an idea sold **directly** (subscription / one-time / usage-based) to a segment
whose payability is below the low threshold is held to Conditional with risk floored at Medium —
the pain may be real, but the wallet isn't. Downgrade-only, never forces No-Go, abstains when
payability is unscored or the idea monetizes via ads/affiliate/commission. The explanation ships
in `go_no_go_verdict.payability_context`.

**No-Go is reserved for structural blockers** (product decision, 2026-07-06): when the
score-based verdict would land on No-Go for an idea that is *buildable* (technical feasibility ≥
the Conditional bar) and whose market_fit was grounded by weak buyer payability, the verdict
presents as **Conditional / High risk** with the condition named — "validate real payment intent
(pre-sales, paid pilots, or a concierge version) before committing". Unbuildable ideas, refuted
data routes, and weak markets with a *healthy* wallet remain genuine No-Gos. Rationale: a paid
analysis should tell the user what must be true, not just "no".

### Phase-5.5 red-team floor (2026-07-30)

The adversarial red-team pass stamps `weakened` / `killed` findings on reviewed ideas, but until
2026-07-30 those findings never reached the verdict — a weakened selection presented exactly like
an unexamined one. The Phase-5.5 floor (between the payability and regulatory phases) fixes that:
a **weakened** selected idea caps Go→Conditional and floors risk at Medium; a **killed** one
additionally floors risk to High and names the refuted premise as the `primary_concern` (a killed
idea can still *be* the selection — the sweep demotions run before the red team, and the kill
path only caps scores). Downgrade-only, never forces No-Go. The explanation ships in
`go_no_go_verdict.red_team_context` and is appended to the rationale **unconditionally** — the
finding stays visible even when the verdict letter was already Conditional. A red-team
vocabulary-mismatch abstain (`red_team_vocab_mismatch` — the probe's search evidence retrieved a
different industry) is a retrieval failure, not a verdict, and never triggers this floor.

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
