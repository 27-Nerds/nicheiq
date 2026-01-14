import { Router, Request, Response } from 'express';
import { prisma } from '../services/db.js';

export const usersRouter = Router();

/**
 * GET /api/users/:userId/jobs
 * Get all jobs for a specific user
 */
usersRouter.get('/:userId/jobs', async (req: Request, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
      return;
    }

    // Check if user exists
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true },
    });

    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    // Get user's jobs
    const jobs = await prisma.job.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50, // Limit for performance
      include: {
        assets: {
          select: {
            assetType: true,
          },
        },
      },
    });

    // Format response
    const formattedJobs = jobs.map((job) => ({
      id: job.id,
      niche: job.niche,
      status: job.status,
      currentStage: job.currentStage,
      currentStageName: job.currentStageName,
      progressPercent: job.progressPercent,
      errorMessage: job.errorMessage,
      createdAt: job.createdAt.toISOString(),
      startedAt: job.startedAt?.toISOString() || null,
      completedAt: job.completedAt?.toISOString() || null,
      hasReport: job.assets.some((a) => a.assetType === 'REPORT_JSON'),
      hasLandingPage: job.assets.some((a) => a.assetType === 'LANDING_PAGE'),
    }));

    res.json({ jobs: formattedJobs });
  } catch (error) {
    console.error('Failed to get user jobs:', error);
    res.status(500).json({ error: 'Failed to get user jobs' });
  }
});

/**
 * GET /api/users/:userId
 * Get user profile
 */
usersRouter.get('/:userId', async (req: Request, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
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
