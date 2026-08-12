-- Preserve whether a catalog idea's delivery surface was explicitly produced.
-- Existing rows intentionally remain NULL.
ALTER TABLE "CatalogIdea" ADD COLUMN "deliveryFormat" VARCHAR(40);
