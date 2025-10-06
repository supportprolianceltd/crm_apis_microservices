import { PrismaClient } from '@prisma/client';
import { logger, logServiceError } from '../utils/logger';
import crypto from 'crypto';

interface TenantEmailConfigData {
  imapHost: string;
  imapPort: number;
  imapUser: string;
  imapPassword: string;
  imapTls: boolean;
  pollInterval: number;
  isActive: boolean;
}

export class TenantEmailConfigService {
  private prisma: PrismaClient;
  private encryptionKey: string;

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
    this.encryptionKey = process.env.EMAIL_ENCRYPTION_KEY || 'default-key-change-in-production';
  }

  /**
   * Encrypt password for storage
   */
  private encryptPassword(password: string): string {
    try {
      const algorithm = 'aes-256-cbc';
      const key = crypto.scryptSync(this.encryptionKey, 'salt', 32);
      const iv = crypto.randomBytes(16);
      
      const cipher = crypto.createCipheriv(algorithm, key, iv);
      let encrypted = cipher.update(password, 'utf8', 'hex');
      encrypted += cipher.final('hex');
      
      // Prepend IV to encrypted data
      return iv.toString('hex') + ':' + encrypted;
    } catch (error) {
      logServiceError('TenantEmailConfig', 'encryptPassword', error);
      return password; // Fallback to plain text (not recommended for production)
    }
  }

  /**
   * Decrypt password for use
   */
  private decryptPassword(encryptedPassword: string): string {
    try {
      // Handle old format without IV separator
      if (!encryptedPassword.includes(':')) {
        const decipher = crypto.createDecipher('aes-256-cbc', this.encryptionKey);
        let decrypted = decipher.update(encryptedPassword, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        return decrypted;
      }
      
      const algorithm = 'aes-256-cbc';
      const key = crypto.scryptSync(this.encryptionKey, 'salt', 32);
      
      const [ivHex, encryptedHex] = encryptedPassword.split(':');
      const iv = Buffer.from(ivHex, 'hex');
      
      const decipher = crypto.createDecipheriv(algorithm, key, iv);
      let decrypted = decipher.update(encryptedHex, 'hex', 'utf8');
      decrypted += decipher.final('utf8');
      return decrypted;
    } catch (error) {
      logServiceError('TenantEmailConfig', 'decryptPassword', error);
      return encryptedPassword; // Fallback to encrypted text
    }
  }

  /**
   * Create or update tenant email configuration
   */
  async upsertTenantEmailConfig(
    tenantId: string,
    configData: TenantEmailConfigData
  ): Promise<any> {
    try {
      const encryptedConfig = {
        ...configData,
        imapPassword: this.encryptPassword(configData.imapPassword)
      };

      const config = await this.prisma.tenantEmailConfig.upsert({
        where: { tenantId },
        update: {
          ...encryptedConfig,
          updatedAt: new Date()
        },
        create: {
          tenantId,
          ...encryptedConfig
        }
      });

      logger.info(`Updated email configuration for tenant: ${tenantId}`);
      return this.sanitizeConfig(config);

    } catch (error) {
      logServiceError('TenantEmailConfig', 'upsertTenantEmailConfig', error, { tenantId });
      throw error;
    }
  }

  /**
   * Get tenant email configuration
   */
  async getTenantEmailConfig(tenantId: string): Promise<any | null> {
    try {
      const config = await this.prisma.tenantEmailConfig.findUnique({
        where: { tenantId }
      });

      if (!config) {
        return null;
      }

      return this.sanitizeConfig(config);

    } catch (error) {
      logServiceError('TenantEmailConfig', 'getTenantEmailConfig', error, { tenantId });
      return null;
    }
  }

  /**
   * Get tenant email configuration with decrypted password (for internal use)
   */
  async getTenantEmailConfigWithCredentials(tenantId: string): Promise<any | null> {
    try {
      const config = await this.prisma.tenantEmailConfig.findUnique({
        where: { tenantId }
      });

      if (!config) {
        return null;
      }

      return {
        ...config,
        imapPassword: this.decryptPassword(config.imapPassword)
      };

    } catch (error) {
      logServiceError('TenantEmailConfig', 'getTenantEmailConfigWithCredentials', error, { tenantId });
      return null;
    }
  }

  /**
   * Get all active tenant email configurations
   */
  async getActiveTenantConfigs(): Promise<any[]> {
    try {
      const configs = await this.prisma.tenantEmailConfig.findMany({
        where: { isActive: true }
      });

      return configs.map(config => ({
        ...config,
        imapPassword: this.decryptPassword(config.imapPassword)
      }));

    } catch (error) {
      logServiceError('TenantEmailConfig', 'getActiveTenantConfigs', error);
      return [];
    }
  }

  /**
   * Delete tenant email configuration
   */
  async deleteTenantEmailConfig(tenantId: string): Promise<void> {
    try {
      await this.prisma.tenantEmailConfig.delete({
        where: { tenantId }
      });

      logger.info(`Deleted email configuration for tenant: ${tenantId}`);

    } catch (error) {
      logServiceError('TenantEmailConfig', 'deleteTenantEmailConfig', error, { tenantId });
      throw error;
    }
  }

  /**
   * Test email connection for a tenant
   */
  async testEmailConnection(tenantId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const config = await this.getTenantEmailConfigWithCredentials(tenantId);
      
      if (!config) {
        return { success: false, error: 'Email configuration not found' };
      }

      logger.info(`Testing email connection for tenant: ${tenantId}`, {
        host: config.imapHost,
        port: config.imapPort,
        user: config.imapUser,
        tls: config.imapTls
      });

      // Import ImapFlow dynamically to avoid loading issues
      const { ImapFlow } = await import('imapflow');

      const client = new ImapFlow({
        host: config.imapHost,
        port: config.imapPort,
        secure: config.imapTls,
        auth: {
          user: config.imapUser,
          pass: config.imapPassword
        },
        logger: false
      });

      try {
        logger.debug(`Connecting to IMAP server: ${config.imapHost}:${config.imapPort}`);
        await client.connect();
        logger.debug(`Successfully connected to IMAP server`);
        
        await client.logout();
        logger.debug(`Successfully logged out from IMAP server`);
        
        logger.info(`Email connection test successful for tenant: ${tenantId}`);
        return { success: true };

      } catch (connectionError) {
        const errorMessage = connectionError instanceof Error ? connectionError.message : 'Unknown connection error';
        logger.error(`IMAP connection failed for tenant: ${tenantId}`, { 
          error: errorMessage,
          stack: connectionError instanceof Error ? connectionError.stack : undefined,
          config: {
            host: config.imapHost,
            port: config.imapPort,
            user: config.imapUser,
            tls: config.imapTls
          }
        });
        return { success: false, error: errorMessage };
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      logServiceError('TenantEmailConfig', 'testEmailConnection', error, { tenantId });
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Update last checked timestamp for a tenant
   */
  async updateLastChecked(tenantId: string): Promise<void> {
    try {
      await this.prisma.tenantEmailConfig.update({
        where: { tenantId },
        data: { lastChecked: new Date() }
      });

    } catch (error) {
      logServiceError('TenantEmailConfig', 'updateLastChecked', error, { tenantId });
    }
  }

  /**
   * Get tenants that need email checking based on poll intervals
   */
  async getTenantsNeedingEmailCheck(): Promise<string[]> {
    try {
      const now = new Date();
      
      const configs = await this.prisma.tenantEmailConfig.findMany({
        where: {
          isActive: true,
          OR: [
            { lastChecked: null },
            {
              lastChecked: {
                lt: new Date(now.getTime() - 5 * 60 * 1000) // Default 5 minutes if no specific interval
              }
            }
          ]
        },
        select: { tenantId: true, pollInterval: true, lastChecked: true }
      });

      // Filter based on individual poll intervals
      const tenantsToCheck = configs.filter(config => {
        if (!config.lastChecked) return true;
        
        const intervalMs = config.pollInterval * 1000;
        const timeSinceLastCheck = now.getTime() - config.lastChecked.getTime();
        
        return timeSinceLastCheck >= intervalMs;
      });

      return tenantsToCheck.map(config => config.tenantId);

    } catch (error) {
      logServiceError('TenantEmailConfig', 'getTenantsNeedingEmailCheck', error);
      return [];
    }
  }

  /**
   * Remove sensitive data from config for API responses
   */
  private sanitizeConfig(config: any): any {
    const { imapPassword, ...sanitized } = config;
    return {
      ...sanitized,
      imapPassword: '***' // Mask the password
    };
  }

  /**
   * Validate email configuration data
   */
  validateEmailConfig(configData: Partial<TenantEmailConfigData>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!configData.imapHost || configData.imapHost.trim() === '') {
      errors.push('IMAP host is required');
    }

    if (!configData.imapUser || configData.imapUser.trim() === '') {
      errors.push('IMAP user is required');
    }

    if (!configData.imapPassword || configData.imapPassword.trim() === '') {
      errors.push('IMAP password is required');
    }

    if (configData.imapPort && (configData.imapPort < 1 || configData.imapPort > 65535)) {
      errors.push('IMAP port must be between 1 and 65535');
    }

    if (configData.pollInterval && configData.pollInterval < 60) {
      errors.push('Poll interval must be at least 60 seconds');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }
}

export default TenantEmailConfigService;