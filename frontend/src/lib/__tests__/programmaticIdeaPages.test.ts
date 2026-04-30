import { describe, expect, it } from 'vitest';
import { programmaticIdeaPages } from '$lib/data/programmaticIdeaPages';

describe('programmaticIdeaPages', () => {
  it('has unique valid slugs and SEO-safe copy lengths', () => {
    const slugs = new Set<string>();
    for (const page of programmaticIdeaPages) {
      expect(page.slug).toMatch(/^[a-z0-9-]+$/);
      expect(slugs.has(page.slug)).toBe(false);
      slugs.add(page.slug);
      expect(page.seoTitle.length).toBeLessThanOrEqual(60);
      expect(page.seoDescription.length).toBeLessThanOrEqual(160);
      expect(page.faqJson.length).toBeGreaterThanOrEqual(4);
      expect(page.faqJson.length).toBeLessThanOrEqual(15);
    }
  });

  it('requires curated featured idea slugs before the launch gate is disabled', () => {
    const launchGateOn = (process.env.SEO_LAUNCH_GATE ?? 'true') !== 'false';
    if (launchGateOn) return;

    for (const page of programmaticIdeaPages) {
      expect(page.featuredIdeaSlugs.length, `${page.slug} featuredIdeaSlugs`).toBeGreaterThanOrEqual(4);
    }
  });
});
