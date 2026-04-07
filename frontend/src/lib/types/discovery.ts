/**
 * Types for materialized discovery evidence data.
 * Served by GET /api/jobs/:jobId/discovery-data after Phase 1 completes.
 */

export interface DiscoveryQuote {
  text: string;
  post_id: string;
  source_url: string;
  upvotes: number;
  subreddit: string;
}

export interface HeroQuote extends DiscoveryQuote {
  pain_point_title: string;
}

export interface AudienceSegment {
  segment_name: string;
  size_estimate: string;
  pain_point_alignment: string[];
  motivation_drivers: string[];
  expertise_level: string;
  budget_sensitivity: string;
  discovery_channels: string[];
}

export interface AudienceData {
  segments: AudienceSegment[];
  primary_target: string;
  prioritization_rationale: string;
  community_hubs: string[];
  common_vocabulary: string[];
  content_preferences: string;
  tools_currently_used: string[];
  frustrations_with_existing: string[];
}

export interface InfluencerTopPost {
  title: string;
  subreddit: string;
  score: number;
  url: string;
}

export interface InfluencerProfile {
  name: string;
  platform: string;
  relevance_score: number;
  content_focus: string;
  top_subreddits: string[];
  top_posts: InfluencerTopPost[];
}

export interface SocialPost {
  title: string;
  subreddit: string;
  score: number;
  num_comments: number;
  url: string;
  created_utc: string;
}

export interface DiscoveryMethodology {
  urls_searched: number;
  urls_relevant: number;
  filtering_rate: number;
  quality_tier: string;
  pain_point_quality_tier: string;
  pain_point_confidence: number;
  total_engagement?: number;
  avg_engagement?: number;
}

export interface DiscoveryData {
  methodology: DiscoveryMethodology;
  hero_quote: HeroQuote | null;
  quotes: Record<string, DiscoveryQuote[]>;
  audience: AudienceData | null;
  influencers: InfluencerProfile[];
  social_posts_sample: SocialPost[];
  subreddit_names: string[];
  data_attribution: string;
  discussion_trend?: { month: string; count: number }[];
  discussion_growth_pct?: number | null;
}
