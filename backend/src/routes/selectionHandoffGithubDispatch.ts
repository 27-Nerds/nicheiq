import {
  IntegrationConnectionStatus,
  IntegrationProvider,
  Prisma,
  SelectionHandoffDispatchStatus,
  type IntegrationConnection,
  type SelectionDecisionHandoff,
  type SelectionHandoffDispatch,
} from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import {
  createGithubIssueWithToken,
  findMatchingGithubIssues,
  GithubProviderError,
  listGithubInstallationRepositories,
  mintGithubInstallationToken,
  type GithubRepository,
} from '../services/githubAppService.js';
import { prisma } from '../services/db.js';
import {
  GithubDispatchPayloadSchema,
  materializeGithubIssuePreview,
} from '../services/selectionHandoffGithubAdapter.js';

const ParamsSchema = z.object({ jobId: z.string().uuid() });
const DispatchParamsSchema = ParamsSchema.extend({ dispatchId: z.string().uuid() });
const PreviewSchema = z.object({
  connectionId: z.string().uuid(),
  repositoryId: z.string().regex(/^\d+$/),
}).strict();
const ConfirmSchema = PreviewSchema.extend({
  payloadFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
}).strict();

const STALE_PENDING_MS = 2 * 60 * 1000;
const RETRYABLE_GITHUB_ERROR_CODES = new Set([
  'GITHUB_FORBIDDEN',
  'GITHUB_REPOSITORY_NOT_FOUND',
  'GITHUB_RATE_LIMITED',
]);

export const selectionHandoffGithubDispatchRouter = Router();

function canRetryGithubDispatch(dispatch: SelectionHandoffDispatch): boolean {
  return dispatch.status === SelectionHandoffDispatchStatus.FAILED
    && !!dispatch.lastErrorCode
    && RETRYABLE_GITHUB_ERROR_CODES.has(dispatch.lastErrorCode);
}

function publicDispatch(dispatch: SelectionHandoffDispatch) {
  return {
    id: dispatch.id,
    handoffId: dispatch.handoffId,
    provider: dispatch.provider,
    adapterVersion: dispatch.adapterVersion,
    destinationContainerId: dispatch.destinationContainerId,
    destination: dispatch.destinationSnapshot,
    payload: dispatch.payload,
    payloadFingerprint: dispatch.payloadFingerprint,
    status: dispatch.status,
    retryable: canRetryGithubDispatch(dispatch),
    attemptCount: dispatch.attemptCount,
    connectionId: dispatch.connectionId,
    providerResourceId: dispatch.providerResourceId,
    providerResourceNodeId: dispatch.providerResourceNodeId,
    providerResourceNumber: dispatch.providerResourceNumber,
    providerResourceUrl: dispatch.providerResourceUrl,
    errorClass: dispatch.lastErrorClass,
    errorCode: dispatch.lastErrorCode,
    providerRequestStartedAt: dispatch.providerRequestStartedAt,
    settledAt: dispatch.settledAt,
    reconciledAt: dispatch.reconciledAt,
    createdAt: dispatch.createdAt,
    updatedAt: dispatch.updatedAt,
  };
}

function authorizedRepositoryIds(connection: IntegrationConnection): Set<string> {
  if (!Array.isArray(connection.authorizedRepositoryIds)) return new Set();
  return new Set(connection.authorizedRepositoryIds.flatMap((value) => (
    typeof value === 'string' && /^\d+$/.test(value) ? [value] : []
  )));
}

async function loadOwnedHandoff(
  jobId: string,
  userId: string,
): Promise<
  | { jobFound: false; handoff: null }
  | { jobFound: true; handoff: SelectionDecisionHandoff | null }
> {
  const job = await prisma.job.findFirst({
    where: { id: jobId, userId },
    select: {
      selectionFinalDecision: {
        select: { decisionHandoff: true },
      },
    },
  });
  if (!job) return { jobFound: false, handoff: null };
  return {
    jobFound: true,
    handoff: job.selectionFinalDecision?.decisionHandoff ?? null,
  };
}

async function loadOwnedConnection(
  connectionId: string,
  userId: string,
): Promise<IntegrationConnection | null> {
  return prisma.integrationConnection.findFirst({
    where: {
      id: connectionId,
      userId,
      provider: IntegrationProvider.GITHUB,
      status: IntegrationConnectionStatus.ACTIVE,
    },
  });
}

async function accessibleRepository(
  connection: IntegrationConnection,
  repositoryId: string,
): Promise<GithubRepository | null> {
  if (!authorizedRepositoryIds(connection).has(repositoryId)) return null;
  const repositories = await listGithubInstallationRepositories(connection.externalId);
  return repositories.find((repository) => String(repository.id) === repositoryId) ?? null;
}

async function recoverStalePending(handoffId: string): Promise<void> {
  await prisma.selectionHandoffDispatch.updateMany({
    where: {
      handoffId,
      provider: IntegrationProvider.GITHUB,
      status: SelectionHandoffDispatchStatus.PENDING,
      updatedAt: { lt: new Date(Date.now() - STALE_PENDING_MS) },
    },
    data: {
      status: SelectionHandoffDispatchStatus.UNKNOWN,
      lastErrorClass: 'AMBIGUOUS',
      lastErrorCode: 'STALE_PENDING',
      settledAt: new Date(),
    },
  });
}

function requestError(error: unknown): { status: number; message: string } {
  if (error instanceof z.ZodError) return { status: 400, message: 'Invalid GitHub dispatch request' };
  if (!(error instanceof Error)) return { status: 500, message: 'GitHub dispatch failed' };
  const errors: Record<string, { status: number; message: string }> = {
    GITHUB_HANDOFF_NOT_DISPATCHABLE: {
      status: 409,
      message: 'This owner decision cannot create external work',
    },
    GITHUB_ISSUES_DISABLED: {
      status: 409,
      message: 'Issues are disabled for this repository',
    },
    GITHUB_REPOSITORY_INVALID: {
      status: 409,
      message: 'GitHub returned an invalid repository destination',
    },
    GITHUB_INSTALLATION_TOKEN_FAILED: {
      status: 502,
      message: 'GitHub installation access could not be verified',
    },
  };
  return errors[error.message] ?? { status: 502, message: 'GitHub dispatch could not be completed' };
}

async function dispatchContext(
  jobId: string,
  userId: string,
  connectionId: string,
  repositoryId: string,
) {
  const owned = await loadOwnedHandoff(jobId, userId);
  if (!owned.jobFound) {
    return { ok: false, error: { status: 404, message: 'Job not found' } } as const;
  }
  const { handoff } = owned;
  if (!handoff) {
    return {
      ok: false,
      error: { status: 409, message: 'Create the decision handoff first' },
    } as const;
  }
  const connection = await loadOwnedConnection(connectionId, userId);
  if (!connection) {
    return {
      ok: false,
      error: { status: 404, message: 'GitHub connection not found' },
    } as const;
  }
  const repository = await accessibleRepository(connection, repositoryId);
  if (!repository) {
    return {
      ok: false,
      error: { status: 404, message: 'Repository is not available to this connection' },
    } as const;
  }
  return { ok: true, handoff, connection, repository } as const;
}

selectionHandoffGithubDispatchRouter.post(
  '/:jobId/decision-handoff/github/preview',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = ParamsSchema.parse(req.params);
      const { connectionId, repositoryId } = PreviewSchema.parse(req.body);
      const context = await dispatchContext(
        jobId,
        req.user!.id,
        connectionId,
        repositoryId,
      );
      if (!context.ok) {
        res.status(context.error.status).json({ error: context.error.message });
        return;
      }
      const preview = materializeGithubIssuePreview(
        context.handoff,
        context.connection.id,
        context.repository,
      );
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ preview });
    } catch (error) {
      const known = requestError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

selectionHandoffGithubDispatchRouter.get(
  '/:jobId/decision-handoff/github/dispatch',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = ParamsSchema.parse(req.params);
      const owned = await loadOwnedHandoff(jobId, req.user!.id);
      if (!owned.jobFound) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const { handoff } = owned;
      if (!handoff) {
        res.json({ dispatch: null });
        return;
      }
      await recoverStalePending(handoff.id);
      const dispatch = await prisma.selectionHandoffDispatch.findUnique({
        where: {
          handoffId_provider: {
            handoffId: handoff.id,
            provider: IntegrationProvider.GITHUB,
          },
        },
      });
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ dispatch: dispatch ? publicDispatch(dispatch) : null });
    } catch (error) {
      const known = requestError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

selectionHandoffGithubDispatchRouter.post(
  '/:jobId/decision-handoff/github/dispatch',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId } = ParamsSchema.parse(req.params);
      const { connectionId, repositoryId, payloadFingerprint } = ConfirmSchema.parse(req.body);
      const context = await dispatchContext(
        jobId,
        req.user!.id,
        connectionId,
        repositoryId,
      );
      if (!context.ok) {
        res.status(context.error.status).json({ error: context.error.message });
        return;
      }
      await recoverStalePending(context.handoff.id);
      const preview = materializeGithubIssuePreview(
        context.handoff,
        context.connection.id,
        context.repository,
      );
      if (preview.payloadFingerprint !== payloadFingerprint) {
        res.status(409).json({ error: 'The GitHub issue preview changed. Review it again.' });
        return;
      }
      const existing = await prisma.selectionHandoffDispatch.findUnique({
        where: {
          handoffId_provider: {
            handoffId: context.handoff.id,
            provider: IntegrationProvider.GITHUB,
          },
        },
      });
      if (existing && !canRetryGithubDispatch(existing)) {
        if (existing.payloadFingerprint !== preview.payloadFingerprint) {
          res.status(409).json({ error: 'A GitHub dispatch already exists for this handoff' });
          return;
        }
        res.json({ dispatch: publicDispatch(existing) });
        return;
      }

      if (existing?.payloadFingerprint !== undefined
        && existing.payloadFingerprint !== preview.payloadFingerprint) {
        res.status(409).json({ error: 'A GitHub dispatch already exists for this handoff' });
        return;
      }

      // Verify credentials before either creating or reclaiming a receipt. Only
      // definitive, transient provider rejections can be retried; UNKNOWN remains
      // reconciliation-only because GitHub may already have created the issue.
      const installationToken = await mintGithubInstallationToken(
        context.connection.externalId,
        repositoryId,
      );
      let pending: SelectionHandoffDispatch;
      if (existing) {
        const reclaimed = await prisma.selectionHandoffDispatch.updateMany({
          where: {
            id: existing.id,
            status: SelectionHandoffDispatchStatus.FAILED,
            attemptCount: existing.attemptCount,
            lastErrorCode: { in: [...RETRYABLE_GITHUB_ERROR_CODES] },
          },
          data: {
            status: SelectionHandoffDispatchStatus.PENDING,
            attemptCount: { increment: 1 },
            providerRequestStartedAt: new Date(),
            lastErrorClass: null,
            lastErrorCode: null,
            settledAt: null,
          },
        });
        if (reclaimed.count === 0) {
          const winner = await prisma.selectionHandoffDispatch.findUniqueOrThrow({
            where: { id: existing.id },
          });
          res.json({ dispatch: publicDispatch(winner) });
          return;
        }
        pending = await prisma.selectionHandoffDispatch.findUniqueOrThrow({
          where: { id: existing.id },
        });
      } else try {
        pending = await prisma.selectionHandoffDispatch.create({
          data: {
            handoffId: context.handoff.id,
            connectionId: context.connection.id,
            provider: IntegrationProvider.GITHUB,
            adapterVersion: preview.adapterVersion,
            destinationContainerId: repositoryId,
            destinationSnapshot: preview.payload.destination,
            payload: preview.payload,
            payloadFingerprint: preview.payloadFingerprint,
            confirmedByUserId: req.user!.id,
          },
        });
      } catch (error) {
        if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
          const winner = await prisma.selectionHandoffDispatch.findUnique({
            where: {
              handoffId_provider: {
                handoffId: context.handoff.id,
                provider: IntegrationProvider.GITHUB,
              },
            },
          });
          if (winner?.payloadFingerprint === preview.payloadFingerprint) {
            res.json({ dispatch: publicDispatch(winner) });
            return;
          }
          res.status(409).json({ error: 'Another GitHub dispatch was created first' });
          return;
        }
        throw error;
      }

      try {
        const issue = await createGithubIssueWithToken(
          installationToken,
          preview.payload.destination.owner,
          preview.payload.destination.name,
          preview.payload.request.title,
          preview.payload.request.body,
        );
        const dispatch = await prisma.selectionHandoffDispatch.update({
          where: { id: pending.id },
          data: {
            status: SelectionHandoffDispatchStatus.SUCCEEDED,
            providerResourceId: String(issue.id),
            providerResourceNodeId: issue.node_id,
            providerResourceNumber: issue.number,
            providerResourceUrl: issue.html_url,
            settledAt: new Date(),
          },
        });
        res.status(201).json({ dispatch: publicDispatch(dispatch) });
      } catch (error) {
        const ambiguous = !(error instanceof GithubProviderError) || error.ambiguous;
        const dispatch = await prisma.selectionHandoffDispatch.update({
          where: { id: pending.id },
          data: {
            status: ambiguous
              ? SelectionHandoffDispatchStatus.UNKNOWN
              : SelectionHandoffDispatchStatus.FAILED,
            lastErrorClass: ambiguous ? 'AMBIGUOUS' : 'PROVIDER_REJECTED',
            lastErrorCode: error instanceof GithubProviderError
              ? error.code
              : 'GITHUB_CREATE_OUTCOME_UNKNOWN',
            settledAt: new Date(),
          },
        });
        res.status(201).json({ dispatch: publicDispatch(dispatch) });
      }
    } catch (error) {
      const known = requestError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

selectionHandoffGithubDispatchRouter.post(
  '/:jobId/decision-handoff/github/dispatch/:dispatchId/reconcile',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { jobId, dispatchId } = DispatchParamsSchema.parse(req.params);
      const owned = await loadOwnedHandoff(jobId, req.user!.id);
      if (!owned.jobFound) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const { handoff } = owned;
      if (!handoff) {
        res.status(404).json({ error: 'Decision handoff not found' });
        return;
      }
      await recoverStalePending(handoff.id);
      const dispatch = await prisma.selectionHandoffDispatch.findFirst({
        where: {
          id: dispatchId,
          handoffId: handoff.id,
          provider: IntegrationProvider.GITHUB,
        },
      });
      if (!dispatch) {
        res.status(404).json({ error: 'GitHub dispatch not found' });
        return;
      }
      if (dispatch.status !== SelectionHandoffDispatchStatus.UNKNOWN) {
        res.json({ dispatch: publicDispatch(dispatch), reconciliation: 'not_required' });
        return;
      }
      const connection = await loadOwnedConnection(dispatch.connectionId, req.user!.id);
      if (!connection) {
        res.status(409).json({ error: 'Reconnect GitHub before reconciling this dispatch' });
        return;
      }
      const payload = GithubDispatchPayloadSchema.parse(dispatch.payload);
      const repository = await accessibleRepository(
        connection,
        payload.destination.repositoryId,
      );
      if (
        !repository
        || repository.full_name !== payload.destination.fullName
      ) {
        res.status(409).json({ error: 'The original GitHub repository is no longer available' });
        return;
      }
      const matches = await findMatchingGithubIssues(
        connection.externalId,
        payload.destination.repositoryId,
        payload.destination.owner,
        payload.destination.name,
        payload.request.title,
        payload.request.body,
        new Date(dispatch.providerRequestStartedAt.getTime() - 2 * 60 * 1000),
      );
      if (matches.length !== 1) {
        const unchanged = matches.length > 1
          ? await prisma.selectionHandoffDispatch.update({
              where: { id: dispatch.id },
              data: {
                lastErrorClass: 'AMBIGUOUS',
                lastErrorCode: 'MULTIPLE_MATCHING_ISSUES',
              },
            })
          : dispatch;
        res.json({
          dispatch: publicDispatch(unchanged),
          reconciliation: matches.length ? 'multiple_matches' : 'not_found',
        });
        return;
      }
      const [issue] = matches;
      await prisma.selectionHandoffDispatch.updateMany({
        where: { id: dispatch.id, status: SelectionHandoffDispatchStatus.UNKNOWN },
        data: {
          status: SelectionHandoffDispatchStatus.SUCCEEDED,
          providerResourceId: String(issue.id),
          providerResourceNodeId: issue.node_id,
          providerResourceNumber: issue.number,
          providerResourceUrl: issue.html_url,
          lastErrorClass: null,
          lastErrorCode: null,
          reconciledAt: new Date(),
          reconciledByUserId: req.user!.id,
        },
      });
      const settled = await prisma.selectionHandoffDispatch.findUniqueOrThrow({
        where: { id: dispatch.id },
      });
      res.json({ dispatch: publicDispatch(settled), reconciliation: 'matched' });
    } catch (error) {
      const known = requestError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);
