## How ideas are generated

Ideas don't come out of a single brainstorm. They run through a funnel that's deliberately wide at the top and ruthless after that, so what you're left with is a handful of distinct, defensible options instead of ten flavours of the same thing.

### The funnel

We start from the strongest problems, the ones with real severity and evidence behind them, and we skip the ones software can't actually solve (the lifestyle and structural stuff), so nothing gets wasted inventing tools for non-tool problems.

From there we brainstorm the same problems from several independent angles and personas at once. Different starting points tend to produce genuinely different ideas rather than near-copies, and sampling several independent attempts and weighing them up is a well-worn way to get more out of this kind of reasoning ([Wang et al., 2022, Self-Consistency](https://arxiv.org/abs/2203.11171)). Then a separate critic goes through every concept and scores it for novelty and feasibility, and it can only ever lower a score. It names the closest existing tool, so "a thinner version of something that already ships" gets caught, and it flags whether the data an idea needs is even obtainable. Having a model check its own work like this is a known way to cut the confident mistakes ([Dhuliawala et al., 2023, Chain-of-Verification](https://arxiv.org/abs/2309.11495)).

After that we drop the duplicates ([SemDeDup, Abbas et al., 2023](https://arxiv.org/abs/2303.09540)), keep a varied shortlist, and write the survivors up in full, each with a reason it isn't obvious rather than just a description. The last step spreads the final set across audiences, mechanisms, and product types, while protecting one deliberately bold idea and any idea that's the only one covering a strong problem.

There's one more pass, but only on the survivors that come out weak: thin, a bit me-too, or leaning on data they probably can't get. Those go through a short back-and-forth with a second model acting as a creative mentor, whose only job is to push the idea toward something sharper and more original that still solves the *same* problem, without bloating it into a bigger product nobody asked for. We learned one thing the hard way here: a model told to "make it more buildable" will cheerfully invent an official API that doesn't exist. So the mentor never gets to claim a data source is real. The idea flags any route it's unsure about, and a separate web search actually checks whether that data is gettable ([Chain-of-Verification, Dhuliawala et al., 2023](https://arxiv.org/abs/2309.11495)). If it isn't, the market-fit score gets capped honestly instead of the idea pretending the data is there. Ideas that are already strong and built on obtainable data skip this pass untouched.

### What you'll see on each idea

The scores (shown as percentages, with an overall green / amber / red composite and a conservative go / no-go) are market fit, feasibility, solo-dev feasibility, SEO, and originality. The [scoring page](/help/methodology) goes into what each one means and how far to trust it.

One thing worth knowing about those numbers: they aren't the idea's own self-grade. The model that comes up with an idea tends to like its own work and marks it generously, so once an idea is written up in full a separate model goes back over it and re-scores it against the same yardstick, leaning conservative when the evidence is thin ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)). So a 70% for market fit is a second opinion that has already argued the optimism back down, not the first number the idea gave itself.

The tags fall into four buckets. **Strengths** are what an idea is genuinely good at (market fit, SEO power, originality, quick to build, solo-friendly), and the standout one gets called out as its "superpower." **Model** is how it works and sells: the product type, who it's for, and how it makes money. **Growth** is how it would realistically pick up users. And **Watch-outs** are the honest cautions, the hard-to-build, the unoriginal, the gated or grey-area data, and risk flags like regulatory, terms-of-service, grey-market, or trust-dependent. Some of these are judgement calls and some are read straight off the scores, and there's a one-line note explaining the calls that aren't obvious.

### What to keep in mind

We don't force an even spread across problems. If the best ideas all land on one problem, that's often a sign the value really is there, so we show you the concentration instead of breaking it up for the sake of variety. The critic can also miss subtler infeasibility, so treat feasibility as a strong hunch, not a guarantee. And the bold idea is chosen for novelty, not market fit, so it's there to widen your options and it may carry more risk than the rest.

### Sources

- Wang et al. (2022), [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171)
- Dhuliawala et al. (2023), [Chain-of-Verification Reduces Hallucination in Large Language Models](https://arxiv.org/abs/2309.11495)
- Abbas et al. (2023), [SemDeDup: Data-efficient learning at web-scale through semantic deduplication](https://arxiv.org/abs/2303.09540)
- Zheng et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
