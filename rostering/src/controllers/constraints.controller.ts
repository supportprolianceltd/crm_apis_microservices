import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { ConstraintsService } from '../services/constraints.service';

export class ConstraintsController {
  private constraintsService: ConstraintsService;

  constructor(private prisma: PrismaClient) {
    this.constraintsService = new ConstraintsService(prisma);
  }

  /**
   * Get active constraints for tenant
   */
  public getConstraints = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = req.user!.tenantId;
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
      const tenantId = req.user!.tenantId;
      const updates = req.body;

      // Validate required fields
      const requiredFields = [
        'wtdMaxHoursPerWeek', 'restPeriodHours', 'bufferMinutes', 
        'travelMaxMinutes', 'continuityTargetPercent'
      ];

      for (const field of requiredFields) {
        if (updates[field] === undefined) {
          res.status(400).json({
            success: false,
            error: `Missing required field: ${field}`
          });
          return;
        }
      }

      const updated = await this.constraintsService.updateConstraints(tenantId, updates);

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
      const tenantId = req.user!.tenantId;
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
      const tenantId = req.user!.tenantId;
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
      const tenantId = req.user!.tenantId;
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
}