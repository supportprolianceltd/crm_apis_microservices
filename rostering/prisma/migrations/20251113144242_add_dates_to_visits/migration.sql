-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "carer_visits" ADD COLUMN     "carePlanId" TEXT,
ADD COLUMN     "endDate" TIMESTAMP(3),
ADD COLUMN     "generatedFromCarePlan" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "startDate" TIMESTAMP(3);

-- CreateIndex
CREATE INDEX "carer_visits_carePlanId_idx" ON "carer_visits"("carePlanId");

-- CreateIndex
CREATE INDEX "carer_visits_generatedFromCarePlan_idx" ON "carer_visits"("generatedFromCarePlan");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
