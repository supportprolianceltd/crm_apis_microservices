-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "carer_visits" ADD COLUMN     "clientId" TEXT;

-- AlterTable
ALTER TABLE "visits" ADD COLUMN     "clientId" TEXT;

-- CreateIndex
CREATE INDEX "carer_visits_clientId_idx" ON "carer_visits"("clientId");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- CreateIndex
CREATE INDEX "visits_clientId_idx" ON "visits"("clientId");
