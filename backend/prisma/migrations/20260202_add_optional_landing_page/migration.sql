-- AlterTable: Add optional landing page generation fields
ALTER TABLE "Job" ADD COLUMN "generateLandingPage" BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE "Job" ADD COLUMN "landingPageStatus" VARCHAR(20);
