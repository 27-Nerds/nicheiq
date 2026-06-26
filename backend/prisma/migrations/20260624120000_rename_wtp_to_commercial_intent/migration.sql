-- Rename CatalogPainPoint.willingnessToPayScore -> commercialIntentScore.
-- Data-preserving column rename (the score is now an ordinal "commercial intent"
-- buying-signal, not a calibrated willingness-to-pay; see help/methodology).
ALTER TABLE "CatalogPainPoint" RENAME COLUMN "willingnessToPayScore" TO "commercialIntentScore";
