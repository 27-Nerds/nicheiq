-- RenameIndex: align the unique-index name on CreditTransaction with Prisma's
-- default naming convention (derived from the @@unique field list).
-- The old name ("unique_job_stage_cycle_transaction") came from an explicit
-- `map:` in the schema that was later removed; Prisma now expects the
-- auto-generated name and would re-create the index on drift.
ALTER INDEX "unique_job_stage_cycle_transaction" RENAME TO "CreditTransaction_relatedJobId_type_stage_cycle_key";
