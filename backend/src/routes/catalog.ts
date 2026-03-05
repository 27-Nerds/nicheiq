import { Router, Response } from 'express';
import { z } from 'zod';
import { AuthenticatedRequest } from '../middleware/auth.js';
import {
  listCategories,
  listPublishedIdeas,
  listPublishedPainPoints,
  getPublishedIdea,
  getPublishedPainPoint,
  getCatalogStats,
  searchCatalog,
} from '../services/catalogService.js';

export const catalogRouter = Router();

// ============================================
// Zod Schemas (sort validated to prevent orderBy injection)
// ============================================

const ListCatalogIdeasSchema = z.object({
  category: z.string().max(120).regex(/^[a-z0-9-]*$/).optional(),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(50).default(20),
  sort: z.enum(['newest', 'highest_market_fit', 'highest_novelty']).default('newest'),
});

const ListCatalogPainPointsSchema = z.object({
  category: z.string().max(120).regex(/^[a-z0-9-]*$/).optional(),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(50).default(20),
  sort: z.enum(['newest', 'highest_severity', 'highest_wtp', 'most_mentions']).default('newest'),
});

// ============================================
// Routes
// ============================================

catalogRouter.get('/categories', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const categories = await listCategories(true);
    res.json({ categories });
  } catch (error) {
    console.error('Failed to list categories:', error);
    res.status(500).json({ error: 'Failed to list categories' });
  }
});

catalogRouter.get('/ideas', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = ListCatalogIdeasSchema.safeParse(req.query);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const result = await listPublishedIdeas({
      categorySlug: parsed.data.category,
      page: parsed.data.page,
      limit: parsed.data.limit,
      sortBy: parsed.data.sort,
    });
    res.json(result);
  } catch (error) {
    console.error('Failed to list ideas:', error);
    res.status(500).json({ error: 'Failed to list ideas' });
  }
});

catalogRouter.get('/ideas/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const idea = await getPublishedIdea(req.params.id);
    if (!idea) {
      res.status(404).json({ error: 'Not found' });
      return;
    }
    res.json(idea);
  } catch (error) {
    console.error('Failed to get idea:', error);
    res.status(500).json({ error: 'Failed to get idea' });
  }
});

catalogRouter.get('/pain-points', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = ListCatalogPainPointsSchema.safeParse(req.query);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const result = await listPublishedPainPoints({
      categorySlug: parsed.data.category,
      page: parsed.data.page,
      limit: parsed.data.limit,
      sortBy: parsed.data.sort,
    });
    res.json(result);
  } catch (error) {
    console.error('Failed to list pain points:', error);
    res.status(500).json({ error: 'Failed to list pain points' });
  }
});

catalogRouter.get('/pain-points/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const pp = await getPublishedPainPoint(req.params.id);
    if (!pp) {
      res.status(404).json({ error: 'Not found' });
      return;
    }
    res.json(pp);
  } catch (error) {
    console.error('Failed to get pain point:', error);
    res.status(500).json({ error: 'Failed to get pain point' });
  }
});

const SearchSchema = z.object({
  q: z.string().min(2).max(100),
  limit: z.coerce.number().int().min(1).max(10).default(5),
});

catalogRouter.get('/search', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = SearchSchema.safeParse(req.query);
    if (!parsed.success) {
      res.status(400).json({ error: 'Validation error', details: parsed.error.errors });
      return;
    }
    const results = await searchCatalog(parsed.data.q, parsed.data.limit);
    res.json(results);
  } catch (error) {
    console.error('Failed to search catalog:', error);
    res.status(500).json({ error: 'Failed to search catalog' });
  }
});

catalogRouter.get('/stats', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const stats = await getCatalogStats();
    res.json(stats);
  } catch (error) {
    console.error('Failed to get catalog stats:', error);
    res.status(500).json({ error: 'Failed to get stats' });
  }
});
