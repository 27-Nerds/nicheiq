-- CreateTable
CREATE TABLE "DiscoveryShare" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "shareToken" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "viewCount" INTEGER NOT NULL DEFAULT 0,
    "lastViewedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "DiscoveryShare_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DiscoveryVote" (
    "id" TEXT NOT NULL,
    "shareId" TEXT NOT NULL,
    "solutionName" VARCHAR(255) NOT NULL,
    "viewerToken" VARCHAR(64) NOT NULL,
    "ipHash" VARCHAR(64) NOT NULL,
    "comment" VARCHAR(500),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DiscoveryVote_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "DiscoveryShare_jobId_key" ON "DiscoveryShare"("jobId");

-- CreateIndex
CREATE UNIQUE INDEX "DiscoveryShare_shareToken_key" ON "DiscoveryShare"("shareToken");

-- CreateIndex
CREATE UNIQUE INDEX "DiscoveryVote_shareId_viewerToken_key" ON "DiscoveryVote"("shareId", "viewerToken");

-- CreateIndex
CREATE INDEX "DiscoveryVote_shareId_idx" ON "DiscoveryVote"("shareId");

-- CreateIndex
CREATE INDEX "DiscoveryVote_shareId_ipHash_idx" ON "DiscoveryVote"("shareId", "ipHash");

-- AddForeignKey
ALTER TABLE "DiscoveryShare" ADD CONSTRAINT "DiscoveryShare_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DiscoveryVote" ADD CONSTRAINT "DiscoveryVote_shareId_fkey" FOREIGN KEY ("shareId") REFERENCES "DiscoveryShare"("id") ON DELETE CASCADE ON UPDATE CASCADE;
