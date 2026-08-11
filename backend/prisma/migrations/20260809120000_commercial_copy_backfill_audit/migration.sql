-- Publication fence and CAS token for the Python-backed commercial-copy migration.
ALTER TABLE "JobAsset"
  ADD COLUMN "commercialCopyStatus" VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  ADD COLUMN "commercialCopySha256" VARCHAR(64),
  ADD COLUMN "commercialCopyCheckedAt" TIMESTAMP(3),
  ADD COLUMN "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE "CommercialCopyBackfillRun" (
  "id" TEXT NOT NULL,
  "contractVersion" VARCHAR(64) NOT NULL,
  "status" VARCHAR(24) NOT NULL,
  "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completedAt" TIMESTAMP(3),
  "authoritativeAssets" INTEGER NOT NULL DEFAULT 0,
  "assetsChanged" INTEGER NOT NULL DEFAULT 0,
  "assetsUnchanged" INTEGER NOT NULL DEFAULT 0,
  "assetsNotPaying" INTEGER NOT NULL DEFAULT 0,
  "assetsPartial" INTEGER NOT NULL DEFAULT 0,
  "assetsSkipped" INTEGER NOT NULL DEFAULT 0,
  "assetsConflicted" INTEGER NOT NULL DEFAULT 0,
  "chatChanged" INTEGER NOT NULL DEFAULT 0,
  "chatUnchanged" INTEGER NOT NULL DEFAULT 0,
  "chatConflicted" INTEGER NOT NULL DEFAULT 0,
  "error" TEXT,
  CONSTRAINT "CommercialCopyBackfillRun_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "CommercialCopyBackfillItem" (
  "id" SERIAL NOT NULL,
  "runId" TEXT NOT NULL,
  "targetKind" VARCHAR(24) NOT NULL,
  "targetId" VARCHAR(64) NOT NULL,
  "jobId" TEXT NOT NULL,
  "assetType" VARCHAR(32),
  "sourcePath" VARCHAR(500),
  "resultPath" VARCHAR(500),
  "sourceSha256" VARCHAR(64),
  "resultSha256" VARCHAR(64),
  "status" VARCHAR(32) NOT NULL,
  "reason" TEXT,
  "sectionResults" JSONB,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "CommercialCopyBackfillItem_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "CommercialCopyBackfillRun_contractVersion_startedAt_idx"
  ON "CommercialCopyBackfillRun"("contractVersion", "startedAt");
CREATE UNIQUE INDEX "CommercialCopyBackfillItem_runId_targetKind_targetId_key"
  ON "CommercialCopyBackfillItem"("runId", "targetKind", "targetId");
CREATE INDEX "CommercialCopyBackfillItem_jobId_idx"
  ON "CommercialCopyBackfillItem"("jobId");
ALTER TABLE "CommercialCopyBackfillItem"
  ADD CONSTRAINT "CommercialCopyBackfillItem_runId_fkey"
  FOREIGN KEY ("runId") REFERENCES "CommercialCopyBackfillRun"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

-- Old or rolling writers may not know about the publication fence. Any registered report-path
-- update therefore resets the row to PENDING. The migration/current writer explicitly stamps a
-- verified status after the registration write.
CREATE OR REPLACE FUNCTION reset_job_asset_commercial_copy_fence()
RETURNS trigger AS $$
BEGIN
  IF NEW."assetType" IN ('PREVIEW_REPORT', 'REPORT_JSON') THEN
    -- A migration run holds this key exclusively. Rolling/old writers block here before their
    -- pointer becomes authoritative; same-path rewrites are fenced too.
    PERFORM pg_advisory_xact_lock_shared(22035661553095223);
    NEW."commercialCopyStatus" := 'PENDING';
    NEW."commercialCopySha256" := NULL;
    NEW."commercialCopyCheckedAt" := NULL;
  END IF;
  IF TG_OP = 'UPDATE' THEN
    NEW."updatedAt" := clock_timestamp();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER "JobAsset_commercial_copy_fence"
BEFORE INSERT OR UPDATE OF "filePath", "fileSizeBytes" ON "JobAsset"
FOR EACH ROW EXECUTE FUNCTION reset_job_asset_commercial_copy_fence();
