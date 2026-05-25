export interface FeatureItem {
  text: string;
  icon?: 'check' | 'plus' | 'star';
  highlight?: boolean;
}

export interface TokenPackage {
  id: string;
  name: string;
  description: string | null;
  credits: number;
  priceInCents: number;
  isPopular: boolean;
  tagline: string | null;
  includesLabel: string | null;
  creditsInfo: string | null;
  features: FeatureItem[] | null;
  ctaText: string | null;
  badgeLabel: string | null;
  promoLine: string | null;
  promoPriceInCents: number | null;
  promoBadge: string | null;
  ctaSubText: string | null;
  ctaSubUrl: string | null;
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  description: string | null;
  monthlyCredits: number;
  priceInCents: number;
  interval: 'month';
  trialDays: number | null;
  isPopular: boolean;
  tagline: string | null;
  includesLabel: string | null;
  creditsInfo: string | null;
  features: FeatureItem[] | null;
  ctaText: string | null;
  badgeLabel: string | null;
  promoLine: string | null;
  promoPriceInCents: number | null;
  promoBadge: string | null;
  ctaSubText: string | null;
  ctaSubUrl: string | null;
}

export type SubscriptionStatus =
  | 'ACTIVE'
  | 'TRIALING'
  | 'PAST_DUE'
  | 'CANCELED'
  | 'INCOMPLETE'
  | 'INCOMPLETE_EXPIRED'
  | 'UNPAID'
  | 'PAUSED';

export interface UserSubscription {
  status: SubscriptionStatus;
  planId: string | null;
  planName: string | null;
  monthlyCredits: number;
  interval: string;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  canceledAt: string | null;
}

export interface BalanceBreakdown {
  available: number;
  monthlyAllowance: number;
  purchasedBalance: number;
  monthlyAllowancePeriodEnd: string | null;
}
