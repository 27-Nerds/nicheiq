import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('validateConfig', () => {
  it('requires an explicit experiment signing secret in production', async () => {
    vi.stubEnv('NODE_ENV', 'production');
    vi.stubEnv('AUTH_SECRET', 'a'.repeat(32));
    vi.stubEnv('EXPERIMENT_SIGNING_SECRET', '');
    vi.stubEnv('GITHUB_APP_ENABLED', 'false');

    const { validateConfig } = await import('../config.js');

    expect(() => validateConfig()).toThrow(
      'Missing required environment variables: EXPERIMENT_SIGNING_SECRET',
    );
  });

  it('accepts an explicit experiment signing secret in production', async () => {
    vi.stubEnv('NODE_ENV', 'production');
    vi.stubEnv('AUTH_SECRET', 'a'.repeat(32));
    vi.stubEnv('EXPERIMENT_SIGNING_SECRET', 'e'.repeat(32));
    vi.stubEnv('GITHUB_APP_ENABLED', 'false');

    const { validateConfig } = await import('../config.js');

    expect(() => validateConfig()).not.toThrow();
  });
});
