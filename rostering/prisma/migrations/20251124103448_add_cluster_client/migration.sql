-- DropIndex
DROP INDEX "external_requests_id_idx";

-- CreateTable
CREATE TABLE "cluster_clients" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "clusterId" TEXT NOT NULL,
    "clientId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "cluster_clients_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "cluster_clients_tenantId_idx" ON "cluster_clients"("tenantId");

-- CreateIndex
CREATE INDEX "cluster_clients_clusterId_idx" ON "cluster_clients"("clusterId");

-- CreateIndex
CREATE INDEX "cluster_clients_clientId_idx" ON "cluster_clients"("clientId");

-- CreateIndex
CREATE UNIQUE INDEX "cluster_clients_tenantId_clusterId_clientId_key" ON "cluster_clients"("tenantId", "clusterId", "clientId");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- AddForeignKey
ALTER TABLE "cluster_clients" ADD CONSTRAINT "cluster_clients_clusterId_fkey" FOREIGN KEY ("clusterId") REFERENCES "clusters"("id") ON DELETE CASCADE ON UPDATE CASCADE;
