## What the scores actually mean

Every report comes with numbers attached, and we want to be straight about what they are. They're estimates, kept in check by guardrails, meant to point you in a direction. They are not promises, and they're not as precise as the decimals make them look. Here's how each one is built and how much weight to put on it.

### Pain point scores

Every pain point we surface has three scores, and they describe the problem, not a product.

**Severity** asks one thing: does this actually block someone's work? We score functional impact, not how loudly someone complains. "I'm so frustrated with this" is volume. "We lost three clients to invoicing delays" is severity. The scores sit on fixed, behaviour-based bands, because giving raters concrete reference points is the part of this with real research behind it ([Nielsen on usability severity ratings](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/)).

**Commercial intent** asks whether there's a buying signal: someone naming a paid tool they already use, mentioning a budget, or a problem that's eating their billable hours. Reading commercial intent from how people write is a well-studied, doable thing ([Jansen, Booth & Spink, 2008](https://doi.org/10.1016/j.ipm.2007.07.015)). What it is not is a dollar figure. You can't get a real willingness-to-pay without a pricing study where people react to actual prices, and public discussion simply can't give you that. Even properly-run surveys overstate what people will pay ([Schmidt & Bijmolt, 2020](https://doi.org/10.1007/s11747-019-00666-6)). So a high score means "there's a buying signal here," not "they'll pay you $X." (We used to call this "willingness to pay." We renamed it because that claimed more than the text can support.)

**Opportunity** combines the two: high when both are strong, medium when one is, low when neither. We weight them equally on purpose. For inputs that point the right way, simple equal weighting is famously hard to beat ([Dawes, 1979](https://doi.org/10.1037/0003-066X.34.7.571)). The cutoff itself is a reasonable rule of thumb, not a threshold we've tuned to the decimal. We don't have the outcome data yet (which ideas actually made money), so we'd rather tell you it's a heuristic than dress it up as something calibrated.

### The guardrails

We built every guardrail to do one job: pull a score down when it's been too generous. None of them can push a score up.

A pain with thin or missing evidence can't hold onto a high severity, however it was worded. If software can't realistically move the needle on a problem (something lifestyle, cultural, or structural), its commercial-intent score gets capped and it's kept out of idea generation, because there's no sense pricing a problem software can't touch. And generic emotional themes like burnout or stress, or anything that would read identically for any audience, get capped too. They don't tell you where the real opportunity is.

### The idea scores

Each generated idea gets its own set of scores, shown as percentages, with an overall composite (coloured green, amber, or red) and a conservative go / no-go signal. The five you'll read are: **market fit** (does this solve a validated problem for a reachable market?), **feasibility** (can it be built with today's tools, and can a solo founder actually get the data it needs, reliably and in bulk?), **solo-dev feasibility** (could one person ship it and keep it running, operating cost included?), **SEO** (can it grow organic traffic at scale? this one's a preliminary estimate, firmed up later with real keyword data), and **originality** (how non-obvious it is, where higher means fewer builders would land on the same thing).

The numbers don't come out of one pass. A creative pass floats the concepts first, and each one has to name the concrete data it would run on, or admit it doesn't need any. Anything that only gestures at its data gets caught right here. Then an independent reviewer pressure-tests each concept: it has to name the real route the data is obtainable in bulk, and if it can't, we treat the data as unverified and mark it down. That step kills most of the easy optimism. The survivors get written up into full ideas.

Here's the part worth knowing about the numbers you actually see: they aren't the idea's own self-grade. A model scoring its own work marks it generously ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)), so once an idea is written up, a separate model re-grades the main scores from scratch (market fit, feasibility, SEO, and how original it is) against the same bands, with its reasoning written out before each number. It leans conservative when the evidence is thin. So a 70% for market fit is a second opinion that already talked the first number down, not the idea's first impression of itself.

Sitting on top of that re-grade is a handful of hard caps, and these can only ever cut a score, never lift it. A named data source is a claim, not a fact: if the data is reachable only one record at a time, sits behind a login, or has no real bulk route, its data score gets capped. Build feasibility can't run far ahead of data feasibility, since you can't build on data you can't get. Running cost is weighed like build cost, so anything that needs constant moderation or hand-seeding takes a hit. An idea whose whole mechanism is publishing claims about named people or businesses gets marked down for the legal exposure, though we still show it to you with the concern flagged. And the SEO score gets pulled back whenever the "thousands of pages" story falls apart, since login-gated pages can't be indexed and a pile of hand-written blog posts isn't programmatic SEO.

Ideas are ranked on the composite of market fit, feasibility, novelty, and SEO. The piece that matters most for trust: that build-feasibility cap feeds the ranking too, so "can you actually build this?" drags fragile ideas down the list. What floats to the top is the part you can lean on, not the part with the best pitch.

### How to read them

Read these as bands, not decimals. A 0.63 and a 0.61 are the same thing. They reflect the discussion we found for your niche on the day we ran it, so more and better source material means better-calibrated scores. They're guides drawn from self-selected public conversation, not instruments measured against ground truth.

The point was never a perfect number. We'd rather hand you a cautious score with the reasoning attached than a confident one that falls apart the moment you push on it.

### Sources

- Jakob Nielsen, [Severity Ratings for Usability Problems](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/) (Nielsen Norman Group)
- Jansen, Booth & Spink (2008), [Determining the informational, navigational, and transactional intent of web queries](https://doi.org/10.1016/j.ipm.2007.07.015), *Information Processing & Management*
- Schmidt & Bijmolt (2020), [Accurately measuring willingness to pay: a meta-analysis of the hypothetical bias](https://doi.org/10.1007/s11747-019-00666-6), *Journal of the Academy of Marketing Science*
- Dawes (1979), [The robust beauty of improper linear models in decision making](https://doi.org/10.1037/0003-066X.34.7.571), *American Psychologist*
- Zheng et al. (2023), [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
