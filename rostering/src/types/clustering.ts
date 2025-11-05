//C:\Users\CPT-003\Desktop\CRM\crm_apis_microservices\rostering\src\types\clustering.ts
import { ExternalRequest } from '@prisma/client';

export interface ClusterVisit extends ExternalRequest {
  timeStartMinutes: number;
  timeEndMinutes: number;
  dayOfWeek: number;
  eligibleCarers: string[];
}

export interface ClusterMetrics {
  totalVisits: number;
  totalDuration: number;
  totalTravelTime?: number;
  averageTravel: number;
  averageDistance?: number;
  skillCoverage: number;
  continuityRisk: number;
  schedulabilityScore?: number;
  suggestedCarers: string[];
}

export interface ClusterResult {
  id: string;
  name: string;
  centroid: { latitude: number; longitude: number };
  visits: ClusterVisit[];
  metrics: ClusterMetrics;
  suggestedCarers: string[];
}

export interface ClusteringParams {
  dateRange: {
    start: Date;
    end: Date;
  };
  maxTravelTime?: number;
  timeWindowTolerance?: number;
  minClusterSize?: number;
  maxClusterSize?: number;
  epsilon?: number;
  minPoints?: number;
}