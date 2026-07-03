# How our idea-generation pipeline learned to stop lying to itself

*July 2026*

When we started NicheIQ, the idea stage was one big prompt: here's a niche, here are some pain
points from Reddit, give us ten SaaS ideas. It worked the way most LLM products work at first.
Impressively, until you looked closely.

The ideas scored themselves. Every single one came back with a market-fit score around 0.88. Ten
ideas, ten different mechanisms, ten near-identical scores. A model grading its own homework gives
itself an A, every time.

This is the story of how we rebuilt that stage, what broke along the way, and why our system now
sometimes tells you *not* to build anything. We think that last part is the most valuable thing it
does.

## Step one: stop pooling, start partitioning

The first structural change was splitting one big ideation call into per-cell tournaments. Each
validated pain point, crossed with an audience segment, gets its own small competition: a few
concepts generated from that cell's specific viewpoint, an ideator-and-judge loop that sharpens the
best one, and one winner per cell.

That fixed coverage. Every important pain got at least one idea instead of whatever the single big
prompt happened to gravitate to. But it introduced a quieter problem we didn't notice for months:
the judge inside each cell picks a winner *before* our strongest evaluator ever sees the
candidates. Roughly two thirds of everything we generated was being thrown away on a first
impression.

## Step two: an independent critic, and the day it disagreed with us

The self-scoring problem we fixed with a separate calibration critic: a different model, blind to
the generator's scores, re-scoring every idea against fixed rubrics. The wall of 0.88s collapsed to
honest 0.35–0.65s.

Then we asked a harder question. Is the *critic* honest? We built a benchmark of 61 ideas across
six niches, each scored by a neutral senior-advisor model as ground truth, and measured agreement.
The result inverted our assumptions. We'd believed the critic was too harsh on unglamorous
SEO-style ideas. It was actually too *generous* on market fit, by +0.13 on average, awarding 14
"Go" verdicts where the neutral panel awarded zero.

One bounded prompt rule (treat pain severity as a ceiling, discount for unproven mechanisms and
crowded markets) cut that optimism in half. Meanwhile a change we'd been convinced was right,
teaching the critic to stop penalizing "obvious" SEO ideas, failed the same benchmark decisively
and never shipped. The benchmark caught both: the fix we needed and the fix we only wanted.

## Step three: the run that exposed everything

In early July we ran the full pipeline on a niche we picked precisely because it should have been
easy: home bakers selling under cottage food laws. Real communities, real search demand, real
money. People in this niche already pay $7–49/month for tools like CakeBoss and Bakesy.

The run produced five ideas. The best scored 0.46. The verdict: No-Go.

The autopsy was humbling. Four of the five ideas were built on data that doesn't exist or can't be
had: smart-oven telemetry from home bakers, scraped supplier sites, cold-start crowdsourced
databases. The generator invented mechanisms first and met reality later, when the critic capped
every unverifiable mechanism at 0.45. Meanwhile the pain cluster this niche's actual paid products
are built on, recipe costing and pricing, got no idea at all. It lost the cell allocation lottery.

And one more thing, found by accident. The tournament judge had discarded a concept, an
allergen-verified bakery directory, that our critic scored higher than four of the five winners
once we finally showed it the losers.

## Step four: the portfolio funnel

Everything we shipped next follows from that one run.

Ideas now start from data that exists. Before generation, we build a verified data-route menu for
the niche: official registries, public agency pages, licensed APIs, plain arithmetic on the user's
own inputs. Every generator brief must anchor its mechanism on that menu. On the same pains, with
the same critic, this single change lifted the best idea from 0.46 to 0.72.

Losers get a second opinion. After the tournaments, the full critic scores the discarded concepts
in one cheap batch, and anything near or above its own cell's winner gets rescued, fully developed,
and labeled honestly in the report as a rescued concept. In testing this recovered one real idea
per niche. Those are ideas the first-impression judge had thrown away.

We compose, not just generate. Single-pain tools are features; buyers pay for products. A synthesis
stage now bundles three to five complementary pains into one product around a real workflow, which
is the CakeBoss shape. On the astrophotography niche the bundled "Siril-to-PixInsight Results Kit"
scored 0.74 against a 0.63 baseline.

And we look up the actual competition. Community discussions surface generic tools like Canva and
QuickBooks, not the incumbents an idea has to beat. A quick web probe now maps the real paid
products, their pricing, and their gaps, and both the generator and the critic see that map.

The user-visible result: instead of five thin ideas topping out at 0.46, a report now carries a
tiered portfolio. A flagship product, usually a bundle. Focused single-problem tools under it. The
occasional rescued concept. Typically eight ideas instead of five, with the top ones scoring where
"worth a serious look" actually begins.

## The part we're proudest of: the No-Gos

Here's the thing we'd tell anyone building an AI research product: the hardest engineering isn't
making the system produce exciting answers. It's making it stop producing them when they aren't
true.

Our cottage-food run still ends in a cautious verdict. The post-COVID home-baking wave is receding
and the system says so, citing the trend data. The difference is that now the verdict sits on top
of ideas that were given every honest chance: real data routes, product shapes people actually pay
for, a critic calibrated against independent ground truth.

When this system finally says "Go," we want it to mean something. Every change in this post was
gated the same way. Build it dark, test it against a benchmark that can say no, ship it only when
it wins, and delete the flag afterward. The same discipline that killed our favorite hypothesis is
the reason we trust the pipeline that survived.
