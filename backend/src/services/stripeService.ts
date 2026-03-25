import Stripe from 'stripe';
import { CONFIG } from '../config.js';
import { prisma } from './db.js';
import { addCredits } from './creditService.js';

// Lazy Stripe initialization - only created when needed
let _stripe: Stripe | null = null;

function getStripe(): Stripe {
  if (!_stripe) {
    if (!CONFIG.stripe.secretKey) {
      throw new Error('STRIPE_SECRET_KEY is not configured');
    }
    _stripe = new Stripe(CONFIG.stripe.secretKey);
  }
  return _stripe;
}

export { getStripe as stripe };

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
 * Validate a return URL to prevent open redirect attacks.
 * Must be a relative path starting with / and resolving to our origin.
 */
function isValidReturnUrl(url: string): boolean {
  if (typeof url !== 'string') return false;
  if (!url.startsWith('/')) return false;
  if (url.startsWith('//')) return false;
  if (url.includes('://')) return false;
  if (url.includes('\\')) return false;
  if (url.length > 500) return false;
  try {
    const parsed = new URL(url, CONFIG.baseUrl);
    if (parsed.origin !== new URL(CONFIG.baseUrl).origin) return false;
  } catch {
    return false;
  }
  return true;
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

  // Handle the event
  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session;
      await handleCheckoutCompleted(session);
      break;
    }

    case 'checkout.session.expired': {
      // Session expired without payment - nothing to do
      console.log('Checkout session expired:', event.data.object.id);
      break;
    }

    default:
      console.log(`Unhandled event type: ${event.type}`);
  }

  return { received: true, event: event.type };
}

/**
 * Process a completed checkout session
 */
async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
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

  // Check if we already processed this session (idempotency)
  const existingTransaction = await prisma.creditTransaction.findFirst({
    where: {
      userId,
      description: { contains: session.id },
    },
  });

  if (existingTransaction) {
    console.log('Session already processed:', session.id);
    return;
  }

  // Add credits to user
  const description = `Purchased ${packageName} (${credits} credits) - Session: ${session.id}`;

  try {
    const result = await addCredits(userId, credits, description);
    console.log(
      `Credits added: userId=${userId}, credits=${credits}, transactionId=${result.transaction.id}`
    );
  } catch (error) {
    console.error('Failed to add credits:', error);
    throw error;
  }
}
