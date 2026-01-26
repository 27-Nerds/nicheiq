import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Mock stripeService
// ============================================
const mockHandleWebhookEvent = vi.fn();

vi.mock('../../services/stripeService.js', () => ({
  handleWebhookEvent: mockHandleWebhookEvent,
}));

// ============================================
// Setup Express App
// ============================================
let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();

  app = express();

  // Webhook route needs raw body parsing
  const { webhooksRouter } = await import('../webhooks.js');
  app.use('/api/webhooks', express.raw({ type: 'application/json' }), webhooksRouter);
});

// ============================================
// T9: POST /api/webhooks/stripe tests
// ============================================
describe('POST /api/webhooks/stripe', () => {
  const validPayload = JSON.stringify({ type: 'checkout.session.completed' });
  const validSignature = 'valid-stripe-signature';

  it('returns 200 on valid webhook event', async () => {
    mockHandleWebhookEvent.mockResolvedValue({
      received: true,
      event: 'checkout.session.completed',
    });

    const response = await request(app)
      .post('/api/webhooks/stripe')
      .set('Content-Type', 'application/json')
      .set('stripe-signature', validSignature)
      .send(validPayload);

    expect(response.status).toBe(200);
    expect(response.body.received).toBe(true);
    expect(response.body.event).toBe('checkout.session.completed');
  });

  it('returns 400 when stripe-signature header missing', async () => {
    const response = await request(app)
      .post('/api/webhooks/stripe')
      .set('Content-Type', 'application/json')
      .send(validPayload);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Missing stripe-signature header');
    expect(mockHandleWebhookEvent).not.toHaveBeenCalled();
  });

  it('returns 400 on invalid signature', async () => {
    mockHandleWebhookEvent.mockRejectedValue(
      new Error('Webhook signature verification failed: Invalid signature')
    );

    const response = await request(app)
      .post('/api/webhooks/stripe')
      .set('Content-Type', 'application/json')
      .set('stripe-signature', 'invalid-signature')
      .send(validPayload);

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('signature verification failed');
  });

  it('passes raw buffer to handleWebhookEvent', async () => {
    mockHandleWebhookEvent.mockResolvedValue({ received: true });

    await request(app)
      .post('/api/webhooks/stripe')
      .set('Content-Type', 'application/json')
      .set('stripe-signature', validSignature)
      .send(validPayload);

    expect(mockHandleWebhookEvent).toHaveBeenCalledWith(
      expect.any(Buffer),
      validSignature
    );

    // Verify the buffer contains the payload
    const [payloadArg] = mockHandleWebhookEvent.mock.calls[0];
    expect(payloadArg.toString()).toBe(validPayload);
  });

  it('handles service error', async () => {
    mockHandleWebhookEvent.mockRejectedValue(new Error('Database error'));

    const response = await request(app)
      .post('/api/webhooks/stripe')
      .set('Content-Type', 'application/json')
      .set('stripe-signature', validSignature)
      .send(validPayload);

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('Database error');
  });

  it('handles checkout.session.expired event', async () => {
    mockHandleWebhookEvent.mockResolvedValue({
      received: true,
      event: 'checkout.session.expired',
    });

    const expiredPayload = JSON.stringify({ type: 'checkout.session.expired' });

    const response = await request(app)
      .post('/api/webhooks/stripe')
      .set('Content-Type', 'application/json')
      .set('stripe-signature', validSignature)
      .send(expiredPayload);

    expect(response.status).toBe(200);
    expect(response.body.event).toBe('checkout.session.expired');
  });
});
