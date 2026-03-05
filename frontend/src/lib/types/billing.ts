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
