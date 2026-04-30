# Catalog slug + SEO fields migration

Adds nullable slug columns + SEO fields + composite indexes to support the public catalog SEO restructure (URL migration `/catalog/*` → `/ideas/*`).

## Apply order

1. **Apply this migration** (`prisma migrate deploy` or equivalent).
2. **Run the backfill script** to populate slugs:

   ```bash
   cd backend
   npx tsx scripts/migrateCatalogSlugs.ts
   ```

   The script is idempotent — safe to re-run if it fails partway.

3. **Verify backfill completed**:

   ```sql
   SELECT count(*) FROM "CatalogIdea" WHERE slug IS NULL;       -- expect 0
   SELECT count(*) FROM "CatalogPainPoint" WHERE slug IS NULL;  -- expect 0
   ```

4. **Apply follow-up migration** `20260427110000_enforce_catalog_slug_constraints` (will be added in a separate step) to set the slug columns NOT NULL. Do NOT apply that migration before backfill completes or the migration will fail.

## What this migration does

- Drops global `@unique` on `CatalogCategory.slug`; replaces with parent-scoped `@@unique([parentId, slug])` plus a partial unique index for top-level rows (where `parentId IS NULL`). Enables nested URLs like `/ideas/saas/b2b-tools` where `b2b-tools` can also exist under another parent.
- Backfills `CatalogCategory.legacySlug` with the current `slug` value so 301-redirect lookups for legacy `/catalog/categories/{old-slug}` URLs continue to work during the migration window.
- Adds SEO fields to `CatalogCategory`: `seoTitle`, `seoDescription`, `longDescription`, `faqJson`, `tags`.
- Adds `slug` (nullable) + `format` to `CatalogIdea`. Adds composite indexes for top-N queries on `(categoryId, createdAt DESC)` and `(categoryId, marketFitScore DESC)`.
- Adds `slug` (nullable) to `CatalogPainPoint`. Adds composite indexes on `(categoryId, createdAt DESC)` and `(categoryId, severityScore DESC)`.
