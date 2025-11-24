const BATHING_ASSISTANCE = ['YES_INDEPENDENTLY', 'YES_WITH_HELP', 'NO_NEEDS_FULL_ASSISTANCE'];
const MOBILITY_LEVEL = ['INDEPENDENT', 'DEPENDENT', 'INDEPENDENT_WITH_AIDS', 'IMMOBILE'];
const MOBILITY_SUPPORT = ['WALKING_STICK', 'WHEELCHAIR', 'NONE', 'OTHERS'];
const GENDER_PREFERENCE = ['NO_PREFERENCE', 'MALE', 'FEMALE', 'NON_BINARY', 'OTHER'];
const CARE_PLAN_STATUS = ['ACTIVE', 'INACTIVE', 'COMPLETED'];

  export function validateCreatePayload(body: any) {
    const errors: string[] = [];
    if (!body) errors.push('body required');
    if (!body.clientId || typeof body.clientId !== 'string') errors.push('clientId is required and must be a string');
    if (!body.title || typeof body.title !== 'string') errors.push('title is required and must be a string');
    // Enum validation for status
    if ('status' in body && body.status !== undefined && body.status !== null) {
      if (typeof body.status !== 'string' || !CARE_PLAN_STATUS.includes(body.status)) {
        errors.push(`status must be one of: ${CARE_PLAN_STATUS.join(', ')}`);
      }
    }

    // Unknown field detection for top-level
    const allowedTopLevel = [
      'tenantId', 'clientId', 'title', 'description', 'startDate', 'endDate', 'status',
      'riskAssessment', 'personalCare', 'everydayActivityPlan', 'fallsAndMobility',
      'psychologicalInfo', 'foodHydration', 'routine', 'cultureValues', 'bodyMap',
      'legalRequirement', 'careRequirements', 'medicalInfo', 'movingHandling', 'carers'
    ];
    Object.keys(body || {}).forEach(key => {
      if (!allowedTopLevel.includes(key)) {
        errors.push(`Unknown field at top-level: ${key}`);
      }
    });

    // Nested validation for riskAssessment (with unknown field detection)
    errors.push(...validateRiskAssessment(body.riskAssessment));
    errors.push(...validatePersonalCare(body.personalCare));
    errors.push(...validateEverydayActivityPlan(body.everydayActivityPlan));
    errors.push(...validateFallsAndMobility(body.fallsAndMobility));
    errors.push(...validatePsychologicalInfo(body.psychologicalInfo));
    errors.push(...validateFoodHydration(body.foodHydration));
    errors.push(...validateRoutine(body.routine));
    errors.push(...validateCultureValues(body.cultureValues));
    errors.push(...validateBodyMap(body.bodyMap));
    errors.push(...validateLegalRequirement(body.legalRequirement));
    errors.push(...validateCareRequirements(body.careRequirements));
    errors.push(...validateMedicalInfo(body.medicalInfo));
    errors.push(...validateMovingHandling(body.movingHandling));
    errors.push(...validateCarers(body.carers));
    return errors;
  }


  
  function validateRiskAssessment(obj: any): string[] {
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

  function validatePersonalCare(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors; // Not required, skip if not present
    // All PersonalCare fields are optional now; validate only when present
    if ('bathingAndShowering' in obj) {
      if (typeof obj.bathingAndShowering !== 'string') {
        errors.push('personalCare.bathingAndShowering must be a string');
      } else if (!BATHING_ASSISTANCE.includes(obj.bathingAndShowering)) {
        errors.push(`personalCare.bathingAndShowering must be one of: ${BATHING_ASSISTANCE.join(', ')}`);
      }
    }
    if ('oralHygiene' in obj && typeof obj.oralHygiene !== 'string') {
      errors.push('personalCare.oralHygiene must be a string');
    }
    if ('maintainThemselves' in obj && typeof obj.maintainThemselves !== 'string') {
      errors.push('personalCare.maintainThemselves must be a string');
    }
    if ('dressThemselves' in obj && typeof obj.dressThemselves !== 'string') {
      errors.push('personalCare.dressThemselves must be a string');
    }
    if ('toiletUsage' in obj && typeof obj.toiletUsage !== 'string') {
      errors.push('personalCare.toiletUsage must be a string');
    }
    if ('bowelControl' in obj && typeof obj.bowelControl !== 'string') {
      errors.push('personalCare.bowelControl must be a string');
    }
    if ('bladderControl' in obj && typeof obj.bladderControl !== 'string') {
      errors.push('personalCare.bladderControl must be a string');
    }
    if ('toiletingSupport' in obj && typeof obj.toiletingSupport !== 'string') {
      errors.push('personalCare.toiletingSupport must be a string');
    }
    if ('continenceCare' in obj && typeof obj.continenceCare !== 'string') {
      errors.push('personalCare.continenceCare must be a string');
    }
    if ('mobilityAssistance' in obj && typeof obj.mobilityAssistance !== 'string') {
      errors.push('personalCare.mobilityAssistance must be a string');
    }
    if ('preferredLanguage' in obj && typeof obj.preferredLanguage !== 'string') {
      errors.push('personalCare.preferredLanguage must be a string');
    }
    if ('communicationStyleNeeds' in obj && typeof obj.communicationStyleNeeds !== 'string') {
      errors.push('personalCare.communicationStyleNeeds must be a string');
    }
    // groomingNeeds must be an array if present
    if ('groomingNeeds' in obj && !Array.isArray(obj.groomingNeeds)) {
      errors.push('personalCare.groomingNeeds must be an array');
    }
    return errors;
  }

  function validateEverydayActivityPlan(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors; // Not required, skip if not present
    // All EverydayActivityPlan fields are optional now; validate only when present
    if ('canTheyShop' in obj && typeof obj.canTheyShop !== 'string') {
      errors.push('everydayActivityPlan.canTheyShop must be a string');
    }
    if ('canTheyCall' in obj && typeof obj.canTheyCall !== 'string') {
      errors.push('everydayActivityPlan.canTheyCall must be a string');
    }
    if ('canTheyWash' in obj && typeof obj.canTheyWash !== 'string') {
      errors.push('everydayActivityPlan.canTheyWash must be a string');
    }
    if ('communityAccessNeeds' in obj && typeof obj.communityAccessNeeds !== 'string') {
      errors.push('everydayActivityPlan.communityAccessNeeds must be a string');
    }
    if ('ExerciseandMobilityActivities' in obj && typeof obj.ExerciseandMobilityActivities !== 'string') {
      errors.push('everydayActivityPlan.ExerciseandMobilityActivities must be a string');
    }
    return errors;
  }

    function validateFallsAndMobility(obj: any): string[] {
        const errors: string[] = [];
          if (!obj) return errors;
          // All FallsAndMobility fields are optional now; validate only when present
          if ('fallenBefore' in obj && typeof obj.fallenBefore !== 'boolean') {
            errors.push('fallsAndMobility.fallenBefore must be a boolean');
          }
          if ('timesFallen' in obj && typeof obj.timesFallen !== 'number') {
            errors.push('fallsAndMobility.timesFallen must be a number');
          }
          if ('mobilityLevel' in obj) {
            if (typeof obj.mobilityLevel !== 'string') {
              errors.push('fallsAndMobility.mobilityLevel must be a string');
            } else if (!MOBILITY_LEVEL.includes(obj.mobilityLevel)) {
              errors.push(`fallsAndMobility.mobilityLevel must be one of: ${MOBILITY_LEVEL.join(', ')}`);
            }
          }
          if ('mobilitySupport' in obj) {
            if (typeof obj.mobilitySupport !== 'string') {
              errors.push('fallsAndMobility.mobilitySupport must be a string');
            } else if (!MOBILITY_SUPPORT.includes(obj.mobilitySupport)) {
              errors.push(`fallsAndMobility.mobilitySupport must be one of: ${MOBILITY_SUPPORT.join(', ')}`);
            }
          }
          if ('activeAsTheyLikeToBe' in obj && typeof obj.activeAsTheyLikeToBe !== 'string') {
            errors.push('fallsAndMobility.activeAsTheyLikeToBe must be a string');
          }
          if ('canTransfer' in obj && typeof obj.canTransfer !== 'string') {
            errors.push('fallsAndMobility.canTransfer must be a string');
          }
          if ('canuseStairs' in obj && typeof obj.canuseStairs !== 'string') {
            errors.push('fallsAndMobility.canuseStairs must be a string');
          }
          if ('canTravelAlone' in obj && typeof obj.canTravelAlone !== 'string') {
            errors.push('fallsAndMobility.canTravelAlone must be a string');
          }
          if ('visionStatus' in obj && typeof obj.visionStatus !== 'string') {
            errors.push('fallsAndMobility.visionStatus must be a string');
          }
          if ('speechStatus' in obj && typeof obj.speechStatus !== 'string') {
            errors.push('fallsAndMobility.speechStatus must be a string');
          }
          if ('hearingStatus' in obj && typeof obj.hearingStatus !== 'string') {
            errors.push('fallsAndMobility.hearingStatus must be a string');
          }
          // Optional: otherMobilitySupport
          if ('otherMobilitySupport' in obj && typeof obj.otherMobilitySupport !== 'string') {
            errors.push('fallsAndMobility.otherMobilitySupport must be a string');
          }
    return errors;
  }

  function validatePsychologicalInfo(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    // All PsychologicalInformation fields are optional now; validate only when present
    if ('healthLevelSatisfaction' in obj && typeof obj.healthLevelSatisfaction !== 'string') {
      errors.push('psychologicalInfo.healthLevelSatisfaction must be a string');
    }
    if ('healthMotivationalLevel' in obj && typeof obj.healthMotivationalLevel !== 'string') {
      errors.push('psychologicalInfo.healthMotivationalLevel must be a string');
    }
    if ('sleepMood' in obj && typeof obj.sleepMood !== 'string') {
      errors.push('psychologicalInfo.sleepMood must be a string');
    }
    if ('specifySleepMood' in obj && typeof obj.specifySleepMood !== 'string') {
      errors.push('psychologicalInfo.specifySleepMood must be a string');
    }
    if ('sleepStatus' in obj && typeof obj.sleepStatus !== 'string') {
      errors.push('psychologicalInfo.sleepStatus must be a string');
    }
    if ('anyoneWorriedAboutMemory' in obj && typeof obj.anyoneWorriedAboutMemory !== 'boolean') {
      errors.push('psychologicalInfo.anyoneWorriedAboutMemory must be a boolean');
    }
    if ('memoryStatus' in obj && typeof obj.memoryStatus !== 'string') {
      errors.push('psychologicalInfo.memoryStatus must be a string');
    }
    if ('specifyMemoryStatus' in obj && typeof obj.specifyMemoryStatus !== 'string') {
      errors.push('psychologicalInfo.specifyMemoryStatus must be a string');
    }
    if ('canTheyDoHouseKeeping' in obj && typeof obj.canTheyDoHouseKeeping !== 'string') {
      errors.push('psychologicalInfo.canTheyDoHouseKeeping must be a string');
    }
    if ('houseKeepingSupport' in obj && typeof obj.houseKeepingSupport !== 'boolean') {
      errors.push('psychologicalInfo.houseKeepingSupport must be a boolean');
    }
    return errors;
  }

  function validateFoodHydration(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    // All FoodNutritionHydration fields are optional now; validate only when present
    if ('dietaryRequirements' in obj && typeof obj.dietaryRequirements !== 'string') {
      errors.push('foodHydration.dietaryRequirements must be a string');
    }
    if ('foodOrDrinkAllergies' in obj && typeof obj.foodOrDrinkAllergies !== 'boolean') {
      errors.push('foodHydration.foodOrDrinkAllergies must be a boolean');
    }
    if ('foodAllergiesSpecification' in obj && typeof obj.foodAllergiesSpecification !== 'string') {
      errors.push('foodHydration.foodAllergiesSpecification must be a string');
    }
    if ('allergiesImpact' in obj && typeof obj.allergiesImpact !== 'string') {
      errors.push('foodHydration.allergiesImpact must be a string');
    }
    if ('favouriteFoods' in obj && typeof obj.favouriteFoods !== 'string') {
      errors.push('foodHydration.favouriteFoods must be a string');
    }
    if ('foodTextures' in obj && typeof obj.foodTextures !== 'string') {
      errors.push('foodHydration.foodTextures must be a string');
    }
    if ('appetiteLevel' in obj && typeof obj.appetiteLevel !== 'string') {
      errors.push('foodHydration.appetiteLevel must be a string');
    }
    if ('swallowingDifficulties' in obj && typeof obj.swallowingDifficulties !== 'string') {
      errors.push('foodHydration.swallowingDifficulties must be a string');
    }
    if ('medicationsAffectingSwallowing' in obj && typeof obj.medicationsAffectingSwallowing !== 'string') {
      errors.push('foodHydration.medicationsAffectingSwallowing must be a string');
    }
    if ('specifyMedicationsAffectingSwallowing' in obj && typeof obj.specifyMedicationsAffectingSwallowing !== 'string') {
      errors.push('foodHydration.specifyMedicationsAffectingSwallowing must be a string');
    }
    if ('canFeedSelf' in obj && typeof obj.canFeedSelf !== 'string') {
      errors.push('foodHydration.canFeedSelf must be a string');
    }
    if ('canPrepareLightMeals' in obj && typeof obj.canPrepareLightMeals !== 'string') {
      errors.push('foodHydration.canPrepareLightMeals must be a string');
    }
    if ('canCookMeals' in obj && typeof obj.canCookMeals !== 'string') {
      errors.push('foodHydration.canCookMeals must be a string');
    }
    if ('clientFoodGiver' in obj && typeof obj.clientFoodGiver !== 'string') {
      errors.push('foodHydration.clientFoodGiver must be a string');
    }
    if ('mealtimeSupport' in obj && typeof obj.mealtimeSupport !== 'string') {
      errors.push('foodHydration.mealtimeSupport must be a string');
    }
    if ('hydrationSchedule' in obj && typeof obj.hydrationSchedule !== 'string') {
      errors.push('foodHydration.hydrationSchedule must be a string');
    }
    if ('strongDislikes' in obj && typeof obj.strongDislikes !== 'string') {
      errors.push('foodHydration.strongDislikes must be a string');
    }
    if ('fluidPreferences' in obj && typeof obj.fluidPreferences !== 'string') {
      errors.push('foodHydration.fluidPreferences must be a string');
    }
    return errors;
  }

  function validateRoutine(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    // All RoutinePreference fields are optional now; validate only when present
    if ('PersonalBiography' in obj && typeof obj.PersonalBiography !== 'string') {
      errors.push('routine.PersonalBiography must be a string');
    }
    if ('haveJob' in obj && typeof obj.haveJob !== 'boolean') {
      errors.push('routine.haveJob must be a boolean');
    }
    if ('aboutJob' in obj && typeof obj.aboutJob !== 'string') {
      errors.push('routine.aboutJob must be a string');
    }
    if ('haveImportantPerson' in obj && typeof obj.haveImportantPerson !== 'boolean') {
      errors.push('routine.haveImportantPerson must be a boolean');
    }
    if ('aboutImportantPerson' in obj && typeof obj.aboutImportantPerson !== 'string') {
      errors.push('routine.aboutImportantPerson must be a string');
    }
    if ('significantPersonHasLocation' in obj && typeof obj.significantPersonHasLocation !== 'boolean') {
      errors.push('routine.significantPersonHasLocation must be a boolean');
    }
    if ('importantPersonLocationEffects' in obj && typeof obj.importantPersonLocationEffects !== 'string') {
      errors.push('routine.importantPersonLocationEffects must be a string');
    }
    if ('canMaintainOralHygiene' in obj && typeof obj.canMaintainOralHygiene !== 'string') {
      errors.push('routine.canMaintainOralHygiene must be a string');
    }
    if ('careGiverGenderPreference' in obj) {
      if (typeof obj.careGiverGenderPreference !== 'string') {
        errors.push('routine.careGiverGenderPreference must be a string');
      } else if (!GENDER_PREFERENCE.includes(obj.careGiverGenderPreference)) {
        errors.push(`routine.careGiverGenderPreference must be one of: ${GENDER_PREFERENCE.join(', ')}`);
      }
    }
    if ('autonomyPreference' in obj && typeof obj.autonomyPreference !== 'string') {
      errors.push('routine.autonomyPreference must be a string');
    }
    if ('dailyRoutine' in obj && typeof obj.dailyRoutine !== 'string') {
      errors.push('routine.dailyRoutine must be a string');
    }
    if ('haveSpecificImportantRoutine' in obj && typeof obj.haveSpecificImportantRoutine !== 'boolean') {
      errors.push('routine.haveSpecificImportantRoutine must be a boolean');
    }
    if ('haveDislikes' in obj && typeof obj.haveDislikes !== 'boolean') {
      errors.push('routine.haveDislikes must be a boolean');
    }
    if ('dislikesEffect' in obj && typeof obj.dislikesEffect !== 'string') {
      errors.push('routine.dislikesEffect must be a string');
    }
    if ('haveHobbiesRoutines' in obj && typeof obj.haveHobbiesRoutines !== 'boolean') {
      errors.push('routine.haveHobbiesRoutines must be a boolean');
    }
    if ('hobbiesRoutinesEffect' in obj && typeof obj.hobbiesRoutinesEffect !== 'string') {
      errors.push('routine.hobbiesRoutinesEffect must be a string');
    }
    return errors;
  }

  function validateCareRequirements(obj: any): string[] {
    const errors: string[] = [];
    if (!obj) return errors;
    // All CareRequirements fields are optional now; validate only when present
    const allowedCareTypes = [
      'SINGLE_HANDED_CALL',
      'DOUBLE_HANDED_CALL',
      'SPECIALCARE'
    ];
    if ('careType' in obj && obj.careType !== undefined && obj.careType !== null) {
      if (typeof obj.careType !== 'string' || !allowedCareTypes.includes(obj.careType)) {
        errors.push(`careRequirements.careType must be one of: ${allowedCareTypes.join(', ')}`);
      }
    }
    // Optional contract bounds (ISO date strings) and rollingWeeks (non-negative integer)
    if ('contractStart' in obj && obj.contractStart !== undefined && obj.contractStart !== null) {
      if (isNaN(Date.parse(obj.contractStart))) {
        errors.push('careRequirements.contractStart must be a valid date string');
      }
    }
    if ('contractEnd' in obj && obj.contractEnd !== undefined && obj.contractEnd !== null) {
      if (isNaN(Date.parse(obj.contractEnd))) {
        errors.push('careRequirements.contractEnd must be a valid date string');
      }
    }
    if ('rollingWeeks' in obj && obj.rollingWeeks !== undefined && obj.rollingWeeks !== null) {
      if (typeof obj.rollingWeeks !== 'number' || !Number.isFinite(obj.rollingWeeks) || obj.rollingWeeks < 0) {
        errors.push('careRequirements.rollingWeeks must be a non-negative number');
      }
    }
    return errors;
  } 
 
  function validateCarers(carers: any): string[] {
    const errors: string[] = [];
    if (carers === undefined || carers === null) return errors; // Not required, skip if not present
    if (!Array.isArray(carers)) {
      errors.push('carers must be an array');
      return errors;
    }
    carers.forEach((c, idx) => {
      if (typeof c === 'string') {
        if (!c || typeof c !== 'string') {
          errors.push(`carers[${idx}] must be a non-empty string (carerId)`);
        }
      } else if (typeof c === 'object' && c !== null) {
        if (!('carerId' in c) || typeof c.carerId !== 'string' || !c.carerId) {
          errors.push(`carers[${idx}].carerId is required and must be a non-empty string`);
        }
        if ('role' in c && typeof c.role !== 'string') {
          errors.push(`carers[${idx}].role must be a string if present`);
        }
      } else {
        errors.push(`carers[${idx}] must be a string (carerId) or object with carerId`);
      }
    });
    return errors;
  }

function validateLegalRequirement(obj: any): string[] {
      const errors: string[] = [];
      if (!obj) return errors;
      // All LegalRequirement fields are optional now; validate only when present
      if ('attorneyInPlace' in obj && typeof obj.attorneyInPlace !== 'boolean') {
        errors.push('legalRequirement.attorneyInPlace must be a boolean');
      }
      if ('attorneyType' in obj && typeof obj.attorneyType !== 'string') {
        errors.push('legalRequirement.attorneyType must be a string');
      }
      if ('attorneyName' in obj && typeof obj.attorneyName !== 'string') {
        errors.push('legalRequirement.attorneyName must be a string');
      }
      if ('attorneyContact' in obj && typeof obj.attorneyContact !== 'string') {
        errors.push('legalRequirement.attorneyContact must be a string');
      }
      if ('attorneyEmail' in obj && typeof obj.attorneyEmail !== 'string') {
        errors.push('legalRequirement.attorneyEmail must be a string');
      }
      if ('solicitor' in obj && typeof obj.solicitor !== 'string') {
        errors.push('legalRequirement.solicitor must be a string');
      }
      if ('certificateNumber' in obj && typeof obj.certificateNumber !== 'string') {
        errors.push('legalRequirement.certificateNumber must be a string');
      }
      if ('certificateUpload' in obj && typeof obj.certificateUpload !== 'string') {
        errors.push('legalRequirement.certificateUpload must be a string');
      }
      // digitalConsentsAndPermissions is an array
      if ('digitalConsentsAndPermissions' in obj && !Array.isArray(obj.digitalConsentsAndPermissions)) {
        errors.push('legalRequirement.digitalConsentsAndPermissions must be an array');
      }
      if ('consertUpload' in obj && typeof obj.consertUpload !== 'string') {
        errors.push('legalRequirement.consertUpload must be a string');
      }
      return errors;
    }
  
    function validateMovingHandling(obj: any): string[] {
      const errors: string[] = [];
      if (!obj) return errors;
      // All MovingHandling fields are optional now; validate only when present
      if ('equipmentsNeeds' in obj && typeof obj.equipmentsNeeds !== 'string') {
        errors.push('movingHandling.equipmentsNeeds must be a string');
      }
      if ('anyPainDuringRestingAndMovement' in obj && typeof obj.anyPainDuringRestingAndMovement !== 'string') {
        errors.push('movingHandling.anyPainDuringRestingAndMovement must be a string');
      }
      if ('anyCognitiveImpairment' in obj && typeof obj.anyCognitiveImpairment !== 'string') {
        errors.push('movingHandling.anyCognitiveImpairment must be a string');
      }
      if ('behaviouralChanges' in obj && typeof obj.behaviouralChanges !== 'boolean') {
        errors.push('movingHandling.behaviouralChanges must be a boolean');
      }
      if ('describeBehaviouralChanges' in obj && typeof obj.describeBehaviouralChanges !== 'string') {
        errors.push('movingHandling.describeBehaviouralChanges must be a string');
      }
      if ('walkIndependently' in obj && typeof obj.walkIndependently !== 'boolean') {
        errors.push('movingHandling.walkIndependently must be a boolean');
      }
      if ('manageStairs' in obj && typeof obj.manageStairs !== 'boolean') {
        errors.push('movingHandling.manageStairs must be a boolean');
      }
      if ('sittingToStandingDependence' in obj && typeof obj.sittingToStandingDependence !== 'string') {
        errors.push('movingHandling.sittingToStandingDependence must be a string');
      }
      if ('limitedSittingBalance' in obj && typeof obj.limitedSittingBalance !== 'boolean') {
        errors.push('movingHandling.limitedSittingBalance must be a boolean');
      }
      if ('turnInBed' in obj && typeof obj.turnInBed !== 'boolean') {
        errors.push('movingHandling.turnInBed must be a boolean');
      }
      if ('lyingToSittingDependence' in obj && typeof obj.lyingToSittingDependence !== 'boolean') {
        errors.push('movingHandling.lyingToSittingDependence must be a boolean');
      }
      if ('gettingUpFromChairDependence' in obj && typeof obj.gettingUpFromChairDependence !== 'string') {
        errors.push('movingHandling.gettingUpFromChairDependence must be a string');
      }
      if ('bathOrShower' in obj && typeof obj.bathOrShower !== 'string') {
        errors.push('movingHandling.bathOrShower must be a string');
      }
      if ('chairToCommodeOrBed' in obj && typeof obj.chairToCommodeOrBed !== 'boolean') {
        errors.push('movingHandling.chairToCommodeOrBed must be a boolean');
      }
      if ('profilingBedAndMattress' in obj && typeof obj.profilingBedAndMattress !== 'boolean') {
        errors.push('movingHandling.profilingBedAndMattress must be a boolean');
      }
      // transferRisks and behaviouralChallenges are arrays
      if ('transferRisks' in obj && !Array.isArray(obj.transferRisks)) {
        errors.push('movingHandling.transferRisks must be an array');
      }
      if ('behaviouralChallenges' in obj && !Array.isArray(obj.behaviouralChallenges)) {
        errors.push('movingHandling.behaviouralChallenges must be an array');
      }
      if ('riskManagementPlan' in obj && typeof obj.riskManagementPlan !== 'string') {
        errors.push('movingHandling.riskManagementPlan must be a string');
      }
      if ('locationRiskReview' in obj && typeof obj.locationRiskReview !== 'string') {
        errors.push('movingHandling.locationRiskReview must be a string');
      }
      if ('EvacuationPlanRequired' in obj && typeof obj.EvacuationPlanRequired !== 'boolean') {
        errors.push('movingHandling.EvacuationPlanRequired must be a boolean');
      }
      if ('dailyGoal' in obj && typeof obj.dailyGoal !== 'string') {
        errors.push('movingHandling.dailyGoal must be a string');
      }
      // IntakeLog: should be an array if present, and each log must have required fields
      if ('IntakeLog' in obj) {
        if (!Array.isArray(obj.IntakeLog)) {
          errors.push('movingHandling.IntakeLog must be an array');
        } else {
          obj.IntakeLog.forEach((log: any, idx: number) => {
            if (typeof log !== 'object' || log === null) {
              errors.push(`movingHandling.IntakeLog[${idx}] must be an object`);
              return;
            }
            if (!('time' in log) || typeof log.time !== 'string') {
              errors.push(`movingHandling.IntakeLog[${idx}].time is required and must be a string`);
            }
            if (!('amount' in log) || typeof log.amount !== 'string') {
              errors.push(`movingHandling.IntakeLog[${idx}].amount is required and must be a string`);
            }
            if ('notes' in log && typeof log.notes !== 'string') {
              errors.push(`movingHandling.IntakeLog[${idx}].notes must be a string`);
            }
          });
        }
      }
      return errors;
    }

      function validateMedicalInfo(obj: any): string[] {
        const errors: string[] = [];
              if (!obj) return errors;
              // All MedicalInformation fields are optional now; validate only when present
              if ('primaryDiagnosis' in obj && typeof obj.primaryDiagnosis !== 'string') {
                errors.push('medicalInfo.primaryDiagnosis must be a string');
              }
              if ('secondaryDiagnoses' in obj && typeof obj.secondaryDiagnoses !== 'string') {
                errors.push('medicalInfo.secondaryDiagnoses must be a string');
              }
              if ('pastMedicalHistory' in obj && typeof obj.pastMedicalHistory !== 'string') {
                errors.push('medicalInfo.pastMedicalHistory must be a string');
              }
              if ('medicalSupport' in obj && typeof obj.medicalSupport !== 'boolean') {
                errors.push('medicalInfo.medicalSupport must be a boolean');
              }
              if ('breathingDifficulty' in obj && typeof obj.breathingDifficulty !== 'boolean') {
                errors.push('medicalInfo.breathingDifficulty must be a boolean');
              }
              if ('breathingSupportNeed' in obj && typeof obj.breathingSupportNeed !== 'string') {
                errors.push('medicalInfo.breathingSupportNeed must be a string');
              }
              if ('useAirWayManagementEquipment' in obj && typeof obj.useAirWayManagementEquipment !== 'boolean') {
                errors.push('medicalInfo.useAirWayManagementEquipment must be a boolean');
              }
              if ('specifyAirwayEquipment' in obj && typeof obj.specifyAirwayEquipment !== 'string') {
                errors.push('medicalInfo.specifyAirwayEquipment must be a string');
              }
              if ('airwayEquipmentRisk' in obj && typeof obj.airwayEquipmentRisk !== 'string') {
                errors.push('medicalInfo.airwayEquipmentRisk must be a string');
              }
              if ('airWayEquipmentMitigationPlan' in obj && typeof obj.airWayEquipmentMitigationPlan !== 'string') {
                errors.push('medicalInfo.airWayEquipmentMitigationPlan must be a string');
              }
              if ('haveSkinPressureSores' in obj && typeof obj.haveSkinPressureSores !== 'boolean') {
                errors.push('medicalInfo.haveSkinPressureSores must be a boolean');
              }
              if ('skinPressureConcerningIssues' in obj && typeof obj.skinPressureConcerningIssues !== 'boolean') {
                errors.push('medicalInfo.skinPressureConcerningIssues must be a boolean');
              }
              if ('skinAdditionalInformation' in obj && typeof obj.skinAdditionalInformation !== 'string') {
                errors.push('medicalInfo.skinAdditionalInformation must be a string');
              }
              if ('currentHealthStatus' in obj && typeof obj.currentHealthStatus !== 'string') {
                errors.push('medicalInfo.currentHealthStatus must be a string');
              }
              if ('raisedSafeGuardingIssue' in obj && typeof obj.raisedSafeGuardingIssue !== 'boolean') {
                errors.push('medicalInfo.raisedSafeGuardingIssue must be a boolean');
              }
              if ('safeGuardingAdditionalInformation' in obj && typeof obj.safeGuardingAdditionalInformation !== 'string') {
                errors.push('medicalInfo.safeGuardingAdditionalInformation must be a string');
              }
        // medications: should be an array if present, and each medication must have required fields
        if ('medications' in obj) {
          if (!Array.isArray(obj.medications)) {
            errors.push('medicalInfo.medications must be an array');
          } else {
            obj.medications.forEach((med: any, idx: number) => {
              if (typeof med !== 'object' || med === null) {
                errors.push(`medicalInfo.medications[${idx}] must be an object`);
                return;
              }
              if (!('drugName' in med) || typeof med.drugName !== 'string') {
                errors.push(`medicalInfo.medications[${idx}].drugName is required and must be a string`);
              }
              if (!('dosage' in med) || typeof med.dosage !== 'string') {
                errors.push(`medicalInfo.medications[${idx}].dosage is required and must be a string`);
              }
              if (!('frequency' in med) || typeof med.frequency !== 'string') {
                errors.push(`medicalInfo.medications[${idx}].frequency is required and must be a string`);
              }
            });
          }
        }
        if ('primaryDoctor' in obj && typeof obj.primaryDoctor !== 'string') {
          errors.push('medicalInfo.primaryDoctor must be a string');
        }
        if ('supportContactPhone' in obj && typeof obj.supportContactPhone !== 'string') {
          errors.push('medicalInfo.supportContactPhone must be a string');
        }
        if ('specialistContact' in obj && typeof obj.specialistContact !== 'string') {
          errors.push('medicalInfo.specialistContact must be a string');
        }
        if ('HospitalContact' in obj && typeof obj.HospitalContact !== 'string') {
          errors.push('medicalInfo.HospitalContact must be a string');
        }
        if ('medicalReportUpload' in obj && typeof obj.medicalReportUpload !== 'string') {
          errors.push('medicalInfo.medicalReportUpload must be a string');
        }
        if ('knownAllergies' in obj && typeof obj.knownAllergies !== 'boolean') {
          errors.push('medicalInfo.knownAllergies must be a boolean');
        }
        // clientAllergies: should be an array if present
          if ('clientAllergies' in obj) {
            if (!Array.isArray(obj.clientAllergies)) {
              errors.push('medicalInfo.clientAllergies must be an array');
            } else {
              obj.clientAllergies.forEach((allergy: any, idx: number) => {
                if (typeof allergy !== 'object' || allergy === null) {
                  errors.push(`medicalInfo.clientAllergies[${idx}] must be an object`);
                  return;
                }
                // Schema fields
                if (!('allergy' in allergy) || typeof allergy.allergy !== 'string') {
                  errors.push(`medicalInfo.clientAllergies[${idx}].allergy is required and must be a string`);
                }
                if (!('severity' in allergy) || typeof allergy.severity !== 'string') {
                  errors.push(`medicalInfo.clientAllergies[${idx}].severity is required and must be a string`);
                }
                if (!('allergyDetails' in allergy) || typeof allergy.allergyDetails !== 'string') {
                  errors.push(`allergyDetails is required and must be a string`);
                }
                if (!('allergyMedicationFrequency' in allergy) || typeof allergy.allergyMedicationFrequency !== 'string') {
                  errors.push(`medicalInfo.clientAllergies[${idx}].allergyMedicationFrequency is required and must be a string`);
                }
                if (!('allergyMedicationName' in allergy) || typeof allergy.allergyMedicationName !== 'string') {
                  errors.push(`medicalInfo.clientAllergies[${idx}].allergyMedicationName is required and must be a string`);
                }
                if (!('allergyMedicationDosage' in allergy) || typeof allergy.allergyMedicationDosage !== 'string') {
                  errors.push(`medicalInfo.clientAllergies[${idx}].allergyMedicationDosage is required and must be a string`);
                }
                if (!('Appointments' in allergy) || isNaN(Date.parse(allergy.Appointments))) {
                  errors.push(`medicalInfo.clientAllergies[${idx}].Appointments is required and must be a valid date string`);
                }
                if (!('knownTrigger' in allergy) || typeof allergy.knownTrigger !== 'string') {
                  errors.push(`medicalInfo.clientAllergies[${idx}].knownTrigger is required and must be a string`);
                }
              });
            }
          }
          return errors;
        }
    
    function validateCultureValues(obj: any): string[] {
        const errors: string[] = [];
        if (!obj) return errors;
        // All CultureValues fields are optional now; validate only when present
        if ('religiousBackground' in obj && typeof obj.religiousBackground !== 'string') {
          errors.push('cultureValues.religiousBackground must be a string');
        }
        if ('ethnicGroup' in obj && typeof obj.ethnicGroup !== 'string') {
          errors.push('cultureValues.ethnicGroup must be a string');
        }
        if ('culturalAccommodation' in obj && typeof obj.culturalAccommodation !== 'string') {
          errors.push('cultureValues.culturalAccommodation must be a string');
        }
        if ('sexualityandRelationshipPreferences' in obj && typeof obj.sexualityandRelationshipPreferences !== 'string') {
          errors.push('cultureValues.sexualityandRelationshipPreferences must be a string');
        }
        if ('sexImpartingCareNeeds' in obj && typeof obj.sexImpartingCareNeeds !== 'string') {
          errors.push('cultureValues.sexImpartingCareNeeds must be a string');
        }
        if ('preferredLanguage' in obj && typeof obj.preferredLanguage !== 'string') {
          errors.push('cultureValues.preferredLanguage must be a string');
        }
        if ('communicationStyleNeeds' in obj && !Array.isArray(obj.communicationStyleNeeds)) {
          errors.push('cultureValues.communicationStyleNeeds must be an array');
        }
        if ('preferredMethodOfCommunication' in obj && typeof obj.preferredMethodOfCommunication !== 'string') {
          errors.push('cultureValues.preferredMethodOfCommunication must be a string');
        }
        if ('keyFamilyMembers' in obj && typeof obj.keyFamilyMembers !== 'string') {
          errors.push('cultureValues.keyFamilyMembers must be a string');
        }
        if ('receivesInformalCare' in obj && typeof obj.receivesInformalCare !== 'boolean') {
          errors.push('cultureValues.receivesInformalCare must be a boolean');
        }
        if ('specifyConcernsOnInformalCare' in obj && typeof obj.specifyConcernsOnInformalCare !== 'string') {
          errors.push('cultureValues.specifyConcernsOnInformalCare must be a string');
        }
        if ('receivesFormalCare' in obj && typeof obj.receivesFormalCare !== 'boolean') {
          errors.push('cultureValues.receivesFormalCare must be a boolean');
        }
        if ('socialGroupAndCommunity' in obj && typeof obj.socialGroupAndCommunity !== 'string') {
          errors.push('cultureValues.socialGroupAndCommunity must be a string');
        }
        if ('mentalWellbeingTracking' in obj && typeof obj.mentalWellbeingTracking !== 'boolean') {
          errors.push('cultureValues.mentalWellbeingTracking must be a boolean');
        }
        // emotionalSupportNeeds is an array
        if ('emotionalSupportNeeds' in obj && !Array.isArray(obj.emotionalSupportNeeds)) {
          errors.push('cultureValues.emotionalSupportNeeds must be an array');
        }
        return errors;
      }
    
      function validateBodyMap(obj: any): string[] {
        const errors: string[] = [];
        if (!obj) return errors;
        // All BodyMap fields are optional now; validate only when present
        if ('visitFrequency' in obj && typeof obj.visitFrequency !== 'string') {
          errors.push('bodyMap.visitFrequency must be a string');
        }
        if ('carePlanReviewDate' in obj && isNaN(Date.parse(obj.carePlanReviewDate))) {
          errors.push('bodyMap.carePlanReviewDate must be a valid date string');
        }
        if ('invoicingCycle' in obj && typeof obj.invoicingCycle !== 'string') {
          errors.push('bodyMap.invoicingCycle must be a string');
        }
        if ('fundingAndInsuranceDetails' in obj && typeof obj.fundingAndInsuranceDetails !== 'string') {
          errors.push('bodyMap.fundingAndInsuranceDetails must be a string');
        }
        if ('assignedCareManager' in obj && typeof obj.assignedCareManager !== 'string') {
          errors.push('bodyMap.assignedCareManager must be a string');
        }
        if ('initialClinicalObservations' in obj && typeof obj.initialClinicalObservations !== 'boolean') {
          errors.push('bodyMap.initialClinicalObservations must be a boolean');
        }
        if ('initialSkinIntegrity' in obj && typeof obj.initialSkinIntegrity !== 'boolean') {
          errors.push('bodyMap.initialSkinIntegrity must be a boolean');
        }
        if ('type' in obj && typeof obj.type !== 'string') {
          errors.push('bodyMap.type must be a string');
        }
        if ('size' in obj && typeof obj.size !== 'string') {
          errors.push('bodyMap.size must be a string');
        }
        if ('locationDescription' in obj && typeof obj.locationDescription !== 'string') {
          errors.push('bodyMap.locationDescription must be a string');
        }
        if ('dateFirstObserved' in obj && isNaN(Date.parse(obj.dateFirstObserved))) {
          errors.push('bodyMap.dateFirstObserved must be a valid date string');
        }
        if ('weight' in obj && typeof obj.weight !== 'string') {
          errors.push('bodyMap.weight must be a string');
        }
        if ('height' in obj && typeof obj.height !== 'string') {
          errors.push('bodyMap.height must be a string');
        }
        return errors;
      }