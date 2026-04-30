import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { canonicalUrl } from '$lib/seo/canonical';
import { buildMeta } from '$lib/seo/meta';
import { organization, website, breadcrumbList, itemList } from '$lib/seo/jsonld';
import { siteOrigin } from '$lib/seo/canonical';
import { programmaticIdeaPages } from '$lib/data/programmaticIdeaPages';

const LAUNCH_GATE_ON = (env.SEO_LAUNCH_GATE ?? 'true') !== 'false';

export const load: PageServerLoad = async ({ url, setHeaders, parent }) => {
  setHeaders({
    'Cache-Control': 'public, max-age=60, s-maxage=300, stale-while-revalidate=86400',
  });

  const { categoriesTree } = await parent();
  const origin = siteOrigin();
  const canonical = canonicalUrl('/ideas', url.searchParams);

  const meta = buildMeta({
    title: 'Startup Ideas & Pain Points | NicheIQ',
    description:
      'Browse hand-curated startup ideas and pain points sourced from Reddit and Hacker News, scored for market fit and feasibility. Updated weekly.',
    canonical,
    type: 'website',
    noindex: LAUNCH_GATE_ON,
  });

  // Phase 5.1: ItemList schema signals to crawlers that this hub aggregates
  // 50+ niche entry points. Each top-level CatalogCategory becomes a ListItem.
  const niches = (categoriesTree as Array<{ name: string; slug: string }>).map(
    (n) => ({
      name: n.name,
      url: `${origin}/ideas/${n.slug}`,
    }),
  );

  const jsonld = [
    organization(),
    website(),
    breadcrumbList([
      { name: 'Home', url: `${origin}/` },
      { name: 'Ideas', url: `${origin}/ideas` },
    ]),
    itemList(niches),
  ];

  return {
    meta,
    jsonld,
    categoriesTree,
    programmaticPages: programmaticIdeaPages.map((p) => ({
      slug: p.slug,
      title: p.title,
      seoDescription: p.seoDescription,
      tags: p.tags,
    })),
  };
};
