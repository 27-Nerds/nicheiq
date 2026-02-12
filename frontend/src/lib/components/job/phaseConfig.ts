/**
 * Phase definitions, stage-to-phase mapping, narrative templates,
 * and celebration tier configuration.
 */

export type PhaseId = 'discovery' | 'analysis';
export type PhaseStatus = 'locked' | 'pending' | 'active' | 'completed' | 'failed';
export type CelebrationTier = 1 | 2 | 3;

export interface NarrativeTemplate {
  running: string;
  completed: (artifact: Record<string, any>) => string;
}

export interface PhaseDefinition {
  id: PhaseId;
  label: string;
  description: string;
  stageNumbers: number[];
  artifactStages: number[];
  narrativeTemplates: Record<number, NarrativeTemplate>;
}

export const PHASES: PhaseDefinition[] = [
  {
    id: 'discovery',
    label: 'Discovery',
    description: 'Scanning social discussions and extracting market signals',
    stageNumbers: [1, 2, 3, 4, 5],
    artifactStages: [1, 2, 3, 4],
    narrativeTemplates: {
      1: {
        running: 'Analyzing your niche and identifying market segments...',
        completed: (a) => {
          const segs = a.market_segments?.length;
          return segs
            ? `Identified ${segs} market segments`
            : 'Niche analysis complete';
        },
      },
      2: {
        running: 'Scanning communities for discussions...',
        completed: (a) => {
          const posts = (a.reddit_posts || 0) + (a.twitter_threads || 0);
          const subs = a.subreddit_count || 0;
          return posts
            ? `Found ${posts} posts across ${subs} communities`
            : 'Search complete';
        },
      },
      3: {
        running: 'Analyzing emotional intensity in posts...',
        completed: (a) => {
          const count = a.count || a.top?.length || 0;
          const maxSev = a.top?.[0]?.severity;
          return maxSev
            ? `${count} pain points extracted, severity up to ${(maxSev * 10).toFixed(1)}`
            : `${count} pain points extracted`;
        },
      },
      4: {
        running: 'Profiling target audience segments...',
        completed: (a) => {
          const target = a.primary_target;
          const segs = a.segment_count || 0;
          return target
            ? `Primary: ${target} (${segs} segments)`
            : `${segs} audience segments identified`;
        },
      },
      5: {
        running: 'Generating solution ideas from pain points...',
        completed: (a) => {
          const count = a.solution_count || a.solutions?.length || 0;
          return `${count} solution ideas generated`;
        },
      },
    },
  },
  {
    id: 'analysis',
    label: 'Deep Analysis',
    description: 'Validating demand, pricing, and market opportunity',
    stageNumbers: [5.5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    artifactStages: [6, 7, 9, 11],
    narrativeTemplates: {
      5.5: {
        running: 'Preparing selected solutions for deep analysis...',
        completed: () => 'Solutions locked in',
      },
      6: {
        running: 'Validating keyword volumes and SEO opportunity...',
        completed: (a) => {
          const vol = a.total_volume;
          const kw = a.validated_keywords || 0;
          if (vol) {
            const fmt = vol >= 1000 ? `${(vol / 1000).toFixed(1)}K` : String(vol);
            return `${fmt} monthly searches across ${kw} keywords`;
          }
          return `${kw} keywords validated`;
        },
      },
      7: {
        running: 'Researching competitor pricing strategies...',
        completed: (a) => {
          if (a.starter_price && a.pro_price) {
            return `Price range: ${a.starter_price}–${a.pro_price}`;
          }
          return a.pricing_model ? `Model: ${a.pricing_model}` : 'Pricing analysis complete';
        },
      },
      8: {
        running: 'Analyzing competitive landscape...',
        completed: () => 'Competitive analysis complete',
      },
      9: {
        running: 'Computing TAM/SAM/SOM...',
        completed: (a) => {
          if (a.som_y1) return `SOM Year 1: ${a.som_y1} estimated`;
          return 'Market sizing complete';
        },
      },
      10: {
        running: 'Evaluating technical feasibility...',
        completed: () => 'Technical feasibility assessed',
      },
      11: {
        running: 'Analyzing market trends and momentum...',
        completed: (a) => {
          const parts: string[] = [];
          if (a.trend_direction) parts.push(a.trend_direction);
          if (a.timing_recommendation) parts.push(a.timing_recommendation);
          return parts.length ? parts.join(' — ') : 'Trend analysis complete';
        },
      },
      12: {
        running: 'Building go-to-market strategy...',
        completed: () => 'GTM strategy ready',
      },
      13: {
        running: 'Compiling executive summary...',
        completed: () => 'Executive summary compiled',
      },
      14: {
        running: 'Assembling final research report...',
        completed: () => 'Report assembled',
      },
    },
  },
];

/** Stages that run in parallel and should be displayed as one row */
export const PARALLEL_STAGE_GROUPS: Record<
  number,
  { hide: number[]; combinedName: string }
> = {
  3: { hide: [4], combinedName: 'Pain Point & Audience Analysis' },
};

/** Celebration tier per stage — higher tier = bigger celebration */
export const CELEBRATION_TIERS: Record<number, CelebrationTier> = {
  1: 1,
  2: 2,   // search discovery — key data moment
  3: 2,   // pain points — key data moment
  4: 1,
  5: 3,   // phase milestone — discovery complete
  6: 2,   // SEO — key data moment
  7: 1,
  8: 1,
  9: 2,   // market sizing — key data moment
  10: 1,
  11: 2,  // trends — key data moment
  12: 1,
  13: 1,
  14: 3,  // phase milestone — report ready
};

/** Lookup phase for a given stage number */
export function getPhaseForStage(stageNumber: number): PhaseId | null {
  for (const phase of PHASES) {
    if (phase.stageNumbers.includes(stageNumber)) return phase.id;
  }
  return null;
}

/** Get narrative text for a stage based on its status and artifact */
export function getNarrativeText(
  stageNumber: number,
  status: string,
  artifact?: Record<string, any> | null,
): string | undefined {
  for (const phase of PHASES) {
    const tmpl = phase.narrativeTemplates[stageNumber];
    if (!tmpl) continue;
    if (status === 'RUNNING') return tmpl.running;
    if (status === 'COMPLETED' && artifact) {
      try {
        return tmpl.completed(artifact);
      } catch {
        return undefined;
      }
    }
  }
  return undefined;
}
