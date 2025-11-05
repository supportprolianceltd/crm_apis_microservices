import { PrismaClient } from '@prisma/client';
import { GeocodingService } from './geocoding.service';
import { logger } from '../utils/logger';

// ========== INTERFACES ==========

export interface ValidationResult {
  schedulability: number; // 0-100 percentage
  totalItems: number;
  validItems: number;
  issues: ValidationIssue[];
  summary: ValidationSummary;
}

export interface ValidationIssue {
  id: string;
  type: ValidationIssueType;
  entity: 'client' | 'carer' | 'visit' | 'constraint';
  entityId: string;
  entityName: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  message: string;
  details: string;
  suggestedAction: string;
  autoFixable: boolean;
  fieldName?: string;
  currentValue?: any;
  expectedValue?: any;
}

export interface ValidationSummary {
  criticalIssues: number;
  highIssues: number;
  mediumIssues: number;
  lowIssues: number;
  autoFixableIssues: number;
  issuesByType: { [key: string]: number };
  issuesByEntity: { [key: string]: number };
}

export type ValidationIssueType =
  | 'missing_postcode'
  | 'missing_coordinates'
  | 'missing_skills'
  | 'invalid_time_window'
  | 'credential_expiry'
  | 'missing_contact'
  | 'invalid_address'
  | 'duplicate_entry'
  | 'insufficient_capacity'
  | 'skill_mismatch'
  | 'availability_conflict'
  | 'missing_requirements'
  | 'invalid_duration'
  | 'geocoding_failed';

export interface FixAction {
  issueId: string;
  action: 'geocode' | 'add_skill' | 'extend_credential' | 'update_field' | 'delete' | 'merge';
  params?: any;
}

export interface FixResult {
  success: boolean;
  issueId: string;
  action: string;
  message: string;
  updatedEntity?: any;
  error?: string;
}

// ========== DATA VALIDATION SERVICE ==========

export class DataValidationService {
  constructor(
    private prisma: PrismaClient,
    private geocodingService: GeocodingService
  ) {}

  /**
   * Validate all data for a tenant
    */
   async validateData(tenantId: string): Promise<ValidationResult> {
    try {
      logger.info('Starting tenant data validation', { tenantId });

      const [clientIssues, carerIssues, visitIssues, constraintIssues] = await Promise.all([
        this.validateClients(tenantId),
        this.validateCarers(tenantId),
        this.validateVisits(tenantId),
        this.validateConstraints(tenantId)
      ]);

      const allIssues = [...clientIssues, ...carerIssues, ...visitIssues, ...constraintIssues];
      const totalItems = await this.getTotalItemCount(tenantId);
      const validItems = totalItems - allIssues.filter(i => i.severity === 'critical').length;
      const schedulability = totalItems > 0 ? Math.round((validItems / totalItems) * 100) : 0;

      const summary = this.generateSummary(allIssues);

      logger.info('Validation completed', {
        tenantId,
        schedulability,
        totalIssues: allIssues.length,
        criticalIssues: summary.criticalIssues
      });

      return {
        schedulability,
        totalItems,
        validItems,
        issues: allIssues,
        summary
      };

    } catch (error) {
      logger.error('Failed to validate tenant data:', error);
      throw error;
    }
  }

  /**
   * Validate clients (ExternalRequest entities)
   */
  async validateClients(tenantId: string): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];

    const clients = await this.prisma.externalRequest.findMany({
      where: { tenantId, status: { in: ['PENDING', 'APPROVED'] } },
      select: {
        id: true,
        requestorName: true,
        requestorEmail: true,
        address: true,
        postcode: true,
        latitude: true,
        longitude: true,
        scheduledStartTime: true,
        scheduledEndTime: true,
        estimatedDuration: true,
        requirements: true,
        urgency: true
      }
    });

    logger.debug('Validating clients', { count: clients.length });

    for (const client of clients) {
      // Check missing postcode
      if (!client.postcode || client.postcode.trim().length === 0) {
        issues.push({
          id: `issue_${client.id}_postcode`,
          type: 'missing_postcode',
          entity: 'client',
          entityId: client.id,
          entityName: client.requestorName || client.requestorEmail,
          severity: 'high',
          message: 'Missing postcode',
          details: `Client "${client.requestorName}" has no postcode`,
          suggestedAction: 'Geocode from address or add manually',
          autoFixable: !!client.address,
          fieldName: 'postcode',
          currentValue: null,
          expectedValue: 'Valid UK postcode'
        });
      }

      // Check missing coordinates
      if (!client.latitude || !client.longitude) {
        issues.push({
          id: `issue_${client.id}_coordinates`,
          type: 'missing_coordinates',
          entity: 'client',
          entityId: client.id,
          entityName: client.requestorName || client.requestorEmail,
          severity: 'critical',
          message: 'Missing location coordinates',
          details: `Cannot cluster or calculate travel without lat/lon`,
          suggestedAction: 'Geocode address to get coordinates',
          autoFixable: !!(client.address || client.postcode),
          fieldName: 'latitude,longitude',
          currentValue: null,
          expectedValue: 'Valid latitude and longitude'
        });
      }

      // Check invalid address
      if (!client.address || client.address.trim().length < 10) {
        issues.push({
          id: `issue_${client.id}_address`,
          type: 'invalid_address',
          entity: 'client',
          entityId: client.id,
          entityName: client.requestorName || client.requestorEmail,
          severity: 'high',
          message: 'Invalid or incomplete address',
          details: `Address too short or missing`,
          suggestedAction: 'Add complete address',
          autoFixable: false,
          fieldName: 'address',
          currentValue: client.address,
          expectedValue: 'Complete address with street, city, postcode'
        });
      }

      // Check invalid time windows
      if (client.scheduledStartTime && client.scheduledEndTime) {
        if (client.scheduledEndTime <= client.scheduledStartTime) {
          issues.push({
            id: `issue_${client.id}_timewindow`,
            type: 'invalid_time_window',
            entity: 'client',
            entityId: client.id,
            entityName: client.requestorName || client.requestorEmail,
            severity: 'critical',
            message: 'Invalid time window',
            details: `End time (${client.scheduledEndTime}) is before or equal to start time (${client.scheduledStartTime})`,
            suggestedAction: 'Correct time window - end must be after start',
            autoFixable: false,
            fieldName: 'scheduledEndTime',
            currentValue: client.scheduledEndTime,
            expectedValue: `Time after ${client.scheduledStartTime}`
          });
        }
      }

      // Check missing duration
      if (!client.estimatedDuration || client.estimatedDuration <= 0) {
        issues.push({
          id: `issue_${client.id}_duration`,
          type: 'invalid_duration',
          entity: 'visit',
          entityId: client.id,
          entityName: client.requestorName || client.requestorEmail,
          severity: 'medium',
          message: 'Missing or invalid visit duration',
          details: `Duration is ${client.estimatedDuration} minutes`,
          suggestedAction: 'Set estimated duration (typically 30-120 minutes)',
          autoFixable: false,
          fieldName: 'estimatedDuration',
          currentValue: client.estimatedDuration,
          expectedValue: 'Positive number (e.g., 60 minutes)'
        });
      }

      // Check missing requirements
      if (client.urgency === 'HIGH' || client.urgency === 'URGENT') {
        if (!client.requirements || client.requirements.trim().length < 5) {
          issues.push({
            id: `issue_${client.id}_requirements`,
            type: 'missing_requirements',
            entity: 'visit',
            entityId: client.id,
            entityName: client.requestorName || client.requestorEmail,
            severity: 'medium',
            message: 'Urgent visit missing detailed requirements',
            details: `Urgent visits should specify care requirements clearly`,
            suggestedAction: 'Add care requirements (skills, equipment, preferences)',
            autoFixable: false,
            fieldName: 'requirements',
            currentValue: client.requirements,
            expectedValue: 'Detailed care requirements'
          });
        }
      }

      // Check missing contact info
      if (!client.requestorEmail && !client.requestorName) {
        issues.push({
          id: `issue_${client.id}_contact`,
          type: 'missing_contact',
          entity: 'client',
          entityId: client.id,
          entityName: 'Unknown Client',
          severity: 'high',
          message: 'Missing client contact information',
          details: `No email or name provided`,
          suggestedAction: 'Add client email or name',
          autoFixable: false,
          fieldName: 'requestorEmail',
          currentValue: null,
          expectedValue: 'Valid email address or full name'
        });
      }
    }

    logger.debug('Client validation completed', { issues: issues.length });
    return issues;
  }

  /**
   * Validate carers
   */
  async validateCarers(tenantId: string): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];

    const carers = await this.prisma.carer.findMany({
      where: { tenantId, isActive: true },
      select: {
        id: true,
        firstName: true,
        lastName: true,
        email: true,
        postcode: true,
        latitude: true,
        longitude: true,
        skills: true,
        availabilityHours: true,
        maxTravelDistance: true,
        phone: true,
        address: true
      }
    });

    logger.debug('Validating carers', { count: carers.length });

    for (const carer of carers) {
      const carerName = `${carer.firstName} ${carer.lastName}`;

      // Check missing postcode
      if (!carer.postcode || carer.postcode.trim().length === 0) {
        issues.push({
          id: `issue_${carer.id}_postcode`,
          type: 'missing_postcode',
          entity: 'carer',
          entityId: carer.id,
          entityName: carerName,
          severity: 'high',
          message: 'Missing postcode',
          details: `Carer "${carerName}" has no postcode - cannot calculate travel`,
          suggestedAction: 'Geocode from address or add manually',
          autoFixable: !!carer.address,
          fieldName: 'postcode',
          currentValue: null,
          expectedValue: 'Valid UK postcode'
        });
      }

      // Check missing coordinates
      if (!carer.latitude || !carer.longitude) {
        issues.push({
          id: `issue_${carer.id}_coordinates`,
          type: 'missing_coordinates',
          entity: 'carer',
          entityId: carer.id,
          entityName: carerName,
          severity: 'critical',
          message: 'Missing location coordinates',
          details: `Cannot assign visits or calculate travel without lat/lon`,
          suggestedAction: 'Geocode address to get coordinates',
          autoFixable: !!(carer.address || carer.postcode),
          fieldName: 'latitude,longitude',
          currentValue: null,
          expectedValue: 'Valid latitude and longitude'
        });
      }

      // Check missing skills
      if (!carer.skills || carer.skills.length === 0) {
        issues.push({
          id: `issue_${carer.id}_skills`,
          type: 'missing_skills',
          entity: 'carer',
          entityId: carer.id,
          entityName: carerName,
          severity: 'high',
          message: 'No skills defined',
          details: `Carer "${carerName}" has no skills - cannot auto-assign`,
          suggestedAction: 'Add skills (e.g., Personal Care, Medication, Mobility)',
          autoFixable: false,
          fieldName: 'skills',
          currentValue: [],
          expectedValue: 'Array of skills: ["Personal Care", "Medication"]'
        });
      }

      // Check missing availability
      if (!carer.availabilityHours || Object.keys(carer.availabilityHours as any).length === 0) {
        issues.push({
          id: `issue_${carer.id}_availability`,
          type: 'availability_conflict',
          entity: 'carer',
          entityId: carer.id,
          entityName: carerName,
          severity: 'medium',
          message: 'No availability schedule defined',
          details: `Cannot check if carer is available for visits`,
          suggestedAction: 'Add weekly availability schedule',
          autoFixable: false,
          fieldName: 'availabilityHours',
          currentValue: null,
          expectedValue: 'JSON with day/time availability'
        });
      }

      // Check missing contact
      if (!carer.phone && !carer.email) {
        issues.push({
          id: `issue_${carer.id}_contact`,
          type: 'missing_contact',
          entity: 'carer',
          entityId: carer.id,
          entityName: carerName,
          severity: 'high',
          message: 'Missing contact information',
          details: `No phone or email - cannot notify about assignments`,
          suggestedAction: 'Add phone number or email address',
          autoFixable: false,
          fieldName: 'phone,email',
          currentValue: null,
          expectedValue: 'Phone number or email address'
        });
      }

      // Check unrealistic travel distance
      if (carer.maxTravelDistance && carer.maxTravelDistance > 50000) {
        issues.push({
          id: `issue_${carer.id}_travel`,
          type: 'skill_mismatch',
          entity: 'carer',
          entityId: carer.id,
          entityName: carerName,
          severity: 'low',
          message: 'Unrealistic max travel distance',
          details: `Max travel distance set to ${Math.round(carer.maxTravelDistance / 1000)}km`,
          suggestedAction: 'Review and adjust to realistic distance (typically 5-20km)',
          autoFixable: false,
          fieldName: 'maxTravelDistance',
          currentValue: carer.maxTravelDistance,
          expectedValue: '5000-20000 meters (5-20km)'
        });
      }
    }

    logger.debug('Carer validation completed', { issues: issues.length });
    return issues;
  }

  /**
   * Validate visits (scheduled requests)
   */
  async validateVisits(tenantId: string): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];

    const visits = await this.prisma.externalRequest.findMany({
      where: {
        tenantId,
        status: 'APPROVED',
        scheduledStartTime: { not: null }
      },
      select: {
        id: true,
        requestorName: true,
        scheduledStartTime: true,
        scheduledEndTime: true,
        estimatedDuration: true,
        requirements: true,
        latitude: true,
        longitude: true
      }
    });

    logger.debug('Validating visits', { count: visits.length });

    for (const visit of visits) {
      // Check missing time window
      if (!visit.scheduledStartTime) {
        issues.push({
          id: `issue_${visit.id}_notime`,
          type: 'invalid_time_window',
          entity: 'visit',
          entityId: visit.id,
          entityName: visit.requestorName || 'Unknown',
          severity: 'critical',
          message: 'No scheduled time',
          details: `Visit has no scheduled start time`,
          suggestedAction: 'Set scheduled start time',
          autoFixable: false,
          fieldName: 'scheduledStartTime',
          currentValue: null,
          expectedValue: 'DateTime in future'
        });
      }

      // Check visit in the past
      if (visit.scheduledStartTime && visit.scheduledStartTime < new Date()) {
        const hoursPast = Math.round((Date.now() - visit.scheduledStartTime.getTime()) / (1000 * 60 * 60));
        if (hoursPast > 24) {
          issues.push({
            id: `issue_${visit.id}_past`,
            type: 'invalid_time_window',
            entity: 'visit',
            entityId: visit.id,
            entityName: visit.requestorName || 'Unknown',
            severity: 'high',
            message: 'Visit scheduled in the past',
            details: `Visit was scheduled ${hoursPast} hours ago`,
            suggestedAction: 'Reschedule or mark as completed/cancelled',
            autoFixable: false,
            fieldName: 'scheduledStartTime',
            currentValue: visit.scheduledStartTime,
            expectedValue: 'DateTime in future'
          });
        }
      }

      // Check missing location
      if (!visit.latitude || !visit.longitude) {
        issues.push({
          id: `issue_${visit.id}_location`,
          type: 'missing_coordinates',
          entity: 'visit',
          entityId: visit.id,
          entityName: visit.requestorName || 'Unknown',
          severity: 'critical',
          message: 'Visit has no location',
          details: `Cannot include in roster without coordinates`,
          suggestedAction: 'Geocode visit address',
          autoFixable: false,
          fieldName: 'latitude,longitude',
          currentValue: null,
          expectedValue: 'Valid coordinates'
        });
      }
    }

    logger.debug('Visit validation completed', { issues: issues.length });
    return issues;
  }

  /**
   * Validate constraints
   */
  async validateConstraints(tenantId: string): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];

    const constraints = await this.prisma.rosteringConstraints.findFirst({
      where: { tenantId, isActive: true }
    });

    if (!constraints) {
      issues.push({
        id: `issue_constraints_missing`,
        type: 'missing_requirements',
        entity: 'constraint',
        entityId: 'constraints',
        entityName: 'Rostering Rules',
        severity: 'critical',
        message: 'No active rostering constraints',
        details: `Tenant has no rostering rules configured`,
        suggestedAction: 'Create default rostering constraints',
        autoFixable: true,
        fieldName: 'constraints',
        currentValue: null,
        expectedValue: 'Active constraint set'
      });
      return issues;
    }

    // Validate WTD hours
    if (constraints.wtdMaxHoursPerWeek > 48 || constraints.wtdMaxHoursPerWeek < 20) {
      issues.push({
        id: `issue_constraints_wtd`,
        type: 'invalid_time_window',
        entity: 'constraint',
        entityId: constraints.id,
        entityName: 'WTD Max Hours',
        severity: 'medium',
        message: 'WTD max hours outside typical range',
        details: `Set to ${constraints.wtdMaxHoursPerWeek} hours (typical: 20-48)`,
        suggestedAction: 'Review WTD compliance (UK law: max 48 hours)',
        autoFixable: false,
        fieldName: 'wtdMaxHoursPerWeek',
        currentValue: constraints.wtdMaxHoursPerWeek,
        expectedValue: '20-48 hours'
      });
    }

    // Validate rest period
    if (constraints.restPeriodHours < 11) {
      issues.push({
        id: `issue_constraints_rest`,
        type: 'invalid_time_window',
        entity: 'constraint',
        entityId: constraints.id,
        entityName: 'Rest Period',
        severity: 'high',
        message: 'Rest period below legal minimum',
        details: `Set to ${constraints.restPeriodHours} hours (UK law: min 11 hours)`,
        suggestedAction: 'Increase to at least 11 hours',
        autoFixable: true,
        fieldName: 'restPeriodHours',
        currentValue: constraints.restPeriodHours,
        expectedValue: '11 hours minimum'
      });
    }

    // Validate travel max
    if (constraints.travelMaxMinutes > 60) {
      issues.push({
        id: `issue_constraints_travel`,
        type: 'skill_mismatch',
        entity: 'constraint',
        entityId: constraints.id,
        entityName: 'Max Travel Time',
        severity: 'low',
        message: 'Max travel time very high',
        details: `Set to ${constraints.travelMaxMinutes} minutes (typical: 15-30)`,
        suggestedAction: 'Consider reducing for better carer experience',
        autoFixable: false,
        fieldName: 'travelMaxMinutes',
        currentValue: constraints.travelMaxMinutes,
        expectedValue: '15-30 minutes'
      });
    }

    logger.debug('Constraint validation completed', { issues: issues.length });
    return issues;
  }

  /**
   * Apply automatic fix for an issue
   */
  async applyFix(tenantId: string, fixAction: FixAction): Promise<FixResult> {
    try {
      logger.info('Applying fix', { tenantId, fixAction });

      switch (fixAction.action) {
        case 'geocode':
          return await this.fixGeocode(tenantId, fixAction);
        
        case 'add_skill':
          return await this.fixAddSkill(tenantId, fixAction);
        
        case 'extend_credential':
          return await this.fixExtendCredential(tenantId, fixAction);
        
        case 'update_field':
          return await this.fixUpdateField(tenantId, fixAction);
        
        default:
          return {
            success: false,
            issueId: fixAction.issueId,
            action: fixAction.action,
            message: `Unknown fix action: ${fixAction.action}`,
            error: 'Invalid action'
          };
      }

    } catch (error: any) {
      logger.error('Failed to apply fix:', error);
      return {
        success: false,
        issueId: fixAction.issueId,
        action: fixAction.action,
        message: 'Fix failed',
        error: error.message
      };
    }
  }

  /**
   * Fix: Geocode address
    */
   private async fixGeocode(tenantId: string, fixAction: FixAction): Promise<FixResult> {
     const { entityId, entityType } = fixAction.params;

     if (entityType === 'client') {
       const client = await this.prisma.externalRequest.findFirst({
         where: { id: entityId, tenantId }
       });

       if (!client) {
         return {
           success: false,
           issueId: fixAction.issueId,
           action: 'geocode',
           message: 'Client not found',
           error: 'Entity not found'
         };
       }

       const addressToGeocode = client.address || client.postcode;
       if (!addressToGeocode) {
         return {
           success: false,
           issueId: fixAction.issueId,
           action: 'geocode',
           message: 'No address or postcode to geocode',
           error: 'Missing data'
         };
       }

       const geocoded = await this.geocodingService.geocodeAddress(addressToGeocode);

       if (!geocoded) {
         return {
           success: false,
           issueId: fixAction.issueId,
           action: 'geocode',
           message: 'Geocoding failed',
           error: 'Geocoding service returned null'
         };
       }

       const updated = await this.prisma.externalRequest.update({
         where: { id: entityId },
         data: {
           latitude: geocoded.latitude,
           longitude: geocoded.longitude,
           postcode: geocoded.address || client.postcode
         }
       });

       return {
         success: true,
         issueId: fixAction.issueId,
         action: 'geocode',
         message: `Geocoded: ${geocoded.latitude}, ${geocoded.longitude}`,
         updatedEntity: updated
       };

     } else if (entityType === 'carer') {
       const carer = await this.prisma.carer.findFirst({
         where: { id: entityId, tenantId }
       });

       if (!carer) {
         return {
           success: false,
           issueId: fixAction.issueId,
           action: 'geocode',
           message: 'Carer not found',
           error: 'Entity not found'
         };
       }

       const addressToGeocode = carer.address || carer.postcode;
       if (!addressToGeocode) {
         return {
           success: false,
           issueId: fixAction.issueId,
           action: 'geocode',
           message: 'No address or postcode to geocode',
           error: 'Missing data'
         };
       }

       const geocoded = await this.geocodingService.geocodeAddress(addressToGeocode);

       if (!geocoded) {
         return {
           success: false,
           issueId: fixAction.issueId,
           action: 'geocode',
           message: 'Geocoding failed',
           error: 'Geocoding service returned null'
         };
       }

       const updated = await this.prisma.carer.update({
         where: { id: entityId },
         data: {
           latitude: geocoded.latitude,
           longitude: geocoded.longitude,
           postcode: geocoded.address || carer.postcode
         }
       });

       return {
         success: true,
         issueId: fixAction.issueId,
         action: 'geocode',
         message: `Geocoded: ${geocoded.latitude}, ${geocoded.longitude}`,
         updatedEntity: updated
       };
     }

     return {
       success: false,
       issueId: fixAction.issueId,
       action: 'geocode',
       message: 'Unknown entity type',
       error: 'Invalid entity type'
     };
   }

  /**
   * Fix: Add skill to carer
   */
  private async fixAddSkill(tenantId: string, fixAction: FixAction): Promise<FixResult> {
    const { entityId, skill } = fixAction.params;

    const carer = await this.prisma.carer.findFirst({
      where: { id: entityId, tenantId }
    });

    if (!carer) {
      return {
        success: false,
        issueId: fixAction.issueId,
        action: 'add_skill',
        message: 'Carer not found',
        error: 'Entity not found'
      };
    }

    const updatedSkills = [...(carer.skills || []), skill];

    const updated = await this.prisma.carer.update({
      where: { id: entityId },
      data: { skills: updatedSkills }
    });

    return {
      success: true,
      issueId: fixAction.issueId,
      action: 'add_skill',
      message: `Added skill: ${skill}`,
      updatedEntity: updated
    };
  }

  /**
   * Fix: Extend credential expiry
   */
  private async fixExtendCredential(tenantId: string, fixAction: FixAction): Promise<FixResult> {
    // Placeholder - implement based on your credential model
    return {
      success: false,
      issueId: fixAction.issueId,
      action: 'extend_credential',
      message: 'Not implemented',
      error: 'Feature not implemented'
    };
  }

  /**
   * Fix: Update a field
   */
  private async fixUpdateField(tenantId: string, fixAction: FixAction): Promise<FixResult> {
    const { entityType, entityId, fieldName, fieldValue } = fixAction.params;

    if (entityType === 'client') {
      const updated = await this.prisma.externalRequest.update({
        where: { id: entityId },
        data: { [fieldName]: fieldValue }
      });

      return {
        success: true,
        issueId: fixAction.issueId,
        action: 'update_field',
        message: `Updated ${fieldName} to ${fieldValue}`,
        updatedEntity: updated
      };

    } else if (entityType === 'carer') {
      const updated = await this.prisma.carer.update({
        where: { id: entityId },
        data: { [fieldName]: fieldValue }
      });

      return {
        success: true,
        issueId: fixAction.issueId,
        action: 'update_field',
        message: `Updated ${fieldName} to ${fieldValue}`,
        updatedEntity: updated
      };
    }

    return {
      success: false,
      issueId: fixAction.issueId,
      action: 'update_field',
      message: 'Unknown entity type',
      error: 'Invalid entity type'
    };
  }

  /**
   * Batch apply multiple fixes
   */
  async applyBatchFixes(tenantId: string, fixes: FixAction[]): Promise<FixResult[]> {
    logger.info('Applying batch fixes', { tenantId, count: fixes.length });

    const results = await Promise.all(
      fixes.map(fix => this.applyFix(tenantId, fix))
    );

    const successCount = results.filter(r => r.success).length;
    logger.info('Batch fixes completed', {
      total: fixes.length,
      successful: successCount,
      failed: fixes.length - successCount
    });

    return results;
  }

  // ========== HELPER METHODS ==========

  private async getTotalItemCount(tenantId: string): Promise<number> {
    const [clientCount, carerCount, visitCount] = await Promise.all([
      this.prisma.externalRequest.count({
        where: { tenantId, status: { in: ['PENDING', 'APPROVED'] } }
      }),
      this.prisma.carer.count({ where: { tenantId, isActive: true } }),
      this.prisma.externalRequest.count({
        where: { tenantId, status: 'APPROVED', scheduledStartTime: { not: null } }
      })
    ]);

    return clientCount + carerCount + visitCount;
  }

  private generateSummary(issues: ValidationIssue[]): ValidationSummary {
const summary: ValidationSummary = {
      criticalIssues: issues.filter(i => i.severity === 'critical').length,
      highIssues: issues.filter(i => i.severity === 'high').length,
      mediumIssues: issues.filter(i => i.severity === 'medium').length,
      lowIssues: issues.filter(i => i.severity === 'low').length,
      autoFixableIssues: issues.filter(i => i.autoFixable).length,
      issuesByType: {},
      issuesByEntity: {}
    };

    // Count by type
    issues.forEach(issue => {
      summary.issuesByType[issue.type] = (summary.issuesByType[issue.type] || 0) + 1;
      summary.issuesByEntity[issue.entity] = (summary.issuesByEntity[issue.entity] || 0) + 1;
    });

    return summary;
  }

  /**
   * Get validation statistics for dashboard
   */
  async getValidationStats(tenantId: string): Promise<{
    schedulability: number;
    lastValidated: Date | null;
    criticalIssuesCount: number;
    autoFixableCount: number;
    topIssues: Array<{ type: string; count: number }>;
  }> {
    try {
      // Run quick validation
      const result = await this.validateData(tenantId);

      // Get top 5 issue types
      const topIssues = Object.entries(result.summary.issuesByType)
        .sort((a: [string, number], b: [string, number]) => b[1] - a[1])
        .slice(0, 5)
        .map(([type, count]: [string, number]) => ({ type, count }));

      return {
        schedulability: result.schedulability,
        lastValidated: new Date(),
        criticalIssuesCount: result.summary.criticalIssues,
        autoFixableCount: result.summary.autoFixableIssues,
        topIssues
      };

    } catch (error) {
      logger.error('Failed to get validation stats:', error);
      throw error;
    }
  }

  /**
   * Get issues by entity type
   */
  async getIssuesByEntity(tenantId: string, entityType: 'client' | 'carer' | 'visit' | 'constraint'): Promise<ValidationIssue[]> {
    const result = await this.validateData(tenantId);
    return result.issues.filter((issue: ValidationIssue) => issue.entity === entityType);
  }

  /**
   * Get issues by severity
   */
  async getIssuesBySeverity(tenantId: string, severity: 'critical' | 'high' | 'medium' | 'low'): Promise<ValidationIssue[]> {
    const result = await this.validateData(tenantId);
    return result.issues.filter((issue: ValidationIssue) => issue.severity === severity);
  }

  /**
   * Get auto-fixable issues
   */
  async getAutoFixableIssues(tenantId: string): Promise<ValidationIssue[]> {
    const result = await this.validateData(tenantId);
    return result.issues.filter((issue: ValidationIssue) => issue.autoFixable);
  }

  /**
   * Validate specific entity
   */
  async validateEntity(tenantId: string, entityType: 'client' | 'carer' | 'visit', entityId: string): Promise<ValidationIssue[]> {
    let allIssues: ValidationIssue[] = [];

    switch (entityType) {
      case 'client':
        allIssues = await this.validateClients(tenantId);
        break;
      case 'carer':
        allIssues = await this.validateCarers(tenantId);
        break;
      case 'visit':
        allIssues = await this.validateVisits(tenantId);
        break;
    }

    return allIssues.filter(issue => issue.entityId === entityId);
  }

  /**
   * Check if entity is schedulable
   */
  async isEntitySchedulable(tenantId: string, entityType: 'client' | 'carer' | 'visit', entityId: string): Promise<{
    schedulable: boolean;
    blockingIssues: ValidationIssue[];
    warningIssues: ValidationIssue[];
  }> {
    const issues = await this.validateEntity(tenantId, entityType, entityId);
    
    const blockingIssues = issues.filter(i => i.severity === 'critical' || i.severity === 'high');
    const warningIssues = issues.filter(i => i.severity === 'medium' || i.severity === 'low');

    return {
      schedulable: blockingIssues.length === 0,
      blockingIssues,
      warningIssues
    };
  }

  /**
   * Get validation report for export
   */
  async getValidationReport(tenantId: string): Promise<{
    generatedAt: Date;
    tenantId: string;
    summary: ValidationSummary;
    issues: ValidationIssue[];
    recommendations: string[];
  }> {
    const result = await this.validateData(tenantId);
    const recommendations = this.generateRecommendations(result);

    return {
      generatedAt: new Date(),
      tenantId,
      summary: result.summary,
      issues: result.issues,
      recommendations
    };
  }

  /**
   * Generate recommendations based on issues
   */
  private generateRecommendations(result: ValidationResult): string[] {
    const recommendations: string[] = [];

    if (result.summary.criticalIssues > 0) {
      recommendations.push(`🔴 Fix ${result.summary.criticalIssues} critical issues immediately - these prevent rostering`);
    }

    if (result.summary.autoFixableIssues > 5) {
      recommendations.push(`✅ ${result.summary.autoFixableIssues} issues can be auto-fixed - click "Fix All" to resolve`);
    }

    const missingCoordinates = result.issues.filter(i => i.type === 'missing_coordinates').length;
    if (missingCoordinates > 0) {
      recommendations.push(`📍 ${missingCoordinates} entities need geocoding - this is required for clustering`);
    }

    const missingSkills = result.issues.filter(i => i.type === 'missing_skills').length;
    if (missingSkills > 0) {
      recommendations.push(`🎓 ${missingSkills} carers have no skills defined - they cannot be auto-assigned`);
    }

    const invalidTimeWindows = result.issues.filter(i => i.type === 'invalid_time_window').length;
    if (invalidTimeWindows > 0) {
      recommendations.push(`⏰ ${invalidTimeWindows} visits have invalid time windows - review and correct`);
    }

    if (result.schedulability < 70) {
      recommendations.push(`⚠️ Schedulability is ${result.schedulability}% - aim for 90%+ for effective rostering`);
    }

    if (result.schedulability >= 90) {
      recommendations.push(`✨ Excellent! Schedulability at ${result.schedulability}% - ready for optimization`);
    }

    // Add tenant-specific recommendations
    const issuesByType = Object.entries(result.summary.issuesByType)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);

    if (issuesByType.length > 0) {
      const topIssue = issuesByType[0];
      recommendations.push(`📊 Most common issue: ${topIssue[0]} (${topIssue[1]} occurrences) - consider bulk fixes`);
    }

    return recommendations;
  }

  /**
   * Validate data import before saving
   */
  async validateImport(tenantId: string, importData: {
    clients?: any[];
    carers?: any[];
  }): Promise<{
    valid: boolean;
    validRecords: number;
    invalidRecords: number;
    issues: Array<{
      row: number;
      field: string;
      message: string;
      severity: string;
    }>;
  }> {
    const issues: Array<{ row: number; field: string; message: string; severity: string }> = [];
    let validRecords = 0;
    let invalidRecords = 0;

    // Validate clients
    if (importData.clients) {
      importData.clients.forEach((client, index) => {
        let hasErrors = false;

        if (!client.address || client.address.trim().length < 10) {
          issues.push({
            row: index + 1,
            field: 'address',
            message: 'Address is missing or too short',
            severity: 'high'
          });
          hasErrors = true;
        }

        if (!client.postcode) {
          issues.push({
            row: index + 1,
            field: 'postcode',
            message: 'Postcode is required for clustering',
            severity: 'high'
          });
          hasErrors = true;
        }

        if (!client.requestorEmail && !client.requestorName) {
          issues.push({
            row: index + 1,
            field: 'contact',
            message: 'Email or name is required',
            severity: 'critical'
          });
          hasErrors = true;
        }

        if (client.scheduledStartTime) {
          const scheduledTime = new Date(client.scheduledStartTime);
          if (isNaN(scheduledTime.getTime())) {
            issues.push({
              row: index + 1,
              field: 'scheduledStartTime',
              message: 'Invalid date format',
              severity: 'high'
            });
            hasErrors = true;
          }
        }

        if (hasErrors) {
          invalidRecords++;
        } else {
          validRecords++;
        }
      });
    }

    // Validate carers
    if (importData.carers) {
      importData.carers.forEach((carer, index) => {
        let hasErrors = false;

        if (!carer.firstName || !carer.lastName) {
          issues.push({
            row: index + 1,
            field: 'name',
            message: 'First name and last name are required',
            severity: 'critical'
          });
          hasErrors = true;
        }

        if (!carer.email && !carer.phone) {
          issues.push({
            row: index + 1,
            field: 'contact',
            message: 'Email or phone is required',
            severity: 'high'
          });
          hasErrors = true;
        }

        if (!carer.postcode) {
          issues.push({
            row: index + 1,
            field: 'postcode',
            message: 'Postcode is required for travel calculations',
            severity: 'high'
          });
          hasErrors = true;
        }

        if (!carer.skills || carer.skills.length === 0) {
          issues.push({
            row: index + 1,
            field: 'skills',
            message: 'At least one skill is required for auto-assignment',
            severity: 'medium'
          });
          hasErrors = true;
        }

        if (hasErrors) {
          invalidRecords++;
        } else {
          validRecords++;
        }
      });
    }

    return {
      valid: invalidRecords === 0,
      validRecords,
      invalidRecords,
      issues
    };
  }

  /**
   * Check data quality score (0-100)
   */
  async getDataQualityScore(tenantId: string): Promise<{
    overallScore: number;
    categoryScores: {
      completeness: number;
      accuracy: number;
      consistency: number;
      timeliness: number;
    };
    breakdown: string[];
  }> {
    const result = await this.validateData(tenantId);

    // Completeness: How much required data is present
    const completenessScore = result.schedulability;

    // Accuracy: How many geocoding/validation errors
    const geocodingIssues = result.issues.filter((i: ValidationIssue) =>
      i.type === 'geocoding_failed' || i.type === 'missing_coordinates'
    ).length;
    const accuracyScore = Math.max(0, 100 - (geocodingIssues * 5));

    // Consistency: How many data conflicts
    const conflictIssues = result.issues.filter((i: ValidationIssue) =>
      i.type === 'duplicate_entry' || i.type === 'availability_conflict'
    ).length;
    const consistencyScore = Math.max(0, 100 - (conflictIssues * 10));

    // Timeliness: How many outdated records
    const outdatedIssues = result.issues.filter((i: ValidationIssue) =>
      i.type === 'credential_expiry' || i.type === 'invalid_time_window'
    ).length;
    const timelinessScore = Math.max(0, 100 - (outdatedIssues * 8));

    const overallScore = Math.round(
      (completenessScore * 0.4) +
      (accuracyScore * 0.3) +
      (consistencyScore * 0.2) +
      (timelinessScore * 0.1)
    );

    const breakdown: string[] = [];
    
    if (completenessScore < 70) {
      breakdown.push(`Completeness: ${completenessScore}% - Many required fields missing`);
    }
    
    if (accuracyScore < 70) {
      breakdown.push(`Accuracy: ${accuracyScore}% - Geocoding or validation issues`);
    }
    
    if (consistencyScore < 70) {
      breakdown.push(`Consistency: ${consistencyScore}% - Data conflicts detected`);
    }
    
    if (timelinessScore < 70) {
      breakdown.push(`Timeliness: ${timelinessScore}% - Outdated records found`);
    }

    return {
      overallScore,
      categoryScores: {
        completeness: completenessScore,
        accuracy: accuracyScore,
        consistency: consistencyScore,
        timeliness: timelinessScore
      },
      breakdown
    };
  }

  /**
    * Geocode a client
    */
   async geocodeClient(clientId: string): Promise<boolean> {
     try {
       const client = await this.prisma.externalRequest.findFirst({
         where: { id: clientId }
       });

       if (!client) return false;

       const addressToGeocode = client.address || client.postcode;
       if (!addressToGeocode) return false;

       const geocoded = await this.geocodingService.geocodeAddress(addressToGeocode);

       if (!geocoded) return false;

       await this.prisma.externalRequest.update({
         where: { id: clientId },
         data: {
           latitude: geocoded.latitude,
           longitude: geocoded.longitude,
           postcode: geocoded.address || client.postcode
         }
       });

       return true;
     } catch (error) {
       logger.error('Failed to geocode client:', error);
       return false;
     }
   }

   /**
    * Add skill to carer
    */
   async addCarerSkill(carerId: string, skill: string): Promise<boolean> {
     try {
       const carer = await this.prisma.carer.findFirst({
         where: { id: carerId }
       });

       if (!carer) return false;

       const updatedSkills = [...(carer.skills || []), skill];

       await this.prisma.carer.update({
         where: { id: carerId },
         data: { skills: updatedSkills }
       });

       return true;
     } catch (error) {
       logger.error('Failed to add carer skill:', error);
       return false;
     }
   }

   /**
    * Check capacity vs demand
    */
   async checkCapacityVsDemand(tenantId: string, dateRange: { start: Date; end: Date }): Promise<{
     sufficient: boolean;
     carerHoursAvailable: number;
     visitHoursRequired: number;
     utilization: number;
     gap: number;
     recommendations: string[];
   }> {
    // Get active carers
    const carers = await this.prisma.carer.findMany({
      where: { tenantId, isActive: true },
      select: { id: true, availabilityHours: true }
    });

    // Get approved visits
    const visits = await this.prisma.externalRequest.findMany({
      where: {
        tenantId,
        status: 'APPROVED',
        scheduledStartTime: {
          gte: dateRange.start,
          lte: dateRange.end
        }
      },
      select: { estimatedDuration: true }
    });

    // Calculate available hours (simplified - assumes 40 hours/week per carer)
    const daysInRange = Math.ceil((dateRange.end.getTime() - dateRange.start.getTime()) / (1000 * 60 * 60 * 24));
    const weeksInRange = daysInRange / 7;
    const carerHoursAvailable = carers.length * 40 * weeksInRange;

    // Calculate required hours
    const visitHoursRequired = visits.reduce((sum, v) => sum + (v.estimatedDuration || 60) / 60, 0);

    const utilization = carerHoursAvailable > 0 ? (visitHoursRequired / carerHoursAvailable) * 100 : 0;
    const gap = carerHoursAvailable - visitHoursRequired;
    const sufficient = gap >= 0;

    const recommendations: string[] = [];

    if (!sufficient) {
      recommendations.push(`⚠️ Insufficient capacity: ${Math.abs(gap).toFixed(1)} hours short`);
      recommendations.push(`💡 Consider recruiting ${Math.ceil(Math.abs(gap) / 40)} additional carers`);
    } else if (utilization > 90) {
      recommendations.push(`⚠️ High utilization: ${utilization.toFixed(1)}% - risk of overload`);
      recommendations.push(`💡 Consider adding buffer capacity for emergencies`);
    } else if (utilization < 50) {
      recommendations.push(`📊 Low utilization: ${utilization.toFixed(1)}% - capacity available`);
      recommendations.push(`💡 Opportunity to take on more clients`);
    } else {
      recommendations.push(`✅ Healthy utilization: ${utilization.toFixed(1)}%`);
    }

    return {
      sufficient,
      carerHoursAvailable: Math.round(carerHoursAvailable),
      visitHoursRequired: Math.round(visitHoursRequired),
      utilization: Math.round(utilization),
      gap: Math.round(gap),
      recommendations
    };
  }
}

export default DataValidationService;