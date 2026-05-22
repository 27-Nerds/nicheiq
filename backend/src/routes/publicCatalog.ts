import { Router, Request, Response } from 'express';
import { z } from 'zod';
import {
  getCategoryLanding,
  getCatalogTotals,
  getIdeaBySlug,
  getPainPointBySlug,
  getCategorySitemapEntries,
  getIdeaSitemapEntries,
  getPainPointSitemapEntries,
  getPublicCategoryTree,
  getTopCatalogPainPoints,
  getDiscoverPainPoints,
  resolveLegacyCategory,
  resolveLegacyIdea,
  resolveLegacyPainPoint,
  isEntitledUser,
} from '../services/catalogService.js';
import {
  listCollectionSummaries,
  getCollectionDetail,
} from '../services/catalogCollectionService.js';
import { catalogCrawlLimiter } from '../middleware/rateLimit.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';

/** Full-catalog entitlement — authoritative DB lookup (ADMIN role or fullCatalogAccess). */
async function isEntitled(user: AuthenticatedRequest['user']): Promise<boolean> {
  return isEntitledUser(user?.id);
}

/**
 * Public-rendering catalog router.
 *
 * Mounted at `/api/public/catalog/*` under `requireInternalService` (service
 * secret only — no `X-User-ID` required). Used by SvelteKit `(public)` SSR
 * loaders that have no session cookie.
 *
 * EXCEPTION: `/idea-by-slug/:slug` and `/pain-point-by-slug/:slug` additionally
 * apply `requireInternalAuth` per-route, so they require a logged-in user
 * (`X-User-ID`). Their detail pages are login-gated; do NOT remove that
 * per-route middleware to "match" the rest of the router — the gate is intended.
 *
 * Counterpart to `catalog.ts` which is mounted under `requireInternalAuth`
 * for in-app callers that already carry a session.
 */
export const publicCatalogRouter = Router();

const SlugParam = z.string().min(1).max(160).regex(/^[a-z0-9-]+$/);

publicCatalogRouter.get(
  '/landing/:parentSlug',
  catalogCrawlLimiter,
  async (req: Request, res: Response) => {
    try {
      const slugParse = SlugParam.safeParse(req.params.parentSlug);
      if (!slugParse.success) {
        res.status(400).json({ error: 'Invalid slug' });
        return;
      }
      const result = await getCategoryLanding({ parentSlug: slugParse.data });
      if (!result) {
        res.status(404).json({ error: 'Not found' });
        return;
      }
      if ('inactive' in result) {
        res.status(410).json({ error: 'Gone' });
        return;
      }
      res.json(result);
    } catch (error) {
      console.error('Failed to get landing:', error);
      res.status(500).json({ error: 'Failed to get landing' });
    }
  },
);

publicCatalogRouter.get(
  '/landing/:parentSlug/:childSlug',
  catalogCrawlLimiter,
  async (req: Request, res: Response) => {
    try {
      const parentParse = SlugParam.safeParse(req.params.parentSlug);
      const childParse = SlugParam.safeParse(req.params.childSlug);
      if (!parentParse.success || !childParse.success) {
        res.status(400).json({ error: 'Invalid slug' });
        return;
      }
      const result = await getCategoryLanding({
        parentSlug: parentParse.data,
        childSlug: childParse.data,
      });
      if (!result) {
        res.status(404).json({ error: 'Not found' });
        return;
      }
      if ('inactive' in result) {
        res.status(410).json({ error: 'Gone' });
        return;
      }
      res.json(result);
    } catch (error) {
      console.error('Failed to get nested landing:', error);
      res.status(500).json({ error: 'Failed to get landing' });
    }
  },
);

publicCatalogRouter.get(
  '/idea-by-slug/:slug',
  catalogCrawlLimiter,
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const slugParse = SlugParam.safeParse(req.params.slug);
      if (!slugParse.success) {
        res.status(400).json({ error: 'Invalid slug' });
        return;
      }
      const entitled = await isEntitled(req.user);
      const idea = await getIdeaBySlug(slugParse.data, { entitled });
      if (!idea) {
        res.status(404).json({ error: 'Not found' });
        return;
      }
      // Non-featured detail for a non-entitled user → locked (no item data in body).
      if ('locked' in idea) {
        res.status(403).json({ error: 'locked' });
        return;
      }
      res.json(idea);
    } catch (error) {
      console.error('Failed to get idea by slug:', error);
      res.status(500).json({ error: 'Failed to get idea' });
    }
  },
);

publicCatalogRouter.get(
  '/pain-point-by-slug/:slug',
  catalogCrawlLimiter,
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const slugParse = SlugParam.safeParse(req.params.slug);
      if (!slugParse.success) {
        res.status(400).json({ error: 'Invalid slug' });
        return;
      }
      const entitled = await isEntitled(req.user);
      const pp = await getPainPointBySlug(slugParse.data, { entitled });
      if (!pp) {
        res.status(404).json({ error: 'Not found' });
        return;
      }
      if ('locked' in pp) {
        res.status(403).json({ error: 'locked' });
        return;
      }
      res.json(pp);
    } catch (error) {
      console.error('Failed to get pain point by slug:', error);
      res.status(500).json({ error: 'Failed to get pain point' });
    }
  },
);

publicCatalogRouter.get(
  '/sitemap',
  catalogCrawlLimiter,
  async (_req: Request, res: Response) => {
    try {
      const [categories, ideas, painPoints] = await Promise.all([
        getCategorySitemapEntries(),
        getIdeaSitemapEntries(),
        getPainPointSitemapEntries(),
      ]);
      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json({ categories, ideas, painPoints });
    } catch (error) {
      console.error('Failed to get catalog sitemap:', error);
      res.status(500).json({ error: 'Failed to get sitemap' });
    }
  },
);

publicCatalogRouter.get(
  '/tree',
  catalogCrawlLimiter,
  async (_req: Request, res: Response) => {
    try {
      const tree = await getPublicCategoryTree();
      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json({ categories: tree });
    } catch (error) {
      console.error('Failed to get catalog tree:', error);
      res.status(500).json({ error: 'Failed to get tree' });
    }
  },
);

// Phase 5.4 — public catalog index aggregate stats. Cached 5 min server-side
// AND via Cache-Control to amortize the COUNT() + SUM() Prisma queries.
publicCatalogRouter.get(
  '/totals',
  catalogCrawlLimiter,
  async (_req: Request, res: Response) => {
    try {
      const totals = await getCatalogTotals();
      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json(totals);
    } catch (error) {
      console.error('Failed to get catalog totals:', error);
      res.status(500).json({ error: 'Failed to get totals' });
    }
  },
);

// Phase 6 — cross-catalog top pain points for the /ideas SEO landing surface.
// Returns at most `limit` (default 10, clamped 1-25) of the highest-severity
// active pain points across every niche, with category + parent for linking
// back to /ideas/[parentSlug]/[childSlug].
publicCatalogRouter.get(
  '/top-pain-points',
  catalogCrawlLimiter,
  async (req: Request, res: Response) => {
    try {
      const raw = Number.parseInt(String(req.query.limit ?? '10'), 10);
      const limit = Number.isFinite(raw) ? raw : 10;
      const painPoints = await getTopCatalogPainPoints(limit);
      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json(painPoints);
    } catch (error) {
      console.error('Failed to get top catalog pain points:', error);
      res.status(500).json({ error: 'Failed to get top pain points' });
    }
  },
);

// "Discover" teaser — a few random active pain points shown on /new as research
// inspiration. Public funnel surface (like /top-pain-points); intentionally NOT
// gated. Moved here from the now-deleted /api/catalog router so all catalog
// endpoints live under /api/public/catalog/*.
publicCatalogRouter.get(
  '/discover',
  catalogCrawlLimiter,
  async (_req: Request, res: Response) => {
    try {
      const items = await getDiscoverPainPoints(4);
      res.setHeader('Cache-Control', 'no-cache');
      res.json({ items });
    } catch (error) {
      console.error('Failed to get discover items:', error);
      res.status(500).json({ error: 'Failed to get discover items' });
    }
  },
);

// Phase 5.4 — featured collection summaries (for the public index page).
// Returns active collections only, sorted by sortOrder. Items NOT hydrated.
publicCatalogRouter.get(
  '/collections',
  catalogCrawlLimiter,
  async (_req: Request, res: Response) => {
    try {
      const summaries = await listCollectionSummaries();
      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json({ collections: summaries });
    } catch (error) {
      console.error('Failed to list catalog collections:', error);
      res.status(500).json({ error: 'Failed to list collections' });
    }
  },
);

// Phase 5.4 — single collection detail with items hydrated as previews.
publicCatalogRouter.get(
  '/collections/:slug',
  catalogCrawlLimiter,
  async (req: Request, res: Response) => {
    try {
      const slugParse = SlugParam.safeParse(req.params.slug);
      if (!slugParse.success) {
        res.status(400).json({ error: 'Invalid slug' });
        return;
      }
      const detail = await getCollectionDetail(slugParse.data);
      if (!detail) {
        res.status(404).json({ error: 'Not found' });
        return;
      }
      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json(detail);
    } catch (error) {
      console.error('Failed to get collection detail:', error);
      res.status(500).json({ error: 'Failed to get collection' });
    }
  },
);

// Legacy `/catalog/*` URL → new path resolver. Used by the SvelteKit
// `hooks.server.ts` 301-redirect layer. Returns `{target: null}` for unknown
// keys (the hook falls through to `/ideas` in that case — never 404 a
// crawled URL).
const LegacyKindParam = z.enum(['category', 'idea', 'pain-point']);
const LegacyKeyParam = z
  .string()
  .min(1)
  .max(160)
  .regex(/^[a-z0-9-]+$/);

publicCatalogRouter.get(
  '/legacy-redirect',
  catalogCrawlLimiter,
  async (req: Request, res: Response) => {
    try {
      const kindParse = LegacyKindParam.safeParse(req.query.kind);
      const keyParse = LegacyKeyParam.safeParse(req.query.key);
      if (!kindParse.success || !keyParse.success) {
        res.status(400).json({ error: 'Invalid kind or key' });
        return;
      }
      const { data: kind } = kindParse;
      const { data: key } = keyParse;

      let target: string | null;
      if (kind === 'category') {
        target = await resolveLegacyCategory(key);
      } else if (kind === 'idea') {
        target = await resolveLegacyIdea(key);
      } else {
        target = await resolveLegacyPainPoint(key);
      }

      res.setHeader('Cache-Control', 'public, max-age=300');
      res.json({ target });
    } catch (error) {
      console.error('Failed to resolve legacy redirect:', error);
      res.status(500).json({ error: 'Failed to resolve legacy redirect' });
    }
  },
);
