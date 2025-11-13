-- CreateEnum
CREATE TYPE "careType" AS ENUM ('SINGLEHANDEDCALL', 'DOUBLEHANDEDCALL', 'SPECIALCARE');

-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "EverydayActivityPlan" ALTER COLUMN "additionalNotes" DROP NOT NULL;

-- AlterTable
ALTER TABLE "FallsAndMobility" ALTER COLUMN "mobilityAdditionalNotes" DROP NOT NULL,
ALTER COLUMN "sensoryAdditionalNotes" DROP NOT NULL;

-- AlterTable
ALTER TABLE "PersonalCare" ALTER COLUMN "additionalNotes" DROP NOT NULL;

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
