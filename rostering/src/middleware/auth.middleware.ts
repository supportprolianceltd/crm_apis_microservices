import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import NodeRSA from 'node-rsa';
import axios from 'axios';
import { logger } from '../utils/logger';

// Extend Express Request interface to include user info
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        username?: string;
        email: string;
        tenantId: string;
        permissions?: string[];
        firstName?: string;
        lastName?: string;
        role?: string;
        jobRole?: string | null;
        tenant?: string | null;
        branch?: string | null;
        status?: string | null;
        profile?: any;
        isLocked?: boolean;
        raw?: any; // raw decoded token (for debugging)
      };
    }
  }
}

interface JWTPayload {
  // Your actual JWT token structure
  jti: string;
  sub: string;
  username: string;
  email: string;
  tenant_id: string;
  tenant_organizational_id: string;
  tenant_name: string;
  tenant_unique_id: string;
  tenant_schema: string;
  tenant_domain: string;
  has_accepted_terms: boolean;
  user_type: string;
  role: string;
  status: string;
  permissions?: string[];
  first_name?: string;
  last_name?: string;
  type: string;
  exp: number;
  iat: number;
}

class AuthMiddleware {
  private hs256Secret: string;
  private authServiceUrl: string;

  constructor() {
    this.hs256Secret = process.env.JWT_SECRET || 'default-secret';
    this.authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://auth-service:8001';
  }

  /**
   * Extract display name from available token fields
   */
  private getDisplayName(decoded: JWTPayload): { firstName: string; lastName: string } {
    // If first_name and last_name are provided and not null, use them
    if (decoded.first_name && decoded.last_name) {
      return {
        firstName: decoded.first_name,
        lastName: decoded.last_name
      };
    }

    // If only first_name is provided, use it and leave lastName empty
    if (decoded.first_name) {
      return {
        firstName: decoded.first_name,
        lastName: '' // No last name available
      };
    }

    // Try to extract from username (e.g., "pgodson6919" -> "Pgodson")
    if (decoded.username && decoded.username !== 'null') {
      // Remove numbers and split camelCase or use as is
      const cleanUsername = decoded.username.replace(/[0-9]/g, '');
      if (cleanUsername.length > 0) {
        return {
          firstName: cleanUsername.charAt(0).toUpperCase() + cleanUsername.slice(1),
          lastName: '' // Username typically doesn't contain last name
        };
      }
    }
    
    // Fallback to email prefix
    const emailPart = decoded.email.split('@')[0];
    return {
      firstName: emailPart.charAt(0).toUpperCase() + emailPart.slice(1),
      lastName: ''
    };
  }

  /**
   * Fetch RS256 public key dynamically using the token for authentication
   */
  private async fetchPublicKeyWithToken(token: string, kid: string, tenantId: string): Promise<string | null> {
    try {
      const publicKeyUrl = `${this.authServiceUrl}/api/public-key/${kid}/?tenant_id=${tenantId}`;
      
      logger.debug('Attempting to fetch public key with token auth', { 
        url: publicKeyUrl,
        kid,
        tenantId 
      });
      
      const response = await axios.get(publicKeyUrl, { 
        timeout: 10000,
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'rostering-service/1.0.0',
          'Authorization': `Bearer ${token}`
        }
      });
      
      logger.debug('Public key response received', { 
        status: response.status,
        hasData: !!response.data,
        dataKeys: response.data ? Object.keys(response.data) : []
      });
      
      if (response.data && response.data.public_key) {
        logger.info('Successfully fetched RS256 public key from auth service', {
          keyLength: response.data.public_key.length,
          url: publicKeyUrl,
          kid
        });
        return response.data.public_key;
      } else {
        logger.error('Invalid public key response format', { 
          responseData: response.data,
          url: publicKeyUrl
        });
        return null;
      }
    } catch (error) {
      logger.error('Failed to fetch RS256 public key:', {
        error: error instanceof Error ? error.message : 'Unknown error',
        url: `${this.authServiceUrl}/api/public-key/${kid}/?tenant_id=${tenantId}`,
        kid,
        tenantId
      });
      return null;
    }
  }

  /**
   * Verify JWT token using RS256 (with dynamic key fetch) or fallback to HS256
   */
  private async verifyToken(token: string): Promise<JWTPayload | null> {
    try {
      logger.debug('Attempting token verification', { 
        tokenPrefix: token.substring(0, 20) + '...'
      });

      // First, decode the token without verification to check for KID and get tenant_id
      const unverifiedHeader = jwt.decode(token, { complete: true })?.header;
      const unverifiedPayload = jwt.decode(token) as any;

      // Try RS256 verification if KID is present
      if (unverifiedHeader?.kid && unverifiedPayload?.tenant_id) {
        try {
          const publicKey = await this.fetchPublicKeyWithToken(
            token, 
            unverifiedHeader.kid, 
            unverifiedPayload.tenant_id
          );

          if (publicKey) {
            const key = new NodeRSA(publicKey, 'public');
            const publicKeyPEM = key.exportKey('public');
            
            const decoded = jwt.verify(token, publicKeyPEM, {
              algorithms: ['RS256']
            }) as JWTPayload;

            logger.debug('Token verified using RS256', { 
              userId: decoded.sub,
              email: decoded.email,
              tenantId: decoded.tenant_id,
              kid: unverifiedHeader.kid
            });
            return decoded;
          }
        } catch (rs256Error) {
          logger.debug('RS256 verification failed, trying HS256 fallback', { 
            error: rs256Error instanceof Error ? rs256Error.message : 'Unknown error',
            kid: unverifiedHeader.kid
          });
          // Fall through to HS256 verification
        }
      } else {
        logger.debug('No KID or tenant_id found in token, using HS256 verification', {
          hasKid: !!unverifiedHeader?.kid,
          hasTenantId: !!unverifiedPayload?.tenant_id
        });
      }

      // Fallback to HS256 verification
      const decoded = jwt.verify(token, this.hs256Secret, {
        algorithms: ['HS256']
      }) as JWTPayload;

      logger.debug('Token verified using HS256', { 
        userId: decoded.sub,
        email: decoded.email,
        tenantId: decoded.tenant_id 
      });
      return decoded;

    } catch (error) {
      logger.error('Token verification failed:', { 
        error: error instanceof Error ? error.message : 'Unknown error',
        tokenPrefix: token.substring(0, 20) + '...'
      });
      return null;
    }
  }

  /**
   * Express middleware for JWT authentication
   */
  public authenticate = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const authHeader = req.headers.authorization;

      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        res.status(401).json({
          error: 'Authentication required',
          message: 'Bearer token must be provided'
        });
        return;
      }

      const token = authHeader.substring(7); // Remove 'Bearer ' prefix

      if (!token) {
        res.status(401).json({
          error: 'Authentication required',
          message: 'Token cannot be empty'
        });
        return;
      }

      // Verify the token
      const decoded = await this.verifyToken(token);

      if (!decoded) {
        res.status(401).json({
          error: 'Invalid token',
          message: 'Token verification failed'
        });
        return;
      }

      // Check token expiration
      const currentTime = Math.floor(Date.now() / 1000);
      if (decoded.exp && decoded.exp < currentTime) {
        res.status(401).json({
          error: 'Token expired',
          message: 'Please refresh your token'
        });
        return;
      }

      // Extract display name from available fields
      const displayName = this.getDisplayName(decoded);

      // Attach comprehensive user info to request. Prefer nested `decoded.user` fields
      // when present (auth service embeds full user object), otherwise fall back
      // to top-level claims. Normalize ID and tenant to strings.
      const decodedAny = decoded as any;
      const nestedUser = decodedAny.user || {};

      const rawUserId = decodedAny.user_id ?? decodedAny.userId ?? nestedUser.id ?? decoded.sub ?? decoded.email;
      const normalizedUserId = rawUserId !== undefined && rawUserId !== null ? String(rawUserId) : '';

      const tenantIdRaw = decodedAny.tenant_id ?? nestedUser.tenant ?? decodedAny.tenant ?? '';
      const normalizedTenantId = tenantIdRaw !== undefined && tenantIdRaw !== null ? String(tenantIdRaw) : '';

      const firstName = decodedAny.first_name ?? nestedUser.first_name ?? nestedUser.firstName ?? displayName.firstName ?? '';
      const lastName = decodedAny.last_name ?? nestedUser.last_name ?? nestedUser.lastName ?? displayName.lastName ?? '';

      req.user = {
        id: normalizedUserId,
        username: nestedUser.username ?? decodedAny.username ?? undefined,
        email: decodedAny.email ?? nestedUser.email ?? '',
        tenantId: normalizedTenantId,
        permissions: decodedAny.permissions || nestedUser.permissions || [],
        firstName: firstName || undefined,
        lastName: lastName || undefined,
        role: decodedAny.role ?? nestedUser.role ?? undefined,
        jobRole: nestedUser.job_role ?? nestedUser.jobRole ?? undefined,
        tenant: nestedUser.tenant ?? undefined,
        branch: nestedUser.branch ?? undefined,
        status: nestedUser.status ?? decodedAny.status ?? undefined,
        profile: nestedUser.profile ?? undefined,
        isLocked: nestedUser.is_locked ?? undefined,
        raw: decodedAny,
      };

      logger.debug(`Authenticated user: ${decoded.email} (tenant: ${decoded.tenant_id})`, {
        firstName: displayName.firstName,
        lastName: displayName.lastName
      });
      next();

    } catch (error) {
      logger.error('Authentication middleware error:', error);
      res.status(500).json({
        error: 'Authentication error',
        message: 'Internal server error during authentication'
      });
    }
  };

  /**
   * Middleware to check specific permissions
   */
  public requirePermission = (permission: string) => {
    return (req: Request, res: Response, next: NextFunction): void => {
      if (!req.user) {
        res.status(401).json({
          error: 'Authentication required',
          message: 'User not authenticated'
        });
        return;
      }

      const userPermissions = req.user.permissions || [];
      
      if (!userPermissions.includes(permission) && !userPermissions.includes('admin')) {
        res.status(403).json({
          error: 'Insufficient permissions',
          message: `Required permission: ${permission}`
        });
        return;
      }

      next();
    };
  };

  /**
   * Middleware to ensure tenant isolation
   */
  public ensureTenantAccess = (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({
        error: 'Authentication required',
        message: 'User not authenticated'
      });
      return;
    }

    // Check if request includes tenant ID parameter and matches user's tenant
    const requestTenantId = req.params.tenantId || req.query.tenantId || req.body.tenantId;
    
    if (requestTenantId && requestTenantId !== req.user.tenantId) {
      res.status(403).json({
        error: 'Tenant access denied',
        message: 'Cannot access resources from different tenant'
      });
      return;
    }

    next();
  };

  /**
   * Refresh public key - not needed with dynamic fetching
   */
  public async refreshPublicKey(): Promise<void> {
    logger.info('Public key refresh not needed - using dynamic fetching per request');
  }
}

// Export singleton instance
export const authMiddleware = new AuthMiddleware();

// Export individual middleware functions for convenience
export const authenticate = authMiddleware.authenticate;
export const requirePermission = authMiddleware.requirePermission;
export const ensureTenantAccess = authMiddleware.ensureTenantAccess;