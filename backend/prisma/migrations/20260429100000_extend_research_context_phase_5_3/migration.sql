-- Phase 5.3: extend CatalogResearchContext with fields needed by the
-- Competitors (unlocked) and GTM Playbook + Monetization Strategy (locked)
-- sections on catalog detail pages. All NULL-allowed — non-breaking add.
-- Backfill via `npx tsx scripts/backfillResearchContexts.ts --force-refresh`
-- to populate existing rows from report.json.

ALTER TABLE "CatalogResearchContext"
    ADD COLUMN "competitiveAnalysis"   JSONB,
    ADD COLUMN "competitiveSummary"    TEXT,
    ADD COLUMN "goToMarketBlueprint"   JSONB,
    ADD COLUMN "pricingStrategy"       JSONB,
    ADD COLUMN "trafficMonetization"   JSONB;
