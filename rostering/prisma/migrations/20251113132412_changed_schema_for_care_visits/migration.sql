-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "carer_visits" ADD COLUMN     "assignedAt" TIMESTAMP(3),
ALTER COLUMN "carerId" DROP NOT NULL;

-- AlterTable
ALTER TABLE "tasks" ADD COLUMN     "pushToVisit" BOOLEAN NOT NULL DEFAULT false;

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- CreateIndex
CREATE INDEX "tasks_carerId_idx" ON "tasks"("carerId");
