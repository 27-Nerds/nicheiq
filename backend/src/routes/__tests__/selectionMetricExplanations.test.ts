import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import express from 'express';
import request from 'supertest';
import { selectionMetricExplanationsRouter } from '../selectionMetricExplanations.js';

const app = express();
app.use('/api/selection', selectionMetricExplanationsRouter);

const CAP_ENV_VARS = [
  'PAYABILITY_LOW_THRESHOLD',
  'PAYABILITY_MARKET_FIT_CAP',
  'PARITY_SHIPPED_MARKET_FIT_CAP',
  'PARITY_PARTIAL_MARKET_FIT_CAP',
  'PARITY_SUBSTITUTE_MARKET_FIT_CAP',
  'PARITY_SUBSTITUTE_WEAK_WALLET_CAP',
  'PARITY_BUNDLED_FREE_CAP',
] as const;

describe('selection metric explanations API', () => {
  const priorSecret = process.env.INTERNAL_SERVICE_SECRET;
  const priorCapEnv = new Map<string, string | undefined>(
    CAP_ENV_VARS.map((name) => [name, process.env[name]]),
  );

  beforeEach(() => {
    process.env.INTERNAL_SERVICE_SECRET = 'metric-test-secret';
    for (const name of CAP_ENV_VARS) delete process.env[name];
  });

  afterEach(() => {
    if (priorSecret === undefined) delete process.env.INTERNAL_SERVICE_SECRET;
    else process.env.INTERNAL_SERVICE_SECRET = priorSecret;
    for (const name of CAP_ENV_VARS) {
      const prior = priorCapEnv.get(name);
      if (prior === undefined) delete process.env[name];
      else process.env[name] = prior;
    }
  });

  it('requires authenticated access', async () => {
    const response = await request(app).get('/api/selection/metric-explanations');

    expect(response.status).toBe(401);
  });

  it('returns the authoritative comparison metric contract', async () => {
    const response = await request(app)
      .get('/api/selection/metric-explanations')
      .set('X-Internal-Service', 'metric-test-secret')
      .set('X-User-ID', 'owner-1');

    expect(response.status).toBe(200);
    expect(response.headers['cache-control']).toBe('private, no-store');
    expect(response.body.schemaVersion).toBe(1);
    expect(response.body.metrics.map((metric: { key: string }) => metric.key)).toEqual([
      'research_score',
      'market_fit',
      'technical_feasibility',
      'distribution_seo',
      'originality',
      'build_estimate',
      'evidence_anchor',
      'audience',
      'distinctive_wedge',
      'known_concern',
    ]);
    expect(response.body.metrics[0]).toMatchObject({
      range: '0-100',
      sourceFields: expect.arrayContaining(['adjusted_composite_score', 'winning_angle']),
    });
    expect(response.body.metrics.find((metric: { key: string }) => metric.key === 'technical_feasibility').method)
      .toContain('does not overwrite it');
    expect(response.body.metrics.find((metric: { key: string }) => metric.key === 'distribution_seo').method)
      .not.toContain('hand-seeded');
    expect(response.body.metrics.find((metric: { key: string }) => metric.key === 'originality').method)
      .toContain('Research score always uses novelty_score');
    expect(response.body.metrics.find((metric: { key: string }) => metric.key === 'research_score').caveat)
      .toContain('missing field contributes zero');
  });

  it('serves the Python-default cap thresholds when no env override is set', async () => {
    const response = await request(app)
      .get('/api/selection/metric-explanations')
      .set('X-Internal-Service', 'metric-test-secret')
      .set('X-User-ID', 'owner-1');

    expect(response.status).toBe(200);
    expect(response.body.capThresholds).toEqual({
      payabilityLowThreshold: 0.35,
      payabilityMarketFitCap: 0.55,
      parityShippedMarketFitCap: 0.45,
      parityPartialMarketFitCap: 0.55,
      paritySubstituteMarketFitCap: 0.5,
      paritySubstituteWeakWalletCap: 0.35,
      parityBundledFreeCap: 0.4,
    });
  });

  it('serves env-overridden cap thresholds and ignores invalid values', async () => {
    process.env.PARITY_SHIPPED_MARKET_FIT_CAP = '0.6';
    process.env.PAYABILITY_LOW_THRESHOLD = '0.25';
    process.env.PAYABILITY_MARKET_FIT_CAP = 'not-a-number'; // invalid → default
    process.env.PARITY_BUNDLED_FREE_CAP = '1.5'; // out of [0,1] → default

    const response = await request(app)
      .get('/api/selection/metric-explanations')
      .set('X-Internal-Service', 'metric-test-secret')
      .set('X-User-ID', 'owner-1');

    expect(response.status).toBe(200);
    expect(response.body.capThresholds).toMatchObject({
      parityShippedMarketFitCap: 0.6,
      payabilityLowThreshold: 0.25,
      payabilityMarketFitCap: 0.55,
      parityBundledFreeCap: 0.4,
    });
  });
});
