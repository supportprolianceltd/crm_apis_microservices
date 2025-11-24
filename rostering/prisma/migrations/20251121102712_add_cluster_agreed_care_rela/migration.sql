-- DropIndex
DROP INDEX "external_requests_id_idx";

-- CreateTable
CREATE TABLE "cluster_agreed_care_schedules" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "clusterId" TEXT NOT NULL,
    "agreedCareScheduleId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "cluster_agreed_care_schedules_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "cluster_agreed_care_schedules_tenantId_idx" ON "cluster_agreed_care_schedules"("tenantId");

-- CreateIndex
CREATE INDEX "cluster_agreed_care_schedules_clusterId_idx" ON "cluster_agreed_care_schedules"("clusterId");

-- CreateIndex
CREATE INDEX "cluster_agreed_care_schedules_agreedCareScheduleId_idx" ON "cluster_agreed_care_schedules"("agreedCareScheduleId");

-- CreateIndex
CREATE UNIQUE INDEX "cluster_agreed_care_schedules_tenantId_clusterId_agreedCare_key" ON "cluster_agreed_care_schedules"("tenantId", "clusterId", "agreedCareScheduleId");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- AddForeignKey
ALTER TABLE "cluster_agreed_care_schedules" ADD CONSTRAINT "cluster_agreed_care_schedules_clusterId_fkey" FOREIGN KEY ("clusterId") REFERENCES "clusters"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "cluster_agreed_care_schedules" ADD CONSTRAINT "cluster_agreed_care_schedules_agreedCareScheduleId_fkey" FOREIGN KEY ("agreedCareScheduleId") REFERENCES "AgreedCareSchedule"("id") ON DELETE CASCADE ON UPDATE CASCADE;
