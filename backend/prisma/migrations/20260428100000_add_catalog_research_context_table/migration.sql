-- Phase 5 Migration A: CatalogResearchContext table + indexes only.
--
-- Persisted projection of source-job report.json data, keyed by sourceJobId.
-- The DB row IS the public-safe projection — anything not projected here cannot
-- leak through the public catalog API.
--
-- This migration adds the table standalone. No FK relations are added on
-- CatalogIdea / CatalogPainPoint yet — the backfill script must populate a row
-- for every distinct sourceJobId across both tables BEFORE Migration B
-- (20260428110000_add_catalog_research_context_relations) lands the required FKs.

CREATE TABLE "CatalogResearchContext" (
    "sourceJobId"            VARCHAR(100) NOT NULL,
    "audienceMapping"        JSONB,
    "marketSizing"           JSONB,
    "trendLongevity"         JSONB,
    "painPointAnalytics"     JSONB,
    "competitiveAnalytics"   JSONB,
    "competitorProfiles"     JSONB,
    "detailedPainPoints"     JSONB,
    "alternativeSolutions"   JSONB,
    "selectedSolution"       JSONB,
    "selectedSolutionName"   TEXT,
    "redditPostsAnalyzed"    INTEGER,
    "redditCommentsAnalyzed" INTEGER,
    "twitterThreadsAnalyzed" INTEGER,
    "genericPostsAnalyzed"   INTEGER,
    "topSubreddits"          JSONB,
    "collectionDate"         TIMESTAMP(3),
    "dataQualityTier"        VARCHAR(20),
    "goNoGoVerdict"          VARCHAR(20),
    "extractedAt"            TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reportGeneratedAt"      TIMESTAMP(3),

    CONSTRAINT "CatalogResearchContext_pkey" PRIMARY KEY ("sourceJobId")
);

CREATE INDEX "CatalogResearchContext_dataQualityTier_idx" ON "CatalogResearchContext"("dataQualityTier");
CREATE INDEX "CatalogResearchContext_reportGeneratedAt_idx" ON "CatalogResearchContext"("reportGeneratedAt");
