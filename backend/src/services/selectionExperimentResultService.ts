import {
  SelectionExperimentEventType,
  type Prisma,
  type SelectionExperimentRunStatus,
} from '@prisma/client';

type ResultClient = Pick<Prisma.TransactionClient, 'selectionExperimentEvent'>;

export interface SelectionExperimentResultSnapshot {
  runStatus: SelectionExperimentRunStatus;
  exposures: number;
  ctaClicks: number;
  disclosures: number;
  ctaRate: number | null;
  sampleTarget: number | null;
  sampleProgress: number | null;
  firstEventAt: Date | null;
  lastEventAt: Date | null;
  dataQualityWarning: string | null;
  quality: {
    status: 'SUFFICIENT' | 'PARTIAL' | 'INVALID' | 'UNKNOWN';
    warnings: Array<{ code: string; message: string }>;
  };
}

export async function calculateSelectionExperimentResults(
  client: ResultClient,
  input: {
    runId: string;
    runStatus: SelectionExperimentRunStatus;
    sampleTarget: number | null;
    observedThrough?: Date;
  },
): Promise<SelectionExperimentResultSnapshot> {
  const where = {
    runId: input.runId,
    ...(input.observedThrough ? { receivedAt: { lte: input.observedThrough } } : {}),
  };
  const [counts, timing] = await Promise.all([
    client.selectionExperimentEvent.groupBy({
      by: ['type'],
      where,
      _count: { _all: true },
    }),
    client.selectionExperimentEvent.aggregate({
      where,
      _min: { receivedAt: true },
      _max: { receivedAt: true },
    }),
  ]);
  const countFor = (type: SelectionExperimentEventType) =>
    counts.find((row) => row.type === type)?._count._all ?? 0;
  const exposures = countFor(SelectionExperimentEventType.STIMULUS_EXPOSED);
  const ctaClicks = countFor(SelectionExperimentEventType.CTA_CLICKED);
  const disclosures = countFor(SelectionExperimentEventType.FAKE_DOOR_DISCLOSED);
  const warnings: Array<{ code: string; message: string }> = [];

  if (ctaClicks > exposures) {
    warnings.push({
      code: 'CTA_WITHOUT_EXPOSURE',
      message: 'Some CTA events are missing a recorded exposure; this run cannot support a pass or fail conclusion.',
    });
  }
  if (input.sampleTarget && exposures < input.sampleTarget) {
    warnings.push({
      code: 'SAMPLE_TARGET_NOT_REACHED',
      message: `The run stopped at ${exposures} of ${input.sampleTarget} planned exposures.`,
    });
  }
  if (exposures === 0) {
    warnings.push({
      code: 'NO_EXPOSURES',
      message: 'No recorded exposures are available to interpret.',
    });
  }

  const qualityStatus = warnings.some((warning) => warning.code === 'CTA_WITHOUT_EXPOSURE')
    ? 'INVALID'
    : warnings.length
      ? 'PARTIAL'
      : exposures > 0
        ? 'SUFFICIENT'
        : 'UNKNOWN';

  return {
    runStatus: input.runStatus,
    exposures,
    ctaClicks,
    disclosures,
    ctaRate: exposures > 0 ? ctaClicks / exposures : null,
    sampleTarget: input.sampleTarget,
    sampleProgress: input.sampleTarget
      ? Math.min(exposures / input.sampleTarget, 1)
      : null,
    firstEventAt: timing._min.receivedAt,
    lastEventAt: timing._max.receivedAt,
    dataQualityWarning: warnings[0]?.message ?? null,
    quality: { status: qualityStatus, warnings },
  };
}
