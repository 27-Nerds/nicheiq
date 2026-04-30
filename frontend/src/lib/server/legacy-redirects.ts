/**
 * Legacy `/catalog/*` URL → new path resolver.
 *
 * Used by `hooks.server.ts` to 301-redirect every legacy URL Google has
 * indexed to its new `/ideas/*`, `/idea/*`, or `/pain-point/*` equivalent.
 * Falls through to the `/ideas` hub on any failure (never 404 a legacy URL).
 *
 * Two-tier cache:
 *  - Frontend in-memory LRU (this file) — 5,000 entries, 10-minute TTL.
 *  - Backend Redis (in `catalogService.resolveLegacy*`) — 24h positive,
 *    1h negative.
 */

import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';
const HUB = '/ideas';
const LOOKUP_TIMEOUT_MS = 500;

// =====================================================================
// Bounded TTL cache (small Map-based LRU; avoids a new npm dep)
// =====================================================================

interface CacheEntry {
  value: string; // resolved target path
  expires: number;
}

const CACHE_MAX = 5000;
const CACHE_TTL_MS = 10 * 60 * 1000;

const cache = new Map<string, CacheEntry>();

function cacheGet(key: string): string | undefined {
  const hit = cache.get(key);
  if (!hit) return undefined;
  if (Date.now() > hit.expires) {
    cache.delete(key);
    return undefined;
  }
  // Refresh recency: re-insert to move to back of Map iteration order.
  cache.delete(key);
  cache.set(key, hit);
  return hit.value;
}

function cacheSet(key: string, value: string): void {
  if (cache.size >= CACHE_MAX) {
    // Evict the oldest entry (first key in Map iteration order).
    const firstKey = cache.keys().next().value;
    if (firstKey !== undefined) cache.delete(firstKey);
  }
  cache.set(key, { value, expires: Date.now() + CACHE_TTL_MS });
}

// =====================================================================
// Path normalization
// =====================================================================

function normalizePath(rawPath: string): string {
  let p: string;
  try {
    p = decodeURIComponent(rawPath);
  } catch {
    p = rawPath;
  }
  p = p.toLowerCase();
  p = p.replace(/\/+/g, '/');
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  return p || '/';
}

// =====================================================================
// Backend lookup
// =====================================================================

const SLUG_RE = /^[a-z0-9-]+$/;

async function backendLookup(
  kind: 'category' | 'idea' | 'pain-point',
  key: string,
): Promise<string | null> {
  if (!SLUG_RE.test(key)) return null;
  const cacheKey = `${kind}:${key}`;
  const cached = cacheGet(cacheKey);
  if (cached !== undefined) return cached === '' ? null : cached;

  try {
    const url = `${BACKEND_URL}/api/public/catalog/legacy-redirect?kind=${kind}&key=${encodeURIComponent(key)}`;
    const res = await fetch(url, {
      headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' },
      signal: AbortSignal.timeout(LOOKUP_TIMEOUT_MS),
    });
    if (!res.ok) {
      console.warn(`[legacy-redirect] backend returned ${res.status} for ${kind}/${key}`);
      return null;
    }
    const body = (await res.json()) as { target: string | null };
    const target = body.target ?? null;
    cacheSet(cacheKey, target ?? '');
    return target;
  } catch (err) {
    console.warn(`[legacy-redirect] lookup failed for ${kind}/${key}:`, err);
    return null;
  }
}

// =====================================================================
// Path resolver — implements the legacy-URL rule table
// =====================================================================

const RE_CATEGORIES = /^\/catalog\/categories\/([a-z0-9-]+)$/;
const RE_IDEA = /^\/catalog\/ideas\/([a-z0-9-]+)$/;
const RE_PAIN_POINT = /^\/catalog\/pain-points\/([a-z0-9-]+)$/;

export function isLegacyCatalogPath(pathname: string): boolean {
  return pathname === '/catalog' || pathname.startsWith('/catalog/');
}

/**
 * Resolve a legacy `/catalog/*` URL to the new path. Returns `null` to signal
 * "fall through to /ideas hub" — never throws, never 404s.
 */
export async function resolveLegacyPath(
  rawPath: string,
  query: URLSearchParams,
): Promise<string | null> {
  const path = normalizePath(rawPath);

  // Static paths
  if (path === '/catalog' || path === '/catalog/browse') return HUB;

  // Listing-style URLs with ?category= override go to the category landing.
  if (path === '/catalog/ideas' || path === '/catalog/pain-points') {
    const category = query.get('category');
    if (category && SLUG_RE.test(category)) {
      const target = await backendLookup('category', category);
      return target ?? HUB;
    }
    return HUB;
  }

  // /catalog/categories/[old-slug]
  const catMatch = RE_CATEGORIES.exec(path);
  if (catMatch) {
    const target = await backendLookup('category', catMatch[1]);
    return target ?? HUB;
  }

  // /catalog/ideas/[uuid-or-slug]
  const ideaMatch = RE_IDEA.exec(path);
  if (ideaMatch) {
    const target = await backendLookup('idea', ideaMatch[1]);
    return target ?? HUB;
  }

  // /catalog/pain-points/[uuid-or-slug]
  const ppMatch = RE_PAIN_POINT.exec(path);
  if (ppMatch) {
    const target = await backendLookup('pain-point', ppMatch[1]);
    return target ?? HUB;
  }

  // Anything else under /catalog/* — catch-all fallback.
  return HUB;
}

// =====================================================================
// Test helpers (only imported by Vitest; not by production code)
// =====================================================================

export function __resetLegacyRedirectCache(): void {
  cache.clear();
}
