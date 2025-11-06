-- AlterTable
ALTER TABLE "external_requests" ADD COLUMN     "recurrence_pattern" TEXT,
ADD COLUMN     "required_skills" TEXT[] DEFAULT ARRAY[]::TEXT[];