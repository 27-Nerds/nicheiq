import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';
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
  let urls = '';

  try {
    const response = await fetch(`${BACKEND_URL}/api/sitemap/entries`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      },
    });

    if (response.ok) {
      const data = await response.json();

      for (const share of data.reportShares ?? []) {
        urls += `  <url>\n    <loc>${escapeXml(origin)}/shared/${escapeXml(share.shareToken)}</loc>\n    <lastmod>${formatDate(share.updatedAt)}</lastmod>\n  </url>\n`;
      }

      for (const share of data.discoveryShares ?? []) {
        urls += `  <url>\n    <loc>${escapeXml(origin)}/shared/discovery/${escapeXml(share.shareToken)}</loc>\n    <lastmod>${formatDate(share.updatedAt)}</lastmod>\n  </url>\n`;
      }
    } else {
      console.error(`Sitemap: backend returned ${response.status}`);
    }
  } catch (err) {
    console.error('Sitemap: failed to fetch entries', err);
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
