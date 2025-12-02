/*
  Warnings:

  - You are about to drop the column `createdAt` on the `attendance` table. All the data in the column will be lost.
  - You are about to drop the column `department` on the `attendance` table. All the data in the column will be lost.
  - You are about to drop the column `remark` on the `attendance` table. All the data in the column will be lost.
  - You are about to drop the column `role` on the `attendance` table. All the data in the column will be lost.
  - You are about to drop the column `staffName` on the `attendance` table. All the data in the column will be lost.
  - You are about to drop the column `updatedAt` on the `attendance` table. All the data in the column will be lost.

*/
-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "attendance" DROP COLUMN "createdAt",
DROP COLUMN "department",
DROP COLUMN "remark",
DROP COLUMN "role",
DROP COLUMN "staffName",
DROP COLUMN "updatedAt",
ADD COLUMN     "carerVisitId" TEXT;

-- CreateIndex
CREATE INDEX "attendance_carerVisitId_idx" ON "attendance"("carerVisitId");

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
