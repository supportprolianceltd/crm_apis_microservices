-- CreateEnum
CREATE TYPE "EntryStatus" AS ENUM ('EARLY_ENTRY', 'LATE_ENTRY', 'ON_TIME');

-- CreateEnum
CREATE TYPE "ExitStatus" AS ENUM ('EARLY_EXIT', 'LATE_EXIT', 'ON_TIME');

-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "attendance" ADD COLUMN     "entryStatus" "EntryStatus",
ADD COLUMN     "exitStatus" "ExitStatus";

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
