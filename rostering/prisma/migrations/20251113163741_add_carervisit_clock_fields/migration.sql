-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "carer_visits" ADD COLUMN     "clockInAt" TIMESTAMP(3),
ADD COLUMN     "clockOutAt" TIMESTAMP(3),
ADD COLUMN     "clockOutNote" TEXT,
ADD COLUMN     "status" "VisitStatus" NOT NULL DEFAULT 'SCHEDULED';

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
