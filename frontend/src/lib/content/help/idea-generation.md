Ideas don't come out of one big brainstorm that gets filtered down. Each of your strongest problems gets worked on its own, by its own small team, so you end up with one well-argued idea per problem instead of ten flavours of whichever problem the brainstorm happened to fixate on.

### One problem, one team

We start from the strongest problems, the ones with real severity and evidence behind them, and skip the ones software can't actually solve (the lifestyle and structural stuff), so nothing gets wasted inventing tools for non-tool problems.

Then each problem, paired with the audience that actually feels it, gets its own back-and-forth. One model proposes ideas from a fresh angle. A second model — a different family, so it isn't grading its own homework — pushes back: is this genuinely novel, can a solo dev build it, and does it still solve *this* problem rather than some bigger one nobody asked for? They go a couple of rounds and the best version wins. Proposing from several independent angles is a well-worn way to get more out of this kind of reasoning ([Wang et al., 2022, Self-Consistency](https://arxiv.org/abs/2203.11171)), and a second model checking the work catches the confident mistakes ([Dhuliawala et al., 2023, Chain-of-Verification](https://arxiv.org/abs/2309.11495)).

The reason it's set up this way: when every strong problem gets its own team, the best ones can't quietly fall out of a shared pool. The highest-value problem in your niche is guaranteed an idea, instead of being the thing that got merged away while the model polished three variations of an easier one.

A critic scores each idea for novelty and feasibility, and it can only ever lower a score. It names the closest existing tool, so "a thinner version of something that already ships" gets caught, and it flags whether the data an idea needs is even gettable. We learned one thing the hard way: a model told to "make it more buildable" will cheerfully invent an official API that doesn't exist. So no model gets to claim a data source is real — every idea's data routes get checked, whichever path it took into the set. Sources the world already knows are open (government registries, official statistics, the big public APIs) are recognized against a maintained catalog of public data sources, with a second model confirming the idea actually needs what that source publicly provides; everything else goes through a web search. If the check turns up a genuine public source, the idea keeps its score; if it shows the data is removed, gated, or doesn't exist, market fit gets capped honestly; and if it can't confirm or deny either way, we don't punish the idea on a guess — it's marked "unverified" so you know to check the data is gettable before you build.

There's one more step for the ideas where the problem is strong but the solution is predictable. If a problem is clearly worth solving but the idea we landed on is the obvious one most builders would reach for, a model takes a second run at it — not to reword it, but to find a genuinely more original mechanism for the *same* problem, built on the *same* data we already confirmed it can get. The rewrite only sticks if it actually comes out better: more original, and no weaker on whether it solves the problem or whether one person can build it. If it doesn't clear that bar, we keep the original. So this step can sharpen an idea, but it can't blunt one.

Finally we drop near-duplicates across the set ([SemDeDup, Abbas et al., 2023](https://arxiv.org/abs/2303.09540)), so you're not handed three versions of the same idea dressed up as three.

### What you'll see on each idea

The scores (shown as percentages, with an overall green / amber / red composite and a conservative go / no-go) are market fit, feasibility, solo-dev feasibility, SEO, and originality. The [scoring page](/help/methodology) goes into what each one means and how far to trust it. Each idea also carries a web-verified competition check (including whether a free or do-it-yourself route already delivers the outcome, and whether the mechanism is already sold commercially in an adjacent market under a different audience), plus a read on [who actually pays and how often they'd use it](/help/methodology) — because a loud pain sold to a buyer without a wallet is not a business.

One thing worth knowing about those numbers: they aren't the idea's own self-grade. The model that comes up with an idea tends to like its own work and marks it generously, so once an idea is written up in full a separate model goes back over it and re-scores it against the same yardstick, leaning conservative when the evidence is thin ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)). So a 70% for market fit is a second opinion that has already argued the optimism back down, not the first number the idea gave itself.

The tags fall into four buckets. **Strengths** are what an idea is genuinely good at (market fit, SEO power, originality, quick to build, solo-friendly), and the standout one gets called out as its "superpower." **Model** is how it works and sells: the product type, who it's for, and how it makes money. **Growth** is how it would realistically pick up users. And **Watch-outs** are the honest cautions, the hard-to-build, the unoriginal, the gated or grey-area data, and risk flags like regulatory, terms-of-service, grey-market, or trust-dependent. Some of these are judgement calls and some are read straight off the scores, and there's a one-line note explaining the calls that aren't obvious.

### Each idea is judged on the angle that actually wins for it

Not every idea wins the same way, so we don't grade them all on the same thing. There are three ways an idea can earn its place: it can win by being **found** (lots of SEO pages plus a way to reach people), by being **genuinely different** (a mechanism competitors can't easily copy), or by **owning a workflow** for one specific kind of user. We label each idea with the one that fits it and judge it on that.

This matters most for the catalog-and-directory ideas. A directory wins by being found and by holding a slice of data nobody else has, not by some clever trick. So when one of those scores low on novelty, we don't hold it against the idea: a low-novelty score is normal for that kind of product, and that isn't the game it's playing. The novelty score comes with a one-line note telling you why it reads the way it does for that type of idea.

You also get a steer. The **Idea focus** control has three settings: **Auto** lets us pick the right angle for each idea, which is the default. **Novelty** and **Distribution** lean both the ideas we come up with and the way we rank them toward that one angle, so you see more of what you're after. It changes the emphasis, not the honesty: every idea still gets the angle label that actually fits it, whatever you set the focus to. The same control shows up when you ask for more ideas, so you can change the lean batch by batch.

One last thing on the selection screen: a single line reads out how the niche's ideas split across these angles, for example "Distribution-leaning niche: 3 of 5 viable ideas win by being found (SEO), not by a novel mechanism." It's a quick way to see what kind of opportunity this niche actually is before you dig in.

### What to keep in mind

The set covers your strongest problems roughly one apiece, so you're seeing breadth by design rather than three takes on the same idea. The critic can still miss subtler infeasibility, so treat feasibility as a strong hunch, not a guarantee.

### Sources

- Wang et al. (2022), [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171)
- Dhuliawala et al. (2023), [Chain-of-Verification Reduces Hallucination in Large Language Models](https://arxiv.org/abs/2309.11495)
- Abbas et al. (2023), [SemDeDup: Data-efficient learning at web-scale through semantic deduplication](https://arxiv.org/abs/2303.09540)
- Zheng et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
