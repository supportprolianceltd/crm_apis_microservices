// src/controllers/demo.controller.ts
import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { logger } from '../utils/logger';
import { generateUniqueRequestId } from '../utils/idGenerator';

export class DemoController {
  constructor(private prisma: PrismaClient) {}

  // Seed all demo data
  seedAll = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = '4';

      logger.info('Starting demo data seeding', { tenantId });

      // Direct seeding implementation

      // Cleanup existing data
      await this.cleanup(tenantId as string);

      // Seed constraints
      logger.info('Seeding constraints...');
      await this.prisma.rosteringConstraints.create({
        data: {
          tenantId,
          travelMaxMinutes: 90,
          bufferMinutes: 15
        }
      });

      // Seed carers
      logger.info('Seeding carers...');
      const carers = [
        { firstName: 'Robert', lastName: 'Johnson', postcode: 'NW4', experience: 8 },
        { firstName: 'Christine', lastName: 'Williams', postcode: 'NW4', experience: 12 },
        { firstName: 'Hasan', lastName: 'Ahmed', postcode: 'HA2', experience: 5 },
        { firstName: 'Olivia', lastName: 'Martinez', postcode: 'W5', experience: 6 },
        { firstName: 'Janet', lastName: 'Thompson', postcode: 'NW10', experience: 15 },
        { firstName: 'Daniel', lastName: 'Brown', postcode: 'HA2', experience: 4 },
        { firstName: 'Sarah', lastName: 'Davis', postcode: 'N12', experience: 10 },
        { firstName: 'Michael', lastName: 'Wilson', postcode: 'HA5', experience: 9 },
      ];

      for (const carerData of carers) {
        await this.prisma.carer.create({
          data: {
            tenantId,
            firstName: carerData.firstName,
            lastName: carerData.lastName,
            email: `${carerData.firstName.toLowerCase()}.${carerData.lastName.toLowerCase()}@example.com`,
            address: `${carerData.postcode}, London`,
            postcode: carerData.postcode,
            experience: carerData.experience,
            skills: ['Personal Care', 'Medication Administration'],
            isActive: true,
            maxTravelDistance: 15000
          }
        });
      }

      // Seed visits
      logger.info('Seeding visits...');
      const baseDate = new Date();
      baseDate.setHours(0, 0, 0, 0);

      const visits = [
        {
          subject: 'Personal Care - Morning',
          requestorName: 'Margaret Smith',
          requestorEmail: 'margaret.smith@example.com',
          address: '25 Hendon Lane, London',
          postcode: 'NW4 3TA',
          requirements: 'Personal Care, Medication Administration',
          urgency: 'MEDIUM',
          scheduledStartTime: new Date(baseDate.getTime() + (9 * 60 * 60 * 1000)),
          estimatedDuration: 45,
          status: 'APPROVED'
        },
        {
          subject: 'Dementia Support',
          requestorName: 'Arthur Johnson',
          requestorEmail: 'arthur.johnson@example.com',
          address: '42 Finchley Road, London',
          postcode: 'NW4 2BJ',
          requirements: 'Dementia Care, Personal Care',
          urgency: 'MEDIUM',
          scheduledStartTime: new Date(baseDate.getTime() + (10 * 60 * 60 * 1000)),
          estimatedDuration: 60,
          status: 'APPROVED'
        }
      ];

      for (const visitData of visits) {
        const requestId = await generateUniqueRequestId(async (id: string) => {
          const existing = await this.prisma.externalRequest.findUnique({
            where: { id },
            select: { id: true }
          });
          return !!existing;
        });
        await this.prisma.externalRequest.create({
          data: {
            id: requestId,
            ...visitData,
            tenantId: tenantId,
            content: visitData.subject,
            sendToRostering: true,
            urgency: visitData.urgency as any,
            status: visitData.status as any
          }
        });
      }

      logger.info('Demo data seeding completed successfully');

      res.json({
        success: true,
        message: 'Demo data seeded successfully',
        data: {
          tenantId: tenantId,
          carersCount: carers.length,
          visitsCount: 'seeded',
          timestamp: new Date().toISOString()
        }
      });

    } catch (error: any) {
      logger.error('Failed to seed demo data:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to seed demo data',
        message: error.message
      });
    }
  };

  // Get demo status
  getDemoStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = '4'; // Fixed for demo

      // Check if demo data exists
      const carersCount = await this.prisma.carer.count({
        where: { tenantId: tenantId as string }
      });

      const visitsCount = await this.prisma.externalRequest.count({
        where: { tenantId: tenantId as string }
      });

      const constraintsCount = await this.prisma.rosteringConstraints.count({
        where: { tenantId: tenantId as string }
      });

      const readyForDemo = carersCount > 0 && visitsCount > 0 && constraintsCount > 0;

      res.json({
        success: true,
        data: {
          tenantId: tenantId,
          readyForDemo,
          counts: {
            carers: carersCount,
            visits: visitsCount,
            constraints: constraintsCount
          },
          timestamp: new Date().toISOString()
        }
      });

    } catch (error: any) {
      logger.error('Failed to get demo status:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to get demo status',
        message: error.message
      });
    }
  };

  // Clear demo data
  clearDemoData = async (req: Request, res: Response): Promise<void> => {
    try {
      const tenantId = '4'; // Fixed for demo

      logger.info('Clearing demo data', { tenantId });

      await this.cleanup(tenantId);

      res.json({
        success: true,
        message: 'Demo data cleared successfully',
        data: {
          tenantId,
          timestamp: new Date().toISOString()
        }
      });

    } catch (error: any) {
      logger.error('Failed to clear demo data:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to clear demo data',
        message: error.message
      });
    }
  };

  // Cleanup helper method
  private cleanup = async (tenantId: string): Promise<void> => {
    logger.info('Cleaning up existing demo data', { tenantId });

    const deleteOps = [
      this.prisma.requestCarerMatch.deleteMany({ where: { tenantId } }),
      this.prisma.assignment.deleteMany({ where: { tenantId } }),
      this.prisma.externalRequest.deleteMany({ where: { tenantId } }),
      this.prisma.carer.deleteMany({ where: { tenantId } }),
      this.prisma.rosteringConstraints.deleteMany({ where: { tenantId } }),
      this.prisma.travelMatrixCache.deleteMany()
    ];

    await this.prisma.$transaction(deleteOps);
    logger.info('Demo data cleanup completed');
  };
}