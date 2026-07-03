import type { RequestHandler } from './$types';
import { fetchBackend } from '$lib/backend';
import { programmaticIdeaPages } from '$lib/data/programmaticIdeaPages';
import { LAUNCH_GATE_ON } from '$lib/seo/launchGate';
import { BLOG_POSTS_SORTED } from '$lib/blog/registry';

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

let cachedXml: string | null = null;
let cacheTimestamp = 0;

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function formatDate(date: string): string {
  return new Date(date).toISOString().split('T')[0];
}

interface SitemapEntry {
  path: string;
  lastmod: string;
  changefreq?: string;
  priority?: string;
}

function entryXml(origin: string, entry: SitemapEntry): string {
  const parts = [
    '  <url>',
    `    <loc>${escapeXml(origin)}${entry.path}</loc>`,
    `    <lastmod>${entry.lastmod}</lastmod>`,
  ];
  if (entry.changefreq) parts.push(`    <changefreq>${entry.changefreq}</changefreq>`);
  if (entry.priority) parts.push(`    <priority>${entry.priority}</priority>`);
  parts.push('  </url>');
  return parts.join('\n') + '\n';
}

interface CategorySitemapEntry {
  slug: string;
  parentSlug: string | null;
  updatedAt: string;
  ideaCount: number;
  painPointCount: number;
}

interface IdeaSitemapEntry {
  slug: string;
  updatedAt: string;
}

export const GET: RequestHandler = async ({ url }) => {
  const now = Date.now();

  if (cachedXml && now - cacheTimestamp < CACHE_TTL_MS) {
    return new Response(cachedXml, {
      headers: {
        'Content-Type': 'application/xml',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  }

  const origin = url.origin;
  const today = new Date().toISOString().split('T')[0];

  // Static public pages. `/ideas` follows SEO_LAUNCH_GATE because its page
  // ships noindex while the public catalog rollout is gated.
  const staticEntries: SitemapEntry[] = [
    { path: '/', changefreq: 'weekly', priority: '1.0', lastmod: today },
    { path: '/privacy', changefreq: 'monthly', priority: '0.3', lastmod: today },
    { path: '/login', changefreq: 'monthly', priority: '0.4', lastmod: today },
    { path: '/register', changefreq: 'monthly', priority: '0.5', lastmod: today },
    { path: '/sample-report', changefreq: 'daily', priority: '0.7', lastmod: today },
    { path: '/blog', changefreq: 'weekly', priority: '0.7', lastmod: today },
  ];
  if (!LAUNCH_GATE_ON) {
    staticEntries.splice(1, 0, {
      path: '/ideas',
      changefreq: 'weekly',
      priority: '0.9',
      lastmod: today,
    });
  }

  let urls = '';
  for (const entry of staticEntries) {
    urls += entryXml(origin, entry);
  }

  // Blog posts — author-controlled, always indexable.
  for (const post of BLOG_POSTS_SORTED) {
    urls += entryXml(origin, {
      path: `/blog/${escapeXml(post.slug)}`,
      lastmod: formatDate(post.date),
      changefreq: 'monthly',
      priority: '0.6',
    });
  }

  // Existing share entries (unrelated to catalog migration; preserved as-is).
  try {
    const response = await fetchBackend('/api/sitemap/entries');
    if (response.ok) {
      const data = await response.json();
      for (const share of data.reportShares ?? []) {
        urls += entryXml(origin, {
          path: `/shared/${escapeXml(share.shareToken)}`,
          lastmod: formatDate(share.updatedAt),
        });
      }
      for (const share of data.discoveryShares ?? []) {
        urls += entryXml(origin, {
          path: `/shared/discovery/${escapeXml(share.shareToken)}`,
          lastmod: formatDate(share.updatedAt),
        });
      }
    } else {
      console.error(`Sitemap: backend returned ${response.status}`);
    }
  } catch (err) {
    console.error('Sitemap: failed to fetch share entries', err);
  }

  // Catalog URLs — only emit when the launch gate is OFF (post-Phase-4.5).
  // While the gate is on, every /ideas/* page ships with `noindex,follow`
  // and the sitemap omits them so Google doesn't index thin content.
  if (!LAUNCH_GATE_ON) {
    // Programmatic SEO pages
    for (const p of programmaticIdeaPages) {
      urls += entryXml(origin, {
        path: `/ideas/${escapeXml(p.slug)}`,
        lastmod: today,
        changefreq: 'weekly',
        priority: '0.8',
      });
    }

    // Categories + ideas + pain-points from backend
    try {
      const catalogRes = await fetchBackend('/api/public/catalog/sitemap');
      if (catalogRes.ok) {
        const data = (await catalogRes.json()) as {
          categories: CategorySitemapEntry[];
          ideas: IdeaSitemapEntry[];
          painPoints: IdeaSitemapEntry[];
        };

        for (const c of data.categories ?? []) {
          if (!c.slug || (c.parentSlug !== null && !c.parentSlug)) continue;
          const path = c.parentSlug
            ? `/ideas/${escapeXml(c.parentSlug)}/${escapeXml(c.slug)}`
            : `/ideas/${escapeXml(c.slug)}`;
          urls += entryXml(origin, {
            path,
            lastmod: formatDate(c.updatedAt),
            changefreq: 'weekly',
            priority: c.parentSlug ? '0.6' : '0.7',
          });
        }

        // Idea (`/idea/*`) and pain-point (`/pain-point/*`) detail pages are
        // login-gated (noindex + 302 to /login for anonymous), so they are
        // intentionally omitted from the sitemap. Only category/sub-category
        // landing pages are emitted as the indexable catalog surface.
      } else {
        console.error(`Sitemap: catalog backend returned ${catalogRes.status}`);
      }
    } catch (err) {
      console.error('Sitemap: failed to fetch catalog entries', err);
    }
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}</urlset>\n`;

  cachedXml = xml;
  cacheTimestamp = now;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
