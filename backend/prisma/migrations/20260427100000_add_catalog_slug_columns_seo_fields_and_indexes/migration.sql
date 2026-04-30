-- Phase 2: Add slug columns + SEO fields + composite indexes to catalog tables.
--
-- IMPORTANT: This migration leaves slug columns nullable on CatalogIdea and
-- CatalogPainPoint so the backfill script can populate them. A follow-up
-- migration (20260427110000_enforce_catalog_slug_constraints) sets NOT NULL
-- after the backfill has run successfully in each environment.
--
-- For CatalogCategory we drop the global unique on slug and add a parent-scoped
-- unique. Top-level uniqueness (parentId IS NULL) is enforced by a partial
-- unique index because Postgres treats NULLs as distinct in regular unique
-- constraints.

-- ============================================
-- CatalogCategory: SEO fields, legacySlug, scoped uniqueness
-- ============================================

-- Drop the old globally-unique slug constraint
ALTER TABLE "CatalogCategory" DROP CONSTRAINT IF EXISTS "CatalogCategory_slug_key";
DROP INDEX IF EXISTS "CatalogCategory_slug_key";

-- Add SEO + migration columns
ALTER TABLE "CatalogCategory"
  ADD COLUMN "legacySlug" VARCHAR(120),
  ADD COLUMN "seoTitle" VARCHAR(160),
  ADD COLUMN "seoDescription" VARCHAR(320),
  ADD COLUMN "longDescription" TEXT,
  ADD COLUMN "faqJson" JSONB,
  ADD COLUMN "tags" TEXT[] NOT NULL DEFAULT '{}';

-- Backfill legacySlug from current slug so 301-redirect lookups work during migration window
UPDATE "CatalogCategory" SET "legacySlug" = "slug" WHERE "legacySlug" IS NULL;

-- Parent-scoped unique: (parentId, slug) tuple is unique
CREATE UNIQUE INDEX "CatalogCategory_parentId_slug_key" ON "CatalogCategory"("parentId", "slug");

-- Partial unique index for top-level slugs (parentId IS NULL).
-- Postgres treats NULL as distinct in regular unique indexes, so a partial
-- index with WHERE clause is required to enforce uniqueness across top-level rows.
CREATE UNIQUE INDEX "CatalogCategory_top_level_slug_unique" ON "CatalogCategory"("slug") WHERE "parentId" IS NULL;

-- Index for legacy-slug lookups during the redirect window
CREATE INDEX "CatalogCategory_legacySlug_idx" ON "CatalogCategory"("legacySlug");

-- ============================================
-- CatalogIdea: slug, format, composite indexes
-- ============================================

ALTER TABLE "CatalogIdea"
  ADD COLUMN "slug" VARCHAR(160),
  ADD COLUMN "format" VARCHAR(40);

-- Unique constraint on slug (multiple NULLs allowed by Postgres semantics — fine during backfill window)
CREATE UNIQUE INDEX "CatalogIdea_slug_key" ON "CatalogIdea"("slug");

-- Composite indexes for top-N queries on the landing page
CREATE INDEX "CatalogIdea_categoryId_createdAt_idx" ON "CatalogIdea"("categoryId", "createdAt" DESC);
CREATE INDEX "CatalogIdea_categoryId_marketFitScore_idx" ON "CatalogIdea"("categoryId", "marketFitScore" DESC);

-- ============================================
-- CatalogPainPoint: slug, composite indexes
-- ============================================

ALTER TABLE "CatalogPainPoint"
  ADD COLUMN "slug" VARCHAR(160);

CREATE UNIQUE INDEX "CatalogPainPoint_slug_key" ON "CatalogPainPoint"("slug");

CREATE INDEX "CatalogPainPoint_categoryId_createdAt_idx" ON "CatalogPainPoint"("categoryId", "createdAt" DESC);
CREATE INDEX "CatalogPainPoint_categoryId_severityScore_idx" ON "CatalogPainPoint"("categoryId", "severityScore" DESC);
