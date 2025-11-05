// rostering/src/types/rostering.ts
import { Roster, Assignment, ExternalRequest, Carer } from '@prisma/client';

// Roster-related interfaces
export interface RosterWithAssignments extends Roster {
  assignments: Array<{
    id: string;
    status: string;
    warnings: string[];
  }>;
}

export interface VisitWithAssignments extends ExternalRequest {
  assignments: Array<{
    carerId: string;
    carer?: {
      firstName: string;
      lastName: string;
    };
  }>;
}

export interface VisitWithFullDetails extends ExternalRequest {
  assignments: Array<{
    carerId: string;
    carer: {
      id: string;
      firstName: string;
      lastName: string;
    };
  }>;
  matches: Array<{
    carerId: string;
  }>;
}

// ... rest of your types

export interface OptimizationStatus {
  activeRosters: number;
  totalAssignments: number;
  warningCount: number;
  lastOptimized: Date | null;
}

export interface ContinuityReport {
  dateFrom: Date;
  dateTo: Date;
  totalClients: number;
  averageContinuityScore: number;
  clients: Array<{
    clientId: string;
    totalVisits: number;
    continuityScore: number;
    differentCarers: number;
  }>;
}

export interface ClientContinuity {
  clientId: string;
  totalVisits: number;
  continuityScore: number;
  mostFrequentCarer: {
    carerId: string;
    visitCount: number;
    percentage: number;
  } | null;
  carerDistribution: Array<{
    carerId: string;
    visitCount: number;
    percentage: number;
  }>;
}

export interface LiveRosterStatus {
  rosterId: string;
  totalAssignments: number;
  completed: number;
  inProgress: number;
  upcoming: number;
  delayed: number;
  completionRate: number;
  onTimeRate: number;
}

// Request/Response types for roster endpoints
export interface GenerateRosterRequest {
  clusterId?: string;
  startDate: string;
  endDate: string;
  strategy?: 'continuity' | 'travel' | 'balanced';
  generateScenarios?: boolean;
}

export interface PublishRosterRequest {
  notificationChannels?: Array<'push' | 'sms' | 'email'>;
  acceptanceDeadlineMinutes?: number;
  versionLabel?: string;
}

export interface EmergencyVisitRequest {
  clientId: string;
  address: string;
  postcode?: string;
  urgency?: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  scheduledStartTime: string;
  estimatedDuration?: number;
  requirements?: string;
}

export interface CarerUnavailableRequest {
  carerId: string;
  reason: string;
  affectedDate: string;
}

export interface SwapAssignmentsRequest {
  assignmentIdA: string;
  assignmentIdB: string;
}

export interface ReassignVisitRequest {
  assignmentId: string;
  newCarerId: string;
  reason?: string;
}

export interface BulkUpdateRequest {
  updates: Array<{
    assignmentId: string;
    carerId?: string;
    scheduledTime?: string;
  }>;
}

export interface ManualChangeValidation {
  isValid: boolean;
  hardBlocks: string[];
  softWarnings: string[];
}