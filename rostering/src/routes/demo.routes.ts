// src/routes/demo.routes.ts
import { Router } from 'express';
import { DemoController } from '../controllers/demo.controller';
import { PrismaClient } from '@prisma/client';

const router = Router();
const prisma = new PrismaClient();
const demoController = new DemoController(prisma);

/**
 * @swagger
 * /api/rostering/demo/seed-all:
 *   post:
 *     summary: Seed all demo data
 *     tags: [Demo]
 *     parameters:
 *       - in: query
 *         name: tenantId
 *         schema:
 *           type: string
 *         description: Tenant ID (default: '4')
 *         required: false
 *     responses:
 *       200:
 *         description: Demo data seeded successfully
 *       500:
 *         description: Failed to seed demo data
 */
router.post('/seed-all', demoController.seedAll);

/**
 * @swagger
 * /api/rostering/demo/status:
 *   get:
 *     summary: Get demo data status
 *     tags: [Demo]
 *     parameters:
 *       - in: query
 *         name: tenantId
 *         schema:
 *           type: string
 *         description: Tenant ID (default: '4')
 *         required: false
 *     responses:
 *       200:
 *         description: Demo status retrieved successfully
 *       500:
 *         description: Failed to get demo status
 */
router.get('/status', demoController.getDemoStatus);

/**
 * @swagger
 * /api/rostering/demo/clear:
 *   delete:
 *     summary: Clear all demo data
 *     tags: [Demo]
 *     parameters:
 *       - in: query
 *         name: tenantId
 *         schema:
 *           type: string
 *         description: Tenant ID (default: '4')
 *         required: false
 *     responses:
 *       200:
 *         description: Demo data cleared successfully
 *       500:
 *         description: Failed to clear demo data
 */
router.delete('/clear', demoController.clearDemoData);

export const createDemoRoutes = () => router;