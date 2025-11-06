import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { ConstraintsService } from '../services/constraints.service';
import { TravelService } from '../services/travel.service';
import { ClusteringService } from '../services/clustering.service';

export class ConstraintsController {
  private constraintsService: ConstraintsService;
  private travelService: TravelService;
  private clusteringService: ClusteringService;

  constructor(private prisma: PrismaClient) {
    this.constraintsService = new ConstraintsService(prisma);
    this.travelService = new TravelService(prisma);
    this.clusteringService = new ClusteringService(prisma, this.constraintsService, this.travelService);
  }

  /**
   * Get active constraints for tenant
   */
  public getConstraints = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = req.user;
      if (!user) {
        res.status(401).json({
          success: false,
          error: 'User not authenticated'
        });
        return;
      }

      const tenantId = user.tenantId.toString();
      const constraints = await this.constraintsService.getActiveConstraints(tenantId);

      res.json({
        success: true,
        data: constraints
      });
    } catch (error) {
      console.error('getConstraints error:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get constraints'
      });
    }
  };

  /**
   * Update constraints
   */
  public updateConstraints = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = req.user;
      if (!user) {
        res.status(401).json({
          success: false,
          error: 'User not authenticated'
        });
        return;
      }

      const tenantId = user.tenantId.toString();
      const updates = req.body;

      // Pass user info to service for tracking
      const updatedByUser = {
        id: user.id,
        email: user.email,
        firstName: user.firstName,
        lastName: user.lastName
      };

      console.log('Updating constraints with user info:', updatedByUser);

      const updated = await this.constraintsService.updateConstraints(
        tenantId, 
        updates,
        updatedByUser
      );

      res.json({
        success: true,
        data: updated,
        message: 'Constraints updated successfully'
      });
    } catch (error) {
      console.error('updateConstraints error:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to update constraints'
      });
    }
  };

  /**
   * Create new rule set
   */
  public createRuleSet = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = req.user;
      if (!user) {
        res.status(401).json({
          success: false,
          error: 'User not authenticated'
        });
        return;
      }

      const tenantId = user.tenantId.toString();
      const { name, ...constraints } = req.body;

      if (!name) {
        res.status(400).json({
          success: false,
          error: 'Rule set name is required'
        });
        return;
      }

      const newRuleSet = await this.constraintsService.createRuleSet(tenantId, name, constraints);

      res.json({
        success: true,
        data: newRuleSet,
        message: 'Rule set created successfully'
      });
    } catch (error) {
      console.error('createRuleSet error:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to create rule set'
      });
    }
  };

  /**
   * Get all rule sets
   */
  public getRuleSets = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = req.user;
      if (!user) {
        res.status(401).json({
          success: false,
          error: 'User not authenticated'
        });
        return;
      }

      const tenantId = user.tenantId.toString();
      const ruleSets = await this.constraintsService.getRuleSets(tenantId);

      res.json({
        success: true,
        data: ruleSets
      });
    } catch (error) {
      console.error('getRuleSets error:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get rule sets'
      });
    }
  };

  /**
   * Validate assignment against constraints
   */
  public validateAssignment = async (req: Request, res: Response): Promise<void> => {
    try {
      const user = req.user;
      if (!user) {
        res.status(401).json({
          success: false,
          error: 'User not authenticated'
        });
        return;
      }

      const tenantId = user.tenantId.toString();
      const assignment = req.body;

      const constraints = await this.constraintsService.getActiveConstraints(tenantId);
      const validation = this.constraintsService.validateAssignment(constraints, assignment);

      res.json({
        success: true,
        data: validation
      });
    } catch (error) {
      console.error('validateAssignment error:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to validate assignment'
      });
    }
  };

  /**
   * Generate AI-powered clusters for a date range
   */
  public async generateClusters(req: Request, res: Response) {
    try {
      const user = req.user;
      if (!user) {
        return res.status(401).json({ 
          success: false,
          error: 'User not authenticated' 
        });
      }

      const tenantId = user.tenantId.toString();
      
      if (!tenantId) {
        return res.status(403).json({ 
          success: false,
          error: 'tenantId missing from auth context' 
        });
      }

      const {
        startDate,
        endDate,
        maxTravelTime = 30,
        timeWindowTolerance = 15,
        minClusterSize = 2,
        maxClusterSize = 8
      } = req.body;

      if (!startDate || !endDate) {
        return res.status(400).json({ 
          success: false,
          error: 'startDate and endDate are required' 
        });
      }

      // Initialize services
      const constraintsService = new ConstraintsService(this.prisma);
      const travelService = new TravelService(this.prisma);
      const clusteringService = new ClusteringService(
        this.prisma, 
        constraintsService, 
        travelService
      );

      const params = {
        dateRange: {
          start: new Date(startDate),
          end: new Date(endDate)
        },
        maxTravelTime,
        timeWindowTolerance,
        minClusterSize,
        maxClusterSize
      };

      const clusters = await clusteringService.generateClusters(tenantId.toString(), params);

      return res.json({
        success: true,
        data: {
          clusters,
          summary: {
            totalClusters: clusters.length,
            totalVisits: clusters.reduce((sum: number, cluster) => sum + cluster.visits.length, 0),
            averageClusterSize: clusters.length > 0 
              ? clusters.reduce((sum: number, cluster) => sum + cluster.visits.length, 0) / clusters.length 
              : 0
          }
        }
      });

    } catch (error: any) {
      console.error('generateClusters error', error);
      return res.status(500).json({ 
        success: false,
        error: 'Failed to generate clusters', 
        details: error.message 
      });
    }
  }
}