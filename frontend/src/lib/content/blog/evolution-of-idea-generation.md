When we started NicheIQ, the idea stage was one big prompt: here's a niche, here are some pain points from Reddit, give us ten SaaS ideas. It worked the way most LLM products work at first. Impressively, until you looked closely.

The ideas scored themselves. Every single one came back with a market-fit score around 0.88. Ten ideas, ten different mechanisms, ten near-identical scores. A model grading its own homework gives itself an A, every time.

This is the story of how we rebuilt that stage, what broke along the way, and why our system now sometimes tells you *not* to build anything. We think that last part is the most valuable thing it does.

## Step one: stop pooling, start partitioning

The first structural change was splitting one big ideation call into per-cell tournaments. Each validated pain point, crossed with an audience segment, gets its own small competition: a few concepts generated from that cell's specific viewpoint, an ideator-and-judge loop that sharpens the best one, and one winner per cell.

That fixed coverage. Every important pain got at least one idea instead of whatever the single big prompt happened to gravitate to. But it introduced a quieter problem we didn't notice for months: the judge inside each cell picks a winner *before* our strongest evaluator ever sees the candidates. Roughly two thirds of everything we generated was being thrown away on a first impression.

![Per-cell tournaments replace one big brainstorm: every validated pain × audience gets its own small competition with one winner](/blog/tournament.svg)

## Step two: an independent critic, and the day it disagreed with us

The self-scoring problem we fixed with a separate calibration critic: a different model, blind to the generator's scores, re-scoring every idea against fixed rubrics. The wall of 0.88s collapsed to honest 0.35–0.65s.

Then we asked a harder question. Is the *critic* honest? We built a benchmark of 61 ideas across six niches, each scored by a neutral senior-advisor model as a reference judge, and measured agreement. The result inverted our assumptions. We'd believed the critic was too harsh on unglamorous SEO-style ideas. It was actually too *generous* on market fit, by +0.13 on average, awarding 14 "Go" verdicts where the neutral panel awarded zero.

One bounded prompt rule (treat pain severity as a ceiling, discount for unproven mechanisms and crowded markets) cut that optimism in half. Meanwhile a change we'd been convinced was right, teaching the critic to stop penalizing "obvious" SEO ideas, failed the same benchmark decisively and never shipped. The benchmark caught both: the fix we needed and the fix we only wanted.

We weren't the only ones hitting this. Researchers keep finding the same shape of failure: language models can be useful judges, but they carry position, verbosity, and self-enhancement biases ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)); when asked to state confidence, they often overstate it ([Xiong et al., 2023](https://arxiv.org/abs/2306.13063)); and verification helps most when claims are checked independently against evidence, not when the same model simply explains itself harder ([Dhuliawala et al., 2023](https://arxiv.org/abs/2309.11495)). A stricter prompt was never going to fix that. We separated the jobs instead: one model generates, another scores against fixed bands, a reference benchmark can disagree with both, and factual claims need evidence before they are allowed to lift a score.

![The wall of 0.88s collapses to honest 0.35–0.65 scores, then a 61-idea benchmark finds the critic itself +0.13 too generous](/blog/score-collapse.svg)

## Step three: the loop that failed four times

Between the critic and everything that came after sits the feature that taught us the most, mostly by failing. The plan sounded obvious: put the ideator in a loop with a reviewer, let them argue for a couple of rounds, ship the improved idea. Self-refinement, the thing every agent demo promises.

Version one made ideas worse by 0.93 points on the judge's 10-point composite. It emptied fields mid-rewrite. Version two fixed the field bug and still landed 0.75 worse. Version three gave the reviewer a stronger model and search grounding: 0.07 worse, a coin flip. By then the failure had a clear shape. Told to make an idea more buildable, the ideator would invent the API it needed. A StubHub "public API" that is actually partner-gated. An HLTV API that does not exist. A Dota-only stats service cited, confidently, for a CS2 product. The reviewer had no way to check reality, so it rewarded the confident lie. This matches what the research predicts: self-correction without reliable external feedback does not work ([Huang et al., 2023](https://arxiv.org/abs/2310.01798)).

Version four stopped letting the loop judge data feasibility at all. The ideator now flags any route it is unsure about instead of asserting it, and a separate search-grounded check resolves the flags afterward. Fabricated APIs went to zero across every test pair. The loop was still net negative, because removing the feasibility question also removed the brake on scope: rewrites ballooned into bigger, more speculative products. Version five changed the reviewer's job description from grader to mentor, with three standing orders: sharpen the buildable core, never expand the scope, keep the original pain. That one finally won: +0.21 on the first test run, +0.97 on the second.

One finding from the mentor-model sweep still bothers us. The recipe works with exactly one model in the mentor seat. The runner-up looked fine on the first run at +0.18, then collapsed to -0.39 on the second, where it invented an oracle that predicts Valve's secret anti-cheat thresholds. Same prompts, same loop, same everything else. People argue about prompts; our benchmark says the model behind the prompt can flip the sign of a feature.

## Step four: scoring ideas on the axis they win on

An honest score also has to be honest about what it measures. A directory of every allergen-certified bakery in the country is not a novel mechanism, and a genuinely new analysis trick may have no search traffic to ride. Grade both on one rubric and you punish each for not being the other.

So a classifier now assigns every idea the angle it actually wins by: found through search, novel mechanism, or workflow depth. The ranking weights shift with that angle, and the report names it, so a low novelty score on a directory reads as "not the point" rather than "weak idea." The classifier went through the same discipline as the critic, tuned against a neutral judge until agreement reached 94%. The tuning notes read like case law. A formula is not a novel mechanism. "Community data" is a distribution tell. Never call an idea distribution-led when it has no search surface to distribute on.

## Step five: the run that exposed everything

In early July we ran the full pipeline on a niche we picked precisely because it should have been easy: home bakers selling under cottage food laws. Real communities, real search demand, real money. People in this niche already pay $7–49/month for tools like CakeBoss and Bakesy.

The run produced five ideas. The best scored 0.46. The verdict: No-Go.

The autopsy was humbling. Four of the five ideas were built on data that doesn't exist or can't be had: smart-oven telemetry from home bakers, scraped supplier sites, cold-start crowdsourced databases. The generator invented mechanisms first and met reality later, when the critic capped every unverifiable mechanism at 0.45. Meanwhile the pain cluster this niche's actual paid products are built on, recipe costing and pricing, got no idea at all. It lost the cell allocation lottery.

And one more thing, found by accident. The tournament judge had discarded a concept, an allergen-verified bakery directory, that our critic scored higher than four of the five winners once we finally showed it the losers.

![The cottage-food run: five ideas, best 0.46, verdict No-Go. Four built on non-existent data, the real paid pain got nothing](/blog/cottage-food.svg)

## Step six: the portfolio funnel

Everything we shipped next follows from that one run.

Ideas now start from data that exists. Before generation, we build a verified data-route menu for the niche: official registries, public agency pages, licensed APIs, plain arithmetic on the user's own inputs. Every generator brief must anchor its mechanism on that menu. On the same pains, with the same critic, this single change lifted the best idea from 0.46 to 0.72.

Losers get a second opinion. After the tournaments, the full critic scores the discarded concepts in one cheap batch, and anything near or above its own cell's winner gets rescued, fully developed, and labeled honestly in the report as a rescued concept. In testing, this recovered one real idea per niche. Those are ideas the first-impression judge had thrown away.

We compose, not just generate. Single-pain tools are features; buyers pay for products. A synthesis stage now bundles three to five complementary pains into one product around a real workflow, which is the CakeBoss shape. On the astrophotography niche the bundled "Siril-to-PixInsight Results Kit" scored 0.74 against a 0.63 baseline.

And we look up the actual competition. Community discussions surface generic tools like Canva and QuickBooks, not the incumbents an idea has to beat. A quick web probe now maps the real paid products, their pricing, and their gaps, and both the generator and the critic see that map.

The allocation lottery had two holes, and we want to be precise about both. Guaranteeing the single highest-severity pain its own generation slot was cheap to prove: replayed across 24 saved niches, top-pain coverage went from 22 to 24 with zero loss of idea diversity (guaranteeing the top two or three cost real diversity, so the floor stays at one). The cottage run's specific miss was the other hole. Recipe costing was only medium-severity; it just happened to be the pain people demonstrably pay for, and cell allocation ranks by opportunity, theme, and severity, never the raw commercial-intent score, so the pain people actually hand over money for could still lose its slot to a louder, cheaper one.

Commercial evidence has a floor now too. The top pain by commercial intent, above a minimum bar so a weak buying signal can't manufacture a slot, gets the same guarantee severity does: its own cell, regardless of where it lands on severity or theme. Replayed across the same ten cached niches, top-three-commercial coverage went from 23 to 26 out of 30, again with zero cost to theme or segment diversity. A regression test now encodes the cottage-food failure itself, so recipe costing can't quietly lose that slot again without the suite catching it. Both holes are closed.

The user-visible result: instead of five thin ideas topping out at 0.46, a report now carries a tiered portfolio. A flagship product, usually a bundle. Focused single-problem tools under it. The occasional rescued concept. Typically eight ideas instead of five, with the top ones scoring where "worth a serious look" actually begins.

![The portfolio funnel: data-route menu → anchored generation → rescued losers → synthesis bundle → tiered portfolio, lifting the best idea from 0.46 to 0.72](/blog/portfolio-funnel.svg)

## Step seven: the skeptic that knew too little

The verification stage from step three had its own failure mode, and it was the opposite of the one it was built for. It exists because generators invent APIs: no model gets to claim a data source is real without evidence. But evidence means search snippets, and search snippets are thin. In one run the verifier read a couple of ambiguous results and concluded that the GitHub API was "restricted" and that SAM.gov, the US government's public procurement database, was "paywalled." Two of the most open data sources on the internet, marked as gated. And the label isn't cosmetic: a gated route caps an idea's market fit, so honest ideas built on genuinely public data were being scored as if their data didn't exist.

The fix is a catalog. We generated a list of about 1,400 known public data sources from the community-maintained public-apis registry, added the government and statistics sources it misses (SEC EDGAR, Companies House, SAM.gov, Eurostat, the census bureaus), and wired a sync script so the list follows upstream. When an idea's claimed sources are all in the catalog, whether GitHub is public no longer hinges on the day's search results.

Then we found the catalog's own failure mode before it shipped. Real entries in that upstream list include APIs named "Cats," "Coffee," and "Base." Match names loosely and every claim containing a common word gets blessed as public. So a catalog hit is only retrieval, never a verdict: a second model reads the retrieved entries and confirms the claim really means that source, and asks for data the source publicly provides. "GitHub Advisory Database" passes. "GitHub private repository scan results" gets rejected, because private repos aren't what the public API serves, and the claim falls back to the ordinary web check. The asymmetry is deliberate. A wrong rejection costs one extra search; a wrong pass would skip verification entirely, so every doubt breaks toward suspicion.

The same pass closed a quieter gap: only tournament winners used to get route verification at birth, so bundled and rescued ideas shipped with whatever label the model's memory assigned. Now every idea gets the same check no matter how it entered the set. The next run reported the same procurement idea, previously "paywalled," as public, with its sources named: Census CBP, Companies House, SAM.gov, SEC EDGAR.

![The data-source catalog: claim → retrieve ~1,400 sources → second model confirms → public verdict, with every doubt breaking toward suspicion](/blog/catalog-flow.svg)

## Step eight: the system learns to say no

For a while, a weak winner still shipped as an idea. If a cell's tournament produced one survivor and the critic scored it 0.31, that 0.31 went into the report next to a flagship at 0.72, formatted the same, presented as one more thing you could build. Nobody reading a numbered list of "your ideas" was going to read the number that hard.

So we stopped shipping them as ideas. Anything that clears its cell but lands below 0.4 market fit after calibration is demoted into a structured, evidence-based finding instead: which pain it was for, why the market underneath it is thin, and the quote it came from. The report calls it what it is, examined and ruled out, instead of padding the list to look fuller than the niche supports. A floor guard restores the strongest demoted idea if visible candidates drop below three, so pruning can't empty the report.

Two more moves closed the same gap. Buyer-visible variants, three ideas that are really one product wearing different names, get merged into one, but only when the merge scores no worse than its best parent; a bad merge never ships, it just gets grouped for display instead. And when demotion leaves the list thin, backfill runs extra cells against pains nothing was generated for yet, instead of padding with a reject. We reran the cottage-food niche to check: two weak winners came back as honest findings, and backfill surfaced one genuinely new candidate the original allocation had never touched.

## Step nine: teaching it the market exists

The critic could already dock an idea for an obvious competitor, if the competitor showed up. It usually didn't. Our incumbent probe ran two generic searches, "best software tools for X," "X app pricing," and called that a market scan. On the cottage-food run, an idea for generating nutrition-facts panels scored 0.75, comfortably a "Go," while ReciPal, a company that already sells exactly that, with a landing page built for cottage-food bakers specifically, sat one search away and unfound.

We widened the probe in every direction that failure pointed. A third query now asks for the niche's actual toolbelt instead of enterprise software: it caught Aftershoot, a real incumbent our first pass missed entirely, on the very next run. A parallel leg hunts free and DIY substitutes, because "nobody sells this" and "everyone already does this for free" kill an idea the same way. A niche wallet probe reads the community's own spend norms, cottage bakers documenting "$0-25/mo, start free," wedding photographers stacking $100-plus a month across tools, and feeds that into the verdict instead of assuming every niche can support a subscription. A verified incumbent shipping an idea's core mechanism now caps its market fit outright, not just a note in prose; a SERP check looks at who actually owns page one before the SEO score assumes there's room to rank.

None of this is hidden reasoning. Every incumbent, price, and gap we find is shown to you directly, as parity chips on the idea and a market-reality table for the niche, and handed once to Deep Research, so the same facts don't get rediscovered, or disagreed with, three crews later.

## The part we're proudest of: the No-Gos

Here's the thing we'd tell anyone building an AI research product: the hardest engineering isn't making the system produce exciting answers. It's making it stop producing them when they aren't true.

Our cottage-food run still ends in a cautious verdict. The post-COVID home-baking wave is receding and the system says so, citing the trend data. The difference is that now the verdict sits on top of ideas that were given every honest chance: real data routes, product shapes people actually pay for, a critic checked against an independent reference panel.

When this system finally says "Go," we want it to mean something. Every change in this post had to beat saved runs before it reached a report. If it only sounded better but failed the benchmark, we threw it away. The same discipline that killed our favorite hypothesis is the reason we trust the pipeline that survived.

![A gauge needle resting at 0.46 in the No-Go zone. The discipline loop: benchmark against saved runs, keep only changes that win](/blog/no-go.svg)

## Step 10: pain was one lens, not the lens

Bundles kept winning. Every A/B we ran on the portfolio funnel, the synthesis stage that composes three to five pains into one workflow product, showed the same pattern: bundles outscored the best single-pain idea more often than chance should allow. We'd built bundles as a patch for one-pain-per-cell ideation's structural blind spot, buyers pay for products, not features. A patch that keeps outperforming the architecture it's patching isn't a healthy sign. It reads like a proxy quietly outscoring the thing it was standing in for.

So we finally asked the question we'd been dodging: what if pain point isn't the only place a good idea should start from? Every cell in our tournament system, this whole post up to now, is a validated pain crossed with an audience segment. That's a strong prior. Most real problems do trace back to somebody's stated pain. But it also means the generator can only ever propose what a pain already implies. A dataset that could obviously be assembled and sold never gets a cell of its own unless some Reddit thread happens to complain about not having it. A competitor's own pricing page, listing exactly what its paying customers wish it did, sits unread while the ideator reasons from scratch.

We didn't have to build new evidence to test this, we had it already, just pointed at other jobs. The incumbent probe (Step 9) already builds a verified map of competitors and their gaps. The data-route menu (Step 6) already verifies what a founder could legally and reliably assemble. And the audience work upstream of both already produces a job-map: the tools people use, what frustrates them about each, cast in the language of jobs-to-be-done. All three are evidence we generate and verify anyway, for other purposes, and then discard once the pain-point cells finish consuming it.

We turned each into its own generation lens: one extra cell per run for competitor-gap, one for data-asset, one for workflow, each seeded directly from that already-verified evidence instead of a fresh brainstorm. A data-asset cell doesn't get to invent a data source; it starts from the menu entry itself and asks what it's worth, and to whom. That lens also picked up a check none of the others needed: a publication-cadence test. If the product needs the data fresher than the source actually publishes it, the concept is unbuildable at birth, however good the dataset looks on paper.

The floor stayed pain-first on purpose. Pain-point cells keep reserve priority: every validated pain above the severity and commercial-evidence bars still gets its cell before the other three lenses touch what's left of the budget. We'd just spent the last several sections of this post proving that starving the pain-point track produces worse ideas, and nothing about this experiment was meant to relitigate that. Lens ideas run the identical gauntlet too: same critic, same route verification, same payability and parity checks, and each one still has to anchor back to a real, validated pain from the discussion or the cell gets dropped. A lens changes where a concept starts. It never changes what the concept has to survive.

We ran it across 8 niches before trusting it with real budget. The data-asset lens produced the first lens-born run-winner we'd seen: FunderCrosscheck, a tool that cross-checks duplicate grant-expense claims for nonprofit bookkeepers, scored 0.75 market fit, the first time a lens-born idea rather than one grown from a pain won its run outright. It also produced the only two variant-merges the whole A/B ever accepted, ideas different enough in framing to look like separate concepts, close enough in mechanism that the merge logic (Step 8) judged them one product. The competitor-gap lens never produced a run-winner across the 8 runs, but it consistently placed solid, mid-table survivors that gave the slate a genuine second angle instead of five variations on one pain. Workflow was the shakiest of the three, worse on average than the other two, but its wins were real wins, and by this stage of the pipeline a bad workflow idea doesn't linger: it either clears calibration and parity or it gets demoted to an honest finding like anything else. High variance we can live with, when the downside gets caught for free.

We tried a fifth lens too: spend-adjacent, seeded from the same wallet and toolbelt evidence the payability work (Step 9) already gathers, betting that budget signals alone might surface something the other four missed. They didn't. Every idea it proposed turned out to be a rephrasing of something the market-reality context already hands every other lens, the same competitor pricing and spend norms, read off the same evidence block. We dropped it. Four lenses, not five, and each one earned its slot the way everything else in this post did: by beating the saved-run benchmark, not by sounding good in a design doc.

Pain is still where most ideas start. It's just no longer the only door in.
