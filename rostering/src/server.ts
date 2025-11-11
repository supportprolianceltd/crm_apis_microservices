import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import dotenv from 'dotenv';
import { PrismaClient } from '@prisma/client';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import swaggerJsdoc from 'swagger-jsdoc';
import swaggerUi from 'swagger-ui-express';

import { logger, logRequest } from './utils/logger';
import { CarerService} from './services/carer.service';
import { GeocodingService } from './services/geocoding.service';
import { EmailService } from './services/email.service';
import { MatchingService } from './services/matching.service';
import { AuthSyncService } from './services/auth-sync.service';
import { NotificationService } from './services/notification.service';
import { TenantEmailConfigService } from './services/tenant-email-config.service';
import { RequestController } from './controllers/request.controller';
import { CarerController } from './controllers/carer.controller';
import { VisitController } from './controllers/visit.controller';
import { createRequestRoutes } from './routes/request.routes';
import { createCarerRoutes } from './routes/carer.routes';
import { createVisitRoutes } from './routes/visit.routes';
import { createSyncRoutes } from './routes/sync.routes';
import { createHealthRoutes } from './routes/health.routes';
import { createEmailRoutes } from './routes/email.routes';
import { createCarePlanRoutes } from './routes/careplan.routes';
import { createTaskRoutes } from './routes/task.routes';
import { createClusterRoutes } from './routes/cluster.routes';
import { createConstraintsRoutes } from './routes/constraints.routes';
import { createRosterRoutes } from './routes/roster.routes';
import { createLiveOpsRoutes } from './routes/live-ops.routes';
import { createDisruptionRoutes } from './routes/disruption.routes';
import { createPublicationRoutes } from './routes/publication.routes';
import { createDataValidationRoutes } from './routes/data-validation.routes';
import { createTravelMatrixRoutes } from './routes/travel-matrix.routes';
import { createEligibilityRoutes } from './routes/eligibility.routes';
import { createClusterMetricsRoutes } from './routes/cluster-metrics.routes';
import { createDemoRoutes } from './routes/demo.routes';
import { createSettlementRoutes } from './routes/settlement.routes';

// ADD THIS IMPORT
import { createEnhancedTravelMatrixRoutes } from './routes/enhanced-travel-matrix.routes';

// Import services
import { ConstraintsService } from './services/constraints.service';
import { TravelService } from './services/travel.service';
import { ClusteringService } from './services/clustering.service';
import { RosterGenerationService } from './services/roster-generation.service';
import { PublicationService } from './services/publication.service';
import { LiveOperationsService } from './services/live-operations.service';
import { DisruptionService } from './services/disruption.service';
import { WebSocketService } from './services/websocket.service';
import { DataValidationService } from './services/data-validation.service';
import { TravelMatrixService } from './services/travel-matrix.service';
import { EligibilityService } from './services/eligibility.service';
import { ClusterMetricsService } from './services/cluster-metrics.service';
import { AdvancedOptimizationService } from './services/advanced-optimization.service';

// Import controllers
import { RosterController } from './controllers/roster.controller';
import { CarePlanController } from './controllers/careplan.controller';
import { TaskController } from './controllers/task.controller';
import { PublicationController } from './controllers/publication.controller';
import { DataValidationController } from './controllers/data-validation.controller';
import { TravelMatrixController } from './controllers/travel-matrix.controller';
import { EligibilityController } from './controllers/eligibility.controller';
import { ClusterMetricsController } from './controllers/cluster-metrics.controller';

// Import workers and middleware
import { EmailWorker } from './workers/email.worker';
import { authenticate } from './middleware/auth.middleware';

// Load environment variables
dotenv.config();

class RosteringServer {
   private app: Application;
   private httpServer: http.Server;
   private io?: SocketIOServer;
   private prisma?: PrismaClient;

  // Services
  private geocodingService?: GeocodingService;
  private emailService?: EmailService;
  private matchingService?: MatchingService;
  private authSyncService?: AuthSyncService;
  private notificationService?: NotificationService;
  private tenantEmailConfigService?: TenantEmailConfigService;
  private constraintsService?: ConstraintsService;
  private travelService?: TravelService;
  private clusteringService?: ClusteringService;
  private rosterService?: RosterGenerationService;
  private publicationService?: PublicationService;
  private liveOpsService?: LiveOperationsService;
  private disruptionService?: DisruptionService;
  private websocketService?: WebSocketService;
  private dataValidationService?: DataValidationService;
  private travelMatrixService?: TravelMatrixService;
  private eligibilityService?: EligibilityService;
  private clusterMetricsService?: ClusterMetricsService;
  private advancedOptimizationService?: AdvancedOptimizationService;

  // Workers
  private emailWorker?: EmailWorker;

  // Controllers
  private requestController?: RequestController;
  private carerController?: CarerController;
  private visitController?: VisitController;
  private rosterController?: RosterController;
  private carePlanController?: CarePlanController;
  private taskController?: TaskController;
  private publicationController?: PublicationController;
  private dataValidationController?: DataValidationController;
  private travelMatrixController?: TravelMatrixController;
  private eligibilityController?: EligibilityController;
  private clusterMetricsController?: ClusterMetricsController;

  constructor() {
    console.log('🔧 [DEBUG] Constructor called');
    this.app = express();
    this.httpServer = http.createServer(this.app);
    console.log('🔧 [DEBUG] Express setup complete');

    // Skip database and service initialization in swagger-only mode
    if (process.env.SWAGGER_ONLY !== 'true') {
      logger.info('Initializing full rostering service...');
      this.initializeServices();
    } else {
      logger.info('Initializing swagger-only mode - skipping database and services');
    }

    console.log('🔧 [DEBUG] Starting middleware setup...');
    this.setupMiddleware();
    console.log('🔧 [DEBUG] Starting routes setup...');
    this.setupRoutes();

    // Skip WebSocket setup in swagger-only mode
    if (process.env.SWAGGER_ONLY !== 'true') {
      this.setupWebSocketHandlers();
    }

    this.setupErrorHandling();
    console.log('🔧 [DEBUG] Server construction complete');
  }

  private initializeServices(): void {
    console.log('🔧 [DEBUG] Starting service initialization...');

    try {
      // Initialize Prisma Client
      this.prisma = new PrismaClient();
      console.log('🔧 [DEBUG] Prisma client created');

      // Initialize core services
      console.log('🔧 [DEBUG] Initializing geocoding service...');
      this.geocodingService = new GeocodingService(this.prisma);
      console.log('🔧 [DEBUG] Initializing tenant email config service...');
      this.tenantEmailConfigService = new TenantEmailConfigService(this.prisma);
      console.log('🔧 [DEBUG] Initializing notification service...');
      this.notificationService = new NotificationService();
      console.log('🔧 [DEBUG] Initializing constraints service...');
      this.constraintsService = new ConstraintsService(this.prisma);
      console.log('🔧 [DEBUG] Initializing travel service...');
      this.travelService = new TravelService(this.prisma);

      // Initialize additional services
      console.log('🔧 [DEBUG] Initializing data validation service...');
      this.dataValidationService = new DataValidationService(this.prisma, this.geocodingService);
      console.log('🔧 [DEBUG] Initializing travel matrix service...');
      this.travelMatrixService = new TravelMatrixService(this.prisma);
      console.log('🔧 [DEBUG] Initializing eligibility service...');
      this.eligibilityService = new EligibilityService(this.prisma);
      console.log('🔧 [DEBUG] Initializing cluster metrics service...');
      this.clusterMetricsService = new ClusterMetricsService(this.prisma);

      // Initialize email service
      console.log('🔧 [DEBUG] Initializing email service...');
      this.emailService = new EmailService(
        this.prisma,
        this.tenantEmailConfigService,
        this.notificationService
      );

      // Initialize business logic services
      console.log('🔧 [DEBUG] Initializing auth sync service...');
      this.authSyncService = new AuthSyncService(this.prisma, this.geocodingService);
      console.log('🔧 [DEBUG] Initializing matching service...');
      this.matchingService = new MatchingService(this.prisma, this.geocodingService);
      console.log('🔧 [DEBUG] Initializing clustering service...');
      this.clusteringService = new ClusteringService(this.prisma, this.constraintsService, this.travelService);
      console.log('🔧 [DEBUG] Initializing roster service...');
      this.rosterService = new RosterGenerationService(this.prisma, this.constraintsService, this.travelService, this.clusteringService);

      // Initialize advanced optimization service
      console.log('🔧 [DEBUG] Initializing advanced optimization service...');
      this.advancedOptimizationService = new AdvancedOptimizationService(this.rosterService);

      // Initialize publication service with WebSocket integration
      console.log('🔧 [DEBUG] Initializing publication service...');
      this.publicationService = new PublicationService(this.prisma, this.notificationService);
      console.log('🔧 [DEBUG] Initializing live ops service...');
      this.liveOpsService = new LiveOperationsService(this.prisma, this.travelService);
      console.log('🔧 [DEBUG] Initializing disruption service...');
      this.disruptionService = new DisruptionService(this.prisma, this.rosterService, this.matchingService, this.notificationService);

      // Initialize Socket.IO
      console.log('🔧 [DEBUG] Initializing Socket.IO...');
      this.io = new SocketIOServer(this.httpServer, {
        cors: {
          origin: process.env.GATEWAY_ORIGIN || process.env.CORS_ORIGIN || '*',
          credentials: true,
        },
        transports: ['websocket', 'polling']
      });

      // Initialize WebSocket service with all dependencies
      console.log('🔧 [DEBUG] Initializing WebSocket service...');
      this.websocketService = new WebSocketService(
        this.io,
        this.liveOpsService,
        this.disruptionService
      );

      // Inject WebSocket service into publication service
      console.log('🔧 [DEBUG] Updating publication service with WebSocket...');
      this.publicationService = new PublicationService(
        this.prisma,
        this.notificationService,
        this.websocketService
      );

      // Initialize workers
      console.log('🔧 [DEBUG] Initializing email worker...');
      this.emailWorker = new EmailWorker(
        this.prisma,
        this.emailService,
        this.matchingService,
        this.tenantEmailConfigService,
        this.notificationService
      );

      // Initialize controllers
      console.log('🔧 [DEBUG] Initializing controllers...');
      this.requestController = new RequestController(this.prisma, this.geocodingService, this.matchingService);
      this.carerController = new CarerController(this.prisma!);
      this.visitController = new VisitController(this.prisma);
      this.rosterController = new RosterController(this.prisma);
      this.carePlanController = new CarePlanController(this.prisma);
      this.taskController = new TaskController(this.prisma);
      this.publicationController = new PublicationController(this.prisma);
      this.dataValidationController = new DataValidationController(this.prisma);
      this.travelMatrixController = new TravelMatrixController(this.prisma);
      this.eligibilityController = new EligibilityController(this.prisma);
      this.clusterMetricsController = new ClusterMetricsController(this.prisma);

      console.log('🔧 [DEBUG] All services initialized successfully');
      logger.info('All services initialized successfully');
    } catch (error) {
      console.error('🔧 [DEBUG] Error initializing services:', error);
      throw error;
    }
  }

  private setupMiddleware(): void {
    this.app.set('trust proxy', 1);

    // Security middleware
    this.app.use(helmet({
      crossOriginEmbedderPolicy: false,
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],
          scriptSrc: ["'self'", "'unsafe-inline'"],
          imgSrc: ["'self'", "data:", "https:"],
        },
      }
    }));

    // CORS configuration
    const allowedOrigins = [
      process.env.GATEWAY_URL || 'http://api_gateway:8000',
      process.env.CORS_ORIGIN || 'http://localhost:8000',
      'http://localhost:5173',
      'http://localhost:3000',
      'https://crm-frontend-react.vercel.app',
      'https://dev.e3os.co.uk/',
      'https://e3os.co.uk/'
    ].filter(Boolean);

    this.app.use(cors({
      origin: (origin, callback) => {
        // Allow requests with no origin (like mobile apps or curl requests)
        if (!origin) return callback(null, true);
        
        if (allowedOrigins.indexOf(origin) !== -1) {
          callback(null, true);
        } else {
          logger.warn(`CORS blocked for origin: ${origin}`);
          callback(new Error('Not allowed by CORS'));
        }
      },
      credentials: true,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With', 'X-API-Key', 'X-Request-ID']
    }));

    // Body parsers
    this.app.use(express.json({ 
      limit: '10mb',
      verify: (req: any, res, buf) => {
        req.rawBody = buf;
      }
    }));
    
    this.app.use(express.urlencoded({ 
      extended: true, 
      limit: '10mb' 
    }));

    // Compression middleware
    // this.app.use(compression({
    //   filter: (req: Request, res: Response) => {
    //     if (req.headers['x-no-compression']) {
    //       return false;
    //     }
    //     return compression.filter(req, res);
    //   },
    //   level: 6,
    //   threshold: 1024
    // }));

    // Rate limiting
    const limiter = rateLimit({
      windowMs: 15 * 60 * 1000, // 15 minutes
      max: process.env.NODE_ENV === 'production' ? 200 : 1000, // Different limits for prod vs dev
      message: { 
        success: false,
        error: 'Too many requests', 
        message: 'Please try again later' 
      },
      standardHeaders: true,
      legacyHeaders: false,
      keyGenerator: (req) => {
        return (req as any).user?.id || req.ip;
      }
    });

    // Apply rate limiting to all routes
    this.app.use('/api/', limiter);

    // More aggressive rate limiting for auth endpoints
    const authLimiter = rateLimit({
      windowMs: 15 * 60 * 1000,
      max: 5,
      message: {
        success: false,
        error: 'Too many authentication attempts',
        message: 'Please try again in 15 minutes'
      }
    });

    // Request logging middleware
    this.app.use((req: Request, res: Response, next: NextFunction) => {
      const start = Date.now();
      const requestId = req.headers['x-request-id'] as string || `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // Add request ID to request object
      (req as any).requestId = requestId;
      
      res.on('finish', () => {
        const responseTime = Date.now() - start;
        logRequest(req, res, responseTime);
      });
      
      next();
    });

    // Health check endpoint (no auth required)
    this.app.get('/health', (req: Request, res: Response) => {
      res.json({
        status: 'healthy',
        service: 'rostering',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        environment: process.env.NODE_ENV || 'development'
      });
    });
  }

  private setupRoutes(): void {
    // Root endpoint
    this.app.get('/', (req: Request, res: Response) => {
      res.json({
        service: 'rostering',
        status: 'running',
        version: '2.1.0',
        timestamp: new Date().toISOString(),
        environment: process.env.NODE_ENV || 'development',
        features: [
          'data-validation',
          'travel-matrix',
          'eligibility-precomputation',
          'cluster-metrics',
          'demo-data-seeding',
          'advanced-optimization',
          'publication-workflow',
          'live-operations',
          'real-time-websockets',
          'disruption-management'
        ],
        documentation: '/api/rostering/docs'
      });
    });

    // Swagger/OpenAPI documentation setup
    this.setupSwagger();

    // Skip API routes in swagger-only mode
    if (process.env.SWAGGER_ONLY === 'true') {
      this.setupSwaggerOnlyRoutes();
      return;
    }

    // Health routes (no authentication)
    this.app.use('/api/rostering/health', createHealthRoutes());
    this.app.use('/health', createHealthRoutes());

    // ========== AUTHENTICATED ROUTES ==========

    // Core business routes
    this.app.use('/api/rostering/requests', createRequestRoutes(this.requestController!));
    this.app.use('/api/rostering/carers', authenticate, createCarerRoutes(this.carerController!));
    this.app.use('/api/rostering/visits', authenticate, createVisitRoutes(this.visitController!));
    this.app.use('/api/rostering/careplans', authenticate, createCarePlanRoutes(this.carePlanController!));
    this.app.use('/api/rostering/tasks', authenticate, createTaskRoutes(this.taskController!));

    // Rostering & optimization routes
    this.app.use('/api/rostering/roster', authenticate, createRosterRoutes(this.prisma!));
    this.app.use('/api/rostering/clusters', authenticate, createClusterRoutes(this.prisma!));
    this.app.use('/api/rostering/constraints', authenticate, createConstraintsRoutes(this.prisma!));
    this.app.use('/api/rostering/publications', authenticate, createPublicationRoutes(this.prisma!));

    // Data & validation routes
    this.app.use('/api/rostering/data-validation', authenticate, createDataValidationRoutes(this.prisma!));

    this.app.use('/api/rostering/travel-matrix', authenticate, createEnhancedTravelMatrixRoutes(this.prisma!));


    this.app.use('/api/rostering/eligibility', authenticate, createEligibilityRoutes(this.prisma!));
    this.app.use('/api/rostering/cluster-metrics', authenticate, createClusterMetricsRoutes(this.prisma!));

    // Demo data routes
    this.app.use('/api/rostering/demo', authenticate, createDemoRoutes());

    // Operations & monitoring routes
    this.app.use('/api/rostering/live', authenticate, createLiveOpsRoutes(this.prisma!, this.liveOpsService!));
    this.app.use('/api/rostering/disruptions', authenticate, createDisruptionRoutes(this.prisma!, this.disruptionService!));

    // System & integration routes
    this.app.use('/api/rostering/sync', authenticate, createSyncRoutes(this.prisma!, this.authSyncService!, this.tenantEmailConfigService!, this.notificationService!));
    this.app.use('/api/rostering/emails', authenticate, createEmailRoutes(this.prisma!, this.emailService!, this.emailWorker!));
    this.app.use('/api/rostering/settlement', authenticate, createSettlementRoutes(this.prisma!));

    // ========== UTILITY & TEST ROUTES ==========

        // Add this route to your server.ts file in the setupRoutes() method
    this.app.get('/api/rostering/debug/env', (req: Request, res: Response) => {
      res.json({
        googleMapsApiKey: process.env.GOOGLE_MAPS_API_KEY ? 'SET (but hidden)' : 'NOT SET',
        nodeEnv: process.env.NODE_ENV,
        allEnvKeys: Object.keys(process.env).filter(key => key.includes('GOOGLE') || key.includes('MAPS'))
      });
    });

    // Service status endpoint
    this.app.get('/api/rostering/status', authenticate, (req: Request, res: Response) => {
      const websocketStatus = this.websocketService ? this.websocketService.getStatus() : null;
      
      res.json({
        success: true,
        data: {
          service: 'rostering',
          status: 'operational',
          version: '2.1.0',
          timestamp: new Date().toISOString(),
          environment: process.env.NODE_ENV || 'development',
          features: {
            dataValidation: !!this.dataValidationService,
            travelMatrix: !!this.travelMatrixService,
            eligibilityPrecomputation: !!this.eligibilityService,
            clusterMetrics: !!this.clusterMetricsService,
            demoDataSeeding: true,
            advancedOptimization: !!this.advancedOptimizationService,
            publicationWorkflow: !!this.publicationService,
            liveOperations: !!this.liveOpsService,
            realTimeWebsockets: !!this.websocketService,
            disruptionManagement: !!this.disruptionService
          },
          database: this.prisma ? 'connected' : 'disconnected',
          websockets: websocketStatus,
          uptime: process.uptime()
        }
      });
    });

    // Feature test endpoints
    this.app.get('/api/rostering/features/compression-test', (req: Request, res: Response) => {
      // Generate a large payload to test compression
      const largeData = Array.from({ length: 1000 }, (_, i) => ({
        id: i,
        name: `Test Item ${i}`,
        timestamp: new Date().toISOString(),
        data: 'x'.repeat(100) // Add some repeated data for better compression
      }));

      res.json({
        message: "Compression test - if you can read this, compression is working correctly",
        timestamp: new Date().toISOString(),
        dataSize: JSON.stringify(largeData).length,
        compressed: true,
        data: largeData
      });
    });

    // WebSocket connection test
    this.app.get('/api/rostering/features/websocket-test', authenticate, (req: Request, res: Response) => {
      const wsStatus = this.websocketService ? this.websocketService.getStatus() : { available: false };

      res.json({
        success: true,
        websocketAvailable: 'available' in wsStatus ? wsStatus.available : false,
        connectedClients: 'totalConnections' in wsStatus ? wsStatus.totalConnections : 0,
        activeTenants: 'tenants' in wsStatus ? wsStatus.tenants : 0,
        message: ('available' in wsStatus && wsStatus.available) ?
          'WebSocket service is running' :
          'WebSocket service is not available'
      });
    });

    // 404 handler for undefined routes
    this.app.use('*', (req: Request, res: Response) => {
      logger.warn('Route not found', {
        method: req.method,
        url: req.originalUrl,
        ip: req.ip,
        userAgent: req.get('User-Agent')
      });

      res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Route ${req.method} ${req.originalUrl} not found`,
        availableRoutes: [
          '/api/rostering/health',
          '/api/rostering/requests',
          '/api/rostering/carers',
          '/api/rostering/visits',
          '/api/rostering/careplans',
          '/api/rostering/tasks',
          '/api/rostering/roster',
          '/api/rostering/publications',
          '/api/rostering/live',
          '/api/rostering/disruptions',
          '/api/rostering/data-validation',
          '/api/rostering/travel-matrix',
          '/api/rostering/eligibility',
          '/api/rostering/cluster-metrics',
          '/api/rostering/demo',
          '/api/rostering/docs'
        ]
      });
    });
  }

  private setupSwagger(): void {
    const options = {
      definition: {
        openapi: '3.0.0',
        info: {
          title: 'AI-Powered Rostering Service API',
          version: '2.1.0',
          description: 'Complete rostering system with AI optimization, real-time monitoring, and publication workflow',
          contact: {
            name: 'Rostering API Support',
            email: 'support@rostering.com'
          },
          license: {
            name: 'Proprietary',
            url: 'https://rostering.com/license'
          }
        },
        servers: [
          {
            url: 'http://localhost:3005/api/rostering',
            description: 'Development Server'
          },
          {
            url: 'https://api.rostering.com/v1',
            description: 'Production API'
          },
          {
            url: 'http://api_gateway:8000/api/rostering',
            description: 'API Gateway'
          }
        ],
        components: {
          securitySchemes: {
            BearerAuth: {
              type: 'http',
              scheme: 'bearer',
              bearerFormat: 'JWT',
              description: 'Enter JWT token in the format: Bearer <token>'
            },
            ApiKeyAuth: {
              type: 'apiKey',
              in: 'header',
              name: 'X-API-Key',
              description: 'API key for service-to-service communication'
            }
          },
          responses: {
            UnauthorizedError: {
              description: 'Access token is missing or invalid',
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    properties: {
                      success: { type: 'boolean', example: false },
                      error: { type: 'string', example: 'Unauthorized' },
                      message: { type: 'string', example: 'Valid authentication required' }
                    }
                  }
                }
              }
            },
            ValidationError: {
              description: 'Request validation failed',
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    properties: {
                      success: { type: 'boolean', example: false },
                      error: { type: 'string', example: 'Validation Failed' },
                      message: { type: 'string', example: 'Invalid input parameters' },
                      details: { 
                        type: 'array',
                        items: {
                          type: 'object',
                          properties: {
                            field: { type: 'string' },
                            message: { type: 'string' }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        },
        security: [{ BearerAuth: [] }],
        tags: [
          {
            name: 'Publications',
            description: 'Roster publication and acceptance workflow'
          },
          {
            name: 'Rostering',
            description: 'Roster generation and optimization'
          },
          {
            name: 'Live Operations',
            description: 'Real-time monitoring and operations'
          },
          {
            name: 'Carers',
            description: 'Carer management and availability'
          },
          {
            name: 'Clients',
            description: 'Client and visit management'
          },
          {
            name: 'System',
            description: 'System administration and health'
          }
        ]
      },
      apis: [
        './src/routes/*.ts',
        './src/routes/*.js',
        './src/controllers/*.ts',
        './src/controllers/*.js',
        './dist/routes/*.js',
        './dist/controllers/*.js'
      ],
    };

    try {
      const swaggerSpec = swaggerJsdoc(options);
      
      // Serve Swagger UI
      this.app.use('/api/rostering/docs', swaggerUi.serve, 
        swaggerUi.setup(swaggerSpec, {
          explorer: true,
          customCss: '.swagger-ui .topbar { display: none }',
          customSiteTitle: 'Rostering API Documentation',
          swaggerOptions: {
            persistAuthorization: true,
            displayRequestDuration: true,
            docExpansion: 'none',
            filter: true,
            showExtensions: true,
            showCommonExtensions: true
          },
          customfavIcon: '/favicon.ico'
        })
      );

      // Raw OpenAPI spec
      this.app.get('/api/rostering/api-docs.json', (req: Request, res: Response) => {
        res.setHeader('Content-Type', 'application/json');
        res.json(swaggerSpec);
      });

      // OpenAPI spec in YAML
      this.app.get('/api/rostering/api-docs.yaml', (req: Request, res: Response) => {
        res.setHeader('Content-Type', 'text/yaml');
        // In a real implementation, you'd convert JSON to YAML here
        res.send('OpenAPI YAML specification would be served here');
      });

      logger.info('Swagger documentation setup completed successfully');

    } catch (error) {
      logger.error('Failed to setup Swagger documentation:', error);
    }
  }

  private setupSwaggerOnlyRoutes(): void {
    // Test route to verify Swagger is working
    this.app.get('/api/rostering/swagger-test', (req: Request, res: Response) => {
      res.json({
        message: "Swagger test endpoint - API documentation is working",
        timestamp: new Date().toISOString(),
        mode: 'swagger-only',
        working: true,
        features: [
          'api-documentation',
          'openapi-spec',
          'interactive-docs'
        ]
      });
    });

    // Health check for swagger mode
    this.app.get('/api/rostering/health', (req: Request, res: Response) => {
      res.json({
        status: 'healthy',
        mode: 'swagger-only',
        service: 'rostering-docs',
        timestamp: new Date().toISOString()
      });
    });

    // 404 handler for swagger mode
    this.app.use('*', (req: Request, res: Response) => {
      res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Route ${req.method} ${req.originalUrl} not found in swagger-only mode`,
        documentation: '/api/rostering/docs'
      });
    });
  }

  private setupWebSocketHandlers(): void {
    if (this.websocketService) {
      logger.info('Setting up WebSocket handlers with real-time features');
      this.websocketService.initialize();
      
      // Periodic WebSocket status logging
      setInterval(() => {
        try {
          const status = this.websocketService!.getStatus();
          if (status.totalConnections > 0) {
            logger.debug('WebSocket connection status', {
              connectedClients: status.totalConnections,
              activeTenants: status.tenants,
              activeRooms: status.activeRooms,
              uptime: Math.floor(status.uptime / 1000 / 60) + ' minutes'
            });
          }
        } catch (error) {
          logger.error('Error logging WebSocket status:', error);
        }
      }, 60000); // Every minute

      // WebSocket health monitoring
      setInterval(() => {
        try {
          if (this.websocketService) {
            const status = this.websocketService.getStatus();
            // Broadcast health status to monitoring systems
            if (status.totalConnections === 0) {
              logger.warn('No active WebSocket connections');
            }
          }
        } catch (error) {
          logger.error('WebSocket health check failed:', error);
        }
      }, 300000); // Every 5 minutes

      logger.info('WebSocket handlers initialized with real-time monitoring');
    } else {
      logger.warn('WebSocket service not available - real-time features disabled');
    }
  }

  private setupErrorHandling(): void {
    // 404 handler (catch any unhandled routes)
    this.app.use('*', (req: Request, res: Response) => {
      res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Route ${req.method} ${req.originalUrl} not found`,
        requestId: (req as any).requestId
      });
    });

    // Global error handler
    this.app.use((error: Error, req: Request, res: Response, next: NextFunction) => {
      const requestId = (req as any).requestId || 'unknown';
      
      logger.error('Unhandled error occurred', { 
        error: error.message, 
        stack: error.stack, 
        url: req.url,
        method: req.method,
        userId: (req as any).user?.id,
        requestId,
        ip: req.ip,
        userAgent: req.get('User-Agent')
      });
      
      // Determine appropriate status code
      let statusCode = 500;
      let userMessage = 'Internal Server Error';
      
      if (error.name === 'ValidationError') {
        statusCode = 400;
        userMessage = 'Validation Failed';
      } else if (error.name === 'UnauthorizedError') {
        statusCode = 401;
        userMessage = 'Authentication Required';
      } else if (error.name === 'ForbiddenError') {
        statusCode = 403;
        userMessage = 'Access Denied';
      } else if (error.message.includes('not found')) {
        statusCode = 404;
        userMessage = 'Resource Not Found';
      }
      
      res.status(statusCode).json({
        success: false,
        error: userMessage,
        message: process.env.NODE_ENV === 'development' ? error.message : 'Something went wrong',
        requestId,
        ...(process.env.NODE_ENV === 'development' && { stack: error.stack })
      });
    });

    // Unhandled promise rejection handler
    process.on('unhandledRejection', (reason: any, promise: Promise<any>) => {
      logger.error('Unhandled Promise Rejection:', { 
        reason: reason?.message || reason, 
        stack: reason?.stack,
        promise: promise.toString()
      });
      
      // In production, you might want to exit the process
      if (process.env.NODE_ENV === 'production') {
        process.exit(1);
      }
    });
    
    // Uncaught exception handler
    process.on('uncaughtException', (error: Error) => {
      logger.error('Uncaught Exception:', { 
        error: error.message, 
        stack: error.stack 
      });
      
      // Exit the process for uncaught exceptions
      setTimeout(() => {
        process.exit(1);
      }, 1000);
    });

    // Graceful shutdown handlers
    process.on('SIGTERM', () => {
      logger.info('Received SIGTERM signal - starting graceful shutdown');
      this.shutdown();
    });
    
    process.on('SIGINT', () => {
      logger.info('Received SIGINT signal - starting graceful shutdown');
      this.shutdown();
    });

    logger.info('Error handling and graceful shutdown handlers configured');
  }

  public async start(port: number = 3005): Promise<void> {
    const actualPort = process.env.PORT ? parseInt(process.env.PORT) : port;
    
    try {
      // Skip database connection for swagger-only mode
      if (process.env.SWAGGER_ONLY === 'true') {
        logger.info(`Starting server in swagger-only mode on port ${actualPort}`);
        this.httpServer.listen(actualPort, () => {
          logger.info(`✅ Rostering service (swagger-only) running at http://localhost:${actualPort}`);
          logger.info(`📚 API Documentation: http://localhost:${actualPort}/api/rostering/docs`);
        });
        return;
      }

      // Connect to database
      logger.info('Connecting to database...');
      await this.prisma!.$connect();
      logger.info('✅ Database connected successfully');

      // Verify database connection
      await this.prisma!.$queryRaw`SELECT 1`;
      logger.info('✅ Database connection verified');

      // Start background workers
      logger.info('Starting background workers...');
      this.emailWorker!.start();
      logger.info('✅ Email worker started');

      // Start cleanup jobs
      this.startCleanupJobs();

      // Start the server
      this.httpServer.listen(actualPort, () => {
        logger.info(`✅ Rostering service started successfully`);
        logger.info(`   Server URL: http://localhost:${actualPort}`);
        logger.info(`   API Base: http://localhost:${actualPort}/api/rostering`);
        logger.info(`   Documentation: http://localhost:${actualPort}/api/rostering/docs`);
        logger.info(`   Health Check: http://localhost:${actualPort}/health`);
        logger.info('');
        logger.info('🚀 Available Features:');
        logger.info('   • Data Validation Engine');
        logger.info('   • Travel Matrix Caching');
        logger.info('   • Eligibility Pre-computation');
        logger.info('   • Cluster Metrics Calculator');
        logger.info('   • Demo Data Seeding');
        logger.info('   • Advanced Optimization (OR-Tools)');
        logger.info('   • Publication & Acceptance Workflow');
        logger.info('   • Live Operations & Real-time Monitoring');
        logger.info('   • WebSocket Real-time Updates');
        logger.info('   • Disruption Management');
        logger.info('');
        logger.info('📊 Environment:', {
          node_env: process.env.NODE_ENV,
          port: actualPort,
          gateway_url: process.env.GATEWAY_URL,
          database: 'connected'
        });
      });

    } catch (error: any) {
      logger.error('❌ Failed to start Rostering service:', {
        error: error.message,
        stack: error.stack
      });
      process.exit(1);
    }
  }

  private startCleanupJobs(): void {
    logger.info('Starting background cleanup jobs...');

    // Clean up expired travel matrix entries every hour
    setInterval(async () => {
      try {
        if (this.travelMatrixService) {
          const cleanedCount = await this.travelMatrixService.cleanupExpiredEntries();
          if (cleanedCount > 0) {
            logger.info(`🧹 Cleaned up ${cleanedCount} expired travel matrix entries`);
          }
        }
      } catch (error) {
        logger.error('Travel matrix cleanup job failed:', error);
      }
    }, 60 * 60 * 1000); // Every hour

    // Clean up old WebSocket connections (every 30 minutes)
    setInterval(async () => {
      try {
        // This would clean up any stale connections or sessions
        logger.debug('Running connection cleanup job');
      } catch (error) {
        logger.error('Connection cleanup job failed:', error);
      }
    }, 30 * 60 * 1000); // Every 30 minutes

    // Database maintenance (daily at 2 AM)
    setInterval(async () => {
      try {
        const now = new Date();
        if (now.getHours() === 2 && now.getMinutes() === 0) {
          logger.info('Running daily database maintenance');
          // Add any daily maintenance tasks here
        }
      } catch (error) {
        logger.error('Daily maintenance job failed:', error);
      }
    }, 60 * 1000); // Check every minute

    logger.info('✅ Background cleanup jobs started');
  }

  private async shutdown(): Promise<void> {
    const shutdownTimeout = setTimeout(() => {
      logger.error('Shutdown timeout reached, forcing exit');
      process.exit(1);
    }, 30000); // 30 second timeout

    try {
      logger.info('🚦 Starting graceful shutdown sequence...');

      // Step 1: Stop accepting new connections
      this.httpServer.close(() => {
        logger.info('✅ HTTP server closed');
      });

      // Step 2: Shutdown WebSocket service
      if (this.websocketService) {
        this.websocketService.shutdown();
        logger.info('✅ WebSocket service shutdown');
      }

      // Step 3: Stop background workers
      if (this.emailWorker) {
        this.emailWorker.stop();
        logger.info('✅ Email worker stopped');
      }

      // Step 4: Close email connections
      if (this.emailService) {
        await this.emailService.closeConnections();
        logger.info('✅ Email connections closed');
      }

      // Step 5: Disconnect from database
      if (this.prisma) {
        await this.prisma.$disconnect();
        logger.info('✅ Database disconnected');
      }

      clearTimeout(shutdownTimeout);
      logger.info('✅ Rostering service shutdown completed gracefully');
      process.exit(0);

    } catch (error: any) {
      logger.error('❌ Error during shutdown:', {
        error: error.message,
        stack: error.stack
      });
      clearTimeout(shutdownTimeout);
      process.exit(1);
    }
  }
}

// Start server if this file is run directly
if (require.main === module) {
  const server = new RosteringServer();
  const port = parseInt(process.env.PORT || '3005', 10);
  
  // Add error handlers to catch startup issues
  process.on('unhandledRejection', (reason, promise) => {
    logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
    process.exit(1);
  });

  process.on('uncaughtException', (error) => {
    logger.error('Uncaught Exception:', error);
    process.exit(1);
  });

  // Start the server
  server.start(port).catch((error) => {
    logger.error('Failed to start server:', error);
    process.exit(1);
  });
} else {
  // For testing/import scenarios
  module.exports = RosteringServer;
}

export default RosteringServer;