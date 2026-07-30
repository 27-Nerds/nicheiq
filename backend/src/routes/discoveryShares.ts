import { Router, Request, Response } from 'express';
import { z } from 'zod';
import crypto from 'crypto';
import { prisma } from '../services/db.js';
import { getJob } from '../services/jobService.js';
import { getDiscoveryDataForJob, getPreviewReportForJob } from '../services/assetService.js';
import { sanitizeDiscoveryData, sanitizePreviewReport } from './schemas/sharedDiscoveryPayload.js';
import { JobStatus, Prisma } from '@prisma/client';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import rateLimit from 'express-rate-limit';
import { CONFIG } from '../config.js';
import { ensureIdeaIdentities, ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';

// Zod schemas
const JobIdParamSchema = z.object({
  jobId: z.string().uuid(),
});

const ShareTokenParamSchema = z.object({
  shareToken: z.string().regex(/^[A-Za-z0-9_-]{22}$/, 'Invalid share token format'),
});

const VoteBodySchema = z.object({
  solutionId: z.string().min(1).max(255).optional(),
  solutionName: z.string().min(1).max(255).optional(),
  viewerToken: z.string().uuid(),
  comment: z.string().trim().max(500).optional(),
}).superRefine((value, ctx) => {
  if (!value.solutionId && !value.solutionName) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'solutionId or solutionName is required' });
  }
});

const ViewerTokenQuerySchema = z.object({
  viewerToken: z.string().uuid().optional(),
});

// Rate limiters
const publicDiscoveryLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: CONFIG.nodeEnv === 'production' ? 5 : 1000,
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

async function lockJobForShareMutation(
  tx: Prisma.TransactionClient,
  jobId: string,
): Promise<{ userId: string | null; status: JobStatus } | null> {
  const rows = await tx.$queryRaw<Array<{ userId: string | null; status: JobStatus }>>(Prisma.sql`
    SELECT "userId", "status"
    FROM "Job"
    WHERE "id" = ${jobId}
    FOR UPDATE
  `);
  return rows[0] ?? null;
}

// Helper: build vote summary for a share
async function buildVoteSummary(shareId: string, solutions: IdeaRecord[] = []) {
  const votes = await prisma.discoveryVote.groupBy({
    by: ['solutionId', 'solutionName'],
    where: { shareId },
    _count: { id: true },
  });

  const solutionVotes: Record<string, number> = {};
  const solutionVotesById: Record<string, number> = {};
  let totalVotes = 0;
  for (const v of votes) {
    solutionVotes[v.solutionName] = (solutionVotes[v.solutionName] ?? 0) + v._count.id;

    const storedSolution = v.solutionId
      ? solutions.find(solution => solution.idea_id === v.solutionId)
      : undefined;
    const legacyMatches = v.solutionId
      ? []
      : solutions.filter(solution => ideaName(solution) === v.solutionName);
    const solutionId = storedSolution?.idea_id
      ?? (legacyMatches.length === 1 ? legacyMatches[0].idea_id : undefined);
    if (solutionId) {
      solutionVotesById[solutionId] = (solutionVotesById[solutionId] ?? 0) + v._count.id;
    }
    totalVotes += v._count.id;
  }

  return { totalVotes, solutionVotes, solutionVotesById };
}

async function buildVoteRationales(shareId: string, solutions: IdeaRecord[] = []) {
  const votes = await prisma.discoveryVote.findMany({
    where: { shareId, comment: { not: null } },
    select: { solutionId: true, solutionName: true, comment: true },
    orderBy: { createdAt: 'desc' },
  });

  return votes.flatMap((vote) => {
    const comment = vote.comment?.trim();
    if (!comment) return [];

    const storedSolution = vote.solutionId
      ? solutions.find(solution => solution.idea_id === vote.solutionId)
      : undefined;
    const legacyMatches = vote.solutionId
      ? []
      : solutions.filter(solution => ideaName(solution) === vote.solutionName);
    const solutionId = storedSolution?.idea_id
      ?? vote.solutionId
      ?? (legacyMatches.length === 1 ? legacyMatches[0].idea_id : undefined);

    return [{ solutionId, solutionName: vote.solutionName, comment }];
  });
}

/**
 * @deprecated Legacy minimal-shape builder kept for one release so pre-deploy
 * visitor tabs don't crash. New clients use `previewReport` + `discoveryData`.
 * Remove in the next PR after dual-ship window closes.
 */
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

    const solutions = ensureIdeaIdentities(parsed.data.jobId, job.solutionIdeas);
    const [summary, voteRationales] = await Promise.all([
      buildVoteSummary(share.id, solutions),
      buildVoteRationales(share.id, solutions),
    ]);

    res.json({
      isShared: true,
      shareToken: share.shareToken,
      viewCount: share.viewCount,
      voteCount: summary.totalVotes,
      solutionVotes: summary.solutionVotes,
      solutionVotesById: summary.solutionVotesById,
      voteRationales,
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

    const result = await prisma.$transaction(async (tx) => {
      // Job first: Deep Research authorization takes this same lock before deactivating the
      // share, so enable cannot commit a stale reactivation after authorization.
      const job = await lockJobForShareMutation(tx, parsed.data.jobId);
      if (!job) return { outcome: 'not_found' as const };
      if (!verifyOwnership(req, job.userId)) return { outcome: 'forbidden' as const };
      if (job.status !== JobStatus.AWAITING_SELECTION && job.status !== JobStatus.REGENERATING) {
        return { outcome: 'invalid_status' as const };
      }

      const existing = await tx.discoveryShare.findUnique({
        where: { jobId: parsed.data.jobId },
      });
      const share = existing
        ? await tx.discoveryShare.update({
            where: { jobId: parsed.data.jobId },
            data: { isActive: true },
          })
        : await tx.discoveryShare.create({
            data: {
              jobId: parsed.data.jobId,
              userId: req.user!.id,
              shareToken: generateShareToken(),
              isActive: true,
            },
          });
      const voteCount = await tx.discoveryVote.count({ where: { shareId: share.id } });
      return { outcome: 'ok' as const, share, voteCount };
    });
    if (result.outcome === 'not_found') {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (result.outcome === 'forbidden') {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }
    if (result.outcome === 'invalid_status') {
      res.status(400).json({ error: 'Discovery can only be shared when awaiting selection' });
      return;
    }
    res.json({
      isShared: true,
      shareToken: result.share.shareToken,
      viewCount: result.share.viewCount,
      voteCount: result.voteCount,
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

    const result = await prisma.$transaction(async (tx) => {
      // Match Deep Research and share-enable lock order. The status check happens after the
      // lock, preventing token regeneration from resurrecting a link after authorization.
      const job = await lockJobForShareMutation(tx, parsed.data.jobId);
      if (!job) return { outcome: 'not_found' as const };
      if (!verifyOwnership(req, job.userId)) return { outcome: 'forbidden' as const };
      if (job.status !== JobStatus.AWAITING_SELECTION && job.status !== JobStatus.REGENERATING) {
        return { outcome: 'invalid_status' as const };
      }

      const existing = await tx.discoveryShare.findUnique({
        where: { jobId: parsed.data.jobId },
      });
      if (!existing) return { outcome: 'share_not_found' as const };

      // A regenerated token and its cleared vote history are one visible state transition.
      await tx.discoveryVote.deleteMany({ where: { shareId: existing.id } });
      const share = await tx.discoveryShare.update({
        where: { jobId: parsed.data.jobId },
        data: {
          shareToken: generateShareToken(),
          viewCount: 0,
          lastViewedAt: null,
          isActive: true,
        },
      });
      return { outcome: 'ok' as const, share };
    });
    if (result.outcome === 'not_found') {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (result.outcome === 'forbidden') {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }
    if (result.outcome === 'invalid_status') {
      res.status(400).json({ error: 'Discovery can only be shared when awaiting selection' });
      return;
    }
    if (result.outcome === 'share_not_found') {
      res.status(404).json({ error: 'Sharing not enabled for this job' });
      return;
    }
    res.json({
      isShared: true,
      shareToken: result.share.shareToken,
      viewCount: result.share.viewCount,
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

    const solutions = ensureIdeaIdentities(share.job.id, share.job.solutionIdeas);
    const [discoveryFindings, rawDiscoveryData, rawPreviewReport, voteSummary] = await Promise.all([
      buildDiscoveryFindings(share.jobId), // @deprecated — remove next release
      getDiscoveryDataForJob(share.jobId),
      getPreviewReportForJob(share.jobId),
      buildVoteSummary(share.id, solutions),
    ]);

    const discoveryData = sanitizeDiscoveryData(rawDiscoveryData);
    const previewReport = sanitizePreviewReport(rawPreviewReport);

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
      discoveryFindings, // @deprecated — remove next release; use discoveryData + previewReport
      discoveryData,
      previewReport,
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

    const { solutionId, solutionName, viewerToken, comment } = bodyParsed.data;

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

    const solutions = ensureIdeaIdentities(share.jobId, share.job.solutionIdeas);
    const selectedById = solutionId
      ? solutions.find(solution => solution.idea_id === solutionId)
      : undefined;
    const matchingNames = solutionName
      ? solutions.filter(solution => ideaName(solution) === solutionName)
      : [];

    if (solutionId && !selectedById) {
      res.status(400).json({ error: 'Invalid solution identity' });
      return;
    }
    if (selectedById && solutionName && ideaName(selectedById) !== solutionName) {
      res.status(400).json({ error: 'solutionId and solutionName refer to different ideas' });
      return;
    }
    if (!solutionId && matchingNames.length !== 1) {
      res.status(400).json({
        error: matchingNames.length > 1
          ? 'solutionName is ambiguous; solutionId is required'
          : 'Invalid solution identity',
      });
      return;
    }

    const selectedSolution = selectedById ?? matchingNames[0];
    const resolvedSolutionId = selectedSolution?.idea_id;
    const resolvedSolutionName = selectedSolution ? ideaName(selectedSolution) : undefined;
    if (!resolvedSolutionId || !resolvedSolutionName) {
      res.status(400).json({ error: 'Invalid solution identity' });
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
      create: {
        shareId: share.id,
        solutionId: resolvedSolutionId,
        solutionName: resolvedSolutionName,
        viewerToken,
        ipHash,
        comment: comment || null,
      },
      update: {
        solutionId: resolvedSolutionId,
        solutionName: resolvedSolutionName,
        ...(comment === undefined ? {} : { comment: comment || null }),
      },
    });

    const voteSummary = await buildVoteSummary(share.id, solutions);

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

    const solutions = ensureIdeaIdentities(share.jobId, share.job.solutionIdeas);
    const voteSummary = await buildVoteSummary(share.id, solutions);

    let viewerVote: {
      solutionId?: string;
      solutionName: string;
      comment: string | null;
    } | null = null;
    if (viewerToken) {
      const vote = await prisma.discoveryVote.findUnique({
        where: { shareId_viewerToken: { shareId: share.id, viewerToken } },
      });
      if (vote) {
        const storedSolution = vote.solutionId
          ? solutions.find(solution => solution.idea_id === vote.solutionId)
          : undefined;
        const legacyMatches = solutions.filter(solution => ideaName(solution) === vote.solutionName);
        const solutionId = storedSolution?.idea_id
          ?? (legacyMatches.length === 1 ? legacyMatches[0].idea_id : undefined);
        viewerVote = { solutionId, solutionName: vote.solutionName, comment: vote.comment };
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
