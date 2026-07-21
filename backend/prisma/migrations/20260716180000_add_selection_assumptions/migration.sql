-- CreateEnum
CREATE TYPE "SelectionAssumptionImpact" AS ENUM ('DECISIVE', 'HIGH', 'MEDIUM');

-- CreateEnum
CREATE TYPE "SelectionAssumptionOwnerState" AS ENUM ('OPEN', 'ACCEPTED_RISK', 'RETIRED');

-- AlterTable
ALTER TABLE "SelectionExperiment" ADD COLUMN "assumptionId" TEXT;

-- CreateTable
CREATE TABLE "SelectionAssumption" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "ideaId" VARCHAR(100) NOT NULL,
    "ideaRevision" INTEGER NOT NULL,
    "lens" "SelectionChallengeLens" NOT NULL,
    "statement" TEXT NOT NULL,
    "impactIfFalse" TEXT NOT NULL,
    "falsificationQuestion" TEXT NOT NULL,
    "impact" "SelectionAssumptionImpact" NOT NULL,
    "ownerState" "SelectionAssumptionOwnerState" NOT NULL DEFAULT 'OPEN',
    "version" INTEGER NOT NULL DEFAULT 1,
    "originChallengeId" TEXT,
    "originQuestionId" VARCHAR(100),
    "statementFingerprint" CHAR(64) NOT NULL,
    "createdByUserId" VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SelectionAssumption_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SelectionAssumption_jobId_ideaId_ideaRevision_ownerState_idx" ON "SelectionAssumption"("jobId", "ideaId", "ideaRevision", "ownerState");

-- CreateIndex
CREATE INDEX "SelectionAssumption_originChallengeId_idx" ON "SelectionAssumption"("originChallengeId");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionAssumption_jobId_ideaId_ideaRevision_lens_statemen_key" ON "SelectionAssumption"("jobId", "ideaId", "ideaRevision", "lens", "statementFingerprint");

-- CreateIndex
CREATE UNIQUE INDEX "SelectionAssumption_jobId_originChallengeId_originQuestionI_key" ON "SelectionAssumption"("jobId", "originChallengeId", "originQuestionId");

-- CreateIndex
CREATE INDEX "SelectionExperiment_assumptionId_idx" ON "SelectionExperiment"("assumptionId");

-- AddForeignKey
ALTER TABLE "SelectionAssumption" ADD CONSTRAINT "SelectionAssumption_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionAssumption" ADD CONSTRAINT "SelectionAssumption_originChallengeId_fkey" FOREIGN KEY ("originChallengeId") REFERENCES "SelectionChallenge"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SelectionExperiment" ADD CONSTRAINT "SelectionExperiment_assumptionId_fkey" FOREIGN KEY ("assumptionId") REFERENCES "SelectionAssumption"("id") ON DELETE SET NULL ON UPDATE CASCADE;
