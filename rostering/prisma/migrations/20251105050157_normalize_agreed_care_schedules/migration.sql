-- CreateEnum
CREATE TYPE "DayOfWeek" AS ENUM ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY');

-- CreateTable
CREATE TABLE "AgreedCareSchedule" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "careRequirementsId" TEXT NOT NULL,
    "day" "DayOfWeek" NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT false,
    "lunchStart" TEXT,
    "lunchEnd" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AgreedCareSchedule_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AgreedCareSlot" (
    "id" TEXT NOT NULL,
    "scheduleId" TEXT NOT NULL,
    "startTime" TEXT NOT NULL,
    "endTime" TEXT NOT NULL,
    "externalId" TEXT,
    "position" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AgreedCareSlot_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AgreedCareSchedule_tenantId_idx" ON "AgreedCareSchedule"("tenantId");

-- CreateIndex
CREATE INDEX "AgreedCareSchedule_careRequirementsId_idx" ON "AgreedCareSchedule"("careRequirementsId");

-- CreateIndex
CREATE UNIQUE INDEX "AgreedCareSchedule_careRequirementsId_day_key" ON "AgreedCareSchedule"("careRequirementsId", "day");

-- CreateIndex
CREATE INDEX "AgreedCareSlot_scheduleId_idx" ON "AgreedCareSlot"("scheduleId");

-- AddForeignKey
ALTER TABLE "AgreedCareSchedule" ADD CONSTRAINT "AgreedCareSchedule_careRequirementsId_fkey" FOREIGN KEY ("careRequirementsId") REFERENCES "CareRequirements"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgreedCareSlot" ADD CONSTRAINT "AgreedCareSlot_scheduleId_fkey" FOREIGN KEY ("scheduleId") REFERENCES "AgreedCareSchedule"("id") ON DELETE CASCADE ON UPDATE CASCADE;
