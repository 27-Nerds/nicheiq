Pain points are the problems we catch people actually talking about. They come out of public discussion, mostly forums and community threads (Reddit, Hacker News, with more sources over time), so they're things people chose to post about in the open. We didn't run a survey.

## From conversation to problem

It runs roughly like this. We turn your niche into a lot of targeted searches, phrased the way people actually describe problems ("anyone else…", "how do you deal with…", "stuck on…"), and gather the threads that come back. Most search hits aren't really on topic, so we filter down to the ones that are, and we show you how many we scanned versus how many we kept, because we'd rather you see the funnel than trust a black box.

Before we analyse anything we collapse near-identical discussions, so a popular post that got re-shared ten times doesn't show up as ten separate problems ([SemDeDup, Abbas et al., 2023](https://arxiv.org/abs/2303.09540)). Then we cluster the conversations into themes and split each theme into specific, concrete problems. "Can't confirm a part is compatible before buying" is a pain point. "Hardware issues" isn't.

Every problem we keep is backed by real quotes from the discussions, and here's the part we care about most: we check that each quote you see actually appears in the post it's attributed to, so nothing gets paraphrased into something the person never said. Tying claims back to checkable source text is a known way to stop AI summaries from drifting ([Gao et al., 2023](https://arxiv.org/abs/2305.14627)). Finally each problem gets scored for severity and buying signal, and [How scoring works](/help/methodology) covers what those numbers mean and how far to trust them.

There's one more pass we're glad made the cut: a check that the problems actually reflect the whole audience in the discussion, not just its loudest corner. Competitive players venting tend to drown out quieter groups (spectators, collectors, event organizers) even when the community clearly talks about them too. So after the first read we compare the problems we found against who's really posting, and if a genuine part of the audience got crowded out, we go back and pull their problems as well. We only keep that second pass when it fills the gap without dropping anything that was already there.

## What to keep in mind

This is a self-selected sample. We only see the people who chose to post. The quieter majority, and anyone who just solves the problem without writing about it, isn't in here, so think of prevalence as "how much it gets talked about," not "how many people have it."

It also skews recent. Active, current discussion is easier to surface than old threads, so a long-standing problem can be under-counted unless people are still bringing it up. And loud isn't the same as severe. Strong frustration doesn't automatically mean a problem blocks real work, which is exactly why the severity score is built to separate the two ([Nielsen on severity ratings](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/)).

## Sources

- Abbas et al. (2023), [SemDeDup: Data-efficient learning at web-scale through semantic deduplication](https://arxiv.org/abs/2303.09540)
- Gao et al. (2023), [Enabling Large Language Models to Generate Text with Citations](https://arxiv.org/abs/2305.14627)
- Jakob Nielsen, [Severity Ratings for Usability Problems](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/) (Nielsen Norman Group)
