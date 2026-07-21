CREATE TABLE "DiscoveryAnnotationDocument" (
    "jobId" TEXT NOT NULL,
    "document" JSONB NOT NULL,
    "revision" INTEGER NOT NULL DEFAULT 1,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "DiscoveryAnnotationDocument_pkey" PRIMARY KEY ("jobId")
);

ALTER TABLE "DiscoveryAnnotationDocument"
ADD CONSTRAINT "DiscoveryAnnotationDocument_jobId_fkey"
FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

