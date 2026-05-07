-- CreateTable
CREATE TABLE "SavedIdea" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "ideaId" TEXT NOT NULL,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SavedIdea_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SavedPainPoint" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "painPointId" TEXT NOT NULL,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SavedPainPoint_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SavedIdea_userId_createdAt_idx" ON "SavedIdea"("userId", "createdAt" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "SavedIdea_userId_ideaId_key" ON "SavedIdea"("userId", "ideaId");

-- CreateIndex
CREATE INDEX "SavedPainPoint_userId_createdAt_idx" ON "SavedPainPoint"("userId", "createdAt" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "SavedPainPoint_userId_painPointId_key" ON "SavedPainPoint"("userId", "painPointId");

-- AddForeignKey
ALTER TABLE "SavedIdea" ADD CONSTRAINT "SavedIdea_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SavedIdea" ADD CONSTRAINT "SavedIdea_ideaId_fkey" FOREIGN KEY ("ideaId") REFERENCES "CatalogIdea"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SavedPainPoint" ADD CONSTRAINT "SavedPainPoint_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SavedPainPoint" ADD CONSTRAINT "SavedPainPoint_painPointId_fkey" FOREIGN KEY ("painPointId") REFERENCES "CatalogPainPoint"("id") ON DELETE CASCADE ON UPDATE CASCADE;
