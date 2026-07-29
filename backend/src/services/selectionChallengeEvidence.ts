import {
  SelectionChallengeSourceSchema,
  SelectionChallengeSubjectSchema,
  type SelectionChallengeLens,
  type SelectionChallengeSource,
  type SelectionChallengeSubject,
} from '../types/selectionChallenge.js';
import { ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';

const SUBJECT_FIELDS = [
  'solution_name',
  'headline',
  'description',
  'value_proposition',
  'source_pain',
  'source_segment',
  'target_personas',
  'core_features',
  'technical_approach',
  'project_type',
  'pricing_strategy',
  'competitor_analysis',
  'differentiation_factors',
  'programmatic_seo_opportunity',
  'data_acquisition_notes',
  'critic_concern',
  'red_team_caveats',
] as const;

type SourceInput = Omit<SelectionChallengeSource, 'key'>;

export interface SelectionChallengeOwnerEvidence {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: 'DEMAND' | 'COMPETITION' | 'DISTRIBUTION' | 'DEPENDENCIES';
  kind: 'NOTE' | 'CUSTOMER_QUOTE' | 'ANALYTICS_OBSERVATION' | 'LINK';
  position: 'SUPPORTS' | 'CONTRADICTS' | 'CONTEXT';
  title: string;
  content: string;
  sourceUrl: string | null;
  observedAt: Date | null;
  createdAt: Date;
  retractedAt: Date | null;
}

export interface SelectionChallengeExperimentResult {
  id: string;
  ideaId: string;
  ideaRevision: number;
  originChallengeId: string | null;
  originChallenge: {
    id: string;
    ideaId: string;
    ideaRevision: number;
    lens: 'DEMAND' | 'COMPETITION' | 'DISTRIBUTION' | 'DEPENDENCIES';
  } | null;
  conclusion: {
    id: string;
    createdAt: Date;
    snapshot: unknown;
  } | null;
}

function record(input: unknown): Record<string, unknown> {
  return input && typeof input === 'object' && !Array.isArray(input)
    ? input as Record<string, unknown>
    : {};
}

function array(input: unknown): unknown[] {
  return Array.isArray(input) ? input : [];
}

function text(input: unknown, max = 1_500): string {
  if (typeof input === 'string') return input.trim().slice(0, max);
  if (input == null) return '';
  if (typeof input === 'number' || typeof input === 'boolean') return String(input).slice(0, max);
  if (Array.isArray(input)) {
    return input
      .map(item => text(item, max))
      .filter(Boolean)
      .join(', ')
      .slice(0, max);
  }
  if (typeof input !== 'object') return '';

  return Object.entries(input)
    .flatMap(([key, value]) => {
      const readableValue = text(value, max);
      if (!readableValue) return [];
      const label = key
        .replace(/[_-]+/g, ' ')
        .replace(/^\w/, character => character.toUpperCase());
      return [`${label}: ${readableValue}`];
    })
    .join(' · ')
    .slice(0, max);
}

function httpUrl(input: unknown): string | null {
  if (typeof input !== 'string' || !/^https?:\/\//i.test(input)) return null;
  try {
    return new URL(input).toString();
  } catch {
    return null;
  }
}

function isoDate(input: unknown): string | null {
  if (typeof input !== 'string') return null;
  const parsed = new Date(input);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function normalizeLabel(input: unknown): string {
  return typeof input === 'string'
    ? input.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
    : '';
}

function hasValue(input: unknown): boolean {
  if (input == null) return false;
  if (typeof input === 'string') return input.trim().length > 0;
  if (Array.isArray(input)) return input.length > 0;
  if (typeof input === 'object') return Object.keys(input as Record<string, unknown>).length > 0;
  return true;
}

function ownerEvidenceSources(
  rows: SelectionChallengeOwnerEvidence[],
  lens: SelectionChallengeLens,
  idea: IdeaRecord,
): SourceInput[] {
  return rows
    .filter(row =>
      !row.retractedAt
      && row.ideaId === String(idea.idea_id)
      && row.ideaRevision === Number(idea.idea_revision)
      && row.lens.toLowerCase() === lens
    )
    .map(row => ({
      kind: 'owner_evidence' as const,
      title: `Owner-provided: ${row.title}`,
      excerpt: text(row.content),
      url: httpUrl(row.sourceUrl),
      capturedAt: (row.observedAt ?? row.createdAt).toISOString(),
      provenance: {
        assetType: 'OWNER_EVIDENCE' as const,
        evidenceItemId: row.id,
        position: row.position,
        ownerKind: row.kind,
      },
    }));
}

function experimentMetric(input: unknown) {
  const metric = record(input);
  const key = text(metric.key, 100);
  const label = text(metric.label, 300);
  const valueType = text(metric.valueType, 50);
  if (!key || !label || !valueType || typeof metric.value !== 'number' || !Number.isFinite(metric.value)) {
    return null;
  }
  return {
    key,
    label,
    valueType,
    value: metric.value,
    ...(typeof metric.numerator === 'number' && Number.isFinite(metric.numerator)
      ? { numerator: metric.numerator }
      : {}),
    ...(typeof metric.denominator === 'number' && Number.isFinite(metric.denominator)
      ? { denominator: metric.denominator }
      : {}),
    isPrimary: metric.isPrimary === true,
  };
}

function positiveInteger(input: unknown): number | null {
  return typeof input === 'number' && Number.isInteger(input) && input > 0 ? input : null;
}

function nonnegativeInteger(input: unknown): number | null {
  return typeof input === 'number' && Number.isInteger(input) && input >= 0 ? input : null;
}

function experimentResultSources(
  rows: SelectionChallengeExperimentResult[],
  lens: SelectionChallengeLens,
  idea: IdeaRecord,
): SourceInput[] {
  return rows.flatMap(row => {
    const origin = row.originChallenge;
    const conclusion = row.conclusion;
    if (
      !origin
      || !conclusion
      || row.originChallengeId !== origin.id
      || row.ideaId !== String(idea.idea_id)
      || row.ideaRevision !== Number(idea.idea_revision)
      || origin.ideaId !== row.ideaId
      || origin.ideaRevision !== row.ideaRevision
      || origin.lens.toLowerCase() !== lens
    ) return [];

    const snapshot = record(conclusion.snapshot);
    const experiment = record(snapshot.experiment);
    const originSnapshot = record(experiment.originSnapshot);
    const precommitment = record(snapshot.precommitment);
    const evidence = record(snapshot.evidence);
    const source = record(evidence.source);
    const sample = record(evidence.sample);
    const window = record(evidence.window);
    const sourceType = source.sourceType;
    const adapterKey = text(source.adapterKey, 100);
    if (
      experiment.experimentId !== row.id
      || experiment.ideaId !== row.ideaId
      || experiment.ideaRevision !== row.ideaRevision
      || originSnapshot.challengeId !== origin.id
      || originSnapshot.lens !== lens
      || (sourceType !== 'FIRST_PARTY' && sourceType !== 'MANUAL')
      || !adapterKey
    ) return [];
    const canonicalSourceType: 'FIRST_PARTY' | 'MANUAL' = sourceType;

    const primaryMetric = text(precommitment.primaryMetric, 500);
    const passThreshold = text(precommitment.passThreshold, 500);
    const failThreshold = text(precommitment.failThreshold, 500);
    const measurementWindow = text(precommitment.measurementWindow, 500);
    if (!primaryMetric || !passThreshold || !failThreshold || !measurementWindow) return [];

    const observationSummary = text(evidence.observationSummary) || null;
    const observedMetric = text(evidence.observedMetric, 500) || null;
    const metrics = array(evidence.metrics)
      .slice(0, 12)
      .map(experimentMetric)
      .filter((metric): metric is NonNullable<typeof metric> => metric !== null);
    const limitations = array(evidence.limitations)
      .map(item => text(item, 500))
      .filter(Boolean)
      .slice(0, 10);
    const observedThrough = isoDate(window.observedThrough);
    const observed = nonnegativeInteger(sample.observed);
    const target = positiveInteger(sample.target);
    const unit = text(sample.unit, 100) || null;
    if (!observationSummary && !observedMetric && metrics.length === 0 && observed === null) return [];

    const observation = {
      observedThrough,
      observationSummary,
      observedMetric,
      metrics,
      sample: { observed, target, unit },
      limitations,
    };
    return [{
      kind: 'experiment_result' as const,
      title: `Experiment result: ${primaryMetric}`,
      excerpt: text({
        precommitment: { primaryMetric, passThreshold, failThreshold, measurementWindow },
        observation,
      }),
      url: null,
      capturedAt: conclusion.createdAt.toISOString(),
      provenance: {
        assetType: 'EXPERIMENT_RESULT' as const,
        experimentId: row.id,
        conclusionId: conclusion.id,
        originChallengeId: origin.id,
        evidenceClass: canonicalSourceType === 'FIRST_PARTY' ? 'observed' as const : 'proxy' as const,
        sourceType: canonicalSourceType,
        adapterKey,
        precommitment: {
          primaryMetric,
          passThreshold,
          failThreshold,
          measurementWindow,
          sampleTarget: positiveInteger(precommitment.sampleTarget),
        },
        observation,
      },
    }];
  }).slice(0, 6);
}

export function selectionChallengeIdeaSnapshot(idea: IdeaRecord): Record<string, unknown> {
  const snapshot: Record<string, unknown> = {
    idea_id: idea.idea_id,
    idea_revision: idea.idea_revision,
    solution_name: ideaName(idea),
  };
  for (const field of SUBJECT_FIELDS) {
    if (field === 'solution_name') continue;
    if (hasValue(idea[field])) snapshot[field] = idea[field];
  }
  return snapshot;
}

export function selectionChallengeSubjects(idea: IdeaRecord): SelectionChallengeSubject[] {
  const snapshot = selectionChallengeIdeaSnapshot(idea);
  const fields = SUBJECT_FIELDS.filter(field => hasValue(snapshot[field]));
  return fields.map((field, index) => SelectionChallengeSubjectSchema.parse({
    key: `I${index + 1}`,
    field,
    value: snapshot[field],
  }));
}

const MAX_PAIN_QUOTES = 6;

/**
 * Customer quotes for the pains an idea addresses.
 *
 * Keyed on `source_pain` AND `pain_points_addressed`, because `source_pain` is null on
 * most generated ideas — 4 of 6 on a representative run. Keying on `source_pain` alone
 * shipped an empty packet, the reviewer then correctly reported "no direct customer
 * quotes", and the UI rendered that as "SAVED EVIDENCE RAISES CONCERNS · NOT
 * ESTABLISHED" for a pain whose verbatim quote was visible one page earlier. Absence of
 * a packet is not absence of evidence.
 */
function painQuoteSources(discovery: unknown, idea: IdeaRecord): SourceInput[] {
  const quotes = record(record(discovery).quotes);
  const quoteKeys = Object.keys(quotes);
  if (quoteKeys.length === 0) return [];

  // source_pain first so the originating pain's quotes survive the cap; the addressed
  // pains follow in their stated order.
  const candidates = [idea.source_pain, ...array(idea.pain_points_addressed)];
  const titles: string[] = [];
  for (const candidate of candidates) {
    const pain = normalizeLabel(candidate);
    if (!pain) continue;
    const title = quoteKeys.find(key => normalizeLabel(key) === pain);
    if (title && !titles.includes(title)) titles.push(title);
  }
  if (titles.length === 0) return [];

  const sources: SourceInput[] = [];
  for (const title of titles) {
    array(quotes[title]).forEach((input, index) => {
      if (sources.length >= MAX_PAIN_QUOTES) return;
      const quote = record(input);
      const excerpt = text(quote.text);
      if (!excerpt) return;
      sources.push({
        kind: 'customer_quote' as const,
        title: `${title} · captured quote ${index + 1}`,
        excerpt,
        url: httpUrl(quote.source_url),
        capturedAt: isoDate(quote.created_at),
        provenance: {
          assetType: 'DISCOVERY_DATA' as const,
          jsonPointer: `/quotes/${title}/${index}`,
        },
      });
    });
    if (sources.length >= MAX_PAIN_QUOTES) break;
  }
  return sources;
}

function competitorSources(preview: unknown): SourceInput[] {
  const incumbents = array(record(record(preview).market_reality).incumbents);
  return incumbents.slice(0, 8).flatMap((input, index) => {
    const incumbent = record(input);
    const title = text(incumbent.name ?? incumbent.tool_name ?? incumbent.competitor, 300);
    const excerpt = text({
      focus: incumbent.focus ?? incumbent.description,
      pricing: incumbent.pricing ?? incumbent.price,
      gap: incumbent.gap ?? incumbent.weakness,
      evidence: incumbent.evidence,
    });
    if (!title || !excerpt) return [];
    return [{
      kind: 'competitor_fact' as const,
      title,
      excerpt,
      url: httpUrl(incumbent.url ?? incumbent.source_url),
      capturedAt: isoDate(incumbent.captured_at),
      provenance: {
        assetType: 'PREVIEW_REPORT' as const,
        jsonPointer: `/market_reality/incumbents/${index}`,
      },
    }];
  });
}

function audienceSources(preview: unknown): SourceInput[] {
  const segments = array(record(record(preview).audience_mapping).audience_segments);
  return segments.slice(0, 6).flatMap((input, index) => {
    const segment = record(input);
    const title = text(segment.segment_name ?? segment.name, 300);
    const excerpt = text({
      description: segment.description,
      size: segment.size_estimate,
      budget_sensitivity: segment.budget_sensitivity,
      payability: segment.payability_class,
      where_they_gather: segment.where_they_gather ?? segment.channels,
    });
    if (!title || !excerpt) return [];
    return [{
      kind: 'audience_fact' as const,
      title,
      excerpt,
      url: null,
      capturedAt: null,
      provenance: {
        assetType: 'PREVIEW_REPORT' as const,
        jsonPointer: `/audience_mapping/audience_segments/${index}`,
      },
    }];
  });
}

function caveatSources(preview: unknown): SourceInput[] {
  const pr = record(preview);
  const quality = record(pr.data_quality_summary);
  const caveats = array(quality.quality_caveats);
  const difficulty = record(pr.niche_difficulty_verdict);
  const wallet = record(record(pr.market_reality).wallet);
  const inputs: Array<{ title: string; excerpt: unknown; pointer: string }> = [];

  caveats.slice(0, 6).forEach((caveat, index) => {
    inputs.push({
      title: `Data caveat ${index + 1}`,
      excerpt: caveat,
      pointer: `/data_quality_summary/quality_caveats/${index}`,
    });
  });
  if (hasValue(difficulty.narrative_summary ?? difficulty.headline)) {
    inputs.push({
      title: text(difficulty.headline, 300) || 'Niche difficulty',
      excerpt: difficulty.narrative_summary ?? difficulty.headline,
      pointer: '/niche_difficulty_verdict',
    });
  }
  if (hasValue(wallet.evidence)) {
    inputs.push({
      title: `Buyer-wallet evidence${wallet.wallet_class ? ` · ${text(wallet.wallet_class, 80)}` : ''}`,
      excerpt: wallet.evidence,
      pointer: '/market_reality/wallet/evidence',
    });
  }

  return inputs.flatMap(input => {
    const excerpt = text(input.excerpt);
    if (!excerpt) return [];
    return [{
      kind: 'market_caveat' as const,
      title: input.title,
      excerpt,
      url: null,
      capturedAt: null,
      provenance: {
        assetType: 'PREVIEW_REPORT' as const,
        jsonPointer: input.pointer,
      },
    }];
  });
}

function dependencySources(preview: unknown): SourceInput[] {
  const pr = record(preview);
  const notes = [
    ...array(pr.data_access_notes),
    ...array(pr.dependency_notes),
    ...array(pr.platform_risks),
  ];
  return notes.slice(0, 8).flatMap((note, index) => {
    const excerpt = text(note);
    if (!excerpt) return [];
    return [{
      kind: 'dependency_note' as const,
      title: `Dependency evidence ${index + 1}`,
      excerpt,
      url: null,
      capturedAt: null,
      provenance: {
        assetType: 'PREVIEW_REPORT' as const,
        jsonPointer: `/dependency_notes/${index}`,
      },
    }];
  });
}

export function buildSelectionChallengeEvidence(
  lens: SelectionChallengeLens,
  idea: IdeaRecord,
  preview: unknown,
  discovery: unknown,
  ownerEvidence: SelectionChallengeOwnerEvidence[] = [],
  experimentResults: SelectionChallengeExperimentResult[] = [],
): SelectionChallengeSource[] {
  const experimentSources = experimentResultSources(experimentResults, lens, idea);
  const ownerSources = ownerEvidenceSources(ownerEvidence, lens, idea);
  const quotes = painQuoteSources(discovery, idea);
  const competitors = competitorSources(preview);
  const audiences = audienceSources(preview);
  const caveats = caveatSources(preview);
  const dependencies = dependencySources(preview);

  const selected = lens === 'demand'
    ? [...quotes, ...audiences, ...caveats]
    : lens === 'competition'
      ? [...competitors, ...caveats]
      : lens === 'distribution'
        ? [...audiences, ...quotes, ...caveats]
        : [...dependencies, ...caveats];

  return [...experimentSources, ...ownerSources, ...selected].slice(0, 24).map((source, index) => SelectionChallengeSourceSchema.parse({
    ...source,
    key: `S${index + 1}`,
  }));
}
