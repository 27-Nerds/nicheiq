-- Persist the model/cost provenance for analyst turns and make mutation follow-ups
-- idempotent across worker callback retries.
ALTER TABLE "ChatMessage"
  ADD COLUMN "model" VARCHAR(100),
  ADD COLUMN "origin" VARCHAR(40),
  ADD COLUMN "operationId" VARCHAR(64),
  ADD COLUMN "inputTokens" INTEGER,
  ADD COLUMN "outputTokens" INTEGER,
  ADD COLUMN "cacheWriteTokens" INTEGER,
  ADD COLUMN "cacheReadTokens" INTEGER;

CREATE UNIQUE INDEX "ChatMessage_operationId_key" ON "ChatMessage"("operationId");
