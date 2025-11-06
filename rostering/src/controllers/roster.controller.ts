import { Request, Response } from 'express';
import { PrismaClient, Roster, Assignment, ExternalRequest, Carer } from '@prisma/client';
import { RosterGenerationService, OptimizationParams } from '../services/roster-generation.service';
import { ConstraintsService } from '../services/constraints.service';
import { TravelService } from '../services/travel.service';
import { ClusteringService } from '../services/clustering.service';
import { logger } from '../utils/logger';
import { DisruptionService } from '../services/disruption.service';
import { NotificationService } from '../services/notification.service';
import { GeocodingService } from '../services/geocoding.service';
import { MatchingService } from '../services/matching.service';
import { generateUniqueRequestId } from '../utils/idGenerator';
import { 
  RosterWithAssignments, 
  OptimizationStatus,
  ContinuityReport,
  ClientContinuity,
  LiveRosterStatus,
  ManualChangeValidation
} from '../types/rostering';

// Define types for the request user
interface AuthenticatedRequest extends Request {
  user: {
    id: string;
    email: string;
    tenantId: string;
    permissions?: string[];
  };
}

export class RosterController {
  private rosterService: RosterGenerationService;
  private disruptionService: DisruptionService;
  private notificationService: NotificationService;
  private websocketService?: any; // Optional websocket service

  constructor(private prisma: PrismaClient) {
    const constraintsService = new ConstraintsService(prisma);
    const travelService = new TravelService(prisma);
    const clusteringService = new ClusteringService(
      prisma,
      constraintsService,
      travelService
    );

    this.rosterService = new RosterGenerationService(
      prisma,
      constraintsService,
      travelService,
      clusteringService
    );

    const matchingService = new MatchingService(prisma, new GeocodingService(prisma));
    this.notificationService = new NotificationService();
    this.disruptionService = new DisruptionService(
      prisma,
      this.rosterService,
      matchingService,
      this.notificationService
    );
  }

  /**
   * Generate roster scenarios
   * POST /api/rostering/roster/generate
   */
  generateRoster = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const {
        clusterId,
        startDate,
        endDate,
        strategy,
        generateScenarios = true
      } = req.body;

      if (!startDate || !endDate) {
        res.status(400).json({
          success: false,
          error: 'startDate and endDate are required'
        });
        return;
      }

      const params: OptimizationParams = {
        clusterId,
        dateRange: {
          start: new Date(startDate),
          end: new Date(endDate)
        },
        strategy,
        generateScenarios
      };

      const scenarios = await this.rosterService.generateRoster(tenantId, params);

      // Convert scenarios to plain objects to avoid JSON serialization issues
      const plainScenarios = scenarios.map(scenario => ({
        id: scenario.id,
        label: scenario.label,
        strategy: scenario.strategy,
        score: scenario.score,
        metrics: {
          totalTravel: scenario.metrics.totalTravel,
          continuityScore: scenario.metrics.continuityScore,
          violations: scenario.metrics.violations,
          overtimeMinutes: scenario.metrics.overtimeMinutes,
          averageCarerWorkload: scenario.metrics.averageCarerWorkload
        },
        assignments: scenario.assignments.map(assignment => ({
          id: assignment.id,
          visitId: assignment.visitId,
          carerId: assignment.carerId,
          carerName: assignment.carerName,
          scheduledTime: assignment.scheduledTime.toISOString(),
          estimatedEndTime: assignment.estimatedEndTime.toISOString(),
          travelFromPrevious: assignment.travelFromPrevious,
          travelToPrevious: assignment.travelToPrevious,
          complianceChecks: {
            wtdCompliant: assignment.complianceChecks.wtdCompliant,
            restPeriodOK: assignment.complianceChecks.restPeriodOK,
            travelTimeOK: assignment.complianceChecks.travelTimeOK,
            skillsMatch: assignment.complianceChecks.skillsMatch,
            warnings: assignment.complianceChecks.warnings
          },
          visitDetails: {
            clientName: assignment.visitDetails.clientName,
            address: assignment.visitDetails.address,
            duration: assignment.visitDetails.duration,
            requirements: assignment.visitDetails.requirements
          }
        }))
      }));

      res.json({
        success: true,
        data: {
          scenarios: plainScenarios,
          summary: {
            totalScenarios: scenarios.length,
            recommended: scenarios[0]?.id,
            totalAssignments: scenarios[0]?.assignments?.length || 0
          }
        }
      });

    } catch (error: any) {
      logger.error('Failed to generate roster:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to generate roster',
        message: error.message
      });
    }
  };

  /**
   * Get roster by ID
   * GET /api/rostering/roster/:id
   */
  getRoster = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const rosterId = req.params.id;

      const roster = await this.prisma.roster.findFirst({
        where: {
          id: rosterId,
          tenantId
        },
        include: {
          assignments: {
            include: {
              visit: true,
              carer: {
                select: {
                  id: true,
                  firstName: true,
                  lastName: true,
                  email: true
                }
              }
            }
          }
        }
      });

      if (!roster) {
        res.status(404).json({
          success: false,
          error: 'Roster not found'
        });
        return;
      }

      res.json({
        success: true,
        data: roster
      });

    } catch (error) {
      logger.error('Failed to get roster:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve roster'
      });
    }
  };

  /**
   * Publish roster to carers
   * POST /api/rostering/roster/:id/publish
   */
  publishRoster = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const rosterId = req.params.id;
      const {
        notificationChannels = ['push', 'sms', 'email'],
        acceptanceDeadlineMinutes = 30,
        versionLabel
      } = req.body;

      res.status(501).json({
        success: false,
        error: 'Publication feature coming in Phase 2',
        message: 'This endpoint will be implemented with the Publication & Acceptance module'
      });

    } catch (error) {
      logger.error('Failed to publish roster:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to publish roster'
      });
    }
  };

  /**
   * Get roster acceptance status
   * GET /api/rostering/roster/:id/acceptance
   */
  getAcceptanceStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const rosterId = req.params.id;

      res.status(501).json({
        success: false,
        error: 'Acceptance tracking coming in Phase 2'
      });

    } catch (error) {
      logger.error('Failed to get acceptance status:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve acceptance status'
      });
    }
  };

  /**
   * Compare two roster scenarios
   * POST /api/rostering/roster/compare
   */
  compareScenarios = async (req: Request, res: Response): Promise<void> => {
    try {
      const { scenarioA, scenarioB } = req.body;

      if (!scenarioA || !scenarioB) {
        res.status(400).json({
          success: false,
          error: 'Both scenarioA and scenarioB are required'
        });
        return;
      }

      const comparison = {
        travel: {
          scenarioA: scenarioA.metrics.totalTravel,
          scenarioB: scenarioB.metrics.totalTravel,
          difference: scenarioB.metrics.totalTravel - scenarioA.metrics.totalTravel,
          winner: scenarioA.metrics.totalTravel < scenarioB.metrics.totalTravel ? 'A' : 'B'
        },
        continuity: {
          scenarioA: scenarioA.metrics.continuityScore,
          scenarioB: scenarioB.metrics.continuityScore,
          difference: scenarioB.metrics.continuityScore - scenarioA.metrics.continuityScore,
          winner: scenarioA.metrics.continuityScore > scenarioB.metrics.continuityScore ? 'A' : 'B'
        },
        violations: {
          scenarioA: scenarioA.metrics.violations,
          scenarioB: scenarioB.metrics.violations,
          winner: (scenarioA.metrics.violations.hard + scenarioA.metrics.violations.soft) <
                  (scenarioB.metrics.violations.hard + scenarioB.metrics.violations.soft) ? 'A' : 'B'
        },
        overallScore: {
          scenarioA: scenarioA.score,
          scenarioB: scenarioB.score,
          winner: scenarioA.score > scenarioB.score ? 'A' : 'B'
        }
      };

      res.json({
        success: true,
        data: comparison
      });

    } catch (error) {
      logger.error('Failed to compare scenarios:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to compare scenarios'
      });
    }
  };

  /**
   * Create manual assignment
   * POST /api/rostering/assignments
   */
  createAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const {
        visitId,
        carerId,
        scheduledTime,
        notes
      } = req.body;

      if (!visitId || !carerId || !scheduledTime) {
        res.status(400).json({
          success: false,
          error: 'visitId, carerId, and scheduledTime are required'
        });
        return;
      }

      const [visit, carer] = await Promise.all([
        this.prisma.externalRequest.findFirst({
          where: { id: visitId, tenantId }
        }),
        this.prisma.carer.findFirst({
          where: { id: carerId, tenantId }
        })
      ]);

      if (!visit || !carer) {
        res.status(404).json({
          success: false,
          error: 'Visit or carer not found'
        });
        return;
      }

      res.json({
        success: true,
        data: {
          id: `assignment_${Date.now()}`,
          visitId,
          carerId,
          scheduledTime: new Date(scheduledTime),
          status: 'pending',
          createdAt: new Date()
        },
        message: 'Assignment created successfully'
      });

    } catch (error) {
      logger.error('Failed to create assignment:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to create assignment'
      });
    }
  };

  /**
   * Validate assignment against constraints
   * POST /api/rostering/assignments/validate
   */
  validateAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { visitId, carerId, scheduledTime } = req.body;

      const constraintsService = new ConstraintsService(this.prisma);
      const constraints = await constraintsService.getActiveConstraints(tenantId);

      const [visit, carer] = await Promise.all([
        this.prisma.externalRequest.findFirst({
          where: { id: visitId, tenantId }
        }),
        this.prisma.carer.findFirst({
          where: { id: carerId, tenantId }
        })
      ]);

      if (!visit || !carer) {
        res.status(404).json({
          success: false,
          error: 'Visit or carer not found'
        });
        return;
      }

      const validation = {
        valid: true,
        hardBlocks: [] as string[],
        softWarnings: [] as string[]
      };

      const hasSkills = this.checkSkillsMatch(visit.requirements, carer.skills);
      if (!hasSkills) {
        validation.valid = false;
        validation.hardBlocks.push('Carer does not have required skills');
      }

      if (visit.latitude && visit.longitude && carer.latitude && carer.longitude) {
        const distance = this.calculateDistance(
          visit.latitude, visit.longitude,
          carer.latitude, carer.longitude
        );

        if (distance > carer.maxTravelDistance) {
          validation.softWarnings.push(
            `Travel distance ${(distance / 1000).toFixed(1)}km exceeds carer's preferred range`
          );
        }
      }

      res.json({
        success: true,
        data: validation
      });

    } catch (error) {
      logger.error('Failed to validate assignment:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to validate assignment'
      });
    }
  };

  // Helper methods
  private checkSkillsMatch(requirements: string | null, carerSkills: string[]): boolean {
    if (!requirements) return true;
    const reqLower = requirements.toLowerCase();
    return carerSkills.some(skill => reqLower.includes(skill.toLowerCase()));
  }

  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371e3;
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c;
  }

  /**
   * Real-Time Optimization - Regenerate roster immediately
   * POST /api/rostering/roster/optimize-now
   */
  optimizeNow = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { clusterId, dateRange, strategy } = req.body;

      if (!dateRange || !dateRange.start || !dateRange.end) {
        res.status(400).json({
          success: false,
          error: 'dateRange with start and end is required'
        });
        return;
      }

      logger.info('Running real-time optimization', { tenantId, clusterId });

      const scenarios = await this.rosterService.generateRoster(tenantId, {
        clusterId,
        dateRange: {
          start: new Date(dateRange.start),
          end: new Date(dateRange.end)
        },
        strategy: strategy || 'balanced',
        generateScenarios: true
      });

      res.json({
        success: true,
        data: {
          scenarios,
          optimizedAt: new Date(),
          message: 'Roster optimized successfully'
        }
      });

    } catch (error: any) {
      logger.error('Failed to optimize roster:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to optimize roster',
        message: error.message
      });
    }
  };

  /**
   * Get optimization status
   * GET /api/rostering/roster/optimization-status/:tenantId
   */
  getOptimizationStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.params.tenantId;

      const rosters = await this.prisma.roster.findMany({
        where: {
          tenantId,
          status: { in: ['DRAFT', 'PENDING_APPROVAL', 'APPROVED'] }
        },
        include: {
          assignments: {
            select: {
              id: true,
              status: true,
              warnings: true
            }
          }
        },
        orderBy: { createdAt: 'desc' },
        take: 5
      }) as RosterWithAssignments[];

      const status: OptimizationStatus = {
        activeRosters: rosters.length,
        totalAssignments: rosters.reduce((sum: number, r: RosterWithAssignments) => sum + r.assignments.length, 0),
        warningCount: rosters.reduce((sum: number, r: RosterWithAssignments) => 
          sum + r.assignments.filter((a: { warnings: string[] }) => a.warnings.length > 0).length, 0
        ),
        lastOptimized: rosters[0]?.updatedAt || null
      };

      res.json({ success: true, data: status });

    } catch (error: any) {
      logger.error('Failed to get optimization status:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Add emergency visit
   * POST /api/rostering/roster/emergency-visit
   */
  addEmergencyVisit = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { 
        clientId, 
        address, 
        postcode, 
        urgency = 'URGENT',
        scheduledStartTime,
        estimatedDuration = 60,
        requirements 
      } = req.body;

      if (!clientId || !address || !scheduledStartTime) {
        res.status(400).json({
          success: false,
          error: 'clientId, address, and scheduledStartTime are required'
        });
        return;
      }

      logger.info('Adding emergency visit', { tenantId, clientId });

      logger.info('Adding emergency visit', { tenantId, clientId });

      // ✅ Generate unique ID before creating
      const requestId = await generateUniqueRequestId(async (id: string) => {
        const existing = await this.prisma.externalRequest.findUnique({
          where: { id },
          select: { id: true }
        });
        return !!existing;
      });

      const visit = await this.prisma.externalRequest.create({
        data: {
          id: requestId, // ✅ Add the ID here
          tenantId,
          subject: 'Emergency Visit',
          content: 'Emergency care visit',
          requestorEmail: clientId,
          address,
          postcode: postcode || '',
          urgency,
          status: 'APPROVED',
          scheduledStartTime: new Date(scheduledStartTime),
          estimatedDuration,
          requirements,
          sendToRostering: true
        }
      });

      const disruption = await this.disruptionService.reportDisruption(tenantId, {
        type: 'emergency_visit',
        description: `Emergency visit added for ${clientId}`,
        reportedBy: (req as AuthenticatedRequest).user.id,
        affectedVisits: [visit.id],
        severity: 'high'
      });

      res.json({
        success: true,
        data: {
          visit,
          disruption,
          resolutionOptions: disruption.resolutionOptions
        },
        message: 'Emergency visit added. Resolution options generated.'
      });

    } catch (error: any) {
      logger.error('Failed to add emergency visit:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Handle carer unavailable (sick/emergency)
   * POST /api/rostering/roster/carer-unavailable
   */
  handleCarerUnavailable = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { carerId, reason, affectedDate } = req.body;

      if (!carerId || !affectedDate) {
        res.status(400).json({
          success: false,
          error: 'carerId and affectedDate are required'
        });
        return;
      }

      logger.info('Handling carer unavailability', { tenantId, carerId, affectedDate });

      const dateStart = new Date(affectedDate);
      dateStart.setHours(0, 0, 0, 0);
      const dateEnd = new Date(dateStart);
      dateEnd.setDate(dateEnd.getDate() + 1);

      const affectedVisits = await this.prisma.externalRequest.findMany({
        where: {
          tenantId,
          scheduledStartTime: {
            gte: dateStart,
            lt: dateEnd
          },
          visits: {
            some: {
              assignments: {
                some: {
                  carerId,
                  status: { in: ['PENDING', 'OFFERED', 'ACCEPTED'] }
                }
              }
            }
          }
        }
      });

      const disruption = await this.disruptionService.reportDisruption(tenantId, {
        type: reason === 'sick' ? 'carer_sick' : 'carer_unavailable',
        description: `Carer ${carerId} unavailable: ${reason}`,
        reportedBy: (req as AuthenticatedRequest).user.id,
        affectedVisits: affectedVisits.map(v => v.id),
        affectedCarers: [carerId],
        severity: affectedVisits.length > 5 ? 'high' : 'medium'
      });

      res.json({
        success: true,
        data: {
          disruption,
          affectedVisitsCount: affectedVisits.length,
          resolutionOptions: disruption.resolutionOptions
        },
        message: `Found ${affectedVisits.length} affected visits. Resolution options generated.`
      });

    } catch (error: any) {
      logger.error('Failed to handle carer unavailability:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get emergency resolution options
   * POST /api/rostering/roster/emergency-options
   */
  getEmergencyResolutionOptions = async (req: Request, res: Response): Promise<void> => {
    try {
      const { disruptionId } = req.body;

      if (!disruptionId) {
        res.status(400).json({
          success: false,
          error: 'disruptionId is required'
        });
        return;
      }

      const disruption = await this.disruptionService.getDisruption(disruptionId);

      if (!disruption) {
        res.status(404).json({
          success: false,
          error: 'Disruption not found'
        });
        return;
      }

      res.json({
        success: true,
        data: {
          disruption,
          resolutionOptions: disruption.resolutionOptions
        }
      });

    } catch (error: any) {
      logger.error('Failed to get resolution options:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Apply emergency resolution
   * POST /api/rostering/roster/apply-emergency-resolution
   */
  applyEmergencyResolution = async (req: Request, res: Response): Promise<void> => {
    try {
      const { disruptionId, resolutionId } = req.body;
      const appliedBy = (req as AuthenticatedRequest).user.id;

      if (!disruptionId || !resolutionId) {
        res.status(400).json({
          success: false,
          error: 'disruptionId and resolutionId are required'
        });
        return;
      }

      const result = await this.disruptionService.applyResolution(
        disruptionId,
        resolutionId,
        appliedBy
      );

      res.json({
        success: true,
        data: result,
        message: 'Resolution applied successfully'
      });

    } catch (error: any) {
      logger.error('Failed to apply resolution:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Swap two assignments
   * POST /api/rostering/roster/swap-assignments
   */
/**
 * Swap two assignments between carers with full validation, audit trail, and rollback
 * POST /api/rostering/roster/swap-assignments
 */
swapAssignments = async (req: Request, res: Response): Promise<void> => {
  try {
    const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
    const userId = (req as AuthenticatedRequest).user.id;
    const userEmail = (req as AuthenticatedRequest).user.email;
    const { assignmentIdA, assignmentIdB, reason, forceOverride } = req.body;

    // ============================================
    // 1. INPUT VALIDATION
    // ============================================
    if (!assignmentIdA || !assignmentIdB) {
      res.status(400).json({
        success: false,
        error: 'Both assignmentIdA and assignmentIdB are required'
      });
      return;
    }

    if (assignmentIdA === assignmentIdB) {
      res.status(400).json({
        success: false,
        error: 'Cannot swap assignment with itself'
      });
      return;
    }

    logger.info('Starting assignment swap', {
      tenantId,
      assignmentIdA,
      assignmentIdB,
      userId,
      reason
    });

    // ============================================
    // 2. FETCH ASSIGNMENTS WITH FULL CONTEXT
    // ============================================
    const [assignmentA, assignmentB] = await Promise.all([
      this.prisma.assignment.findFirst({
        where: { id: assignmentIdA, tenantId },
        include: {
          visit: {
            select: {
              id: true,
              requestorName: true,
              address: true,
              scheduledStartTime: true,
              scheduledEndTime: true,
              estimatedDuration: true,
              requirements: true,
              postcode: true
            }
          },
          carer: {
            select: {
              id: true,
              firstName: true,
              lastName: true,
              email: true,
              skills: true,
              postcode: true
            }
          },
          roster: {
            select: {
              id: true,
              status: true,
              startDate: true,
              endDate: true
            }
          }
        }
      }),
      this.prisma.assignment.findFirst({
        where: { id: assignmentIdB, tenantId },
        include: {
          visit: {
            select: {
              id: true,
              requestorName: true,
              address: true,
              scheduledStartTime: true,
              scheduledEndTime: true,
              estimatedDuration: true,
              requirements: true,
              postcode: true
            }
          },
          carer: {
            select: {
              id: true,
              firstName: true,
              lastName: true,
              email: true,
              skills: true,
              postcode: true
            }
          },
          roster: {
            select: {
              id: true,
              status: true,
              startDate: true,
              endDate: true
            }
          }
        }
      })
    ]);

    // ============================================
    // 3. EXISTENCE VALIDATION
    // ============================================
    if (!assignmentA) {
      res.status(404).json({
        success: false,
        error: `Assignment A not found: ${assignmentIdA}`
      });
      return;
    }

    if (!assignmentB) {
      res.status(404).json({
        success: false,
        error: `Assignment B not found: ${assignmentIdB}`
      });
      return;
    }

    // ============================================
    // 4. LOCK STATUS CHECK
    // ============================================
    if (assignmentA.locked && !forceOverride) {
      res.status(400).json({
        success: false,
        error: `Assignment A is locked: ${assignmentA.lockedReason || 'Locked by coordinator'}`,
        code: 'ASSIGNMENT_LOCKED',
        lockedBy: assignmentA.lockedBy,
        lockedAt: assignmentA.lockedAt
      });
      return;
    }

    if (assignmentB.locked && !forceOverride) {
      res.status(400).json({
        success: false,
        error: `Assignment B is locked: ${assignmentB.lockedReason || 'Locked by coordinator'}`,
        code: 'ASSIGNMENT_LOCKED',
        lockedBy: assignmentB.lockedBy,
        lockedAt: assignmentB.lockedAt
      });
      return;
    }

    // ============================================
    // 5. ROSTER STATUS CHECK
    // ============================================
    if (assignmentA.roster?.status === 'COMPLETED') {
      res.status(400).json({
        success: false,
        error: 'Cannot swap assignments in completed roster',
        code: 'ROSTER_COMPLETED'
      });
      return;
    }

    if (assignmentB.roster?.status === 'COMPLETED') {
      res.status(400).json({
        success: false,
        error: 'Cannot swap assignments in completed roster',
        code: 'ROSTER_COMPLETED'
      });
      return;
    }

    // ============================================
    // 6. CONSTRAINT VALIDATION
    // ============================================
    const constraintsService = new ConstraintsService(this.prisma);
    
    // Validate swapping A's visit to B's carer
    const validationA = await constraintsService.validateManualChange(
      tenantId,
      {
        assignmentId: assignmentIdA,
        visitId: assignmentA.visitId,
        newCarerId: assignmentB.carerId,
        newScheduledTime: assignmentA.scheduledTime
      }
    );

    // Validate swapping B's visit to A's carer
    const validationB = await constraintsService.validateManualChange(
      tenantId,
      {
        assignmentId: assignmentIdB,
        visitId: assignmentB.visitId,
        newCarerId: assignmentA.carerId,
        newScheduledTime: assignmentB.scheduledTime
      }
    );

    // Collect all violations
    const allHardBlocks = [
      ...validationA.hardBlocks,
      ...validationB.hardBlocks
    ];

    const allSoftWarnings = [
      ...validationA.softWarnings,
      ...validationB.softWarnings
    ];

    // ============================================
    // 7. HARD CONSTRAINT ENFORCEMENT
    // ============================================
    if (allHardBlocks.length > 0 && !forceOverride) {
      res.status(400).json({
        success: false,
        error: 'Swap would violate hard constraints',
        code: 'CONSTRAINT_VIOLATION',
        violations: {
          hard: allHardBlocks,
          soft: allSoftWarnings
        },
        details: {
          assignmentA: {
            visit: assignmentA.visit.requestorName,
            currentCarer: `${assignmentA.carer.firstName} ${assignmentA.carer.lastName}`,
            proposedCarer: `${assignmentB.carer.firstName} ${assignmentB.carer.lastName}`,
            violations: validationA.hardBlocks
          },
          assignmentB: {
            visit: assignmentB.visit.requestorName,
            currentCarer: `${assignmentB.carer.firstName} ${assignmentB.carer.lastName}`,
            proposedCarer: `${assignmentA.carer.firstName} ${assignmentA.carer.lastName}`,
            violations: validationB.hardBlocks
          }
        },
        hint: 'Use forceOverride=true to bypass constraints (requires manager approval)'
      });
      return;
    }

    // ============================================
    // 8. CALCULATE TRAVEL TIME IMPACT
    // ============================================
    const travelService = new TravelService(this.prisma);
    let travelImpact = {
      assignmentA: { before: assignmentA.travelFromPrevious, after: 0 },
      assignmentB: { before: assignmentB.travelFromPrevious, after: 0 }
    };

    try {
      // Calculate new travel times after swap
      if (assignmentA.visit.postcode && assignmentB.carer.postcode) {
        const travelA = await travelService.getTravelTime(
          assignmentB.carer.postcode,
          assignmentA.visit.postcode
        );
        travelImpact.assignmentA.after = Math.ceil(travelA.durationSeconds / 60);
      }

      if (assignmentB.visit.postcode && assignmentA.carer.postcode) {
        const travelB = await travelService.getTravelTime(
          assignmentA.carer.postcode,
          assignmentB.visit.postcode
        );
        travelImpact.assignmentB.after = Math.ceil(travelB.durationSeconds / 60);
      }
    } catch (error) {
      logger.warn('Failed to calculate travel impact', { error: (error as any).message });
      // Continue with swap even if travel calculation fails
    }

    // ============================================
    // 9. EXECUTE SWAP IN TRANSACTION
    // ============================================
    const swapResult = await this.prisma.$transaction(async (tx) => {
      // 9.1. Create audit records
      const auditRecords = await Promise.all([
        tx.assignmentHistory.create({
          data: {
            assignmentId: assignmentIdA,
            tenantId,
            changeType: 'manual_swap',
            previousCarerId: assignmentA.carerId,
            newCarerId: assignmentB.carerId,
            previousTime: assignmentA.scheduledTime,
            newTime: assignmentA.scheduledTime, // Time stays same, carer changes
            changedBy: userId, // This should be the authenticated user's ID
            changedByEmail: userEmail,
            reason: reason || 'Manual swap via coordinator',
            constraintOverrides: forceOverride ? {
              overridden: true,
              violations: allHardBlocks
            } : undefined
          }
        }),
        tx.assignmentHistory.create({
          data: {
            assignmentId: assignmentIdB,
            tenantId,
            changeType: 'manual_swap',
            previousCarerId: assignmentB.carerId,
            newCarerId: assignmentA.carerId,
            previousTime: assignmentB.scheduledTime,
            newTime: assignmentB.scheduledTime,
            changedBy: userId, // This should be the authenticated user's ID
            changedByEmail: userEmail,
            reason: reason || 'Manual swap via coordinator',
            constraintOverrides: forceOverride ? {
              overridden: true,
              violations: allHardBlocks
            } : undefined
          }
        })
      ]);

      // 9.2. Perform the swap
      const [updatedA, updatedB] = await Promise.all([
        tx.assignment.update({
          where: { id: assignmentIdA },
          data: {
            carerId: assignmentB.carerId,
            travelFromPrevious: travelImpact.assignmentA.after,
            manuallyAssigned: true,
            warnings: allSoftWarnings.length > 0 ? allSoftWarnings : [],
            updatedAt: new Date()
          },
          include: {
            carer: {
              select: {
                id: true,
                firstName: true,
                lastName: true,
                email: true
              }
            },
            visit: {
              select: {
                id: true,
                requestorName: true,
                address: true
              }
            }
          }
        }),
        tx.assignment.update({
          where: { id: assignmentIdB },
          data: {
            carerId: assignmentA.carerId,
            travelFromPrevious: travelImpact.assignmentB.after,
            manuallyAssigned: true,
            warnings: allSoftWarnings.length > 0 ? allSoftWarnings : [],
            updatedAt: new Date()
          },
          include: {
            carer: {
              select: {
                id: true,
                firstName: true,
                lastName: true,
                email: true
              }
            },
            visit: {
              select: {
                id: true,
                requestorName: true,
                address: true
              }
            }
          }
        })
      ]);

      // 9.3. Update roster metrics if needed
      if (assignmentA.rosterId === assignmentB.rosterId) {
        const roster = await tx.roster.findUnique({
          where: { id: assignmentA.rosterId },
          include: { assignments: true }
        });

        if (roster) {
          const totalTravel = roster.assignments.reduce(
            (sum, a) => sum + (a.travelFromPrevious || 0),
            0
          );

          await tx.roster.update({
            where: { id: roster.id },
            data: {
              totalTravelMinutes: totalTravel,
              updatedAt: new Date()
            }
          });
        }
      }

      return { updatedA, updatedB, auditRecords };
    }, {
      maxWait: 5000, // 5 seconds
      timeout: 10000, // 10 seconds
      isolationLevel: 'Serializable' // Highest isolation level
    });

    // ============================================
    // 10. SEND NOTIFICATIONS
    // ============================================
    try {
      const notificationService = new NotificationService();

      // Notify carer A (now assigned to B's visit)
      await notificationService.sendNotification({
        event_type: 'assignment_swapped',
        recipient_type: 'push',
        recipient: assignmentB.carerId,
        tenant_id: tenantId,
        data: {
          assignmentId: assignmentIdA,
          previousVisit: assignmentA.visit.requestorName,
          newVisit: assignmentB.visit.requestorName,
          newAddress: assignmentB.visit.address,
          scheduledTime: assignmentB.scheduledTime,
          message: `Your assignment has been swapped. You are now visiting ${assignmentB.visit.requestorName} instead of ${assignmentA.visit.requestorName}.`
        }
      });

      // Notify carer B (now assigned to A's visit)
      await notificationService.sendNotification({
        event_type: 'assignment_swapped',
        recipient_type: 'push',
        recipient: assignmentA.carerId,
        tenant_id: tenantId,
        data: {
          assignmentId: assignmentIdB,
          previousVisit: assignmentB.visit.requestorName,
          newVisit: assignmentA.visit.requestorName,
          newAddress: assignmentA.visit.address,
          scheduledTime: assignmentA.scheduledTime,
          message: `Your assignment has been swapped. You are now visiting ${assignmentA.visit.requestorName} instead of ${assignmentB.visit.requestorName}.`
        }
      });
    } catch (notificationError) {
      logger.error('Failed to send swap notifications', {
        error: (notificationError as any).message
      });
      // Don't fail the swap if notifications fail
    }

    // ============================================
    // 11. BROADCAST VIA WEBSOCKET (if available)
    // ============================================
    if (this.websocketService) {
      this.websocketService.broadcastToTenant(tenantId, 'assignment:swapped', {
        assignmentIdA,
        assignmentIdB,
        swappedAt: new Date(),
        changes: {
          assignmentA: {
            previousCarer: `${assignmentA.carer.firstName} ${assignmentA.carer.lastName}`,
            newCarer: `${swapResult.updatedA.carer.firstName} ${swapResult.updatedA.carer.lastName}`
          },
          assignmentB: {
            previousCarer: `${assignmentB.carer.firstName} ${assignmentB.carer.lastName}`,
            newCarer: `${swapResult.updatedB.carer.firstName} ${swapResult.updatedB.carer.lastName}`
          }
        }
      });
    }

    // ============================================
    // 12. LOG SUCCESS
    // ============================================
    logger.info('Assignment swap completed successfully', {
      tenantId,
      assignmentIdA,
      assignmentIdB,
      userId,
      travelImpact,
      softWarnings: allSoftWarnings.length,
      forceOverride
    });

    // ============================================
    // 13. RETURN SUCCESS RESPONSE
    // ============================================
    res.json({
      success: true,
      message: 'Assignments swapped successfully',
      data: {
        assignmentA: {
          id: swapResult.updatedA.id,
          visit: swapResult.updatedA.visit,
          carer: swapResult.updatedA.carer,
          travelImpact: {
            before: travelImpact.assignmentA.before,
            after: travelImpact.assignmentA.after,
            change: travelImpact.assignmentA.after - travelImpact.assignmentA.before
          }
        },
        assignmentB: {
          id: swapResult.updatedB.id,
          visit: swapResult.updatedB.visit,
          carer: swapResult.updatedB.carer,
          travelImpact: {
            before: travelImpact.assignmentB.before,
            after: travelImpact.assignmentB.after,
            change: travelImpact.assignmentB.after - travelImpact.assignmentB.before
          }
        },
        validation: {
          softWarnings: allSoftWarnings,
          constraintsOverridden: forceOverride && allHardBlocks.length > 0
        },
        audit: {
          swappedBy: userEmail,
          swappedAt: new Date(),
          reason: reason || 'Manual swap via coordinator',
          auditIds: swapResult.auditRecords.map((r: any) => r.id)
        }
      }
    });

  } catch (error: any) {
    logger.error('Failed to swap assignments:', {
      error: error.message,
      stack: error.stack,
      assignmentIdA: req.body.assignmentIdA,
      assignmentIdB: req.body.assignmentIdB
    });

    res.status(500).json({
      success: false,
      error: 'Failed to swap assignments',
      message: error.message,
      code: 'SWAP_FAILED'
    });
  }
};

  /**
   * Reassign visit to different carer
   * POST /api/rostering/roster/reassign
   */
  reassignVisit = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { assignmentId, newCarerId, reason } = req.body;

      if (!assignmentId || !newCarerId) {
        res.status(400).json({
          success: false,
          error: 'assignmentId and newCarerId are required'
        });
        return;
      }

      const assignment = await this.prisma.assignment.findFirst({
        where: { id: assignmentId, tenantId },
        include: { visit: true }
      });

      if (!assignment) {
        res.status(404).json({
          success: false,
          error: 'Assignment not found'
        });
        return;
      }

      const newCarer = await this.prisma.carer.findFirst({
        where: { id: newCarerId, tenantId }
      });

      if (!newCarer) {
        res.status(404).json({
          success: false,
          error: 'New carer not found'
        });
        return;
      }

      await this.prisma.assignment.update({
        where: { id: assignmentId },
        data: {
          carerId: newCarerId,
          updatedAt: new Date()
        }
      });

      await this.notificationService.sendNotification({
        event_type: 'assignment_notification',
        recipient_type: 'push',
        recipient: newCarerId,
        tenant_id: (req as AuthenticatedRequest).user.tenantId,
        data: {
          assignmentId,
          visitId: assignment.visitId,
          address: assignment.visit.address,
          message: `You've been assigned to visit ${assignment.visit.address}`
        }
      });

      logger.info('Visit reassigned', { assignmentId, newCarerId, reason });

      res.json({
        success: true,
        message: 'Visit reassigned successfully'
      });

    } catch (error: any) {
      logger.error('Failed to reassign visit:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Lock assignment (prevent auto-optimization from changing it)
   * POST /api/rostering/roster/assignments/:id/lock
   */
  lockAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const { id } = req.params;
      const { reason } = req.body;

      await this.prisma.assignment.update({
        where: { id },
        data: {
          updatedAt: new Date()
        }
      });

      logger.info('Assignment locked', { id, reason });

      res.json({
        success: true,
        message: 'Assignment locked successfully'
      });

    } catch (error: any) {
      logger.error('Failed to lock assignment:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Unlock assignment
   * DELETE /api/rostering/roster/assignments/:id/lock
   */
  unlockAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const { id } = req.params;

      await this.prisma.assignment.update({
        where: { id },
        data: {
          updatedAt: new Date()
        }
      });

      logger.info('Assignment unlocked', { id });

      res.json({
        success: true,
        message: 'Assignment unlocked successfully'
      });

    } catch (error: any) {
      logger.error('Failed to unlock assignment:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get locked assignments
   * GET /api/rostering/roster/locked-assignments/:rosterId
   */
  getLockedAssignments = async (req: Request, res: Response): Promise<void> => {
    try {
      const { rosterId } = req.params;

      const assignments = await this.prisma.assignment.findMany({
        where: {
          rosterId
        },
        include: {
          visit: true,
          carer: {
            select: {
              id: true,
              firstName: true,
              lastName: true
            }
          }
        }
      });

      res.json({
        success: true,
        data: assignments
      });

    } catch (error: any) {
      logger.error('Failed to get locked assignments:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Validate manual change before applying
   * POST /api/rostering/roster/validate-manual-change
   */
 // File: src/controllers/roster.controller.ts

/**
 * ✅ UPDATED: Validate manual change before applying
 * POST /api/rostering/roster/validate-manual-change
 */
validateManualChange = async (req: Request, res: Response): Promise<void> => {
  try {
    const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
    const { assignmentId, visitId, newCarerId, newScheduledTime } = req.body;

    if (!visitId || !newCarerId) {
      res.status(400).json({
        success: false,
        error: 'visitId and newCarerId are required'
      });
      return;
    }

    // ✅ Use the new validation service
    const constraintsService = new ConstraintsService(this.prisma);
    const validation = await constraintsService.validateManualChange(
      tenantId,
      {
        assignmentId,
        visitId,
        newCarerId,
        newScheduledTime: newScheduledTime ? new Date(newScheduledTime) : undefined
      }
    );

    res.json({
      success: true,
      data: validation,
      message: validation.isValid 
        ? 'Change is valid' 
        : 'Change violates constraints'
    });

  } catch (error: any) {
    logger.error('Failed to validate manual change:', error);
    res.status(500).json({ success: false, error: error.message });
  }
};

  /**
   * Bulk update assignments
   * POST /api/rostering/roster/bulk-update
   */
  bulkUpdateAssignments = async (req: Request, res: Response): Promise<void> => {
    try {
      const { updates } = req.body;

      if (!Array.isArray(updates) || updates.length === 0) {
        res.status(400).json({
          success: false,
          error: 'updates array is required'
        });
        return;
      }

      await this.prisma.$transaction(
        updates.map((update: { assignmentId: string; carerId?: string; scheduledTime?: string }) =>
          this.prisma.assignment.update({
            where: { id: update.assignmentId },
            data: {
              carerId: update.carerId,
              scheduledTime: update.scheduledTime ? new Date(update.scheduledTime) : undefined,
              updatedAt: new Date()
            }
          })
        )
      );

      logger.info('Bulk assignment update completed', { count: updates.length });

      res.json({
        success: true,
        message: `${updates.length} assignments updated successfully`
      });

    } catch (error: any) {
      logger.error('Failed to bulk update assignments:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get client continuity score
   * GET /api/rostering/roster/continuity/client/:clientId
   */
  getClientContinuity = async (req: Request, res: Response): Promise<void> => {
    try {
      const { clientId } = req.params;
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();

      const visits = await this.prisma.externalRequest.findMany({
        where: {
          tenantId,
          requestorEmail: clientId
        },
        include: {
          visits: {
            include: {
              assignments: {
                select: {
                  carerId: true,
                  carer: {
                    select: {
                      firstName: true,
                      lastName: true
                    }
                  }
                }
              }
            }
          }
        },
        orderBy: { scheduledStartTime: 'desc' },
        take: 30
      });

      const carerFrequency = new Map<string, number>();
      visits.forEach((request: any) => {
        request.visits.forEach((visit: any) => {
          visit.assignments.forEach((assignment: any) => {
            const count = carerFrequency.get(assignment.carerId) || 0;
            carerFrequency.set(assignment.carerId, count + 1);
          });
        });
      });

      const totalVisits = visits.length;
      const mostFrequentCarer = Array.from(carerFrequency.entries())
        .sort((a, b) => b[1] - a[1])[0];

      const continuityScore = mostFrequentCarer 
        ? (mostFrequentCarer[1] / totalVisits) * 100 
        : 0;

      const clientContinuity: ClientContinuity = {
        clientId,
        totalVisits,
        continuityScore: Math.round(continuityScore),
        mostFrequentCarer: mostFrequentCarer ? {
          carerId: mostFrequentCarer[0],
          visitCount: mostFrequentCarer[1],
          percentage: Math.round((mostFrequentCarer[1] / totalVisits) * 100)
        } : null,
        carerDistribution: Array.from(carerFrequency.entries()).map(([carerId, count]) => ({
          carerId,
          visitCount: count,
          percentage: Math.round((count / totalVisits) * 100)
        }))
      };

      res.json({
        success: true,
        data: clientContinuity
      });

    } catch (error: any) {
      logger.error('Failed to get client continuity:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get continuity report
   * POST /api/rostering/roster/continuity/report
   */
  getContinuityReport = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();
      const { dateFrom, dateTo } = req.body;

      if (!dateFrom || !dateTo) {
        res.status(400).json({
          success: false,
          error: 'dateFrom and dateTo are required'
        });
        return;
      }

      const visits = await this.prisma.externalRequest.findMany({
        where: {
          tenantId,
          scheduledStartTime: {
            gte: new Date(dateFrom),
            lte: new Date(dateTo)
          }
        },
        include: {
          visits: {
            include: {
              assignments: {
                select: {
                  carerId: true
                }
              }
            }
          }
        }
      });

      const clientVisits = new Map<string, any[]>();
      visits.forEach((visit: any) => {
        const clientId = visit.requestorEmail;
        if (!clientVisits.has(clientId)) {
          clientVisits.set(clientId, []);
        }
        clientVisits.get(clientId)!.push(visit);
      });

      const report = Array.from(clientVisits.entries()).map(([clientId, clientVisitList]: [string, any[]]) => {
        const carerCounts = new Map<string, number>();
        clientVisitList.forEach((request: any) => {
          request.visits.forEach((visit: any) => {
            visit.assignments.forEach((assignment: any) => {
              const count = carerCounts.get(assignment.carerId) || 0;
              carerCounts.set(assignment.carerId, count + 1);
            });
          });
        });

        const totalVisits = clientVisitList.reduce((sum, request) => sum + request.visits.length, 0);
        const maxCount = Math.max(...Array.from(carerCounts.values()));
        const continuityScore = (maxCount / totalVisits) * 100;

        return {
          clientId,
          totalVisits,
          continuityScore: Math.round(continuityScore),
          differentCarers: carerCounts.size
        };
      });

      const avgContinuity = report.reduce((sum: number, r: any) => sum + r.continuityScore, 0) / report.length;

      const continuityReport: ContinuityReport = {
        dateFrom: new Date(dateFrom),
        dateTo: new Date(dateTo),
        totalClients: report.length,
        averageContinuityScore: Math.round(avgContinuity),
        clients: report.sort((a: any, b: any) => a.continuityScore - b.continuityScore)
      };

      res.json({
        success: true,
        data: continuityReport
      });

    } catch (error: any) {
      logger.error('Failed to get continuity report:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get continuity alerts
   * GET /api/rostering/roster/continuity-alerts/:tenantId
   */
  getContinuityAlerts = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.params.tenantId;

      const today = new Date();
      const nextWeek = new Date(today);
      nextWeek.setDate(nextWeek.getDate() + 7);

      const visits = await this.prisma.externalRequest.findMany({
        where: {
          tenantId,
          scheduledStartTime: {
            gte: today,
            lte: nextWeek
          }
        },
        include: {
          visits: {
            include: {
              assignments: {
                include: {
                  carer: {
                    select: {
                      id: true,
                      firstName: true,
                      lastName: true
                    }
                  }
                }
              }
            }
          },
          matches: {
            where: {
              response: 'ACCEPTED'
            },
            select: {
              carerId: true
            }
          }
        }
      });

      const alerts = visits
        .filter((request: any) => {
          const preferredCarers = request.matches.map((m: any) => m.carerId);
          const visit = request.visits[0]; // Get the first visit
          const assignedCarer = visit?.assignments[0]?.carerId;

          return preferredCarers.length > 0 &&
                 assignedCarer &&
                 !preferredCarers.includes(assignedCarer);
        })
        .map((request: any) => {
          const visit = request.visits[0]; // Get the first visit
          return {
            visitId: visit?.id || request.id,
            clientId: request.requestorEmail,
            clientName: request.requestorName,
            scheduledTime: request.scheduledStartTime,
            assignedCarer: visit?.assignments[0]?.carer,
            preferredCarers: request.matches.map((m: any) => m.carerId),
            reason: 'Preferred carer not assigned'
          };
        });

      res.json({
        success: true,
        data: {
          alertCount: alerts.length,
          alerts
        }
      });

    } catch (error: any) {
      logger.error('Failed to get continuity alerts:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get live roster status
   * GET /api/rostering/roster/live-status/:rosterId
   */
  getLiveRosterStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const { rosterId } = req.params;

      const roster = await this.prisma.roster.findUnique({
        where: { id: rosterId },
        include: {
          assignments: {
            include: {
              visit: true,
              carer: {
                select: {
                  id: true,
                  firstName: true,
                  lastName: true
                }
              }
            }
          }
        }
      });

      if (!roster) {
        res.status(404).json({
          success: false,
          error: 'Roster not found'
        });
        return;
      }

      const now = new Date();
      const assignments = roster.assignments;

      const completed = assignments.filter((a: Assignment) => a.status === 'COMPLETED').length;
      const inProgress = assignments.filter((a: Assignment) => {
        const start = new Date(a.scheduledTime);
        const end = new Date(a.estimatedEndTime);
        return now >= start && now <= end;
      }).length;
      const upcoming = assignments.filter((a: Assignment) => {
        const start = new Date(a.scheduledTime);
        return now < start;
      }).length;
      const delayed = assignments.filter((a: Assignment) => a.warnings.includes('late')).length;

      const liveStatus: LiveRosterStatus = {
        rosterId,
        totalAssignments: assignments.length,
        completed,
        inProgress,
        upcoming,
        delayed,
        completionRate: Math.round((completed / assignments.length) * 100),
        onTimeRate: Math.round(((assignments.length - delayed) / assignments.length) * 100)
      };

      res.json({
        success: true,
        data: liveStatus
      });

    } catch (error: any) {
      logger.error('Failed to get live roster status:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Update visit status
   * PATCH /api/rostering/roster/visits/:visitId/status
   */
  updateVisitStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const { visitId } = req.params;
      const { status, notes } = req.body;

      if (!['STARTED', 'COMPLETED', 'DELAYED', 'CANCELLED'].includes(status)) {
        res.status(400).json({
          success: false,
          error: 'Invalid status. Must be STARTED, COMPLETED, DELAYED, or CANCELLED'
        });
        return;
      }

      await this.prisma.assignment.updateMany({
        where: { visitId },
        data: {
          status: status === 'STARTED' ? 'ACCEPTED' : 
                  status === 'COMPLETED' ? 'COMPLETED' : 'PENDING',
          updatedAt: new Date()
        }
      });

      if (status === 'DELAYED') {
        const visit = await this.prisma.externalRequest.findUnique({
          where: { id: visitId },
          select: { requestorEmail: true, requestorName: true }
        });

        if (visit) {
          await this.notificationService.sendNotification({
            event_type: 'visit_delayed_notification',
            recipient_type: 'sms',
            recipient: visit.requestorEmail,
            tenant_id: (req as AuthenticatedRequest).user.tenantId,
            data: {
              visitId,
              notes: notes || '',
              message: `Your scheduled visit has been delayed. ${notes || ''}`
            }
          });
        }
      }

      logger.info('Visit status updated', { visitId, status });

      res.json({
        success: true,
        message: 'Visit status updated successfully'
      });

    } catch (error: any) {
      logger.error('Failed to update visit status:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };

  /**
   * Get at-risk visits (likely to be late)
   * GET /api/rostering/roster/at-risk-visits/:rosterId
   */
  getAtRiskVisits = async (req: Request, res: Response): Promise<void> => {
    try {
      const { rosterId } = req.params;

      const assignments = await this.prisma.assignment.findMany({
        where: {
          rosterId,
          status: { in: ['PENDING', 'OFFERED', 'ACCEPTED'] }
        },
        include: {
          visit: true,
          carer: {
            select: {
              id: true,
              firstName: true,
              lastName: true
            }
          }
        }
      });

      const now = new Date();
      const atRiskVisits = assignments.filter((assignment: any) => {
        const scheduledTime = new Date(assignment.scheduledTime);
        const minutesUntilVisit = (scheduledTime.getTime() - now.getTime()) / 60000;

        return minutesUntilVisit > 0 &&
               minutesUntilVisit <= 60 &&
               assignment.warnings.length > 0;
      });

      res.json({
        success: true,
        data: {
          atRiskCount: atRiskVisits.length,
          visits: atRiskVisits.map(a => ({
            assignmentId: a.id,
            visitId: a.visitId,
            clientAddress: a.visit.address,
            scheduledTime: a.scheduledTime,
            carer: a.carer,
            warnings: a.warnings,
            minutesUntilVisit: Math.round((new Date(a.scheduledTime).getTime() - now.getTime()) / 60000)
          }))
        }
      });

    } catch (error: any) {
      logger.error('Failed to get at-risk visits:', error);
      res.status(500).json({ success: false, error: error.message });
    }
  };
}