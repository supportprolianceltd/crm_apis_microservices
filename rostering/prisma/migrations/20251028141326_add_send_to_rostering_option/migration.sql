/*
  Warnings:

  - Added the required column `sendToRostering` to the `external_requests` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "external_requests" ADD COLUMN     "sendToRostering" BOOLEAN NOT NULL;
