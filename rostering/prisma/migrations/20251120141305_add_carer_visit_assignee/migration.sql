/*
  Warnings:

  - The `careType` column on the `CareRequirements` table would be dropped and recreated. This will lead to data loss if there is data in the column.

*/
-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "CareRequirements" DROP COLUMN "careType",
ADD COLUMN     "careType" "careType";

-- AlterTable
ALTER TABLE "carer_visits" ADD COLUMN     "careType" "careType";

-- CreateTable
CREATE TABLE "carer_visit_assignees" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carerVisitId" TEXT NOT NULL,
    "carerId" TEXT NOT NULL,
    "assignedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "carer_visit_assignees_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "carer_visit_assignees_tenantId_carerVisitId_idx" ON "carer_visit_assignees"("tenantId", "carerVisitId");

-- CreateIndex
CREATE UNIQUE INDEX "carer_visit_assignees_carerVisitId_carerId_key" ON "carer_visit_assignees"("carerVisitId", "carerId");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- AddForeignKey
ALTER TABLE "carer_visit_assignees" ADD CONSTRAINT "carer_visit_assignees_carerVisitId_fkey" FOREIGN KEY ("carerVisitId") REFERENCES "carer_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;
