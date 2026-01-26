import { Router, Request, Response } from 'express';
import { handleWebhookEvent } from '../services/stripeService.js';

export const webhooksRouter = Router();

/**
 * POST /api/webhooks/stripe
 * Handle Stripe webhook events
 *
 * Note: This route uses raw body parsing (configured in index.ts)
 */
webhooksRouter.post('/stripe', async (req: Request, res: Response) => {
  const signature = req.headers['stripe-signature'];

  if (!signature || typeof signature !== 'string') {
    res.status(400).json({ error: 'Missing stripe-signature header' });
    return;
  }

  // req.body is the raw Buffer when using express.raw()
  const payload = req.body as Buffer;

  if (!Buffer.isBuffer(payload)) {
    res.status(400).json({ error: 'Invalid payload format' });
    return;
  }

  try {
    const result = await handleWebhookEvent(payload, signature);
    res.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('Webhook error:', message);
    res.status(400).json({ error: message });
  }
});
