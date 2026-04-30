import { siteOrigin } from './canonical';

export type JsonLd = Record<string, unknown>;

export function organization(): JsonLd {
  const origin = siteOrigin();
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
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
    name: 'NicheIQ',
    url: origin,
  };
}

export function breadcrumbList(items: { name: string; url: string }[]): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

export function collectionPage(args: {
  name: string;
  description: string;
  url: string;
  about?: string;
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
  return result;
}

export function itemList(items: { name: string; url: string }[]): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      url: item.url,
      name: item.name,
    })),
  };
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
  author?: string;
}): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: args.headline,
    description: args.description,
    datePublished: args.datePublished,
    dateModified: args.dateModified,
    url: args.url,
    author: {
      '@type': 'Organization',
      name: args.author ?? 'NicheIQ Research Team',
    },
    publisher: {
      '@type': 'Organization',
      name: 'NicheIQ',
      logo: {
        '@type': 'ImageObject',
        url: `${siteOrigin()}/niche-logo-beta.svg`,
      },
    },
  };
}

/**
 * XSS-safe JSON-LD serialization: escapes `<` so a malicious string
 * containing `</script>` cannot break out of the script tag.
 */
export function serializeJsonLd(data: JsonLd): string {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}
