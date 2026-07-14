-- AlterEnum
ALTER TYPE "DispatchKind" ADD VALUE 'SEED_IDEA';

-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "seedIdeaCount" INTEGER NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "JobDispatch" ADD COLUMN     "seedOrdinal" INTEGER,
ADD COLUMN     "sourceMessageId" VARCHAR(64);
