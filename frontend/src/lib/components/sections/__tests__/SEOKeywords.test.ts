import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import SEOKeywords from '../SEOKeywords.svelte';
import type { SEOStrategy, SEOAnalytics, Keyword } from '$lib/types/report';

// Helper to create mock keyword
function createMockKeyword(overrides: Partial<Keyword> = {}): Keyword {
  return {
    keyword: 'test keyword',
    search_volume: 1000,
    competition: 'medium',
    opportunity_score: 75,
    strategy: 'Content marketing',
    intent: 'informational',
    tier: 0,
    tier_rationale: 'High volume, low competition',
    ...overrides,
  };
}

// Helper to create mock SEO strategy
function createMockStrategy(overrides: Partial<SEOStrategy> = {}): SEOStrategy {
  return {
    total_keywords_analyzed: 50,
    total_monthly_volume: 100000,
    tier_0_keywords: [
      createMockKeyword({ keyword: 'premium keyword 1', tier: 0 }),
      createMockKeyword({ keyword: 'premium keyword 2', tier: 0 }),
    ],
    tier_1_keywords: [
      createMockKeyword({ keyword: 'quick win 1', tier: 1 }),
      createMockKeyword({ keyword: 'quick win 2', tier: 1 }),
    ],
    tier_2_keywords: [
      createMockKeyword({ keyword: 'high value 1', tier: 2 }),
    ],
    key_findings: ['Test findings'],
    ...overrides,
  };
}

// Helper to create mock SEO analytics
function createMockAnalytics(overrides: Partial<SEOAnalytics> = {}): SEOAnalytics {
  return {
    tier0_count: 2,
    tier1_count: 2,
    tier2_count: 1,
    tier3_count: 0,
    tier4_count: 0,
    total_keywords: 5,
    total_search_volume: 100000,
    avg_competition: 45,
    keyword_diversity_score: 0.8,
    high_volume_keywords: 3,
    ...overrides,
  };
}

describe('SEOKeywords Component', () => {
  describe('Limited Keywords Warning', () => {
    it('does not show warning when both tier_0 and tier_1 keywords are present', () => {
      const strategy = createMockStrategy();
      const analytics = createMockAnalytics();

      render(SEOKeywords, { props: { strategy, analytics } });

      // Warning should NOT be present
      expect(screen.queryByText('Limited Keyword Data')).not.toBeInTheDocument();
    });

    it('shows warning when tier_0_keywords is empty', () => {
      const strategy = createMockStrategy({
        tier_0_keywords: [],
      });
      const analytics = createMockAnalytics({
        tier0_count: 0,
      });

      render(SEOKeywords, { props: { strategy, analytics } });

      // Warning should be present
      expect(screen.getByText('Limited Keyword Data')).toBeInTheDocument();
      expect(
        screen.getByText(/Not enough high-opportunity keywords were found/)
      ).toBeInTheDocument();
    });

    it('shows warning when tier_1_keywords is empty', () => {
      const strategy = createMockStrategy({
        tier_1_keywords: [],
      });
      const analytics = createMockAnalytics({
        tier1_count: 0,
      });

      render(SEOKeywords, { props: { strategy, analytics } });

      // Warning should be present
      expect(screen.getByText('Limited Keyword Data')).toBeInTheDocument();
    });

    it('shows warning when both tier_0 and tier_1 keywords are empty', () => {
      const strategy = createMockStrategy({
        tier_0_keywords: [],
        tier_1_keywords: [],
      });
      const analytics = createMockAnalytics({
        tier0_count: 0,
        tier1_count: 0,
      });

      render(SEOKeywords, { props: { strategy, analytics } });

      // Warning should be present
      expect(screen.getByText('Limited Keyword Data')).toBeInTheDocument();
    });

    it('shows warning when tier_0_keywords is undefined', () => {
      const strategy = createMockStrategy();
      // @ts-expect-error - testing undefined case
      strategy.tier_0_keywords = undefined;

      const analytics = createMockAnalytics({
        tier0_count: 0,
      });

      render(SEOKeywords, { props: { strategy, analytics } });

      // Warning should be present
      expect(screen.getByText('Limited Keyword Data')).toBeInTheDocument();
    });

    it('shows warning when tier_1_keywords is undefined', () => {
      const strategy = createMockStrategy();
      // @ts-expect-error - testing undefined case
      strategy.tier_1_keywords = undefined;

      const analytics = createMockAnalytics({
        tier1_count: 0,
      });

      render(SEOKeywords, { props: { strategy, analytics } });

      // Warning should be present
      expect(screen.getByText('Limited Keyword Data')).toBeInTheDocument();
    });
  });

  describe('Basic Rendering', () => {
    it('renders section header', () => {
      const strategy = createMockStrategy();
      const analytics = createMockAnalytics();

      render(SEOKeywords, { props: { strategy, analytics } });

      expect(screen.getByText('SEO Strategy & Keywords')).toBeInTheDocument();
    });

    it('renders hero metrics', () => {
      const strategy = createMockStrategy();
      const analytics = createMockAnalytics({
        total_keywords: 50,
        total_search_volume: 100000,
      });

      render(SEOKeywords, { props: { strategy, analytics } });

      expect(screen.getByText('Keywords')).toBeInTheDocument();
      expect(screen.getByText('Category reach')).toBeInTheDocument();
    });

    it('renders key findings when present', () => {
      const strategy = createMockStrategy({
        key_findings: ['This niche has strong SEO potential'],
      });
      const analytics = createMockAnalytics();

      render(SEOKeywords, { props: { strategy, analytics } });

      expect(screen.getByText('Key Findings')).toBeInTheDocument();
      expect(screen.getByText('This niche has strong SEO potential')).toBeInTheDocument();
    });

    it('leads with idea-intent volume and demotes the aggregate to category reach', () => {
      const strategy = createMockStrategy({
        total_monthly_volume: 2264020,
        idea_intent_monthly_volume: 5230,
        offtopic_volume_share: 0.5182,
        category_volume_share: 0.4795,
      });
      const analytics = createMockAnalytics({ total_search_volume: 2264020 });

      render(SEOKeywords, { props: { strategy, analytics } });

      expect(screen.getByText('Idea-intent vol')).toBeInTheDocument();
      expect(screen.getByText('5.2K')).toBeInTheDocument();
      expect(screen.getByText('Category reach')).toBeInTheDocument();
      expect(screen.queryByText('Monthly Vol')).not.toBeInTheDocument();
      expect(
        screen.getByText(/52% of that volume is off-topic, 48% is broader category terms/)
      ).toBeInTheDocument();
    });

    it('relabels the aggregate as category reach when idea-intent volume is missing', () => {
      const strategy = createMockStrategy({ total_monthly_volume: 2264020 });
      const analytics = createMockAnalytics({ total_search_volume: 2264020 });

      render(SEOKeywords, { props: { strategy, analytics } });

      expect(screen.queryByText('Idea-intent vol')).not.toBeInTheDocument();
      expect(screen.getByText('Category reach')).toBeInTheDocument();
      expect(
        screen.getByText(/Treat it as category reach, not validated idea demand/)
      ).toBeInTheDocument();
    });

    it('renders keyword preview section', () => {
      const strategy = createMockStrategy();
      const analytics = createMockAnalytics();

      render(SEOKeywords, { props: { strategy, analytics } });

      expect(screen.getByText('Top Keywords by Tier')).toBeInTheDocument();
    });
  });
});
