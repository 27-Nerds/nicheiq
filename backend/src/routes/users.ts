import { Router, Response } from 'express';
import { z } from 'zod';
import bcrypt from 'bcryptjs';
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
        creditTransactions: {
          where: { type: 'REFUND' },
          select: { id: true, amount: true },
        },
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
        passwordHash: true,
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
      hasPassword: !!user.passwordHash,
      createdAt: user.createdAt.toISOString(),
      jobCount: user._count.jobs,
    });
  } catch (error) {
    console.error('Failed to get user:', error);
    res.status(500).json({ error: 'Failed to get user profile' });
  }
});

/**
 * GET /api/users/:userId/notification-preferences
 * Get user's notification preferences (requires authentication and ownership)
 */
usersRouter.get('/:userId/notification-preferences', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
      return;
    }

    // Verify user can only access their own preferences
    if (req.user!.id !== userId) {
      res.status(403).json({ error: 'Not authorized to view these preferences' });
      return;
    }

    // Get or create notification preferences (upsert pattern)
    let preferences = await prisma.notificationPreferences.findUnique({
      where: { userId },
    });

    // If no preferences exist, return defaults (will be created on first update)
    if (!preferences) {
      res.json({
        emailEnabled: true,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: true,
        emailOnSolutionsReady: true,
      });
      return;
    }

    res.json({
      emailEnabled: preferences.emailEnabled,
      emailOnJobStart: preferences.emailOnJobStart,
      emailOnJobComplete: preferences.emailOnJobComplete,
      emailOnJobError: preferences.emailOnJobError,
      emailOnSolutionsReady: preferences.emailOnSolutionsReady,
    });
  } catch (error) {
    console.error('Failed to get notification preferences:', error);
    res.status(500).json({ error: 'Failed to get notification preferences' });
  }
});

/**
 * PUT /api/users/:userId/notification-preferences
 * Update user's notification preferences (requires authentication and ownership)
 */
usersRouter.put('/:userId/notification-preferences', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
      return;
    }

    // Verify user can only update their own preferences
    if (req.user!.id !== userId) {
      res.status(403).json({ error: 'Not authorized to update these preferences' });
      return;
    }

    // Validate request body
    const {
      emailEnabled,
      emailOnJobStart,
      emailOnJobComplete,
      emailOnJobError,
      emailOnSolutionsReady,
    } = req.body;

    // Build update data (only include provided fields)
    const updateData: Record<string, boolean> = {};
    if (typeof emailEnabled === 'boolean') updateData.emailEnabled = emailEnabled;
    if (typeof emailOnJobStart === 'boolean') updateData.emailOnJobStart = emailOnJobStart;
    if (typeof emailOnJobComplete === 'boolean') updateData.emailOnJobComplete = emailOnJobComplete;
    if (typeof emailOnJobError === 'boolean') updateData.emailOnJobError = emailOnJobError;
    if (typeof emailOnSolutionsReady === 'boolean') updateData.emailOnSolutionsReady = emailOnSolutionsReady;

    if (Object.keys(updateData).length === 0) {
      res.status(400).json({ error: 'No valid preference fields provided' });
      return;
    }

    // Upsert preferences
    const preferences = await prisma.notificationPreferences.upsert({
      where: { userId },
      update: updateData,
      create: {
        userId,
        ...updateData,
      },
    });

    res.json({
      emailEnabled: preferences.emailEnabled,
      emailOnJobStart: preferences.emailOnJobStart,
      emailOnJobComplete: preferences.emailOnJobComplete,
      emailOnJobError: preferences.emailOnJobError,
      emailOnSolutionsReady: preferences.emailOnSolutionsReady,
    });
  } catch (error) {
    console.error('Failed to update notification preferences:', error);
    res.status(500).json({ error: 'Failed to update notification preferences' });
  }
});

// Validation schema for password change
const ChangePasswordSchema = z.object({
  currentPassword: z.string().min(1, 'Current password is required'),
  newPassword: z.string().min(8, 'New password must be at least 8 characters'),
});

/**
 * POST /api/users/:userId/change-password
 * Change user's password (requires authentication and ownership)
 */
usersRouter.post('/:userId/change-password', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
      res.status(400).json({ error: 'Invalid user ID format' });
      return;
    }

    // Verify user can only change their own password
    if (req.user!.id !== userId) {
      res.status(403).json({ error: 'Not authorized to change this password' });
      return;
    }

    // Validate request body
    const input = ChangePasswordSchema.parse(req.body);

    // Get user with password hash
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { passwordHash: true },
    });

    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    // Check if user has a password (not OAuth-only)
    if (!user.passwordHash) {
      res.status(400).json({ error: 'Account uses OAuth login. Password cannot be changed.' });
      return;
    }

    // Verify current password
    const isCurrentValid = await bcrypt.compare(input.currentPassword, user.passwordHash);
    if (!isCurrentValid) {
      res.status(401).json({ error: 'Current password is incorrect' });
      return;
    }

    // Hash new password
    const newPasswordHash = await bcrypt.hash(input.newPassword, 12);

    // Update password
    await prisma.user.update({
      where: { id: userId },
      data: { passwordHash: newPasswordHash },
    });

    res.json({ message: 'Password changed successfully' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation error',
        details: error.errors,
      });
      return;
    }

    console.error('Failed to change password:', error);
    res.status(500).json({ error: 'Failed to change password' });
  }
});
