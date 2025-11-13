-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "MedicalInformation" ALTER COLUMN "primaryAdditionalNotes" DROP NOT NULL,
ALTER COLUMN "secondaryAdditionalNotes" DROP NOT NULL,
ALTER COLUMN "EmergencyCareNotes" DROP NOT NULL;

-- AlterTable
ALTER TABLE "PsychologicalInformation" ALTER COLUMN "houseKeepingAdditionalNotes" DROP NOT NULL;

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
