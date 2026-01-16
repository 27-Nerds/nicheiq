import { Router, Response } from 'express';
import { prisma } from '../services/db.js';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';
import { formatJobResponse } from '../utils/jobFormatter.js';

export const usersRouter = Router();

/**
 * GET /api/users/:userId/jobs
 * Get all jobs for a specific user (requires authentication and ownership)
 */
usersRouter.get('/:userId/jobs', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
      return;
    }

    // Verify user can only access their own jobs
    if (req.user!.id !== userId) {
      res.status(403).json({ error: 'Not authorized to view these jobs' });
      return;
    }

    // Get user's jobs
    const jobs = await prisma.job.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50, // Limit for performance
      include: {
        progress: true,
        assets: true,
      },
    });

    // Format response using shared helper
    const formattedJobs = jobs.map((job) => formatJobResponse(job, {
      includeCreatedAt: true,
      includeAssetFlags: true,
    }));

    res.json({ jobs: formattedJobs });
  } catch (error) {
    console.error('Failed to get user jobs:', error);
    res.status(500).json({ error: 'Failed to get user jobs' });
  }
});

/**
 * GET /api/users/:userId
 * Get user profile (requires authentication and ownership)
 */
usersRouter.get('/:userId', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
      return;
    }

    // Verify user can only access their own profile
    if (req.user!.id !== userId) {
      res.status(403).json({ error: 'Not authorized to view this profile' });
      return;
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        name: true,
        image: true,
        createdAt: true,
        _count: {
          select: { jobs: true },
        },
      },
    });

    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    res.json({
      id: user.id,
      email: user.email,
      name: user.name,
      image: user.image,
      createdAt: user.createdAt.toISOString(),
      jobCount: user._count.jobs,
    });
  } catch (error) {
    console.error('Failed to get user:', error);
    res.status(500).json({ error: 'Failed to get user profile' });
  }
});
