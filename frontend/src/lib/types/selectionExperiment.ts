export type ExperimentStatus = 'DRAFT' | 'LOCKED';
export type ExperimentAssumptionType = 'DESIRABILITY' | 'USABILITY' | 'FEASIBILITY' | 'VIABILITY' | 'ETHICS';
export type ExperimentMethod =
  | 'CUSTOMER_INTERVIEWS'
  | 'SURVEY'
  | 'CTA_SMOKE_TEST'
  | 'BOOKED_CALL'
  | 'PREORDER'
  | 'CONCIERGE'
  | 'PROTOTYPE'
  | 'TECHNICAL_SPIKE'
  | 'OTHER';
export type ExperimentEvidenceSignal =
  | 'LANGUAGE'
  | 'STATED_PREFERENCE'
  | 'CTA_INTEREST'
  | 'SMALL_COMMITMENT'
  | 'PAYMENT_INTENT'
  | 'USAGE';


export type ExperimentCtaLabel = 'IM_INTERESTED' | 'SHOW_ME_THE_CONCEPT' | 'ID_TRY_THIS';
export type ExperimentRunStatus = 'ACTIVE' | 'CLOSED';
export type ExperimentConclusionOutcome = 'PASS' | 'FAIL' | 'AMBIGUOUS' | 'INVALID';
export type ExperimentEvidenceSource = 'HOSTED_RUN' | 'MANUAL';
export type PublicExperimentEventType =
  | 'STIMULUS_EXPOSED'
  | 'CTA_CLICKED'
  | 'FAKE_DOOR_DISCLOSED'
  | 'CLIENT_ERROR';

export interface SelectionExperimentArtifact {
  version: number;
  headline: string;
  promise: string;
  ctaLabel: string;
  disclosure: {
    title: string;
    body: string;
  };
}

export interface SelectionExperimentRun {
  id: string;
  publicToken: string;
  status: ExperimentRunStatus;
  artifact: SelectionExperimentArtifact;
  launchedAt: string;
  closedAt: string | null;
}

export interface SelectionExperimentLaunch {
  headline: string;
  promise: string;
  ctaLabel: ExperimentCtaLabel;
}

export interface SelectionExperimentResults {
  runStatus: ExperimentRunStatus;
  exposures: number;
  ctaClicks: number;
  disclosures: number;
  ctaRate: number | null;
  sampleTarget: number | null;
  sampleProgress: number | null;
  firstEventAt: string | null;
  lastEventAt: string | null;
  dataQualityWarning: string | null;
}

export interface SelectionExperimentConclusion {
  id: string;
  experimentId: string;
  ideaId: string;
  ideaRevision: number;
  outcome: ExperimentConclusionOutcome;
  evidenceSource: ExperimentEvidenceSource;
  requestFingerprint: string;
  ownerRationale: string;
  nextActionSnapshot: string;
  snapshot: {
    schemaVersion: 1;
    experiment: Record<string, unknown>;
    precommitment: Record<string, unknown>;
    evidence: Record<string, unknown>;
    adjudication: Record<string, unknown>;
  };
  concludedByUserId: string;
  createdAt: string;
  assumptionTransition?: {
    assumptionId: string;
    before: {
      direction: "UNKNOWN" | "SUPPORTING" | "MIXED" | "CONTRADICTING";
      evidenceClass: "NONE" | "INFERENCE" | "PROXY" | "OBSERVED";
    };
    after: {
      direction: "UNKNOWN" | "SUPPORTING" | "MIXED" | "CONTRADICTING";
      evidenceClass: "NONE" | "INFERENCE" | "PROXY" | "OBSERVED";
    };
  } | null;
}

interface ConclusionBaseInput {
  outcome: ExperimentConclusionOutcome;
  ownerRationale: string;
  limitations: string[];
}

export type SelectionExperimentConclusionInput =
  | (ConclusionBaseInput & {
      evidenceSource: 'HOSTED_RUN';
    })
  | (ConclusionBaseInput & {
      evidenceSource: 'MANUAL';
      observationSummary: string;
      observedAt: string;
      sampleSize: number | null;
      observedMetric: string;
      sourceReferences: string[];
    });

export interface PublicExperimentTest {
  artifact: SelectionExperimentArtifact;
  viewToken: string;
}

export interface SelectionExperimentOriginSnapshot {
  version: 1;
  kind: 'SELECTION_CHALLENGE_QUESTION';
  challengeId: string;
  challengeInputFingerprint: string;
  questionId: string;
  lens: 'demand' | 'competition' | 'distribution' | 'dependencies';
  consensus: 'supported' | 'contradicted' | 'mixed' | 'disputed' | 'insufficient';
  evidenceKeys: string[];
  skeptic: {
    questionId: string;
    position: 'supports' | 'contradicts' | 'mixed' | 'insufficient';
    summary: string;
    subjectKeys: string[];
    evidenceKeys: string[];
    evidenceClass: 'observed' | 'proxy' | 'inference';
  };
  auditor: SelectionExperimentOriginSnapshot['skeptic'];
  citedSources: Array<{
    key: string;
    kind: string;
    title: string;
    excerpt: string;
    url: string | null;
    capturedAt: string | null;
    provenance: Record<string, unknown>;
  }>;
}

export interface SelectionExperimentDraft {
  ideaId: string;
  ideaRevision: number;
  assumptionId?: string | null;
  originChallengeId?: string | null;
  originQuestionId?: string | null;
  assumptionType: ExperimentAssumptionType;
  assumption: string;
  whyCritical: string;
  currentEvidence: string;
  method: ExperimentMethod;
  evidenceSignal: ExperimentEvidenceSignal;
  stimulus: string;
  audience: string;
  channel: string;
  primaryMetric: string;
  passThreshold: string;
  failThreshold: string;
  measurementWindow: string;
  sampleTarget: number | null;
  costEstimate: string;
  passAction: string;
  failAction: string;
  flatAction: string;
  invalidAction: string;
}

export type SelectionExperimentDraftSeed = Pick<SelectionExperimentDraft, 'ideaId' | 'ideaRevision'>
  & Partial<Omit<SelectionExperimentDraft, 'ideaId' | 'ideaRevision'>>;

export interface SelectionExperimentPrefill {
  requestId: string;
  draft: SelectionExperimentDraftSeed;
  /** Why fields were supplied. Generated suggestions are reviewable starting
   * points, never owner-authored evidence or saved decisions. */
  source?: "founder_fit" | "analyst" | "challenge" | "manual";
  suggestedFields?: Array<keyof SelectionExperimentDraft>;
}

export interface SelectionExperiment extends SelectionExperimentDraft {
  id: string;
  jobId: string;
  ideaSnapshot: Record<string, unknown>;
  status: ExperimentStatus;
  lockedAt: string | null;
  createdAt: string;
  updatedAt: string;
  originSnapshot?: SelectionExperimentOriginSnapshot | null;
  run?: SelectionExperimentRun | null;
  conclusion?: SelectionExperimentConclusion | null;
}
