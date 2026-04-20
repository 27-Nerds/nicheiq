/**
 * Hardcoded placeholder data for the LOCKED teaser sections on the shared
 * discovery view. Rendered behind CSS blur; visitor cannot see real values.
 * Kept intentionally abstract (glyph filler, no plausibly-fake names) so the
 * visitor understands "data exists, unlock to see" without being misled.
 *
 * SECURITY BOUNDARY: `filter: blur(5px)` is cosmetic, not redaction. Real
 * text rendered in HTML is readable via DevTools. These constants MUST stay
 * as placeholder glyphs — never interpolate real niche data here.
 */

import type { Influencer } from '$lib/types/report';

/** Fake influencer rows. Typed as `Influencer` so they drop into the shared
 *  AudienceSection's existing influencer-card loop without a separate type. */
export const LOCKED_INFLUENCERS: Influencer[] = Array.from({ length: 5 }, () => ({
  name: '████████ ██████',
  platform: 'Reddit',
  follower_estimate: '██K',
  content_focus: '████ ███████ ████████████ ██████████',
  top_subreddits: ['████████', '██████████'],
}));

export interface LockedSourcePost {
  title: string;
  subreddit: string;
  score: string;
  age: string;
}

export const LOCKED_SOURCE_POSTS: LockedSourcePost[] = Array.from({ length: 5 }, () => ({
  title: '████████ ██████████ ██████ ████ ████████████',
  subreddit: '████████',
  score: '██',
  age: '██d',
}));
