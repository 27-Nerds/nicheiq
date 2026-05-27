import Stripe from 'stripe';
import { Prisma, CreditTransactionType } from '@prisma/client';
import { CONFIG } from '../config.js';
import { prisma } from './db.js';
import { addCredits } from './creditService.js';
import { getStripe } from './stripeClient.js';
import { isValidReturnUrl } from '../utils/returnUrl.js';
import {
  handleSubscriptionCheckoutCompleted,
  upsertSubscriptionFromStripe,
  handleSubscriptionDeleted,
  handleInvoicePaid,
  handleInvoicePaymentFailed,
} from './subscriptionService.js';

/**
 * Get all active token packages
 */
export async function getPackages() {
  return prisma.tokenPackage.findMany({
    where: { isActive: true },
    orderBy: { sortOrder: 'asc' },
    select: {
      id: true,
      name: true,
      description: true,
      credits: true,
      priceInCents: true,
      isPopular: true,
      tagline: true,
      includesLabel: true,
      creditsInfo: true,
      features: true,
      ctaText: true,
      badgeLabel: true,
      promoLine: true,
      promoPriceInCents: true,
      promoBadge: true,
      ctaSubText: true,
      ctaSubUrl: true,
    },
  });
}

/**
 * Get a single package by ID
 */
export async function getPackageById(packageId: string) {
  return prisma.tokenPackage.findUnique({
    where: { id: packageId },
  });
}

/**
 * Create a Stripe Checkout Session for purchasing credits.
 * If a valid returnUrl is provided, Stripe redirects back to that page
 * instead of /billing (used by the credit top-up modal).
 */
export async function createCheckoutSession(
  userId: string,
  userEmail: string,
  packageId: string,
  returnUrl?: string
): Promise<{ url: string }> {
  // Get the package
  const pkg = await prisma.tokenPackage.findUnique({
    where: { id: packageId },
  });

  if (!pkg) {
    throw new Error('Package not found');
  }

  if (!pkg.isActive) {
    throw new Error('Package is no longer available');
  }

  // Build return URLs — use returnUrl if valid, otherwise default to /billing
  let successUrl: string;
  let cancelUrl: string;

  if (returnUrl && isValidReturnUrl(returnUrl)) {
    const sep = returnUrl.includes('?') ? '&' : '?';
    successUrl = `${CONFIG.baseUrl}${returnUrl}${sep}credits_added=true&session_id={CHECKOUT_SESSION_ID}`;
    cancelUrl = `${CONFIG.baseUrl}${returnUrl}${sep}checkout_canceled=true`;
  } else {
    successUrl = `${CONFIG.baseUrl}/billing?success=true&session_id={CHECKOUT_SESSION_ID}`;
    cancelUrl = `${CONFIG.baseUrl}/billing?canceled=true`;
  }

  // Create Stripe Checkout Session
  const session = await getStripe().checkout.sessions.create({
    mode: 'payment',
    payment_method_types: ['card'],
    customer_email: userEmail,
    client_reference_id: userId,
    line_items: [
      {
        price: pkg.stripePriceId,
        quantity: 1,
      },
    ],
    metadata: {
      userId,
      packageId: pkg.id,
      packageName: pkg.name,
      credits: pkg.credits.toString(),
    },
    success_url: successUrl,
    cancel_url: cancelUrl,
  });

  if (!session.url) {
    throw new Error('Failed to create checkout session');
  }

  return { url: session.url };
}

/**
 * Handle Stripe webhook event
 */
export async function handleWebhookEvent(
  payload: Buffer,
  signature: string
): Promise<{ received: boolean; event?: string }> {
  let event: Stripe.Event;

  // Verify webhook signature
  try {
    event = getStripe().webhooks.constructEvent(
      payload,
      signature,
      CONFIG.stripe.webhookSecret
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    throw new Error(`Webhook signature verification failed: ${message}`);
  }

  // Durable idempotency: fast-skip if we've already fully processed this event. The row is
  // written only AFTER the handler succeeds (below), so a handler that throws is retried by
  // Stripe; the retry/concurrent window is safe because every handler is independently idempotent.
  const seen = await prisma.processedStripeEvent.findUnique({ where: { eventId: event.id } });
  if (seen) return { received: true, event: event.type };

  await routeWebhookEvent(event);

  try {
    await prisma.processedStripeEvent.create({ data: { eventId: event.id, type: event.type } });
  } catch (err) {
    // Concurrent delivery already recorded it — fine.
    if (!(err instanceof Prisma.PrismaClientKnownRequestError && err.code === 'P2002')) throw err;
  }

  return { received: true, event: event.type };
}

async function routeWebhookEvent(event: Stripe.Event): Promise<void> {
  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session;
      // Discriminate by mode — one-time top-ups keep the legacy path untouched.
      if (session.mode === 'subscription') {
        await handleSubscriptionCheckoutCompleted(session);
      } else {
        await handleCheckoutCompleted(session);
      }
      break;
    }

    case 'customer.subscription.created':
    case 'customer.subscription.updated':
      await upsertSubscriptionFromStripe(event.data.object as Stripe.Subscription);
      break;

    case 'customer.subscription.deleted':
      await handleSubscriptionDeleted(event.data.object as Stripe.Subscription);
      break;

    case 'invoice.paid':
      await handleInvoicePaid(event.data.object as Stripe.Invoice);
      break;

    case 'invoice.payment_failed':
    case 'invoice.payment_action_required':
      await handleInvoicePaymentFailed(event.data.object as Stripe.Invoice);
      break;

    case 'checkout.session.expired':
      console.log('Checkout session expired:', event.data.object.id);
      break;

    default:
      console.log(`Unhandled event type: ${event.type}`);
  }
}

/**
 * Process a completed checkout session
 */
async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  if (session.mode === 'subscription') return; // belt-and-suspenders; routed elsewhere

  const userId = session.client_reference_id;
  const metadata = session.metadata;

  if (!userId || !metadata) {
    console.error('Missing userId or metadata in checkout session:', session.id);
    return;
  }

  const credits = parseInt(metadata.credits, 10);
  const packageName = metadata.packageName;

  if (isNaN(credits) || credits <= 0) {
    console.error('Invalid credits in metadata:', metadata.credits);
    return;
  }

  // Idempotency is now durable: addCredits writes the unique stripeCheckoutSessionId and
  // catches P2002, so a re-delivered/concurrent event credits exactly once.
  const description = `Purchased ${packageName} (${credits} credits) - Session: ${session.id}`;
  try {
    const result = await addCredits(userId, credits, description, CreditTransactionType.PURCHASE, {
      stripeCheckoutSessionId: session.id,
    });
    console.log(
      `Credits added: userId=${userId}, credits=${credits}, transactionId=${result.transaction.id}`,
    );
  } catch (error) {
    console.error('Failed to add credits:', error);
    throw error;
  }
}
