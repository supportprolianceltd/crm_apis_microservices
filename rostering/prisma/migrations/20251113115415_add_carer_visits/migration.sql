-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "tasks" ADD COLUMN     "carerId" TEXT,
ADD COLUMN     "carerVisitId" TEXT;

-- CreateTable
CREATE TABLE "carer_visits" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carerId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "carer_visits_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "carer_visits_tenantId_idx" ON "carer_visits"("tenantId");

-- CreateIndex
CREATE INDEX "carer_visits_carerId_idx" ON "carer_visits"("carerId");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- CreateIndex
CREATE INDEX "tasks_carerVisitId_idx" ON "tasks"("carerVisitId");

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_carerVisitId_fkey" FOREIGN KEY ("carerVisitId") REFERENCES "carer_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;
