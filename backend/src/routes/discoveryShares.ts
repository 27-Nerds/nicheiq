import { Router, Request, Response } from 'express';
import { z } from 'zod';
import crypto from 'crypto';
import { prisma } from '../services/db.js';
import { getJob } from '../services/jobService.js';
import { JobStatus } from '@prisma/client';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import rateLimit from 'express-rate-limit';
import { CONFIG } from '../config.js';

// Zod schemas
const JobIdParamSchema = z.object({
  jobId: z.string().uuid(),
});

const ShareTokenParamSchema = z.object({
  shareToken: z.string().regex(/^[A-Za-z0-9_-]{22}$/, 'Invalid share token format'),
});

const VoteBodySchema = z.object({
  solutionName: z.string().min(1).max(255),
  viewerToken: z.string().uuid(),
  comment: z.string().max(500).regex(/^[^<>&"'`]*$/).optional(),
});

const ViewerTokenQuerySchema = z.object({
  viewerToken: z.string().uuid().optional(),
});

// Rate limiters
const publicDiscoveryLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: CONFIG.nodeEnv === 'production' ? 30 : 1000,
  message: { error: 'Too many requests, please slow down' },
  standardHeaders: true,
  legacyHeaders: false,
});

const voteLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: CONFIG.nodeEnv === 'production' ? 10 : 1000,
  keyGenerator: (req: Request) => `${req.ip}:${req.params.shareToken}`,
  message: { error: 'Too many votes, please slow down' },
  standardHeaders: true,
  legacyHeaders: false,
  validate: { ip: false, keyGeneratorIpFallback: false },
});

const IP_HASH_SALT = CONFIG.ipHashSalt || 'nicheiq-vote-salt';
const MAX_TOKENS_PER_IP = 5;

function generateShareToken(): string {
  return crypto.randomBytes(16).toString('base64url'); // 22 chars
}

function hashIp(ip: string): string {
  return crypto.createHash('sha256').update(`${IP_HASH_SALT}:${ip}`).digest('hex');
}

// Helper: build vote summary for a share
async function buildVoteSummary(shareId: string) {
  const votes = await prisma.discoveryVote.groupBy({
    by: ['solutionName'],
    where: { shareId },
    _count: { id: true },
  });

  const solutionVotes: Record<string, number> = {};
  let totalVotes = 0;
  for (const v of votes) {
    solutionVotes[v.solutionName] = v._count.id;
    totalVotes += v._count.id;
  }

  return { totalVotes, solutionVotes };
}

// Helper: build discovery findings from job progress
async function buildDiscoveryFindings(jobId: string) {
  const stages = await prisma.jobProgress.findMany({
    where: { jobId, stageNumber: { lte: 4 } },
    orderBy: { stageNumber: 'asc' },
  });

  const findings: Record<string, any> = {};

  for (const stage of stages) {
    const details = stage.details as Record<string, any> | null;
    if (!details) continue;

    switch (stage.stageNumber) {
      case 1:
        findings.nicheContext = {
          niche_description: details.niche_description || details.nicheDescription || null,
          market_segments: details.market_segments || details.marketSegments || [],
        };
        break;
      case 2:
        findings.socialContent = {
          reddit_posts: details.reddit_posts ?? details.redditPosts ?? 0,
          subreddit_count: details.subreddit_count ?? details.subredditCount ?? 0,
        };
        break;
      case 3:
        findings.painPoints = {
          top: details.top_pain_points || details.topPainPoints || details.top || [],
        };
        break;
      case 4:
        findings.audience = {
          primary_target: details.primary_target || details.primaryTarget || null,
          segment_count: details.segment_count ?? details.segmentCount ?? 0,
          community_hubs: details.community_hubs || details.communityHubs || [],
        };
        break;
    }
  }

  return findings;
}


// ============================================
// Authenticated Routes (mounted at /api/jobs)
// ============================================
export const discoverySharesRouter = Router();

/**
 * GET /api/jobs/:jobId/discovery-share
 */
discoverySharesRouter.get('/:jobId/discovery-share', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
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

    const share = await prisma.discoveryShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    if (!share || !share.isActive) {
      res.json({ isShared: false });
      return;
    }

    const summary = await buildVoteSummary(share.id);

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
      voteCount: summary.totalVotes,
      solutionVotes: summary.solutionVotes,
    });
  } catch (error) {
    console.error('Failed to get discovery share status:', error);
    res.status(500).json({ error: 'Failed to get share status' });
  }
});

/**
 * POST /api/jobs/:jobId/discovery-share
 */
discoverySharesRouter.post('/:jobId/discovery-share', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
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

    if (job.status !== JobStatus.AWAITING_SELECTION && job.status !== JobStatus.REGENERATING) {
      res.status(400).json({ error: 'Discovery can only be shared when awaiting selection' });
      return;
    }

    // Upsert: reactivate or create
    const existing = await prisma.discoveryShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    let share;
    if (existing) {
      share = await prisma.discoveryShare.update({
        where: { jobId: parsed.data.jobId },
        data: { isActive: true },
      });
    } else {
      share = await prisma.discoveryShare.create({
        data: {
          jobId: parsed.data.jobId,
          userId: req.user!.id,
          shareToken: generateShareToken(),
          isActive: true,
        },
      });
    }

    const voteCount = await prisma.discoveryVote.count({ where: { shareId: share.id } });

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
      voteCount,
    });
  } catch (error) {
    console.error('Failed to enable discovery sharing:', error);
    res.status(500).json({ error: 'Failed to enable sharing' });
  }
});

/**
 * DELETE /api/jobs/:jobId/discovery-share
 */
discoverySharesRouter.delete('/:jobId/discovery-share', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
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

    const existing = await prisma.discoveryShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    if (existing) {
      await prisma.discoveryShare.update({
        where: { jobId: parsed.data.jobId },
        data: { isActive: false },
      });
    }

    res.json({ isShared: false });
  } catch (error) {
    console.error('Failed to disable discovery sharing:', error);
    res.status(500).json({ error: 'Failed to disable sharing' });
  }
});

/**
 * POST /api/jobs/:jobId/discovery-share/regenerate
 */
discoverySharesRouter.post('/:jobId/discovery-share/regenerate', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
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

    const existing = await prisma.discoveryShare.findUnique({
      where: { jobId: parsed.data.jobId },
    });

    if (!existing) {
      res.status(404).json({ error: 'Sharing not enabled for this job' });
      return;
    }

    // Delete all votes and regenerate token
    await prisma.discoveryVote.deleteMany({ where: { shareId: existing.id } });

    const share = await prisma.discoveryShare.update({
      where: { jobId: parsed.data.jobId },
      data: {
        shareToken: generateShareToken(),
        viewCount: 0,
        lastViewedAt: null,
        isActive: true,
      },
    });

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
      voteCount: 0,
    });
  } catch (error) {
    console.error('Failed to regenerate discovery share token:', error);
    res.status(500).json({ error: 'Failed to regenerate share link' });
  }
});


// ============================================
// Public Routes (mounted at /api/shared/discovery)
// ============================================
export const publicDiscoveryShareRouter = Router();

/**
 * GET /api/shared/discovery/:shareToken
 */
publicDiscoveryShareRouter.get('/:shareToken', publicDiscoveryLimiter, async (req: Request, res: Response) => {
  try {
    const parsed = ShareTokenParamSchema.safeParse(req.params);
    if (!parsed.success) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const share = await prisma.discoveryShare.findUnique({
      where: { shareToken: parsed.data.shareToken },
      include: {
        job: {
          select: {
            id: true,
            niche: true,
            solutionIdeas: true,
            status: true,
          },
        },
      },
    });

    // Identical 404 for all failure modes
    if (!share || !share.isActive) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const solutions = (share.job.solutionIdeas as any[]) || [];
    const discoveryFindings = await buildDiscoveryFindings(share.jobId);
    const voteSummary = await buildVoteSummary(share.id);

    // SEO headers (conditional based on admin indexing toggle)
    if (!share.allowIndexing) {
      res.setHeader('X-Robots-Tag', 'noindex, nofollow');
    }
    res.setHeader('Cache-Control', 'private, no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');

    res.json({
      shareType: 'discovery',
      niche: share.job.niche,
      solutions,
      discoveryFindings,
      voteSummary,
      allowIndexing: share.allowIndexing,
    });

    // Fire-and-forget view count increment
    prisma.discoveryShare.update({
      where: { id: share.id },
      data: {
        viewCount: { increment: 1 },
        lastViewedAt: new Date(),
      },
    }).catch((err) => {
      console.error('Failed to increment discovery view count:', err);
    });
  } catch (error) {
    console.error('Failed to serve shared discovery:', error);
    res.status(500).json({ error: 'Failed to load discovery' });
  }
});

/**
 * POST /api/shared/discovery/:shareToken/vote
 */
publicDiscoveryShareRouter.post('/:shareToken/vote', voteLimiter, async (req: Request, res: Response) => {
  try {
    const paramsParsed = ShareTokenParamSchema.safeParse(req.params);
    if (!paramsParsed.success) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const bodyParsed = VoteBodySchema.safeParse(req.body);
    if (!bodyParsed.success) {
      res.status(400).json({ error: 'Invalid vote data', details: bodyParsed.error.flatten() });
      return;
    }

    const { solutionName, viewerToken, comment } = bodyParsed.data;

    const share = await prisma.discoveryShare.findUnique({
      where: { shareToken: paramsParsed.data.shareToken },
      include: {
        job: {
          select: { solutionIdeas: true },
        },
      },
    });

    if (!share || !share.isActive) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    // Validate solution name against actual solutions
    const solutions = (share.job.solutionIdeas as any[]) || [];
    if (!solutions.some((s: any) => s.solution_name === solutionName || s.name === solutionName)) {
      res.status(400).json({ error: 'Invalid solution name' });
      return;
    }

    // IP-based Sybil prevention
    const ipHash = hashIp(req.ip || 'unknown');

    const existingVote = await prisma.discoveryVote.findUnique({
      where: { shareId_viewerToken: { shareId: share.id, viewerToken } },
    });

    if (!existingVote) {
      const existingTokensFromIp = await prisma.discoveryVote.count({
        where: { shareId: share.id, ipHash },
      });

      if (existingTokensFromIp >= MAX_TOKENS_PER_IP) {
        res.status(429).json({ error: 'Vote limit reached' });
        return;
      }
    }

    // Upsert vote
    await prisma.discoveryVote.upsert({
      where: { shareId_viewerToken: { shareId: share.id, viewerToken } },
      create: { shareId: share.id, solutionName, viewerToken, ipHash, comment: comment || null },
      update: { solutionName, comment: comment || null },
    });

    const voteSummary = await buildVoteSummary(share.id);

    res.json(voteSummary);
  } catch (error) {
    console.error('Failed to submit vote:', error);
    res.status(500).json({ error: 'Failed to submit vote' });
  }
});

/**
 * GET /api/shared/discovery/:shareToken/votes
 */
publicDiscoveryShareRouter.get('/:shareToken/votes', publicDiscoveryLimiter, async (req: Request, res: Response) => {
  try {
    const paramsParsed = ShareTokenParamSchema.safeParse(req.params);
    if (!paramsParsed.success) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const queryParsed = ViewerTokenQuerySchema.safeParse(req.query);
    const viewerToken = queryParsed.success ? queryParsed.data.viewerToken : undefined;

    const share = await prisma.discoveryShare.findUnique({
      where: { shareToken: paramsParsed.data.shareToken },
    });

    if (!share || !share.isActive) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const voteSummary = await buildVoteSummary(share.id);

    let viewerVote: { solutionName: string; comment: string | null } | null = null;
    if (viewerToken) {
      const vote = await prisma.discoveryVote.findUnique({
        where: { shareId_viewerToken: { shareId: share.id, viewerToken } },
      });
      if (vote) {
        viewerVote = { solutionName: vote.solutionName, comment: vote.comment };
      }
    }

    res.setHeader('X-Robots-Tag', 'noindex, nofollow');
    res.setHeader('Cache-Control', 'private, no-store');

    res.json({ ...voteSummary, viewerVote });
  } catch (error) {
    console.error('Failed to get vote summary:', error);
    res.status(500).json({ error: 'Failed to load votes' });
  }
});
