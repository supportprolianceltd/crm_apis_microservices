import { Server as SocketIOServer, Socket } from 'socket.io';
import { LiveOperationsService } from './live-operations.service';
import { DisruptionService } from './disruption.service';
import { PublicationService } from './publication.service';
import { logger } from '../utils/logger';

export interface WebSocketClient {
  socketId: string;
  userId: string;
  tenantId: string;
  role: string;
  connectedAt: Date;
  rooms: string[];
  lastPing?: Date;
}

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: Date;
  from?: string;
}

export class WebSocketService {
  private clients: Map<string, WebSocketClient> = new Map();
  private tenantRooms: Map<string, Set<string>> = new Map();
  private carerRooms: Map<string, Set<string>> = new Map();
  private startTime: number = Date.now();
  private backgroundIntervals: NodeJS.Timeout[] = [];

  constructor(
    private io: SocketIOServer,
    private liveOpsService: LiveOperationsService,
    private disruptionService: DisruptionService,
    private publicationService?: PublicationService
  ) {}

  /**
   * Initialize WebSocket handlers with enhanced real-time features
   */
  initialize(): void {
    logger.info('Initializing WebSocket service with real-time features');

    this.io.on('connection', (socket: Socket) => {
      this.handleConnection(socket);
    });

    // Start background real-time updates
    this.startRealTimeUpdates();

    // Start connection health monitoring
    this.startHealthMonitoring();

    logger.info('WebSocket service initialized with real-time features');
  }

  /**
   * Handle new WebSocket connection with enhanced authentication
   */
  private handleConnection(socket: Socket): void {
    logger.info(`New WebSocket connection: ${socket.id}`, {
      headers: socket.handshake.headers,
      auth: socket.handshake.auth,
      query: socket.handshake.query
    });

    // Extract user info from handshake (would come from auth middleware)
    const userId = socket.handshake.auth.userId || socket.handshake.query.userId as string;
    const tenantId = socket.handshake.auth.tenantId || socket.handshake.query.tenantId as string;
    const role = socket.handshake.auth.role || socket.handshake.query.role as string || 'user';
    const userEmail = socket.handshake.auth.email || socket.handshake.query.email as string;

    if (!userId || !tenantId) {
      logger.warn('Connection rejected: missing auth info', { userId, tenantId });
      socket.emit('error', { 
        message: 'Authentication required',
        code: 'AUTH_REQUIRED'
      });
      socket.disconnect();
      return;
    }

    // Register client
    const client: WebSocketClient = {
      socketId: socket.id,
      userId,
      tenantId,
      role,
      connectedAt: new Date(),
      rooms: [],
      lastPing: new Date()
    };

    this.clients.set(socket.id, client);

    // Join tenant room
    const tenantRoom = `tenant:${tenantId}`;
    socket.join(tenantRoom);
    client.rooms.push(tenantRoom);

    // Join role-specific room
    const roleRoom = `role:${role}:${tenantId}`;
    socket.join(roleRoom);
    client.rooms.push(roleRoom);

    // Join carer-specific room if applicable
    if (role === 'carer') {
      const carerRoom = `carer:${userId}`;
      socket.join(carerRoom);
      client.rooms.push(carerRoom);

      // Track carer rooms for targeted broadcasts
      if (!this.carerRooms.has(userId)) {
        this.carerRooms.set(userId, new Set());
      }
      this.carerRooms.get(userId)!.add(socket.id);
    }

    // Add to tenant tracking
    if (!this.tenantRooms.has(tenantId)) {
      this.tenantRooms.set(tenantId, new Set());
    }
    this.tenantRooms.get(tenantId)!.add(socket.id);

    // Send welcome message with connection info
    socket.emit('connected', {
      socketId: socket.id,
      userId,
      tenantId,
      role,
      timestamp: new Date(),
      features: {
        realTimeUpdates: true,
        locationTracking: role === 'carer',
        dashboardAccess: role === 'coordinator',
        publicationNotifications: true
      }
    });

    // Send initial pending assignments if carer
    if (role === 'carer' && this.publicationService) {
      this.sendPendingAssignments(socket, client);
    }

    // Setup event handlers
    this.setupEventHandlers(socket, client);

    // Cleanup on disconnect
    socket.on('disconnect', (reason) => {
      this.handleDisconnection(socket, client, reason);
    });

    socket.on('error', (error) => {
      logger.error(`Socket error for client ${client.userId}:`, error);
    });

    logger.info(`Client connected: ${userId} (tenant: ${tenantId}, role: ${role}, email: ${userEmail})`);
  }

  /**
   * Setup comprehensive event handlers for a socket
   */
  private setupEventHandlers(socket: Socket, client: WebSocketClient): void {
    // Room management
    socket.on('subscribe', (data: { room: string }) => {
      this.handleSubscribe(socket, client, data.room);
    });

    socket.on('unsubscribe', (data: { room: string }) => {
      this.handleUnsubscribe(socket, client, data.room);
    });

    // Location and tracking (carers only)
    if (client.role === 'carer') {
      socket.on('location:update', async (data: {
        latitude: number;
        longitude: number;
        accuracy: number;
        batteryLevel?: number;
        activityType?: string;
      }) => {
        await this.handleLocationUpdate(socket, client, data);
      });

      socket.on('location:start_tracking', () => {
        this.handleStartTracking(socket, client);
      });

      socket.on('location:stop_tracking', () => {
        this.handleStopTracking(socket, client);
      });
    }

    // Visit operations (carers only)
    if (client.role === 'carer') {
      socket.on('visit:checkin', async (data: {
        visitId: string;
        latitude: number;
        longitude: number;
        notes?: string;
        photos?: string[];
      }) => {
        await this.handleCheckIn(socket, client, data);
      });

      socket.on('visit:checkout', async (data: {
        visitId: string;
        latitude: number;
        longitude: number;
        tasksCompleted?: string[];
        incidentReported?: boolean;
        incidentDetails?: string;
        notes?: string;
        photos?: string[];
      }) => {
        await this.handleCheckOut(socket, client, data);
      });

      socket.on('visit:start_travel', async (data: { visitId: string }) => {
        await this.handleStartTravel(socket, client, data);
      });

      socket.on('visit:update_eta', async (data: { visitId: string; etaMinutes: number }) => {
        await this.handleUpdateETA(socket, client, data);
      });
    }

    // Dashboard and monitoring (coordinators only)
    if (client.role === 'coordinator') {
      socket.on('dashboard:request', async () => {
        await this.handleDashboardRequest(socket, client);
      });

      socket.on('dashboard:subscribe', () => {
        this.handleDashboardSubscribe(socket, client);
      });

      socket.on('carer:status', async (data: { carerId: string }) => {
        await this.handleCarerStatusRequest(socket, client, data.carerId);
      });

      socket.on('alerts:acknowledge', async (data: { alertId: string }) => {
        await this.handleAcknowledgeAlert(socket, client, data.alertId);
      });
    }

    // Publication and assignments
    socket.on('publication:status', async (data: { publicationId: string }) => {
      await this.handlePublicationStatusRequest(socket, client, data.publicationId);
    });

    socket.on('assignment:accept', async (data: { assignmentId: string }) => {
      await this.handleAssignmentAccept(socket, client, data.assignmentId);
    });

    socket.on('assignment:decline', async (data: { assignmentId: string; reason?: string }) => {
      await this.handleAssignmentDecline(socket, client, data.assignmentId, data.reason);
    });

    // Disruption management
    socket.on('disruption:report', async (data: {
      type: string;
      description: string;
      affectedEntities: string[];
      severity?: 'low' | 'medium' | 'high' | 'critical';
    }) => {
      await this.handleDisruptionReport(socket, client, data);
    });

    socket.on('disruption:resolve', async (data: { disruptionId: string; resolution: string }) => {
      await this.handleDisruptionResolve(socket, client, data);
    });

    // Real-time communication
    socket.on('message:send', async (data: {
      to: string;
      message: string;
      type: 'text' | 'alert' | 'update';
    }) => {
      await this.handleSendMessage(socket, client, data);
    });

    // System events
    socket.on('ping', () => {
      client.lastPing = new Date();
      socket.emit('pong', { 
        timestamp: new Date(),
        serverTime: Date.now()
      });
    });

    socket.on('health:check', () => {
      this.handleHealthCheck(socket, client);
    });

    // Emergency features
    socket.on('emergency:alert', async (data: {
      type: string;
      location: { latitude: number; longitude: number };
      details: string;
    }) => {
      await this.handleEmergencyAlert(socket, client, data);
    });
  }

  /**
   * Handle subscription to a room with enhanced validation
   */
  private handleSubscribe(socket: Socket, client: WebSocketClient, room: string): void {
    try {
      // Validate room access
      if (!this.canAccessRoom(client, room)) {
        socket.emit('error', { 
          message: `Access denied to room: ${room}`,
          code: 'ROOM_ACCESS_DENIED'
        });
        return;
      }

      // Check if already subscribed
      if (client.rooms.includes(room)) {
        socket.emit('subscribed', { 
          room, 
          timestamp: new Date(),
          warning: 'Already subscribed'
        });
        return;
      }

      socket.join(room);
      client.rooms.push(room);

      logger.info(`Client ${client.userId} subscribed to ${room}`, {
        tenantId: client.tenantId,
        role: client.role
      });

      socket.emit('subscribed', { 
        room, 
        timestamp: new Date(),
        message: `Successfully subscribed to ${room}`
      });

      // Send room-specific initial data
      this.sendRoomInitialData(socket, client, room);

    } catch (error) {
      logger.error('Failed to handle subscription:', error);
      socket.emit('error', { 
        message: 'Failed to subscribe to room',
        code: 'SUBSCRIBE_FAILED'
      });
    }
  }

  /**
   * Handle unsubscription from a room
   */
  private handleUnsubscribe(socket: Socket, client: WebSocketClient, room: string): void {
    try {
      socket.leave(room);
      client.rooms = client.rooms.filter(r => r !== room);

      logger.info(`Client ${client.userId} unsubscribed from ${room}`);
      
      socket.emit('unsubscribed', { 
        room, 
        timestamp: new Date(),
        message: `Successfully unsubscribed from ${room}`
      });

    } catch (error) {
      logger.error('Failed to handle unsubscription:', error);
      socket.emit('error', { 
        message: 'Failed to unsubscribe from room',
        code: 'UNSUBSCRIBE_FAILED'
      });
    }
  }

  /**
   * Enhanced location update handler with real-time analytics
   */
  private async handleLocationUpdate(
    socket: Socket,
    client: WebSocketClient,
    data: {
      latitude: number;
      longitude: number;
      accuracy: number;
      batteryLevel?: number;
      activityType?: string;
    }
  ): Promise<void> {
    try {
      logger.debug(`Location update from carer ${client.userId}`, {
        latitude: data.latitude,
        longitude: data.longitude,
        accuracy: data.accuracy
      });

      // Update location in service
      const location = await this.liveOpsService.updateCarerLocation(
        client.userId,
        data
      );

      // Broadcast to tenant coordinators
      this.broadcastToTenant(client.tenantId, 'location:updated', {
        carerId: client.userId,
        location: {
          ...location,
          batteryLevel: data.batteryLevel,
          activityType: data.activityType
        },
        timestamp: new Date()
      });

      // Check for and broadcast any new alerts
      const alerts = await this.checkForNewAlerts(client.tenantId, client.userId, data);
      if (alerts.length > 0) {
        this.broadcastToTenant(client.tenantId, 'alerts:new', {
          alerts,
          timestamp: new Date()
        });
      }

      // Acknowledge to sender with processing info
      socket.emit('location:ack', { 
        success: true, 
        location,
        processedAt: new Date(),
        alertsGenerated: alerts.length
      });

    } catch (error) {
      logger.error('Failed to update location:', error);
      socket.emit('error', { 
        message: 'Failed to update location',
        code: 'LOCATION_UPDATE_FAILED'
      });
    }
  }

  /**
   * Handle dashboard data request with real-time subscription
   */
  private async handleDashboardRequest(socket: Socket, client: WebSocketClient): Promise<void> {
    try {
      const dashboardData = await this.liveOpsService.getDashboardData(client.tenantId);
      socket.emit('dashboard:data', {
        ...dashboardData,
        live: true,
        updatedAt: new Date()
      });
    } catch (error) {
      logger.error('Failed to get dashboard data:', error);
      socket.emit('error', { 
        message: 'Failed to get dashboard data',
        code: 'DASHBOARD_DATA_FAILED'
      });
    }
  }

  /**
   * Handle dashboard real-time subscription
   */
  private handleDashboardSubscribe(socket: Socket, client: WebSocketClient): void {
    const dashboardRoom = `dashboard:${client.tenantId}`;
    this.handleSubscribe(socket, client, dashboardRoom);
    
    socket.emit('dashboard:subscribed', {
      room: dashboardRoom,
      updateInterval: 30000, // 30 seconds
      timestamp: new Date()
    });
  }

  /**
   * Enhanced carer status request
   */
  private async handleCarerStatusRequest(
    socket: Socket,
    client: WebSocketClient,
    carerId: string
  ): Promise<void> {
    try {
      // Get comprehensive carer status
      // Note: getCarerStatus is private, need to implement public method or remove this call
      const carerStatus = { carerId, status: 'unknown' };
      
      socket.emit('carer:status:response', {
        carerId,
        status: carerStatus,
        timestamp: new Date(),
        live: true
      });

    } catch (error) {
      logger.error('Failed to get carer status:', error);
      socket.emit('error', { 
        message: 'Failed to get carer status',
        code: 'CARER_STATUS_FAILED'
      });
    }
  }

  /**
   * Enhanced check-in handler with photo support
   */
  private async handleCheckIn(
    socket: Socket,
    client: WebSocketClient,
    data: {
      visitId: string;
      latitude: number;
      longitude: number;
      notes?: string;
      photos?: string[];
    }
  ): Promise<void> {
    try {
      const checkIn = await this.liveOpsService.checkIn(
        data.visitId,
        client.userId,
        { latitude: data.latitude, longitude: data.longitude },
        data.notes
      );

      // Handle photos if provided
      if (data.photos && data.photos.length > 0) {
        await this.handleVisitPhotos(data.visitId, client.userId, data.photos, 'checkin');
      }

      // Acknowledge to sender
      socket.emit('visit:checkin:ack', { 
        success: true, 
        checkIn,
        photosProcessed: data.photos?.length || 0
      });

      // Broadcast to tenant
      this.broadcastToTenant(client.tenantId, 'visit:checkedin', {
        visitId: data.visitId,
        carerId: client.userId,
        checkIn,
        hasPhotos: !!(data.photos && data.photos.length > 0),
        timestamp: new Date()
      });

      logger.info(`Check-in recorded: visit ${data.visitId}, carer ${client.userId}`, {
        hasPhotos: !!(data.photos && data.photos.length > 0),
        notesLength: data.notes?.length || 0
      });

    } catch (error) {
      logger.error('Failed to record check-in:', error);
      socket.emit('error', { 
        message: 'Failed to record check-in',
        code: 'CHECKIN_FAILED'
      });
    }
  }

  /**
   * Enhanced check-out handler
   */
  private async handleCheckOut(
    socket: Socket,
    client: WebSocketClient,
    data: {
      visitId: string;
      latitude: number;
      longitude: number;
      tasksCompleted?: string[];
      incidentReported?: boolean;
      incidentDetails?: string;
      notes?: string;
      photos?: string[];
    }
  ): Promise<void> {
    try {
      const checkOut = await this.liveOpsService.checkOut(
        data.visitId,
        client.userId,
        { latitude: data.latitude, longitude: data.longitude },
        {
          tasksCompleted: data.tasksCompleted,
          incidentReported: data.incidentReported,
          incidentDetails: data.incidentDetails,
          notes: data.notes
        }
      );

      // Handle photos if provided
      if (data.photos && data.photos.length > 0) {
        await this.handleVisitPhotos(data.visitId, client.userId, data.photos, 'checkout');
      }

      // Acknowledge to sender
      socket.emit('visit:checkout:ack', { 
        success: true, 
        checkOut,
        photosProcessed: data.photos?.length || 0
      });

      // Broadcast to tenant
      this.broadcastToTenant(client.tenantId, 'visit:checkedout', {
        visitId: data.visitId,
        carerId: client.userId,
        checkOut,
        hasPhotos: !!(data.photos && data.photos.length > 0),
        incidentReported: data.incidentReported,
        timestamp: new Date()
      });

      // If incident reported, send urgent alert
      if (data.incidentReported) {
        this.broadcastToTenant(client.tenantId, 'incident:reported', {
          visitId: data.visitId,
          carerId: client.userId,
          details: data.incidentDetails,
          severity: 'high',
          requiresImmediateAttention: true,
          timestamp: new Date()
        });
      }

      logger.info(`Check-out recorded: visit ${data.visitId}, carer ${client.userId}`, {
        hasPhotos: !!(data.photos && data.photos.length > 0),
        incidentReported: data.incidentReported,
        tasksCompleted: data.tasksCompleted?.length || 0
      });

    } catch (error) {
      logger.error('Failed to record check-out:', error);
      socket.emit('error', { 
        message: 'Failed to record check-out',
        code: 'CHECKOUT_FAILED'
      });
    }
  }

  /**
   * Handle start travel notification
   */
  private async handleStartTravel(
    socket: Socket,
    client: WebSocketClient,
    data: { visitId: string }
  ): Promise<void> {
    try {
      this.broadcastToTenant(client.tenantId, 'visit:travel_started', {
        visitId: data.visitId,
        carerId: client.userId,
        timestamp: new Date(),
        message: 'Carer has started traveling to visit'
      });

      socket.emit('visit:travel_started:ack', { 
        success: true,
        visitId: data.visitId
      });

    } catch (error) {
      logger.error('Failed to handle travel start:', error);
      socket.emit('error', { 
        message: 'Failed to record travel start',
        code: 'TRAVEL_START_FAILED'
      });
    }
  }

  /**
   * Handle ETA update
   */
  private async handleUpdateETA(
    socket: Socket,
    client: WebSocketClient,
    data: { visitId: string; etaMinutes: number }
  ): Promise<void> {
    try {
      this.broadcastToTenant(client.tenantId, 'visit:eta_updated', {
        visitId: data.visitId,
        carerId: client.userId,
        etaMinutes: data.etaMinutes,
        timestamp: new Date(),
        expectedArrival: new Date(Date.now() + data.etaMinutes * 60000)
      });

      socket.emit('visit:eta_updated:ack', { 
        success: true,
        visitId: data.visitId
      });

    } catch (error) {
      logger.error('Failed to update ETA:', error);
      socket.emit('error', { 
        message: 'Failed to update ETA',
        code: 'ETA_UPDATE_FAILED'
      });
    }
  }

  /**
   * Enhanced disruption report handler
   */
  private async handleDisruptionReport(
    socket: Socket,
    client: WebSocketClient,
    data: {
      type: string;
      description: string;
      affectedEntities: string[];
      severity?: 'low' | 'medium' | 'high' | 'critical';
    }
  ): Promise<void> {
    try {
      // Create disruption event
      const disruption = await this.disruptionService.reportDisruption(
        client.tenantId,
        {
          type: data.type as any,
          description: data.description,
          reportedBy: client.userId,
          affectedVisits: data.affectedEntities,
          severity: data.severity || 'medium'
        }
      );

      // Acknowledge to sender
      socket.emit('disruption:ack', { 
        success: true, 
        disruption,
        autoResolutionInProgress: true
      });

      // Broadcast to all tenant coordinators with urgency
      this.broadcastToTenant(client.tenantId, 'disruption:new', {
        disruption,
        urgency: data.severity || 'medium',
        requiresAttention: true,
        timestamp: new Date(),
        message: `New ${data.severity || 'medium'} priority disruption reported`
      });

      // Start auto-resolution process
      this.startDisruptionResolution(disruption.id, client.tenantId);

      logger.info(`Disruption reported: ${disruption.id} by ${client.userId}`, {
        type: data.type,
        severity: data.severity,
        affectedEntities: data.affectedEntities.length
      });

    } catch (error) {
      logger.error('Failed to report disruption:', error);
      socket.emit('error', { 
        message: 'Failed to report disruption',
        code: 'DISRUPTION_REPORT_FAILED'
      });
    }
  }

  /**
   * Handle disruption resolution
   */
  private async handleDisruptionResolve(
    socket: Socket,
    client: WebSocketClient,
    data: { disruptionId: string; resolution: string }
  ): Promise<void> {
    try {
      // This would call the disruption service to resolve the issue
      this.broadcastToTenant(client.tenantId, 'disruption:resolved', {
        disruptionId: data.disruptionId,
        resolvedBy: client.userId,
        resolution: data.resolution,
        timestamp: new Date()
      });

      socket.emit('disruption:resolve:ack', { 
        success: true,
        disruptionId: data.disruptionId
      });

    } catch (error) {
      logger.error('Failed to resolve disruption:', error);
      socket.emit('error', { 
        message: 'Failed to resolve disruption',
        code: 'DISRUPTION_RESOLVE_FAILED'
      });
    }
  }

  /**
   * Handle publication status request
   */
  private async handlePublicationStatusRequest(
    socket: Socket,
    client: WebSocketClient,
    publicationId: string
  ): Promise<void> {
    try {
      if (!this.publicationService) {
        throw new Error('Publication service not available');
      }

      const publication = await this.publicationService.getPublicationStatus(publicationId);
      
      socket.emit('publication:status:response', {
        publication,
        timestamp: new Date()
      });

    } catch (error) {
      logger.error('Failed to get publication status:', error);
      socket.emit('error', { 
        message: 'Failed to get publication status',
        code: 'PUBLICATION_STATUS_FAILED'
      });
    }
  }

  /**
   * Handle assignment acceptance
   */
  private async handleAssignmentAccept(
    socket: Socket,
    client: WebSocketClient,
    assignmentId: string
  ): Promise<void> {
    try {
      if (!this.publicationService) {
        throw new Error('Publication service not available');
      }

      const assignment = await this.publicationService.acceptAssignment(
        client.tenantId,
        assignmentId,
        client.userId
      );

      socket.emit('assignment:accept:ack', { 
        success: true, 
        assignment
      });

      logger.info(`Assignment accepted: ${assignmentId} by ${client.userId}`);

    } catch (error) {
      logger.error('Failed to accept assignment:', error);
      socket.emit('error', { 
        message: 'Failed to accept assignment',
        code: 'ASSIGNMENT_ACCEPT_FAILED'
      });
    }
  }

  /**
   * Handle assignment decline
   */
  private async handleAssignmentDecline(
    socket: Socket,
    client: WebSocketClient,
    assignmentId: string,
    reason?: string
  ): Promise<void> {
    try {
      if (!this.publicationService) {
        throw new Error('Publication service not available');
      }

      const assignment = await this.publicationService.declineAssignment(
        client.tenantId,
        assignmentId,
        client.userId,
        reason
      );

      socket.emit('assignment:decline:ack', { 
        success: true, 
        assignment
      });

      logger.info(`Assignment declined: ${assignmentId} by ${client.userId}`, { reason });

    } catch (error) {
      logger.error('Failed to decline assignment:', error);
      socket.emit('error', { 
        message: 'Failed to decline assignment',
        code: 'ASSIGNMENT_DECLINE_FAILED'
      });
    }
  }

  /**
   * Handle message sending between users
   */
  private async handleSendMessage(
    socket: Socket,
    client: WebSocketClient,
    data: {
      to: string;
      message: string;
      type: 'text' | 'alert' | 'update';
    }
  ): Promise<void> {
    try {
      this.sendToUser(data.to, 'message:received', {
        from: client.userId,
        message: data.message,
        type: data.type,
        timestamp: new Date()
      });

      socket.emit('message:send:ack', { 
        success: true,
        deliveredTo: data.to,
        timestamp: new Date()
      });

    } catch (error) {
      logger.error('Failed to send message:', error);
      socket.emit('error', { 
        message: 'Failed to send message',
        code: 'MESSAGE_SEND_FAILED'
      });
    }
  }

  /**
   * Handle emergency alert
   */
  private async handleEmergencyAlert(
    socket: Socket,
    client: WebSocketClient,
    data: {
      type: string;
      location: { latitude: number; longitude: number };
      details: string;
    }
  ): Promise<void> {
    try {
      // Broadcast emergency to all coordinators in tenant
      this.broadcastToTenant(client.tenantId, 'emergency:alert', {
        carerId: client.userId,
        type: data.type,
        location: data.location,
        details: data.details,
        timestamp: new Date(),
        priority: 'critical',
        requiresImmediateAction: true
      });

      // Also send to specific emergency response team if configured
      this.broadcastToRoom(`emergency:${client.tenantId}`, 'emergency:alert', {
        carerId: client.userId,
        type: data.type,
        location: data.location,
        details: data.details,
        timestamp: new Date()
      });

      socket.emit('emergency:alert:ack', { 
        success: true,
        alertBroadcasted: true,
        timestamp: new Date()
      });

      logger.warn(`Emergency alert from carer ${client.userId}`, {
        type: data.type,
        location: data.location,
        details: data.details
      });

    } catch (error) {
      logger.error('Failed to handle emergency alert:', error);
      socket.emit('error', { 
        message: 'Failed to send emergency alert',
        code: 'EMERGENCY_ALERT_FAILED'
      });
    }
  }

  /**
   * Handle health check
   */
  private handleHealthCheck(socket: Socket, client: WebSocketClient): void {
    const healthStatus = {
      socketId: client.socketId,
      userId: client.userId,
      tenantId: client.tenantId,
      role: client.role,
      connectedAt: client.connectedAt,
      uptime: Date.now() - client.connectedAt.getTime(),
      lastPing: client.lastPing,
      rooms: client.rooms,
      serverTime: Date.now(),
      features: {
        realTimeUpdates: true,
        locationTracking: client.role === 'carer',
        publicationAccess: !!this.publicationService
      }
    };

    socket.emit('health:status', healthStatus);
  }

  /**
   * Handle start tracking
   */
  private handleStartTracking(socket: Socket, client: WebSocketClient): void {
    socket.emit('location:tracking_started', {
      success: true,
      trackingActive: true,
      updateInterval: 30000, // 30 seconds
      timestamp: new Date()
    });

    logger.info(`Location tracking started for carer ${client.userId}`);
  }

  /**
   * Handle stop tracking
   */
  private handleStopTracking(socket: Socket, client: WebSocketClient): void {
    socket.emit('location:tracking_stopped', {
      success: true,
      trackingActive: false,
      timestamp: new Date()
    });

    logger.info(`Location tracking stopped for carer ${client.userId}`);
  }

  /**
   * Handle acknowledge alert
   */
  private async handleAcknowledgeAlert(
    socket: Socket,
    client: WebSocketClient,
    alertId: string
  ): Promise<void> {
    try {
      // This would update the alert status in the database
      this.broadcastToTenant(client.tenantId, 'alert:acknowledged', {
        alertId,
        acknowledgedBy: client.userId,
        timestamp: new Date()
      });

      socket.emit('alert:acknowledge:ack', { 
        success: true,
        alertId
      });

    } catch (error) {
      logger.error('Failed to acknowledge alert:', error);
      socket.emit('error', { 
        message: 'Failed to acknowledge alert',
        code: 'ALERT_ACK_FAILED'
      });
    }
  }

  /**
   * Handle client disconnection with enhanced cleanup
   */
  private handleDisconnection(socket: Socket, client: WebSocketClient, reason: string): void {
    logger.info(`Client disconnected: ${client.userId} (${socket.id})`, {
      reason,
      connectionDuration: Date.now() - client.connectedAt.getTime(),
      rooms: client.rooms.length
    });

    // Notify about disconnection if it was a carer
    if (client.role === 'carer') {
      this.broadcastToTenant(client.tenantId, 'carer:disconnected', {
        carerId: client.userId,
        reason,
        timestamp: new Date(),
        wasActive: this.wasCarerActive(client.userId)
      });
    }

    // Remove from tracking
    this.clients.delete(socket.id);

    // Remove from tenant room
    const tenantSockets = this.tenantRooms.get(client.tenantId);
    if (tenantSockets) {
      tenantSockets.delete(socket.id);
      if (tenantSockets.size === 0) {
        this.tenantRooms.delete(client.tenantId);
      }
    }

    // Remove from carer rooms
    if (client.role === 'carer') {
      this.carerRooms.delete(client.userId);
    }

    // Clean up room subscriptions
    client.rooms.forEach(room => {
      socket.leave(room);
    });
  }

  // ========== REAL-TIME UPDATE METHODS ==========

  /**
   * Start background real-time data updates
   */
  private startRealTimeUpdates(): void {
    // Update dashboard data every 30 seconds for subscribed clients
    const dashboardInterval = setInterval(() => {
      this.broadcastDashboardUpdates();
    }, 30000);

    // Check for lateness predictions every minute
    const latenessInterval = setInterval(() => {
      this.broadcastLatenessPredictions();
    }, 60000);

    // Update publication status every 2 minutes
    const publicationInterval = setInterval(() => {
      this.broadcastPublicationUpdates();
    }, 120000);

    // Clean up stale connections every 5 minutes
    const cleanupInterval = setInterval(() => {
      this.cleanupStaleConnections();
    }, 300000);

    this.backgroundIntervals.push(
      dashboardInterval,
      latenessInterval,
      publicationInterval,
      cleanupInterval
    );

    logger.info('Background real-time updates started');
  }

  /**
   * Start connection health monitoring
   */
  private startHealthMonitoring(): void {
    const healthInterval = setInterval(() => {
      this.checkConnectionHealth();
    }, 60000); // Every minute

    this.backgroundIntervals.push(healthInterval);
  }

  /**
   * Broadcast dashboard updates to all subscribed coordinators
   */
  private async broadcastDashboardUpdates(): Promise<void> {
    try {
      const tenants = Array.from(this.tenantRooms.keys());
      
      for (const tenantId of tenants) {
        const dashboardRoom = `dashboard:${tenantId}`;
        const roomSockets = await this.io.in(dashboardRoom).fetchSockets();
        
        if (roomSockets.length > 0) {
          const dashboardData = await this.liveOpsService.getDashboardData(tenantId);
          
          this.broadcastToRoom(dashboardRoom, 'dashboard:update', {
            ...dashboardData,
            live: true,
            updatedAt: new Date()
          });
        }
      }
    } catch (error) {
      logger.error('Failed to broadcast dashboard updates:', error);
    }
  }

  /**
   * Broadcast lateness predictions
   */
  private async broadcastLatenessPredictions(): Promise<void> {
    try {
      const tenants = Array.from(this.tenantRooms.keys());
      
      for (const tenantId of tenants) {
        const predictions = await this.liveOpsService.predictLateness(tenantId);
        
        if (predictions.length > 0) {
          this.broadcastToTenant(tenantId, 'lateness:predictions', {
            predictions,
            timestamp: new Date(),
            totalAtRisk: predictions.length
          });
        }
      }
    } catch (error) {
      logger.error('Failed to broadcast lateness predictions:', error);
    }
  }

  /**
   * Broadcast publication updates
   */
  private async broadcastPublicationUpdates(): Promise<void> {
    try {
      // This would fetch and broadcast updates for active publications
      // Implementation depends on your publication service structure
    } catch (error) {
      logger.error('Failed to broadcast publication updates:', error);
    }
  }

  /**
   * Clean up stale connections
   */
  private cleanupStaleConnections(): void {
    const now = Date.now();
    let cleanedCount = 0;

    this.clients.forEach((client, socketId) => {
      // Disconnect clients with no ping in last 5 minutes
      if (client.lastPing && (now - client.lastPing.getTime()) > 300000) {
        const socket = this.io.sockets.sockets.get(socketId);
        if (socket) {
          socket.disconnect(true);
          cleanedCount++;
        }
      }
    });

    if (cleanedCount > 0) {
      logger.info(`Cleaned up ${cleanedCount} stale connections`);
    }
  }

  /**
   * Check connection health
   */
  private checkConnectionHealth(): void {
    const now = Date.now();
    let healthyCount = 0;
    let warningCount = 0;

    this.clients.forEach((client) => {
      if (client.lastPing && (now - client.lastPing.getTime()) < 120000) {
        healthyCount++;
      } else {
        warningCount++;
      }
    });

    if (warningCount > 0) {
      logger.warn(`Connection health: ${healthyCount} healthy, ${warningCount} with issues`);
    }
  }

  // ========== BROADCAST METHODS ==========

  /**
   * Broadcast message to entire tenant
   */
  broadcastToTenant(tenantId: string, event: string, data: any): void {
    const room = `tenant:${tenantId}`;
    this.io.to(room).emit(event, data);
    logger.debug(`Broadcast to ${room}: ${event}`, {
      tenantId,
      event,
      dataSize: JSON.stringify(data).length
    });
  }

  /**
   * Broadcast to specific room
   */
  broadcastToRoom(room: string, event: string, data: any): void {
    this.io.to(room).emit(event, data);
    logger.debug(`Broadcast to ${room}: ${event}`);
  }

  /**
   * Send to specific user
   */
  sendToUser(userId: string, event: string, data: any): void {
    const userSockets = Array.from(this.clients.values())
      .filter(c => c.userId === userId)
      .map(c => c.socketId);

    userSockets.forEach(socketId => {
      this.io.to(socketId).emit(event, data);
    });

    if (userSockets.length === 0) {
      logger.debug(`No active sockets for user ${userId}, message not delivered`);
    }
  }

  /**
   * Broadcast to all carers in tenant
   */
  broadcastToCarers(tenantId: string, event: string, data: any): void {
    const room = `role:carer:${tenantId}`;
    this.broadcastToRoom(room, event, data);
  }

  /**
   * Broadcast to all coordinators in tenant
   */
  broadcastToCoordinators(tenantId: string, event: string, data: any): void {
    const room = `role:coordinator:${tenantId}`;
    this.broadcastToRoom(room, event, data);
  }

  // ========== SPECIFIC EVENT BROADCASTS ==========

  /**
   * Broadcast roster published event
   */
  broadcastRosterPublished(tenantId: string, publication: any): void {
    this.broadcastToTenant(tenantId, 'roster:published', {
      publication,
      timestamp: new Date(),
      message: `New roster published with ${publication.assignments?.length || 0} assignments`
    });

    // Notify carers specifically
    this.broadcastToCarers(tenantId, 'roster:published', {
      publication,
      hasAssignments: publication.assignments?.length > 0,
      timestamp: new Date()
    });
  }

  /**
   * Broadcast assignment acceptance
   */
  broadcastAssignmentAccepted(tenantId: string, assignment: any): void {
    this.broadcastToTenant(tenantId, 'assignment:accepted', {
      assignment,
      timestamp: new Date(),
      message: `Assignment accepted by carer`
    });

    // Also notify the specific carer if they're connected
    this.sendToUser(assignment.carerId, 'assignment:confirmed', {
      assignment,
      message: 'Your assignment has been confirmed',
      timestamp: new Date()
    });
  }

  /**
   * Broadcast assignment decline with escalation
   */
  broadcastAssignmentDeclined(tenantId: string, assignment: any, reason?: string): void {
    this.broadcastToTenant(tenantId, 'assignment:declined', {
      assignment,
      reason,
      timestamp: new Date(),
      message: `Assignment declined${reason ? `: ${reason}` : ''}`
    });

    // Notify coordinators that escalation is in progress
    this.broadcastToCoordinators(tenantId, 'escalation:started', {
      assignmentId: assignment.id,
      originalCarerId: assignment.carerId,
      timestamp: new Date(),
      message: 'Assignment escalation initiated'
    });
  }

  /**
   * Broadcast lateness alert
   */
  broadcastLatenessAlert(tenantId: string, alert: any): void {
    this.broadcastToTenant(tenantId, 'alert:lateness', {
      alert,
      timestamp: new Date(),
      priority: this.getAlertPriority(alert.delayMinutes)
    });

    // High priority alerts also go to emergency channel
    if (alert.delayMinutes > 30) {
      this.broadcastToRoom(`emergency:${tenantId}`, 'alert:lateness_critical', {
        alert,
        timestamp: new Date(),
        requiresImmediateAction: true
      });
    }
  }

  /**
   * Broadcast real-time visit status changes
   */
  broadcastVisitStatusChange(tenantId: string, visitId: string, status: string, carerId?: string): void {
    this.broadcastToTenant(tenantId, 'visit:status_changed', {
      visitId,
      status,
      carerId,
      timestamp: new Date(),
      message: `Visit status updated to ${status}`
    });
  }

  /**
   * Broadcast incident reports in real-time
   */
  broadcastIncidentReported(tenantId: string, incident: any): void {
    this.broadcastToTenant(tenantId, 'incident:reported', {
      incident,
      timestamp: new Date(),
      urgency: incident.severity === 'CRITICAL' ? 'high' : 'medium',
      message: `New incident reported: ${incident.title}`,
      requiresAttention: true
    });
  }

  // ========== UTILITY METHODS ==========

  /**
   * Check if client can access a room
   */
  private canAccessRoom(client: WebSocketClient, room: string): boolean {
    // Room format: "type:identifier"
    const [type, identifier] = room.split(':');

    switch (type) {
      case 'tenant':
        return identifier === client.tenantId;
      case 'carer':
        return identifier === client.userId || client.role === 'coordinator';
      case 'visit':
        // Would check if user is assigned to this visit
        return client.role === 'coordinator' || client.role === 'carer';
      case 'role':
        return identifier === client.role && room.endsWith(client.tenantId);
      case 'dashboard':
        return client.role === 'coordinator' && identifier === client.tenantId;
      case 'emergency':
        return client.role === 'coordinator' && identifier === client.tenantId;
      default:
        return false;
    }
  }

  /**
   * Send room-specific initial data when subscribing
   */
  private sendRoomInitialData(socket: Socket, client: WebSocketClient, room: string): void {
    const [type] = room.split(':');

    switch (type) {
      case 'dashboard':
        this.handleDashboardRequest(socket, client);
        break;
      case 'carer':
        // Send carer-specific data
        break;
      default:
        // No specific initial data for this room type
        break;
    }
  }

  /**
   * Send pending assignments to carer on connection
   */
  private async sendPendingAssignments(socket: Socket, client: WebSocketClient): Promise<void> {
    try {
      if (!this.publicationService) return;

      const assignments = await this.publicationService.getPendingAssignmentsForCarer(
        client.tenantId,
        client.userId
      );

      if (assignments.length > 0) {
        socket.emit('assignments:pending', {
          assignments,
          total: assignments.length,
          timestamp: new Date()
        });
      }
    } catch (error) {
      logger.error('Failed to send pending assignments:', error);
    }
  }

  /**
   * Check for new alerts based on location update
   */
  private async checkForNewAlerts(
    tenantId: string, 
    carerId: string, 
    locationData: any
  ): Promise<any[]> {
    // This would check for:
    // - Geofence breaches
    // - Unusual location patterns
    // - Visit time violations
    // Return any new alerts that should be broadcast
    
    const alerts: any[] = [];
    
    // Example: Check if carer is far from assigned visits
    // This would be implemented based on your business logic
    
    return alerts;
  }

  /**
   * Handle visit photos (stub implementation)
   */
  private async handleVisitPhotos(
    visitId: string,
    carerId: string,
    photos: string[],
    type: 'checkin' | 'checkout'
  ): Promise<void> {
    // This would handle photo upload and storage
    // Implementation depends on your file storage system
    logger.info(`Processing ${photos.length} photos for visit ${visitId}`, {
      carerId,
      type
    });
  }

  /**
   * Start auto-resolution for disruption
   */
  private async startDisruptionResolution(disruptionId: string, tenantId: string): Promise<void> {
    // This would initiate automatic resolution processes
    // Implementation depends on your disruption service
    logger.info(`Starting auto-resolution for disruption ${disruptionId}`);
  }

  /**
   * Check if carer was active before disconnection
   */
  private wasCarerActive(carerId: string): boolean {
    // This would check if the carer had active visits or recent activity
    // Simplified implementation
    return true;
  }

  /**
   * Get alert priority based on delay minutes
   */
  private getAlertPriority(delayMinutes: number): 'low' | 'medium' | 'high' | 'critical' {
    if (delayMinutes <= 10) return 'low';
    if (delayMinutes <= 20) return 'medium';
    if (delayMinutes <= 30) return 'high';
    return 'critical';
  }

  // ========== STATUS AND MANAGEMENT METHODS ==========

  /**
   * Get enhanced connection status
   */
  getStatus(): {
    totalConnections: number;
    tenants: number;
    connectedTenants: string[];
    activeRooms: number;
    uptime: number;
    health: {
      healthy: number;
      warning: number;
      total: number;
    };
  } {
    const now = Date.now();
    let healthy = 0;
    let warning = 0;

    this.clients.forEach(client => {
      if (client.lastPing && (now - client.lastPing.getTime()) < 120000) {
        healthy++;
      } else {
        warning++;
      }
    });

    let activeRooms = 0;
    this.tenantRooms.forEach(room => {
      if (room.size > 0) activeRooms++;
    });

    return {
      totalConnections: this.clients.size,
      tenants: this.tenantRooms.size,
      connectedTenants: Array.from(this.tenantRooms.keys()),
      activeRooms,
      uptime: now - this.startTime,
      health: {
        healthy,
        warning,
        total: healthy + warning
      }
    };
  }

  /**
   * Get connected clients for a tenant
   */
  getTenantClients(tenantId: string): WebSocketClient[] {
    return Array.from(this.clients.values())
      .filter(c => c.tenantId === tenantId);
  }

  /**
   * Get connected carers for a tenant
   */
  getConnectedCarers(tenantId: string): WebSocketClient[] {
    return Array.from(this.clients.values())
      .filter(c => c.tenantId === tenantId && c.role === 'carer');
  }

  /**
   * Get connected coordinators for a tenant
   */
  getConnectedCoordinators(tenantId: string): WebSocketClient[] {
    return Array.from(this.clients.values())
      .filter(c => c.tenantId === tenantId && c.role === 'coordinator');
  }

  /**
   * Shutdown WebSocket service gracefully
   */
  shutdown(): void {
    logger.info('Shutting down WebSocket service gracefully');

    // Clear all background intervals
    this.backgroundIntervals.forEach(interval => clearInterval(interval));
    this.backgroundIntervals = [];

    // Notify all clients
    this.io.emit('server:shutdown', {
      message: 'Server is shutting down for maintenance',
      timestamp: new Date(),
      reconnectAfter: 300 // 5 minutes
    });

    // Disconnect all clients after short delay
    setTimeout(() => {
      this.io.disconnectSockets(true);
      
      // Clear tracking
      this.clients.clear();
      this.tenantRooms.clear();
      this.carerRooms.clear();

      logger.info('WebSocket service shut down completely');
    }, 5000); // 5 second grace period
  }

  /**
   * Force disconnect a specific user
   */
  forceDisconnectUser(userId: string, reason: string = 'Administrative action'): void {
    const userSockets = Array.from(this.clients.values())
      .filter(c => c.userId === userId)
      .map(c => c.socketId);

    userSockets.forEach(socketId => {
      const socket = this.io.sockets.sockets.get(socketId);
      if (socket) {
        socket.emit('force_disconnect', { reason, timestamp: new Date() });
        socket.disconnect(true);
      }
    });

    logger.info(`Force disconnected user ${userId}`, { reason, affectedSockets: userSockets.length });
  }
}