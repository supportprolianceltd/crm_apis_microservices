// src/middleware/auth.middleware.js
import jwt from "jsonwebtoken";
import axios from "axios";
import { AUTH_SERVICE_URL, JWT_SECRET } from "../config/config.js";
import prisma from "../config/prisma.js";

class UnauthorizedError extends Error {
  constructor(message) {
    super(message);
    this.status = 401;
    this.name = "UnauthorizedError";
  }
}

class AuthenticationFailed extends Error {
  constructor(message) {
    super(message);
    this.status = 403;
    this.name = "AuthenticationFailed";
  }
}

// Public paths that don't require authentication
const publicPaths = ["/api-docs", "/health", "/socket.io/", "/api/schema/"];

// Simple user class to match the Python implementation
class SimpleUser {
  constructor(payload) {
    this.id = payload.user_id || payload.sub;
    this.tenant_id = payload.tenant_id;
    this.role = payload.role;
    this.email = payload.email || "";
    this.username = payload.username || "";
    this.firstName = payload.first_name || "";
    this.lastName = payload.last_name || "";
    this.pk = this.id;
    this.is_staff = this.role === "admin";
    this.is_superuser = this.role === "admin";
    this.is_authenticated = true;
    this.is_active = true;
    this.is_anonymous = false;
  }

  get_username() {
    return this.username;
  }
}

// Helper function to ensure user and tenant exist in the database
async function ensureUserAndTenant(payload) {
  try {
    const tenantId = parseInt(payload.tenant_id, 10);
    const userId = parseInt(payload.user.id || payload.sub, 10);

    console.log(tenantId, userId);

    if (isNaN(tenantId) || isNaN(userId)) {
      throw new Error("Invalid user or tenant ID in token");
    }

    // Create or update tenant
    const tenant = await prisma.tenant.upsert({
      where: { id: tenantId },
      update: {
        name: payload.tenant_name || `Tenant ${tenantId}`,
        schema: payload.tenant_schema || `tenant_${tenantId}`,
      },
      create: {
        id: tenantId,
        name: payload.tenant_name || `Tenant ${tenantId}`,
        schema: payload.tenant_schema || `tenant_${tenantId}`,
      },
    });

    // Create or update user
    const user = await prisma.user.upsert({
      where: { id: userId },
      update: {
        email: payload.email,
        username:
          payload.username || payload.email?.split("@")[0] || `user_${userId}`,
        firstName: payload.first_name || payload.firstName || "",
        lastName: payload.last_name || payload.lastName || "",
        role: payload.role || "user",
        tenantId: tenant.id,
      },
      create: {
        id: userId,
        email: payload.email,
        username:
          payload.username || payload.email?.split("@")[0] || `user_${userId}`,
        firstName: payload.first_name || payload.firstName || "",
        lastName: payload.last_name || payload.lastName || "",
        role: payload.role || "user",
        tenantId: tenant.id,
      },
    });

    return { user, tenant };
  } catch (error) {
    console.error("Error ensuring user and tenant:", error);
    throw error;
  }
}

export const authMiddleware = async (req, res, next) => {
  try {
    // Skip authentication for public paths
    if (publicPaths.some((path) => req.path.startsWith(path))) {
      return next();
    }

    // Get token from header
    const authHeader = req.headers.authorization || "";
    if (!authHeader.startsWith("Bearer ")) {
      console.warn("No Bearer token provided");
      return next();
    }

    const token = authHeader.split(" ")[1];

    try {
      let payload;
      const unverifiedHeader = jwt.decode(token, { complete: true })?.header;

      // Try RS256 verification if KID is present
      if (unverifiedHeader?.kid) {
        const unverifiedPayload = jwt.decode(token);
        const tenantId = unverifiedPayload?.tenant_id;

        if (!tenantId) {
          console.warn("No tenant_id in token");
          return next(
            new AuthenticationFailed("Invalid token: Missing tenant_id")
          );
        }

        try {
          const publicKeyUrl = `${AUTH_SERVICE_URL}/api/public-key/${unverifiedHeader.kid}/?tenant_id=${tenantId}`;
          console.log(`Fetching public key from: ${publicKeyUrl}`);

          const response = await axios.get(publicKeyUrl, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 5000,
          });

          if (response.status === 200 && response.data?.public_key) {
            const publicKey = response.data.public_key;
            payload = jwt.verify(token, publicKey, { algorithms: ["RS256"] });
          }
        } catch (rsaError) {
          console.error(
            "RS256 verification failed, falling back to HS256:",
            rsaError.message
          );
          // Continue to HS256 fallback
        }
      }

      // Fallback to HS256 if RS256 failed or no KID
      if (!payload) {
        payload = jwt.verify(token, JWT_SECRET, { algorithms: ["HS256"] });
      }

      // Ensure user and tenant exist in the database
      const { user, tenant } = await ensureUserAndTenant(payload);

      // Attach user and tenant to request
      req.user = new SimpleUser({
        ...user,
        tenant_id: tenant.id,
        role: user.role,
      });
      req.tenant = {
        id: tenant.id,
        schemaName: tenant.schema,
        name: tenant.name,
      };
      req.jwt_payload = payload;

      return next();
    } catch (error) {
      if (error.name === "TokenExpiredError") {
        return next(new UnauthorizedError("Token expired"));
      } else if (error.name === "JsonWebTokenError") {
        return next(new UnauthorizedError("Invalid token"));
      }
      console.error("Authentication error:", error);
      return next(new AuthenticationFailed("Authentication failed"));
    }
  } catch (error) {
    console.error("Unexpected error in auth middleware:", error);
    return next(new AuthenticationFailed("Authentication error"));
  }
};

export const socketAuth = async (socket, next) => {
  try {
    const token =
      socket.handshake.auth.token ||
      (socket.handshake.headers.authorization || "").split(" ")[1];

    if (!token) {
      console.warn("Socket connection attempt without token");
      return next(new Error("Authentication error: No token provided"));
    }

    try {
      let decoded;
      const unverifiedHeader = jwt.decode(token, { complete: true })?.header;

      // Try RS256 verification if KID is present
      if (unverifiedHeader?.kid) {
        const unverifiedPayload = jwt.decode(token);
        const tenantId = unverifiedPayload?.tenant_id;

        if (!tenantId) {
          console.warn("No tenant_id in token");
          return next(
            new Error("Authentication error: Invalid token (missing tenant_id)")
          );
        }

        try {
          const publicKeyUrl = `${AUTH_SERVICE_URL}/api/public-key/${unverifiedHeader.kid}/?tenant_id=${tenantId}`;
          console.log(`[Socket] Fetching public key from: ${publicKeyUrl}`);

          const response = await axios.get(publicKeyUrl, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 5000,
          });

          if (response.status === 200 && response.data?.public_key) {
            const publicKey = response.data.public_key;
            decoded = jwt.verify(token, publicKey, { algorithms: ["RS256"] });
          }
        } catch (rsaError) {
          console.error(
            "RS256 verification failed, falling back to HS256:",
            rsaError.message
          );
          // Continue to HS256 fallback
        }
      }

      // Fallback to HS256 if RS256 failed or no KID
      if (!decoded) {
        decoded = jwt.verify(token, JWT_SECRET, { algorithms: ["HS256"] });
      }

      console.log(decoded);
      // Ensure user and tenant exist in the database
      const { user, tenant } = await ensureUserAndTenant(decoded);

      // Attach user and tenant to socket
      socket.user = {
        id: user.id,
        email: user.email,
        username: user.username,
        firstName: user.firstName,
        lastName: user.lastName,
        role: user.role,
        tenantId: user.tenantId,
      };

      socket.tenant = {
        id: tenant.id,
        schemaName: tenant.schema,
        name: tenant.name,
      };

      console.log(
        `Socket authenticated: user=${socket.user.id}, tenant=${socket.tenant.id}`
      );
      return next();
    } catch (error) {
      console.error("Socket authentication error:", error.message);
      if (error.name === "TokenExpiredError") {
        return next(new Error("Authentication error: Token expired"));
      } else if (error.name === "JsonWebTokenError") {
        return next(new Error("Authentication error: Invalid token"));
      }
      return next(new Error("Authentication error: " + error.message));
    }
  } catch (error) {
    console.error("Unexpected error in socket auth:", error);
    return next(new Error("Authentication error: " + error.message));
  }
};
