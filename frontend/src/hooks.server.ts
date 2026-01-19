import { handle as authHandle } from './auth';
import { env } from '$env/dynamic/private';

// Fail fast if required env vars are not set
if (!env.INTERNAL_SERVICE_SECRET) {
  throw new Error('INTERNAL_SERVICE_SECRET environment variable is required');
}

export const handle = authHandle;
