// ...existing code...

  // ...existing code...

// ...existing code...

  // ...existing code...


import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';

function getUserFriendlyError(error: any): string {
  if (error?.code === 'P2002') {
    return 'A record with this unique value already exists.';
  }
  if (error?.code === 'P2025') {
    return 'The requested record was not found.';
  }
  if (error?.code === 'P2003') {
    return 'Invalid reference to a related record.';
  }
  if (error?.name === 'ValidationError') {
    return 'Invalid data provided.';
  }
  // Add more Prisma or validation error codes as needed
  return 'An unexpected error occurred. Please try again or contact support.';
}

export class CarePlanController {
  private prisma: PrismaClient;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  private validateRiskAssessment(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors; // Not required, skip if not present
    // Required fields from schema
    if (!('primarySupportNeed' in obj) || typeof obj.primarySupportNeed !== 'string') {
      errors.push('riskAssessment.primarySupportNeed is required and must be a string');
    }
    // Arrays: riskFactorsAndAlerts, areasRequiringSupport, safetyFeaturesPresent, hazards, accessibilityNeeds
    if ('riskFactorsAndAlerts' in obj && !Array.isArray(obj.riskFactorsAndAlerts)) {
      errors.push('riskAssessment.riskFactorsAndAlerts must be an array');
    }
    if ('areasRequiringSupport' in obj && !Array.isArray(obj.areasRequiringSupport)) {
      errors.push('riskAssessment.areasRequiringSupport must be an array');
    }
    if ('safetyFeaturesPresent' in obj && !Array.isArray(obj.safetyFeaturesPresent)) {
      errors.push('riskAssessment.safetyFeaturesPresent must be an array');
    }
    if ('hazards' in obj && !Array.isArray(obj.hazards)) {
      errors.push('riskAssessment.hazards must be an array');
    }
    if ('accessibilityNeeds' in obj && !Array.isArray(obj.accessibilityNeeds)) {
      errors.push('riskAssessment.accessibilityNeeds must be an array');
    }
    if ('loneWorkerConsideration' in obj && typeof obj.loneWorkerConsideration !== 'boolean') {
      errors.push('riskAssessment.loneWorkerConsideration must be a boolean');
    }
    // Optional fields: details, homeLayout, riskAssessmentAndTraining
    if ('details' in obj && typeof obj.details !== 'string') {
      errors.push('riskAssessment.details must be a string');
    }
    if ('homeLayout' in obj && typeof obj.homeLayout !== 'string') {
      errors.push('riskAssessment.homeLayout must be a string');
    }
    if ('riskAssessmentAndTraining' in obj && typeof obj.riskAssessmentAndTraining !== 'string') {
      errors.push('riskAssessment.riskAssessmentAndTraining must be a string');
    }
    return errors;
  }

  private validatePersonalCare(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors; // Not required, skip if not present
    // Required fields from schema
    if (!('bathingAndShowering' in obj) || typeof obj.bathingAndShowering !== 'string') {
      errors.push('personalCare.bathingAndShowering is required and must be a string');
    }
    if (!('oralHygiene' in obj) || typeof obj.oralHygiene !== 'string') {
      errors.push('personalCare.oralHygiene is required and must be a string');
    }
    if (!('maintainThemselves' in obj) || typeof obj.maintainThemselves !== 'string') {
      errors.push('personalCare.maintainThemselves is required and must be a string');
    }
    if (!('dressThemselves' in obj) || typeof obj.dressThemselves !== 'string') {
      errors.push('personalCare.dressThemselves is required and must be a string');
    }
    if (!('toiletUsage' in obj) || typeof obj.toiletUsage !== 'string') {
      errors.push('personalCare.toiletUsage is required and must be a string');
    }
    if (!('bowelControl' in obj) || typeof obj.bowelControl !== 'string') {
      errors.push('personalCare.bowelControl is required and must be a string');
    }
    if (!('bladderControl' in obj) || typeof obj.bladderControl !== 'string') {
      errors.push('personalCare.bladderControl is required and must be a string');
    }
    if (!('toiletingSupport' in obj) || typeof obj.toiletingSupport !== 'string') {
      errors.push('personalCare.toiletingSupport is required and must be a string');
    }
    if (!('additionalNotes' in obj) || typeof obj.additionalNotes !== 'string') {
      errors.push('personalCare.additionalNotes is required and must be a string');
    }
    if (!('continenceCare' in obj) || typeof obj.continenceCare !== 'string') {
      errors.push('personalCare.continenceCare is required and must be a string');
    }
    if (!('mobilityAssistance' in obj) || typeof obj.mobilityAssistance !== 'string') {
      errors.push('personalCare.mobilityAssistance is required and must be a string');
    }
    if (!('preferredLanguage' in obj) || typeof obj.preferredLanguage !== 'string') {
      errors.push('personalCare.preferredLanguage is required and must be a string');
    }
    if (!('communicationStyleNeeds' in obj) || typeof obj.communicationStyleNeeds !== 'string') {
      errors.push('personalCare.communicationStyleNeeds is required and must be a string');
    }
    // groomingNeeds must be an array
    if ('groomingNeeds' in obj && !Array.isArray(obj.groomingNeeds)) {
      errors.push('personalCare.groomingNeeds must be an array');
    }
    return errors;
  }

  private validateEverydayActivityPlan(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors; // Not required, skip if not present
    // Required fields from schema
    if (!('canTheyShop' in obj) || typeof obj.canTheyShop !== 'string') {
      errors.push('everydayActivityPlan.canTheyShop is required and must be a string');
    }
    if (!('canTheyCall' in obj) || typeof obj.canTheyCall !== 'string') {
      errors.push('everydayActivityPlan.canTheyCall is required and must be a string');
    }
    if (!('canTheyWash' in obj) || typeof obj.canTheyWash !== 'string') {
      errors.push('everydayActivityPlan.canTheyWash is required and must be a string');
    }
    if (!('additionalNotes' in obj) || typeof obj.additionalNotes !== 'string') {
      errors.push('everydayActivityPlan.additionalNotes is required and must be a string');
    }
    if (!('communityAccessNeeds' in obj) || typeof obj.communityAccessNeeds !== 'string') {
      errors.push('everydayActivityPlan.communityAccessNeeds is required and must be a string');
    }
    if (!('ExerciseandMobilityActivities' in obj) || typeof obj.ExerciseandMobilityActivities !== 'string') {
      errors.push('everydayActivityPlan.ExerciseandMobilityActivities is required and must be a string');
    }
    return errors;
  }

      private validateFallsAndMobility(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    // Required fields from schema
    if (!('fallenBefore' in obj) || typeof obj.fallenBefore !== 'boolean') {
      errors.push('fallsAndMobility.fallenBefore is required and must be a boolean');
    }
    if (!('timesFallen' in obj) || typeof obj.timesFallen !== 'number') {
      errors.push('fallsAndMobility.timesFallen is required and must be a number');
    }
    if (!('mobilityLevel' in obj) || typeof obj.mobilityLevel !== 'string') {
      errors.push('fallsAndMobility.mobilityLevel is required and must be a string');
    }
    if (!('mobilitySupport' in obj) || typeof obj.mobilitySupport !== 'string') {
      errors.push('fallsAndMobility.mobilitySupport is required and must be a string');
    }
    if (!('activeAsTheyLikeToBe' in obj) || typeof obj.activeAsTheyLikeToBe !== 'string') {
      errors.push('fallsAndMobility.activeAsTheyLikeToBe is required and must be a string');
    }
    if (!('canTransfer' in obj) || typeof obj.canTransfer !== 'string') {
      errors.push('fallsAndMobility.canTransfer is required and must be a string');
    }
    if (!('canuseStairs' in obj) || typeof obj.canuseStairs !== 'string') {
      errors.push('fallsAndMobility.canuseStairs is required and must be a string');
    }
    if (!('canTravelAlone' in obj) || typeof obj.canTravelAlone !== 'string') {
      errors.push('fallsAndMobility.canTravelAlone is required and must be a string');
    }
    if (!('mobilityAdditionalNotes' in obj) || typeof obj.mobilityAdditionalNotes !== 'string') {
      errors.push('fallsAndMobility.mobilityAdditionalNotes is required and must be a string');
    }
    if (!('visionStatus' in obj) || typeof obj.visionStatus !== 'string') {
      errors.push('fallsAndMobility.visionStatus is required and must be a string');
    }
    if (!('speechStatus' in obj) || typeof obj.speechStatus !== 'string') {
      errors.push('fallsAndMobility.speechStatus is required and must be a string');
    }
    if (!('hearingStatus' in obj) || typeof obj.hearingStatus !== 'string') {
      errors.push('fallsAndMobility.hearingStatus is required and must be a string');
    }
    if (!('sensoryAdditionalNotes' in obj) || typeof obj.sensoryAdditionalNotes !== 'string') {
      errors.push('fallsAndMobility.sensoryAdditionalNotes is required and must be a string');
    }
    // Optional: otherMobilitySupport
    if ('otherMobilitySupport' in obj && typeof obj.otherMobilitySupport !== 'string') {
      errors.push('fallsAndMobility.otherMobilitySupport must be a string');
    }
    return errors;
  }

  private validatePsychologicalInfo(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    if (!('healthLevelSatisfaction' in obj) || typeof obj.healthLevelSatisfaction !== 'string') {
      errors.push('psychologicalInfo.healthLevelSatisfaction is required and must be a string');
    }
    if (!('healthMotivationalLevel' in obj) || typeof obj.healthMotivationalLevel !== 'string') {
      errors.push('psychologicalInfo.healthMotivationalLevel is required and must be a string');
    }
    if (!('sleepMood' in obj) || typeof obj.sleepMood !== 'string') {
      errors.push('psychologicalInfo.sleepMood is required and must be a string');
    }
    if (!('specifySleepMood' in obj) || typeof obj.specifySleepMood !== 'string') {
      errors.push('psychologicalInfo.specifySleepMood is required and must be a string');
    }
    if (!('sleepStatus' in obj) || typeof obj.sleepStatus !== 'string') {
      errors.push('psychologicalInfo.sleepStatus is required and must be a string');
    }
    if (!('anyoneWorriedAboutMemory' in obj) || typeof obj.anyoneWorriedAboutMemory !== 'boolean') {
      errors.push('psychologicalInfo.anyoneWorriedAboutMemory is required and must be a boolean');
    }
    if (!('memoryStatus' in obj) || typeof obj.memoryStatus !== 'string') {
      errors.push('psychologicalInfo.memoryStatus is required and must be a string');
    }
    if (!('specifyMemoryStatus' in obj) || typeof obj.specifyMemoryStatus !== 'string') {
      errors.push('psychologicalInfo.specifyMemoryStatus is required and must be a string');
    }
    if (!('canTheyDoHouseKeeping' in obj) || typeof obj.canTheyDoHouseKeeping !== 'string') {
      errors.push('psychologicalInfo.canTheyDoHouseKeeping is required and must be a string');
    }
    if (!('houseKeepingSupport' in obj) || typeof obj.houseKeepingSupport !== 'boolean') {
      errors.push('psychologicalInfo.houseKeepingSupport is required and must be a boolean');
    }
    if (!('houseKeepingAdditionalNotes' in obj) || typeof obj.houseKeepingAdditionalNotes !== 'string') {
      errors.push('psychologicalInfo.houseKeepingAdditionalNotes is required and must be a string');
    }
    return errors;
  }

  private validateFoodHydration(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    if (!('dietaryRequirements' in obj) || typeof obj.dietaryRequirements !== 'string') {
      errors.push('foodHydration.dietaryRequirements is required and must be a string');
    }
    if (!('foodOrDrinkAllergies' in obj) || typeof obj.foodOrDrinkAllergies !== 'boolean') {
      errors.push('foodHydration.foodOrDrinkAllergies is required and must be a boolean');
    }
    if (!('foodAllergiesSpecification' in obj) || typeof obj.foodAllergiesSpecification !== 'string') {
      errors.push('foodHydration.foodAllergiesSpecification is required and must be a string');
    }
    if (!('allergiesImpact' in obj) || typeof obj.allergiesImpact !== 'string') {
      errors.push('foodHydration.allergiesImpact is required and must be a string');
    }
    if (!('favouriteFoods' in obj) || typeof obj.favouriteFoods !== 'string') {
      errors.push('foodHydration.favouriteFoods is required and must be a string');
    }
    if (!('foodTextures' in obj) || typeof obj.foodTextures !== 'string') {
      errors.push('foodHydration.foodTextures is required and must be a string');
    }
    if (!('appetiteLevel' in obj) || typeof obj.appetiteLevel !== 'string') {
      errors.push('foodHydration.appetiteLevel is required and must be a string');
    }
    if (!('swallowingDifficulties' in obj) || typeof obj.swallowingDifficulties !== 'string') {
      errors.push('foodHydration.swallowingDifficulties is required and must be a string');
    }
    if (!('medicationsAffectingSwallowing' in obj) || typeof obj.medicationsAffectingSwallowing !== 'string') {
      errors.push('foodHydration.medicationsAffectingSwallowing is required and must be a string');
    }
    if (!('specifyMedicationsAffectingSwallowing' in obj) || typeof obj.specifyMedicationsAffectingSwallowing !== 'string') {
      errors.push('foodHydration.specifyMedicationsAffectingSwallowing is required and must be a string');
    }
    if (!('canFeedSelf' in obj) || typeof obj.canFeedSelf !== 'string') {
      errors.push('foodHydration.canFeedSelf is required and must be a string');
    }
    if (!('canPrepareLightMeals' in obj) || typeof obj.canPrepareLightMeals !== 'string') {
      errors.push('foodHydration.canPrepareLightMeals is required and must be a string');
    }
    if (!('canCookMeals' in obj) || typeof obj.canCookMeals !== 'string') {
      errors.push('foodHydration.canCookMeals is required and must be a string');
    }
    if (!('clientFoodGiver' in obj) || typeof obj.clientFoodGiver !== 'string') {
      errors.push('foodHydration.clientFoodGiver is required and must be a string');
    }
    if (!('mealtimeSupport' in obj) || typeof obj.mealtimeSupport !== 'string') {
      errors.push('foodHydration.mealtimeSupport is required and must be a string');
    }
    if (!('hydrationSchedule' in obj) || typeof obj.hydrationSchedule !== 'string') {
      errors.push('foodHydration.hydrationSchedule is required and must be a string');
    }
    if (!('strongDislikes' in obj) || typeof obj.strongDislikes !== 'string') {
      errors.push('foodHydration.strongDislikes is required and must be a string');
    }
    if (!('fluidPreferences' in obj) || typeof obj.fluidPreferences !== 'string') {
      errors.push('foodHydration.fluidPreferences is required and must be a string');
    }
    return errors;
  }

  private validateRoutine(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    // Required fields from schema
    if (!('PersonalBiography' in obj) || typeof obj.PersonalBiography !== 'string') {
      errors.push('routine.PersonalBiography is required and must be a string');
    }
    if (!('haveJob' in obj) || typeof obj.haveJob !== 'boolean') {
      errors.push('routine.haveJob is required and must be a boolean');
    }
    if (!('aboutJob' in obj) || typeof obj.aboutJob !== 'string') {
      errors.push('routine.aboutJob is required and must be a string');
    }
    if (!('haveImportantPerson' in obj) || typeof obj.haveImportantPerson !== 'boolean') {
      errors.push('routine.haveImportantPerson is required and must be a boolean');
    }
    if (!('aboutImportantPerson' in obj) || typeof obj.aboutImportantPerson !== 'string') {
      errors.push('routine.aboutImportantPerson is required and must be a string');
    }
    if (!('significantPersonHasLocation' in obj) || typeof obj.significantPersonHasLocation !== 'boolean') {
      errors.push('routine.significantPersonHasLocation is required and must be a boolean');
    }
    if (!('importantPersonLocationEffects' in obj) || typeof obj.importantPersonLocationEffects !== 'string') {
      errors.push('routine.importantPersonLocationEffects is required and must be a string');
    }
    if (!('canMaintainOralHygiene' in obj) || typeof obj.canMaintainOralHygiene !== 'string') {
      errors.push('routine.canMaintainOralHygiene is required and must be a string');
    }
    if (!('careGiverGenderPreference' in obj) || typeof obj.careGiverGenderPreference !== 'string') {
      errors.push('routine.careGiverGenderPreference is required and must be a string');
    }
    if (!('autonomyPreference' in obj) || typeof obj.autonomyPreference !== 'string') {
      errors.push('routine.autonomyPreference is required and must be a string');
    }
    if (!('dailyRoutine' in obj) || typeof obj.dailyRoutine !== 'string') {
      errors.push('routine.dailyRoutine is required and must be a string');
    }
    if (!('haveSpecificImportantRoutine' in obj) || typeof obj.haveSpecificImportantRoutine !== 'boolean') {
      errors.push('routine.haveSpecificImportantRoutine is required and must be a boolean');
    }
    if (!('haveDislikes' in obj) || typeof obj.haveDislikes !== 'boolean') {
      errors.push('routine.haveDislikes is required and must be a boolean');
    }
    if (!('dislikesEffect' in obj) || typeof obj.dislikesEffect !== 'string') {
      errors.push('routine.dislikesEffect is required and must be a string');
    }
    if (!('haveHobbiesRoutines' in obj) || typeof obj.haveHobbiesRoutines !== 'boolean') {
      errors.push('routine.haveHobbiesRoutines is required and must be a boolean');
    }
    if (!('hobbiesRoutinesEffect' in obj) || typeof obj.hobbiesRoutinesEffect !== 'string') {
      errors.push('routine.hobbiesRoutinesEffect is required and must be a string');
    }
    return errors;
  }

  private validateCareRequirements(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    if (!('careType' in obj) || typeof obj.careType !== 'string') {
      errors.push('careRequirements.careType is required and must be a string');
    }
    return errors;
  }

    private validateCultureValues(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    if (!('religiousBackground' in obj) || typeof obj.religiousBackground !== 'string') {
      errors.push('cultureValues.religiousBackground is required and must be a string');
    }
    if (!('ethnicGroup' in obj) || typeof obj.ethnicGroup !== 'string') {
      errors.push('cultureValues.ethnicGroup is required and must be a string');
    }
    if (!('culturalAccommodation' in obj) || typeof obj.culturalAccommodation !== 'string') {
      errors.push('cultureValues.culturalAccommodation is required and must be a string');
    }
    if (!('sexualityandRelationshipPreferences' in obj) || typeof obj.sexualityandRelationshipPreferences !== 'string') {
      errors.push('cultureValues.sexualityandRelationshipPreferences is required and must be a string');
    }
    if (!('sexImpartingCareNeeds' in obj) || typeof obj.sexImpartingCareNeeds !== 'string') {
      errors.push('cultureValues.sexImpartingCareNeeds is required and must be a string');
    }
    if (!('preferredLanguage' in obj) || typeof obj.preferredLanguage !== 'string') {
      errors.push('cultureValues.preferredLanguage is required and must be a string');
    }
    if (!('communicationStyleNeeds' in obj) || !Array.isArray(obj.communicationStyleNeeds)) {
      errors.push('cultureValues.communicationStyleNeeds is required and must be an array');
    }
    if (!('preferredMethodOfCommunication' in obj) || typeof obj.preferredMethodOfCommunication !== 'string') {
      errors.push('cultureValues.preferredMethodOfCommunication is required and must be a string');
    }
    if (!('keyFamilyMembers' in obj) || typeof obj.keyFamilyMembers !== 'string') {
      errors.push('cultureValues.keyFamilyMembers is required and must be a string');
    }
    if (!('receivesInformalCare' in obj) || typeof obj.receivesInformalCare !== 'boolean') {
      errors.push('cultureValues.receivesInformalCare is required and must be a boolean');
    }
    if (!('specifyConcernsOnInformalCare' in obj) || typeof obj.specifyConcernsOnInformalCare !== 'string') {
      errors.push('cultureValues.specifyConcernsOnInformalCare is required and must be a string');
    }
    if (!('receivesFormalCare' in obj) || typeof obj.receivesFormalCare !== 'boolean') {
      errors.push('cultureValues.receivesFormalCare is required and must be a boolean');
    }
    if (!('socialGroupAndCommunity' in obj) || typeof obj.socialGroupAndCommunity !== 'string') {
      errors.push('cultureValues.socialGroupAndCommunity is required and must be a string');
    }
    if (!('mentalWellbeingTracking' in obj) || typeof obj.mentalWellbeingTracking !== 'boolean') {
      errors.push('cultureValues.mentalWellbeingTracking is required and must be a boolean');
    }
    // emotionalSupportNeeds is an array
    if ('emotionalSupportNeeds' in obj && !Array.isArray(obj.emotionalSupportNeeds)) {
      errors.push('cultureValues.emotionalSupportNeeds must be an array');
    }
    return errors;
  }

  private validateBodyMap(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    if (!('visitFrequency' in obj) || typeof obj.visitFrequency !== 'string') {
      errors.push('bodyMap.visitFrequency is required and must be a string');
    }
    if (!('carePlanReviewDate' in obj) || isNaN(Date.parse(obj.carePlanReviewDate))) {
      errors.push('bodyMap.carePlanReviewDate is required and must be a valid date string');
    }
    if (!('invoicingCycle' in obj) || typeof obj.invoicingCycle !== 'string') {
      errors.push('bodyMap.invoicingCycle is required and must be a string');
    }
    if (!('fundingAndInsuranceDetails' in obj) || typeof obj.fundingAndInsuranceDetails !== 'string') {
      errors.push('bodyMap.fundingAndInsuranceDetails is required and must be a string');
    }
    if (!('assignedCareManager' in obj) || typeof obj.assignedCareManager !== 'string') {
      errors.push('bodyMap.assignedCareManager is required and must be a string');
    }
    if (!('initialClinicalObservations' in obj) || typeof obj.initialClinicalObservations !== 'boolean') {
      errors.push('bodyMap.initialClinicalObservations is required and must be a boolean');
    }
    if (!('initialSkinIntegrity' in obj) || typeof obj.initialSkinIntegrity !== 'boolean') {
      errors.push('bodyMap.initialSkinIntegrity is required and must be a boolean');
    }
    if (!('type' in obj) || typeof obj.type !== 'string') {
      errors.push('bodyMap.type is required and must be a string');
    }
    if (!('size' in obj) || typeof obj.size !== 'string') {
      errors.push('bodyMap.size is required and must be a string');
    }
    if (!('locationDescription' in obj) || typeof obj.locationDescription !== 'string') {
      errors.push('bodyMap.locationDescription is required and must be a string');
    }
    if (!('dateFirstObserved' in obj) || isNaN(Date.parse(obj.dateFirstObserved))) {
      errors.push('bodyMap.dateFirstObserved is required and must be a valid date string');
    }
    if (!('weight' in obj) || typeof obj.weight !== 'string') {
      errors.push('bodyMap.weight is required and must be a string');
    }
    if (!('height' in obj) || typeof obj.height !== 'string') {
      errors.push('bodyMap.height is required and must be a string');
    }
    return errors;
  }

  private validateLegalRequirement(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    if (!('attorneyInPlace' in obj) || typeof obj.attorneyInPlace !== 'boolean') {
      errors.push('legalRequirement.attorneyInPlace is required and must be a boolean');
    }
    if (!('attorneyType' in obj) || typeof obj.attorneyType !== 'string') {
      errors.push('legalRequirement.attorneyType is required and must be a string');
    }
    if (!('attorneyName' in obj) || typeof obj.attorneyName !== 'string') {
      errors.push('legalRequirement.attorneyName is required and must be a string');
    }
    if (!('attorneyContact' in obj) || typeof obj.attorneyContact !== 'string') {
      errors.push('legalRequirement.attorneyContact is required and must be a string');
    }
    if (!('attorneyEmail' in obj) || typeof obj.attorneyEmail !== 'string') {
      errors.push('legalRequirement.attorneyEmail is required and must be a string');
    }
    if (!('solicitor' in obj) || typeof obj.solicitor !== 'string') {
      errors.push('legalRequirement.solicitor is required and must be a string');
    }
    if (!('certificateNumber' in obj) || typeof obj.certificateNumber !== 'string') {
      errors.push('legalRequirement.certificateNumber is required and must be a string');
    }
    // digitalConsentsAndPermissions is an array
    if ('digitalConsentsAndPermissions' in obj && !Array.isArray(obj.digitalConsentsAndPermissions)) {
      errors.push('legalRequirement.digitalConsentsAndPermissions must be an array');
    }
    return errors;
  }

  private validateCreatePayload(body: any) {
    const errors: string[] = [];
    if (!body) errors.push('body required');
    if (!body.clientId || typeof body.clientId !== 'string') errors.push('clientId is required and must be a string');
    if (!body.title || typeof body.title !== 'string') errors.push('title is required and must be a string');
    // Nested validation for riskAssessment
    errors.push(...this.validateRiskAssessment(body.riskAssessment));
    // Nested validation for personalCare
    errors.push(...this.validatePersonalCare(body.personalCare));
    // Nested validation for everydayActivityPlan
    errors.push(...this.validateEverydayActivityPlan(body.everydayActivityPlan));
  // Nested validation for fallsAndMobility
  errors.push(...this.validateFallsAndMobility(body.fallsAndMobility));
  // Nested validation for psychologicalInfo
  errors.push(...this.validatePsychologicalInfo(body.psychologicalInfo));
  // Nested validation for foodHydration
  errors.push(...this.validateFoodHydration(body.foodHydration));
  // Nested validation for routine
  errors.push(...this.validateRoutine(body.routine));
  // Nested validation for cultureValues
  errors.push(...this.validateCultureValues(body.cultureValues));
  // Nested validation for bodyMap
  errors.push(...this.validateBodyMap(body.bodyMap));
  // Nested validation for legalRequirement
  errors.push(...this.validateLegalRequirement(body.legalRequirement));
  // Nested validation for careRequirements
  errors.push(...this.validateCareRequirements(body.careRequirements));
    return errors;
  }

  private toDateOrNull(val: any) {
    if (!val) return null;
    const d = new Date(val);
    return isNaN(d.getTime()) ? null : d;
  }

  public async createCarePlan(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.body && req.body.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const payload = req.body || {};
      const errors = this.validateCreatePayload(payload);
      if (errors.length) return res.status(400).json({ errors });

      // Build the create data with optional nested creates
      const data: any = {
        tenantId: tenantId.toString(),
        clientId: payload.clientId,
        title: payload.title,
      };

      if (payload.description !== undefined) data.description = payload.description;
      if (payload.startDate) data.startDate = this.toDateOrNull(payload.startDate);
      if (payload.endDate) data.endDate = this.toDateOrNull(payload.endDate);
      if (payload.status) data.status = payload.status;

      // Helper to attach nested create if present
      const attachNested = (key: string, value: any) => {
        if (value === undefined || value === null) return;
        data[key] = { create: value };
      };

      // Simple one-to-one nested objects
      attachNested('riskAssessment', payload.riskAssessment ? { ...payload.riskAssessment, tenantId: tenantId.toString() } : undefined);
      attachNested('personalCare', payload.personalCare ? { ...payload.personalCare, tenantId: tenantId.toString() } : undefined);
      attachNested('everydayActivityPlan', payload.everydayActivityPlan ? { ...payload.everydayActivityPlan, tenantId: tenantId.toString() } : undefined);
      attachNested('fallsAndMobility', payload.fallsAndMobility ? { ...payload.fallsAndMobility, tenantId: tenantId.toString() } : undefined);
      attachNested('psychologicalInfo', payload.psychologicalInfo ? { ...payload.psychologicalInfo, tenantId: tenantId.toString() } : undefined);
      attachNested('foodHydration', payload.foodHydration ? { ...payload.foodHydration, tenantId: tenantId.toString() } : undefined);
      attachNested('routine', payload.routine ? { ...payload.routine, tenantId: tenantId.toString() } : undefined);
      attachNested('cultureValues', payload.cultureValues ? { ...payload.cultureValues, tenantId: tenantId.toString() } : undefined);
      attachNested('bodyMap', payload.bodyMap ? { ...payload.bodyMap, tenantId: tenantId.toString() } : undefined);
      attachNested('legalRequirement', payload.legalRequirement ? { ...payload.legalRequirement, tenantId: tenantId.toString() } : undefined);
      attachNested('careRequirements', payload.careRequirements ? { ...payload.careRequirements, tenantId: tenantId.toString() } : undefined);

      // Medical information is nested and may include arrays
      if (payload.medicalInfo) {
        const mi: any = { ...payload.medicalInfo, tenantId: tenantId.toString() };
        if (Array.isArray(payload.medicalInfo.medications) && payload.medicalInfo.medications.length) {
          mi.medications = { create: payload.medicalInfo.medications.map((m: any) => ({ ...m, tenantId: tenantId.toString() })) };
        }
        if (Array.isArray(payload.medicalInfo.clientAllergies) && payload.medicalInfo.clientAllergies.length) {
          mi.clientAllergies = { create: payload.medicalInfo.clientAllergies.map((a: any) => ({ ...a, tenantId: tenantId.toString() })) };
        }
        data.medicalInfo = { create: mi };
      }

      // MovingHandling may include IntakeLog array
      if (payload.movingHandling) {
        const mh: any = { ...payload.movingHandling, tenantId: tenantId.toString() };
        if (Array.isArray(payload.movingHandling.IntakeLog) && payload.movingHandling.IntakeLog.length) {
          mh.IntakeLog = { create: payload.movingHandling.IntakeLog.map((i: any) => ({ ...i, tenantId: tenantId.toString() })) };
        }
        data.movingHandling = { create: mh };
      }

      // carers (CarePlanCarer) - array of carerId strings or objects
      if (Array.isArray(payload.carers) && payload.carers.length) {
        const carersCreate = payload.carers.map((c: any) => {
          if (typeof c === 'string') return { tenantId: tenantId.toString(), carerId: c };
          return { tenantId: tenantId.toString(), carerId: c.carerId, ...('role' in c ? { role: c.role } : {}) };
        });
        data.carers = { create: carersCreate };
      }

      // include shape for returning full nested relations
      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: true,
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      // create the care plan with nested relations when present
      // Prisma client types may be out-of-date in dev; cast to any so the code compiles until `prisma generate` is run
      const created = await (this.prisma as any).carePlan.create({ data, include: includeShape });

      return res.status(201).json(created);
    } catch (error: any) {
      console.error('createCarePlan error', error);
      return res.status(500).json({ error: getUserFriendlyError(error) });
    }
  }

  // Get all care plans for a tenant (with optional pagination)
  public async listCarePlans(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const page = parseInt((req.query.page as string) || '1', 10);
      const pageSize = parseInt((req.query.pageSize as string) || '50', 10);
      const skip = (Math.max(page, 1) - 1) * pageSize;

      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: true,
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const [items, total] = await Promise.all([
        (this.prisma as any).carePlan.findMany({
          where: { tenantId: tenantId.toString() },
          skip,
          take: pageSize,
          orderBy: { createdAt: 'desc' },
          include: includeShape,
        }),
        (this.prisma as any).carePlan.count({ where: { tenantId: tenantId.toString() } }),
      ]);

      return res.json({ items, total, page, pageSize });
    } catch (error: any) {
      console.error('listCarePlans error', error);
      return res.status(500).json({ error: 'Failed to list care plans', details: error?.message });
    }
  }

  // Get care plans for a specific clientId
  public async getCarePlansByClient(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const clientId = req.params.clientId;
      if (!clientId) return res.status(400).json({ error: 'clientId required in path' });

      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: true,
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const plans = await (this.prisma as any).carePlan.findMany({
        where: { tenantId: tenantId.toString(), clientId },
        orderBy: { createdAt: 'desc' },
        include: includeShape,
      });

      return res.json(plans);
    } catch (error: any) {
      console.error('getCarePlansByClient error', error);
      return res.status(500).json({ error: 'Failed to fetch care plans for client', details: error?.message });
    }
  }

  // Get care plans by carerId (find carePlanIds from CarePlanCarer)
  public async getCarePlansByCarer(req: Request, res: Response) {
    try {
      const tenantId = req.user?.tenantId ?? (req.query && req.query.tenantId);
      if (!tenantId) return res.status(403).json({ error: 'tenantId missing from auth context' });

      const carerId = req.params.carerId;
      if (!carerId) return res.status(400).json({ error: 'carerId required in path' });

      const links = await (this.prisma as any).carePlanCarer.findMany({
        where: { tenantId: tenantId.toString(), carerId },
        select: { carePlanId: true },
      });

      const carePlanIds = links.map((l: any) => l.carePlanId);
      if (!carePlanIds.length) return res.json([]);

      const includeShape = {
        carers: true,
        riskAssessment: true,
        personalCare: true,
        everydayActivityPlan: true,
        fallsAndMobility: true,
        psychologicalInfo: true,
        foodHydration: true,
        routine: true,
        cultureValues: true,
        bodyMap: true,
        legalRequirement: true,
        careRequirements: true,
        medicalInfo: { include: { medications: true, clientAllergies: true } },
        movingHandling: { include: { IntakeLog: true } },
      } as const;

      const plans = await (this.prisma as any).carePlan.findMany({
        where: { id: { in: carePlanIds }, tenantId: tenantId.toString() },
        orderBy: { createdAt: 'desc' },
        include: includeShape,
      });

      return res.json(plans);
    } catch (error: any) {
      console.error('getCarePlansByCarer error', error);
      return res.status(500).json({ error: 'Failed to fetch care plans by carer', details: error?.message });
    }
  }
}
