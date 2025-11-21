/*
  Warnings:

  - The values [SINGLEHANDEDCALL,DOUBLEHANDEDCALL] on the enum `careType` will be removed. If these variants are still used in the database, this will fail.

*/
-- AlterEnum
BEGIN;
CREATE TYPE "careType_new" AS ENUM ('SINGLE_HANDED_CALL', 'DOUBLE_HANDED_CALL', 'SPECIALCARE');
ALTER TYPE "careType" RENAME TO "careType_old";
ALTER TYPE "careType_new" RENAME TO "careType";
DROP TYPE "careType_old";
COMMIT;

-- DropIndex
DROP INDEX "external_requests_id_idx";

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
