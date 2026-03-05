-- CreateTable
CREATE TABLE "CatalogCategory" (
    "id" TEXT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "slug" VARCHAR(120) NOT NULL,
    "description" VARCHAR(500),
    "parentId" TEXT,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogCategory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CatalogIdea" (
    "id" TEXT NOT NULL,
    "categoryId" TEXT NOT NULL,
    "sourceJobId" VARCHAR(100) NOT NULL,
    "sourceNiche" TEXT NOT NULL,
    "sourceVerdict" VARCHAR(20),
    "sourceGeneratedAt" TIMESTAMP(3),
    "solutionName" VARCHAR(255) NOT NULL,
    "description" TEXT NOT NULL,
    "valueProposition" TEXT,
    "projectType" VARCHAR(100),
    "coreFeatures" JSONB,
    "targetPersonas" JSONB,
    "technicalApproach" TEXT,
    "differentiationFactors" JSONB,
    "pricingStrategy" TEXT,
    "estimatedDevTime" VARCHAR(100),
    "marketFitScore" DOUBLE PRECISION,
    "technicalFeasibility" DOUBLE PRECISION,
    "seoScalabilityScore" DOUBLE PRECISION,
    "noveltyScore" DOUBLE PRECISION,
    "soloDevFeasibility" DOUBLE PRECISION,
    "estimatedCacOrganic" VARCHAR(100),
    "estimatedIndexablePages" INTEGER,
    "programmaticSeoOpp" TEXT,
    "publishedById" VARCHAR(100) NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "isFeatured" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogIdea_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CatalogPainPoint" (
    "id" TEXT NOT NULL,
    "categoryId" TEXT NOT NULL,
    "sourceJobId" VARCHAR(100) NOT NULL,
    "sourceNiche" TEXT NOT NULL,
    "sourceGeneratedAt" TIMESTAMP(3),
    "title" VARCHAR(255) NOT NULL,
    "description" TEXT NOT NULL,
    "mentionCount" INTEGER NOT NULL DEFAULT 0,
    "severityScore" DOUBLE PRECISION NOT NULL,
    "willingnessToPayScore" DOUBLE PRECISION NOT NULL,
    "opportunityLevel" VARCHAR(20) NOT NULL,
    "representativeQuotes" JSONB,
    "sourcePlatforms" JSONB,
    "categories" JSONB,
    "affectedSegments" JSONB,
    "solutionApproach" TEXT,
    "publishedById" VARCHAR(100) NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "isFeatured" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogPainPoint_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CatalogItemCache" (
    "id" TEXT NOT NULL,
    "jobId" VARCHAR(100) NOT NULL,
    "userId" VARCHAR(100) NOT NULL,
    "niche" TEXT NOT NULL,
    "itemType" VARCHAR(20) NOT NULL,
    "itemIndex" INTEGER NOT NULL,
    "itemName" VARCHAR(255) NOT NULL,
    "itemDescription" TEXT NOT NULL,
    "itemScores" JSONB,
    "verdict" VARCHAR(20),
    "isPublished" BOOLEAN NOT NULL DEFAULT false,
    "categoryId" VARCHAR(100),
    "reportGeneratedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogItemCache_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "CatalogCategory_slug_key" ON "CatalogCategory"("slug");

-- CreateIndex
CREATE INDEX "CatalogCategory_parentId_idx" ON "CatalogCategory"("parentId");

-- CreateIndex
CREATE INDEX "CatalogCategory_isActive_sortOrder_idx" ON "CatalogCategory"("isActive", "sortOrder");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogIdea_sourceJobId_solutionName_key" ON "CatalogIdea"("sourceJobId", "solutionName");

-- CreateIndex
CREATE INDEX "CatalogIdea_categoryId_idx" ON "CatalogIdea"("categoryId");

-- CreateIndex
CREATE INDEX "CatalogIdea_sourceJobId_idx" ON "CatalogIdea"("sourceJobId");

-- CreateIndex
CREATE INDEX "CatalogIdea_isActive_idx" ON "CatalogIdea"("isActive");

-- CreateIndex
CREATE INDEX "CatalogIdea_createdAt_idx" ON "CatalogIdea"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogPainPoint_sourceJobId_title_key" ON "CatalogPainPoint"("sourceJobId", "title");

-- CreateIndex
CREATE INDEX "CatalogPainPoint_categoryId_idx" ON "CatalogPainPoint"("categoryId");

-- CreateIndex
CREATE INDEX "CatalogPainPoint_sourceJobId_idx" ON "CatalogPainPoint"("sourceJobId");

-- CreateIndex
CREATE INDEX "CatalogPainPoint_isActive_idx" ON "CatalogPainPoint"("isActive");

-- CreateIndex
CREATE INDEX "CatalogPainPoint_severityScore_idx" ON "CatalogPainPoint"("severityScore");

-- CreateIndex
CREATE INDEX "CatalogPainPoint_createdAt_idx" ON "CatalogPainPoint"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogItemCache_jobId_itemType_itemIndex_key" ON "CatalogItemCache"("jobId", "itemType", "itemIndex");

-- CreateIndex
CREATE INDEX "CatalogItemCache_userId_idx" ON "CatalogItemCache"("userId");

-- CreateIndex
CREATE INDEX "CatalogItemCache_itemType_idx" ON "CatalogItemCache"("itemType");

-- CreateIndex
CREATE INDEX "CatalogItemCache_isPublished_idx" ON "CatalogItemCache"("isPublished");

-- AddForeignKey
ALTER TABLE "CatalogCategory" ADD CONSTRAINT "CatalogCategory_parentId_fkey" FOREIGN KEY ("parentId") REFERENCES "CatalogCategory"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CatalogIdea" ADD CONSTRAINT "CatalogIdea_categoryId_fkey" FOREIGN KEY ("categoryId") REFERENCES "CatalogCategory"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CatalogPainPoint" ADD CONSTRAINT "CatalogPainPoint_categoryId_fkey" FOREIGN KEY ("categoryId") REFERENCES "CatalogCategory"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
