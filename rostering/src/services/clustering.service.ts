import { PrismaClient, RequestStatus, ExternalRequest } from '../types/prisma';
import { ConstraintsService, RosteringConstraints } from './constraints.service';
import { TravelService, TravelResult } from './travel.service';
import { logger } from '../utils/logger';

export interface ClusterVisit extends ExternalRequest {
  timeStartMinutes: number;
  timeEndMinutes: number;
  dayOfWeek: number;
  eligibleCarers: string[];
  latitude: number | null;
  longitude: number | null;
  postcode: string | null;
  requirements: string | null;
  estimatedDuration: number | null;
  visitType?: 'single' | 'double';
  matches?: {
    response: string;
    carerId: string;
  }[];
}

export interface ClusterResult {
  id: string;
  name: string;
  centroid: { latitude: number; longitude: number };
  visits: ClusterVisit[];
  metrics: {
    totalVisits: number;
    totalDuration: number;
    averageTravel: number;
    skillCoverage: number;
    continuityRisk: number;
    suggestedCarers: string[];
    carerFitScore?: number; // Added for optimization
  };
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
  epsilon?: number; // DBSCAN parameter
  minPoints?: number; // DBSCAN parameter
  enableOptimization?: boolean; // Added for optimization
}

// ========== OPTIMIZATION INTERFACES ==========
export interface ClusterQualityMetrics {
  geographicCompactness: number;    // Lower = better (meters variance)
  timeWindowCohesion: number;       // Higher = better (0-100 score)
  carerFitScore: number;            // Higher = better (0-100 score)
  workloadBalance: number;          // Higher = better (0-100 score)
  continuityScore: number;          // Higher = better (0-100 score)
  overallScore: number;             // Composite score (0-100)
}

export interface OptimizationResult {
  clusters: ClusterResult[];
  metrics: {
    before: ClusterQualityMetrics;
    after: ClusterQualityMetrics;
    improvements: {
      geographicCompactness: number;
      timeWindowCohesion: number;
      carerFitScore: number;
      workloadBalance: number;
    };
  };
  actions: {
    clustersSplit: number;
    clustersMerged: number;
    outliersRemoved: number;
    visitsReassigned: number;
  };
}
// ========== END OPTIMIZATION INTERFACES ==========

export class ClusteringService {
  constructor(
    private prisma: PrismaClient,
    private constraintsService: ConstraintsService,
    private travelService: TravelService
  ) {}

  /**
   * Generate AI-powered clusters using DBSCAN algorithm with optional optimization
   */
  async generateClusters(tenantId: string, params: ClusteringParams): Promise<ClusterResult[]> {
    try {
      logger.info(`Generating clusters for tenant ${tenantId}`, { params });

      // Get active constraints
      const constraints = await this.constraintsService.getActiveConstraints(tenantId);

      // Get approved requests within date range
      const visits = await this.getVisitsForClustering(tenantId, params);
      
      if (visits.length === 0) {
        logger.info('No visits found for clustering');
        return [];
      }

      // Pre-compute eligible carers for each visit
      const visitsWithEligibility = await this.preComputeEligibility(visits);

      // Convert visits to feature vectors for DBSCAN
      const featureVectors = this.createFeatureVectors(visitsWithEligibility);

      // Run DBSCAN clustering
      const clusters = await this.runDBSCAN(
        featureVectors, 
        visitsWithEligibility, 
        params,
        constraints
      );

      // Calculate cluster metrics
      let clustersWithMetrics = await this.calculateClusterMetrics(clusters, constraints);

      // Apply optimization if enabled
      if (params.enableOptimization) {
        clustersWithMetrics = await this.optimizeClusters(clustersWithMetrics, params, tenantId);
      }

      logger.info(`Generated ${clustersWithMetrics.length} clusters`);
      return clustersWithMetrics;

    } catch (error) {
      logger.error('Failed to generate clusters:', error);
      throw error;
    }
  }

  /**
   * NEW: Generate optimized clusters with detailed metrics
   */
/**
 * NEW: Generate optimized clusters with detailed metrics - FIXED VERSION
 */
public async generateOptimizedClusters(
  tenantId: string, 
  params: ClusteringParams
): Promise<OptimizationResult> {
  try {
    logger.info(`Generating optimized clusters for tenant ${tenantId}`, { params });

    // Generate initial clusters without optimization
    const rawParams = { ...params, enableOptimization: false };
    const rawClusters = await this.generateClusters(tenantId, rawParams);
    
    if (rawClusters.length === 0) {
      // Return proper structure with empty metrics
      const emptyMetrics = this.getEmptyMetrics();
      return {
        clusters: [],
        metrics: {
          before: emptyMetrics,
          after: emptyMetrics,
          improvements: {
            geographicCompactness: 0,
            timeWindowCohesion: 0,
            carerFitScore: 0,
            workloadBalance: 0
          }
        },
        actions: { clustersSplit: 0, clustersMerged: 0, outliersRemoved: 0, visitsReassigned: 0 }
      };
    }

    // Calculate initial metrics
    const initialMetrics = this.calculateOverallQualityMetrics(rawClusters);

    // Apply optimization
    const optimizedClusters = await this.optimizeClusters(rawClusters, params, tenantId);

    // Calculate final metrics
    const finalMetrics = this.calculateOverallQualityMetrics(optimizedClusters);

    // Track optimization actions
    const actions = this.calculateOptimizationActions(rawClusters, optimizedClusters);

    return {
      clusters: optimizedClusters,
      metrics: {
        before: initialMetrics,
        after: finalMetrics,
        improvements: {
          geographicCompactness: finalMetrics.geographicCompactness - initialMetrics.geographicCompactness,
          timeWindowCohesion: finalMetrics.timeWindowCohesion - initialMetrics.timeWindowCohesion,
          carerFitScore: finalMetrics.carerFitScore - initialMetrics.carerFitScore,
          workloadBalance: finalMetrics.workloadBalance - initialMetrics.workloadBalance
        }
      },
      actions
    };

  } catch (error) {
    logger.error('Failed to generate optimized clusters:', error);
    throw error;
  }
}

  // ========== OPTIMIZATION METHODS ==========

  /**
   * Main optimization pipeline
   */
  private async optimizeClusters(
    clusters: ClusterResult[], 
    params: ClusteringParams,
    tenantId: string
  ): Promise<ClusterResult[]> {
    let optimizedClusters = [...clusters];
    
    // Optimization pipeline
    optimizedClusters = await this.sizeOptimization(optimizedClusters, params);
    optimizedClusters = await this.geographicOptimization(optimizedClusters);
    optimizedClusters = await this.timeWindowOptimization(optimizedClusters);
    optimizedClusters = await this.carerMatchingOptimization(optimizedClusters, tenantId);

    return optimizedClusters;
  }

  /**
   * SIZE OPTIMIZATION: Split oversized and merge undersized clusters
   */
  private async sizeOptimization(
    clusters: ClusterResult[], 
    params: ClusteringParams
  ): Promise<ClusterResult[]> {
    const optimized: ClusterResult[] = [];
    const minSize = params.minClusterSize || 2;
    const maxSize = params.maxClusterSize || 8;

    for (const cluster of clusters) {
      const clusterSize = cluster.visits.length;

      if (clusterSize > maxSize) {
        // Split oversized cluster
        const splitClusters = await this.splitOversizedCluster(cluster, maxSize);
        optimized.push(...splitClusters);
      } else if (clusterSize < minSize) {
        // Try to merge with nearby small clusters
        const merged = await this.mergeUndersizedCluster(cluster, clusters, minSize);
        if (merged) {
          optimized.push(merged);
        } else {
          // Keep as is if no suitable merge partner
          optimized.push(cluster);
        }
      } else {
        // Keep clusters within ideal size range
        optimized.push(cluster);
      }
    }

    return optimized;
  }

  /**
   * Split a cluster that's too large
   */
  private async splitOversizedCluster(
    cluster: ClusterResult, 
    maxSize: number
  ): Promise<ClusterResult[]> {
    const subClusters: ClusterResult[] = [];
    const visits = [...cluster.visits];

    // Sort visits by time to create time-based subgroups
    visits.sort((a, b) => a.timeStartMinutes - b.timeStartMinutes);

    // Split into subgroups of ideal size
    while (visits.length > 0) {
      const subgroup = visits.splice(0, maxSize);
      
      // If remaining visits would create too-small cluster, redistribute
      if (visits.length > 0 && visits.length < 3) {
        // Distribute remaining visits to existing subgroups
        this.distributeRemainingVisits(subClusters, visits);
        break;
      }

      if (subgroup.length >= 2) {
        const subCluster = await this.createSubCluster(cluster, subgroup);
        subClusters.push(subCluster);
      }
    }

    return subClusters;
  }

  /**
   * Merge clusters that are too small
   */
  private async mergeUndersizedCluster(
    cluster: ClusterResult,
    allClusters: ClusterResult[],
    minSize: number
  ): Promise<ClusterResult | null> {
    if (cluster.visits.length >= minSize) {
      return cluster; // No need to merge
    }

    // Find nearest cluster that's also small and compatible
    const compatibleClusters = allClusters
      .filter(c => c.id !== cluster.id && c.visits.length < minSize)
      .filter(c => this.areClustersCompatible(cluster, c));

    if (compatibleClusters.length === 0) {
      return null; // No suitable merge partner
    }

    // Find closest compatible cluster
    const closest = compatibleClusters.reduce((closest, current) => {
      const currentDistance = this.calculateClusterDistance(cluster, current);
      const closestDistance = this.calculateClusterDistance(cluster, closest);
      return currentDistance < closestDistance ? current : closest;
    });

    // Merge the clusters
    return await this.mergeClusters(cluster, closest);
  }

  /**
   * GEOGRAPHIC OPTIMIZATION: Improve spatial coherence
   */
  private async geographicOptimization(clusters: ClusterResult[]): Promise<ClusterResult[]> {
    const optimized: ClusterResult[] = [];

    for (const cluster of clusters) {
      const cleanedCluster = await this.removeGeographicOutliers(cluster);
      optimized.push(cleanedCluster);
    }

    return optimized;
  }

  /**
   * Remove visits that are geographic outliers
   */
  private async removeGeographicOutliers(cluster: ClusterResult): Promise<ClusterResult> {
    if (cluster.visits.length <= 3) {
      return cluster; // Keep small clusters intact
    }

    const distances = await this.calculateVisitDistancesFromCentroid(cluster);
    const avgDistance = distances.reduce((sum, d) => sum + d, 0) / distances.length;
    const stdDev = Math.sqrt(
      distances.reduce((sum, d) => sum + Math.pow(d - avgDistance, 2), 0) / distances.length
    );

    // Remove visits more than 2 standard deviations from centroid
    const threshold = avgDistance + (2 * stdDev);
    const filteredVisits = cluster.visits.filter((visit, index) => 
      distances[index] <= threshold
    );

    if (filteredVisits.length >= 2) {
      return await this.recalculateClusterMetrics({
        ...cluster,
        visits: filteredVisits
      });
    }

    return cluster; // Keep original if filtering would make cluster too small
  }

  /**
   * TIME WINDOW OPTIMIZATION: Ensure temporal compatibility
   */
  private async timeWindowOptimization(clusters: ClusterResult[]): Promise<ClusterResult[]> {
    const optimized: ClusterResult[] = [];

    for (const cluster of clusters) {
      const timeOptimized = await this.resolveTimeConflicts(cluster);
      optimized.push(timeOptimized);
    }

    return optimized;
  }

  /**
   * Resolve time conflicts within a cluster
   */
  private async resolveTimeConflicts(cluster: ClusterResult): Promise<ClusterResult> {
    const conflicts = this.findTimeConflicts(cluster.visits);
    
    if (conflicts.length === 0) {
      return cluster; // No conflicts to resolve
    }

    // For each conflict, move one visit to a more suitable cluster
    let resolvedVisits = [...cluster.visits];
    
    for (const conflict of conflicts) {
      const [visit1, visit2] = conflict;
      
      // Keep the visit that's closer to centroid, move the other
      const distance1 = await this.calculateDistance(
        cluster.centroid.latitude, cluster.centroid.longitude,
        visit1.latitude!, visit1.longitude!
      );
      const distance2 = await this.calculateDistance(
        cluster.centroid.latitude, cluster.centroid.longitude,
        visit2.latitude!, visit2.longitude!
      );

      const visitToMove = distance1 > distance2 ? visit1 : visit2;
      
      // Remove the visit to move from this cluster
      resolvedVisits = resolvedVisits.filter(v => v.id !== visitToMove.id);
    }

    if (resolvedVisits.length >= 2) {
      return await this.recalculateClusterMetrics({
        ...cluster,
        visits: resolvedVisits
      });
    }

    return cluster; // Keep original if resolution would break cluster
  }

  /**
   * CARER MATCHING OPTIMIZATION: Ensure adequate carer coverage
   */
  private async carerMatchingOptimization(
    clusters: ClusterResult[], 
    tenantId: string
  ): Promise<ClusterResult[]> {
    const optimized: ClusterResult[] = [];

    for (const cluster of clusters) {
      const carerOptimized = await this.optimizeCarerMatching(cluster, tenantId);
      optimized.push(carerOptimized);
    }

    return optimized;
  }

  /**
   * Optimize cluster for carer matching
   */
  private async optimizeCarerMatching(
    cluster: ClusterResult, 
    tenantId: string
  ): Promise<ClusterResult> {
    const availableCarers = await this.findAvailableCarersForCluster(cluster, tenantId);
    
    if (availableCarers.length === 0) {
      // No carers available - this cluster is problematic
      logger.warn(`No available carers found for cluster ${cluster.id}`);
      return cluster;
    }

    // Calculate carer fit score for each carer
    const carerScores = await Promise.all(
      availableCarers.map(async carer => ({
        carer,
        score: await this.calculateCarerFitScore(cluster, carer)
      }))
    );

    // Filter to carers with adequate fit
    const suitableCarers = carerScores
      .filter(cs => cs.score >= 0.7) // 70% fit threshold
      .map(cs => cs.carer.id);

    return {
      ...cluster,
      metrics: {
        ...cluster.metrics,
        suggestedCarers: suitableCarers.slice(0, 5), // Top 5 suitable carers
        carerFitScore: suitableCarers.length > 0 ? 
          Math.max(...carerScores.map(cs => cs.score)) * 100 : 0
      }
    };
  }

  // ========== QUALITY METRICS CALCULATION ==========

  
  /**
   * Calculate comprehensive quality metrics for clusters - CHANGED TO PUBLIC
   */
  public calculateOverallQualityMetrics(clusters: ClusterResult[]): ClusterQualityMetrics {
    if (clusters.length === 0) {
      return this.getEmptyMetrics();
    }

    const clusterMetrics = clusters.map(cluster => this.calculateSingleClusterMetrics(cluster));
    
    return {
      geographicCompactness: this.average(clusterMetrics.map(m => m.geographicCompactness)),
      timeWindowCohesion: this.average(clusterMetrics.map(m => m.timeWindowCohesion)),
      carerFitScore: this.average(clusterMetrics.map(m => m.carerFitScore)),
      workloadBalance: this.calculateWorkloadBalance(clusters),
      continuityScore: this.average(clusterMetrics.map(m => m.continuityScore)),
      overallScore: this.calculateOverallScore(clusterMetrics)
    };
  }
  private calculateSingleClusterMetrics(cluster: ClusterResult) {
    return {
      geographicCompactness: this.calculateGeographicCompactness(cluster),
      timeWindowCohesion: this.calculateTimeWindowCohesion(cluster),
      carerFitScore: cluster.metrics.carerFitScore || 0,
      continuityScore: cluster.metrics.continuityRisk ? 100 - cluster.metrics.continuityRisk : 0
    };
  }

  private calculateGeographicCompactness(cluster: ClusterResult): number {
    // Lower is better - represents average distance from centroid
    const distances = cluster.visits.map(visit => 
      this.calculateDistance(
        cluster.centroid.latitude, cluster.centroid.longitude,
        visit.latitude!, visit.longitude!
      )
    );
    return distances.reduce((sum, dist) => sum + dist, 0) / distances.length;
  }

  private calculateTimeWindowCohesion(cluster: ClusterResult): number {
    if (cluster.visits.length <= 1) return 100;

    const timeWindows = cluster.visits.map(v => ({
      start: v.timeStartMinutes,
      end: v.timeEndMinutes,
      duration: v.estimatedDuration || 60
    }));

    // Calculate overlap and proximity of time windows
    let cohesionScore = 0;
    let pairCount = 0;

    for (let i = 0; i < timeWindows.length; i++) {
      for (let j = i + 1; j < timeWindows.length; j++) {
        const window1 = timeWindows[i];
        const window2 = timeWindows[j];
        
        // Check if time windows are compatible (no overlap + reasonable gap)
        const timeGap = Math.abs(window1.start - window2.start);
        const maxGap = 4 * 60; // 4 hours maximum gap
        
        if (timeGap <= maxGap) {
          cohesionScore += (1 - (timeGap / maxGap));
        }
        
        pairCount++;
      }
    }

    return pairCount > 0 ? (cohesionScore / pairCount) * 100 : 100;
  }

  // ========== OPTIMIZATION HELPER METHODS ==========

  private async createSubCluster(
    parent: ClusterResult, 
    visits: ClusterVisit[]
  ): Promise<ClusterResult> {
    const centroid = this.calculateCentroid(visits);
    const constraints = await this.constraintsService.getActiveConstraints(parent.visits[0].tenantId);
    const metrics = await this.calculateSingleClusterMetricsFromVisits(visits, constraints);

    return {
      id: `sub_${parent.id}_${Date.now()}`,
      name: `${parent.name} (Sub)`,
      centroid,
      visits,
      metrics
    };
  }

  private areClustersCompatible(cluster1: ClusterResult, cluster2: ClusterResult): boolean {
    // Check if clusters can be merged (geographically and temporally close)
    const distance = this.calculateClusterDistance(cluster1, cluster2);
    const timeDiff = this.calculateClusterTimeDifference(cluster1, cluster2);
    
    return distance < 5000 && timeDiff < 2 * 60; // 5km and 2 hours
  }

  private calculateClusterDistance(cluster1: ClusterResult, cluster2: ClusterResult): number {
    return this.calculateDistance(
      cluster1.centroid.latitude, cluster1.centroid.longitude,
      cluster2.centroid.latitude, cluster2.centroid.longitude
    );
  }

  private calculateClusterTimeDifference(cluster1: ClusterResult, cluster2: ClusterResult): number {
    const avgTime1 = cluster1.visits.reduce((sum, v) => sum + v.timeStartMinutes, 0) / cluster1.visits.length;
    const avgTime2 = cluster2.visits.reduce((sum, v) => sum + v.timeStartMinutes, 0) / cluster2.visits.length;
    return Math.abs(avgTime1 - avgTime2);
  }

  private async mergeClusters(cluster1: ClusterResult, cluster2: ClusterResult): Promise<ClusterResult> {
    const mergedVisits = [...cluster1.visits, ...cluster2.visits];
    const centroid = this.calculateCentroid(mergedVisits);
    const constraints = await this.constraintsService.getActiveConstraints(cluster1.visits[0].tenantId);
    const metrics = await this.calculateSingleClusterMetricsFromVisits(mergedVisits, constraints);

    return {
      id: `merged_${cluster1.id}_${cluster2.id}`,
      name: `Merged ${cluster1.name} + ${cluster2.name}`,
      centroid,
      visits: mergedVisits,
      metrics
    };
  }

  private distributeRemainingVisits(subClusters: ClusterResult[], remainingVisits: ClusterVisit[]) {
    for (const visit of remainingVisits) {
      // Find the subcluster with closest centroid
      const bestCluster = subClusters.reduce((best, current) => {
        const bestDistance = this.calculateDistance(
          best.centroid.latitude, best.centroid.longitude,
          visit.latitude!, visit.longitude!
        );
        const currentDistance = this.calculateDistance(
          current.centroid.latitude, current.centroid.longitude,
          visit.latitude!, visit.longitude!
        );
        return currentDistance < bestDistance ? current : best;
      });

      bestCluster.visits.push(visit);
    }
  }

  private findTimeConflicts(visits: ClusterVisit[]): [ClusterVisit, ClusterVisit][] {
    const conflicts: [ClusterVisit, ClusterVisit][] = [];

    for (let i = 0; i < visits.length; i++) {
      for (let j = i + 1; j < visits.length; j++) {
        const visit1 = visits[i];
        const visit2 = visits[j];
        
        if (this.doTimeWindowsConflict(visit1, visit2)) {
          conflicts.push([visit1, visit2]);
        }
      }
    }

    return conflicts;
  }

  private doTimeWindowsConflict(visit1: ClusterVisit, visit2: ClusterVisit): boolean {
    // Consider buffer time for travel
    const buffer = 30; // 30 minutes buffer for travel
    
    return !(
      visit1.timeEndMinutes + buffer < visit2.timeStartMinutes ||
      visit2.timeEndMinutes + buffer < visit1.timeStartMinutes
    );
  }

  private async calculateVisitDistancesFromCentroid(cluster: ClusterResult): Promise<number[]> {
    return await Promise.all(
      cluster.visits.map(async visit => 
        this.calculateDistance(
          cluster.centroid.latitude, cluster.centroid.longitude,
          visit.latitude!, visit.longitude!
        )
      )
    );
  }

  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    // Haversine formula for great-circle distance
    const R = 6371e3; // Earth radius in meters
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c; // Distance in meters
  }

  private calculateWorkloadBalance(clusters: ClusterResult[]): number {
    if (clusters.length <= 1) return 100;

    const workloads = clusters.map(c => c.visits.length);
    const avgWorkload = workloads.reduce((sum, w) => sum + w, 0) / workloads.length;
    const variance = workloads.reduce((sum, w) => sum + Math.pow(w - avgWorkload, 2), 0) / workloads.length;
    
    // Convert to 0-100 score (higher = more balanced)
    const maxVariance = Math.max(...workloads) - Math.min(...workloads);
    return maxVariance > 0 ? (1 - (variance / maxVariance)) * 100 : 100;
  }

  private calculateOverallScore(metrics: any[]): number {
    const weights = {
      geographicCompactness: 0.3,
      timeWindowCohesion: 0.25,
      carerFitScore: 0.25,
      continuityScore: 0.2
    };

    const weightedScores = metrics.map(m => 
      (1 - m.geographicCompactness / 10000) * weights.geographicCompactness * 100 +
      m.timeWindowCohesion * weights.timeWindowCohesion +
      m.carerFitScore * weights.carerFitScore +
      m.continuityScore * weights.continuityScore
    );

    return this.average(weightedScores);
  }

  private average(values: number[]): number {
    return values.reduce((sum, val) => sum + val, 0) / values.length;
  }

  private calculateOptimizationActions(
    before: ClusterResult[], 
    after: ClusterResult[]
  ): { clustersSplit: number; clustersMerged: number; outliersRemoved: number; visitsReassigned: number } {
    const beforeVisits = before.flatMap(c => c.visits).length;
    const afterVisits = after.flatMap(c => c.visits).length;
    
    return {
      clustersSplit: Math.max(0, after.length - before.length),
      clustersMerged: Math.max(0, before.length - after.length),
      outliersRemoved: beforeVisits - afterVisits,
      visitsReassigned: Math.abs(beforeVisits - afterVisits)
    };
  }

  private getEmptyMetrics(): ClusterQualityMetrics {
    return {
      geographicCompactness: 0,
      timeWindowCohesion: 0,
      carerFitScore: 0,
      workloadBalance: 0,
      continuityScore: 0,
      overallScore: 0
    };
  }

  private async recalculateClusterMetrics(cluster: ClusterResult): Promise<ClusterResult> {
    const constraints = await this.constraintsService.getActiveConstraints(cluster.visits[0].tenantId);
    const metrics = await this.calculateSingleClusterMetricsFromVisits(cluster.visits, constraints);
    return { ...cluster, metrics };
  }

  private async calculateSingleClusterMetricsFromVisits(
    visits: ClusterVisit[], 
    constraints: RosteringConstraints
  ): Promise<ClusterResult['metrics']> {
    const totalVisits = visits.length;
    const totalDuration = visits.reduce((sum, visit) => {
      const duration = visit.estimatedDuration || 60;
      return sum + duration;
    }, 0);

    const travelMetrics = await this.calculateTravelMetrics(visits);
    const skillCoverage = this.calculateSkillCoverage(visits);
    const continuityRisk = this.calculateContinuityRisk(visits);
    const suggestedCarers = this.suggestCarersForCluster(visits);

    return {
      totalVisits,
      totalDuration,
      averageTravel: travelMetrics.averageTravel,
      skillCoverage,
      continuityRisk,
      suggestedCarers,
      carerFitScore: 0 // Will be calculated in optimization
    };
  }

  // ========== PLACEHOLDER METHODS ==========
  private async findAvailableCarersForCluster(cluster: ClusterResult, tenantId: string): Promise<any[]> {
    // Implementation would query database for suitable carers
    // For now, return empty array - you can implement this based on your carer data
    return [];
  }

  private async calculateCarerFitScore(cluster: ClusterResult, carer: any): Promise<number> {
    // Implementation would calculate how well carer fits the cluster
    // For now, return placeholder score
    return 0.8;
  }

  // ========== EXISTING METHODS (keep all your original methods below) ==========
  
  /**
   * Get visits ready for clustering (approved requests with location data)
   */
  private async getVisitsForClustering(tenantId: string, params: ClusteringParams): Promise<ExternalRequest[]> {
    return await this.prisma.externalRequest.findMany({
      where: {
        tenantId,
        status: RequestStatus.APPROVED,
        scheduledStartTime: {
          gte: params.dateRange.start,
          lte: params.dateRange.end
        },
        latitude: { not: null },
        longitude: { not: null },
        clusterId: null // Only unclustered visits
      },
      include: {
        matches: {
          include: {
            carer: true
          }
        }
      }
    });
  }

  /**
   * Pre-compute eligible carers for each visit
   */
  private async preComputeEligibility(visits: ExternalRequest[]): Promise<ClusterVisit[]> {
    const visitsWithEligibility: ClusterVisit[] = [];

    for (const visit of visits) {
      // Convert time to feature vector components
      const scheduledStart = visit.scheduledStartTime ? new Date(visit.scheduledStartTime) : new Date();
      const scheduledEnd = visit.scheduledEndTime ? new Date(visit.scheduledEndTime) : new Date(scheduledStart.getTime() + 60 * 60 * 1000); // Default 1 hour

      const timeStartMinutes = this.timeToMinutes(scheduledStart);
      const timeEndMinutes = this.timeToMinutes(scheduledEnd);
      const dayOfWeek = scheduledStart.getDay();

      // Find eligible carers (simplified - would need proper skills matching)
      const eligibleCarers = await this.findEligibleCarers(visit);

      visitsWithEligibility.push({
        ...visit,
        timeStartMinutes,
        timeEndMinutes,
        dayOfWeek,
        eligibleCarers
      });
    }

    return visitsWithEligibility;
  }

  /**
   * Find eligible carers for a visit based on skills, availability, and location
   */
  private async findEligibleCarers(visit: ExternalRequest): Promise<string[]> {
    try {
      // Get active carers in the same tenant
      const carers = await this.prisma.carer.findMany({
        where: {
          tenantId: visit.tenantId,
          isActive: true,
          latitude: { not: null },
          longitude: { not: null }
        },
        select: {
          id: true,
          skills: true,
          maxTravelDistance: true,
          latitude: true,
          longitude: true
        }
      });

      const eligibleCarerIds: string[] = [];

      for (const carer of carers) {
        // Check skills match
        const skillsMatch = this.checkSkillsMatch(visit.requirements, carer.skills);
        
        // Check travel distance
        const withinDistance = await this.checkTravelDistance(
          visit.latitude!, visit.longitude!,
          carer.latitude!, carer.longitude!,
          carer.maxTravelDistance
        );

        if (skillsMatch && withinDistance) {
          eligibleCarerIds.push(carer.id);
        }
      }

      return eligibleCarerIds;
    } catch (error) {
      logger.error('Error finding eligible carers:', error);
      return [];
    }
  }

  /**
   * Check if carer skills match visit requirements
   */
  private checkSkillsMatch(visitRequirements: string | null, carerSkills: string[]): boolean {
    if (!visitRequirements) return true; // No specific requirements
    
    // Simple keyword matching - enhance with proper NLP in production
    const requirements = visitRequirements.toLowerCase();
    return carerSkills.some(skill => 
      requirements.includes(skill.toLowerCase())
    );
  }

  /**
   * Check if carer is within travel distance
   */
  private async checkTravelDistance(
    visitLat: number, visitLon: number,
    carerLat: number, carerLon: number,
    maxTravelDistance: number
  ): Promise<boolean> {
    try {
      // Use PostGIS for distance calculation
      const result = await this.prisma.$queryRaw<Array<{ distance: number }>>`
        SELECT ST_Distance(
          ST_SetSRID(ST_MakePoint(${visitLon}, ${visitLat}), 4326)::geography,
          ST_SetSRID(ST_MakePoint(${carerLon}, ${carerLat}), 4326)::geography
        ) as distance
      `;

      const distance = result[0]?.distance || 0;
      return distance <= maxTravelDistance;
    } catch (error) {
      logger.error('Error calculating travel distance:', error);
      return false;
    }
  }

  /**
   * Create feature vectors for DBSCAN [lat, lon, time, day]
   */
  private createFeatureVectors(visits: ClusterVisit[]): number[][] {
    return visits.map(visit => {
      // Normalize features for DBSCAN
      const normalizedLat = visit.latitude! / 90; // Normalize to [-1, 1]
      const normalizedLon = visit.longitude! / 180; // Normalize to [-1, 1]
      const normalizedTime = visit.timeStartMinutes / (24 * 60); // Normalize to [0, 1]
      const normalizedDay = visit.dayOfWeek / 7; // Normalize to [0, 1]

      return [normalizedLat, normalizedLon, normalizedTime, normalizedDay];
    });
  }

  /**
   * Run DBSCAN clustering algorithm
   */
  private async runDBSCAN(
    featureVectors: number[][],
    visits: ClusterVisit[],
    params: ClusteringParams,
    constraints: RosteringConstraints
  ): Promise<ClusterVisit[][]> {
    const epsilon = params.epsilon || 0.1; // Adjusted for normalized features
    const minPoints = params.minPoints || params.minClusterSize || 2;

    const visited = new Set<number>();
    const clusters: ClusterVisit[][] = [];
    const noise: ClusterVisit[] = [];

    for (let i = 0; i < featureVectors.length; i++) {
      if (visited.has(i)) continue;

      visited.add(i);
      const neighbors = this.regionQuery(featureVectors, i, epsilon);

      if (neighbors.length < minPoints) {
        noise.push(visits[i]);
      } else {
        const cluster: ClusterVisit[] = [visits[i]];
        this.expandCluster(
          featureVectors, 
          visits, 
          i, 
          neighbors, 
          cluster, 
          visited, 
          epsilon, 
          minPoints
        );
        
        // Apply cluster size constraints
        if (cluster.length >= (params.minClusterSize || 1) && 
            cluster.length <= (params.maxClusterSize || 10)) {
          clusters.push(cluster);
        } else {
          noise.push(...cluster);
        }
      }
    }

    // Handle noise points (visits that couldn't be clustered)
    if (noise.length > 0) {
      logger.info(`${noise.length} visits could not be clustered (noise)`);
      // Option: Create single-visit clusters for noise, or leave unclustered
    }

    return clusters;
  }

  /**
   * Find neighbors within epsilon distance
   */
  private regionQuery(vectors: number[][], index: number, epsilon: number): number[] {
    const neighbors: number[] = [];
    const point = vectors[index];

    for (let i = 0; i < vectors.length; i++) {
      if (i === index) continue;
      
      const distance = this.euclideanDistance(point, vectors[i]);
      if (distance <= epsilon) {
        neighbors.push(i);
      }
    }

    return neighbors;
  }

  /**
   * Expand cluster from core point
   */
  private expandCluster(
    vectors: number[][],
    visits: ClusterVisit[],
    index: number,
    neighbors: number[],
    cluster: ClusterVisit[],
    visited: Set<number>,
    epsilon: number,
    minPoints: number
  ): void {
    for (let i = 0; i < neighbors.length; i++) {
      const neighborIndex = neighbors[i];

      if (!visited.has(neighborIndex)) {
        visited.add(neighborIndex);
        const neighborNeighbors = this.regionQuery(vectors, neighborIndex, epsilon);

        if (neighborNeighbors.length >= minPoints) {
          neighbors.push(...neighborNeighbors.filter(n => !neighbors.includes(n)));
        }
      }

      // Add to cluster if not already in any cluster
      if (!cluster.includes(visits[neighborIndex])) {
        cluster.push(visits[neighborIndex]);
      }
    }
  }

  /**
   * Calculate Euclidean distance between two feature vectors
   */
  private euclideanDistance(a: number[], b: number[]): number {
    let sum = 0;
    for (let i = 0; i < a.length; i++) {
      sum += Math.pow(a[i] - b[i], 2);
    }
    return Math.sqrt(sum);
  }

  /**
   * Calculate comprehensive cluster metrics
   */
  private async calculateClusterMetrics(
    clusters: ClusterVisit[][],
    constraints: RosteringConstraints
  ): Promise<ClusterResult[]> {
    const results: ClusterResult[] = [];

    for (const clusterVisits of clusters) {
      // Calculate centroid
      const centroid = this.calculateCentroid(clusterVisits);

      // Calculate metrics
      const totalVisits = clusterVisits.length;
      const totalDuration = clusterVisits.reduce((sum, visit) => {
        const duration = visit.estimatedDuration || 60; // Default 60 minutes
        return sum + duration;
      }, 0);

      // Calculate travel metrics
      const travelMetrics = await this.calculateTravelMetrics(clusterVisits);

      // Calculate skill coverage
      const skillCoverage = this.calculateSkillCoverage(clusterVisits);

      // Calculate continuity risk
      const continuityRisk = this.calculateContinuityRisk(clusterVisits);

      // Suggest carers for the cluster
      const suggestedCarers = this.suggestCarersForCluster(clusterVisits);

      results.push({
        id: `cluster_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        name: await this.generateClusterName(centroid),
        centroid,
        visits: clusterVisits,
        metrics: {
          totalVisits,
          totalDuration,
          averageTravel: travelMetrics.averageTravel,
          skillCoverage,
          continuityRisk,
          suggestedCarers
        }
      });
    }

    return results;
  }

  /**
   * Calculate geographic centroid of cluster visits
   */
  private calculateCentroid(visits: ClusterVisit[]): { latitude: number; longitude: number } {
    const sumLat = visits.reduce((sum, visit) => sum + visit.latitude!, 0);
    const sumLon = visits.reduce((sum, visit) => sum + visit.longitude!, 0);
    
    return {
      latitude: sumLat / visits.length,
      longitude: sumLon / visits.length
    };
  }

  /**
   * Calculate travel metrics for cluster
   */
  private async calculateTravelMetrics(visits: ClusterVisit[]): Promise<{ averageTravel: number }> {
    if (visits.length <= 1) {
      return { averageTravel: 0 };
    }

    let totalTravel = 0;
    let pairCount = 0;

    // Calculate average travel between visits in cluster
    for (let i = 0; i < visits.length; i++) {
      for (let j = i + 1; j < visits.length; j++) {
        const fromPostcode = visits[i].postcode;
        const toPostcode = visits[j].postcode;

        if (fromPostcode && toPostcode) {
          try {
            const travel = await this.travelService.getTravelTime(fromPostcode, toPostcode);
            totalTravel += travel.durationSeconds / 60; // Convert to minutes
            pairCount++;
          } catch (error) {
            // Skip failed travel calculations
          }
        }
      }
    }

    return {
      averageTravel: pairCount > 0 ? totalTravel / pairCount : 0
    };
  }

  /**
   * Calculate skill coverage percentage
   */
  private calculateSkillCoverage(visits: ClusterVisit[]): number {
    if (visits.length === 0) return 0;

    const totalRequirements = visits.filter(v => v.requirements).length;
    if (totalRequirements === 0) return 100;

    const coveredRequirements = visits.filter(visit => 
      visit.requirements && visit.eligibleCarers.length > 0
    ).length;

    return (coveredRequirements / totalRequirements) * 100;
  }

  /**
   * Calculate continuity risk percentage
   */
  private calculateContinuityRisk(visits: ClusterVisit[]): number {
    if (visits.length === 0) return 0;

    const visitsWithHistory = visits.filter(visit => 
      visit.matches && visit.matches.length > 0
    );

    if (visitsWithHistory.length === 0) return 0;

    const riskyVisits = visitsWithHistory.filter(visit => {
      // Consider visit risky if preferred carer isn't available
      const preferredCarers = visit.matches!
        .filter(match => match.response === 'ACCEPTED')
        .map(match => match.carerId);

      return preferredCarers.length > 0 && 
             !preferredCarers.some(carerId => 
               visit.eligibleCarers.includes(carerId)
             );
    });

    return (riskyVisits.length / visitsWithHistory.length) * 100;
  }

  /**
   * Suggest carers for the entire cluster
   */
  private suggestCarersForCluster(visits: ClusterVisit[]): string[] {
    const carerScores = new Map<string, number>();

    visits.forEach(visit => {
      visit.eligibleCarers.forEach(carerId => {
        const currentScore = carerScores.get(carerId) || 0;
        carerScores.set(carerId, currentScore + 1);
      });
    });

    // Return top 5 carers by coverage score
    return Array.from(carerScores.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([carerId]) => carerId);
  }

  /**
   * Generate cluster name based on centroid
   */
  private async generateClusterName(centroid: { latitude: number; longitude: number }): Promise<string> {
    const latPrefix = centroid.latitude >= 0 ? 'N' : 'S';
    const lngPrefix = centroid.longitude >= 0 ? 'E' : 'W';
    
    return `Cluster ${latPrefix}${Math.abs(centroid.latitude).toFixed(2)} ${lngPrefix}${Math.abs(centroid.longitude).toFixed(2)}`;
  }

  /**
   * Convert time to minutes since midnight
   */
  private timeToMinutes(date: Date): number {
    return date.getHours() * 60 + date.getMinutes();
  }

  // ... (keep all your existing methods like findOrCreateClusterForLocation, createNewCluster, etc.)
  // I've omitted them for brevity but they should remain in your class

  /**
   * Find the nearest cluster for a location or create a new one if none exists within threshold
   */
  async findOrCreateClusterForLocation(
    tenantId: string,
    latitude: number,
    longitude: number,
    maxDistanceMeters: number = 5000
  ) {
    try {
      // Find nearest existing cluster using PostGIS
      const nearestClusters = await this.prisma.$queryRaw<Array<{
        id: string;
        name: string;
        distance: number;
      }>>`
        SELECT 
          id, 
          name,
          ST_Distance(
            "regionCenter"::geography, 
            ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)::geography
          ) AS distance
        FROM clusters 
        WHERE "tenantId" = ${tenantId}
        ORDER BY "regionCenter" <-> ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)
        LIMIT 1
      `;

      // If nearest cluster is within threshold, use it
      if (nearestClusters.length > 0 && nearestClusters[0].distance <= maxDistanceMeters) {
        return await this.prisma.cluster.findUnique({
          where: { id: nearestClusters[0].id }
        });
      }

      // Otherwise, create new cluster
      return await this.createNewCluster(tenantId, latitude, longitude);
    } catch (error) {
      console.error('Error finding/creating cluster:', error);
      // Fallback: create new cluster
      return await this.createNewCluster(tenantId, latitude, longitude);
    }
  }

  /**
   * Create a new cluster at the specified location
   */
  private async createNewCluster(tenantId: string, latitude: number, longitude: number) {
    const clusterName = await this.generateClusterNameFromCoords(latitude, longitude);
    
    // Create cluster without PostGIS field first
    const cluster = await (this.prisma as any).cluster.create({
      data: {
        tenantId,
        name: clusterName,
        latitude,
        longitude,
        radiusMeters: 5000,
        activeRequestCount: 0,
        totalRequestCount: 0,
        activeCarerCount: 0,
        totalCarerCount: 0,
        lastActivityAt: new Date()
      }
    });

    // Update PostGIS regionCenter field using raw SQL
    try {
      await this.prisma.$executeRaw`
        UPDATE clusters 
        SET "regionCenter" = ST_SetSRID(ST_MakePoint(${longitude}, ${latitude}), 4326)::geography
        WHERE id = ${cluster.id}
      `;
    } catch (error) {
      console.error('Failed to update cluster regionCenter:', error);
    }

    return cluster;
  }

  /**
   * Generate a readable cluster name based on coordinates
   */
  private async generateClusterNameFromCoords(latitude: number, longitude: number): Promise<string> {
    return this.generateClusterName({ latitude, longitude });
  }

/**
   * Update cluster statistics using ClusterAssignment table
   */
  async updateClusterStats(clusterId: string) {
    try {
      // Get counts from ClusterAssignment table
      const stats = await this.prisma.$queryRaw<Array<{
        active_carers: number;
        total_carers: number;
        active_requests: number;
        total_requests: number;
      }>>`
        SELECT 
          COUNT(ca.id) as active_carers,
          COUNT(ca.id) as total_carers, -- For now, all assigned carers are considered active
          COUNT(CASE WHEN er.status IN ('PENDING', 'PROCESSING', 'MATCHED') THEN 1 END) as active_requests,
          COUNT(er.id) as total_requests
        FROM clusters cl
        LEFT JOIN cluster_assignments ca ON ca."clusterId" = cl.id
        LEFT JOIN external_requests er ON er."clusterId" = cl.id
        WHERE cl.id = ${clusterId}
        GROUP BY cl.id
      `;

      if (stats.length > 0) {
        await this.prisma.cluster.update({
          where: { id: clusterId },
          data: {
            activeRequestCount: Number(stats[0].active_requests) || 0,
            totalRequestCount: Number(stats[0].total_requests) || 0,
            activeCarerCount: Number(stats[0].active_carers) || 0,
            totalCarerCount: Number(stats[0].total_carers) || 0,
            lastActivityAt: new Date()
          }
        });
      }
    } catch (error) {
      console.error('Error updating cluster stats:', error);
    }
  }

    /**
   * Get carer assignments in a cluster (returns assignment IDs, not carer details)
   */
  async getCarerAssignmentsInCluster(clusterId: string) {
    return await this.prisma.clusterAssignment.findMany({
      where: { clusterId },
      include: { cluster: true }
    });
  }

  /**
   * Get available carer assignments in cluster with optional nearby clusters
   */
    async getCarerAssignmentsInClusterWithNearby(
      clusterId: string, 
      includeNearby: boolean = false,
      maxDistanceMeters: number = 10000
    ) {
      const cluster = await this.prisma.cluster.findUnique({
        where: { id: clusterId }
      });

      if (!cluster || !cluster.latitude || !cluster.longitude) {
        return await this.getCarerAssignmentsInCluster(clusterId);
      }

      let assignments = await this.getCarerAssignmentsInCluster(clusterId);

      // If not enough carers in cluster and nearby requested, find nearby assignments
      if (includeNearby && assignments.length < 3) {
        try {
          const nearbyAssignments = await this.prisma.$queryRaw<any[]>`
            SELECT ca.* 
            FROM cluster_assignments ca
            JOIN clusters c ON c.id = ca."clusterId"
            WHERE ca."clusterId" != ${clusterId}
              AND ca."tenantId" = ${cluster.tenantId}
              AND c.latitude IS NOT NULL 
              AND c.longitude IS NOT NULL
              AND ST_DWithin(
                c."regionCenter"::geography,
                ST_SetSRID(ST_MakePoint(${cluster.longitude}, ${cluster.latitude}), 4326)::geography,
                ${maxDistanceMeters}
              )
            ORDER BY ST_Distance(
              c."regionCenter"::geography,
              ST_SetSRID(ST_MakePoint(${cluster.longitude}, ${cluster.latitude}), 4326)::geography
            )
            LIMIT 10
          `;

          assignments = [...assignments, ...nearbyAssignments];
        } catch (error) {
          console.error('Error finding nearby carer assignments:', error);
        }
      }

      return assignments;
    }


  /**
   * Assign a carer to a cluster based on their location
   */
  async assignCarerToCluster(tenantId: string, carerId: string, latitude: number, longitude: number) {
    try {


      const cluster = await this.findOrCreateClusterForLocation(
        tenantId,
        latitude,
        longitude
      );

      if (cluster) {
        await this.prisma.clusterAssignment.upsert({
        where: {
          carerId_tenantId: {
            carerId: carerId,
            tenantId: tenantId
          }
        },
        update: { 
          clusterId: cluster.id,
          updatedAt: new Date()
        },
        create: {
          carerId: carerId,
          clusterId: cluster.id,
          tenantId: tenantId,
          assignedAt: new Date()
        }
        });

        // Update cluster stats
        await this.updateClusterStats(cluster.id);
      }

      return cluster;
    } catch (error) {
      console.error('Error assigning carer to cluster:', error);
      throw error;
    }
  }

  /**
   * Get cluster overview for analytics
   */
  async getClusterAnalytics(tenantId: string) {
    const clusters = await (this.prisma as any).cluster.findMany({
      where: { tenantId: tenantId.toString() },
      orderBy: [
        { activeRequestCount: 'desc' },
        { activeCarerCount: 'desc' }
      ]
    });

    // Find clusters that need attention (high demand, low supply)
    const needAttention = clusters.filter(
      (c: any) => c.activeRequestCount > 5 && c.activeCarerCount < 3
    );

    return {
      clusters,
      summary: {
        totalClusters: clusters.length,
        needAttention: needAttention.length,
        totalActiveRequests: clusters.reduce((sum: number, c: any) => sum + c.activeRequestCount, 0),
        totalActiveCarers: clusters.reduce((sum: number, c: any) => sum + c.activeCarerCount, 0),
        clustersNeedingAttention: needAttention
      }
    };
  }

  
}

  /**
   * Remove carer from cluster (when they become inactive)
   */
  async removeCarerFromCluster(tenantId: string, carerId: string) {
    const assignment = await this.prisma.clusterAssignment.findUnique({
      where: { carerId_tenantId: { carerId, tenantId } }
    });

    if (assignment) {
      await this.prisma.clusterAssignment.delete({
        where: { carerId_tenantId: { carerId, tenantId } }
      });
      await this.updateClusterStats(assignment.clusterId);
    }
  }

  /**
   * Get carer's current cluster assignment
   */
  async getCarerClusterAssignment(tenantId: string, carerId: string) {
    return await this.prisma.clusterAssignment.findUnique({
      where: { carerId_tenantId: { carerId, tenantId } },
      include: { cluster: true }
    });
  }

  /**
   * Move carer from one cluster to another
   */
  async moveCarerToCluster(tenantId: string, carerId: string, newClusterId: string) {
    try {
      // Verify the new cluster exists and belongs to the same tenant
      const newCluster = await this.prisma.cluster.findUnique({
        where: { id: newClusterId }
      });

      if (!newCluster) {
        throw new Error('Target cluster not found');
      }

      if (newCluster.tenantId !== tenantId) {
        throw new Error('Target cluster does not belong to tenant');
      }

      // Get current assignment to track which cluster stats to update
      const currentAssignment = await this.prisma.clusterAssignment.findUnique({
        where: {
          carerId_tenantId: {
            carerId: carerId,
            tenantId: tenantId
          }
        }
      });

      // Move carer to new cluster
      const updatedAssignment = await this.prisma.clusterAssignment.upsert({
        where: {
          carerId_tenantId: {
            carerId: carerId,
            tenantId: tenantId
          }
        },
        update: { 
          clusterId: newClusterId,
          updatedAt: new Date()
        },
        create: {
          carerId: carerId,
          clusterId: newClusterId,
          tenantId: tenantId,
          assignedAt: new Date()
        }
      });

      // Update stats for both old and new clusters
      if (currentAssignment) {
        await this.updateClusterStats(currentAssignment.clusterId); // Old cluster
      }
      await this.updateClusterStats(newClusterId); // New cluster

      return {
        carerId,
        previousClusterId: currentAssignment?.clusterId || null,
        newClusterId,
        message: 'Carer moved to cluster successfully'
      };
    } catch (error) {
      console.error('Error moving carer to cluster:', error);
      throw error;
    }
  }
}
