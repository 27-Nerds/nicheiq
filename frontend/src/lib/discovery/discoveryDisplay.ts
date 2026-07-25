import type { DiscoveryData } from "$lib/types/discovery";
import type { PreviewReport } from "$lib/types/previewReport";
import type { DetailedPainPoint } from "$lib/types/report";
import type { SharedDiscoveryData, SharedPreviewReport } from "$lib/api";
import {
  finiteUnitScore,
  nonNegativeInteger,
  safeStringList,
} from "$lib/utils/displayGuards";

const DISCOVERY_SECTION_ORDER = [
  "overview",
  "market-snapshot",
  "pain-points",
  "audience",
  "community",
] as const;

function count(value: unknown): number {
  return nonNegativeInteger(value) ?? 0;
}

export function rankDiscoveryPainPoints(
  painPoints: readonly (Partial<DetailedPainPoint> & { title: string })[] | null | undefined,
): DetailedPainPoint[] {
  return (painPoints ?? [])
    .map((painPoint, index) => ({
      painPoint: {
        title: painPoint.title,
        description: painPoint.description ?? "",
        mention_count: count(painPoint.mention_count),
        severity_score: finiteUnitScore(painPoint.severity_score) ?? 0,
        commercial_intent: finiteUnitScore(painPoint.commercial_intent) ?? 0,
        opportunity_level: painPoint.opportunity_level ?? "low",
        representative_quotes: safeStringList(painPoint.representative_quotes),
        source_platforms: safeStringList(painPoint.source_platforms),
        categories: safeStringList(painPoint.categories),
        source_post_ids: safeStringList(painPoint.source_post_ids),
        affected_segments: safeStringList(painPoint.affected_segments),
        solution_approach: painPoint.solution_approach,
        opportunity_downgrade_reason: painPoint.opportunity_downgrade_reason,
      } satisfies DetailedPainPoint,
      index,
    }))
    .sort((a, b) => {
      const severityDelta =
        (Number.isFinite(b.painPoint.severity_score) ? b.painPoint.severity_score : 0)
        - (Number.isFinite(a.painPoint.severity_score) ? a.painPoint.severity_score : 0);
      return severityDelta || a.index - b.index;
    })
    .map(({ painPoint }) => painPoint);
}

export function discoveryDiscussionCount(
  previewReport: PreviewReport | SharedPreviewReport | null | undefined,
  discoveryData: DiscoveryData | SharedDiscoveryData | null | undefined,
): number {
  const metadata = previewReport?.research_metadata as Record<string, unknown> | null | undefined;
  const analyzed =
    count(metadata?.["reddit_posts_analyzed"])
    + count(metadata?.["twitter_threads_analyzed"])
    + count(metadata?.["generic_posts_analyzed"]);
  if (analyzed > 0) return analyzed;

  return count(discoveryData?.methodology?.urls_relevant)
    || count(
      (metadata?.["filtering_stats"] as Record<string, unknown> | null)?.["total_urls_relevant"],
    );
}

export function discoveryCommunityNames(
  discoveryData: DiscoveryData | SharedDiscoveryData | null | undefined,
  previewReport: PreviewReport | SharedPreviewReport | null | undefined,
): string[] {
  const candidates = [
    ...safeStringList(discoveryData?.subreddit_names),
    ...safeStringList(previewReport?.audience_mapping?.community_hubs),
  ];
  return [...new Set(candidates)];
}

export interface DiscoveryDisplayModel {
  discussionCount: number;
  painPoints: DetailedPainPoint[];
  painPointCount: number;
  segmentCount: number;
  communityNames: string[];
  totalEngagement: number;
  availableSectionIds: string[];
}

export function createDiscoveryDisplayModel(
  previewReport: PreviewReport | SharedPreviewReport | null | undefined,
  discoveryData: DiscoveryData | SharedDiscoveryData | null | undefined,
): DiscoveryDisplayModel {
  const painPoints = rankDiscoveryPainPoints(previewReport?.detailed_pain_points);
  const painPointCount =
    count(previewReport?.pain_point_analytics?.total_pain_points) || painPoints.length;
  const segmentCount = previewReport?.audience_mapping?.audience_segments?.length ?? 0;
  const communityNames = discoveryCommunityNames(discoveryData, previewReport);
  const available = new Set<string>();

  if (previewReport) available.add("overview");
  if (discoveryData?.discussion_trend?.length) available.add("market-snapshot");
  if (painPoints.length) available.add("pain-points");
  if (previewReport?.audience_mapping) available.add("audience");
  if (discoveryData || previewReport?.evidence_appendix) available.add("community");

  return {
    discussionCount: discoveryDiscussionCount(previewReport, discoveryData),
    painPoints,
    painPointCount,
    segmentCount,
    communityNames,
    totalEngagement: count(discoveryData?.methodology?.total_engagement),
    availableSectionIds: DISCOVERY_SECTION_ORDER.filter((section) => available.has(section)),
  };
}
