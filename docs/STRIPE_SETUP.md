# Stripe Setup Guide

Complete guide to setting up Stripe payments for NicheIQ.

## Prerequisites

- Stripe account (https://stripe.com)
- Access to your database (Prisma Studio or SQL client)

## 1. Get API Keys

1. Go to https://dashboard.stripe.com/apikeys
2. Copy your keys:
   - **Secret key**: `sk_test_...` (development) or `sk_live_...` (production)

3. Add to `.env`:
   ```bash
   STRIPE_SECRET_KEY=sk_test_...
   ```

> **Note:** We don't use the Publishable key since we use Stripe Checkout (redirect to Stripe's hosted page).

## 2. Create Products & Prices

1. Go to https://dashboard.stripe.com/test/products (use `/products` for live mode)

2. Click **"Add product"** for each token package:

   | Product Name | Price | Type |
   |--------------|-------|------|
   | Starter Pack | $5.00 | One-time |
   | Pro Pack | $15.00 | One-time |
   | Enterprise Pack | $50.00 | One-time |

3. For each product:
   - Enter name and description
   - Click **"Add pricing"**
   - Select **"One time"**
   - Enter the price
   - Click **"Add product"**

4. Copy the **Price ID** for each (starts with `price_...`)

**How to find the Price ID:**

The Price ID is different from the Product ID (`prod_...`). To find it:

1. Go to https://dashboard.stripe.com/test/products (or `/products` for live)
2. Click on a product name
3. In the **Pricing** section, find your price row (e.g., "$5.00 USD")
4. Click the **"..."** (three dots) on the right → **"Copy price ID"**

Or click on the price row - the Price ID appears in:
- The details panel on the right
- The URL: `https://dashboard.stripe.com/test/prices/price_1ABC123...`

> **Note:** Each product can have multiple prices. Make sure you copy the correct one (check amount and currency).

## 3. Update Database with Price IDs

Your `TokenPackage` table needs real Stripe Price IDs.

### Option A: Using Prisma Studio

```bash
cd backend
npm run db:studio
```

1. Open the `TokenPackage` table
2. Edit each row's `stripePriceId` field
3. Replace placeholder values with real Price IDs from Stripe

### Option B: Using SQL

```sql
-- Update each package with the real Stripe Price ID
UPDATE "TokenPackage" SET "stripePriceId" = 'price_1ABC...' WHERE name = 'Starter';
UPDATE "TokenPackage" SET "stripePriceId" = 'price_1DEF...' WHERE name = 'Pro';
UPDATE "TokenPackage" SET "stripePriceId" = 'price_1GHI...' WHERE name = 'Enterprise';
```

### Option C: Insert new packages

If you don't have packages yet:

```sql
INSERT INTO "TokenPackage" (id, name, description, credits, "priceInCents", "stripePriceId", "isActive", "isPopular", "sortOrder", "createdAt", "updatedAt")
VALUES
  (gen_random_uuid(), 'Starter', '10 research credits', 10, 500, 'price_YOUR_STARTER_ID', true, false, 1, NOW(), NOW()),
  (gen_random_uuid(), 'Pro', '50 research credits', 50, 1500, 'price_YOUR_PRO_ID', true, true, 2, NOW(), NOW()),
  (gen_random_uuid(), 'Enterprise', '200 research credits', 200, 5000, 'price_YOUR_ENTERPRISE_ID', true, false, 3, NOW(), NOW());
```

## 4. Set Up Webhooks

Webhooks notify your backend when payments complete.

### Production Setup

1. Go to https://dashboard.stripe.com/webhooks
2. Click **"Add endpoint"**
3. Enter your endpoint URL:
   ```
   https://yourdomain.com/api/webhooks/stripe
   ```
4. Select events to listen to:
   - `checkout.session.completed` (required)
   - `checkout.session.expired` (optional)
5. Click **"Add endpoint"**
6. Copy the **Signing secret** (`whsec_...`)
7. Add to `.env`:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

### Local Development Setup

Use Stripe CLI to forward webhooks to localhost:

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli

2. Login to Stripe:
   ```bash
   stripe login
   ```

3. Forward webhooks to your local server:
   ```bash
   stripe listen --forward-to localhost:3001/api/webhooks/stripe
   ```

4. Copy the webhook signing secret from the CLI output:
   ```
   Ready! Your webhook signing secret is whsec_... (^C to quit)
   ```

5. Add to `.env`:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

> **Note:** Keep the `stripe listen` command running while testing payments locally.

## 5. Webhook Events Reference

| Event | Handler | Purpose |
|-------|---------|---------|
| `checkout.session.completed` | `handleCheckoutCompleted()` | Adds credits to user account |
| `checkout.session.expired` | Logs only | Session expired without payment |

Events we **don't** handle (not needed for card payments):
- `checkout.session.async_payment_failed`
- `checkout.session.async_payment_succeeded`

These are for delayed payment methods (bank transfers, SEPA) which we don't use.

## 6. Test the Integration

### Test a purchase flow:

1. Start your backend:
   ```bash
   cd backend && npm run dev
   ```

2. Start Stripe CLI (in another terminal):
   ```bash
   stripe listen --forward-to localhost:3001/api/webhooks/stripe
   ```

3. Start your frontend:
   ```bash
   cd frontend && npm run dev
   ```

4. Go to the billing page and click a package

5. Use Stripe test card:
   - Card: `4242 4242 4242 4242`
   - Expiry: Any future date
   - CVC: Any 3 digits

6. Check the backend logs for webhook confirmation

### Verify credits were added:

```sql
SELECT * FROM "CreditTransaction" ORDER BY "createdAt" DESC LIMIT 5;
```

## 7. Go Live Checklist

Before switching to production:

- [ ] Replace `sk_test_...` with `sk_live_...` in production `.env`
- [ ] Create products/prices in live mode (not test mode)
- [ ] Update database with live Price IDs
- [ ] Create production webhook endpoint with live URL
- [ ] Update `STRIPE_WEBHOOK_SECRET` with live webhook secret
- [ ] Test a real purchase with a small amount

## Environment Variables Summary

```bash
# Required
STRIPE_SECRET_KEY=sk_test_...        # or sk_live_... for production
STRIPE_WEBHOOK_SECRET=whsec_...      # from webhook endpoint or Stripe CLI
```

## Troubleshooting

### "No such price: 'price_xxx'"

Your database has placeholder Price IDs. Update `TokenPackage.stripePriceId` with real Stripe Price IDs (see Section 3).

### Webhook signature verification failed

- Make sure `STRIPE_WEBHOOK_SECRET` matches your endpoint
- For local dev, use the secret from `stripe listen` output
- Don't mix test/live webhook secrets

### Credits not added after payment

1. Check backend logs for webhook errors
2. Verify `stripe listen` is running (local dev)
3. Check webhook endpoint is receiving events in Stripe Dashboard > Webhooks > Select endpoint > Recent events

### Checkout redirects to wrong URL

Check `BASE_URL` in `.env`:
```bash
BASE_URL=http://localhost:3000  # development
BASE_URL=https://yourdomain.com # production
```

## Additional Resources

- [Stripe Checkout Docs](https://stripe.com/docs/checkout)
- [Stripe CLI Docs](https://stripe.com/docs/stripe-cli)
- [Stripe Test Cards](https://stripe.com/docs/testing#cards)
- [Webhook Best Practices](https://stripe.com/docs/webhooks/best-practices)
