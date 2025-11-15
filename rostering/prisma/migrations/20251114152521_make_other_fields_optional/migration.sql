-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "BodyMap" ALTER COLUMN "initialClinicalObservations" DROP NOT NULL,
ALTER COLUMN "initialSkinIntegrity" DROP NOT NULL;

-- AlterTable
ALTER TABLE "CultureValues" ALTER COLUMN "receivesInformalCare" DROP NOT NULL,
ALTER COLUMN "receivesFormalCare" DROP NOT NULL,
ALTER COLUMN "mentalWellbeingTracking" DROP NOT NULL;

-- AlterTable
ALTER TABLE "FoodNutritionHydration" ALTER COLUMN "foodOrDrinkAllergies" DROP NOT NULL;

-- AlterTable
ALTER TABLE "LegalRequirement" ALTER COLUMN "attorneyInPlace" DROP NOT NULL;

-- AlterTable
ALTER TABLE "MovingHandling" ALTER COLUMN "behaviouralChanges" DROP NOT NULL,
ALTER COLUMN "walkIndependently" DROP NOT NULL,
ALTER COLUMN "manageStairs" DROP NOT NULL,
ALTER COLUMN "limitedSittingBalance" DROP NOT NULL,
ALTER COLUMN "turnInBed" DROP NOT NULL,
ALTER COLUMN "lyingToSittingDependence" DROP NOT NULL,
ALTER COLUMN "chairToCommodeOrBed" DROP NOT NULL,
ALTER COLUMN "profilingBedAndMattress" DROP NOT NULL,
ALTER COLUMN "EvacuationPlanRequired" DROP NOT NULL;

-- AlterTable
ALTER TABLE "RoutinePreference" ALTER COLUMN "haveJob" DROP NOT NULL,
ALTER COLUMN "haveImportantPerson" DROP NOT NULL,
ALTER COLUMN "significantPersonHasLocation" DROP NOT NULL,
ALTER COLUMN "haveSpecificImportantRoutine" DROP NOT NULL,
ALTER COLUMN "haveDislikes" DROP NOT NULL,
ALTER COLUMN "haveHobbiesRoutines" DROP NOT NULL;

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
