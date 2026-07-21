-- CreateEnum
CREATE TYPE "SelectionExperimentStatus" AS ENUM ('DRAFT', 'LOCKED');

-- CreateEnum
CREATE TYPE "ExperimentAssumptionType" AS ENUM ('DESIRABILITY', 'USABILITY', 'FEASIBILITY', 'VIABILITY', 'ETHICS');

-- CreateEnum
CREATE TYPE "ExperimentMethod" AS ENUM ('CUSTOMER_INTERVIEWS', 'SURVEY', 'CTA_SMOKE_TEST', 'BOOKED_CALL', 'PREORDER', 'CONCIERGE', 'PROTOTYPE', 'TECHNICAL_SPIKE', 'OTHER');

-- CreateEnum
CREATE TYPE "ExperimentEvidenceSignal" AS ENUM ('LANGUAGE', 'STATED_PREFERENCE', 'CTA_INTEREST', 'SMALL_COMMITMENT', 'PAYMENT_INTENT', 'USAGE');

-- CreateEnum
CREATE TYPE "SelectionExperimentRunStatus" AS ENUM ('ACTIVE', 'CLOSED');

-- CreateEnum
CREATE TYPE "SelectionExperimentOutcome" AS ENUM ('PASS', 'FAIL', 'AMBIGUOUS', 'INVALID');

-- CreateEnum
CREATE TYPE "SelectionExperimentEvidenceSource" AS ENUM ('HOSTED_RUN', 'MANUAL');

-- CreateEnum
CREATE TYPE "SelectionFinalDecisionDisposition" AS ENUM ('PROCEED', 'TEST_FIRST', 'PARK', 'STOP');

-- CreateEnum
CREATE TYPE "SelectionRecommendationRelation" AS ENUM ('FOLLOWED', 'OVERRIDDEN', 'DEFERRED', 'REJECTED');

-- CreateEnum
CREATE TYPE "SelectionDecisionHandoffAction" AS ENUM ('BUILD', 'VALIDATE_MORE', 'PARK', 'STOP');

-- CreateEnum
CREATE TYPE "IntegrationProvider" AS ENUM ('GITHUB');

-- CreateEnum
CREATE TYPE "IntegrationConnectionStatus" AS ENUM ('ACTIVE', 'REVOKED');

-- CreateEnum
CREATE TYPE "SelectionHandoffDispatchStatus" AS ENUM ('PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "SelectionExperimentEventType" AS ENUM ('STIMULUS_EXPOSED', 'CTA_CLICKED', 'FAKE_DOOR_DISCLOSED', 'CLIENT_ERROR');

-- CreateEnum
CREATE TYPE "SelectionChallengeLens" AS ENUM ('DEMAND', 'COMPETITION', 'DISTRIBUTION', 'DEPENDENCIES');

-- CreateEnum
CREATE TYPE "SelectionOwnerEvidenceKind" AS ENUM ('NOTE', 'CUSTOMER_QUOTE', 'ANALYTICS_OBSERVATION', 'LINK');

-- CreateEnum
CREATE TYPE "SelectionOwnerEvidencePosition" AS ENUM ('SUPPORTS', 'CONTRADICTS', 'CONTEXT');

-- AlterTable
ALTER TABLE "DiscoveryVote" ADD COLUMN     "solutionId" VARCHAR(100);

-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "deepResearchRecommendedIdeaId" VARCHAR(100),
ADD COLUMN     "deepResearchRecommendedIdeaRevision" INTEGER,
ADD COLUMN     "selectedSolutionIds" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
ADD COLUMN     "selectionDecisionProfile" JSONB,
ADD COLUMN     "selectionDraft" JSONB,
ADD COLUMN     "selectionDraftVersion" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "selectionFounderFit" JSONB;

-- CreateTable
CREATE TABLE "SelectionOwnerEvidence" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "ideaId" VARCHAR(100) NOT NULL,
    "ideaRevision" INTEGER NOT NULL,
    "lens" "SelectionChallengeLens" NOT NULL,
    "kind" "SelectionOwnerEvidenceKind" NOT NULL,
    "position" "SelectionOwnerEvidencePosition" NOT NULL,
    "title" VARCHAR(300) NOT NULL,
    "content" TEXT NOT NULL,
    "sourceUrl" VARCHAR(1000),
    "observedAt" TIMESTAMP(3),
    "inputFingerprint" CHAR(64) NOT NULL,
    "createdByUserId" VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "retractedAt" TIMESTAMP(3),
    "retractionReason" VARCHAR(500),

    CONSTRAINT "SelectionOwnerEvidence_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionChallenge" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "ideaId" VARCHAR(100) NOT NULL,
    "ideaRevision" INTEGER NOT NULL,
    "lens" "SelectionChallengeLens" NOT NULL,
    "inputFingerprint" CHAR(64) NOT NULL,
    "ideaSnapshot" JSONB NOT NULL,
    "evidenceSnapshot" JSONB NOT NULL,
    "artifact" JSONB NOT NULL,
    "skepticModel" VARCHAR(255) NOT NULL,
    "auditorModel" VARCHAR(255) NOT NULL,
    "promptVersion" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SelectionChallenge_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionConceptSet" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "purpose" VARCHAR(32) NOT NULL,
    "inputFingerprint" CHAR(64) NOT NULL,
    "parentRefs" JSONB NOT NULL,
    "artifact" JSONB NOT NULL,
    "model" VARCHAR(255) NOT NULL,
    "promptId" VARCHAR(100) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SelectionConceptSet_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionExperiment" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "ideaId" VARCHAR(100) NOT NULL,
    "ideaRevision" INTEGER NOT NULL,
    "ideaSnapshot" JSONB NOT NULL,
    "originChallengeId" TEXT,
    "originQuestionId" VARCHAR(100),
    "originSnapshot" JSONB,
    "status" "SelectionExperimentStatus" NOT NULL DEFAULT 'DRAFT',
    "assumptionType" "ExperimentAssumptionType" NOT NULL,
    "assumption" TEXT NOT NULL,
    "whyCritical" TEXT NOT NULL,
    "currentEvidence" TEXT NOT NULL DEFAULT '',
    "method" "ExperimentMethod" NOT NULL,
    "evidenceSignal" "ExperimentEvidenceSignal" NOT NULL,
    "stimulus" TEXT NOT NULL,
    "audience" TEXT NOT NULL,
    "channel" VARCHAR(500) NOT NULL,
    "primaryMetric" VARCHAR(500) NOT NULL,
    "passThreshold" VARCHAR(500) NOT NULL,
    "failThreshold" VARCHAR(500) NOT NULL,
    "measurementWindow" VARCHAR(500) NOT NULL,
    "sampleTarget" INTEGER,
    "costEstimate" VARCHAR(255) NOT NULL DEFAULT '',
    "passAction" TEXT NOT NULL,
    "failAction" TEXT NOT NULL,
    "flatAction" TEXT NOT NULL,
    "invalidAction" TEXT NOT NULL,
    "lockedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SelectionExperiment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionExperimentConclusion" (
    "id" TEXT NOT NULL,
    "experimentId" TEXT NOT NULL,
    "ideaId" VARCHAR(100) NOT NULL,
    "ideaRevision" INTEGER NOT NULL,
    "outcome" "SelectionExperimentOutcome" NOT NULL,
    "evidenceSource" "SelectionExperimentEvidenceSource" NOT NULL,
    "requestFingerprint" CHAR(64) NOT NULL,
    "ownerRationale" TEXT NOT NULL,
    "nextActionSnapshot" TEXT NOT NULL,
    "snapshot" JSONB NOT NULL,
    "concludedByUserId" VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SelectionExperimentConclusion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionFinalDecision" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "disposition" "SelectionFinalDecisionDisposition" NOT NULL,
    "selectedIdeaId" VARCHAR(100),
    "selectedIdeaRevision" INTEGER,
    "testExperimentId" TEXT,
    "testExperimentSnapshot" JSONB,
    "preMortemSnapshot" JSONB,
    "recommendationRelation" "SelectionRecommendationRelation" NOT NULL,
    "rationale" TEXT NOT NULL,
    "acceptedRisks" TEXT NOT NULL DEFAULT '',
    "changeCriterion" TEXT NOT NULL,
    "overrideReason" TEXT,
    "requestFingerprint" CHAR(64) NOT NULL,
    "sourceFingerprint" CHAR(64) NOT NULL,
    "recommendationSnapshot" JSONB NOT NULL,
    "selectedIdeaSnapshot" JSONB,
    "alternativesSnapshot" JSONB NOT NULL,
    "evidenceSnapshot" JSONB NOT NULL,
    "reportSha256" CHAR(64) NOT NULL,
    "decidedByUserId" VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SelectionFinalDecision_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionDecisionHandoff" (
    "id" TEXT NOT NULL,
    "finalDecisionId" TEXT NOT NULL,
    "action" "SelectionDecisionHandoffAction" NOT NULL,
    "ideaId" VARCHAR(100),
    "ideaRevision" INTEGER,
    "inputFingerprint" CHAR(64) NOT NULL,
    "artifact" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SelectionDecisionHandoff_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "IntegrationConnection" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "provider" "IntegrationProvider" NOT NULL,
    "externalId" VARCHAR(100) NOT NULL,
    "accountId" VARCHAR(100) NOT NULL,
    "accountLogin" VARCHAR(255) NOT NULL,
    "accountType" VARCHAR(50),
    "repositorySelection" VARCHAR(20),
    "permissions" JSONB NOT NULL,
    "authorizedRepositoryIds" JSONB NOT NULL,
    "status" "IntegrationConnectionStatus" NOT NULL DEFAULT 'ACTIVE',
    "lastVerifiedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "IntegrationConnection_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionHandoffDispatch" (
    "id" TEXT NOT NULL,
    "handoffId" TEXT NOT NULL,
    "connectionId" TEXT NOT NULL,
    "provider" "IntegrationProvider" NOT NULL,
    "adapterVersion" INTEGER NOT NULL DEFAULT 1,
    "destinationContainerId" VARCHAR(100) NOT NULL,
    "destinationSnapshot" JSONB NOT NULL,
    "payload" JSONB NOT NULL,
    "payloadFingerprint" CHAR(64) NOT NULL,
    "status" "SelectionHandoffDispatchStatus" NOT NULL DEFAULT 'PENDING',
    "confirmedByUserId" VARCHAR(255) NOT NULL,
    "attemptCount" INTEGER NOT NULL DEFAULT 1,
    "providerRequestStartedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "providerResourceId" VARCHAR(100),
    "providerResourceNodeId" VARCHAR(100),
    "providerResourceNumber" INTEGER,
    "providerResourceUrl" TEXT,
    "lastErrorClass" VARCHAR(50),
    "lastErrorCode" VARCHAR(100),
    "settledAt" TIMESTAMP(3),
    "reconciledAt" TIMESTAMP(3),
    "reconciledByUserId" VARCHAR(255),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SelectionHandoffDispatch_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionExperimentRun" (
    "id" TEXT NOT NULL,
    "experimentId" TEXT NOT NULL,
    "publicToken" VARCHAR(64) NOT NULL,
    "status" "SelectionExperimentRunStatus" NOT NULL DEFAULT 'ACTIVE',
    "artifact" JSONB NOT NULL,
    "briefVersion" INTEGER NOT NULL DEFAULT 1,
    "stimulusVersion" INTEGER NOT NULL DEFAULT 1,
    "launchedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "closedAt" TIMESTAMP(3),

    CONSTRAINT "SelectionExperimentRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SelectionExperimentEvent" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "eventId" UUID NOT NULL,
    "viewId" UUID NOT NULL,
    "type" "SelectionExperimentEventType" NOT NULL,
    "occurredAt" TIMESTAMP(3) NOT NULL,
    "receivedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SelectionExperimentEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SelectionOwnerEvidence_jobId_ideaId_ideaRevision_retractedA_idx" ON "SelectionOwnerEvidence"("jobId", "ideaId", "ideaRevision", "retractedAt");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionOwnerEvidence_jobId_ideaId_ideaRevision_inputFinge_key" ON "SelectionOwnerEvidence"("jobId", "ideaId", "ideaRevision", "inputFingerprint");

-- CreateIndex
CREATE INDEX "SelectionChallenge_jobId_ideaId_ideaRevision_createdAt_idx" ON "SelectionChallenge"("jobId", "ideaId", "ideaRevision", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionChallenge_jobId_ideaId_ideaRevision_lens_inputFing_key" ON "SelectionChallenge"("jobId", "ideaId", "ideaRevision", "lens", "inputFingerprint");

-- CreateIndex
CREATE INDEX "SelectionConceptSet_jobId_createdAt_idx" ON "SelectionConceptSet"("jobId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionConceptSet_jobId_inputFingerprint_key" ON "SelectionConceptSet"("jobId", "inputFingerprint");

-- CreateIndex
CREATE INDEX "SelectionExperiment_jobId_createdAt_idx" ON "SelectionExperiment"("jobId", "createdAt");

-- CreateIndex
CREATE INDEX "SelectionExperiment_jobId_ideaId_ideaRevision_idx" ON "SelectionExperiment"("jobId", "ideaId", "ideaRevision");

-- CreateIndex
CREATE INDEX "SelectionExperiment_originChallengeId_idx" ON "SelectionExperiment"("originChallengeId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionExperimentConclusion_experimentId_key" ON "SelectionExperimentConclusion"("experimentId");

-- CreateIndex
CREATE INDEX "SelectionExperimentConclusion_ideaId_ideaRevision_createdAt_idx" ON "SelectionExperimentConclusion"("ideaId", "ideaRevision", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionFinalDecision_jobId_key" ON "SelectionFinalDecision"("jobId");

-- CreateIndex
CREATE INDEX "SelectionFinalDecision_selectedIdeaId_selectedIdeaRevision_idx" ON "SelectionFinalDecision"("selectedIdeaId", "selectedIdeaRevision");

-- CreateIndex
CREATE INDEX "SelectionFinalDecision_testExperimentId_idx" ON "SelectionFinalDecision"("testExperimentId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionDecisionHandoff_finalDecisionId_key" ON "SelectionDecisionHandoff"("finalDecisionId");

-- CreateIndex
CREATE INDEX "SelectionDecisionHandoff_action_createdAt_idx" ON "SelectionDecisionHandoff"("action", "createdAt");

-- CreateIndex
CREATE INDEX "SelectionDecisionHandoff_ideaId_ideaRevision_idx" ON "SelectionDecisionHandoff"("ideaId", "ideaRevision");

-- CreateIndex
CREATE INDEX "IntegrationConnection_userId_provider_status_idx" ON "IntegrationConnection"("userId", "provider", "status");

-- CreateIndex
CREATE UNIQUE INDEX "IntegrationConnection_userId_provider_externalId_key" ON "IntegrationConnection"("userId", "provider", "externalId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionHandoffDispatch_payloadFingerprint_key" ON "SelectionHandoffDispatch"("payloadFingerprint");

-- CreateIndex
CREATE INDEX "SelectionHandoffDispatch_connectionId_idx" ON "SelectionHandoffDispatch"("connectionId");

-- CreateIndex
CREATE INDEX "SelectionHandoffDispatch_status_updatedAt_idx" ON "SelectionHandoffDispatch"("status", "updatedAt");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionHandoffDispatch_handoffId_provider_key" ON "SelectionHandoffDispatch"("handoffId", "provider");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionHandoffDispatch_provider_providerResourceId_key" ON "SelectionHandoffDispatch"("provider", "providerResourceId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionExperimentRun_experimentId_key" ON "SelectionExperimentRun"("experimentId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionExperimentRun_publicToken_key" ON "SelectionExperimentRun"("publicToken");

-- CreateIndex
CREATE INDEX "SelectionExperimentRun_status_launchedAt_idx" ON "SelectionExperimentRun"("status", "launchedAt");

-- CreateIndex
CREATE INDEX "SelectionExperimentEvent_runId_type_receivedAt_idx" ON "SelectionExperimentEvent"("runId", "type", "receivedAt");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionExperimentEvent_runId_eventId_key" ON "SelectionExperimentEvent"("runId", "eventId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionExperimentEvent_runId_viewId_type_key" ON "SelectionExperimentEvent"("runId", "viewId", "type");

-- CreateIndex
CREATE INDEX "DiscoveryVote_shareId_solutionId_idx" ON "DiscoveryVote"("shareId", "solutionId");

-- AddForeignKey
ALTER TABLE "SelectionOwnerEvidence" ADD CONSTRAINT "SelectionOwnerEvidence_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionChallenge" ADD CONSTRAINT "SelectionChallenge_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionConceptSet" ADD CONSTRAINT "SelectionConceptSet_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionExperiment" ADD CONSTRAINT "SelectionExperiment_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionExperiment" ADD CONSTRAINT "SelectionExperiment_originChallengeId_fkey" FOREIGN KEY ("originChallengeId") REFERENCES "SelectionChallenge"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionExperimentConclusion" ADD CONSTRAINT "SelectionExperimentConclusion_experimentId_fkey" FOREIGN KEY ("experimentId") REFERENCES "SelectionExperiment"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionFinalDecision" ADD CONSTRAINT "SelectionFinalDecision_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionFinalDecision" ADD CONSTRAINT "SelectionFinalDecision_testExperimentId_fkey" FOREIGN KEY ("testExperimentId") REFERENCES "SelectionExperiment"("id") ON DELETE NO ACTION ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionDecisionHandoff" ADD CONSTRAINT "SelectionDecisionHandoff_finalDecisionId_fkey" FOREIGN KEY ("finalDecisionId") REFERENCES "SelectionFinalDecision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "IntegrationConnection" ADD CONSTRAINT "IntegrationConnection_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionHandoffDispatch" ADD CONSTRAINT "SelectionHandoffDispatch_handoffId_fkey" FOREIGN KEY ("handoffId") REFERENCES "SelectionDecisionHandoff"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionHandoffDispatch" ADD CONSTRAINT "SelectionHandoffDispatch_connectionId_fkey" FOREIGN KEY ("connectionId") REFERENCES "IntegrationConnection"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionExperimentRun" ADD CONSTRAINT "SelectionExperimentRun_experimentId_fkey" FOREIGN KEY ("experimentId") REFERENCES "SelectionExperiment"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionExperimentEvent" ADD CONSTRAINT "SelectionExperimentEvent_runId_fkey" FOREIGN KEY ("runId") REFERENCES "SelectionExperimentRun"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Prisma does not model these cross-column invariants. Keep them in the database.
ALTER TABLE "SelectionFinalDecision"
ADD CONSTRAINT "SelectionFinalDecision_target_check" CHECK (
  ("disposition" IN ('PROCEED', 'TEST_FIRST') AND "selectedIdeaId" IS NOT NULL AND "selectedIdeaRevision" IS NOT NULL)
  OR ("disposition" IN ('PARK', 'STOP') AND "selectedIdeaId" IS NULL AND "selectedIdeaRevision" IS NULL)
),
ADD CONSTRAINT "SelectionFinalDecision_override_check" CHECK (
  ("recommendationRelation" = 'OVERRIDDEN' AND "overrideReason" IS NOT NULL AND length(trim("overrideReason")) > 0)
  OR ("recommendationRelation" <> 'OVERRIDDEN' AND "overrideReason" IS NULL)
),
ADD CONSTRAINT "SelectionFinalDecision_test_brief_check" CHECK (
  (
    "disposition" = 'TEST_FIRST'
    AND "testExperimentId" IS NOT NULL
    AND "testExperimentSnapshot" IS NOT NULL
  )
  OR (
    "disposition" <> 'TEST_FIRST'
    AND "testExperimentId" IS NULL
    AND "testExperimentSnapshot" IS NULL
  )
),
ADD CONSTRAINT "SelectionFinalDecision_pre_mortem_check" CHECK (
  ("disposition" IN ('PROCEED', 'TEST_FIRST') AND "preMortemSnapshot" IS NOT NULL)
  OR ("disposition" IN ('PARK', 'STOP') AND "preMortemSnapshot" IS NULL)
);

ALTER TABLE "SelectionDecisionHandoff"
ADD CONSTRAINT "SelectionDecisionHandoff_target_check" CHECK (
  ("action" IN ('BUILD', 'VALIDATE_MORE') AND "ideaId" IS NOT NULL AND "ideaRevision" IS NOT NULL AND "ideaRevision" > 0)
  OR ("action" IN ('PARK', 'STOP') AND "ideaId" IS NULL AND "ideaRevision" IS NULL)
);

ALTER TABLE "SelectionHandoffDispatch"
ADD CONSTRAINT "SelectionHandoffDispatch_attempt_count_positive" CHECK ("attemptCount" >= 1),
ADD CONSTRAINT "SelectionHandoffDispatch_adapter_v1" CHECK ("adapterVersion" = 1),
ADD CONSTRAINT "SelectionHandoffDispatch_reconciliation_pair" CHECK (
  ("reconciledAt" IS NULL AND "reconciledByUserId" IS NULL)
  OR ("reconciledAt" IS NOT NULL AND "reconciledByUserId" IS NOT NULL)
),
ADD CONSTRAINT "SelectionHandoffDispatch_valid_state" CHECK (
  (
    "status" = 'PENDING'
    AND "providerResourceId" IS NULL
    AND "providerResourceUrl" IS NULL
    AND "settledAt" IS NULL
    AND "lastErrorClass" IS NULL
    AND "lastErrorCode" IS NULL
  )
  OR (
    "status" = 'SUCCEEDED'
    AND "providerResourceId" IS NOT NULL
    AND "providerResourceUrl" IS NOT NULL
    AND "settledAt" IS NOT NULL
    AND "lastErrorClass" IS NULL
    AND "lastErrorCode" IS NULL
  )
  OR (
    "status" IN ('FAILED', 'UNKNOWN')
    AND "providerResourceId" IS NULL
    AND "providerResourceUrl" IS NULL
    AND "settledAt" IS NOT NULL
    AND "lastErrorClass" IS NOT NULL
    AND "lastErrorCode" IS NOT NULL
  )
);
