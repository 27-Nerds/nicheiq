-- DropIndex: Remove the old 2-field unique constraint (relatedJobId, type)
-- that conflicts with the new 3-field constraint (relatedJobId, type, stage).
-- The previous migration (20260216120000) tried to drop "unique_job_transaction_type"
-- but the actual Prisma-generated index name was "CreditTransaction_relatedJobId_type_key".
DROP INDEX IF EXISTS "CreditTransaction_relatedJobId_type_key";
DROP INDEX IF EXISTS "unique_job_transaction_type";
