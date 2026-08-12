Ideas do not come out of one large brainstorm that gets filtered down. Strong, software-solvable problems get separate generation tracks, which reduces the chance that one easy theme crowds out the rest. Other tracks start from competitor gaps, usable data assets, and audience workflows. All candidates still have to pass the same later checks.

## One problem, one team

We start from strongly supported problems and screen out problems that software cannot directly address, such as structural or lifestyle conditions. A failed generation or validation step can still reduce the final set; the workflow does not manufacture a candidate to satisfy a quota.

Then each problem is paired with the audience that appears to feel it and gets its own propose-and-review loop. The active loop uses separate configured model families for refinement and review. The review asks whether the mechanism stays bound to the source problem, whether it is differentiated, and whether the build assumptions are plausible. Independent samples and a separate verification pass are design influences here, not proof that a generated idea is correct ([Wang et al., 2022, Self-Consistency](https://arxiv.org/abs/2203.11171); [Dhuliawala et al., 2023, Chain-of-Verification](https://arxiv.org/abs/2309.11495)).

The reason it is set up this way is coverage. Separate tracks make it harder for several candidates to converge on the same easy problem, while later deduplication removes candidates that still end up too similar.

Review and calibration are separate from generation. An independent calibration pass can replace an idea's self-assigned scores in either direction; deterministic rules then cap unsupported high scores. The checks look for close substitutes and for the data routes the product would require. Known public sources are matched against a maintained catalog and confirmed against the proposed use; other claims can be searched directly. A verified open route supports the feasibility case. A blocked, gated, per-item-only, or otherwise unsuitable route constrains the relevant scores. An unresolved route stays visibly unverified and must not be treated as available.

There's one more step for the ideas where the problem is strong but the solution is predictable. If a problem is clearly worth solving but the idea we landed on is the obvious one most builders would reach for, a model takes a second run at it, not to reword it but to find a genuinely more distinct mechanism for the *same* problem, built on the *same* data we already confirmed it can get. The rewrite only sticks if it actually comes out better: more distinct, and no weaker on whether it solves the problem or whether one person can build it. If it doesn't clear that bar, we keep the original. So this step can sharpen an idea, but it can't blunt one.

Finally we drop near-duplicates across the set ([SemDeDup, Abbas et al., 2023](https://arxiv.org/abs/2303.09540)), so you're not handed three versions of the same idea dressed up as three.

## Four ways an idea can start

Most ideas start life this way: one strong problem, its own team. But a problem isn't the only place a good idea can come from, so three more generation lenses run alongside the pain-point one, each starting from something we've already checked out for your niche rather than guessing:

- **Competitor gap** — built from a close look at where the tools people already use in this niche fall short: a real complaint, a missing feature, a review that says "wish it did X."
- **Data asset** — built from a dataset we've confirmed you could realistically assemble, asking what it would let someone build and who'd pay to see what it reveals.
- **Workflow** — built from a map of your audience's actual day-to-day work: the pains, what motivates them, and where their tools keep getting in the way.

Every idea from these three still has to trace back to a real, validated problem from the discussion, or it doesn't make the cut. It goes through the exact same scoring, the same feasibility and data checks, and the same critic as an idea that started life as one problem's own team. The only thing that changes is where it started, and that's the one thing we show you: a small **generation lens** tag on each idea, so you can tell whether it grew out of a pain, a competitor gap, a data opportunity, or a workflow friction. Your strongest, best-evidenced problems still get worked first; the other three lenses fill out what's left of the budget.

## What you'll see on each idea

The ranked list shows a Research score alongside market fit, feasibility, and a build estimate. The detail and comparison views can also show organic discovery and distinctiveness. These are directional scores, not a pre-Deep-Research Go / No-Go verdict. The [scoring page](/help/methodology) explains what each metric means and how far to trust it. Ideas also carry competition, substitute, data-access, and buyer-payability findings where those checks returned evidence.

One thing worth knowing about those numbers: the displayed core scores are not simply the generator's self-grade. A separate calibration pass re-scores the candidate against evidence and can abstain when a dimension is unsupported. Deterministic caps then apply known constraints, such as an unavailable data route. The result is still an estimate from model judgment and rules, not a measured probability ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)).

The tags fall into four buckets. **Strengths** name the qualities that stand out: strong demand fit, strong organic discovery, a distinct mechanism, technically straightforward, or solo-manageable. One may be called out as the primary strength. **Model** is how the idea works and sells: the product type, who it's for, and how it makes money. **Growth** is how it could realistically pick up users. **Watch-outs** name cautions such as a hard-to-run-solo build, a familiar approach, gated or gray-area data, and regulatory, terms, market, or trust risks. Tags describe evidence and trade-offs in plain language; they do not add points to an idea.

Two labels that sound similar describe different things. **Product shape** is the business archetype, such as SaaS, a directory, or a marketplace. **Delivered as** is the primary surface the buyer uses, such as a browser extension, API, mobile app, report, or service. Older ideas may have only Product shape; the interface does not invent a delivery format for them.

## Each idea is judged on the angle that actually wins for it

Not every idea wins the same way, so we don't grade them all on the same thing. There are three ways an idea can earn its place: it can win by being **found** (lots of SEO pages plus a way to reach people), by being **genuinely different** (a mechanism competitors can't easily copy), or by **owning a workflow** for one specific kind of user. We label each idea with the one that fits it and judge it on that. This is a different label from the generation lens above: the lens is where an idea started (a pain, a competitor gap, a data opportunity, a workflow friction), the angle is how it actually wins once it exists. A workflow-lens idea doesn't have to win by owning a workflow, and plenty of pain-point ideas do.

This matters most for catalog and directory ideas. A directory can win by being found and by presenting a useful slice of data better than the alternatives, even when its mechanism is familiar. Its Distinctiveness rating describes how far its approach departs from obvious alternatives; the accompanying explanation says where the idea's real edge is meant to live.

You also get a steer. The **Idea focus** control has three settings: **Auto** lets us pick the right angle for each idea, which is the default. **Differentiation** and **Distribution** lean both the ideas we come up with and the way we rank them toward that one angle, so you see more of what you're after. It changes the emphasis, not the honesty: every idea still gets the angle label that actually fits it, whatever you set the focus to. The same control shows up when you ask for more ideas, so you can change the lean batch by batch.

One last thing on the selection screen: a single line reads out how the niche's ideas split across these angles, for example "Distribution-leaning niche: 3 of 5 viable ideas win by being found (SEO), not through a distinct mechanism." It's a quick way to see what kind of opportunity this niche actually is before you dig in.

## The strongest ideas get one more fight before you see them

Scoring an idea well and an idea surviving contact with the real world aren't the same test, so a slice of the pool goes through one more round before it reaches you: an adversarial review (internally we sometimes call it a red-team pass). The slice covers different kinds of risk rather than one leaderboard. It takes the idea most likely to become the recommendation, the most *shippable* candidate (the one a single builder could realistically build and run), and the strongest of the rest. Fresh web searches then look specifically for reasons the idea might not hold up — a competitor that shows up under the category's own name rather than the idea's phrasing, a capability some other tool already gives away for free, a mechanism that handles the clean version of the problem but not the messy one most users actually have.

Every finding comes with the evidence attached, and the review lands on one of three calls. The idea survives, it comes out weakened, or the review can't find evidence for the premise the whole idea rests on, usually that a reachable buyer wants this at all. That last call is marked **premise unproven**. It doesn't remove the idea or rewrite its scores, because those scores describe how well the idea would work if the premise holds; it does mean the idea won't be put forward as the recommendation until someone tests the premise. The [scoring page](/help/methodology) explains how to read a high score sitting next to that mark.

A search can also come back empty, or come back about a plainly different industry, which happens when an idea's own wording collides with someone else's vocabulary. Then nothing changes. We don't invent a flaw to justify the step, we don't treat silence as a clean bill of health, and we don't let a bad search masquerade as market evidence.

When the review finds something fixable, we take one shot at repairing it. The rewrite has to earn its way back in through the exact same scoring the original went through — same critic, same checks — or the original stands, caveats and all. This isn't cosmetic. In one case it turned a plain lookup tool (a commodity three other sites already offer) into an eligibility check plus the paperwork it triggers. That's a sharper, harder-to-copy version of the same idea, and it's the one an independent human review had arrived at on its own.

The selection screen can include a **Discovery take** or analyst guidance, but only when it is safely tied to the current idea records. Stored prose is not allowed to assign a recommendation badge or override the score ranking on its own. If the saved guidance is no longer bound to the exact current revisions, the screen marks it unavailable and tells you to use the current scores and evidence instead.

## The list is organised by the job, not by the idea

The selection screen doesn't hand you a flat run of ideas. It groups them by the job someone would be hiring a product to do: one card per **product thesis**, with that thesis's variants nested underneath it. The card carries what the whole family shares: who the buyer is, the job that sets them looking, whether anyone already occupies that ground, and any assumption that would sink every variant in the card if it turned out false. The variants differ in how they'd do the job, not in what the job is.

Expect fewer things to read, across more genuinely different businesses. Four similar-looking ideas in a row become one thesis with four variants, which is what they were all along. Every variant keeps its rank, its scores and its place in your shortlist; the grouping changes how the pool is presented, not what's in it. A line above the list sums it up: how many buyer jobs were examined, how many turned into theses, and how many came out with nothing. Anything generated after the grouping was worked out — an extra batch, an idea you seeded — sits in its own "added after grouping" card and behaves exactly like the rest.

The jobs that came out with nothing get their own section: **validated buyer jobs with no surviving idea**. The pain research confirmed people have these problems; nothing in the ranked list addresses them, because nothing we generated for them survived the checks. That's a finding, not a hole in the report, and it's often the more useful half. A confirmed problem with no good answer in it is worth knowing about. Unexamined is not the same as ruled out.

## What to keep in mind

The set aims for breadth across strong problems and the additional generation lenses, but a lens can produce no viable candidate and later checks can remove one. Review models can still miss subtle infeasibility, so treat every feasibility score as a reasoned estimate, not a guarantee.

## Sources

- Wang et al. (2022), [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171)
- Dhuliawala et al. (2023), [Chain-of-Verification Reduces Hallucination in Large Language Models](https://arxiv.org/abs/2309.11495)
- Abbas et al. (2023), [SemDeDup: Data-efficient learning at web-scale through semantic deduplication](https://arxiv.org/abs/2303.09540)
- Zheng et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
