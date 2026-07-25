import { IntegrationConnectionStatus, IntegrationProvider, Prisma } from '@prisma/client';
import { Router, type Response } from 'express';
import { z } from 'zod';
import { CONFIG } from '../config.js';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { requireDecisionToolsAccess } from '../middleware/featureAccess.js';
import {
  exchangeGithubCode,
  githubAppEnabled,
  githubInstallUrl,
  githubUserAuthorizationUrl,
  listGithubInstallationRepositories,
  listGithubUserInstallations,
  listGithubUserRepositories,
} from '../services/githubAppService.js';
import {
  consumeGithubConnectionState,
  createGithubConnectionState,
  createPkcePair,
} from '../services/githubConnectionStateService.js';
import { prisma } from '../services/db.js';

const JobBodySchema = z.object({ jobId: z.string().uuid() }).strict();
const SetupBodySchema = z.object({
  state: z.string().min(1),
  installationId: z.string().regex(/^\d+$/),
}).strict();
const CallbackBodySchema = z.object({
  state: z.string().min(1),
  code: z.string().min(1).max(255),
}).strict();
const ConnectionParamsSchema = z.object({ connectionId: z.string().uuid() });

export const githubIntegrationsRouter = Router();

function publicConnection(connection: {
  id: string;
  accountLogin: string;
  accountType: string | null;
  repositorySelection: string | null;
  status: IntegrationConnectionStatus;
  lastVerifiedAt: Date | null;
  createdAt: Date;
}) {
  return {
    id: connection.id,
    provider: 'GITHUB' as const,
    accountLogin: connection.accountLogin,
    accountType: connection.accountType,
    repositorySelection: connection.repositorySelection,
    status: connection.status,
    lastVerifiedAt: connection.lastVerifiedAt,
    createdAt: connection.createdAt,
  };
}

function repositoryIds(value: Prisma.JsonValue): Set<string> {
  if (!Array.isArray(value)) return new Set();
  return new Set(value.flatMap((id) => (
    typeof id === 'string' && /^\d+$/.test(id) ? [id] : []
  )));
}

async function ownedConnection(connectionId: string, userId: string) {
  return prisma.integrationConnection.findFirst({
    where: {
      id: connectionId,
      userId,
      provider: IntegrationProvider.GITHUB,
      status: IntegrationConnectionStatus.ACTIVE,
    },
  });
}

function integrationError(error: unknown): { status: number; message: string } {
  if (error instanceof z.ZodError) return { status: 400, message: 'Invalid GitHub integration request' };
  if (!(error instanceof Error)) return { status: 500, message: 'GitHub integration failed' };
  const known: Record<string, { status: number; message: string }> = {
    GITHUB_APP_DISABLED: { status: 503, message: 'GitHub integration is not configured' },
    GITHUB_APP_NOT_CONFIGURED: { status: 503, message: 'GitHub integration is not configured' },
    GITHUB_STATE_INVALID: { status: 400, message: 'This GitHub connection link is invalid or expired' },
    GITHUB_STATE_UNAVAILABLE: { status: 503, message: 'Could not start GitHub connection' },
    GITHUB_OAUTH_EXCHANGE_FAILED: { status: 400, message: 'GitHub authorization could not be verified' },
    GITHUB_ACCESS_CHECK_FAILED: { status: 403, message: 'GitHub installation access could not be verified' },
    GITHUB_ISSUES_PERMISSION_REQUIRED: { status: 409, message: 'The GitHub App requires Issues: write permission' },
    GITHUB_INSTALLATION_NOT_ACCESSIBLE: { status: 403, message: 'That GitHub installation is not available to this user' },
  };
  return known[error.message] ?? { status: 502, message: 'GitHub integration could not be completed' };
}

githubIntegrationsRouter.get(
  '/connections',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      if (!githubAppEnabled()) {
        res.json({ enabled: false, connections: [] });
        return;
      }
      const connections = await prisma.integrationConnection.findMany({
        where: {
          userId: req.user!.id,
          provider: IntegrationProvider.GITHUB,
          status: IntegrationConnectionStatus.ACTIVE,
        },
        orderBy: { createdAt: 'asc' },
      });
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ enabled: true, connections: connections.map(publicConnection) });
    } catch (error) {
      console.error('Failed to list GitHub connections:', error);
      res.status(500).json({ error: 'Failed to load GitHub connections' });
    }
  },
);

githubIntegrationsRouter.post(
  '/install-session',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      if (!githubAppEnabled()) throw new Error('GITHUB_APP_DISABLED');
      const { jobId } = JobBodySchema.parse(req.body);
      const job = await prisma.job.findFirst({
        where: { id: jobId, userId: req.user!.id },
        select: { id: true },
      });
      if (!job) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }
      const state = await createGithubConnectionState({
        stage: 'INSTALL',
        userId: req.user!.id,
        jobId,
      });
      res.status(201).json({ installUrl: githubInstallUrl(state) });
    } catch (error) {
      const known = integrationError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

githubIntegrationsRouter.post(
  '/setup',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { state, installationId } = SetupBodySchema.parse(req.body);
      const pending = await consumeGithubConnectionState(state);
      if (pending.stage !== 'INSTALL' || pending.userId !== req.user!.id) {
        throw new Error('GITHUB_STATE_INVALID');
      }
      const pkce = createPkcePair();
      const oauthState = await createGithubConnectionState({
        stage: 'OAUTH',
        userId: pending.userId,
        jobId: pending.jobId,
        installationId,
        codeVerifier: pkce.verifier,
      });
      res.json({ authorizeUrl: githubUserAuthorizationUrl(oauthState, pkce.challenge) });
    } catch (error) {
      const known = integrationError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

githubIntegrationsRouter.post(
  '/callback',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { state, code } = CallbackBodySchema.parse(req.body);
      const pending = await consumeGithubConnectionState(state);
      if (pending.stage !== 'OAUTH' || pending.userId !== req.user!.id) {
        throw new Error('GITHUB_STATE_INVALID');
      }
      const userToken = await exchangeGithubCode(code, pending.codeVerifier);
      const installations = await listGithubUserInstallations(userToken);
      const installation = installations.find((item) => (
        String(item.id) === pending.installationId
        && String(item.app_id) === CONFIG.githubApp.appId
      ));
      if (!installation) throw new Error('GITHUB_INSTALLATION_NOT_ACCESSIBLE');
      if (installation.permissions.issues !== 'write') {
        throw new Error('GITHUB_ISSUES_PERMISSION_REQUIRED');
      }
      const repositories = await listGithubUserRepositories(userToken, pending.installationId);
      const connection = await prisma.integrationConnection.upsert({
        where: {
          userId_provider_externalId: {
            userId: pending.userId,
            provider: IntegrationProvider.GITHUB,
            externalId: pending.installationId,
          },
        },
        create: {
          userId: pending.userId,
          provider: IntegrationProvider.GITHUB,
          externalId: pending.installationId,
          accountId: String(installation.account.id),
          accountLogin: installation.account.login,
          accountType: installation.account.type ?? null,
          repositorySelection: installation.repository_selection ?? null,
          permissions: installation.permissions,
          authorizedRepositoryIds: repositories.map((repository) => String(repository.id)),
          lastVerifiedAt: new Date(),
        },
        update: {
          accountId: String(installation.account.id),
          accountLogin: installation.account.login,
          accountType: installation.account.type ?? null,
          repositorySelection: installation.repository_selection ?? null,
          permissions: installation.permissions,
          authorizedRepositoryIds: repositories.map((repository) => String(repository.id)),
          status: IntegrationConnectionStatus.ACTIVE,
          lastVerifiedAt: new Date(),
        },
      });
      res.json({
        connection: publicConnection(connection),
        returnPath: `/jobs/${pending.jobId}/report?github=connected`,
      });
    } catch (error) {
      const known = integrationError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

githubIntegrationsRouter.get(
  '/connections/:connectionId/repositories',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { connectionId } = ConnectionParamsSchema.parse(req.params);
      const connection = await ownedConnection(connectionId, req.user!.id);
      if (!connection) {
        res.status(404).json({ error: 'GitHub connection not found' });
        return;
      }
      const allowed = repositoryIds(connection.authorizedRepositoryIds);
      const live = await listGithubInstallationRepositories(connection.externalId);
      const repositories = live
        .filter((repository) => allowed.has(String(repository.id)))
        .map((repository) => ({
          id: String(repository.id),
          name: repository.name,
          fullName: repository.full_name,
          htmlUrl: repository.html_url,
          private: repository.private,
          hasIssues: repository.has_issues,
        }))
        .sort((a, b) => a.fullName.localeCompare(b.fullName));
      await prisma.integrationConnection.update({
        where: { id: connection.id },
        data: { lastVerifiedAt: new Date() },
      });
      res.setHeader('Cache-Control', 'private, no-store');
      res.json({ repositories });
    } catch (error) {
      const known = integrationError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);

githubIntegrationsRouter.delete(
  '/connections/:connectionId',
  requireInternalAuth,
  requireDecisionToolsAccess,
  async (req: AuthenticatedRequest, res: Response) => {
    try {
      const { connectionId } = ConnectionParamsSchema.parse(req.params);
      const result = await prisma.integrationConnection.updateMany({
        where: {
          id: connectionId,
          userId: req.user!.id,
          provider: IntegrationProvider.GITHUB,
          status: IntegrationConnectionStatus.ACTIVE,
        },
        data: { status: IntegrationConnectionStatus.REVOKED },
      });
      if (!result.count) {
        res.status(404).json({ error: 'GitHub connection not found' });
        return;
      }
      res.status(204).send();
    } catch (error) {
      const known = integrationError(error);
      res.status(known.status).json({ error: known.message });
    }
  },
);
