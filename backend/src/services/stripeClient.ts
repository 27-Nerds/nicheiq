import Stripe from 'stripe';
import { CONFIG } from '../config.js';

// Shared, lazily-initialized Stripe client.
//
// The apiVersion is PINNED. In the Clover/Basil era several fields moved off the
// objects we read in webhooks (subscription period → `sub.items.data[].current_period_*`;
// `invoice.subscription` → `invoice.parent.subscription_details.subscription`). Pinning
// the version here — and matching the webhook endpoint's version in the Stripe Dashboard —
// keeps those field paths stable instead of silently following the account default.
let _stripe: Stripe | null = null;

export function getStripe(): Stripe {
  if (!_stripe) {
    if (!CONFIG.stripe.secretKey) {
      throw new Error('STRIPE_SECRET_KEY is not configured');
    }
    _stripe = new Stripe(CONFIG.stripe.secretKey, { apiVersion: '2025-12-15.clover' });
  }
  return _stripe;
}
