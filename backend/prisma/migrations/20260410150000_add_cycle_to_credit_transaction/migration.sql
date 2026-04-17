-- Add cycle column for resume attempt tracking
-- Replaces the resume_ prefix naming hack in stage column

-- Step 1: Add cycle column (instant in PG11+, no table rewrite)
ALTER TABLE "CreditTransaction" ADD COLUMN "cycle" INT NOT NULL DEFAULT 0;

-- Step 2: Drop old unique constraint BEFORE backfill
-- (backfill renames resume_discovery → discovery, which would violate old constraint)
DROP INDEX "CreditTransaction_relatedJobId_type_stage_key";

-- Step 3: Backfill resume_ prefixed records (consistent anchored regex)
UPDATE "CreditTransaction"
SET
  cycle = (length(stage) - length(regexp_replace(stage, '^(resume_)+', ''))) / 7,
  stage = regexp_replace(stage, '^(resume_)+', '')
WHERE stage LIKE 'resume_%';

-- Step 4: Safety check — abort if backfill created duplicates
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "CreditTransaction"
    WHERE "relatedJobId" IS NOT NULL
    GROUP BY "relatedJobId", "type", stage, cycle
    HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'Duplicate (relatedJobId, type, stage, cycle) tuples after backfill';
  END IF;
END $$;

-- Step 5: Create new unique index
CREATE UNIQUE INDEX "unique_job_stage_cycle_transaction"
  ON "CreditTransaction"("relatedJobId", "type", "stage", "cycle");

-- Step 6: Drop redundant single-column index (covered by new composite)
DROP INDEX IF EXISTS "CreditTransaction_relatedJobId_idx";
