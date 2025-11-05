import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { DataValidationService } from '../services/data-validation.service';
import { logger } from '../utils/logger';

interface AuthenticatedRequest extends Request {
  user: {
    id: string;
    email: string;
    tenantId: string;
  };
}

export class DataValidationController {
  private validationService: DataValidationService;

  constructor(private prisma: PrismaClient) {
    const geocodingService = new (require('../services/geocoding.service').GeocodingService)(prisma);
    this.validationService = new DataValidationService(prisma, geocodingService);
  }

  validateData = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = (req as AuthenticatedRequest).user.tenantId.toString();

      const result = await this.validationService.validateData(tenantId);

      res.json({
        success: true,
        data: result
      });
    } catch (error: any) {
      logger.error('Data validation failed:', error);
      res.status(500).json({
        success: false,
        error: 'Data validation failed',
        message: error.message
      });
    }
  };

  fixIssue = async (req: Request, res: Response): Promise<void> => {
    try {
      const { issueType, entityId, actionData } = req.body;
      let success = false;

      switch (issueType) {
        case 'missing_postcode':
        case 'missing_location':
          success = await this.validationService.geocodeClient(entityId);
          break;
        case 'missing_skills':
          success = await this.validationService.addCarerSkill(entityId, actionData.skill);
          break;
        default:
          res.status(400).json({
            success: false,
            error: 'Unsupported action type'
          });
          return;
      }

      res.json({
        success: true,
        data: { fixed: success }
      });
    } catch (error: any) {
      logger.error('Fix issue failed:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to fix issue',
        message: error.message
      });
    }
  };
}