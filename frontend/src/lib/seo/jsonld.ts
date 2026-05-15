import { siteOrigin } from './canonical';

export type JsonLd = Record<string, unknown>;

/**
 * Stable @id URIs for the site's brand entities. These let other JSON-LD
 * blocks (Article publisher, etc.) reference the layout-defined Organization
 * and WebSite entities by URI instead of inlining duplicate data, which
 * strengthens the E-E-A-T entity chain that AI Overviews and Knowledge Graph
 * consumers trace.
 */
const ORG_ID = `${siteOrigin()}/#org`;
const SITE_ID = `${siteOrigin()}/#site`;
const RESEARCH_TEAM_ID = `${siteOrigin()}/#research-team`;

export function organization(): JsonLd {
  const origin = siteOrigin();
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': ORG_ID,
    name: 'NicheIQ',
    url: origin,
    logo: `${origin}/niche-logo-beta.svg`,
    sameAs: [],
  };
}

export function website(): JsonLd {
  const origin = siteOrigin();
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': SITE_ID,
    name: 'NicheIQ',
    url: origin,
    publisher: { '@id': ORG_ID },
  };
}

export function breadcrumbList(items: { name: string; url: string }[]): JsonLd {
  const lastIndex = items.length - 1;
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => {
      // Final breadcrumb (current page) MUST omit `item` per Google's spec —
      // linking the current page to itself is redundant and triggers warnings
      // in the Rich Results Test.
      const node: JsonLd = {
        '@type': 'ListItem',
        position: index + 1,
        name: item.name,
      };
      if (index < lastIndex) node.item = item.url;
      return node;
    }),
  };
}

export function collectionPage(args: {
  name: string;
  description: string;
  url: string;
  about?: string;
  /** ISO 8601 timestamp or `YYYY-MM-DD` date-only — both accepted by
   *  schema.org. Surfaces as `dateModified`, a concrete freshness signal
   *  Google uses alongside sitemap lastmod. */
  dateModified?: string | null;
  /** First publish date — ISO 8601 or `YYYY-MM-DD`. Pairs with
   *  `dateModified` so crawlers can compare freshness against age. */
  datePublished?: string | null;
  /** Human review timestamp — ISO 8601 or `YYYY-MM-DD`. Typically equal
   *  to `dateModified` when the page is auto-refreshed alongside content. */
  lastReviewed?: string | null;
  /** Comma-separated keyword string for legacy `keywords` markup. */
  keywords?: string | null;
  /** Parent CollectionPage this page is part of. Helper wraps the value
   *  with `@type: "CollectionPage"` automatically so callers only supply
   *  `{name, url}`. */
  isPartOf?: { name: string; url: string } | null;
  /** Optional `@id` reference to another entity (typically an ItemList) that
   *  this page is "about". Declares the page's primary subject for AI
   *  Overviews / Knowledge Graph consumers. */
  mainEntityId?: string | null;
}): JsonLd {
  const result: JsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: args.name,
    description: args.description,
    url: args.url,
  };
  if (args.about) {
    result.about = { '@type': 'Thing', name: args.about };
  }
  if (args.datePublished) {
    result.datePublished = args.datePublished;
  }
  if (args.dateModified) {
    result.dateModified = args.dateModified;
  }
  if (args.lastReviewed) {
    result.lastReviewed = args.lastReviewed;
  }
  if (args.keywords) {
    result.keywords = args.keywords;
  }
  if (args.isPartOf) {
    result.isPartOf = {
      '@type': 'CollectionPage',
      name: args.isPartOf.name,
      url: args.isPartOf.url,
    };
  }
  if (args.mainEntityId) {
    result.mainEntity = { '@id': args.mainEntityId };
  }
  return result;
}

export function itemList(
  items: { name: string; url: string; description?: string }[],
  opts: { numberOfItems?: number; name?: string; id?: string } = {},
): JsonLd {
  const result: JsonLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    itemListElement: items.map((item, index) => {
      const listItem: JsonLd = {
        '@type': 'ListItem',
        position: index + 1,
        url: item.url,
        name: item.name,
      };
      // Optional `description` flows into the ListItem — useful for pain-point
      // rows where the row title carries the actual semantic payload that
      // AI Overviews are likely to quote.
      if (item.description) {
        listItem.description = item.description;
      }
      return listItem;
    }),
  };
  // Stable `@id` lets a sibling entity (e.g. CollectionPage.mainEntity)
  // reference this list rather than inlining it.
  if (typeof opts.id === 'string' && opts.id.length > 0) {
    result['@id'] = opts.id;
  }
  // Optional `name` lets a page emit two distinct ItemLists ("Ideas in X",
  // "Pain points in X") so crawlers can tell semantically distinct
  // collections apart instead of seeing one flattened list.
  if (typeof opts.name === 'string' && opts.name.length > 0) {
    result.name = opts.name;
  }
  // numberOfItems advertises the total when itemListElement is paginated —
  // useful so crawlers know the visible list is a subset of a larger set.
  if (typeof opts.numberOfItems === 'number') {
    result.numberOfItems = opts.numberOfItems;
  }
  return result;
}

export function faqPage(qa: { q: string; a: string }[]): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: qa.map(({ q, a }) => ({
      '@type': 'Question',
      name: q,
      acceptedAnswer: {
        '@type': 'Answer',
        text: a,
      },
    })),
  };
}

export function article(args: {
  headline: string;
  description?: string;
  datePublished: string;
  dateModified: string;
  url: string;
  image?: string;
  author?: string;
}): JsonLd {
  const origin = siteOrigin();
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: args.headline,
    description: args.description,
    datePublished: args.datePublished,
    dateModified: args.dateModified,
    url: args.url,
    // `image` is required by Google for Article rich-result eligibility.
    // Fall back to the brand logo when no per-page image is supplied; this
    // satisfies the requirement without forcing per-idea image generation.
    image: args.image ?? `${origin}/niche-logo-beta.svg`,
    // Author is modeled as a sub-organization of the site's Organization
    // (parentOrganization → @id) so the E-E-A-T author chain
    // Article → author Person/Organization → parent Organization → sameAs
    // is traceable by AI Overviews and Knowledge Graph consumers.
    author: {
      '@type': 'Organization',
      '@id': RESEARCH_TEAM_ID,
      name: args.author ?? 'NicheIQ Research Team',
      parentOrganization: { '@id': ORG_ID },
    },
    publisher: { '@id': ORG_ID },
  };
}

/**
 * XSS-safe JSON-LD serialization. Escapes characters that could break out of
 * a `<script>` tag or cause issues with legacy JS parsers:
 *   - `<` `>` `&` (closing-tag attack vectors via `</script>`)
 *   - U+2028 / U+2029 (line/paragraph separators that broke pre-ES2019 parsers)
 *
 * The replacement strings are 6-character JSON Unicode escapes; JSON parsers
 * decode them back to the original characters at runtime, while the HTML
 * parser sees only safe text.
 */
export function serializeJsonLd(data: JsonLd): string {
  return JSON.stringify(data)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}
