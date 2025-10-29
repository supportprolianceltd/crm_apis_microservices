-- CreateExtension
CREATE EXTENSION IF NOT EXISTS "postgis";

-- CreateEnum
CREATE TYPE "RequestUrgency" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT');

-- CreateEnum
CREATE TYPE "RequestStatus" AS ENUM ('PENDING', 'PROCESSING', 'MATCHED', 'APPROVED', 'COMPLETED', 'DECLINED', 'FAILED');

-- CreateEnum
CREATE TYPE "MatchStatus" AS ENUM ('PENDING', 'SENT', 'OPENED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "MatchResponse" AS ENUM ('ACCEPTED', 'DECLINED', 'INTERESTED');

-- CreateEnum
CREATE TYPE "ProcessingStatus" AS ENUM ('SUCCESS', 'FAILED', 'DUPLICATE', 'INVALID_FORMAT', 'GEOCODING_FAILED');

-- CreateEnum
CREATE TYPE "CarePlanStatus" AS ENUM ('ACTIVE', 'INACTIVE', 'COMPLETED');

-- CreateEnum
CREATE TYPE "BathingAssistance" AS ENUM ('YES_INDEPENDENTLY', 'YES_WITH_HELP', 'NO_NEEDS_FULL_ASSISTANCE');

-- CreateEnum
CREATE TYPE "MobilityLevel" AS ENUM ('INDEPENDENT', 'DEPENDENT', 'INDEPENDENT_WITH_AIDS', 'IMMOBILE');

-- CreateEnum
CREATE TYPE "MobilitySupport" AS ENUM ('WALKING_STICK', 'WHEELCHAIR', 'NONE', 'OTHERS');

-- CreateEnum
CREATE TYPE "GenderPreference" AS ENUM ('NO_PREFERENCE', 'MALE', 'FEMALE', 'NON_BINARY', 'OTHER');

-- CreateEnum
CREATE TYPE "CommunicationMethod" AS ENUM ('PHONE', 'EMAIL', 'SMS', 'IN_PERSON');

-- CreateEnum
CREATE TYPE "TaskStatus" AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD');

-- CreateTable
CREATE TABLE "external_requests" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
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
    "urgency" "RequestUrgency" NOT NULL DEFAULT 'MEDIUM',
    "status" "RequestStatus" NOT NULL DEFAULT 'PENDING',
    "requirements" TEXT,
    "estimatedDuration" INTEGER,
    "scheduledStartTime" TIMESTAMP(3),
    "scheduledEndTime" TIMESTAMP(3),
    "notes" TEXT,
    "emailMessageId" TEXT,
    "emailThreadId" TEXT,
    "approvedBy" TEXT,
    "approvedAt" TIMESTAMP(3),
    "clusterId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "processedAt" TIMESTAMP(3),

    CONSTRAINT "external_requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carers" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "firstName" TEXT NOT NULL,
    "lastName" TEXT NOT NULL,
    "phone" TEXT,
    "address" TEXT NOT NULL,
    "postcode" TEXT NOT NULL,
    "country" TEXT,
    "location" geography(POINT, 4326),
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "maxTravelDistance" INTEGER NOT NULL DEFAULT 10000,
    "availabilityHours" JSONB,
    "skills" TEXT[],
    "languages" TEXT[],
    "qualification" TEXT,
    "experience" INTEGER,
    "hourlyRate" DOUBLE PRECISION,
    "authUserId" TEXT,
    "clusterId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "carers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "request_carer_matches" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "requestId" TEXT NOT NULL,
    "carerId" TEXT NOT NULL,
    "distance" DOUBLE PRECISION NOT NULL,
    "matchScore" DOUBLE PRECISION NOT NULL,
    "status" "MatchStatus" NOT NULL DEFAULT 'PENDING',
    "respondedAt" TIMESTAMP(3),
    "response" "MatchResponse",
    "responseNotes" TEXT,
    "notificationSent" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "request_carer_matches_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "email_processing_logs" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "messageId" TEXT NOT NULL,
    "subject" TEXT NOT NULL,
    "fromAddress" TEXT NOT NULL,
    "processedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "status" "ProcessingStatus" NOT NULL,
    "errorMessage" TEXT,
    "requestId" TEXT,

    CONSTRAINT "email_processing_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "geocoding_cache" (
    "id" TEXT NOT NULL,
    "address" TEXT NOT NULL,
    "postcode" TEXT,
    "latitude" DOUBLE PRECISION NOT NULL,
    "longitude" DOUBLE PRECISION NOT NULL,
    "location" geography(POINT, 4326) NOT NULL,
    "confidence" DOUBLE PRECISION,
    "source" TEXT NOT NULL DEFAULT 'nominatim',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "geocoding_cache_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "tenant_email_configs" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "imapHost" TEXT NOT NULL,
    "imapPort" INTEGER NOT NULL DEFAULT 993,
    "imapUser" TEXT NOT NULL,
    "imapPassword" TEXT NOT NULL,
    "imapTls" BOOLEAN NOT NULL DEFAULT true,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "pollInterval" INTEGER NOT NULL DEFAULT 300,
    "lastChecked" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "tenant_email_configs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clusters" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "regionCenter" geography(POINT, 4326),
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "radiusMeters" INTEGER NOT NULL DEFAULT 5000,
    "activeRequestCount" INTEGER NOT NULL DEFAULT 0,
    "totalRequestCount" INTEGER NOT NULL DEFAULT 0,
    "activeCarerCount" INTEGER NOT NULL DEFAULT 0,
    "totalCarerCount" INTEGER NOT NULL DEFAULT 0,
    "averageMatchTime" INTEGER,
    "lastActivityAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "clusters_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CarePlan" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "clientId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "startDate" TIMESTAMP(3),
    "endDate" TIMESTAMP(3),
    "status" "CarePlanStatus" NOT NULL DEFAULT 'ACTIVE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CarePlan_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CarePlanCarer" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "carerId" TEXT NOT NULL,

    CONSTRAINT "CarePlanCarer_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RiskAssessment" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "primarySupportNeed" TEXT,
    "riskFactorsAndAlerts" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "details" TEXT,
    "areasRequiringSupport" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "homeLayout" TEXT,
    "safetyFeaturesPresent" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "hazards" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "accessibilityNeeds" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "loneWorkerConsideration" BOOLEAN,
    "riskAssessmentAndTraining" TEXT,

    CONSTRAINT "RiskAssessment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PersonalCare" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "bathingAndShowering" "BathingAssistance" NOT NULL,
    "oralHygiene" TEXT NOT NULL,
    "maintainThemselves" TEXT NOT NULL,
    "dressThemselves" TEXT NOT NULL,
    "groomingNeeds" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "toiletUsage" TEXT NOT NULL,
    "bowelControl" TEXT NOT NULL,
    "bladderControl" TEXT NOT NULL,
    "toiletingSupport" TEXT NOT NULL,
    "additionalNotes" TEXT NOT NULL,
    "continenceCare" TEXT NOT NULL,
    "mobilityAssistance" TEXT NOT NULL,
    "preferredLanguage" TEXT NOT NULL,
    "communicationStyleNeeds" TEXT NOT NULL,

    CONSTRAINT "PersonalCare_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EverydayActivityPlan" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "canTheyShop" TEXT NOT NULL,
    "canTheyCall" TEXT NOT NULL,
    "canTheyWash" TEXT NOT NULL,
    "additionalNotes" TEXT NOT NULL,
    "communityAccessNeeds" TEXT NOT NULL,
    "ExerciseandMobilityActivities" TEXT NOT NULL,

    CONSTRAINT "EverydayActivityPlan_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FallsAndMobility" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "fallenBefore" BOOLEAN NOT NULL DEFAULT false,
    "timesFallen" INTEGER NOT NULL,
    "mobilityLevel" "MobilityLevel" NOT NULL,
    "mobilitySupport" "MobilitySupport" NOT NULL,
    "otherMobilitySupport" TEXT,
    "activeAsTheyLikeToBe" TEXT NOT NULL,
    "canTransfer" TEXT NOT NULL,
    "canuseStairs" TEXT NOT NULL,
    "canTravelAlone" TEXT NOT NULL,
    "mobilityAdditionalNotes" TEXT NOT NULL,
    "visionStatus" TEXT NOT NULL,
    "speechStatus" TEXT NOT NULL,
    "hearingStatus" TEXT NOT NULL,
    "sensoryAdditionalNotes" TEXT NOT NULL,

    CONSTRAINT "FallsAndMobility_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "MedicalInformation" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "primaryDiagnosis" TEXT NOT NULL,
    "primaryAdditionalNotes" TEXT NOT NULL,
    "secondaryDiagnoses" TEXT NOT NULL,
    "secondaryAdditionalNotes" TEXT NOT NULL,
    "pastMedicalHistory" TEXT NOT NULL,
    "medicalSupport" BOOLEAN NOT NULL DEFAULT false,
    "breathingDifficulty" BOOLEAN NOT NULL DEFAULT false,
    "breathingSupportNeed" TEXT NOT NULL,
    "useAirWayManagementEquipment" BOOLEAN NOT NULL DEFAULT false,
    "specifyAirwayEquipment" TEXT,
    "airwayEquipmentRisk" TEXT,
    "airWayEquipmentMitigationPlan" TEXT NOT NULL,
    "haveSkinPressureSores" BOOLEAN NOT NULL DEFAULT false,
    "skinPressureConcerningIssues" BOOLEAN NOT NULL DEFAULT false,
    "skinAdditionalInformation" TEXT,
    "currentHealthStatus" TEXT NOT NULL,
    "raisedSafeGuardingIssue" BOOLEAN NOT NULL DEFAULT false,
    "safeGuardingAdditionalInformation" TEXT,
    "primaryDoctor" TEXT NOT NULL,
    "supportContactPhone" TEXT NOT NULL,
    "specialistContact" TEXT NOT NULL,
    "HospitalContact" TEXT NOT NULL,
    "EmergencyCareNotes" TEXT NOT NULL,
    "medicalReportUpload" TEXT,
    "knownAllergies" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "MedicalInformation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ClientAllergy" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "medicalInfoId" TEXT NOT NULL,
    "allergy" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "allergyDetails" TEXT NOT NULL,
    "allergyMedicationFrequency" TEXT NOT NULL,
    "allergyMedicationName" TEXT NOT NULL,
    "allergyMedicationDosage" TEXT NOT NULL,
    "Appointments" TIMESTAMP(3) NOT NULL,
    "knownTrigger" TEXT NOT NULL,

    CONSTRAINT "ClientAllergy_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Medication" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "medicalInfoId" TEXT NOT NULL,
    "drugName" TEXT NOT NULL,
    "dosage" TEXT NOT NULL,
    "frequency" TEXT NOT NULL,

    CONSTRAINT "Medication_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PsychologicalInformation" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "healthLevelSatisfaction" TEXT NOT NULL,
    "healthMotivationalLevel" TEXT NOT NULL,
    "sleepMood" TEXT NOT NULL,
    "specifySleepMood" TEXT NOT NULL,
    "sleepStatus" TEXT NOT NULL,
    "anyoneWorriedAboutMemory" BOOLEAN NOT NULL DEFAULT false,
    "memoryStatus" TEXT NOT NULL,
    "specifyMemoryStatus" TEXT NOT NULL,
    "canTheyDoHouseKeeping" TEXT NOT NULL,
    "houseKeepingSupport" BOOLEAN NOT NULL DEFAULT false,
    "houseKeepingAdditionalNotes" TEXT NOT NULL,

    CONSTRAINT "PsychologicalInformation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FoodNutritionHydration" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "dietaryRequirements" TEXT NOT NULL,
    "foodOrDrinkAllergies" BOOLEAN NOT NULL DEFAULT false,
    "foodAllergiesSpecification" TEXT NOT NULL,
    "allergiesImpact" TEXT NOT NULL,
    "favouriteFoods" TEXT NOT NULL,
    "foodTextures" TEXT NOT NULL,
    "appetiteLevel" TEXT NOT NULL,
    "swallowingDifficulties" TEXT NOT NULL,
    "medicationsAffectingSwallowing" TEXT NOT NULL,
    "specifyMedicationsAffectingSwallowing" TEXT NOT NULL,
    "canFeedSelf" TEXT NOT NULL,
    "canPrepareLightMeals" TEXT NOT NULL,
    "canCookMeals" TEXT NOT NULL,
    "clientFoodGiver" TEXT NOT NULL,
    "mealtimeSupport" TEXT NOT NULL,
    "hydrationSchedule" TEXT NOT NULL,
    "strongDislikes" TEXT NOT NULL,
    "fluidPreferences" TEXT NOT NULL,

    CONSTRAINT "FoodNutritionHydration_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RoutinePreference" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "PersonalBiography" TEXT NOT NULL,
    "haveJob" BOOLEAN NOT NULL DEFAULT false,
    "aboutJob" TEXT NOT NULL,
    "haveImportantPerson" BOOLEAN NOT NULL DEFAULT false,
    "aboutImportantPerson" TEXT NOT NULL,
    "significantPersonHasLocation" BOOLEAN NOT NULL DEFAULT false,
    "importantPersonLocationEffects" TEXT NOT NULL,
    "canMaintainOralHygiene" TEXT NOT NULL,
    "careGiverGenderPreference" "GenderPreference" NOT NULL DEFAULT 'NO_PREFERENCE',
    "autonomyPreference" TEXT NOT NULL,
    "dailyRoutine" TEXT NOT NULL,
    "haveSpecificImportantRoutine" BOOLEAN NOT NULL DEFAULT false,
    "haveDislikes" BOOLEAN NOT NULL DEFAULT false,
    "dislikesEffect" TEXT NOT NULL,
    "haveHobbiesRoutines" BOOLEAN NOT NULL DEFAULT false,
    "hobbiesRoutinesEffect" TEXT NOT NULL,

    CONSTRAINT "RoutinePreference_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CultureValues" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "religiousBackground" TEXT NOT NULL,
    "ethnicGroup" TEXT NOT NULL,
    "culturalAccommodation" TEXT NOT NULL,
    "sexualityandRelationshipPreferences" TEXT NOT NULL,
    "sexImpartingCareNeeds" TEXT NOT NULL,
    "preferredLanguage" TEXT NOT NULL,
    "communicationStyleNeeds" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "preferredMethodOfCommunication" TEXT NOT NULL,
    "keyFamilyMembers" TEXT NOT NULL,
    "receivesInformalCare" BOOLEAN NOT NULL DEFAULT false,
    "informalCareByWho" TEXT,
    "supportMethodByInformalCare" TEXT,
    "concernsOnInformalCare" TEXT,
    "specifyConcernsOnInformalCare" TEXT NOT NULL,
    "receivesFormalCare" BOOLEAN NOT NULL DEFAULT false,
    "specifyFormalCare" TEXT,
    "socialGroupAndCommunity" TEXT NOT NULL,
    "emotionalSupportNeeds" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "mentalWellbeingTracking" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "CultureValues_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "BodyMap" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "visitFrequency" TEXT NOT NULL,
    "carePlanReviewDate" TIMESTAMP(3) NOT NULL,
    "invoicingCycle" TEXT NOT NULL,
    "fundingAndInsuranceDetails" TEXT NOT NULL,
    "assignedCareManager" TEXT NOT NULL,
    "initialClinicalObservations" BOOLEAN NOT NULL DEFAULT false,
    "initialSkinIntegrity" BOOLEAN NOT NULL DEFAULT false,
    "type" TEXT NOT NULL,
    "size" TEXT NOT NULL,
    "locationDescription" TEXT NOT NULL,
    "dateFirstObserved" TIMESTAMP(3) NOT NULL,
    "weight" TEXT NOT NULL,
    "height" TEXT NOT NULL,

    CONSTRAINT "BodyMap_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "MovingHandling" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "equipmentsNeeds" TEXT NOT NULL,
    "anyPainDuringRestingAndMovement" TEXT NOT NULL,
    "anyCognitiveImpairment" TEXT NOT NULL,
    "behaviouralChanges" BOOLEAN NOT NULL DEFAULT false,
    "describeBehaviouralChanges" TEXT NOT NULL,
    "walkIndependently" BOOLEAN NOT NULL DEFAULT false,
    "manageStairs" BOOLEAN NOT NULL DEFAULT false,
    "sittingToStandingDependence" TEXT NOT NULL,
    "limitedSittingBalance" BOOLEAN NOT NULL DEFAULT false,
    "turnInBed" BOOLEAN NOT NULL DEFAULT false,
    "lyingToSittingDependence" BOOLEAN NOT NULL DEFAULT false,
    "gettingUpFromChairDependence" TEXT NOT NULL,
    "bathOrShower" TEXT NOT NULL,
    "chairToCommodeOrBed" BOOLEAN NOT NULL DEFAULT false,
    "profilingBedAndMattress" BOOLEAN NOT NULL DEFAULT false,
    "transferRisks" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "behaviouralChallenges" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "riskManagementPlan" TEXT NOT NULL,
    "locationRiskReview" TEXT NOT NULL,
    "EvacuationPlanRequired" BOOLEAN NOT NULL DEFAULT false,
    "dailyGoal" TEXT NOT NULL,

    CONSTRAINT "MovingHandling_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "IntakeLog" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "movingHandlingId" TEXT NOT NULL,
    "time" TEXT NOT NULL,
    "amount" TEXT NOT NULL,
    "notes" TEXT,

    CONSTRAINT "IntakeLog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CareRequirements" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "careType" TEXT NOT NULL,

    CONSTRAINT "CareRequirements_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LegalRequirement" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "attorneyInPlace" BOOLEAN NOT NULL DEFAULT false,
    "attorneyType" TEXT NOT NULL,
    "attorneyName" TEXT NOT NULL,
    "attorneyContact" TEXT NOT NULL,
    "attorneyEmail" TEXT NOT NULL,
    "solicitor" TEXT NOT NULL,
    "certificateNumber" TEXT NOT NULL,
    "certificateUpload" TEXT,
    "digitalConsentsAndPermissions" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "consertUpload" TEXT,

    CONSTRAINT "LegalRequirement_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "tasks" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "carePlanId" TEXT NOT NULL,
    "relatedTable" TEXT NOT NULL,
    "relatedId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "status" "TaskStatus" NOT NULL DEFAULT 'PENDING',
    "riskCategory" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "riskFrequency" TEXT NOT NULL,
    "startDate" TIMESTAMP(3),
    "dueDate" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdBy" TEXT,
    "additionalNotes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "tasks_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "external_requests_tenantId_idx" ON "external_requests"("tenantId");

-- CreateIndex
CREATE INDEX "external_requests_status_idx" ON "external_requests"("status");

-- CreateIndex
CREATE INDEX "external_requests_urgency_idx" ON "external_requests"("urgency");

-- CreateIndex
CREATE INDEX "external_requests_postcode_idx" ON "external_requests"("postcode");

-- CreateIndex
CREATE INDEX "external_requests_createdAt_idx" ON "external_requests"("createdAt");

-- CreateIndex
CREATE INDEX "external_requests_scheduledStartTime_idx" ON "external_requests"("scheduledStartTime");

-- CreateIndex
CREATE INDEX "external_requests_clusterId_idx" ON "external_requests"("clusterId");

-- CreateIndex
CREATE INDEX "carers_tenantId_idx" ON "carers"("tenantId");

-- CreateIndex
CREATE INDEX "carers_isActive_idx" ON "carers"("isActive");

-- CreateIndex
CREATE INDEX "carers_postcode_idx" ON "carers"("postcode");

-- CreateIndex
CREATE INDEX "carers_skills_idx" ON "carers"("skills");

-- CreateIndex
CREATE INDEX "carers_clusterId_idx" ON "carers"("clusterId");

-- CreateIndex
CREATE UNIQUE INDEX "carers_tenantId_email_key" ON "carers"("tenantId", "email");

-- CreateIndex
CREATE INDEX "request_carer_matches_tenantId_idx" ON "request_carer_matches"("tenantId");

-- CreateIndex
CREATE INDEX "request_carer_matches_status_idx" ON "request_carer_matches"("status");

-- CreateIndex
CREATE INDEX "request_carer_matches_createdAt_idx" ON "request_carer_matches"("createdAt");

-- CreateIndex
CREATE INDEX "request_carer_matches_distance_idx" ON "request_carer_matches"("distance");

-- CreateIndex
CREATE UNIQUE INDEX "request_carer_matches_requestId_carerId_key" ON "request_carer_matches"("requestId", "carerId");

-- CreateIndex
CREATE INDEX "email_processing_logs_tenantId_idx" ON "email_processing_logs"("tenantId");

-- CreateIndex
CREATE INDEX "email_processing_logs_processedAt_idx" ON "email_processing_logs"("processedAt");

-- CreateIndex
CREATE INDEX "email_processing_logs_status_idx" ON "email_processing_logs"("status");

-- CreateIndex
CREATE UNIQUE INDEX "email_processing_logs_tenantId_messageId_key" ON "email_processing_logs"("tenantId", "messageId");

-- CreateIndex
CREATE UNIQUE INDEX "geocoding_cache_address_key" ON "geocoding_cache"("address");

-- CreateIndex
CREATE INDEX "geocoding_cache_postcode_idx" ON "geocoding_cache"("postcode");

-- CreateIndex
CREATE UNIQUE INDEX "tenant_email_configs_tenantId_key" ON "tenant_email_configs"("tenantId");

-- CreateIndex
CREATE INDEX "clusters_tenantId_idx" ON "clusters"("tenantId");

-- CreateIndex
CREATE INDEX "clusters_latitude_longitude_idx" ON "clusters"("latitude", "longitude");

-- CreateIndex
CREATE INDEX "clusters_tenantId_activeRequestCount_idx" ON "clusters"("tenantId", "activeRequestCount");

-- CreateIndex
CREATE INDEX "clusters_tenantId_activeCarerCount_idx" ON "clusters"("tenantId", "activeCarerCount");

-- CreateIndex
CREATE INDEX "CarePlan_tenantId_idx" ON "CarePlan"("tenantId");

-- CreateIndex
CREATE INDEX "CarePlan_tenantId_clientId_idx" ON "CarePlan"("tenantId", "clientId");

-- CreateIndex
CREATE INDEX "CarePlanCarer_tenantId_idx" ON "CarePlanCarer"("tenantId");

-- CreateIndex
CREATE UNIQUE INDEX "CarePlanCarer_tenantId_carePlanId_carerId_key" ON "CarePlanCarer"("tenantId", "carePlanId", "carerId");

-- CreateIndex
CREATE UNIQUE INDEX "RiskAssessment_carePlanId_key" ON "RiskAssessment"("carePlanId");

-- CreateIndex
CREATE INDEX "RiskAssessment_tenantId_idx" ON "RiskAssessment"("tenantId");

-- CreateIndex
CREATE INDEX "RiskAssessment_carePlanId_idx" ON "RiskAssessment"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "PersonalCare_carePlanId_key" ON "PersonalCare"("carePlanId");

-- CreateIndex
CREATE INDEX "PersonalCare_tenantId_idx" ON "PersonalCare"("tenantId");

-- CreateIndex
CREATE INDEX "PersonalCare_carePlanId_idx" ON "PersonalCare"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "EverydayActivityPlan_carePlanId_key" ON "EverydayActivityPlan"("carePlanId");

-- CreateIndex
CREATE INDEX "EverydayActivityPlan_tenantId_idx" ON "EverydayActivityPlan"("tenantId");

-- CreateIndex
CREATE INDEX "EverydayActivityPlan_carePlanId_idx" ON "EverydayActivityPlan"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "FallsAndMobility_carePlanId_key" ON "FallsAndMobility"("carePlanId");

-- CreateIndex
CREATE INDEX "FallsAndMobility_tenantId_idx" ON "FallsAndMobility"("tenantId");

-- CreateIndex
CREATE INDEX "FallsAndMobility_carePlanId_idx" ON "FallsAndMobility"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "MedicalInformation_carePlanId_key" ON "MedicalInformation"("carePlanId");

-- CreateIndex
CREATE INDEX "MedicalInformation_tenantId_idx" ON "MedicalInformation"("tenantId");

-- CreateIndex
CREATE INDEX "MedicalInformation_carePlanId_idx" ON "MedicalInformation"("carePlanId");

-- CreateIndex
CREATE INDEX "ClientAllergy_tenantId_idx" ON "ClientAllergy"("tenantId");

-- CreateIndex
CREATE INDEX "ClientAllergy_medicalInfoId_idx" ON "ClientAllergy"("medicalInfoId");

-- CreateIndex
CREATE INDEX "Medication_tenantId_idx" ON "Medication"("tenantId");

-- CreateIndex
CREATE INDEX "Medication_medicalInfoId_idx" ON "Medication"("medicalInfoId");

-- CreateIndex
CREATE UNIQUE INDEX "PsychologicalInformation_carePlanId_key" ON "PsychologicalInformation"("carePlanId");

-- CreateIndex
CREATE INDEX "PsychologicalInformation_tenantId_idx" ON "PsychologicalInformation"("tenantId");

-- CreateIndex
CREATE INDEX "PsychologicalInformation_carePlanId_idx" ON "PsychologicalInformation"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "FoodNutritionHydration_carePlanId_key" ON "FoodNutritionHydration"("carePlanId");

-- CreateIndex
CREATE INDEX "FoodNutritionHydration_tenantId_idx" ON "FoodNutritionHydration"("tenantId");

-- CreateIndex
CREATE INDEX "FoodNutritionHydration_carePlanId_idx" ON "FoodNutritionHydration"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "RoutinePreference_carePlanId_key" ON "RoutinePreference"("carePlanId");

-- CreateIndex
CREATE INDEX "RoutinePreference_tenantId_idx" ON "RoutinePreference"("tenantId");

-- CreateIndex
CREATE INDEX "RoutinePreference_carePlanId_idx" ON "RoutinePreference"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "CultureValues_carePlanId_key" ON "CultureValues"("carePlanId");

-- CreateIndex
CREATE INDEX "CultureValues_tenantId_idx" ON "CultureValues"("tenantId");

-- CreateIndex
CREATE INDEX "CultureValues_carePlanId_idx" ON "CultureValues"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "BodyMap_carePlanId_key" ON "BodyMap"("carePlanId");

-- CreateIndex
CREATE INDEX "BodyMap_tenantId_idx" ON "BodyMap"("tenantId");

-- CreateIndex
CREATE INDEX "BodyMap_carePlanId_idx" ON "BodyMap"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "MovingHandling_carePlanId_key" ON "MovingHandling"("carePlanId");

-- CreateIndex
CREATE INDEX "MovingHandling_tenantId_idx" ON "MovingHandling"("tenantId");

-- CreateIndex
CREATE INDEX "MovingHandling_carePlanId_idx" ON "MovingHandling"("carePlanId");

-- CreateIndex
CREATE INDEX "IntakeLog_tenantId_idx" ON "IntakeLog"("tenantId");

-- CreateIndex
CREATE INDEX "IntakeLog_movingHandlingId_idx" ON "IntakeLog"("movingHandlingId");

-- CreateIndex
CREATE UNIQUE INDEX "CareRequirements_carePlanId_key" ON "CareRequirements"("carePlanId");

-- CreateIndex
CREATE INDEX "CareRequirements_tenantId_idx" ON "CareRequirements"("tenantId");

-- CreateIndex
CREATE INDEX "CareRequirements_carePlanId_idx" ON "CareRequirements"("carePlanId");

-- CreateIndex
CREATE UNIQUE INDEX "LegalRequirement_carePlanId_key" ON "LegalRequirement"("carePlanId");

-- CreateIndex
CREATE INDEX "LegalRequirement_tenantId_idx" ON "LegalRequirement"("tenantId");

-- CreateIndex
CREATE INDEX "LegalRequirement_carePlanId_idx" ON "LegalRequirement"("carePlanId");

-- CreateIndex
CREATE INDEX "tasks_tenantId_idx" ON "tasks"("tenantId");

-- CreateIndex
CREATE INDEX "tasks_carePlanId_idx" ON "tasks"("carePlanId");

-- CreateIndex
CREATE INDEX "tasks_relatedTable_relatedId_idx" ON "tasks"("relatedTable", "relatedId");

-- CreateIndex
CREATE INDEX "tasks_status_idx" ON "tasks"("status");

-- CreateIndex
CREATE INDEX "tasks_dueDate_idx" ON "tasks"("dueDate");

-- AddForeignKey
ALTER TABLE "external_requests" ADD CONSTRAINT "external_requests_clusterId_fkey" FOREIGN KEY ("clusterId") REFERENCES "clusters"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carers" ADD CONSTRAINT "carers_clusterId_fkey" FOREIGN KEY ("clusterId") REFERENCES "clusters"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "request_carer_matches" ADD CONSTRAINT "request_carer_matches_requestId_fkey" FOREIGN KEY ("requestId") REFERENCES "external_requests"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "request_carer_matches" ADD CONSTRAINT "request_carer_matches_carerId_fkey" FOREIGN KEY ("carerId") REFERENCES "carers"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CarePlanCarer" ADD CONSTRAINT "CarePlanCarer_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RiskAssessment" ADD CONSTRAINT "RiskAssessment_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PersonalCare" ADD CONSTRAINT "PersonalCare_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EverydayActivityPlan" ADD CONSTRAINT "EverydayActivityPlan_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FallsAndMobility" ADD CONSTRAINT "FallsAndMobility_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "MedicalInformation" ADD CONSTRAINT "MedicalInformation_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ClientAllergy" ADD CONSTRAINT "ClientAllergy_medicalInfoId_fkey" FOREIGN KEY ("medicalInfoId") REFERENCES "MedicalInformation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Medication" ADD CONSTRAINT "Medication_medicalInfoId_fkey" FOREIGN KEY ("medicalInfoId") REFERENCES "MedicalInformation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PsychologicalInformation" ADD CONSTRAINT "PsychologicalInformation_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FoodNutritionHydration" ADD CONSTRAINT "FoodNutritionHydration_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RoutinePreference" ADD CONSTRAINT "RoutinePreference_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CultureValues" ADD CONSTRAINT "CultureValues_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "BodyMap" ADD CONSTRAINT "BodyMap_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "MovingHandling" ADD CONSTRAINT "MovingHandling_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "IntakeLog" ADD CONSTRAINT "IntakeLog_movingHandlingId_fkey" FOREIGN KEY ("movingHandlingId") REFERENCES "MovingHandling"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CareRequirements" ADD CONSTRAINT "CareRequirements_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "LegalRequirement" ADD CONSTRAINT "LegalRequirement_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_carePlanId_fkey" FOREIGN KEY ("carePlanId") REFERENCES "CarePlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

