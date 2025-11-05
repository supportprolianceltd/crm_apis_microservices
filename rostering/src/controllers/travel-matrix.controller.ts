import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { TravelMatrixService } from '../services/travel-matrix.service';
import { logger } from '../utils/logger';

interface AuthenticatedRequest extends Request {
  user: {
    id: string;
    email: string;
    tenantId: string;
  };
}

export class TravelMatrixController {
  private travelMatrixService: TravelMatrixService;

  constructor(private prisma: PrismaClient) {
    this.travelMatrixService = new TravelMatrixService(prisma);
  }

  getTravelTime = async (req: Request, res: Response): Promise<void> => {
    try {
      const { fromPostcode, toPostcode } = req.query;
      
      if (!fromPostcode || !toPostcode) {
        res.status(400).json({
          success: false,
          error: 'fromPostcode and toPostcode are required'
        });
        return;
      }

      const travelTime = await this.travelMatrixService.getTravelTime(
        fromPostcode as string, 
        toPostcode as string
      );

      res.json({
        success: true,
        data: travelTime
      });
    } catch (error: any) {
      logger.error('Failed to get travel time:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get travel time',
        message: error.message
      });
    }
  };

  // Add other methods for batch updates, cache stats, etc.
}