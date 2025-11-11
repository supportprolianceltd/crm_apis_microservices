import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { EnhancedTravelService } from '../services/enhanced-travel.service';
import { TravelCalculationRequest } from '../types/travel-matrix.types';
import { logger } from '../utils/logger';

export class EnhancedTravelMatrixController {
  private travelService: EnhancedTravelService;

  constructor(private prisma: PrismaClient) {
    this.travelService = new EnhancedTravelService(prisma);
  }

  /**
   * POST /api/rostering/travel-matrix/calculate
   * Calculate travel time and distance between two locations
   */
  calculateTravel = async (req: Request, res: Response): Promise<void> => {
    try {
      const requestBody: TravelCalculationRequest = req.body;

      // Validate request body exists
      if (!requestBody || Object.keys(requestBody).length === 0) {
        res.status(400).json({
          success: false,
          error: 'Invalid Request',
          message: 'Request body is required'
        });
        return;
      }

      // Calculate travel
      const result = await this.travelService.calculateTravel(requestBody);

      res.status(200).json({
        success: true,
        data: result
      });

    } catch (error: any) {
      logger.error('Travel calculation failed:', error);

      // Determine appropriate status code
      let statusCode = 500;
      if (error.message.includes('Invalid') || error.message.includes('required')) {
        statusCode = 400;
      } else if (error.message.includes('Google Maps API')) {
        statusCode = 502; // Bad Gateway
      }

      res.status(statusCode).json({
        success: false,
        error: 'Travel Calculation Failed',
        message: error.message,
        ...(process.env.NODE_ENV === 'development' && { stack: error.stack })
      });
    }
  };

  /**
   * GET /api/rostering/travel-matrix/cache/stats
   * Get cache statistics
   */
  getCacheStats = async (req: Request, res: Response): Promise<void> => {
    try {
      const stats = await this.travelService.getCacheStats();

      res.status(200).json({
        success: true,
        data: stats
      });

    } catch (error: any) {
      logger.error('Failed to get cache stats:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to retrieve cache statistics',
        message: error.message
      });
    }
  };

  /**
   * DELETE /api/rostering/travel-matrix/cache/cleanup
   * Clean up expired cache entries
   */
  cleanupCache = async (req: Request, res: Response): Promise<void> => {
    try {
      const deletedCount = await this.travelService.cleanupExpiredCache();

      res.status(200).json({
        success: true,
        message: `Cleaned up ${deletedCount} expired cache entries`,
        data: { deletedCount }
      });

    } catch (error: any) {
      logger.error('Cache cleanup failed:', error);
      res.status(500).json({
        success: false,
        error: 'Cache cleanup failed',
        message: error.message
      });
    }
  };
}