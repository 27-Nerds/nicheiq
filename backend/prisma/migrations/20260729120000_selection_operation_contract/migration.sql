-- Selection operations become exact, charge-linked and independently cancellable.
ALTER TYPE "DispatchKind" ADD VALUE IF NOT EXISTS 'DEEP_RESEARCH';
ALTER TYPE "DispatchState" ADD VALUE IF NOT EXISTS 'CANCELLED';

ALTER TABLE "Job"
  ADD COLUMN "selectedSolutionRefs" JSONB,
  ADD COLUMN "selectionDecisionProfileVersion" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "ideaBatchCompletedCount" INTEGER NOT NULL DEFAULT 0;

ALTER TABLE "SelectionExperiment"
  ADD COLUMN "version" INTEGER NOT NULL DEFAULT 1;

ALTER TABLE "JobDispatch"
  ADD COLUMN "clientRequestId" UUID,
  ADD COLUMN "refundTransactionId" TEXT,
  ADD COLUMN "refundedAt" TIMESTAMP(3),
  ADD COLUMN "refundedAmount" INTEGER,
  ADD COLUMN "requestSnapshot" JSONB,
  ADD COLUMN "requestFingerprint" CHAR(64),
  ADD COLUMN "workPayload" JSONB,
  ADD COLUMN "resultSnapshot" JSONB,
  ADD COLUMN "resultFingerprint" CHAR(64),
  ADD COLUMN "batchOrdinal" INTEGER,
  ADD COLUMN "deliveryAttempts" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN "lastDeliveryAt" TIMESTAMP(3),
  ADD COLUMN "lastDeliveryError" TEXT;

ALTER TABLE "CreditTransaction"
  ADD COLUMN "reversalOfId" TEXT;

CREATE UNIQUE INDEX "JobDispatch_jobId_clientRequestId_key"
  ON "JobDispatch"("jobId", "clientRequestId");
CREATE UNIQUE INDEX "JobDispatch_chargeId_key"
  ON "JobDispatch"("chargeId");
CREATE UNIQUE INDEX "JobDispatch_refundTransactionId_key"
  ON "JobDispatch"("refundTransactionId");
CREATE UNIQUE INDEX "CreditTransaction_reversalOfId_key"
  ON "CreditTransaction"("reversalOfId");

ALTER TABLE "JobDispatch"
  ADD CONSTRAINT "JobDispatch_chargeId_fkey"
  FOREIGN KEY ("chargeId") REFERENCES "CreditTransaction"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "JobDispatch"
  ADD CONSTRAINT "JobDispatch_refundTransactionId_fkey"
  FOREIGN KEY ("refundTransactionId") REFERENCES "CreditTransaction"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "CreditTransaction"
  ADD CONSTRAINT "CreditTransaction_reversalOfId_fkey"
  FOREIGN KEY ("reversalOfId") REFERENCES "CreditTransaction"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- Historical numbered regeneration charges already represent completed batches, except for
-- the one active REGENERATE dispatch (if any).
UPDATE "Job" AS j
SET "ideaBatchCompletedCount" = GREATEST(
  j."regenerationCount" - CASE
    WHEN EXISTS (
      SELECT 1
      FROM "JobDispatch" d
      WHERE d.id = j."activeDispatchId"
        AND d.kind = 'REGENERATE'
        AND d.state IN ('AUTHORIZED', 'CLAIMED')
    ) THEN 1 ELSE 0 END,
  0
);

UPDATE "JobDispatch"
SET "batchOrdinal" = NULLIF(
  regexp_replace("segment", '^regenerate_ideas_', ''),
  ''
)::INTEGER
WHERE kind = 'REGENERATE'
  AND "segment" ~ '^regenerate_ideas_[0-9]+$';

-- Link historical refunds to the exact deduction when the existing stage/cycle uniqueness
-- makes the pairing unambiguous.
UPDATE "CreditTransaction" AS refund
SET "reversalOfId" = charge.id
FROM "CreditTransaction" AS charge
WHERE refund.type = 'REFUND'
  AND charge.type = 'JOB_DEDUCTION'
  AND refund."relatedJobId" = charge."relatedJobId"
  AND refund.stage = charge.stage
  AND refund.cycle = charge.cycle
  AND refund."reversalOfId" IS NULL;

-- Refuse to install the active-operation invariant over corrupt historical state.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "JobDispatch"
    WHERE state IN ('AUTHORIZED', 'CLAIMED')
    GROUP BY "jobId"
    HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION 'multiple active dispatches exist for one or more jobs';
  END IF;
END $$;

-- Prisma 5.22 cannot represent this partial unique index. Keep it in hand-written migration SQL.
CREATE UNIQUE INDEX "JobDispatch_one_active_per_job"
  ON "JobDispatch"("jobId")
  WHERE state IN ('AUTHORIZED', 'CLAIMED');
