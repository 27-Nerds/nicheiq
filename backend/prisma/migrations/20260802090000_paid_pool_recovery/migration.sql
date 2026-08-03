ALTER TYPE "DispatchState" ADD VALUE 'RECOVERING' AFTER 'CLAIMED';

ALTER TABLE "JobDispatch"
ADD COLUMN "recoveryJournal" JSONB,
ADD COLUMN "recoveryPreparedAt" TIMESTAMP(3),
ADD COLUMN "recoveryToken" UUID;

-- Older deployments did not enforce the chat-source idempotency key, so a lost HTTP
-- response could leave more than one dispatch row for the same seed card. Preserve every
-- billing/audit row, but keep the key on exactly one deterministic canonical operation:
-- an in-flight operation wins; otherwise the newest durable row wins. PostgreSQL unique
-- indexes allow multiple NULLs, so historical noncanonical rows remain queryable without
-- blocking the constraint.
WITH ranked AS (
  SELECT
    dispatch."id",
    ROW_NUMBER() OVER (
      PARTITION BY dispatch."jobId", dispatch."sourceMessageId"
      ORDER BY
        CASE WHEN job."activeDispatchId" = dispatch."id" THEN 0 ELSE 1 END,
        CASE dispatch."state"
          WHEN 'CLAIMED' THEN 0
          WHEN 'AUTHORIZED' THEN 1
          ELSE 2
        END,
        dispatch."createdAt" DESC,
        dispatch."id" DESC
    ) AS "canonicalRank"
  FROM "JobDispatch" AS dispatch
  JOIN "Job" AS job ON job."id" = dispatch."jobId"
  WHERE dispatch."sourceMessageId" IS NOT NULL
), noncanonical AS (
  SELECT "id"
  FROM ranked
  WHERE "canonicalRank" > 1
)
UPDATE "JobDispatch" AS dispatch
SET "sourceMessageId" = NULL
FROM noncanonical
WHERE dispatch."id" = noncanonical."id";

CREATE UNIQUE INDEX "JobDispatch_jobId_sourceMessageId_key"
ON "JobDispatch"("jobId", "sourceMessageId");
