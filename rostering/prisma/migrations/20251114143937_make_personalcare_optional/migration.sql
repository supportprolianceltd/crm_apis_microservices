-- DropIndex
DROP INDEX "external_requests_id_idx";

-- AlterTable
ALTER TABLE "BodyMap" ALTER COLUMN "visitFrequency" DROP NOT NULL,
ALTER COLUMN "carePlanReviewDate" DROP NOT NULL,
ALTER COLUMN "invoicingCycle" DROP NOT NULL,
ALTER COLUMN "fundingAndInsuranceDetails" DROP NOT NULL,
ALTER COLUMN "assignedCareManager" DROP NOT NULL,
ALTER COLUMN "type" DROP NOT NULL,
ALTER COLUMN "size" DROP NOT NULL,
ALTER COLUMN "locationDescription" DROP NOT NULL,
ALTER COLUMN "dateFirstObserved" DROP NOT NULL,
ALTER COLUMN "weight" DROP NOT NULL,
ALTER COLUMN "height" DROP NOT NULL;

-- AlterTable
ALTER TABLE "CareRequirements" ALTER COLUMN "careType" DROP NOT NULL;

-- AlterTable
ALTER TABLE "CultureValues" ALTER COLUMN "religiousBackground" DROP NOT NULL,
ALTER COLUMN "ethnicGroup" DROP NOT NULL,
ALTER COLUMN "culturalAccommodation" DROP NOT NULL,
ALTER COLUMN "sexualityandRelationshipPreferences" DROP NOT NULL,
ALTER COLUMN "sexImpartingCareNeeds" DROP NOT NULL,
ALTER COLUMN "preferredLanguage" DROP NOT NULL,
ALTER COLUMN "preferredMethodOfCommunication" DROP NOT NULL,
ALTER COLUMN "keyFamilyMembers" DROP NOT NULL,
ALTER COLUMN "specifyConcernsOnInformalCare" DROP NOT NULL,
ALTER COLUMN "socialGroupAndCommunity" DROP NOT NULL;

-- AlterTable
ALTER TABLE "EverydayActivityPlan" ALTER COLUMN "canTheyShop" DROP NOT NULL,
ALTER COLUMN "canTheyCall" DROP NOT NULL,
ALTER COLUMN "canTheyWash" DROP NOT NULL,
ALTER COLUMN "communityAccessNeeds" DROP NOT NULL,
ALTER COLUMN "ExerciseandMobilityActivities" DROP NOT NULL;

-- AlterTable
ALTER TABLE "FallsAndMobility" ALTER COLUMN "timesFallen" DROP NOT NULL,
ALTER COLUMN "mobilityLevel" DROP NOT NULL,
ALTER COLUMN "mobilitySupport" DROP NOT NULL,
ALTER COLUMN "activeAsTheyLikeToBe" DROP NOT NULL,
ALTER COLUMN "canTransfer" DROP NOT NULL,
ALTER COLUMN "canuseStairs" DROP NOT NULL,
ALTER COLUMN "canTravelAlone" DROP NOT NULL,
ALTER COLUMN "visionStatus" DROP NOT NULL,
ALTER COLUMN "speechStatus" DROP NOT NULL,
ALTER COLUMN "hearingStatus" DROP NOT NULL;

-- AlterTable
ALTER TABLE "FoodNutritionHydration" ALTER COLUMN "dietaryRequirements" DROP NOT NULL,
ALTER COLUMN "foodAllergiesSpecification" DROP NOT NULL,
ALTER COLUMN "allergiesImpact" DROP NOT NULL,
ALTER COLUMN "favouriteFoods" DROP NOT NULL,
ALTER COLUMN "foodTextures" DROP NOT NULL,
ALTER COLUMN "appetiteLevel" DROP NOT NULL,
ALTER COLUMN "swallowingDifficulties" DROP NOT NULL,
ALTER COLUMN "medicationsAffectingSwallowing" DROP NOT NULL,
ALTER COLUMN "specifyMedicationsAffectingSwallowing" DROP NOT NULL,
ALTER COLUMN "canFeedSelf" DROP NOT NULL,
ALTER COLUMN "canPrepareLightMeals" DROP NOT NULL,
ALTER COLUMN "canCookMeals" DROP NOT NULL,
ALTER COLUMN "clientFoodGiver" DROP NOT NULL,
ALTER COLUMN "mealtimeSupport" DROP NOT NULL,
ALTER COLUMN "hydrationSchedule" DROP NOT NULL,
ALTER COLUMN "strongDislikes" DROP NOT NULL,
ALTER COLUMN "fluidPreferences" DROP NOT NULL;

-- AlterTable
ALTER TABLE "LegalRequirement" ALTER COLUMN "attorneyType" DROP NOT NULL,
ALTER COLUMN "attorneyName" DROP NOT NULL,
ALTER COLUMN "attorneyContact" DROP NOT NULL,
ALTER COLUMN "attorneyEmail" DROP NOT NULL,
ALTER COLUMN "solicitor" DROP NOT NULL,
ALTER COLUMN "certificateNumber" DROP NOT NULL;

-- AlterTable
ALTER TABLE "MedicalInformation" ALTER COLUMN "primaryDiagnosis" DROP NOT NULL,
ALTER COLUMN "secondaryDiagnoses" DROP NOT NULL,
ALTER COLUMN "pastMedicalHistory" DROP NOT NULL,
ALTER COLUMN "breathingSupportNeed" DROP NOT NULL,
ALTER COLUMN "airWayEquipmentMitigationPlan" DROP NOT NULL,
ALTER COLUMN "currentHealthStatus" DROP NOT NULL,
ALTER COLUMN "primaryDoctor" DROP NOT NULL,
ALTER COLUMN "supportContactPhone" DROP NOT NULL,
ALTER COLUMN "specialistContact" DROP NOT NULL,
ALTER COLUMN "HospitalContact" DROP NOT NULL;

-- AlterTable
ALTER TABLE "MovingHandling" ALTER COLUMN "equipmentsNeeds" DROP NOT NULL,
ALTER COLUMN "anyPainDuringRestingAndMovement" DROP NOT NULL,
ALTER COLUMN "anyCognitiveImpairment" DROP NOT NULL,
ALTER COLUMN "describeBehaviouralChanges" DROP NOT NULL,
ALTER COLUMN "sittingToStandingDependence" DROP NOT NULL,
ALTER COLUMN "gettingUpFromChairDependence" DROP NOT NULL,
ALTER COLUMN "bathOrShower" DROP NOT NULL,
ALTER COLUMN "riskManagementPlan" DROP NOT NULL,
ALTER COLUMN "locationRiskReview" DROP NOT NULL,
ALTER COLUMN "dailyGoal" DROP NOT NULL;

-- AlterTable
ALTER TABLE "PersonalCare" ALTER COLUMN "bathingAndShowering" DROP NOT NULL,
ALTER COLUMN "oralHygiene" DROP NOT NULL,
ALTER COLUMN "maintainThemselves" DROP NOT NULL,
ALTER COLUMN "dressThemselves" DROP NOT NULL,
ALTER COLUMN "toiletUsage" DROP NOT NULL,
ALTER COLUMN "bowelControl" DROP NOT NULL,
ALTER COLUMN "bladderControl" DROP NOT NULL,
ALTER COLUMN "toiletingSupport" DROP NOT NULL,
ALTER COLUMN "continenceCare" DROP NOT NULL,
ALTER COLUMN "mobilityAssistance" DROP NOT NULL,
ALTER COLUMN "preferredLanguage" DROP NOT NULL,
ALTER COLUMN "communicationStyleNeeds" DROP NOT NULL;

-- AlterTable
ALTER TABLE "PsychologicalInformation" ALTER COLUMN "healthLevelSatisfaction" DROP NOT NULL,
ALTER COLUMN "healthMotivationalLevel" DROP NOT NULL,
ALTER COLUMN "sleepMood" DROP NOT NULL,
ALTER COLUMN "specifySleepMood" DROP NOT NULL,
ALTER COLUMN "sleepStatus" DROP NOT NULL,
ALTER COLUMN "memoryStatus" DROP NOT NULL,
ALTER COLUMN "specifyMemoryStatus" DROP NOT NULL,
ALTER COLUMN "canTheyDoHouseKeeping" DROP NOT NULL;

-- AlterTable
ALTER TABLE "RoutinePreference" ALTER COLUMN "PersonalBiography" DROP NOT NULL,
ALTER COLUMN "aboutJob" DROP NOT NULL,
ALTER COLUMN "aboutImportantPerson" DROP NOT NULL,
ALTER COLUMN "importantPersonLocationEffects" DROP NOT NULL,
ALTER COLUMN "canMaintainOralHygiene" DROP NOT NULL,
ALTER COLUMN "autonomyPreference" DROP NOT NULL,
ALTER COLUMN "dailyRoutine" DROP NOT NULL,
ALTER COLUMN "dislikesEffect" DROP NOT NULL,
ALTER COLUMN "hobbiesRoutinesEffect" DROP NOT NULL;

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
