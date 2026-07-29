-- `SelectionConceptSet.archivedAt` reached databases through `prisma db push` and was
-- never captured in a migration: the table's only prior migration
-- (20260715220000_add_idea_selection_decision_lab) creates it without the column. Any
-- database rebuilt from history alone — a shadow database, CI, a fresh environment —
-- therefore lacks it, and `migrate dev` fails here with "column archivedAt does not
-- exist". Backfilled idempotently, so already-pushed databases are unaffected.
ALTER TABLE "SelectionConceptSet"
  ADD COLUMN IF NOT EXISTS "archivedAt" TIMESTAMP(3);

-- A discarded concept set used to keep its fingerprint reserved, so asking for the same
-- directions again revived the exact artifact the user had just thrown away — "Discard
-- this set" could not be followed by "generate different options".
--
-- Uniqueness should only ever have covered LIVE sets: at most one un-archived set per
-- (job, input fingerprint). Archived rows keep their fingerprint for provenance but no
-- longer block a fresh generation for the same inputs.
--
-- Prisma cannot express a partial unique index, so it is not declared in schema.prisma
-- and `prisma migrate dev` will offer to drop it. Keep it.
DROP INDEX IF EXISTS "SelectionConceptSet_jobId_inputFingerprint_key";

CREATE UNIQUE INDEX IF NOT EXISTS "SelectionConceptSet_jobId_inputFingerprint_live_key"
  ON "SelectionConceptSet" ("jobId", "inputFingerprint")
  WHERE "archivedAt" IS NULL;
