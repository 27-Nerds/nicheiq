-- Repair links that an older backend left active after Deep Research authorization.
-- Runtime revocation now happens atomically with the Job status flip, charge and dispatch.
UPDATE "DiscoveryShare" AS share
SET
  "isActive" = false,
  "updatedAt" = CURRENT_TIMESTAMP
FROM "Job" AS job
WHERE share."jobId" = job."id"
  AND share."isActive" = true
  AND (
    cardinality(job."selectedSolutions") > 0
    OR job."selectedSolutionRefs" IS NOT NULL
    OR EXISTS (
      SELECT 1
      FROM "JobDispatch" AS dispatch
      WHERE dispatch."jobId" = job."id"
        AND dispatch."kind" = 'DEEP_RESEARCH'
    )
  );
