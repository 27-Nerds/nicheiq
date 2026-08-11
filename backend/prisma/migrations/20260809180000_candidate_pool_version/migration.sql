-- Existing jobs and preview assets intentionally remain NULL. Their historical candidate
-- binding cannot be reconstructed safely, so CurrentSelectionContext treats them as legacy
-- and withholds run-level framing until a future pool write and preview publication bind them.
ALTER TABLE "Job" ADD COLUMN "candidatePoolVersion" INTEGER;
ALTER TABLE "JobAsset" ADD COLUMN "candidatePoolVersion" INTEGER;

-- Job.candidatePoolVersion is database-owned. Every INSERT/UPDATE passes through this
-- function, so ORM, raw SQL, scripts, and future writers cannot change solutionIdeas without
-- advancing the version or forge a version independently of the candidate payload.
CREATE OR REPLACE FUNCTION "set_job_candidate_pool_version"()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW."solutionIdeas" IS NOT NULL THEN
      NEW."candidatePoolVersion" := 1;
    ELSE
      NEW."candidatePoolVersion" := NULL;
    END IF;
  ELSIF NEW."solutionIdeas" IS DISTINCT FROM OLD."solutionIdeas" THEN
    NEW."candidatePoolVersion" := COALESCE(OLD."candidatePoolVersion", 0) + 1;
  ELSE
    NEW."candidatePoolVersion" := OLD."candidatePoolVersion";
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "Job_candidate_pool_version_on_insert"
BEFORE INSERT ON "Job"
FOR EACH ROW
EXECUTE FUNCTION "set_job_candidate_pool_version"();

CREATE TRIGGER "Job_candidate_pool_version_on_update"
BEFORE UPDATE OF "solutionIdeas", "candidatePoolVersion" ON "Job"
FOR EACH ROW
EXECUTE FUNCTION "set_job_candidate_pool_version"();

-- Preview publication binds the materialized artifact to the exact current candidate pool.
-- UPDATE OF also fires for an upsert that republishes the same path, while hash changes cover
-- in-place rewrites made by regeneration and seed completion.
CREATE OR REPLACE FUNCTION "bind_preview_asset_candidate_pool_version"()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW."assetType" = 'PREVIEW_REPORT' THEN
    SELECT "candidatePoolVersion"
      INTO NEW."candidatePoolVersion"
      FROM "Job"
      WHERE "id" = NEW."jobId";
  ELSE
    NEW."candidatePoolVersion" := NULL;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "JobAsset_preview_candidate_pool_version"
BEFORE INSERT OR UPDATE OF "filePath", "fileSizeBytes", "commercialCopySha256" ON "JobAsset"
FOR EACH ROW
EXECUTE FUNCTION "bind_preview_asset_candidate_pool_version"();
