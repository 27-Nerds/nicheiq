import { describe, it, expect } from 'vitest';
import {
  parentCategoryDescription,
  categoryLede,
  buildCategoryJsonLd,
} from '../catalogSeo';
import type { CategoryLandingPayload } from '$lib/types/catalog-landing';

// Minimal payload fixture builder. Mutators are supplied via partial overrides
// at the call site so each test focuses on the one shape feature it asserts.
function makePayload(over: Partial<CategoryLandingPayload> = {}): CategoryLandingPayload {
  // Spread `over` BEFORE the category block so the merged category below
  // wins. Order matters: a bare `...over` at the bottom would clobber the
  // carefully composed category with whatever shape the caller supplied.
  const { category: categoryOver, ...rest } = over;
  return {
    parent: null,
    superGroup: null,
    children: [],
    siblings: [],
    topIdeas: [],
    topPainPoints: [],
    totalIdeas: 27,
    totalPainPoints: 99,
    contentItemsMined: 120,
    sourceCommunities: 0,
    qualitySignals: null,
    nicheContext: null,
    latestModifiedAt: '2026-05-14T08:30:00.000Z',
    ...rest,
    category: {
      id: 'cat1',
      name: 'Design & Creative Tools',
      slug: 'design-creative-tools',
      description: 'UI/UX design, prototyping, and creative production software',
      seoTitle: null,
      seoDescription: null,
      longDescription: null,
      faqJson: null,
      faqJsonMeta: null,
      tags: [],
      isActive: true,
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-05-14T12:00:00.000Z',
      ...categoryOver,
    },
  } as CategoryLandingPayload;
}

function makeChild(name: string, ideaCount: number) {
  return {
    id: `c-${name}`,
    name,
    slug: name.toLowerCase().replace(/\s+/g, '-'),
    description: null,
    ideaCount,
    painPointCount: 0,
  };
}

describe('parentCategoryDescription()', () => {
  it('honors the seoDescription admin override verbatim', () => {
    const payload = makePayload({
      category: { seoDescription: 'Curated copy from admin.' } as Partial<
        CategoryLandingPayload['category']
      > as CategoryLandingPayload['category'],
    });
    expect(parentCategoryDescription(payload)).toBe('Curated copy from admin.');
  });

  it('builds the full dynamic template when ≥4 children exist (appends ", and more")', () => {
    const payload = makePayload({
      children: [
        makeChild('UI/UX Design Tools', 5),
        makeChild('Photo Editing & Management', 4),
        makeChild('Logo Design', 3),
        makeChild('Drawing & Illustration', 2),
      ],
    });
    expect(parentCategoryDescription(payload)).toBe(
      'Explore 27 startup ideas across 4 Design & Creative Tools sub-niches — UI/UX Design Tools, Photo Editing & Management, Logo Design, and more. 99 validated pain points sourced from 120 real community discussions.',
    );
  });

  it('omits ", and more" when children.length === 3', () => {
    const payload = makePayload({
      children: [
        makeChild('UI/UX Design Tools', 5),
        makeChild('Photo Editing & Management', 4),
        makeChild('Logo Design', 3),
      ],
    });
    expect(parentCategoryDescription(payload)).toContain(
      'UI/UX Design Tools, Photo Editing & Management, Logo Design.',
    );
    expect(parentCategoryDescription(payload)).not.toContain(', and more');
  });

  it('renders singular "sub-niche" when only one child', () => {
    const payload = makePayload({ children: [makeChild('UI/UX Design Tools', 1)] });
    // Singular: "1 Design & Creative Tools sub-niche — UI/UX Design Tools"
    expect(parentCategoryDescription(payload)).toContain(
      '1 Design & Creative Tools sub-niche — UI/UX Design Tools.',
    );
  });

  it('drops the "— top3" segment cleanly when no children, no dangling em-dash', () => {
    const payload = makePayload({ children: [] });
    const out = parentCategoryDescription(payload);
    expect(out).not.toContain(' — ');
    expect(out).toBe(
      'Explore 27 startup ideas across 0 sub-niches in Design & Creative Tools. 99 validated pain points sourced from 120 real community discussions.',
    );
  });

  it('breaks ideaCount ties by name.localeCompare', () => {
    const payload = makePayload({
      children: [
        makeChild('Banana', 5),
        makeChild('Apple', 5),
        makeChild('Cherry', 5),
        makeChild('Date', 5),
      ],
    });
    // Three children tie on ideaCount=5; alphabetical wins. Apple < Banana < Cherry.
    expect(parentCategoryDescription(payload)).toContain('Apple, Banana, Cherry, and more');
  });

  it('drops the "sourced from" clause when contentItemsMined is 0', () => {
    const payload = makePayload({
      contentItemsMined: 0,
      children: [makeChild('A', 1)],
    });
    const out = parentCategoryDescription(payload);
    expect(out).not.toContain('sourced from');
    expect(out).not.toContain('discussions');
    expect(out).toMatch(/validated pain points\.$/);
  });
});

describe('categoryLede()', () => {
  it('embeds category.description when present', () => {
    const payload = makePayload({
      children: [makeChild('A', 1), makeChild('B', 1)],
    });
    expect(categoryLede(payload)).toBe(
      '27 startup ideas and 99 validated pain points across 2 sub-niches in UI/UX design, prototyping, and creative production software — sourced from 120 real community discussions.',
    );
  });

  it('falls back to category.name when description is null', () => {
    const payload = makePayload({
      category: { description: null } as Partial<
        CategoryLandingPayload['category']
      > as CategoryLandingPayload['category'],
      children: [makeChild('A', 1)],
    });
    expect(categoryLede(payload)).toContain('in Design & Creative Tools — sourced from');
  });

  it('pluralizes discussions singular at 1 and uses comma separators at large counts', () => {
    const singular = categoryLede(
      makePayload({ contentItemsMined: 1, children: [makeChild('A', 1)] }),
    );
    expect(singular).toContain('1 real community discussion.');

    const big = categoryLede(
      makePayload({ contentItemsMined: 12345, children: [makeChild('A', 1)] }),
    );
    expect(big).toContain('12,345 real community discussions.');
  });

  it('drops the trailing "— sourced from" clause when contentItemsMined is 0', () => {
    const out = categoryLede(
      makePayload({ contentItemsMined: 0, children: [makeChild('A', 1)] }),
    );
    expect(out).not.toContain('sourced from');
    expect(out).not.toContain('discussions');
    expect(out).not.toContain(' — ');
    // Ends with "…in {niche}." with a clean period.
    expect(out).toMatch(/in [^.]+\.$/);
  });
});

describe('buildCategoryJsonLd() — CollectionPage fields', () => {
  function getCollectionPage(blocks: ReturnType<typeof buildCategoryJsonLd>) {
    return blocks.find(
      (b): b is Record<string, unknown> & { '@type': 'CollectionPage' } =>
        (b as Record<string, unknown>)['@type'] === 'CollectionPage',
    ) as Record<string, unknown>;
  }

  it('emits name with the "— Startup Ideas & Pain Points" suffix', () => {
    const cp = getCollectionPage(
      buildCategoryJsonLd(makePayload(), 'https://nicheiq.dev/ideas/design-creative-tools', 'desc'),
    );
    expect(cp.name).toBe('Design & Creative Tools — Startup Ideas & Pain Points');
  });

  it('emits datePublished from category.createdAt truncated to YYYY-MM-DD', () => {
    const cp = getCollectionPage(
      buildCategoryJsonLd(makePayload(), 'https://nicheiq.dev/ideas/design-creative-tools', 'desc'),
    );
    // Default fixture createdAt: '2026-01-01T00:00:00.000Z'
    expect(cp.datePublished).toBe('2026-01-01');
  });

  it('emits dateModified from latestModifiedAt truncated to YYYY-MM-DD, and lastReviewed === dateModified', () => {
    const cp = getCollectionPage(
      buildCategoryJsonLd(makePayload(), 'https://nicheiq.dev/ideas/design-creative-tools', 'desc'),
    );
    expect(cp.dateModified).toBe('2026-05-14');
    expect(cp.lastReviewed).toBe(cp.dateModified);
  });

  it('emits the canonical comma-separated keywords string', () => {
    const cp = getCollectionPage(
      buildCategoryJsonLd(makePayload(), 'https://nicheiq.dev/ideas/design-creative-tools', 'desc'),
    );
    expect(cp.keywords).toBe(
      'Design & Creative Tools, startup ideas, pain points, saas niche, validated startup ideas',
    );
  });

  it('emits isPartOf with @type CollectionPage when payload.parent is set (sub-niche route)', () => {
    const payload = makePayload({
      parent: { id: 'p1', name: 'Design & Creative Tools', slug: 'design-creative-tools' },
      category: {
        name: '3D Design & Modeling',
        slug: '3d-design-modeling',
      } as Partial<CategoryLandingPayload['category']> as CategoryLandingPayload['category'],
    });
    const cp = getCollectionPage(
      buildCategoryJsonLd(
        payload,
        'https://nicheiq.dev/ideas/design-creative-tools/3d-design-modeling',
        'desc',
      ),
    );
    expect(cp.isPartOf).toEqual({
      '@type': 'CollectionPage',
      name: 'Design & Creative Tools — Startup Ideas & Pain Points',
      url: 'https://nicheiq.dev/ideas/design-creative-tools',
    });
    // sub-niche schema name also gets the suffix (with the sub-niche's own name)
    expect(cp.name).toBe('3D Design & Modeling — Startup Ideas & Pain Points');
  });

  it('omits isPartOf when payload.parent is null (parent route)', () => {
    const cp = getCollectionPage(
      buildCategoryJsonLd(makePayload(), 'https://nicheiq.dev/ideas/design-creative-tools', 'desc'),
    );
    expect(cp.isPartOf).toBeUndefined();
  });
});
