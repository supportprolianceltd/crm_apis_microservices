// src/middleware/auth.middleware.js
import jwt from "jsonwebtoken";
import { JWT_SECRET, AUTH_SERVICE_URL } from "../config/config.js";
import prisma from "../config/prisma.js";
import axios from "axios";

class UnauthorizedError extends Error {
  constructor(message) {
    super(message);
    this.status = 401;
    this.name = "UnauthorizedError";
  }
}

class ForbiddenError extends Error {
  constructor(message) {
    super(message);
    this.status = 403;
    this.name = "ForbiddenError";
  }
}
class AuthenticationFailed extends Error {
  constructor(message) {
    super(message);
    this.name = "AuthenticationFailed";
    this.status = 403;
  }
}

export const authenticate = async (req, res, next) => {
  try {
    // Define public paths that don't require authentication
    const publicPaths = ["/api-docs", "/health", "/socket.io/"];

    // Skip authentication for public endpoints
    if (publicPaths.some((path) => req.path.startsWith(path))) {
      return next();
    }

    // Get token from header
    const authHeader = req.headers.authorization || "";
    if (!authHeader.startsWith("Bearer ")) {
      console.warn("Authorization header missing Bearer prefix");
      throw new UnauthorizedError("Unauthorized");
    }

    const token = authHeader.split(" ")[1];

    try {
      // Verify JWT token
      const decoded = jwt.verify(token, JWT_SECRET);

      // Extract tenant and user info from token
      const tenantId = decoded.tenant_id;
      const tenantSchema = decoded.tenant_schema;
      const userId = decoded.user_id;

      if (!tenantId) {
        console.error("Tenant ID missing in JWT token");
        throw new AuthenticationFailed("Tenant ID missing from token");
      }

      // Try to get tenant from database
      let tenant;
      try {
        tenant = await prisma.tenant.findUnique({
          where: { id: tenantId },
          select: { id: true, schema_name: true, name: true },
        });

        if (!tenant) {
          // Optional: Fetch tenant from auth service if not found locally
          if (AUTH_SERVICE_URL) {
            try {
              const response = await axios.get(
                `${AUTH_SERVICE_URL}/api/tenants/${tenantId}/`,
                { headers: { Authorization: `Bearer ${token}` } }
              );

              const tenantData = response.data;
              tenant = await prisma.tenant.upsert({
                where: { id: tenantId },
                update: {
                  name: tenantData.name || "",
                  schema_name: tenantSchema || `tenant_${tenantId}`,
                },
                create: {
                  id: tenantId,
                  name: tenantData.name || "",
                  schema_name: tenantSchema || `tenant_${tenantId}`,
                },
                select: { id: true, schema_name: true, name: true },
              });
            } catch (error) {
              console.error(
                "Error fetching tenant from auth service:",
                error.message
              );
              throw new AuthenticationFailed("Failed to verify tenant");
            }
          } else {
            throw new AuthenticationFailed("Tenant not found");
          }
        }

        // Set tenant context
        req.tenant = {
          id: tenant.id,
          schemaName: tenant.schema_name,
          name: tenant.name,
        };

        // Set user context
        req.user = {
          id: userId,
          tenantId: tenant.id,
        };

        // Here you would typically set the schema for the database connection
        // This depends on your database setup (e.g., using a connection pool)
        // For example: await setSchema(tenant.schema_name);

        next();
      } catch (error) {
        console.error("Tenant lookup error:", error.message);
        throw error;
      }
    } catch (error) {
      if (error.name === "JsonWebTokenError") {
        throw new UnauthorizedError("Invalid token");
      } else if (error.name === "TokenExpiredError") {
        throw new UnauthorizedError("Token expired");
      }
      throw error;
    }
  } catch (error) {
    next(error);
  }
};

// Error handling middleware
export const errorHandler = (err, req, res, next) => {
  console.error("Error:", err);

  const status = err.status || 500;
  const message = err.message || "Internal Server Error";
  const errorResponse = {
    success: false,
    error: {
      message,
      code: err.code,
    },
  };

  // Include stack trace in development
  if (process.env.NODE_ENV === "development") {
    errorResponse.error.stack = err.stack;
  }

  res.status(status).json(errorResponse);
};

// Socket.IO middleware for authentication
export const socketAuth = async (socket, next) => {
  try {
    const token =
      socket.handshake.auth.token ||
      socket.handshake.headers.authorization?.split(" ")[1];

    if (!token) {
      console.warn("Socket connection attempt without token");
      return next(new Error("Authentication error: No token provided"));
    }

    try {
      const decoded = jwt.verify(token, JWT_SECRET);

      if (!decoded.tenant_id) {
        console.warn(
          "Socket connection with invalid token (missing tenant_id)"
        );
        return next(new Error("Authentication error: Invalid token"));
      }

      // Store user and tenant info in the socket
      socket.user = {
        id: decoded.user_id,
        tenantId: decoded.tenant_id,
      };

      // Set tenant context if needed
      socket.tenant = {
        id: decoded.tenant_id,
        schemaName: decoded.tenant_schema || `tenant_${decoded.tenant_id}`,
      };

      next();
    } catch (error) {
      console.error("Socket authentication error:", error.message);
      if (error.name === "JsonWebTokenError") {
        return next(new Error("Authentication error: Invalid token"));
      } else if (error.name === "TokenExpiredError") {
        return next(new Error("Authentication error: Token expired"));
      }
      throw error;
    }
  } catch (error) {
    console.error("Unexpected error in socketAuth:", error);
    next(new Error("Authentication error: Internal server error"));
  }
};
