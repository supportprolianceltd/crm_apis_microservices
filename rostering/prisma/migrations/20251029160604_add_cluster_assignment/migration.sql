-- CreateTable
CREATE TABLE "ClusterAssignment" (
    "id" TEXT NOT NULL,
    "carerId" TEXT NOT NULL,
    "clusterId" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "assignedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ClusterAssignment_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ClusterAssignment_carerId_idx" ON "ClusterAssignment"("carerId");

-- CreateIndex
CREATE INDEX "ClusterAssignment_clusterId_idx" ON "ClusterAssignment"("clusterId");

-- CreateIndex
CREATE INDEX "ClusterAssignment_tenantId_idx" ON "ClusterAssignment"("tenantId");

-- CreateIndex
CREATE INDEX "ClusterAssignment_assignedAt_idx" ON "ClusterAssignment"("assignedAt");

-- CreateIndex
CREATE UNIQUE INDEX "ClusterAssignment_carerId_tenantId_key" ON "ClusterAssignment"("carerId", "tenantId");

-- AddForeignKey
ALTER TABLE "ClusterAssignment" ADD CONSTRAINT "ClusterAssignment_clusterId_fkey" FOREIGN KEY ("clusterId") REFERENCES "clusters"("id") ON DELETE CASCADE ON UPDATE CASCADE;
