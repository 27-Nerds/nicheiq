import { Router, Request, Response } from 'express';
import { z } from 'zod';
import crypto from 'crypto';
import { prisma } from '../services/db.js';
import { getJob } from '../services/jobService.js';
import { getDiscoveryDataForJob } from '../services/assetService.js';
import { getPreviewReportForJob } from '../services/selectionBoundary/rawPreviewReport.js';
import {
  applyPreviewFieldAllowlist,
  sanitizeDiscoveryData,
  sanitizePreviewReport,
} from './schemas/sharedDiscoveryPayload.js';
import { DispatchKind, JobStatus, Prisma } from '@prisma/client';
import { requireInternalAuth, verifyOwnership, AuthenticatedRequest } from '../middleware/auth.js';
import rateLimit from 'express-rate-limit';
import { CONFIG } from '../config.js';
import { ensureIdeaIdentities, ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';
import { ideaPortfolioFingerprint } from '../utils/ideaPortfolioFingerprint.js';
import { toNicheDisplay } from '../utils/jobFormatter.js';
import {
  DISCOVERY_SHARE_LIFECYCLE_JOB_SELECT,
  isDiscoveryShareLifecycleOpen,
  isDiscoveryShareLifecycleOpenForJob,
} from '../services/discoveryShareLifecycle.js';

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
): Promise<{
  userId: string | null;
  status: JobStatus;
  activeDispatchKind: DispatchKind | null;
} | null> {
  const rows = await tx.$queryRaw<Array<{
    userId: string | null;
    status: JobStatus;
    activeDispatchKind: DispatchKind | null;
  }>>(Prisma.sql`
    SELECT j."userId", j."status", d."kind" AS "activeDispatchKind"
    FROM "Job" AS j
    LEFT JOIN "JobDispatch" AS d ON d."id" = j."activeDispatchId"
    WHERE j."id" = ${jobId}
    FOR UPDATE OF j
  `);
  return rows[0] ?? null;
}

// Helper: build vote summary for a share
async function buildVoteSummary(
  shareId: string,
  solutions: IdeaRecord[] = [],
  db: Pick<Prisma.TransactionClient, 'discoveryVote'> = prisma,
) {
  const votes = await db.discoveryVote.groupBy({
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

async function buildVoteRationales(
  shareId: string,
  solutions: IdeaRecord[] = [],
  db: Pick<Prisma.TransactionClient, 'discoveryVote'> = prisma,
) {
  const votes = await db.discoveryVote.findMany({
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

/**
 * The `candidatePoolVersion` half of the owner-side boundary, expressed as a predicate the
 * share can AND into its own check.
 *
 * Returns true ONLY when the Job and its PREVIEW_REPORT asset both carry a version and the
 * two differ. A null on either side means the pair predates migration 20260809180000 (which
 * leaves Job.candidatePoolVersion NULL until the next solutionIdeas write); those shares keep
 * the fingerprint-only legacy path rather than failing closed the day the migration lands.
 */
async function candidatePoolVersionsDisagree(
  jobId: string,
  jobPoolVersion: number | null,
): Promise<boolean> {
  if (jobPoolVersion === null || jobPoolVersion === undefined) return false;
  const asset = await prisma.jobAsset.findUnique({
    where: { jobId_assetType: { jobId, assetType: 'PREVIEW_REPORT' } },
    select: { candidatePoolVersion: true },
  });
  const artifactPoolVersion = asset?.candidatePoolVersion ?? null;
  if (artifactPoolVersion === null) return false;
  return jobPoolVersion !== artifactPoolVersion;
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

    if (!share) {
      res.json({ isShared: false });
      return;
    }

    const solutions = ensureIdeaIdentities(parsed.data.jobId, job.solutionIdeas);
    const [summary, voteRationales] = await Promise.all([
      buildVoteSummary(share.id, solutions),
      buildVoteRationales(share.id, solutions),
    ]);

    const isShared = share.isActive && isDiscoveryShareLifecycleOpenForJob(job);
    res.json({
      isShared,
      ...(isShared ? { shareToken: share.shareToken } : {}),
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
      if (!isDiscoveryShareLifecycleOpen(job)) {
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
      res.status(400).json({ error: 'Discovery can only be shared while selection is open' });
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

    const result = await prisma.$transaction(async (tx) => {
      // Match every share lifecycle mutation and Deep Research authorization: once this
      // lock is held, no vote can enter behind a stale active-link read.
      const lockedJob = await lockJobForShareMutation(tx, parsed.data.jobId);
      if (!lockedJob) return { outcome: 'not_found' as const };
      if (!verifyOwnership(req, lockedJob.userId)) return { outcome: 'forbidden' as const };

      const [job, existing] = await Promise.all([
        tx.job.findUnique({
          where: { id: parsed.data.jobId },
          select: { solutionIdeas: true },
        }),
        tx.discoveryShare.findUnique({
          where: { jobId: parsed.data.jobId },
        }),
      ]);
      if (!job) return { outcome: 'not_found' as const };
      if (!existing) return { outcome: 'no_share' as const };

      await tx.discoveryShare.update({
        where: { jobId: parsed.data.jobId },
        data: { isActive: false },
      });

      const solutions = ensureIdeaIdentities(parsed.data.jobId, job.solutionIdeas);
      const [summary, voteRationales] = await Promise.all([
        buildVoteSummary(existing.id, solutions, tx),
        buildVoteRationales(existing.id, solutions, tx),
      ]);
      return { outcome: 'ok' as const, existing, summary, voteRationales };
    });

    if (result.outcome === 'not_found') {
      res.status(404).json({ error: 'Job not found' });
      return;
    }
    if (result.outcome === 'forbidden') {
      res.status(403).json({ error: 'Not authorized' });
      return;
    }
    if (result.outcome === 'no_share') {
      res.json({ isShared: false });
      return;
    }
    res.json({
      isShared: false,
      viewCount: result.existing.viewCount,
      voteCount: result.summary.totalVotes,
      solutionVotes: result.summary.solutionVotes,
      solutionVotesById: result.summary.solutionVotesById,
      voteRationales: result.voteRationales,
    });
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
      if (!isDiscoveryShareLifecycleOpen(job)) {
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
      res.status(400).json({ error: 'Discovery can only be shared while selection is open' });
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
            candidatePoolVersion: true,
            ...DISCOVERY_SHARE_LIFECYCLE_JOB_SELECT,
          },
        },
      },
    });

    // Identical 404 for all failure modes
    if (
      !share
      || !share.isActive
      || !isDiscoveryShareLifecycleOpenForJob(share.job)
    ) {
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
    // Finding D2 on a public URL. A visitor votes on `solutions` above, which is always
    // the LIVE pool; the preview asset is a snapshot of whatever pool the run last
    // produced. Pool-scoped preview fields therefore need the same boundary the owner
    // gets from loadCurrentSelectionContext: trust them only while the pool is settled
    // AND the stored portfolio fingerprint still names exactly the ideas being served.
    // Every other state fails closed, including a legacy report carrying no fingerprint
    // and a mid-regeneration pool that has already grown past its snapshot.
    const previewRecord = rawPreviewReport !== null
      && typeof rawPreviewReport === 'object'
      && !Array.isArray(rawPreviewReport)
      ? rawPreviewReport as Record<string, unknown>
      : null;
    const storedFingerprint = typeof previewRecord?.idea_portfolio_summary_fingerprint === 'string'
      ? previewRecord.idea_portfolio_summary_fingerprint
      : null;
    const fingerprintCurrent = share.job.status === JobStatus.AWAITING_SELECTION
      && storedFingerprint !== null
      && storedFingerprint === ideaPortfolioFingerprint(share.job.solutionIdeas);
    // Supplementary AND-condition, not a replacement: loadCurrentSelectionContext also binds
    // Job.candidatePoolVersion to the PREVIEW_REPORT asset's, catching a pool mutation whose
    // rewritten snapshot happens to fingerprint-match. Routing the share through that loader
    // instead would fail every pre-deploy share closed — migration 20260809180000 leaves
    // Job.candidatePoolVersion NULL until the next solutionIdeas write — so a null on either
    // side stays on the legacy path and only two present-and-different versions withhold.
    const poolArtifactsCurrent = fingerprintCurrent
      && !(await candidatePoolVersionsDisagree(share.jobId, share.job.candidatePoolVersion));
    const sanitizedPreviewReport = sanitizePreviewReport(rawPreviewReport);
    // The classification runs on BOTH branches. Pool staleness decides only the `pool` half;
    // a top-level key with no classification is a field this boundary has never reasoned
    // about, and a current pool says nothing about it, so it never reaches the public URL.
    const previewReport = applyPreviewFieldAllowlist(
      sanitizedPreviewReport,
      poolArtifactsCurrent ? 'serve' : 'withhold',
    );
    const evidenceFramingWithheld = previewRecord !== null && !poolArtifactsCurrent;

    // SEO headers (conditional based on admin indexing toggle)
    if (!share.allowIndexing) {
      res.setHeader('X-Robots-Tag', 'noindex, nofollow');
    }
    res.setHeader('Cache-Control', 'private, no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');

    res.json({
      shareType: 'discovery',
      niche: share.job.niche,
      // Display-safe short label — same word-boundary truncation as formatJobResponse.
      // `niche` above stays verbatim.
      nicheDisplay: toNicheDisplay(share.job.niche),
      solutions,
      discoveryFindings, // @deprecated — remove next release; use discoveryData + previewReport
      discoveryData,
      previewReport,
      // Honest signal for the visitor: the ranked list is current, the guidance about it
      // is not. Carries no reason code — the public payload states the fact, not the
      // internal artifact state that produced it.
      evidenceFramingWithheld,
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

    const shareHint = await prisma.discoveryShare.findUnique({
      where: { shareToken: paramsParsed.data.shareToken },
      select: { jobId: true },
    });
    if (!shareHint) {
      res.status(404).json({ error: 'Not found' });
      return;
    }

    const result = await prisma.$transaction(async (tx) => {
      // The token lookup above is only a routing hint. The locked Job row is the
      // serialization point shared with disable, rotate, and Deep Research start.
      const job = await lockJobForShareMutation(tx, shareHint.jobId);
      if (!job || !isDiscoveryShareLifecycleOpen(job)) {
        return { outcome: 'not_found' as const };
      }

      // Re-read the exact token and active flag after the lock. An old token must not vote
      // if disable/rotation/Deep Research won the race while this request was waiting.
      const share = await tx.discoveryShare.findUnique({
        where: { shareToken: paramsParsed.data.shareToken },
        include: {
          job: {
            select: { solutionIdeas: true },
          },
        },
      });
      if (!share || !share.isActive || share.jobId !== shareHint.jobId) {
        return { outcome: 'not_found' as const };
      }

      const { solutionId, solutionName, viewerToken, comment } = bodyParsed.data;
      const solutions = ensureIdeaIdentities(share.jobId, share.job.solutionIdeas);
      const selectedById = solutionId
        ? solutions.find(solution => solution.idea_id === solutionId)
        : undefined;
      const matchingNames = solutionName
        ? solutions.filter(solution => ideaName(solution) === solutionName)
        : [];

      if (solutionId && !selectedById) {
        return { outcome: 'invalid_identity' as const, reason: 'Invalid solution identity' };
      }
      if (selectedById && solutionName && ideaName(selectedById) !== solutionName) {
        return {
          outcome: 'invalid_identity' as const,
          reason: 'solutionId and solutionName refer to different ideas',
        };
      }
      if (!solutionId && matchingNames.length !== 1) {
        return {
          outcome: 'invalid_identity' as const,
          reason: matchingNames.length > 1
            ? 'solutionName is ambiguous; solutionId is required'
            : 'Invalid solution identity',
        };
      }

      const selectedSolution = selectedById ?? matchingNames[0];
      const resolvedSolutionId = selectedSolution?.idea_id;
      const resolvedSolutionName = selectedSolution ? ideaName(selectedSolution) : undefined;
      if (!resolvedSolutionId || !resolvedSolutionName) {
        return { outcome: 'invalid_identity' as const, reason: 'Invalid solution identity' };
      }

      const ipHash = hashIp(req.ip || 'unknown');
      const existingVote = await tx.discoveryVote.findUnique({
        where: { shareId_viewerToken: { shareId: share.id, viewerToken } },
      });

      if (!existingVote) {
        const existingTokensFromIp = await tx.discoveryVote.count({
          where: { shareId: share.id, ipHash },
        });
        if (existingTokensFromIp >= MAX_TOKENS_PER_IP) {
          return { outcome: 'vote_limit' as const };
        }
      }

      await tx.discoveryVote.upsert({
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

      const voteSummary = await buildVoteSummary(share.id, solutions, tx);
      return { outcome: 'ok' as const, voteSummary };
    });

    if (result.outcome === 'not_found') {
      res.status(404).json({ error: 'Not found' });
      return;
    }
    if (result.outcome === 'invalid_identity') {
      res.status(400).json({ error: result.reason });
      return;
    }
    if (result.outcome === 'vote_limit') {
      res.status(429).json({ error: 'Vote limit reached' });
      return;
    }
    res.json(result.voteSummary);
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
          select: {
            solutionIdeas: true,
            ...DISCOVERY_SHARE_LIFECYCLE_JOB_SELECT,
          },
        },
      },
    });

    if (
      !share
      || !share.isActive
      || !isDiscoveryShareLifecycleOpenForJob(share.job)
    ) {
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
