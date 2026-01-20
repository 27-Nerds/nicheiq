-- CreateIndex
CREATE UNIQUE INDEX "CreditTransaction_relatedJobId_type_key" ON "CreditTransaction"("relatedJobId", "type");
