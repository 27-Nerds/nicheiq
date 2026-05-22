import { Router, Response } from 'express';
import { requireInternalService } from '../middleware/auth.js';
import * as statsService from '../services/statsService.js';

export const statsRouter = Router();

statsRouter.get('/public', requireInternalService, async (_req, res: Response) => {
  try {
    const stats = await statsService.getPublicStats();
    res.json(stats);
  } catch (error) {
    console.error('Public stats endpoint error:', error);
    res.status(500).json({ completedJobs: 47, activeFounders: null });
  }
});
