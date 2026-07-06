NicheIQ isn't one big AI prompt. A report gets put together by a pipeline of small, specialised steps, each doing one job and handing its work to the next. We want to explain how that's wired up, mostly because it's the reason we trust the output more than we'd trust a single model asked to "research this niche."

### Lots of small jobs, not one big one

A single run leans on more than thirty specialised agents across a pipeline of specialised stages — and some stages, like idea generation, are multi-step systems of their own, with tournaments, critics, and verification passes. Each agent has a narrow job: read your niche, decide whether a thread is relevant, pull a specific problem out of a discussion, poke holes in an idea's feasibility, and so on. Cutting the work up this way means we can make each step genuinely good at its own task instead of asking one model to juggle everything at once.

Those agents pull from around nine data tools that reach into the real world, the community discussions (Reddit, Hacker News), the web and keyword-demand searches, and the fetchers behind them. The research is grounded in live data, not whatever the model happens to remember.

### A different model for each job

Different steps want different things. Classifying thousands of search hits has to be fast and cheap. Scoring an idea's feasibility needs careful judgement. Writing the final copy needs to come out clean and complete. So we don't run one model everywhere; there are fifteen-plus separate model choices, one per step.

And we don't pick them by gut. Before a model gets wired into a step, we run the candidates head-to-head on real examples from that exact task and compare them on what matters there: accuracy, consistency, speed, cost. The best fit wins. When a stronger model shows up, we run the comparison again and switch only if it's a real improvement, not just a newer name.

### Nothing ships untested

The instructions each agent follows get tuned constantly, but a change has to earn its place. When we adjust a prompt or swap a model, we A/B-test it against real past runs, examples where we already know what good output looks like. So a tweak that sounds smart has to actually produce better results on real data before it goes live. Plenty of clever-sounding changes get thrown out because the numbers don't move.

### Guardrails that only subtract

The quality comes from guardrails, not optimism, and they all work the same way: they can pull a score down, never up. A claim that isn't backed by the gathered discussion gets capped. Every quote we display is checked against the post it's attributed to. And if a single step trips, the run falls back to what it can verify instead of inventing something to fill the hole. It fails safe rather than fails loud.

### Always being sharpened

None of this is frozen. We revisit the models and the prompts as better options turn up and as we learn from real runs. Through all of it we tune for output that's honest and a little conservative rather than output that just looks impressive. We'd take a cautious number with its reasoning attached over a confident one that doesn't survive a second look, every time.

It's still AI-assisted research, so what you get are well-guarded estimates, not guarantees. But the whole point of this machinery is to make those estimates as trustworthy, and as honest about where they stop, as we can manage.
