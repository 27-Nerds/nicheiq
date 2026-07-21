import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import express from 'express';
import request from 'supertest';
import { selectionMetricExplanationsRouter } from '../selectionMetricExplanations.js';

const app = express();
app.use('/api/selection', selectionMetricExplanationsRouter);

describe('selection metric explanations API', () => {
  const priorSecret = process.env.INTERNAL_SERVICE_SECRET;

  beforeEach(() => {
    process.env.INTERNAL_SERVICE_SECRET = 'metric-test-secret';
  });

  afterEach(() => {
    if (priorSecret === undefined) delete process.env.INTERNAL_SERVICE_SECRET;
    else process.env.INTERNAL_SERVICE_SECRET = priorSecret;
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
  });
});
