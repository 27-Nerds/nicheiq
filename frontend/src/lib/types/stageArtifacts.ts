/**
 * Discriminated union types for each stage's artifact shape.
 * Used to safely access artifact data from stage progress updates.
 */

// Stage 1: Niche Analysis
export interface NicheAnalysisArtifact {
  type: 'niche_analysis';
  niche_description?: string;
  market_segments?: string[];
  problem_space?: string;
}

// Stage 2: Search & Discovery
export interface SearchDiscoveryArtifact {
  type: 'search_discovery';
  reddit_posts: number;
  twitter_threads?: number;
  subreddit_count: number;
  quality_tier?: string;
  subreddits?: string[];
}

// Stage 3: Pain Point Extraction
export interface PainPointsArtifact {
  type: 'pain_points';
  count: number;
  top: Array<{ title: string; severity: number }>;
}

// Stage 4: Audience Analysis
export interface AudienceArtifact {
  type: 'audience';
  primary_target?: string;
  segment_count?: number;
  community_hubs?: string[];
}

// Stage 5: Solution Ideation (pre-selection)
export interface SolutionIdeationArtifact {
  type: 'solution_ideation';
  solution_count?: number;
  solutions?: Array<{ name: string; description?: string }>;
}

// Stage 6: SEO Strategy
export interface SeoStrategyArtifact {
  type: 'seo_strategy';
  total_volume?: number;
  validated_keywords?: number;
  cluster_count?: number;
  avg_difficulty?: number;
  demand_signal?: string;
  top_clusters?: string[];
  winner_name?: string;
}

// Stage 7: Pricing
export interface PricingArtifact {
  type: 'pricing';
  pricing_model?: string;
  starter_price?: string;
  pro_price?: string;
  arpu?: string;
  confidence?: string;
}

// Stage 9: Market Sizing
export interface MarketSizingArtifact {
  type: 'market_sizing';
  tam?: string;
  sam?: string;
  som_y1?: string;
  viability?: string;
  growth_rate?: string;
  monetization?: {
    model?: string;
    monthly_revenue_range?: string;
  };
}

// Stage 11: Trend Analysis
export interface TrendAnalysisArtifact {
  type: 'trend_analysis';
  trend_direction?: string;
  market_maturity?: string;
  momentum_score?: number;
  timing_recommendation?: string;
  longevity_verdict?: string;
}

export type StageArtifact =
  | NicheAnalysisArtifact
  | SearchDiscoveryArtifact
  | PainPointsArtifact
  | AudienceArtifact
  | SolutionIdeationArtifact
  | SeoStrategyArtifact
  | PricingArtifact
  | MarketSizingArtifact
  | TrendAnalysisArtifact;

// --- Findings stream item types ---

export type FindingType =
  | 'pain_point'
  | 'community'
  | 'audience'
  | 'solution'
  | 'keyword'
  | 'market'
  | 'milestone';

export interface FindingItem {
  id: string;
  type: FindingType;
  title: string;
  detail?: string;
  value?: string | number;
  stageNumber: number;
  expandable?: boolean;
  expandedContent?: string;
}

// --- Runtime type guards ---

export function isSearchDiscovery(a: Record<string, any>): a is SearchDiscoveryArtifact {
  return typeof a.reddit_posts === 'number' || typeof a.subreddit_count === 'number';
}

export function isPainPoints(a: Record<string, any>): a is PainPointsArtifact {
  return Array.isArray(a.top) && typeof a.count === 'number';
}

export function isAudience(a: Record<string, any>): a is AudienceArtifact {
  return 'primary_target' in a || 'segment_count' in a;
}

export function isSeoStrategy(a: Record<string, any>): a is SeoStrategyArtifact {
  return 'total_volume' in a || 'validated_keywords' in a || 'demand_signal' in a;
}

export function isMarketSizing(a: Record<string, any>): a is MarketSizingArtifact {
  return 'tam' in a || 'sam' in a || 'som_y1' in a;
}

export function isTrendAnalysis(a: Record<string, any>): a is TrendAnalysisArtifact {
  return 'trend_direction' in a || 'momentum_score' in a || 'longevity_verdict' in a;
}

export function isPricing(a: Record<string, any>): a is PricingArtifact {
  return 'pricing_model' in a || 'starter_price' in a || 'arpu' in a;
}
