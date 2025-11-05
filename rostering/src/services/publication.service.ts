// src/services/publication.service.ts
import { PrismaClient, PublicationStatus, AcceptanceStatus } from '@prisma/client';
import { NotificationService } from './notification.service';
import { logger } from '../utils/logger';
import { WebSocketService } from './websocket.service';

export interface RosterPublication {
  id: string;
  rosterId: string;
  tenantId: string;
  versionLabel: string;
  publishedAt: Date;
  publishedBy: string;
  acceptanceDeadline: Date;
  notificationChannels: string[];
  status: PublicationStatus;
  
  assignments: PublishedAssignment[];
  acceptanceStats: {
    total: number;
    accepted: number;
    declined: number;
    pending: number;
    expired: number;
  };
}

export interface PublishedAssignment {
  id: string;
  publicationId: string;
  assignmentId: string;
  carerId: string;
  carerName: string;
  scheduledTime: Date;
  estimatedEndTime: Date;
  
  visitDetails: {
    clientName: string;
    address: string;
    duration: number;
    requirements: string;
  };
  
  status: AcceptanceStatus;
  acceptedAt?: Date;
  declinedAt?: Date;
  declineReason?: string;
  notificationSentAt?: Date;
  escalatedAt?: Date;
  responseTime?: number; // seconds
}

export class PublicationService {
  constructor(
    private prisma: PrismaClient,
    private notificationService: NotificationService,
    private websocketService?: WebSocketService
  ) {}

  /**
   * Publish roster to carers with full acceptance workflow
   */
  async publishRoster(
    tenantId: string,
    rosterId: string,
    publishedBy: string,
    options: {
      versionLabel?: string;
      notificationChannels?: string[];
      acceptanceDeadlineMinutes?: number;
      notes?: string;
    } = {}
  ): Promise<RosterPublication> {
    try {
      logger.info(`Publishing roster ${rosterId}`, { tenantId, publishedBy });

      // Fetch roster with assignments and related data
      const roster = await this.fetchRosterForPublication(tenantId, rosterId);
      
      if (!roster) {
        throw new Error('Roster not found');
      }

      if (roster.status !== 'DRAFT' && roster.status !== 'PENDING_APPROVAL') {
        throw new Error(`Cannot publish roster with status: ${roster.status}`);
      }

      // Create publication record
      const publication = await this.createPublicationRecord(
        tenantId,
        rosterId,
        publishedBy,
        options
      );

      // Create published assignments
      const publishedAssignments = await this.createPublishedAssignments(
        publication.id,
        roster.assignments
      );

      // Update roster status
      await this.prisma.roster.update({
        where: { id: rosterId },
        data: {
          status: 'PUBLISHED',
          publishedAt: new Date(),
          updatedAt: new Date()
        }
      });

      // Send notifications to carers
      await this.sendPublicationNotifications(
        tenantId,
        publishedAssignments,
        options.notificationChannels || ['push', 'sms', 'email']
      );

      // Start escalation timer
      this.scheduleEscalation(publication.id, options.acceptanceDeadlineMinutes || 30);

      // Broadcast via WebSocket
      if (this.websocketService) {
        this.websocketService.broadcastRosterPublished(tenantId, publication);
      }

      // Calculate stats
      const acceptanceStats = this.calculateAcceptanceStats(publishedAssignments);

      logger.info(`Roster published successfully`, {
        publicationId: publication.id,
        assignments: publishedAssignments.length,
        deadline: publication.acceptanceDeadline
      });

      return {
        ...publication,
        assignments: publishedAssignments,
        acceptanceStats
      };

    } catch (error) {
      logger.error('Failed to publish roster:', error);
      throw error;
    }
  }

  /**
   * Get publication status with real-time updates
   */
  async getPublicationStatus(publicationId: string): Promise<RosterPublication> {
    try {
      const publication = await this.prisma.rosterPublication.findUnique({
        where: { id: publicationId },
        include: {
          publishedAssignments: {
            include: {
              assignment: {
                include: {
                  visit: {
                    select: {
                      requestorName: true,
                      address: true,
                      estimatedDuration: true,
                      requirements: true
                    }
                  },
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
        }
      });

      if (!publication) {
        throw new Error('Publication not found');
      }

      const assignments = publication.publishedAssignments.map(pa => ({
        id: pa.id,
        publicationId: pa.publicationId,
        assignmentId: pa.assignmentId,
        carerId: pa.carerId,
        carerName: `${pa.assignment.carer.firstName} ${pa.assignment.carer.lastName}`,
        scheduledTime: pa.assignment.scheduledTime,
        estimatedEndTime: pa.assignment.estimatedEndTime,
        visitDetails: {
          clientName: pa.assignment.visit.requestorName || 'Unknown',
          address: pa.assignment.visit.address,
          duration: pa.assignment.visit.estimatedDuration || 60,
          requirements: pa.assignment.visit.requirements || 'General care'
        },
        status: pa.status,
        acceptedAt: pa.acceptedAt || undefined,
        declinedAt: pa.declinedAt || undefined,
        declineReason: pa.declineReason || undefined,
        notificationSentAt: pa.notificationSentAt || undefined,
        escalatedAt: pa.escalatedAt || undefined,
        responseTime: pa.responseTime || undefined
      }));

      const acceptanceStats = this.calculateAcceptanceStats(assignments);

      return {
        id: publication.id,
        rosterId: publication.rosterId,
        tenantId: publication.tenantId,
        versionLabel: publication.versionLabel,
        publishedAt: publication.publishedAt,
        publishedBy: publication.publishedBy,
        acceptanceDeadline: publication.acceptanceDeadline,
        notificationChannels: publication.notificationChannels,
        status: publication.status,
        assignments,
        acceptanceStats
      };

    } catch (error) {
      logger.error('Failed to get publication status:', error);
      throw error;
    }
  }

  /**
   * Record carer acceptance
   */
  async acceptAssignment(
    tenantId: string,
    assignmentId: string,
    carerId: string,
    acceptedBy?: string
  ): Promise<PublishedAssignment> {
    try {
      logger.info(`Carer ${carerId} accepting assignment ${assignmentId}`);

      const publishedAssignment = await this.prisma.publishedAssignment.findFirst({
        where: {
          assignmentId,
          carerId,
          publication: {
            tenantId
          }
        },
        include: {
          assignment: {
            include: {
              visit: true,
              carer: true
            }
          }
        }
      });

      if (!publishedAssignment) {
        throw new Error('Published assignment not found');
      }

      if (publishedAssignment.status !== 'PENDING') {
        throw new Error(`Assignment already ${publishedAssignment.status.toLowerCase()}`);
      }

      // Calculate response time
      const responseTime = publishedAssignment.notificationSentAt 
        ? Math.floor((Date.now() - publishedAssignment.notificationSentAt.getTime()) / 1000)
        : undefined;

      // Update assignment status
      const updated = await this.prisma.publishedAssignment.update({
        where: { id: publishedAssignment.id },
        data: {
          status: 'ACCEPTED',
          acceptedAt: new Date(),
          acceptedBy: acceptedBy || carerId,
          responseTime,
          updatedAt: new Date()
        },
        include: {
          assignment: {
            include: {
              visit: {
                select: {
                  requestorName: true,
                  address: true,
                  estimatedDuration: true,
                  requirements: true
                }
              },
              carer: {
                select: {
                  firstName: true,
                  lastName: true
                }
              }
            }
          }
        }
      });

      // Update original assignment status
      await this.prisma.assignment.update({
        where: { id: assignmentId },
        data: {
          status: 'ACCEPTED',
          acceptedAt: new Date(),
          updatedAt: new Date()
        }
      });

      // Update publication stats
      await this.updatePublicationStats(updated.publicationId);

      // Notify coordinator
      await this.notificationService.sendNotification({
        event_type: 'assignment_accepted',
        recipient_type: 'push',
        recipient: 'coordinator', // Would get actual coordinator ID
        tenant_id: tenantId,
        data: {
          assignmentId,
          carerId,
          carerName: `${updated.assignment.carer.firstName} ${updated.assignment.carer.lastName}`,
          clientName: updated.assignment.visit.requestorName,
          scheduledTime: updated.assignment.scheduledTime,
          responseTime,
          message: 'Carer has accepted assignment'
        }
      });

      // Broadcast via WebSocket
      if (this.websocketService) {
        this.websocketService.broadcastAssignmentAccepted(tenantId, updated);
      }

      logger.info(`Assignment accepted`, {
        assignmentId,
        carerId,
        responseTime
      });

      return this.mapToPublishedAssignment(updated);

    } catch (error) {
      logger.error('Failed to accept assignment:', error);
      throw error;
    }
  }

  /**
   * Record carer decline with reason
   */
  async declineAssignment(
    tenantId: string,
    assignmentId: string,
    carerId: string,
    reason?: string
  ): Promise<PublishedAssignment> {
    try {
      logger.info(`Carer ${carerId} declining assignment ${assignmentId}`, { reason });

      const publishedAssignment = await this.prisma.publishedAssignment.findFirst({
        where: {
          assignmentId,
          carerId,
          publication: {
            tenantId
          }
        },
        include: {
          assignment: {
            include: {
              visit: true,
              carer: true
            }
          }
        }
      });

      if (!publishedAssignment) {
        throw new Error('Published assignment not found');
      }

      if (publishedAssignment.status !== 'PENDING') {
        throw new Error(`Assignment already ${publishedAssignment.status.toLowerCase()}`);
      }

      // Update assignment status
      const updated = await this.prisma.publishedAssignment.update({
        where: { id: publishedAssignment.id },
        data: {
          status: 'DECLINED',
          declinedAt: new Date(),
          declineReason: reason,
          updatedAt: new Date()
        },
        include: {
          assignment: {
            include: {
              visit: {
                select: {
                  requestorName: true,
                  address: true,
                  estimatedDuration: true,
                  requirements: true
                }
              },
              carer: {
                select: {
                  firstName: true,
                  lastName: true
                }
              }
            }
          }
        }
      });

      // Update publication stats
      await this.updatePublicationStats(updated.publicationId);

      // Trigger escalation immediately
      await this.escalateAssignment(tenantId, publishedAssignment.id);

      // Broadcast via WebSocket
      if (this.websocketService) {
        this.websocketService.broadcastAssignmentDeclined(tenantId, updated, reason);
      }

      logger.info(`Assignment declined`, {
        assignmentId,
        carerId,
        reason
      });

      return this.mapToPublishedAssignment(updated);

    } catch (error) {
      logger.error('Failed to decline assignment:', error);
      throw error;
    }
  }

  /**
   * Get assignments pending acceptance for a carer
   */
  async getPendingAssignmentsForCarer(
    tenantId: string,
    carerId: string
  ): Promise<PublishedAssignment[]> {
    try {
      const assignments = await this.prisma.publishedAssignment.findMany({
        where: {
          carerId,
          status: 'PENDING',
          publication: {
            tenantId,
            status: 'ACTIVE'
          }
        },
        include: {
          assignment: {
            include: {
              visit: {
                select: {
                  requestorName: true,
                  address: true,
                  estimatedDuration: true,
                  requirements: true
                }
              },
              carer: {
                select: {
                  firstName: true,
                  lastName: true
                }
              }
            }
          }
        },
        orderBy: {
          assignment: {
            scheduledTime: 'asc'
          }
        }
      });

      return assignments.map(this.mapToPublishedAssignment);
    } catch (error) {
      logger.error('Failed to get pending assignments:', error);
      throw error;
    }
  }

  /**
   * Manual escalation for assignments
   */
  async manuallyEscalateAssignment(
    assignmentId: string,
    escalatedBy: string
  ): Promise<void> {
    try {
      await this.escalateAssignment('tenantId', assignmentId, escalatedBy);
    } catch (error) {
      logger.error('Failed to manually escalate assignment:', error);
      throw error;
    }
  }

  // ========== PRIVATE METHODS ==========

  private async fetchRosterForPublication(tenantId: string, rosterId: string) {
    return await this.prisma.roster.findUnique({
      where: {
        id: rosterId,
        tenantId
      },
      include: {
        assignments: {
          where: {
            status: { in: ['PENDING', 'OFFERED'] }
          },
          include: {
            visit: {
              select: {
                requestorName: true,
                address: true,
                estimatedDuration: true,
                requirements: true
              }
            },
            carer: {
              select: {
                id: true,
                firstName: true,
                lastName: true,
                email: true,
                phone: true
              }
            }
          }
        }
      }
    });
  }

  private async createPublicationRecord(
    tenantId: string,
    rosterId: string,
    publishedBy: string,
    options: any
  ) {
    const versionLabel = options.versionLabel || 
      `Roster-${rosterId.slice(-8)}-${new Date().toISOString().slice(0, 10)}`;
    
    const deadlineMinutes = options.acceptanceDeadlineMinutes || 30;
    const acceptanceDeadline = new Date(Date.now() + deadlineMinutes * 60000);

    return await this.prisma.rosterPublication.create({
      data: {
        tenantId,
        rosterId,
        versionLabel,
        publishedBy,
        publishedAt: new Date(),
        acceptanceDeadline,
        notificationChannels: options.notificationChannels || ['push'],
        status: 'ACTIVE',
        notes: options.notes,
        totalAssignments: 0, // Will be updated after assignments are created
        metadata: {
          publishedByUser: publishedBy,
          originalRosterId: rosterId,
          acceptanceDeadlineMinutes: deadlineMinutes
        }
      }
    });
  }

  private async createPublishedAssignments(
    publicationId: string,
    assignments: any[]
  ): Promise<PublishedAssignment[]> {
    const publishedAssignments = await this.prisma.$transaction(
      assignments.map(assignment =>
        this.prisma.publishedAssignment.create({
          data: {
            publicationId,
            assignmentId: assignment.id,
            carerId: assignment.carerId,
            notificationSentAt: new Date(),
            status: 'PENDING'
          },
          include: {
            assignment: {
              include: {
                visit: {
                  select: {
                    requestorName: true,
                    address: true,
                    estimatedDuration: true,
                    requirements: true
                  }
                },
                carer: {
                  select: {
                    firstName: true,
                    lastName: true
                  }
                }
              }
            }
          }
        })
      )
    );

    // Update total assignments count
    await this.prisma.rosterPublication.update({
      where: { id: publicationId },
      data: {
        totalAssignments: publishedAssignments.length,
        pendingCount: publishedAssignments.length
      }
    });

    return publishedAssignments.map(this.mapToPublishedAssignment);
  }

  private async sendPublicationNotifications(
    tenantId: string,
    assignments: PublishedAssignment[],
    channels: string[]
  ): Promise<void> {
    try {
      const notifications = assignments.map(assignment => ({
        event_type: 'new_shift_assignment',
        recipient_type: 'push' as const,
        recipient: assignment.carerId,
        tenant_id: tenantId,
        data: {
          assignmentId: assignment.id,
          publicationId: assignment.publicationId,
          actionUrl: `/accept-assignment/${assignment.id}`,
          clientName: assignment.visitDetails.clientName,
          scheduledTime: assignment.scheduledTime,
          address: assignment.visitDetails.address,
          duration: assignment.visitDetails.duration,
          deadline: new Date(Date.now() + 30 * 60000), // 30 minutes from now
          message: `New visit: ${assignment.visitDetails.clientName} at ${assignment.scheduledTime.toLocaleString()}`
        }
      }));

      await Promise.all(
        notifications.map(notification =>
          this.notificationService.sendNotification(notification)
        )
      );

      logger.info(`Sent ${notifications.length} notifications`);

    } catch (error) {
      logger.error('Failed to send notifications:', error);
      // Don't throw - publication should succeed even if notifications fail
    }
  }

  private async escalateAssignment(
    tenantId: string,
    publishedAssignmentId: string,
    escalatedBy: string = 'system'
  ): Promise<void> {
    try {
      logger.info(`Escalating assignment ${publishedAssignmentId}`);

      const publishedAssignment = await this.prisma.publishedAssignment.findUnique({
        where: { id: publishedAssignmentId },
        include: {
          assignment: {
            include: {
              visit: true,
              carer: true
            }
          },
          publication: true
        }
      });

      if (!publishedAssignment) {
        throw new Error('Published assignment not found');
      }

      // Find next-best eligible carers
      const eligibleCarers = await this.findEligibleAlternateCarers(
        tenantId,
        publishedAssignment.assignment.visitId,
        publishedAssignment.carerId
      );

      if (eligibleCarers.length > 0) {
        // Offer to the best alternate
        const bestAlternate = eligibleCarers[0];
        
        // Create new published assignment for alternate
        const newPublishedAssignment = await this.prisma.publishedAssignment.create({
          data: {
            publicationId: publishedAssignment.publicationId,
            assignmentId: publishedAssignment.assignmentId,
            carerId: bestAlternate.id,
            status: 'PENDING',
            notificationSentAt: new Date(),
            escalatedAt: new Date(),
            escalatedTo: [bestAlternate.id],
            escalationCount: 1
          }
        });

        // Send notification to alternate
        await this.notificationService.sendNotification({
          event_type: 'escalated_shift_assignment',
          recipient_type: 'push',
          recipient: bestAlternate.id,
          tenant_id: tenantId,
          data: {
            assignmentId: newPublishedAssignment.id,
            originalCarerId: publishedAssignment.carerId,
            clientName: publishedAssignment.assignment.visit.requestorName,
            scheduledTime: publishedAssignment.assignment.scheduledTime,
            message: 'Urgent: Shift reassigned to you'
          }
        });

        logger.info(`Assignment escalated to alternate carer`, {
          originalAssignment: publishedAssignmentId,
          newCarer: bestAlternate.id,
          carerName: `${bestAlternate.firstName} ${bestAlternate.lastName}`
        });

      } else {
        // No alternates found, notify coordinator
        await this.notificationService.sendNotification({
          event_type: 'assignment_escalation_failed',
          recipient_type: 'push',
          recipient: 'coordinator',
          tenant_id: tenantId,
          data: {
            assignmentId: publishedAssignmentId,
            visitId: publishedAssignment.assignment.visitId,
            clientName: publishedAssignment.assignment.visit.requestorName,
            scheduledTime: publishedAssignment.assignment.scheduledTime,
            message: 'No eligible alternate carers found for escalated assignment'
          }
        });

        logger.warn(`No eligible alternate carers found for assignment`, {
          assignmentId: publishedAssignmentId
        });
      }

      // Mark original as escalated
      await this.prisma.publishedAssignment.update({
        where: { id: publishedAssignmentId },
        data: {
          status: 'ESCALATED',
          escalatedAt: new Date(),
          updatedAt: new Date()
        }
      });

    } catch (error) {
      logger.error('Failed to escalate assignment:', error);
    }
  }

  private async findEligibleAlternateCarers(
    tenantId: string,
    visitId: string,
    excludedCarerId: string
  ) {
    // This would use your existing eligibility service
    // For now, return a simplified version
    return await this.prisma.carer.findMany({
      where: {
        tenantId,
        isActive: true,
        id: { not: excludedCarerId },
        // Add more eligibility criteria based on skills, availability, etc.
      },
      take: 5,
      orderBy: {
        // Order by some criteria like proximity, skills match, etc.
        createdAt: 'desc'
      }
    });
  }

  private scheduleEscalation(publicationId: string, deadlineMinutes: number): void {
    setTimeout(async () => {
      try {
        logger.info(`Checking for expired assignments in publication ${publicationId}`);
        
        const expiredAssignments = await this.prisma.publishedAssignment.findMany({
          where: {
            publicationId,
            status: 'PENDING',
            notificationSentAt: {
              lt: new Date(Date.now() - deadlineMinutes * 60000)
            }
          }
        });

        for (const assignment of expiredAssignments) {
          await this.prisma.publishedAssignment.update({
            where: { id: assignment.id },
            data: {
              status: 'EXPIRED',
              expiredAt: new Date(),
              updatedAt: new Date()
            }
          });

          // Escalate expired assignments
          await this.escalateAssignment('system', assignment.id);
        }

        // Update publication stats
        await this.updatePublicationStats(publicationId);

        logger.info(`Processed ${expiredAssignments.length} expired assignments`);

      } catch (error) {
        logger.error('Escalation timer failed:', error);
      }
    }, deadlineMinutes * 60 * 1000);
  }

  private async updatePublicationStats(publicationId: string): Promise<void> {
    const stats = await this.prisma.publishedAssignment.groupBy({
      by: ['status'],
      where: { publicationId },
      _count: true
    });

    const counts = {
      ACCEPTED: 0,
      DECLINED: 0,
      PENDING: 0,
      EXPIRED: 0,
      ESCALATED: 0
    };

    stats.forEach(stat => {
      counts[stat.status as keyof typeof counts] = stat._count;
    });

    await this.prisma.rosterPublication.update({
      where: { id: publicationId },
      data: {
        acceptedCount: counts.ACCEPTED,
        declinedCount: counts.DECLINED,
        pendingCount: counts.PENDING,
        expiredCount: counts.EXPIRED,
        updatedAt: new Date()
      }
    });
  }

  private calculateAcceptanceStats(assignments: PublishedAssignment[]): RosterPublication['acceptanceStats'] {
    const statusCounts = assignments.reduce((acc, assignment) => {
      acc[assignment.status] = (acc[assignment.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      total: assignments.length,
      accepted: statusCounts.ACCEPTED || 0,
      declined: statusCounts.DECLINED || 0,
      pending: statusCounts.PENDING || 0,
      expired: statusCounts.EXPIRED || 0
    };
  }

  private mapToPublishedAssignment(dbAssignment: any): PublishedAssignment {
    return {
      id: dbAssignment.id,
      publicationId: dbAssignment.publicationId,
      assignmentId: dbAssignment.assignmentId,
      carerId: dbAssignment.carerId,
      carerName: `${dbAssignment.assignment.carer.firstName} ${dbAssignment.assignment.carer.lastName}`,
      scheduledTime: dbAssignment.assignment.scheduledTime,
      estimatedEndTime: dbAssignment.assignment.estimatedEndTime,
      visitDetails: {
        clientName: dbAssignment.assignment.visit.requestorName || 'Unknown',
        address: dbAssignment.assignment.visit.address,
        duration: dbAssignment.assignment.visit.estimatedDuration || 60,
        requirements: dbAssignment.assignment.visit.requirements || 'General care'
      },
      status: dbAssignment.status,
      acceptedAt: dbAssignment.acceptedAt,
      declinedAt: dbAssignment.declinedAt,
      declineReason: dbAssignment.declineReason,
      notificationSentAt: dbAssignment.notificationSentAt,
      escalatedAt: dbAssignment.escalatedAt,
      responseTime: dbAssignment.responseTime
    };
  }
}