-- AlterTable: Add stage column with default
ALTER TABLE "CreditTransaction" ADD COLUMN "stage" VARCHAR(50) NOT NULL DEFAULT 'unknown';

-- Backfill existing records
UPDATE "CreditTransaction" SET stage = 'discovery' WHERE type IN ('JOB_DEDUCTION', 'REFUND') AND "relatedJobId" IS NOT NULL AND stage = 'unknown';
UPDATE "CreditTransaction" SET stage = 'purchase' WHERE type = 'PURCHASE' AND stage = 'unknown';
UPDATE "CreditTransaction" SET stage = 'promo' WHERE type = 'PROMO_REDEMPTION' AND stage = 'unknown';
UPDATE "CreditTransaction" SET stage = 'admin' WHERE type = 'ADMIN_ADJUSTMENT' AND stage = 'unknown';

-- DropIndex: Remove old unique constraint
DROP INDEX IF EXISTS "unique_job_transaction_type";

-- CreateIndex: New unique constraint including stage
CREATE UNIQUE INDEX "unique_job_stage_transaction" ON "CreditTransaction"("relatedJobId", "type", "stage");
