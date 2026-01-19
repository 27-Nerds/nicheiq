-- CreateIndex
CREATE INDEX "CreditTransaction_relatedJobId_idx" ON "CreditTransaction"("relatedJobId");

-- AddForeignKey
ALTER TABLE "CreditTransaction" ADD CONSTRAINT "CreditTransaction_relatedJobId_fkey" FOREIGN KEY ("relatedJobId") REFERENCES "Job"("id") ON DELETE SET NULL ON UPDATE CASCADE;
