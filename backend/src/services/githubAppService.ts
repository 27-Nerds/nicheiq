import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { CONFIG } from '../config.js';

const API_ROOT = 'https://api.github.com';
const OAUTH_TOKEN_URL = 'https://github.com/login/oauth/access_token';
const API_VERSION = '2026-03-10';

const AccountSchema = z.object({
  id: z.number().int().nonnegative(),
  login: z.string().min(1),
  type: z.string().optional(),
});

const InstallationSchema = z.object({
  id: z.number().int().nonnegative(),
  app_id: z.number().int().nonnegative(),
  account: AccountSchema,
  permissions: z.record(z.string()),
  repository_selection: z.string().optional(),
});

const RepositorySchema = z.object({
  id: z.number().int().nonnegative(),
  name: z.string().min(1),
  full_name: z.string().min(3),
  html_url: z.string().url(),
  has_issues: z.boolean(),
  private: z.boolean(),
});

const OAuthTokenSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string(),
});

const IssueSchema = z.object({
  id: z.number().int().nonnegative(),
  node_id: z.string().min(1),
  number: z.number().int().positive(),
  html_url: z.string().url(),
  title: z.string(),
  body: z.string().nullable().optional(),
});

const ListedIssueSchema = IssueSchema.extend({
  pull_request: z.unknown().optional(),
});

export type GithubInstallation = z.infer<typeof InstallationSchema>;
export type GithubRepository = z.infer<typeof RepositorySchema>;
export type GithubIssue = z.infer<typeof IssueSchema>;

export class GithubProviderError extends Error {
  constructor(
    public readonly status: number | null,
    public readonly code: string,
    public readonly ambiguous: boolean,
  ) {
    super(code);
  }
}

function requireGithubConfig() {
  if (!CONFIG.githubApp.enabled) throw new Error('GITHUB_APP_DISABLED');
  if (
    !CONFIG.githubApp.appId
    || !CONFIG.githubApp.slug
    || !CONFIG.githubApp.clientId
    || !CONFIG.githubApp.clientSecret
    || !CONFIG.githubApp.privateKeyBase64
    || !CONFIG.githubApp.callbackUrl
  ) {
    throw new Error('GITHUB_APP_NOT_CONFIGURED');
  }
  return CONFIG.githubApp;
}

function githubHeaders(token: string): Record<string, string> {
  return {
    Accept: 'application/vnd.github+json',
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    'User-Agent': 'NicheIQ-GitHub-App',
    'X-GitHub-Api-Version': API_VERSION,
  };
}

async function jsonResponse(response: Response): Promise<unknown> {
  return response.json().catch(() => null);
}

async function apiRequest(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { ...githubHeaders(token), ...init.headers },
    signal: init.signal ?? AbortSignal.timeout(10_000),
  });
}

function safeRepositoryId(repositoryId: string): number {
  const value = Number(repositoryId);
  if (!Number.isSafeInteger(value) || value < 1) throw new Error('GITHUB_REPOSITORY_ID_INVALID');
  return value;
}

function createAppJwt(): string {
  const config = requireGithubConfig();
  const privateKey = Buffer.from(config.privateKeyBase64, 'base64').toString('utf8');
  if (!privateKey.includes('PRIVATE KEY')) throw new Error('GITHUB_APP_PRIVATE_KEY_INVALID');
  const now = Math.floor(Date.now() / 1000);
  return jwt.sign(
    { iat: now - 60, exp: now + 9 * 60, iss: config.clientId },
    privateKey,
    { algorithm: 'RS256', noTimestamp: true },
  );
}

export function githubAppEnabled(): boolean {
  return CONFIG.githubApp.enabled;
}

export function githubInstallUrl(state: string): string {
  const config = requireGithubConfig();
  const url = new URL(`https://github.com/apps/${config.slug}/installations/new`);
  url.searchParams.set('state', state);
  return url.toString();
}

export function githubUserAuthorizationUrl(
  state: string,
  codeChallenge: string,
): string {
  const config = requireGithubConfig();
  const url = new URL('https://github.com/login/oauth/authorize');
  url.searchParams.set('client_id', config.clientId);
  url.searchParams.set('redirect_uri', config.callbackUrl);
  url.searchParams.set('state', state);
  url.searchParams.set('code_challenge', codeChallenge);
  url.searchParams.set('code_challenge_method', 'S256');
  return url.toString();
}

export async function exchangeGithubCode(
  code: string,
  codeVerifier: string,
): Promise<string> {
  const config = requireGithubConfig();
  const response = await fetch(OAUTH_TOKEN_URL, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'User-Agent': 'NicheIQ-GitHub-App',
    },
    body: JSON.stringify({
      client_id: config.clientId,
      client_secret: config.clientSecret,
      code,
      redirect_uri: config.callbackUrl,
      code_verifier: codeVerifier,
    }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error('GITHUB_OAUTH_EXCHANGE_FAILED');
  return OAuthTokenSchema.parse(await jsonResponse(response)).access_token;
}

async function paginated<T>(
  path: string,
  token: string,
  itemSchema: z.ZodType<T>,
  containerKey: 'installations' | 'repositories',
): Promise<T[]> {
  const items: T[] = [];
  for (let page = 1; page <= 100; page += 1) {
    const separator = path.includes('?') ? '&' : '?';
    const response = await apiRequest(`${path}${separator}per_page=100&page=${page}`, token);
    if (!response.ok) throw new Error('GITHUB_ACCESS_CHECK_FAILED');
    const body = z.record(z.unknown()).parse(await jsonResponse(response));
    const batch = z.array(itemSchema).parse(body[containerKey]);
    items.push(...batch);
    if (batch.length < 100) return items;
  }
  throw new Error('GITHUB_PAGINATION_LIMIT');
}

export async function listGithubUserInstallations(
  userToken: string,
): Promise<GithubInstallation[]> {
  return paginated('/user/installations', userToken, InstallationSchema, 'installations');
}

export async function listGithubUserRepositories(
  userToken: string,
  installationId: string,
): Promise<GithubRepository[]> {
  return paginated(
    `/user/installations/${encodeURIComponent(installationId)}/repositories`,
    userToken,
    RepositorySchema,
    'repositories',
  );
}

export async function mintGithubInstallationToken(
  installationId: string,
  repositoryId?: string,
): Promise<string> {
  const body = repositoryId
    ? { repository_ids: [safeRepositoryId(repositoryId)], permissions: { issues: 'write' } }
    : {};
  const response = await apiRequest(
    `/app/installations/${encodeURIComponent(installationId)}/access_tokens`,
    createAppJwt(),
    { method: 'POST', body: JSON.stringify(body) },
  );
  if (!response.ok) throw new Error('GITHUB_INSTALLATION_TOKEN_FAILED');
  return z.object({ token: z.string().min(1) }).parse(await jsonResponse(response)).token;
}

export async function listGithubInstallationRepositories(
  installationId: string,
): Promise<GithubRepository[]> {
  const token = await mintGithubInstallationToken(installationId);
  return paginated('/installation/repositories', token, RepositorySchema, 'repositories');
}

function issueErrorCode(status: number): string {
  if (status === 400) return 'GITHUB_BAD_REQUEST';
  if (status === 403) return 'GITHUB_FORBIDDEN';
  if (status === 404) return 'GITHUB_REPOSITORY_NOT_FOUND';
  if (status === 429) return 'GITHUB_RATE_LIMITED';
  if (status === 410) return 'GITHUB_ISSUES_DISABLED';
  if (status === 422) return 'GITHUB_VALIDATION_FAILED';
  if (status >= 500) return 'GITHUB_UNAVAILABLE';
  return 'GITHUB_CREATE_REJECTED';
}

export async function createGithubIssueWithToken(
  token: string,
  owner: string,
  name: string,
  title: string,
  body: string,
): Promise<GithubIssue> {
  let response: Response;
  try {
    response = await apiRequest(
      `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}/issues`,
      token,
      {
        method: 'POST',
        body: JSON.stringify({ title, body }),
        signal: AbortSignal.timeout(12_000),
      },
    );
  } catch {
    throw new GithubProviderError(null, 'GITHUB_CREATE_OUTCOME_UNKNOWN', true);
  }
  if (!response.ok) {
    throw new GithubProviderError(
      response.status,
      issueErrorCode(response.status),
      response.status >= 500,
    );
  }
  try {
    const issue = IssueSchema.parse(await jsonResponse(response));
    if (!issue.html_url.startsWith('https://github.com/')) throw new Error('invalid URL');
    return issue;
  } catch {
    throw new GithubProviderError(response.status, 'GITHUB_CREATE_RESPONSE_INVALID', true);
  }
}

export async function findMatchingGithubIssues(
  installationId: string,
  repositoryId: string,
  owner: string,
  name: string,
  title: string,
  body: string,
  since: Date,
): Promise<GithubIssue[]> {
  const token = await mintGithubInstallationToken(installationId, repositoryId);
  const matches: GithubIssue[] = [];
  for (let page = 1; page <= 3; page += 1) {
    const query = new URLSearchParams({
      state: 'all',
      sort: 'created',
      direction: 'desc',
      since: since.toISOString(),
      per_page: '100',
      page: String(page),
    });
    const response = await apiRequest(
      `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}/issues?${query}`,
      token,
    );
    if (!response.ok) throw new Error('GITHUB_RECONCILIATION_FAILED');
    const batch = z.array(ListedIssueSchema).parse(await jsonResponse(response));
    for (const issue of batch) {
      if (!issue.pull_request && issue.title === title && (issue.body ?? '') === body) {
        matches.push(IssueSchema.parse(issue));
      }
    }
    if (batch.length < 100) break;
  }
  return matches;
}
