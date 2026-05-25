-- CreateEnum
CREATE TYPE "SubscriptionStatus" AS ENUM ('ACTIVE', 'TRIALING', 'PAST_DUE', 'CANCELED', 'INCOMPLETE', 'INCOMPLETE_EXPIRED', 'UNPAID', 'PAUSED');

-- AlterEnum
ALTER TYPE "CreditTransactionType" ADD VALUE 'SUBSCRIPTION_GRANT';

-- AlterTable
ALTER TABLE "CreditTransaction" ADD COLUMN     "fromMonthly" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "monthlyPeriodStart" TIMESTAMP(3),
ADD COLUMN     "stripeCheckoutSessionId" VARCHAR(255),
ADD COLUMN     "stripeInvoiceId" VARCHAR(255);

-- AlterTable
ALTER TABLE "User" ADD COLUMN     "hasActiveSubscription" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "stripeCustomerId" VARCHAR(255);

-- AlterTable
ALTER TABLE "UserCredits" ADD COLUMN     "monthlyAllowance" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "monthlyAllowancePeriodEnd" TIMESTAMP(3),
ADD COLUMN     "monthlyAllowancePeriodStart" TIMESTAMP(3);

-- CreateTable
CREATE TABLE "SubscriptionPlan" (
    "id" TEXT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "description" VARCHAR(500),
    "monthlyCredits" INTEGER NOT NULL DEFAULT 0,
    "priceInCents" INTEGER NOT NULL,
    "interval" VARCHAR(20) NOT NULL DEFAULT 'month',
    "trialDays" INTEGER,
    "stripePriceId" VARCHAR(255) NOT NULL,
    "stripeProductId" VARCHAR(255),
    "stripeCouponId" VARCHAR(255),
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "isPopular" BOOLEAN NOT NULL DEFAULT false,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "tagline" VARCHAR(200),
    "includesLabel" VARCHAR(200),
    "features" JSONB,
    "creditsInfo" VARCHAR(200),
    "ctaText" VARCHAR(100),
    "badgeLabel" VARCHAR(50),
    "promoLine" VARCHAR(200),
    "promoPriceInCents" INTEGER,
    "promoBadge" VARCHAR(50),
    "ctaSubText" VARCHAR(100),
    "ctaSubUrl" VARCHAR(500),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SubscriptionPlan_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserSubscription" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "planId" TEXT,
    "stripeSubscriptionId" VARCHAR(255) NOT NULL,
    "stripeCustomerId" VARCHAR(255) NOT NULL,
    "stripePriceId" VARCHAR(255),
    "status" "SubscriptionStatus" NOT NULL,
    "currentPeriodStart" TIMESTAMP(3),
    "currentPeriodEnd" TIMESTAMP(3),
    "cancelAtPeriodEnd" BOOLEAN NOT NULL DEFAULT false,
    "canceledAt" TIMESTAMP(3),
    "stripeCreatedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "UserSubscription_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ProcessedStripeEvent" (
    "eventId" VARCHAR(255) NOT NULL,
    "type" VARCHAR(100) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ProcessedStripeEvent_pkey" PRIMARY KEY ("eventId")
);

-- CreateIndex
CREATE UNIQUE INDEX "SubscriptionPlan_stripePriceId_key" ON "SubscriptionPlan"("stripePriceId");

-- CreateIndex
CREATE INDEX "SubscriptionPlan_isActive_idx" ON "SubscriptionPlan"("isActive");

-- CreateIndex
CREATE INDEX "SubscriptionPlan_sortOrder_idx" ON "SubscriptionPlan"("sortOrder");

-- CreateIndex
CREATE UNIQUE INDEX "UserSubscription_userId_key" ON "UserSubscription"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "UserSubscription_stripeSubscriptionId_key" ON "UserSubscription"("stripeSubscriptionId");

-- CreateIndex
CREATE INDEX "UserSubscription_userId_idx" ON "UserSubscription"("userId");

-- CreateIndex
CREATE INDEX "UserSubscription_stripeCustomerId_idx" ON "UserSubscription"("stripeCustomerId");

-- CreateIndex
CREATE INDEX "UserSubscription_status_idx" ON "UserSubscription"("status");

-- CreateIndex
CREATE INDEX "UserSubscription_stripeSubscriptionId_idx" ON "UserSubscription"("stripeSubscriptionId");

-- CreateIndex
CREATE UNIQUE INDEX "CreditTransaction_stripeCheckoutSessionId_key" ON "CreditTransaction"("stripeCheckoutSessionId");

-- CreateIndex
CREATE UNIQUE INDEX "CreditTransaction_stripeInvoiceId_key" ON "CreditTransaction"("stripeInvoiceId");

-- CreateIndex
CREATE UNIQUE INDEX "User_stripeCustomerId_key" ON "User"("stripeCustomerId");

-- CreateIndex
CREATE INDEX "User_stripeCustomerId_idx" ON "User"("stripeCustomerId");

-- AddForeignKey
ALTER TABLE "UserSubscription" ADD CONSTRAINT "UserSubscription_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UserSubscription" ADD CONSTRAINT "UserSubscription_planId_fkey" FOREIGN KEY ("planId") REFERENCES "SubscriptionPlan"("id") ON DELETE SET NULL ON UPDATE CASCADE;


-- Backstop against concurrent-charge underflow on the monthly bucket (Prisma schema cannot express CHECK).
ALTER TABLE "UserCredits" ADD CONSTRAINT "UserCredits_monthlyAllowance_nonneg" CHECK ("monthlyAllowance" >= 0);
