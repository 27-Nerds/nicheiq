-- CreateTable
CREATE TABLE "TokenPackage" (
    "id" TEXT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "description" VARCHAR(500),
    "credits" INTEGER NOT NULL,
    "priceInCents" INTEGER NOT NULL,
    "stripePriceId" VARCHAR(255) NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "isPopular" BOOLEAN NOT NULL DEFAULT false,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "TokenPackage_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "TokenPackage_stripePriceId_key" ON "TokenPackage"("stripePriceId");

-- CreateIndex
CREATE INDEX "TokenPackage_isActive_idx" ON "TokenPackage"("isActive");

-- CreateIndex
CREATE INDEX "TokenPackage_sortOrder_idx" ON "TokenPackage"("sortOrder");
