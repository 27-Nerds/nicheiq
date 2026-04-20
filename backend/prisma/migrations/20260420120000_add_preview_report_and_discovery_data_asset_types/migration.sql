-- AlterEnum: add the two asset types used by the Phase-1 preview / discovery-data pipeline.
-- These values were added to schema.prisma via `prisma db push` during development
-- but no migration file was committed, so prod's enum was missing them. Prisma queries
-- that filter by these values failed with "invalid input value for enum" on prod.
ALTER TYPE "AssetType" ADD VALUE 'DISCOVERY_DATA';
ALTER TYPE "AssetType" ADD VALUE 'PREVIEW_REPORT';
