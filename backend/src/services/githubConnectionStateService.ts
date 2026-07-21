import crypto from 'node:crypto';
import { z } from 'zod';
import { getRedis } from './redis.js';

const STATE_TTL_SECONDS = 10 * 60;
const KEY_PREFIX = 'github-app-state:';

const StatePayloadSchema = z.discriminatedUnion('stage', [
  z.object({
    stage: z.literal('INSTALL'),
    userId: z.string().min(1),
    jobId: z.string().uuid(),
  }),
  z.object({
    stage: z.literal('OAUTH'),
    userId: z.string().min(1),
    jobId: z.string().uuid(),
    installationId: z.string().regex(/^\d+$/),
    codeVerifier: z.string().min(43).max(128),
  }),
]);

export type GithubConnectionState = z.infer<typeof StatePayloadSchema>;

function stateKey(state: string): string {
  return `${KEY_PREFIX}${crypto.createHash('sha256').update(state).digest('hex')}`;
}

export async function createGithubConnectionState(
  payload: GithubConnectionState,
): Promise<string> {
  const parsed = StatePayloadSchema.parse(payload);
  const redis = getRedis();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const state = crypto.randomBytes(32).toString('base64url');
    const stored = await redis.set(
      stateKey(state),
      JSON.stringify(parsed),
      'EX',
      STATE_TTL_SECONDS,
      'NX',
    );
    if (stored === 'OK') return state;
  }
  throw new Error('GITHUB_STATE_UNAVAILABLE');
}

export async function consumeGithubConnectionState(
  state: string,
): Promise<GithubConnectionState> {
  if (!/^[A-Za-z0-9_-]{43}$/.test(state)) throw new Error('GITHUB_STATE_INVALID');
  const redis = getRedis();
  const key = stateKey(state);
  const raw = await redis.eval(
    'local value = redis.call("GET", KEYS[1]); if value then redis.call("DEL", KEYS[1]); end; return value',
    1,
    key,
  );
  if (typeof raw !== 'string') throw new Error('GITHUB_STATE_INVALID');
  return StatePayloadSchema.parse(JSON.parse(raw));
}

export function createPkcePair(): { verifier: string; challenge: string } {
  const verifier = crypto.randomBytes(48).toString('base64url');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}
