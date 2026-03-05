-- AlterTable
ALTER TABLE "TokenPackage" ADD COLUMN "tagline" VARCHAR(200);
ALTER TABLE "TokenPackage" ADD COLUMN "includesLabel" VARCHAR(200);
ALTER TABLE "TokenPackage" ADD COLUMN "features" JSONB;
ALTER TABLE "TokenPackage" ADD COLUMN "ctaText" VARCHAR(100);
ALTER TABLE "TokenPackage" ADD COLUMN "badgeLabel" VARCHAR(50);
ALTER TABLE "TokenPackage" ADD COLUMN "promoLine" VARCHAR(200);
ALTER TABLE "TokenPackage" ADD COLUMN "promoPriceInCents" INTEGER;
ALTER TABLE "TokenPackage" ADD COLUMN "promoBadge" VARCHAR(50);
ALTER TABLE "TokenPackage" ADD COLUMN "ctaSubText" VARCHAR(100);
ALTER TABLE "TokenPackage" ADD COLUMN "ctaSubUrl" VARCHAR(500);
