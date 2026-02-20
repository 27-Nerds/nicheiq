import { Router, Response } from 'express';
import { requireInternalService } from '../middleware/auth.js';
import { prisma } from '../services/db.js';

export const sitemapRouter = Router();

sitemapRouter.get('/entries', requireInternalService, async (_req, res: Response) => {
  try {
    const [reportShares, discoveryShares] = await Promise.all([
      prisma.reportShare.findMany({
        where: { isActive: true, allowIndexing: true },
        select: { shareToken: true, updatedAt: true },
      }),
      prisma.discoveryShare.findMany({
        where: { isActive: true, allowIndexing: true },
        select: { shareToken: true, updatedAt: true },
      }),
    ]);

    res.json({ reportShares, discoveryShares });
  } catch (error) {
    console.error('Sitemap entries endpoint error:', error);
    res.status(500).json({ error: 'Failed to fetch sitemap entries' });
  }
});
