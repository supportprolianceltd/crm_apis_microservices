import axios from 'axios';
import { logger, logServiceError } from '../utils/logger';

interface NotificationEvent {
  event_type: string;
  recipient_type: 'email' | 'sms' | 'push';
  recipient: string;
  tenant_id: string;
  data: Record<string, any>;
  template?: string;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  scheduled_at?: string;
}

export class NotificationService {
  private notificationServiceUrl: string;

  constructor() {
    this.notificationServiceUrl = process.env.NOTIFICATION_SERVICE_URL || 'http://notify/events';
  }

  /**
   * Send notification for new carer match
   */
  async notifyCarerMatch(
    carerId: string,
    carerEmail: string,
    requestId: string,
    tenantId: string,
    matchDetails: {
      requestorName?: string;
      address: string;
      urgency: string;
      estimatedDuration?: number;
      requirements?: string;
      distance: number;
      matchScore: number;
    }
  ): Promise<void> {
    try {
      const event: NotificationEvent = {
        event_type: 'carer_match_notification',
        recipient_type: 'email',
        recipient: carerEmail,
        tenant_id: tenantId,
        priority: matchDetails.urgency === 'URGENT' ? 'urgent' : 'medium',
        data: {
          carer_id: carerId,
          request_id: requestId,
          requestor_name: matchDetails.requestorName || 'Client',
          address: matchDetails.address,
          urgency: matchDetails.urgency,
          estimated_duration: matchDetails.estimatedDuration,
          requirements: matchDetails.requirements,
          distance_meters: Math.round(matchDetails.distance),
          match_score: matchDetails.matchScore,
          accept_url: `${process.env.FRONTEND_URL}/matches/${requestId}/accept`,
          decline_url: `${process.env.FRONTEND_URL}/matches/${requestId}/decline`
        },
        template: 'carer_match_notification'
      };

      await this.sendNotification(event);
      logger.info(`Sent carer match notification to ${carerEmail}`, { 
        carerId, 
        requestId, 
        tenantId 
      });

    } catch (error) {
      logServiceError('Notification', 'notifyCarerMatch', error, { 
        carerId, 
        carerEmail, 
        requestId 
      });
    }
  }

  /**
   * Send notification when request is assigned to a carer
   */
  async notifyRequestAssigned(
    requestorEmail: string,
    carerName: string,
    carerPhone: string,
    requestId: string,
    tenantId: string,
    requestDetails: {
      subject: string;
      scheduledStartTime?: Date;
      address: string;
    }
  ): Promise<void> {
    try {
      const event: NotificationEvent = {
        event_type: 'request_assigned_notification',
        recipient_type: 'email',
        recipient: requestorEmail,
        tenant_id: tenantId,
        priority: 'medium',
        data: {
          request_id: requestId,
          carer_name: carerName,
          carer_phone: carerPhone,
          subject: requestDetails.subject,
          scheduled_start: requestDetails.scheduledStartTime?.toISOString(),
          address: requestDetails.address,
          tracking_url: `${process.env.FRONTEND_URL}/requests/${requestId}`
        },
        template: 'request_assigned_notification'
      };

      await this.sendNotification(event);
      logger.info(`Sent assignment notification to ${requestorEmail}`, { 
        requestId, 
        tenantId 
      });

    } catch (error) {
      logServiceError('Notification', 'notifyRequestAssigned', error, { 
        requestorEmail, 
        requestId 
      });
    }
  }

  /**
   * Send notification for urgent requests to all available carers
   */
  async notifyUrgentRequest(
    carerEmails: string[],
    requestId: string,
    tenantId: string,
    requestDetails: {
      subject: string;
      address: string;
      requirements?: string;
      requestorName?: string;
    }
  ): Promise<void> {
    try {
      const notifications = carerEmails.map(email => ({
        event_type: 'urgent_request_notification',
        recipient_type: 'email' as const,
        recipient: email,
        tenant_id: tenantId,
        priority: 'urgent' as const,
        data: {
          request_id: requestId,
          subject: requestDetails.subject,
          address: requestDetails.address,
          requirements: requestDetails.requirements,
          requestor_name: requestDetails.requestorName || 'Client',
          respond_url: `${process.env.FRONTEND_URL}/requests/${requestId}/respond`
        },
        template: 'urgent_request_notification'
      }));

      // Send batch notifications
      await Promise.allSettled(
        notifications.map(notification => this.sendNotification(notification))
      );

      logger.info(`Sent urgent request notifications to ${carerEmails.length} carers`, { 
        requestId, 
        tenantId 
      });

    } catch (error) {
      logServiceError('Notification', 'notifyUrgentRequest', error, { 
        requestId, 
        carerCount: carerEmails.length 
      });
    }
  }

  /**
   * Send notification when carer responds to a match
   */
  async notifyMatchResponse(
    adminEmails: string[],
    carerId: string,
    carerName: string,
    requestId: string,
    response: 'ACCEPTED' | 'DECLINED' | 'INTERESTED',
    tenantId: string,
    responseNotes?: string
  ): Promise<void> {
    try {
      const notifications = adminEmails.map(email => ({
        event_type: 'match_response_notification',
        recipient_type: 'email' as const,
        recipient: email,
        tenant_id: tenantId,
        priority: response === 'ACCEPTED' ? 'high' as const : 'medium' as const,
        data: {
          carer_id: carerId,
          carer_name: carerName,
          request_id: requestId,
          response: response.toLowerCase(),
          response_notes: responseNotes,
          manage_url: `${process.env.ADMIN_URL}/requests/${requestId}/manage`
        },
        template: 'match_response_notification'
      }));

      await Promise.allSettled(
        notifications.map(notification => this.sendNotification(notification))
      );

      logger.info(`Sent match response notifications for ${response}`, { 
        carerId, 
        requestId, 
        tenantId 
      });

    } catch (error) {
      logServiceError('Notification', 'notifyMatchResponse', error, { 
        carerId, 
        requestId, 
        response 
      });
    }
  }

  /**
   * Send notification when email processing fails
   */
  async notifyEmailProcessingError(
    adminEmails: string[],
    tenantId: string,
    emailSubject: string,
    fromAddress: string,
    errorMessage: string
  ): Promise<void> {
    try {
      const notifications = adminEmails.map(email => ({
        event_type: 'email_processing_error',
        recipient_type: 'email' as const,
        recipient: email,
        tenant_id: tenantId,
        priority: 'medium' as const,
        data: {
          email_subject: emailSubject,
          from_address: fromAddress,
          error_message: errorMessage,
          timestamp: new Date().toISOString(),
          admin_url: `${process.env.ADMIN_URL}/email-logs`
        },
        template: 'email_processing_error'
      }));

      await Promise.allSettled(
        notifications.map(notification => this.sendNotification(notification))
      );

      logger.info(`Sent email processing error notifications`, { 
        tenantId, 
        fromAddress 
      });

    } catch (error) {
      logServiceError('Notification', 'notifyEmailProcessingError', error, { 
        tenantId, 
        fromAddress 
      });
    }
  }

  /**
   * Send the notification event to the notification service
   */
  private async sendNotification(event: NotificationEvent): Promise<void> {
    try {
      await axios.post(this.notificationServiceUrl, event, {
        headers: {
          'Content-Type': 'application/json'
        },
        timeout: 10000
      });

      logger.debug(`Notification sent successfully`, { 
        eventType: event.event_type, 
        recipient: event.recipient 
      });

    } catch (error) {
      if (axios.isAxiosError(error)) {
        logger.error(`Notification service error: ${error.response?.status}`, {
          url: error.config?.url,
          data: error.response?.data,
          event: event.event_type
        });
      }
      throw error;
    }
  }

  /**
   * Send test notification (for configuration validation)
   */
  async sendTestNotification(
    recipientEmail: string, 
    tenantId: string
  ): Promise<void> {
    const event: NotificationEvent = {
      event_type: 'test_notification',
      recipient_type: 'email',
      recipient: recipientEmail,
      tenant_id: tenantId,
      priority: 'low',
      data: {
        message: 'This is a test notification from the rostering service',
        timestamp: new Date().toISOString()
      },
      template: 'test_notification'
    };

    await this.sendNotification(event);
    logger.info(`Sent test notification to ${recipientEmail}`, { tenantId });
  }
}

export default NotificationService;