-- Secondary artifacts and analyst prose must carry the exact candidate-pool version
-- they were derived from. Historical rows remain NULL deliberately: assigning the
-- current version would invent trust that cannot be reconstructed.
ALTER TABLE "SelectionConceptSet"
  ADD COLUMN "candidatePoolVersion" INTEGER;

ALTER TABLE "ChatMessage"
  ADD COLUMN "candidatePoolVersion" INTEGER;

ALTER TABLE "SelectionConceptSet"
  ADD CONSTRAINT "SelectionConceptSet_candidatePoolVersion_positive"
  CHECK ("candidatePoolVersion" IS NULL OR "candidatePoolVersion" > 0);

ALTER TABLE "ChatMessage"
  ADD CONSTRAINT "ChatMessage_candidatePoolVersion_positive"
  CHECK ("candidatePoolVersion" IS NULL OR "candidatePoolVersion" > 0);

-- The old live-set key treated an artifact from an obsolete pool as the cache winner
-- when the same inputs appeared again. Version is now part of artifact identity. Null
-- legacy rows are never cacheable and therefore do not reserve a trusted key.
DROP INDEX IF EXISTS "SelectionConceptSet_jobId_inputFingerprint_live_key";

CREATE UNIQUE INDEX "SelectionConceptSet_jobId_poolVersion_inputFingerprint_live_key"
  ON "SelectionConceptSet" ("jobId", "candidatePoolVersion", "inputFingerprint")
  WHERE "archivedAt" IS NULL AND "candidatePoolVersion" IS NOT NULL;

CREATE INDEX "SelectionConceptSet_jobId_poolVersion_idx"
  ON "SelectionConceptSet" ("jobId", "candidatePoolVersion");

CREATE INDEX "ChatMessage_jobId_gateStage_poolVersion_idx"
  ON "ChatMessage" ("jobId", "gateStage", "candidatePoolVersion");
