/*
  Warnings:

  - You are about to drop the column `recurrence_pattern` on the `external_requests` table. All the data in the column will be lost.
  - You are about to drop the column `required_skills` on the `external_requests` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[from_address,to_address,mode]` on the table `travel_matrix_cache` will be added. If there are existing duplicate values, this will fail.
  - Changed the type of `startTime` on the `AgreedCareSlot` table. No cast exists, the column would be dropped and recreated, which cannot be done if there is data, since the column is required.
  - Changed the type of `endTime` on the `AgreedCareSlot` table. No cast exists, the column would be dropped and recreated, which cannot be done if there is data, since the column is required.
  - Added the required column `expires_at` to the `travel_matrix_cache` table without a default value. This is not possible if the table is not empty.

*/
-- CreateEnum
CREATE TYPE "PrecisionLevel" AS ENUM ('COORDINATES', 'ADDRESS', 'POSTCODE');

-- CreateEnum
CREATE TYPE "VisitStatus" AS ENUM ('SCHEDULED', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW');

-- DropForeignKey
ALTER TABLE "assignments" DROP CONSTRAINT "assignments_visit_id_fkey";

-- DropForeignKey
ALTER TABLE "invoice_line_items" DROP CONSTRAINT "invoice_line_items_visit_id_fkey";

-- DropForeignKey
ALTER TABLE "timesheet_entries" DROP CONSTRAINT "timesheet_entries_visit_id_fkey";

-- AlterTable
ALTER TABLE "AgreedCareSlot" DROP COLUMN "startTime",
ADD COLUMN     "startTime" TIME NOT NULL,
DROP COLUMN "endTime",
ADD COLUMN     "endTime" TIME NOT NULL;

-- AlterTable
ALTER TABLE "carers" ALTER COLUMN "skills" SET DEFAULT ARRAY[]::TEXT[],
ALTER COLUMN "languages" SET DEFAULT ARRAY[]::TEXT[];

-- AlterTable
ALTER TABLE "external_requests" DROP COLUMN "recurrence_pattern",
DROP COLUMN "required_skills",
ADD COLUMN     "approved_by_email" TEXT,
ADD COLUMN     "approved_by_first_name" TEXT,
ADD COLUMN     "approved_by_last_name" TEXT,
ADD COLUMN     "availabilityRequirements" JSONB,
ADD COLUMN     "created_by" TEXT,
ADD COLUMN     "created_by_email" TEXT,
ADD COLUMN     "created_by_first_name" TEXT,
ADD COLUMN     "created_by_last_name" TEXT,
ADD COLUMN     "recurrencePattern" TEXT,
ADD COLUMN     "requestTypes" TEXT,
ADD COLUMN     "requiredSkills" TEXT[] DEFAULT ARRAY[]::TEXT[],
ADD COLUMN     "updated_by" TEXT,
ADD COLUMN     "updated_by_email" TEXT,
ADD COLUMN     "updated_by_first_name" TEXT,
ADD COLUMN     "updated_by_last_name" TEXT;

-- AlterTable
ALTER TABLE "travel_matrix_cache" ADD COLUMN     "expires_at" TIMESTAMP(3) NOT NULL,
ADD COLUMN     "from_address" TEXT,
ADD COLUMN     "from_latitude" DOUBLE PRECISION,
ADD COLUMN     "from_longitude" DOUBLE PRECISION,
ADD COLUMN     "precision_level" "PrecisionLevel" NOT NULL DEFAULT 'POSTCODE',
ADD COLUMN     "to_address" TEXT,
ADD COLUMN     "to_latitude" DOUBLE PRECISION,
ADD COLUMN     "to_longitude" DOUBLE PRECISION;

-- CreateTable
CREATE TABLE "visits" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "external_request_id" TEXT,
    "subject" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "requestorEmail" TEXT NOT NULL,
    "requestorName" TEXT,
    "requestorPhone" TEXT,
    "address" TEXT NOT NULL,
    "postcode" TEXT NOT NULL,
    "location" geography(POINT, 4326),
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "scheduledStartTime" TIMESTAMP(3) NOT NULL,
    "scheduledEndTime" TIMESTAMP(3),
    "estimatedDuration" INTEGER,
    "recurrencePattern" TEXT,
    "urgency" "RequestUrgency" NOT NULL DEFAULT 'MEDIUM',
    "requirements" TEXT,
    "requiredSkills" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "notes" TEXT,
    "availabilityRequirements" JSONB,
    "status" "VisitStatus" NOT NULL DEFAULT 'SCHEDULED',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "assignmentStatus" "AssignmentStatus" NOT NULL DEFAULT 'PENDING',
    "assignedAt" TIMESTAMP(3),
    "travelFromPrevious" INTEGER,
    "complianceChecks" JSONB,
    "assignedCarerId" TEXT,
    "assignedCarerFirstName" TEXT,
    "assignedCarerLastName" TEXT,
    "assignedCarerEmail" TEXT,
    "assignedCarerSkills" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "assignedCarerAvailability" JSONB,
    "clusterId" TEXT,
    "created_by" TEXT,
    "created_by_email" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "visits_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "client_cluster_distances" (
    "id" TEXT NOT NULL,
    "client_postcode" TEXT NOT NULL,
    "cluster_id" TEXT NOT NULL,
    "distance_km" DOUBLE PRECISION NOT NULL,
    "last_updated" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "client_cluster_distances_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "visits_tenantId_idx" ON "visits"("tenantId");

-- CreateIndex
CREATE INDEX "visits_external_request_id_idx" ON "visits"("external_request_id");

-- CreateIndex
CREATE INDEX "visits_status_idx" ON "visits"("status");

-- CreateIndex
CREATE INDEX "visits_scheduledStartTime_idx" ON "visits"("scheduledStartTime");

-- CreateIndex
CREATE INDEX "visits_clusterId_idx" ON "visits"("clusterId");

-- CreateIndex
CREATE INDEX "visits_created_by_idx" ON "visits"("created_by");

-- CreateIndex
CREATE INDEX "client_cluster_distances_client_postcode_idx" ON "client_cluster_distances"("client_postcode");

-- CreateIndex
CREATE INDEX "client_cluster_distances_cluster_id_idx" ON "client_cluster_distances"("cluster_id");

-- CreateIndex
CREATE INDEX "client_cluster_distances_expires_at_idx" ON "client_cluster_distances"("expires_at");

-- CreateIndex
CREATE UNIQUE INDEX "client_cluster_distances_client_postcode_cluster_id_key" ON "client_cluster_distances"("client_postcode", "cluster_id");

-- CreateIndex
CREATE INDEX "external_requests_created_by_idx" ON "external_requests"("created_by");

-- CreateIndex
CREATE INDEX "external_requests_approvedBy_idx" ON "external_requests"("approvedBy");

-- CreateIndex
CREATE INDEX "external_requests_updated_by_idx" ON "external_requests"("updated_by");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);

-- CreateIndex
CREATE INDEX "travel_matrix_cache_from_postcode_to_postcode_idx" ON "travel_matrix_cache"("from_postcode", "to_postcode");

-- CreateIndex
CREATE INDEX "travel_matrix_cache_expires_at_idx" ON "travel_matrix_cache"("expires_at");

-- CreateIndex
CREATE UNIQUE INDEX "travel_matrix_cache_from_address_to_address_mode_key" ON "travel_matrix_cache"("from_address", "to_address", "mode");

-- AddForeignKey
ALTER TABLE "visits" ADD CONSTRAINT "visits_external_request_id_fkey" FOREIGN KEY ("external_request_id") REFERENCES "external_requests"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "visits" ADD CONSTRAINT "visits_clusterId_fkey" FOREIGN KEY ("clusterId") REFERENCES "clusters"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assignments" ADD CONSTRAINT "assignments_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "visit_check_ins" ADD CONSTRAINT "visit_check_ins_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "visit_check_outs" ADD CONSTRAINT "visit_check_outs_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "lateness_alerts" ADD CONSTRAINT "lateness_alerts_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "incidents" ADD CONSTRAINT "incidents_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_cluster_distances" ADD CONSTRAINT "client_cluster_distances_cluster_id_fkey" FOREIGN KEY ("cluster_id") REFERENCES "clusters"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "timesheet_entries" ADD CONSTRAINT "timesheet_entries_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_line_items" ADD CONSTRAINT "invoice_line_items_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "visits"("id") ON DELETE SET NULL ON UPDATE CASCADE;
