/**
 * GA4 conversion tracking.
 *
 * GA4 only loads after the visitor accepts analytics cookies (see
 * Analytics.svelte), so events fired before that are queued and flushed on
 * consent. If consent is declined the queue is simply never flushed.
 *
 * Event names are the ones configured as conversions in GA4 / Google Ads:
 *   - "Signup" + "sign_up" — account created (credentials or OAuth)
 *   - "purchase"           — any completed Stripe checkout (package or subscription)
 *
 * Signup is emitted under both names: "sign_up" is the GA4 recommended name
 * (so built-in reporting picks it up), "Signup" is the name the Google Ads
 * conversion action was set up against. Import only ONE of the two into Google
 * Ads — importing both double-counts every signup.
 */
import { browser } from '$app/environment';

type Params = Record<string, unknown>;

let gaReady = false;
const queue: Array<{ name: string; params: Params }> = [];
const QUEUE_MAX = 20;

/** Captured at module load — before any component can strip the return params. */
const initialSearch = browser ? window.location.search : '';

export function trackEvent(name: string, params: Params = {}): void {
  if (!browser) return;
  if (gaReady && typeof window.gtag === 'function') {
    window.gtag('event', name, params);
    return;
  }
  if (queue.length < QUEUE_MAX) queue.push({ name, params });
}

/** Called by Analytics.svelte once gtag.js has loaded with consent granted. */
export function markAnalyticsReady(): void {
  gaReady = true;
  while (queue.length) {
    const e = queue.shift()!;
    window.gtag('event', e.name, e.params);
  }
}

// ── Signup ────────────────────────────────────────────────────────────────

const SIGNUP_SENT_KEY = 'ga_signup_sent';

/** Both signup event names, emitted together. See the file header. */
const SIGNUP_EVENT_NAMES = ['Signup', 'sign_up'] as const;

/**
 * Fire the signup events at most once per browser session. The OAuth path
 * re-reads the session flag on every navigation inside its freshness window,
 * so the guard is what keeps it to a single pair of events.
 */
export function trackSignup(method: string): void {
  if (!browser) return;
  try {
    if (sessionStorage.getItem(SIGNUP_SENT_KEY)) return;
    sessionStorage.setItem(SIGNUP_SENT_KEY, '1');
  } catch {
    // Private mode / storage disabled — fall through and fire anyway.
  }
  for (const name of SIGNUP_EVENT_NAMES) {
    trackEvent(name, { method });
  }
}

// ── Purchase ──────────────────────────────────────────────────────────────

const PENDING_KEY = 'ga_pending_purchase';
const SENT_KEY = 'ga_purchases_sent';
const SENT_MAX = 20;

interface PendingPurchase {
  id: string;
  name: string;
  value: number;
  currency: string;
  kind: 'package' | 'subscription';
}

interface PriceLike {
  id: string;
  name: string;
  priceInCents: number;
  promoPriceInCents?: number | null;
}

/**
 * Stash what the visitor is about to buy, immediately before redirecting to
 * Stripe. Read back by `flushPendingPurchase()` when Stripe returns them.
 * sessionStorage survives the round trip because it is the same tab + origin.
 */
export function stashPendingPurchase(
  item: PriceLike,
  kind: 'package' | 'subscription',
): void {
  if (!browser) return;
  const cents = item.promoPriceInCents ?? item.priceInCents;
  const pending: PendingPurchase = {
    id: item.id,
    name: item.name,
    value: cents / 100,
    currency: 'USD',
    kind,
  };
  try {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch {
    // Nothing to do — the purchase still fires, just without a value.
  }
}

function readPending(): PendingPurchase | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingPurchase;
    return typeof parsed?.value === 'number' ? parsed : null;
  } catch {
    return null;
  }
}

/** Stripe session ids already reported, so a reload can't double-count. */
function alreadySent(sessionId: string): boolean {
  try {
    const sent = JSON.parse(localStorage.getItem(SENT_KEY) || '[]') as string[];
    if (sent.includes(sessionId)) return true;
    sent.push(sessionId);
    localStorage.setItem(SENT_KEY, JSON.stringify(sent.slice(-SENT_MAX)));
    return false;
  } catch {
    return false;
  }
}

/**
 * Fire "purchase" if this page load is a return from a completed Stripe
 * checkout. Covers all three success params the backend redirects to:
 * `success` (/billing package), `sub_success` (/billing subscription), and
 * `credits_added` (catalog top-up).
 */
export function flushPendingPurchase(): void {
  if (!browser) return;

  const params = new URLSearchParams(initialSearch);
  const succeeded =
    params.get('success') === 'true' ||
    params.get('sub_success') === 'true' ||
    params.get('credits_added') === 'true';
  if (!succeeded) return;

  const sessionId = params.get('session_id');
  if (!sessionId || alreadySent(sessionId)) return;

  const pending = readPending();
  try {
    sessionStorage.removeItem(PENDING_KEY);
  } catch {
    // ignore
  }

  trackEvent('purchase', {
    transaction_id: sessionId,
    currency: pending?.currency ?? 'USD',
    value: pending?.value ?? 0,
    items: pending
      ? [
          {
            item_id: pending.id,
            item_name: pending.name,
            item_category: pending.kind,
            price: pending.value,
            quantity: 1,
          },
        ]
      : [],
  });
}
