-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "chatCostUsd" DOUBLE PRECISION DEFAULT 0,
ADD COLUMN     "chatMode" BOOLEAN NOT NULL DEFAULT false;

-- CreateTable
CREATE TABLE "ChatMessage" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "gateStage" INTEGER NOT NULL,
    "role" VARCHAR(16) NOT NULL,
    "content" TEXT NOT NULL,
    "patchJson" JSONB,
    "costUsd" DOUBLE PRECISION,
    "truncated" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ChatMessage_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ChatMessage_jobId_idx" ON "ChatMessage"("jobId");

-- CreateIndex
CREATE INDEX "ChatMessage_jobId_gateStage_idx" ON "ChatMessage"("jobId", "gateStage");

-- AddForeignKey
ALTER TABLE "ChatMessage" ADD CONSTRAINT "ChatMessage_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;
