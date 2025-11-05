import { PrismaClient, IncidentSeverity, IncidentType, IncidentStatus } from '@prisma/client';
import { TravelService } from './travel.service';
import { logger } from '../utils/logger';

export interface LiveCarerStatus {
  carerId: string;
  currentVisitId?: string;
  location?: {
    latitude: number;
    longitude: number;
    accuracy: number;
    timestamp: Date;
  };
  status: 'available' | 'traveling' | 'on_visit' | 'break' | 'off_duty';
  currentVisitStatus?: 'traveling_to' | 'on_site' | 'completed' | 'delayed';
  nextVisitId?: string;
  etaToNext?: number; // minutes
}

export interface LiveVisitStatus {
  visitId: string;
  carerId?: string;
  scheduledTime: Date;
  estimatedEndTime: Date;
  actualStartTime?: Date;
  actualEndTime?: Date;
  status: 'scheduled' | 'traveling_to' | 'on_site' | 'completed' | 'cancelled' | 'delayed';
  locationStatus?: 'on_time' | 'running_late' | 'at_risk' | 'missed';
  predictedLateness?: number; // minutes
  checkInTime?: Date;
  checkOutTime?: Date;
  clientNotified?: boolean;
}

export interface LiveDashboardData {
  timestamp: Date;
  summary: {
    totalVisits: number;
    completed: number;
    inProgress: number;
    upcoming: number;
    delayed: number;
    missed: number;
  };
  alerts: LiveAlert[];
  carerStatus: LiveCarerStatus[];
  visitStatus: LiveVisitStatus[];
  incidents: LiveIncident[];
}

export interface LiveAlert {
  id: string;
  type: 'lateness' | 'no_checkin' | 'geofence_breach' | 'incident' | 'escalation';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  relatedEntity: {
    type: 'visit' | 'carer' | 'client';
    id: string;
    name: string;
  };
  timestamp: Date;
  acknowledged: boolean;
  actions: string[];
}

export interface LiveIncident {
  id: string;
  type: IncidentType;
  severity: IncidentSeverity;
  title: string;
  description: string;
  visitId?: string;
  carerId?: string;
  clientId?: string;
  reportedAt: Date;
  status: IncidentStatus;
  assignedTo?: string;
}

export class LiveOperationsService {
  constructor(
    private prisma: PrismaClient,
    private travelService: TravelService
  ) {}

  /**
   * Update carer location and status
   */
  async updateCarerLocation(
    carerId: string,
    location: {
      latitude: number;
      longitude: number;
      accuracy: number;
    }
  ): Promise<LiveCarerStatus> {
    try {
      // Store location update
      await this.prisma.carerLocationUpdate.create({
        data: {
          carerId,
          latitude: location.latitude,
          longitude: location.longitude,
          accuracy: location.accuracy,
          recordedAt: new Date()
        }
      });

      // Get current assignment for the carer
      const currentAssignment = await this.prisma.assignment.findFirst({
        where: {
          carerId,
          scheduledTime: {
            lte: new Date()
          },
          estimatedEndTime: {
            gte: new Date()
          },
          status: { in: ['ACCEPTED', 'COMPLETED'] }
        },
        include: {
          visit: true
        },
        orderBy: {
          scheduledTime: 'desc'
        }
      });

      // Determine status based on location and assignments
      let status: LiveCarerStatus['status'] = 'available';
      let currentVisitStatus: LiveCarerStatus['currentVisitStatus'] = undefined;

      if (currentAssignment) {
        const isOnSite = await this.isCarerAtVisitLocation(carerId, currentAssignment.visitId, location);
        
        if (isOnSite) {
          status = 'on_visit';
          currentVisitStatus = 'on_site';
        } else {
          status = 'traveling';
          currentVisitStatus = 'traveling_to';
        }
      }

      const carerStatus: LiveCarerStatus = {
        carerId,
        location: {
          ...location,
          timestamp: new Date()
        },
        status,
        currentVisitStatus,
        currentVisitId: currentAssignment?.visitId
      };

      // Check for lateness and create alerts if needed
      await this.checkForLateness(carerId, currentAssignment);

      return carerStatus;

    } catch (error) {
      logger.error('Failed to update carer location:', error);
      throw error;
    }
  }

  /**
   * Check-in to visit with geofence validation
   */
  async checkIn(
    visitId: string,
    carerId: string,
    location: { latitude: number; longitude: number },
    notes?: string
  ) {
    try {
      const visit = await this.prisma.externalRequest.findUnique({
        where: { id: visitId },
        include: { assignments: true }
      });

      if (!visit) {
        throw new Error('Visit not found');
      }

      // Validate carer is assigned to this visit
      const assignment = visit.assignments.find(a => a.carerId === carerId);
      if (!assignment) {
        throw new Error('Carer not assigned to this visit');
      }

      // Check geofence (100m radius)
      const withinGeofence = visit.latitude && visit.longitude ? await this.isWithinGeofence(
        location.latitude,
        location.longitude,
        visit.latitude,
        visit.longitude,
        100
      ) : false;

      const distance = visit.latitude && visit.longitude ? this.calculateDistance(
        location.latitude,
        location.longitude,
        visit.latitude,
        visit.longitude
      ) : 0;

      const checkIn = await this.prisma.visitCheckIn.create({
        data: {
          visitId,
          carerId,
          latitude: location.latitude,
          longitude: location.longitude,
          withinGeofence,
          distance,
          checkInTime: new Date(),
          notes,
          requiresApproval: !withinGeofence
        }
      });

      // Update assignment status
      await this.prisma.assignment.update({
        where: { id: assignment.id },
        data: {
          status: 'COMPLETED', // Mark as in progress
          updatedAt: new Date()
        }
      });

      // Create timesheet entry
      await this.prisma.timesheetEntry.create({
        data: {
          timesheetId: await this.getOrCreateTimesheet(carerId),
          visitId,
          checkInTime: new Date(),
          scheduledStart: assignment.scheduledTime,
          scheduledEnd: assignment.estimatedEndTime,
          scheduledDuration: visit.estimatedDuration || 60,
          checkInLocation: {
            latitude: location.latitude,
            longitude: location.longitude
          },
          withinGeofence
        }
      });

      logger.info(`Check-in recorded for visit ${visitId}`, {
        carerId,
        withinGeofence,
        distance
      });

      return checkIn;

    } catch (error) {
      logger.error('Failed to record check-in:', error);
      throw error;
    }
  }

  /**
   * Check-out from visit
   */
  async checkOut(
    visitId: string,
    carerId: string,
    location: { latitude: number; longitude: number },
    options: {
      tasksCompleted?: string[];
      incidentReported?: boolean;
      incidentDetails?: string;
      notes?: string;
    } = {}
  ) {
    try {
      const visit = await this.prisma.externalRequest.findUnique({
        where: { id: visitId }
      });

      if (!visit) {
        throw new Error('Visit not found');
      }

      const actualDuration = await this.calculateActualDuration(visitId, carerId);

      const checkOut = await this.prisma.visitCheckOut.create({
        data: {
          visitId,
          carerId,
          latitude: location.latitude,
          longitude: location.longitude,
          checkOutTime: new Date(),
          actualDuration,
          tasksCompleted: options.tasksCompleted || [],
          incidentReported: options.incidentReported || false,
          incidentDetails: options.incidentDetails,
          notes: options.notes
        }
      });

      // Update assignment status
      await this.prisma.assignment.updateMany({
        where: {
          visitId,
          carerId,
          status: { in: ['ACCEPTED', 'COMPLETED'] }
        },
        data: {
          status: 'COMPLETED',
          updatedAt: new Date()
        }
      });

      // Update timesheet entry
      await this.prisma.timesheetEntry.updateMany({
        where: {
          visitId,
          timesheet: {
            carerId
          }
        },
        data: {
          checkOutTime: new Date(),
          actualDuration,
          tasksCompleted: options.tasksCompleted || []
        }
      });

      // Create incident if reported
      if (options.incidentReported) {
        await this.prisma.incident.create({
          data: {
            tenantId: visit.tenantId,
            visitId,
            carerId,
            type: 'OTHER',
            severity: 'MEDIUM',
            title: `Incident reported for visit ${visitId}`,
            description: options.incidentDetails || 'Incident reported during visit',
            status: 'REPORTED',
            reportedAt: new Date(),
            reportedBy: carerId
          }
        });
      }

      logger.info(`Check-out recorded for visit ${visitId}`, {
        carerId,
        actualDuration,
        incidentReported: options.incidentReported
      });

      return checkOut;

    } catch (error) {
      logger.error('Failed to record check-out:', error);
      throw error;
    }
  }

  /**
   * Get live dashboard data
   */
  async getDashboardData(tenantId: string): Promise<LiveDashboardData> {
    try {
      const now = new Date();
      const todayStart = new Date(now);
      todayStart.setHours(0, 0, 0, 0);
      const todayEnd = new Date(now);
      todayEnd.setHours(23, 59, 59, 999);

      // Get today's assignments
      const assignments = await this.prisma.assignment.findMany({
        where: {
          tenantId,
          scheduledTime: {
            gte: todayStart,
            lte: todayEnd
          }
        },
        include: {
          visit: true,
          carer: true,
          publishedAssignments: true
        }
      });

      // Calculate summary
      const summary = this.calculateSummary(assignments, now);

      // Get active alerts
      const alerts = await this.getActiveAlerts(tenantId);

      // Get carer status
      const carerStatus = await this.getCarerStatus(tenantId);

      // Get visit status
      const visitStatus = await this.getVisitStatus(assignments, now);

      // Get recent incidents
      const incidents = await this.getRecentIncidents(tenantId);

      return {
        timestamp: now,
        summary,
        alerts,
        carerStatus,
        visitStatus,
        incidents
      };

    } catch (error) {
      logger.error('Failed to get dashboard data:', error);
      throw error;
    }
  }

  /**
   * Predict lateness for upcoming visits
   */
  async predictLateness(tenantId: string): Promise<Array<{
    visitId: string;
    carerId: string;
    scheduledTime: Date;
    predictedLateness: number;
    confidence: number;
    reasons: string[];
  }>> {
    try {
      const upcomingVisits = await this.prisma.assignment.findMany({
        where: {
          tenantId,
          scheduledTime: {
            gte: new Date()
          },
          status: { in: ['PENDING', 'ACCEPTED'] }
        },
        include: {
          visit: true,
          carer: true
        },
        take: 50 // Limit for performance
      });

      const predictions = [];

      for (const assignment of upcomingVisits) {
        const prediction = await this.predictSingleLateness(assignment);
        if (prediction.predictedLateness > 5) { // Only report if >5 minutes late
          predictions.push(prediction);
        }
      }

      return predictions;

    } catch (error) {
      logger.error('Failed to predict lateness:', error);
      return [];
    }
  }

  // ========== PRIVATE METHODS ==========

  private async isCarerAtVisitLocation(
    carerId: string,
    visitId: string,
    location: { latitude: number; longitude: number }
  ): Promise<boolean> {
    const visit = await this.prisma.externalRequest.findUnique({
      where: { id: visitId },
      select: { latitude: true, longitude: true }
    });

    if (!visit || !visit.latitude || !visit.longitude) {
      return false;
    }

    return this.isWithinGeofence(
      location.latitude,
      location.longitude,
      visit.latitude,
      visit.longitude,
      100 // 100m radius
    );
  }

  private async isWithinGeofence(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number,
    radiusMeters: number
  ): Promise<boolean> {
    const distance = this.calculateDistance(lat1, lon1, lat2, lon2);
    return distance <= radiusMeters;
  }

  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371e3; // Earth radius in meters
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

  private async checkForLateness(carerId: string, assignment: any): Promise<void> {
    if (!assignment) return;

    const now = new Date();
    const scheduledTime = new Date(assignment.scheduledTime);
    const timeDiff = (now.getTime() - scheduledTime.getTime()) / (1000 * 60); // minutes

    if (timeDiff > 15) { // 15 minutes late threshold
      // Check if alert already exists
      const existingAlert = await this.prisma.latenessAlert.findFirst({
        where: {
          visitId: assignment.visitId,
          status: 'ACTIVE'
        }
      });

      if (!existingAlert) {
        await this.prisma.latenessAlert.create({
          data: {
            tenantId: assignment.tenantId,
            visitId: assignment.visitId,
            carerId,
            scheduledTime: assignment.scheduledTime,
            estimatedArrival: new Date(now.getTime() + 5 * 60000), // Estimate 5 min from now
            delayMinutes: Math.floor(timeDiff),
            confidence: 0.8,
            reason: 'TRAFFIC',
            status: 'ACTIVE'
          }
        });

        logger.warn(`Lateness alert created for visit ${assignment.visitId}`, {
          carerId,
          delayMinutes: Math.floor(timeDiff)
        });
      }
    }
  }

  private async calculateActualDuration(visitId: string, carerId: string): Promise<number> {
    const checkIn = await this.prisma.visitCheckIn.findFirst({
      where: {
        visitId,
        carerId
      },
      orderBy: {
        checkInTime: 'desc'
      }
    });

    if (!checkIn) {
      throw new Error('No check-in found for this visit');
    }

    const checkInTime = checkIn.checkInTime.getTime();
    const checkOutTime = Date.now();
    
    return Math.floor((checkOutTime - checkInTime) / (1000 * 60)); // minutes
  }

  private async getOrCreateTimesheet(carerId: string): Promise<string> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const existingTimesheet = await this.prisma.timesheet.findFirst({
      where: {
        carerId,
        periodStart: today
      }
    });

    if (existingTimesheet) {
      return existingTimesheet.id;
    }

    const periodEnd = new Date(today);
    periodEnd.setDate(periodEnd.getDate() + 1);

    const newTimesheet = await this.prisma.timesheet.create({
      data: {
        carerId,
        tenantId: '', // This would need to be passed in or retrieved
        periodStart: today,
        periodEnd,
        status: 'DRAFT',
        scheduledHours: 0,
        actualHours: 0
      }
    });

    return newTimesheet.id;
  }

  private calculateSummary(assignments: any[], now: Date) {
    let completed = 0;
    let inProgress = 0;
    let upcoming = 0;
    let delayed = 0;
    let missed = 0;

    assignments.forEach(assignment => {
      const scheduledTime = new Date(assignment.scheduledTime);
      const endTime = new Date(assignment.estimatedEndTime);

      if (assignment.status === 'COMPLETED') {
        completed++;
      } else if (now >= scheduledTime && now <= endTime) {
        inProgress++;
        
        // Check if delayed
        const timeDiff = (now.getTime() - scheduledTime.getTime()) / (1000 * 60);
        if (timeDiff > 15) { // 15 minutes threshold
          delayed++;
        }
      } else if (now < scheduledTime) {
        upcoming++;
      } else if (now > endTime && assignment.status !== 'COMPLETED') {
        missed++;
      }
    });

    return {
      totalVisits: assignments.length,
      completed,
      inProgress,
      upcoming,
      delayed,
      missed
    };
  }

  private async getActiveAlerts(tenantId: string): Promise<LiveAlert[]> {
    const alerts = await this.prisma.latenessAlert.findMany({
      where: {
        tenantId,
        status: 'ACTIVE'
      }
    });

    return alerts.map(alert => ({
      id: alert.id,
      type: 'lateness',
      severity: this.determineLatenessSeverity(alert.delayMinutes),
      title: `Carer running ${alert.delayMinutes} minutes late`,
      description: `Carer is running late for visit`,
      relatedEntity: {
        type: 'visit',
        id: alert.visitId,
        name: 'Unknown'
      },
      timestamp: alert.createdAt,
      acknowledged: false,
      actions: ['notify_client', 'reassign', 'update_eta']
    }));
  }

  private async getCarerStatus(tenantId: string): Promise<LiveCarerStatus[]> {
    const recentLocations = await this.prisma.carerLocationUpdate.findMany({
      where: {
        recordedAt: {
          gte: new Date(Date.now() - 30 * 60 * 1000) // Last 30 minutes
        }
      },
      distinct: ['carerId'],
      orderBy: {
        recordedAt: 'desc'
      }
    });

    return recentLocations.map(location => ({
      carerId: location.carerId,
      location: {
        latitude: location.latitude,
        longitude: location.longitude,
        accuracy: location.accuracy,
        timestamp: location.recordedAt
      },
      status: 'available', // This would be determined by current assignments
      currentVisitStatus: 'traveling_to'
    }));
  }

  private async getVisitStatus(assignments: any[], now: Date): Promise<LiveVisitStatus[]> {
    return assignments.map(assignment => {
      const scheduledTime = new Date(assignment.scheduledTime);
      const timeDiff = (now.getTime() - scheduledTime.getTime()) / (1000 * 60);
      
      let status: LiveVisitStatus['status'] = 'scheduled';
      let locationStatus: LiveVisitStatus['locationStatus'] = 'on_time';

      if (assignment.status === 'COMPLETED') {
        status = 'completed';
      } else if (now >= scheduledTime && now <= new Date(assignment.estimatedEndTime)) {
        status = 'on_site';
      } else if (timeDiff > 0 && timeDiff <= 15) {
        status = 'traveling_to';
        locationStatus = 'running_late';
      } else if (timeDiff > 15) {
        status = 'delayed';
        locationStatus = 'at_risk';
      }

      return {
        visitId: assignment.visitId,
        carerId: assignment.carerId,
        scheduledTime,
        estimatedEndTime: assignment.estimatedEndTime,
        status,
        locationStatus,
        predictedLateness: timeDiff > 0 ? Math.floor(timeDiff) : undefined
      };
    });
  }

  private async getRecentIncidents(tenantId: string): Promise<LiveIncident[]> {
    const incidents = await this.prisma.incident.findMany({
      where: {
        tenantId,
        reportedAt: {
          gte: new Date(Date.now() - 24 * 60 * 60 * 1000) // Last 24 hours
        }
      },
      orderBy: {
        reportedAt: 'desc'
      },
      take: 10
    });

    return incidents.map(incident => ({
      id: incident.id,
      type: incident.type,
      severity: incident.severity,
      title: incident.title,
      description: incident.description,
      visitId: incident.visitId || undefined,
      carerId: incident.carerId || undefined,
      clientId: incident.clientId || undefined,
      reportedAt: incident.reportedAt,
      status: incident.status,
      assignedTo: incident.acknowledgedBy || undefined
    }));
  }

  private async predictSingleLateness(assignment: any): Promise<any> {
    // Simplified prediction logic
    // In production, this would use ML model with features like:
    // - Current traffic conditions
    // - Carer's historical punctuality
    // - Distance to travel
    // - Time of day
    // - Weather conditions

    const now = new Date();
    const scheduledTime = new Date(assignment.scheduledTime);
    const timeUntilVisit = (scheduledTime.getTime() - now.getTime()) / (1000 * 60);

    let predictedLateness = 0;
    let confidence = 0.5;
    const reasons: string[] = [];

    // Simple heuristics
    if (timeUntilVisit < 30) {
      // Check if carer has current assignment that might run over
      const currentAssignment = await this.prisma.assignment.findFirst({
        where: {
          carerId: assignment.carerId,
          scheduledTime: {
            lt: now
          },
          estimatedEndTime: {
            gt: now
          },
          status: { in: ['ACCEPTED', 'COMPLETED'] }
        }
      });

      if (currentAssignment) {
        const potentialOverrun = (new Date(currentAssignment.estimatedEndTime).getTime() - now.getTime()) / (1000 * 60);
        if (potentialOverrun > 15) {
          predictedLateness = Math.max(predictedLateness, potentialOverrun);
          reasons.push('Previous visit running long');
          confidence = 0.7;
        }
      }
    }

    // Check distance if locations available
    if (assignment.carer.latitude && assignment.carer.longitude && 
        assignment.visit.latitude && assignment.visit.longitude) {
      const distance = this.calculateDistance(
        assignment.carer.latitude,
        assignment.carer.longitude,
        assignment.visit.latitude!,
        assignment.visit.longitude!
      );

      const travelTimeEstimate = distance / 500; // 500m per minute
      if (travelTimeEstimate > 30) { // More than 30 minutes travel
        predictedLateness = Math.max(predictedLateness, travelTimeEstimate - 30);
        reasons.push('Long travel distance');
        confidence = 0.6;
      }
    }

    return {
      visitId: assignment.visitId,
      carerId: assignment.carerId,
      scheduledTime,
      predictedLateness: Math.floor(predictedLateness),
      confidence,
      reasons
    };
  }

  private determineLatenessSeverity(delayMinutes: number): 'low' | 'medium' | 'high' | 'critical' {
    if (delayMinutes <= 15) return 'low';
    if (delayMinutes <= 30) return 'medium';
    if (delayMinutes <= 60) return 'high';
    return 'critical';
  }

  /**
   * Suggest swap options for delayed visits
   */
  async suggestSwaps(visitId: string, delayMinutes: number): Promise<Array<{
    carerId: string;
    visitId: string;
    score: number;
    reasons: string[];
  }>> {
    try {
      // Get the delayed visit
      const visit = await this.prisma.externalRequest.findUnique({
        where: { id: visitId },
        include: {
          assignments: {
            include: {
              carer: true
            }
          }
        }
      });

      if (!visit || !visit.assignments[0]) {
        throw new Error('Visit or assignment not found');
      }

      const currentCarer = visit.assignments[0].carer;
      const scheduledTime = visit.scheduledStartTime;

      // Find available carers who could take over
      const availableCarers = await this.prisma.carer.findMany({
        where: {
          tenantId: visit.tenantId,
          isActive: true,
          id: { not: currentCarer.id }
        },
        include: {
          assignments: {
            where: {
              scheduledTime: {
                gte: new Date((scheduledTime || new Date()).getTime() - delayMinutes * 60000),
                lte: new Date((scheduledTime || new Date()).getTime() + delayMinutes * 60000)
              }
            }
          }
        }
      });

      const suggestions = [];

      for (const carer of availableCarers) {
        // Check if carer has conflicting assignments
        const hasConflict = carer.assignments.some(assignment => {
          const assignmentTime = new Date(assignment.scheduledTime);
          const timeDiff = Math.abs(assignmentTime.getTime() - (scheduledTime || new Date()).getTime()) / (1000 * 60);
          return timeDiff < 30; // Within 30 minutes
        });

        if (!hasConflict) {
          let score = 0;
          const reasons: string[] = [];

          // Calculate distance if locations available
          if (carer.latitude && carer.longitude && visit.latitude && visit.longitude) {
            const distance = this.calculateDistance(
              carer.latitude,
              carer.longitude,
              visit.latitude,
              visit.longitude
            );

            if (distance < 5000) { // Within 5km
              score += 20;
              reasons.push('Close proximity');
            }
          }

          // Check skills match
          if (carer.skills && visit.requirements) {
            const skillsMatch = carer.skills.some(skill =>
              (visit.requirements || '').toLowerCase().includes(skill.toLowerCase())
            );
            if (skillsMatch) {
              score += 30;
              reasons.push('Skills match');
            }
          }

          // Check availability
          if (carer.assignments.length === 0) {
            score += 25;
            reasons.push('Fully available');
          }

          if (score > 0) {
            suggestions.push({
              carerId: carer.id,
              visitId,
              score,
              reasons
            });
          }
        }
      }

      // Sort by score descending
      return suggestions.sort((a, b) => b.score - a.score);

    } catch (error) {
      logger.error('Failed to suggest swaps:', error);
      throw error;
    }
  }
}