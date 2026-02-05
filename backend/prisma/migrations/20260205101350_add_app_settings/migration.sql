-- AlterTable
ALTER TABLE "Job" ALTER COLUMN "generateLandingPage" SET DEFAULT false;

-- CreateTable
CREATE TABLE "AppSettings" (
    "key" VARCHAR(100) NOT NULL,
    "value" TEXT NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "updatedBy" TEXT,

    CONSTRAINT "AppSettings_pkey" PRIMARY KEY ("key")
);
