import { PrismaClient } from '@prisma/client';
import { ImapFlow, FetchMessageObject } from 'imapflow';
import { simpleParser, ParsedMail } from 'mailparser';
import { logger, logServiceError } from '../utils/logger';
import { TenantEmailConfigService } from './tenant-email-config.service';
import { NotificationService } from './notification.service';
import { 
  EmailConfig, 
  ParsedEmail, 
  ExtractedRequest, 
  RequestUrgency,
  ProcessingStatus
} from '../types';

export class EmailService {
  private prisma: PrismaClient;
  private tenantEmailConfigService: TenantEmailConfigService;
  private notificationService: NotificationService;
  private connections: Map<string, ImapFlow> = new Map();

  constructor(
    prisma: PrismaClient, 
    tenantEmailConfigService: TenantEmailConfigService,
    notificationService: NotificationService
  ) {
    this.prisma = prisma;
    this.tenantEmailConfigService = tenantEmailConfigService;
    this.notificationService = notificationService;
  }

  /**
   * Get email configuration for a tenant from database
   */
  private async getEmailConfig(tenantId: string): Promise<any | null> {
    try {
      const config = await this.tenantEmailConfigService.getTenantEmailConfigWithCredentials(tenantId);
      
      if (!config || !config.isActive) {
        logger.warn(`No active email configuration found for tenant: ${tenantId}`);
        return null;
      }

      return {
        host: config.imapHost,
        port: config.imapPort,
        secure: config.imapTls,
        user: config.imapUser,
        pass: config.imapPassword
      };
    } catch (error) {
      logServiceError('Email', 'getEmailConfig', error, { tenantId });
      return null;
    }
  }

  /**
   * Connect to IMAP server for a tenant
   */
  async connectToImap(tenantId: string): Promise<ImapFlow | null> {
    const connectStart = Date.now();
    
    try {
      // Check if already connected
      const existingConnection = this.connections.get(tenantId);
      if (existingConnection && !existingConnection.usable) {
        logger.debug(`🔄 Cleaning up existing unusable IMAP connection for tenant: ${tenantId}`);
        await existingConnection.logout();
        this.connections.delete(tenantId);
      } else if (existingConnection?.usable) {
        const reuseTime = Date.now() - connectStart;
        logger.debug(`♻️ Reusing existing IMAP connection for tenant: ${tenantId} (${reuseTime}ms)`);
        return existingConnection;
      }

      logger.debug(`🔧 Getting email configuration for tenant: ${tenantId}`);
      const configStart = Date.now();
      const config = await this.getEmailConfig(tenantId);
      const configTime = Date.now() - configStart;
      
      if (!config) {
        logger.warn(`❌ No email configuration found for tenant: ${tenantId} after ${configTime}ms`);
        return null;
      }
      
      logger.debug(`✅ Email config retrieved in ${configTime}ms for tenant: ${tenantId}`);
      logger.debug(`🌐 Connecting to IMAP server: ${config.host}:${config.port} (secure: ${config.secure}) for tenant: ${tenantId}`);

      const imapStart = Date.now();
      const client = new ImapFlow({
        host: config.host,
        port: config.port,
        secure: config.secure,
        auth: {
          user: config.user,
          pass: config.pass
        },
        logger: false // Disable imapflow logging to use our own
      });

      // Add timeout to connection
      logger.debug(`⏱️ Attempting IMAP connection with 30s timeout...`);
      const connectionPromise = client.connect();
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('IMAP connection timeout after 30 seconds')), 30000);
      });

      await Promise.race([connectionPromise, timeoutPromise]);
      const imapTime = Date.now() - imapStart;
      
      this.connections.set(tenantId, client);
      logger.info(`🔌 IMAP connection established in ${imapTime}ms for tenant: ${tenantId}`);

      // Update last checked timestamp
      const updateStart = Date.now();
      await this.tenantEmailConfigService.updateLastChecked(tenantId);
      const updateTime = Date.now() - updateStart;
      
      logger.debug(`📝 Last checked timestamp updated in ${updateTime}ms`);

      const totalTime = Date.now() - connectStart;
      logger.info(`✅ IMAP connection complete for tenant: ${tenantId} - Total time: ${totalTime}ms (config: ${configTime}ms, connect: ${imapTime}ms, update: ${updateTime}ms)`);
      return client;

    } catch (error) {
      const errorTime = Date.now() - connectStart;
      logger.error(`❌ IMAP connection failed for tenant: ${tenantId} after ${errorTime}ms:`, error);
      logServiceError('Email', 'connectToImap', error, { tenantId, connectionTime: errorTime });
      return null;
    }
  }

  /**
   * Fetch new emails for a tenant
   */
  async fetchNewEmails(tenantId: string, limit: number = 1): Promise<ParsedEmail[]> {
    const overallStart = Date.now();
    
    try {
      logger.info(`📧 STEP 1/5: Starting email fetch for tenant: ${tenantId} (limit: ${limit})`);
      
      // STEP 1: Connect to IMAP
      const connectStart = Date.now();
      const client = await this.connectToImap(tenantId);
      const connectTime = Date.now() - connectStart;
      
      if (!client) {
        logger.warn(`❌ STEP 1 FAILED: Failed to connect to IMAP for tenant: ${tenantId} after ${connectTime}ms`);
        return [];
      }
      logger.info(`✅ STEP 1 COMPLETE: IMAP connected in ${connectTime}ms for tenant: ${tenantId}`);

      // STEP 2: Open INBOX
      const inboxStart = Date.now();
      logger.info(`📬 STEP 2/5: Opening INBOX for tenant: ${tenantId}`);
      await client.mailboxOpen('INBOX');
      const inboxTime = Date.now() - inboxStart;
      logger.info(`✅ STEP 2 COMPLETE: INBOX opened in ${inboxTime}ms`);

      // STEP 3: Fetch unread emails
      const fetchStart = Date.now();
      const since = new Date();
      since.setDate(since.getDate() - 7);
      
      logger.info(`🔍 STEP 3/5: Searching for unread emails since: ${since.toISOString()}`);
      
      const fetchPromise = client.fetch({
        seen: false,
        since
      }, {
        envelope: true,
        source: true,
        uid: true
      });

      const emailsToProcess: any[] = [];
      
      // Collect all emails first
      for await (const message of fetchPromise) {
        emailsToProcess.push(message);
      }
      
      const fetchTime = Date.now() - fetchStart;
      logger.info(`✅ STEP 3 COMPLETE: Found ${emailsToProcess.length} unread emails in ${fetchTime}ms`);

      // STEP 4: Sort by date (most recent first)
      const sortStart = Date.now();
      logger.info(`📅 STEP 4/5: Sorting ${emailsToProcess.length} emails by date (most recent first)`);
      
      emailsToProcess.sort((a, b) => {
        const dateA = a.envelope?.date || new Date(0);
        const dateB = b.envelope?.date || new Date(0);
        return new Date(dateB).getTime() - new Date(dateA).getTime();
      });
      
      const sortTime = Date.now() - sortStart;
      logger.info(`✅ STEP 4 COMPLETE: Emails sorted in ${sortTime}ms`);

      // Show email details for the ones we'll process
      const emailsToProcessCount = Math.min(limit, emailsToProcess.length);
      logger.info(`📋 Processing ${emailsToProcessCount} most recent emails:`);
      
      for (let i = 0; i < emailsToProcessCount; i++) {
        const msg = emailsToProcess[i];
        logger.info(`   ${i + 1}. Subject: "${msg.envelope?.subject || 'No Subject'}" | From: ${msg.envelope?.from?.[0]?.address || 'Unknown'} | Date: ${msg.envelope?.date || 'Unknown'}`);
      }

      // STEP 5: Process emails
      const processStart = Date.now();
      logger.info(`⚙️ STEP 5/5: Processing ${emailsToProcessCount} emails...`);
      
      const emails: ParsedEmail[] = [];

      for (let i = 0; i < emailsToProcessCount; i++) {
        const emailStart = Date.now();
        const message = emailsToProcess[i];
        
        logger.info(`📧 Processing email ${i + 1}/${emailsToProcessCount}: "${message.envelope?.subject || 'No Subject'}"`);
        
        try {
          // Parse email
          const parseStart = Date.now();
          const parsedEmail = await this.parseEmailMessage(message);
          const parseTime = Date.now() - parseStart;
          
          if (parsedEmail) {
            emails.push(parsedEmail);
            logger.info(`   ✅ Email parsed successfully in ${parseTime}ms`);
            
            // Mark as seen
            const markStart = Date.now();
            await client.messageFlagsAdd(message.uid, ['\\Seen']);
            const markTime = Date.now() - markStart;
            
            logger.info(`   ✅ Email marked as read in ${markTime}ms (UID: ${message.uid})`);
          } else {
            logger.warn(`   ❌ Email parsing returned null in ${parseTime}ms`);
          }
          
          const emailTotalTime = Date.now() - emailStart;
          logger.info(`   📊 Email ${i + 1} total processing time: ${emailTotalTime}ms`);
          
        } catch (parseError) {
          const emailErrorTime = Date.now() - emailStart;
          logger.error(`   ❌ Email ${i + 1} processing failed after ${emailErrorTime}ms:`, parseError);
          
          logServiceError('Email', 'parseEmailMessage', parseError, { 
            tenantId, 
            messageId: message.envelope?.messageId || 'unknown',
            emailNumber: i + 1,
            subject: message.envelope?.subject || 'No Subject'
          });
        }
      }

      const processTime = Date.now() - processStart;
      const overallTime = Date.now() - overallStart;
      
      logger.info(`✅ STEP 5 COMPLETE: Processed ${emails.length} emails successfully in ${processTime}ms`);
      logger.info(`🎉 EMAIL PROCESSING SUMMARY for tenant ${tenantId}:`);
      logger.info(`   📊 Total time: ${overallTime}ms`);
      logger.info(`   🔌 IMAP connection: ${connectTime}ms`);
      logger.info(`   📬 INBOX open: ${inboxTime}ms`);
      logger.info(`   🔍 Email fetch: ${fetchTime}ms`);
      logger.info(`   📅 Email sort: ${sortTime}ms`);
      logger.info(`   ⚙️ Email processing: ${processTime}ms`);
      logger.info(`   📧 Emails found: ${emailsToProcess.length}`);
      logger.info(`   ✅ Emails processed: ${emails.length}/${emailsToProcessCount}`);

      return emails;

    } catch (error) {
      const errorTime = Date.now() - overallStart;
      logger.error(`❌ EMAIL PROCESSING FAILED for tenant ${tenantId} after ${errorTime}ms:`, error);
      logServiceError('Email', 'fetchNewEmails', error, { tenantId, processingTime: errorTime });
      return [];
    }
  }

  /**
   * Parse individual email message
   */
  private async parseEmailMessage(message: FetchMessageObject): Promise<ParsedEmail | null> {
    const parseStart = Date.now();
    
    try {
      if (!message.source) {
        logger.warn('📧 Email message has no source content');
        return null;
      }

      logger.debug(`📝 Parsing email content (${message.source.length} bytes)...`);
      const parsingStart = Date.now();
      const parsed = await simpleParser(message.source) as ParsedMail;
      const parsingTime = Date.now() - parsingStart;
      
      logger.debug(`✅ Email content parsed in ${parsingTime}ms`);

      if (!parsed.messageId || !parsed.from?.value[0]?.address) {
        logger.warn(`❌ Email missing required fields - messageId: ${!!parsed.messageId}, from: ${!!parsed.from?.value[0]?.address}`);
        return null;
      }

      const extractStart = Date.now();
      const textContent = this.extractTextContent(parsed);
      const extractTime = Date.now() - extractStart;
      
      logger.debug(`📄 Text content extracted in ${extractTime}ms (${textContent.length} characters)`);

      const parsedEmail: ParsedEmail = {
        messageId: parsed.messageId,
        threadId: parsed.inReplyTo || parsed.references?.[0] || undefined,
        subject: parsed.subject || 'No Subject',
        from: parsed.from.value[0].address,
        content: textContent,
        date: parsed.date || new Date(),
        attachments: parsed.attachments || []
      };

      const totalTime = Date.now() - parseStart;
      logger.debug(`✅ Email parsing complete in ${totalTime}ms - Subject: "${parsedEmail.subject}", From: ${parsedEmail.from}`);

      return parsedEmail;

    } catch (error) {
      const errorTime = Date.now() - parseStart;
      logger.error(`❌ Email parsing failed after ${errorTime}ms:`, error);
      logServiceError('Email', 'parseEmailMessage', error, { 
        messageId: message.envelope?.messageId || 'unknown',
        parsingTime: errorTime
      });
      return null;
    }
  }

  /**
   * Extract text content from parsed email
   */
  private extractTextContent(parsed: ParsedMail): string {
    if (parsed.text) {
      return parsed.text;
    }

    if (parsed.html) {
      // Basic HTML to text conversion (remove tags)
      return parsed.html
        .replace(/<[^>]*>/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .trim();
    }

    return '';
  }

  /**
   * Extract request information from email content using AI/NLP
   * This is a simplified version - in production, you might use OpenAI API or similar
   * Supports global address formats and phone numbers
   */
  extractRequestFromEmail(email: ParsedEmail): ExtractedRequest {
    const content = `${email.subject} ${email.content}`.toLowerCase();
    const originalContent = `${email.subject} ${email.content}`;
    
    // Extract urgency
    let urgency = RequestUrgency.MEDIUM;
    if (content.includes('urgent') || content.includes('emergency') || content.includes('asap')) {
      urgency = RequestUrgency.URGENT;
    } else if (content.includes('high priority') || content.includes('soon')) {
      urgency = RequestUrgency.HIGH;
    } else if (content.includes('low priority') || content.includes('when possible')) {
      urgency = RequestUrgency.LOW;
    }

    // Extract phone number - global patterns
    const phonePatterns = [
      /\+\d{1,4}[\s\-]?\d{6,14}/g,           // International format: +234 xxx xxx xxxx
      /\+\d{1,4}\s?\(\d{1,4}\)\s?\d{6,10}/g, // International with area code: +1 (555) 123-4567
      /\b0\d{9,11}\b/g,                      // National format: 08012345678
      /\b\d{3}[\-\s]?\d{3}[\-\s]?\d{4}\b/g,  // US format: 555-123-4567
      /\b\d{4}[\-\s]?\d{3}[\-\s]?\d{4}\b/g,  // Some international formats
    ];
    
    let phone: string | undefined;
    for (const pattern of phonePatterns) {
      const phoneMatch = originalContent.match(pattern);
      if (phoneMatch && phoneMatch[0]) {
        phone = phoneMatch[0].trim();
        break;
      }
    }

    // Extract postcode/postal code - global patterns
    const postcodePatterns = [
      // UK: SW1A 1AA, B14 7AP, M1 1AA
      /\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b/gi,
      // US ZIP: 12345, 12345-6789
      /\b(\d{5}(?:-\d{4})?)\b/g,
      // Canada: K1A 0A6, H0H 0H0
      /\b([A-Z]\d[A-Z]\s*\d[A-Z]\d)\b/gi,
      // Nigeria: 100001, 234567
      /\b(\d{6})\b/g,
      // Germany: 10115, 80331
      /\b(\d{5})\b/g,
      // France: 75001, 13001
      /\b(\d{5})\b/g,
      // Australia: 2000, 3000
      /\b(\d{4})\b/g,
    ];
    
    let postcode: string | undefined;
    for (const pattern of postcodePatterns) {
      const postcodeMatch = originalContent.match(pattern);
      if (postcodeMatch && postcodeMatch[0]) {
        postcode = postcodeMatch[0].toUpperCase().replace(/\s+/g, ' ').trim();
        break;
      }
    }

    // Extract address - global location patterns
    let address: string | undefined;
    
    // First try to find address with postcode
    if (postcode) {
      const addressWithPostcodePatterns = [
        new RegExp(`(.{10,80}${postcode.replace(/\s/g, '\\s*')})`, 'i'),
        new RegExp(`in\\s+([^.]{5,80}${postcode.replace(/\s/g, '\\s*')})`, 'i'),
        new RegExp(`at\\s+([^.]{5,80}${postcode.replace(/\s/g, '\\s*')})`, 'i'),
        new RegExp(`([A-Za-z\\s,\\-]{5,80}${postcode.replace(/\s/g, '\\s*')})`, 'i')
      ];

      for (const pattern of addressWithPostcodePatterns) {
        const match = originalContent.match(pattern);
        if (match && match[1]) {
          address = match[1].trim();
          address = address.replace(/^(in|at|for|,)\s*/i, '').trim();
          break;
        }
      }
    }
    
    // If no address with postcode found, try general location patterns
    if (!address) {
      const locationPatterns = [
        // "in [Location]" - Victoria Island, Lagos / Birmingham / New York
        /in\s+([A-Za-z\s,\-]{5,50})/gi,
        // "at [Location]" - at Downtown, Lagos / at Manhattan, NY
        /at\s+([A-Za-z\s,\-]{5,50})/gi,
        // "[City], [State/Country]" - Lagos, Nigeria / Birmingham, UK
        /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g,
        // "for a [location]" - for a patient in Victoria Island
        /for\s+a?\s*(?:patient|person|client)?\s*(?:in|at)\s+([A-Za-z\s,\-]{5,50})/gi,
        // Address lines with common keywords
        /(?:address|location|area):\s*([A-Za-z0-9\s,\-]{10,80})/gi,
      ];

      for (const pattern of locationPatterns) {
        const match = originalContent.match(pattern);
        if (match && match[1]) {
          let location = match[1].trim();
          // Clean up common prefixes/suffixes
          location = location.replace(/^(in|at|for|,|\.|a\s*patient|person|client)\s*/i, '').trim();
          location = location.replace(/\s*(,|\.|for|and).*$/i, '').trim();
          
          if (location.length >= 5 && location.length <= 80) {
            address = location;
            break;
          }
        }
      }
    }
    
    // Set fallback address if we have postcode but no full address
    if (!address && postcode) {
      address = `Postcode: ${postcode}`;
    }

    // Extract duration hints
    let estimatedDuration: number | undefined;
    const durationPatterns = [
      /(\d+)\s*hours?/i,
      /(\d+)\s*hrs?/i,
      /(\d+)\s*minutes?/i,
      /(\d+)\s*mins?/i
    ];

    for (const pattern of durationPatterns) {
      const match = originalContent.match(pattern);
      if (match) {
        const value = parseInt(match[1]);
        if (pattern.source.includes('hour') || pattern.source.includes('hr')) {
          estimatedDuration = value * 60; // Convert to minutes
        } else {
          estimatedDuration = value;
        }
        break;
      }
    }

    // Extract date/time patterns
    const dateTimeRegex = /(?:on|at|by)\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}:\d{2})/gi;
    const dateTimeMatches = originalContent.match(dateTimeRegex);

    const extracted: ExtractedRequest = {
      requestorEmail: email.from,
      requestorPhone: phone,
      address: address,
      postcode: postcode,
      urgency,
      estimatedDuration,
      notes: `Original subject: ${email.subject}`
    };

    // Try to extract name from email content - improved patterns
    const namePatterns = [
      /my name is ([a-zA-Z\s]+)/i,
      /i am ([a-zA-Z\s]+)/i,
      /regards,?\s*([a-zA-Z\s]+)/i,
      /sincerely,?\s*([a-zA-Z\s]+)/i,
      /thank you,?\s*([a-zA-Z\s]+)/i,
      /best regards,?\s*([a-zA-Z\s]+)/i,
      /^\s*([A-Z][a-zA-Z\s]+)\s*$/gm, // Name on its own line
      /\n\s*([A-Z][a-z]+\s+[A-Z][a-z]+)\s*\n/g // First Last name pattern
    ];

    for (const pattern of namePatterns) {
      const match = originalContent.match(pattern);
      if (match && match[1]) {
        const name = match[1].trim();
        // Validate name (should be 2-50 chars, only letters and spaces)
        if (name.length >= 2 && name.length <= 50 && /^[a-zA-Z\s]+$/.test(name)) {
          // Avoid common false positives
          const excludePatterns = ['thank you', 'best regards', 'yours sincerely', 'gmail com'];
          if (!excludePatterns.some(exclude => name.toLowerCase().includes(exclude))) {
            extracted.requestorName = name;
            break;
          }
        }
      }
    }

    return extracted;
  }

  /**
   * Process email and create request with carer matching
   */
  async processEmailToRequest(tenantId: string, email: ParsedEmail): Promise<string | null> {
    try {
      // Check if already processed
      const existing = await this.prisma.emailProcessingLog.findUnique({
        where: {
          tenantId_messageId: {
            tenantId,
            messageId: email.messageId
          }
        }
      });

      if (existing) {
        logger.debug(`Email already processed: ${email.messageId}`);
        return existing.requestId;
      }

      // Extract request information
      const extracted = this.extractRequestFromEmail(email);

      // Validate required fields - accept any location information
      if (!extracted.address && !extracted.postcode) {
        await this.logProcessingResult(tenantId, email, ProcessingStatus.INVALID_FORMAT, 
          'No address, postcode, or location information found in email');
        return null;
      }

      // Geocode the location to get coordinates
      let latitude: number | undefined;
      let longitude: number | undefined;
      
      if (extracted.address || extracted.postcode) {
        const locationToGeocode = extracted.address || extracted.postcode;
        logger.debug(`🌍 Geocoding location: ${locationToGeocode}`);
        
        try {
          const { GeocodingService } = await import('./geocoding.service');
          const geocodingService = new GeocodingService(this.prisma);
          const coordinates = await geocodingService.geocodeAddress(locationToGeocode!);
          
          if (coordinates) {
            latitude = coordinates.latitude;
            longitude = coordinates.longitude;
            logger.debug(`✅ Geocoded to: ${latitude}, ${longitude}`);
          } else {
            logger.warn(`⚠️ Could not geocode location: ${locationToGeocode}`);
          }
        } catch (geocodingError) {
          logger.warn(`🔴 Geocoding failed for ${locationToGeocode}:`, geocodingError);
          // Continue without coordinates - request will be created but without location-based matching
        }
      }

      // Create the request first
      const request = await this.prisma.externalRequest.create({
        data: {
          tenantId,
          subject: email.subject,
          content: email.content,
          requestorEmail: extracted.requestorEmail,
          requestorName: extracted.requestorName,
          requestorPhone: extracted.requestorPhone,
          address: extracted.address || `Postcode: ${extracted.postcode}`,
          postcode: extracted.postcode || '',
          latitude: latitude,
          longitude: longitude,
          urgency: extracted.urgency,
          requirements: extracted.requirements,
          estimatedDuration: extracted.estimatedDuration,
          scheduledStartTime: extracted.scheduledStartTime,
          scheduledEndTime: extracted.scheduledEndTime,
          notes: extracted.notes,
          emailMessageId: email.messageId,
          emailThreadId: email.threadId,
          status: 'PENDING',
           sendToRostering: false
        }
      });

      // Find and create carer matches if we have coordinates
      if (latitude && longitude) {
        try {
          logger.debug(`🎯 Finding carers near: ${latitude}, ${longitude}`);
          
          const { MatchingService } = await import('./matching.service');
          const { GeocodingService } = await import('./geocoding.service');
          const geocodingService = new GeocodingService(this.prisma);
          const matchingService = new MatchingService(this.prisma, geocodingService);
          
          // Trigger automatic matching which will create match records
          await matchingService.autoMatchRequest(request.id);
          
          logger.debug(`✅ Carer matching completed for request: ${request.id}`);
          
        } catch (matchingError) {
          logger.warn(`⚠️ Carer matching failed for request ${request.id}:`, matchingError);
          // Continue - request is created, just without matches
        }
      } else {
        logger.debug(`⚠️ No coordinates available - skipping carer matching for request: ${request.id}`);
      }

      // Log successful processing
      await this.logProcessingResult(tenantId, email, ProcessingStatus.SUCCESS, undefined, request.id);

      logger.info(`Created request from email: ${request.id}`, { 
        tenantId, 
        messageId: email.messageId,
        requestId: request.id,
        hasCoordinates: !!(latitude && longitude)
      });

      return request.id;

    } catch (error) {
      await this.logProcessingResult(tenantId, email, ProcessingStatus.FAILED, 
        error instanceof Error ? error.message : 'Unknown error');
      logServiceError('Email', 'processEmailToRequest', error, { tenantId, messageId: email.messageId });
      return null;
    }
  }

  /**
   * Log email processing result
   */
  private async logProcessingResult(
    tenantId: string, 
    email: ParsedEmail, 
    status: ProcessingStatus, 
    errorMessage?: string,
    requestId?: string
  ): Promise<void> {
    try {
      await this.prisma.emailProcessingLog.create({
        data: {
          tenantId,
          messageId: email.messageId,
          subject: email.subject,
          fromAddress: email.from,
          status,
          errorMessage,
          requestId
        }
      });
    } catch (error) {
      logServiceError('Email', 'logProcessingResult', error, { tenantId, messageId: email.messageId });
    }
  }

  /**
   * Get all tenant IDs that have active email configurations
   */
  async getActiveEmailTenants(): Promise<string[]> {
    try {
      return await this.tenantEmailConfigService.getTenantsNeedingEmailCheck();
    } catch (error) {
      logServiceError('Email', 'getActiveEmailTenants', error);
      return [];
    }
  }

  /**
   * Close all IMAP connections
   */
  async closeConnections(): Promise<void> {
    for (const [tenantId, client] of this.connections) {
      try {
        if (client.usable) {
          await client.logout();
        }
      } catch (error) {
        logServiceError('Email', 'closeConnection', error, { tenantId });
      }
    }
    this.connections.clear();
    logger.info('Closed all IMAP connections');
  }
}

export default EmailService;