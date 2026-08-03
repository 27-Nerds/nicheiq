import { Router, Request, Response } from 'express';
import { z } from 'zod';
import crypto from 'crypto';
import { readFileSync } from 'fs';
import { existsSync } from 'fs';
import { prisma } from '../services/db.js';
import { getJob, getJobAsset } from '../services/jobService.js';
import { JobStatus, AssetType } from '@prisma/client';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import { resolveAssetPath } from '../utils/assetPath.js';
import { populateItemCache, removeItemCache } from '../services/catalogService.js';
import rateLimit from 'express-rate-limit';
import { CONFIG } from '../config.js';

// Zod schemas for validation
const JobIdParamSchema = z.object({
  jobId: z.string().uuid(),
});

const ShareTokenParamSchema = z.object({
  shareToken: z.string().regex(/^[A-Za-z0-9_-]{22}$/, 'Invalid share token format'),
});

// Execution internals to strip from public report responses. Research-quality
// grades and caveats are part of the report's evidence contract and must stay
// identical between the owner and shared views.
const STRIPPED_FIELDS = [
  'stage_timing_summary',
];

const PRIVATE_NOTE_REPLACEMENT = 'Owner selection note omitted from this shared report.';

/** Remove the owner's private selection note anywhere an older report may have copied it. */
function redactPrivateSelectionNote(value: unknown, note: string): unknown {
  if (typeof value === 'string') {
    if (value === note) return PRIVATE_NOTE_REPLACEMENT;
    // Avoid corrupting ordinary report prose when a legacy note was only a few characters.
    return note.length >= 16 && value.includes(note)
      ? value.split(note).join(PRIVATE_NOTE_REPLACEMENT)
      : value;
  }
  if (Array.isArray(value)) {
    return value.map(item => redactPrivateSelectionNote(item, note));
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        redactPrivateSelectionNote(item, note),
      ]),
    );
  }
  return value;
}

// Rate limiter for public share endpoint
const publicShareLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: CONFIG.nodeEnv === 'production' ? 30 : 1000,
  message: { error: 'Too many requests, please slow down' },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Generate a URL-safe share token
 */
function generateShareToken(): string {
  return crypto.randomBytes(16).toString('base64url'); // 22 chars
}

// ============================================
// Authenticated Routes (mounted at /api/jobs)
// ============================================
export const sharesRouter = Router();

/**
 * GET /api/jobs/:jobId/share
 * Get share status for a job
 */
sharesRouter.get('/:jobId/share', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = JobIdParamSchema.safeParse(req.params);
    if (!parsed.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    const job = await getJob(parsed.data.jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }

    const share = await prisma.reportShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    if (!share || !share.isActive) {
      res.json({ isShared: false });
      return;
    }

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
    });
  } catch (error) {
    console.error('Failed to get share status:', error);
    res.status(500).json({ error: 'Failed to get share status' });
  }
});

/**
 * POST /api/jobs/:jobId/share
 * Enable sharing for a job
 */
sharesRouter.post('/:jobId/share', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = JobIdParamSchema.safeParse(req.params);
    if (!parsed.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    const job = await getJob(parsed.data.jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }

    if (job.status !== JobStatus.COMPLETED) {
      res.status(400).json({ error: 'Only completed jobs can be shared' });
      return;
    }

    // Upsert: reactivate existing share or create new one
    const existing = await prisma.reportShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    let share;
    if (existing) {
      share = await prisma.reportShare.update({
        where: { jobId: parsed.data.jobId },
        data: { isActive: true },
      });
    } else {
      share = await prisma.reportShare.create({
        data: {
          jobId: parsed.data.jobId,
          userId: req.user!.id,
          shareToken: generateShareToken(),
          isActive: true,
        },
      });
    }

    // Populate catalog item cache (fire-and-forget)
    populateItemCache(parsed.data.jobId).catch(err => {
      console.error('Failed to populate item cache:', err);
    });

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
    });
  } catch (error) {
    console.error('Failed to enable sharing:', error);
    res.status(500).json({ error: 'Failed to enable sharing' });
  }
});

/**
 * DELETE /api/jobs/:jobId/share
 * Disable sharing for a job (keeps token for re-enable)
 */
sharesRouter.delete('/:jobId/share', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = JobIdParamSchema.safeParse(req.params);
    if (!parsed.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    const job = await getJob(parsed.data.jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }

    const existing = await prisma.reportShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    if (existing) {
      await prisma.reportShare.update({
        where: { jobId: parsed.data.jobId },
        data: { isActive: false },
      });

      // Remove catalog item cache (fire-and-forget)
      removeItemCache(parsed.data.jobId).catch(err => {
        console.error('Failed to remove item cache:', err);
      });
    }

    res.json({ isShared: false });
  } catch (error) {
    console.error('Failed to disable sharing:', error);
    res.status(500).json({ error: 'Failed to disable sharing' });
  }
});

/**
 * POST /api/jobs/:jobId/share/regenerate
 * Generate a new share token, resetting view count. Old links stop working.
 */
sharesRouter.post('/:jobId/share/regenerate', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = JobIdParamSchema.safeParse(req.params);
    if (!parsed.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    const job = await getJob(parsed.data.jobId);
    if (!job) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    if (!verifyOwnership(req, job.userId)) {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }

    const existing = await prisma.reportShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    if (!existing) {
      res.status(404).json({ error: 'Sharing not enabled for this job' });
      return;
    }

    const share = await prisma.reportShare.update({
      where: { jobId: parsed.data.jobId },
      data: {
        shareToken: generateShareToken(),
        viewCount: 0,
        lastViewedAt: null,
        isActive: true,
      },
    });

    // Repopulate catalog item cache (fire-and-forget)
    populateItemCache(parsed.data.jobId).catch(err => {
      console.error('Failed to repopulate item cache:', err);
    });

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
    });
  } catch (error) {
    console.error('Failed to regenerate share token:', error);
    res.status(500).json({ error: 'Failed to regenerate share link' });
  }
});

// ============================================
// Public Routes (mounted at /api/shared)
// ============================================
export const publicShareRouter = Router();

/**
 * GET /api/shared/:shareToken
 * Public access to a shared report (no auth required)
 */
publicShareRouter.get('/:shareToken', publicShareLimiter, async (req: Request, res: Response) => {
  try {
    const parsed = ShareTokenParamSchema.safeParse(req.params);
    if (!parsed.success) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const share = await prisma.reportShare.findUnique({
      where: { shareToken: parsed.data.shareToken },
      include: { job: true },
    });

    // All "not found" variants return identical 404 to prevent token enumeration
    if (!share || !share.isActive) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    if (share.job.status !== JobStatus.COMPLETED) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    // Get report file
    const asset = await getJobAsset(share.jobId, AssetType.REPORT_JSON);
    const resolvedPath = asset ? resolveAssetPath(asset.filePath) : '';
    if (!asset || !existsSync(resolvedPath)) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    // Read and sanitize report
    let rawReport = JSON.parse(readFileSync(resolvedPath, 'utf-8'));
    for (const field of STRIPPED_FIELDS) {
      delete rawReport[field];
    }
    const privateSelectionNote = share.job.selectionRationale?.trim();
    if (privateSelectionNote) {
      // The owner and Analyst retain Job.selectionRationale. Public shares use the
      // pipeline's pre-selection reasoning when it is safe, then redact exact legacy
      // copies elsewhere in reports generated before this privacy boundary existed.
      const originalReasoning = rawReport.original_selection_reasoning;
      rawReport.selection_rationale = (
        typeof originalReasoning === 'string'
        && !originalReasoning.includes(privateSelectionNote)
      )
        ? originalReasoning
        : 'The owner selected this shortlist after reviewing the Discovery evidence.';
      rawReport = redactPrivateSelectionNote(rawReport, privateSelectionNote);
    }

    // Set SEO headers (conditional based on admin indexing toggle)
    if (!share.allowIndexing) {
      res.setHeader('X-Robots-Tag', 'noindex, nofollow');
    }
    res.setHeader('Cache-Control', 'private, no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');

    rawReport._shareAllowIndexing = share.allowIndexing;
    res.json(rawReport);

    // Fire-and-forget view count increment
    prisma.reportShare.update({
      where: { id: share.id },
      data: {
        viewCount: { increment: 1 },
        lastViewedAt: new Date(),
      },
    }).catch((err) => {
      console.error('Failed to increment view count:', err);
    });
  } catch (error) {
    console.error('Failed to serve shared report:', error);
    res.status(500).json({ error: 'Failed to load report' });
  }
});
