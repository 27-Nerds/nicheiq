-- DropIndex
DROP INDEX "Job_catalogCategoryId_idx";

-- AlterTable
ALTER TABLE "CatalogIdea" ALTER COLUMN "solutionName" SET DATA TYPE TEXT,
ALTER COLUMN "projectType" SET DATA TYPE TEXT,
ALTER COLUMN "estimatedDevTime" SET DATA TYPE TEXT,
ALTER COLUMN "estimatedCacOrganic" SET DATA TYPE TEXT;

-- AlterTable
ALTER TABLE "CatalogPainPoint" ALTER COLUMN "title" SET DATA TYPE TEXT,
ALTER COLUMN "opportunityLevel" SET DATA TYPE TEXT;

-- AlterTable
ALTER TABLE "Job" ALTER COLUMN "selectedSolutions" DROP DEFAULT;

-- CreateTable
CREATE TABLE "RedditThread" (
    "id" TEXT NOT NULL,
    "postId" VARCHAR(20) NOT NULL,
    "url" VARCHAR(2048) NOT NULL,
    "title" VARCHAR(500) NOT NULL,
    "selftext" TEXT NOT NULL,
    "author" VARCHAR(100) NOT NULL,
    "subreddit" VARCHAR(50) NOT NULL,
    "score" INTEGER NOT NULL,
    "numComments" INTEGER NOT NULL,
    "comments" JSONB,
    "redditCreatedAt" TIMESTAMP(3) NOT NULL,
    "fetchedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "RedditThread_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "RedditThread_postId_key" ON "RedditThread"("postId");

-- CreateIndex
CREATE INDEX "RedditThread_subreddit_idx" ON "RedditThread"("subreddit");

-- CreateIndex
CREATE INDEX "RedditThread_fetchedAt_idx" ON "RedditThread"("fetchedAt");

-- CreateIndex
CREATE INDEX "RedditThread_redditCreatedAt_idx" ON "RedditThread"("redditCreatedAt");

-- CreateIndex
CREATE INDEX "RedditThread_score_idx" ON "RedditThread"("score");

-- RenameIndex
ALTER INDEX "unique_job_stage_transaction" RENAME TO "CreditTransaction_relatedJobId_type_stage_key";
