-- CreateEnum
CREATE TYPE "VisitAction" AS ENUM ('CLOCK_IN', 'CLOCK_OUT', 'CARETYPE_CHANGED', 'TASK_COMPLETED', 'VISIT_COMPLETED', 'VISIT_CREATED', 'VISIT_DELETED', 'ASSIGNEE_ADDED', 'ASSIGNEE_REMOVED');

-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "carer_visits" ADD COLUMN     "switchComment" TEXT,
ADD COLUMN     "switchReason" TEXT;

-- CreateTable
CREATE TABLE "client_visit_logs" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "visitId" TEXT NOT NULL,
    "action" "VisitAction" NOT NULL,
    "taskId" TEXT,
    "performedById" TEXT NOT NULL,
    "details" TEXT,
    "meta" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "client_visit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "client_visit_logs_tenantId_idx" ON "client_visit_logs"("tenantId");

-- CreateIndex
CREATE INDEX "client_visit_logs_visitId_idx" ON "client_visit_logs"("visitId");

-- CreateIndex
CREATE INDEX "client_visit_logs_action_idx" ON "client_visit_logs"("action");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
