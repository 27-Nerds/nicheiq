/**
 * Parses raw stage artifacts into FindingItem[] for the findings stream.
 * Also provides cumulative stats aggregation.
 */

import type { FindingItem, FindingType } from '$lib/types/stageArtifacts';
import {
  isSearchDiscovery,
  isPainPoints,
  isAudience,
  isSeoStrategy,
  isMarketSizing,
  isPricing,
  isTrendAnalysis,
} from '$lib/types/stageArtifacts';

let findingIdCounter = 0;

function makeFinding(
  type: FindingType,
  stageNumber: number,
  title: string,
  opts?: Partial<Pick<FindingItem, 'detail' | 'value' | 'expandable' | 'expandedContent'>>,
): FindingItem {
  return {
    id: `finding-${stageNumber}-${type}-${findingIdCounter++}`,
    type,
    stageNumber,
    title,
    ...opts,
  };
}

/**
 * Transform all stage artifacts into a chronological list of findings.
 */
export function parseArtifactsToFindings(
  stageArtifacts: Record<number, Record<string, any>>,
): FindingItem[] {
  const items: FindingItem[] = [];

  // Stage 1: Niche
  const a1 = stageArtifacts[1];
  if (a1) {
    if (a1.niche_description) {
      items.push(makeFinding('milestone', 1, 'Niche Defined', {
        detail: a1.niche_description,
      }));
    }
  }

  // Stage 2: Communities
  const a2 = stageArtifacts[2];
  if (a2 && isSearchDiscovery(a2)) {
    const totalPosts = (a2.reddit_posts || 0) + (a2.twitter_threads || 0);
    if (totalPosts > 0) {
      items.push(makeFinding('community', 2, `${totalPosts} posts discovered`, {
        detail: `Across ${a2.subreddit_count || 0} communities`,
        value: totalPosts,
      }));
    }
    if (a2.subreddits?.length) {
      for (const sub of a2.subreddits.slice(0, 5)) {
        items.push(makeFinding('community', 2, sub, {
          detail: 'Active community',
        }));
      }
    }
  }

  // Stage 3: Pain Points
  const a3 = stageArtifacts[3];
  if (a3 && isPainPoints(a3)) {
    for (const pp of a3.top || []) {
      items.push(makeFinding('pain_point', 3, pp.title, {
        value: `${(pp.severity * 10).toFixed(0)}/10`,
        detail: `Severity: ${(pp.severity * 10).toFixed(1)}/10`,
        expandable: true,
      }));
    }
  }

  // Stage 4: Audience
  const a4 = stageArtifacts[4];
  if (a4 && isAudience(a4)) {
    if (a4.primary_target) {
      items.push(makeFinding('audience', 4, a4.primary_target, {
        detail: a4.segment_count ? `${a4.segment_count} audience segments` : undefined,
      }));
    }
  }

  // Stage 5: Solutions
  const a5 = stageArtifacts[5];
  if (a5) {
    const solutions = a5.solutions || [];
    for (const sol of solutions.slice(0, 5)) {
      items.push(makeFinding('solution', 5, sol.name, {
        detail: sol.description,
        expandable: !!sol.description,
        expandedContent: sol.description,
      }));
    }
  }

  // Stage 6: SEO/Keywords
  const a6 = stageArtifacts[6];
  if (a6 && isSeoStrategy(a6)) {
    if (a6.total_volume) {
      const fmt = a6.total_volume >= 1000
        ? `${(a6.total_volume / 1000).toFixed(1)}K`
        : String(a6.total_volume);
      items.push(makeFinding('keyword', 6, `${fmt}/mo search volume`, {
        detail: `${a6.validated_keywords || 0} validated keywords in ${a6.cluster_count || 0} clusters`,
        value: a6.total_volume,
      }));
    }
    if (a6.top_clusters?.length) {
      for (const cluster of a6.top_clusters.slice(0, 4)) {
        items.push(makeFinding('keyword', 6, cluster, {
          detail: 'Topic cluster',
        }));
      }
    }
  }

  // Stage 7: Pricing
  const a7 = stageArtifacts[7];
  if (a7 && isPricing(a7)) {
    if (a7.starter_price && a7.pro_price) {
      items.push(makeFinding('market', 7, `${a7.starter_price}–${a7.pro_price}`, {
        detail: a7.pricing_model ? `Model: ${a7.pricing_model}` : 'Price range identified',
      }));
    }
  }

  // Stage 9: Market Sizing
  const a9 = stageArtifacts[9];
  if (a9 && isMarketSizing(a9)) {
    if (a9.som_y1) {
      items.push(makeFinding('market', 9, `SOM Y1: ${a9.som_y1}`, {
        detail: a9.tam ? `TAM: ${a9.tam}` : undefined,
        value: a9.som_y1,
      }));
    }
    if (a9.viability) {
      items.push(makeFinding('market', 9, `${a9.viability} viability`, {
        detail: a9.growth_rate ? `Growth: ${a9.growth_rate}` : undefined,
      }));
    }
  }

  // Stage 11: Trends
  const a11 = stageArtifacts[11];
  if (a11 && isTrendAnalysis(a11)) {
    const parts: string[] = [];
    if (a11.trend_direction) parts.push(a11.trend_direction);
    if (a11.timing_recommendation) parts.push(a11.timing_recommendation);
    if (parts.length) {
      items.push(makeFinding('market', 11, parts.join(' — '), {
        detail: a11.longevity_verdict ? `Longevity: ${a11.longevity_verdict}` : undefined,
      }));
    }
  }

  return items;
}

/**
 * Cumulative stats derived from stage artifacts.
 */
export interface CumulativeStat {
  label: string;
  value: number | null;
  iconName: string;
}

export function computeCumulativeStats(
  stageArtifacts: Record<number, Record<string, any>>,
): CumulativeStat[] {
  const a2 = stageArtifacts[2];
  const a3 = stageArtifacts[3];
  const a6 = stageArtifacts[6];

  const totalPosts = a2 ? (a2.reddit_posts || 0) + (a2.twitter_threads || 0) : null;
  const painCount = a3?.count ?? a3?.top?.length ?? null;
  const keywordCount = a6?.validated_keywords ?? null;

  return [
    { label: 'Posts', value: totalPosts, iconName: 'MessageCircle' },
    { label: 'Pain Points', value: painCount, iconName: 'Flame' },
    { label: 'Keywords', value: keywordCount, iconName: 'TrendingUp' },
  ];
}
