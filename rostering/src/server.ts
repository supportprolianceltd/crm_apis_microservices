import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import dotenv from 'dotenv';
import { PrismaClient } from '@prisma/client';

import { logger, logRequest } from './utils/logger';
import { GeocodingService } from './services/geocoding.service';
import { EmailService } from './services/email.service';
import { MatchingService } from './services/matching.service';
import { AuthSyncService } from './services/auth-sync.service';
import { NotificationService } from './services/notification.service';
import { TenantEmailConfigService } from './services/tenant-email-config.service';
import { RequestController } from './controllers/request.controller';
import { CarerController } from './controllers/carer.controller';
import { createRequestRoutes } from './routes/request.routes';
import { createCarerRoutes } from './routes/carer.routes';
import { createSyncRoutes } from './routes/sync.routes';
import { createHealthRoutes } from './routes/health.routes';
import { createEmailRoutes } from './routes/email.routes';
import { EmailWorker } from './workers/email.worker';

// Load environment variables
dotenv.config();

class RosteringServer {
  private app: Application;
  private prisma: PrismaClient;
  private geocodingService: GeocodingService;
  private emailService: EmailService;
  private matchingService: MatchingService;
  private authSyncService: AuthSyncService;
  private notificationService: NotificationService;
  private tenantEmailConfigService: TenantEmailConfigService;
  private emailWorker: EmailWorker;
  private requestController: RequestController;
  private carerController: CarerController;

  constructor() {
    this.app = express();
    this.prisma = new PrismaClient();
    this.geocodingService = new GeocodingService(this.prisma);
    this.tenantEmailConfigService = new TenantEmailConfigService(this.prisma);
    this.notificationService = new NotificationService();
    this.emailService = new EmailService(this.prisma, this.tenantEmailConfigService, this.notificationService);
    this.authSyncService = new AuthSyncService(this.prisma, this.geocodingService);
    this.matchingService = new MatchingService(this.prisma, this.geocodingService);
    this.emailWorker = new EmailWorker(
      this.prisma,
      this.emailService,
      this.matchingService,
      this.tenantEmailConfigService,
      this.notificationService
    );
    this.requestController = new RequestController(
      this.prisma, 
      this.geocodingService, 
      this.matchingService
    );
    this.carerController = new CarerController(this.prisma);

    this.setupMiddleware();
    this.setupRoutes();
    this.setupErrorHandling();
  }

  private setupMiddleware(): void {
    // Security middleware
    this.app.use(helmet({
      crossOriginEmbedderPolicy: false,
    }));

    // CORS configuration
    this.app.use(cors({
      origin: process.env.CORS_ORIGIN || '*',
      credentials: true,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With']
    }));

    // Compression
    this.app.use(compression());

    // Rate limiting
    const limiter = rateLimit({
      windowMs: 15 * 60 * 1000, // 15 minutes
      max: 100, // limit each IP to 100 requests per windowMs
      message: {
        error: 'Too many requests',
        message: 'Please try again later'
      },
      standardHeaders: true,
      legacyHeaders: false,
    });
    this.app.use(limiter);

    // Body parsing
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // Request logging middleware
    this.app.use((req: Request, res: Response, next: NextFunction) => {
      const start = Date.now();
      
      res.on('finish', () => {
        const responseTime = Date.now() - start;
        logRequest(req, res, responseTime);
      });
      
      next();
    });
  }

  private setupRoutes(): void {
    // Health routes
    this.app.use('/api/v1', createHealthRoutes());

    // API routes
    this.app.use('/api/v1/requests', createRequestRoutes(this.requestController));
    this.app.use('/api/v1/carers', createCarerRoutes(this.carerController));
    this.app.use('/api/v1/sync', createSyncRoutes(
      this.prisma,
      this.authSyncService, 
      this.tenantEmailConfigService,
      this.notificationService
    ));
    this.app.use('/api/v1/emails', createEmailRoutes(
      this.prisma,
      this.emailService,
      this.emailWorker
    ));

    // Root endpoint
    this.app.get('/', (req: Request, res: Response) => {
      res.json({
        service: 'rostering-service',
        version: '1.0.0',
        timestamp: new Date().toISOString(),
        documentation: '/api/v1/health'
      });
    });

    // 404 handler
    this.app.use('*', (req: Request, res: Response) => {
      res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Route ${req.method} ${req.originalUrl} not found`,
        timestamp: new Date().toISOString()
      });
    });
  }

  private setupErrorHandling(): void {
    // Global error handler
    this.app.use((error: Error, req: Request, res: Response, next: NextFunction) => {
      logger.error('Unhandled error:', {
        error: error.message,
        stack: error.stack,
        url: req.url,
        method: req.method,
        body: req.body,
        user: req.user
      });

      res.status(500).json({
        success: false,
        error: 'Internal Server Error',
        message: process.env.NODE_ENV === 'development' ? error.message : 'Something went wrong',
        timestamp: new Date().toISOString()
      });
    });

    // Handle unhandled promise rejections
    process.on('unhandledRejection', (reason: any, promise: Promise<any>) => {
      logger.error('Unhandled Promise Rejection:', { reason, promise });
    });

    // Handle uncaught exceptions
    process.on('uncaughtException', (error: Error) => {
      logger.error('Uncaught Exception:', error);
      process.exit(1);
    });

    // Graceful shutdown
    process.on('SIGTERM', () => {
      logger.info('SIGTERM received, starting graceful shutdown');
      this.shutdown();
    });

    process.on('SIGINT', () => {
      logger.info('SIGINT received, starting graceful shutdown');
      this.shutdown();
    });
  }

  public async start(port: number = 3005): Promise<void> {
    try {
      // Connect to database
      await this.prisma.$connect();
      logger.info('Connected to database');

      // Start email worker
      this.emailWorker.start();
      logger.info('Email worker started');

      // Start server
      this.app.listen(port, () => {
        logger.info(`Rostering service started on port ${port}`, {
          port,
          environment: process.env.NODE_ENV || 'development',
          timestamp: new Date().toISOString()
        });
      });

    } catch (error) {
      logger.error('Failed to start server:', error);
      process.exit(1);
    }
  }

  private async shutdown(): Promise<void> {
    try {
      logger.info('Starting graceful shutdown...');

      // Stop email worker
      this.emailWorker.stop();
      logger.info('Email worker stopped');

      // Close email connections
      await this.emailService.closeConnections();

      // Disconnect from database
      await this.prisma.$disconnect();
      logger.info('Disconnected from database');

      process.exit(0);
    } catch (error) {
      logger.error('Error during shutdown:', error);
      process.exit(1);
    }
  }
}

// Start server if this file is run directly
if (require.main === module) {
  const server = new RosteringServer();
  const port = parseInt(process.env.PORT || '3005', 10);
  server.start(port);
}

export default RosteringServer;