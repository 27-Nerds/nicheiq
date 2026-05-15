import { describe, expect, it } from 'vitest';

import { reduceParentSourceMetric } from '../catalogService.js';

type Ctx = Parameters<typeof reduceParentSourceMetric>[0][number];

function ctx(over: Partial<Ctx> = {}): Ctx {
  return {
    redditPostsAnalyzed: null,
    twitterThreadsAnalyzed: null,
    genericPostsAnalyzed: null,
    topSubreddits: null,
    ...over,
  };
}

describe('reduceParentSourceMetric()', () => {
  it('returns zero pair for an empty input list', () => {
    expect(reduceParentSourceMetric([])).toEqual({
      contentItemsMined: 0,
      sourceCommunities: 0,
    });
  });

  it('sums reddit + twitter + generic across contexts, treating null as 0', () => {
    const result = reduceParentSourceMetric([
      ctx({ redditPostsAnalyzed: 48, genericPostsAnalyzed: 2, twitterThreadsAnalyzed: 0 }),
      ctx({ redditPostsAnalyzed: 84, genericPostsAnalyzed: 1 }), // twitter null
      ctx(), // all null → contributes 0
    ]);
    expect(result.contentItemsMined).toBe(48 + 2 + 84 + 1);
  });

  it('unions distinct subreddit names across contexts (overlap counted once)', () => {
    const result = reduceParentSourceMetric([
      ctx({
        topSubreddits: [
          { name: 'SaaS', post_count: 12 },
          { name: 'Entrepreneur', post_count: 7 },
        ],
      }),
      ctx({
        topSubreddits: [
          { name: 'Entrepreneur', post_count: 4 }, // duplicate of above
          { name: 'startups', post_count: 9 },
        ],
      }),
    ]);
    expect(result.sourceCommunities).toBe(3);
  });

  it('trims whitespace before dedup so " saas " and "saas" collapse', () => {
    const result = reduceParentSourceMetric([
      ctx({ topSubreddits: [{ name: ' saas ' }] }),
      ctx({ topSubreddits: [{ name: 'saas' }] }),
    ]);
    expect(result.sourceCommunities).toBe(1);
  });

  it('ignores malformed topSubreddits entries (non-array, non-object, missing name, empty)', () => {
    const result = reduceParentSourceMetric([
      ctx({ topSubreddits: 'not-an-array' }),
      ctx({ topSubreddits: null }),
      ctx({
        topSubreddits: [
          null,
          'bare string',
          { post_count: 3 }, // missing name
          { name: '' }, // empty after trim
          { name: '   ' }, // whitespace only
          { name: 'ValidOne' },
        ],
      }),
    ]);
    expect(result.sourceCommunities).toBe(1);
  });

  it('returns zero pair when every context contributes nothing', () => {
    const result = reduceParentSourceMetric([ctx(), ctx(), ctx({ topSubreddits: [] })]);
    expect(result).toEqual({ contentItemsMined: 0, sourceCommunities: 0 });
  });
});
