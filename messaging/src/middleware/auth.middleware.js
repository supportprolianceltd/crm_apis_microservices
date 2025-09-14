// src/middleware/auth.middleware.js
import jwt from "jsonwebtoken";
import { JWT_SECRET } from "../config/config.js";
import prisma from "../config/prisma.js";

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

export const authenticate = async (req, res, next) => {
  try {
    // Skip authentication for public endpoints
    const publicPaths = ["/api-docs", "/health", "/socket.io/"];
    if (publicPaths.some((path) => req.path.startsWith(path))) {
      return next();
    }

    // Get token from header
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      throw new UnauthorizedError("No token provided");
    }

    const token = authHeader.split(" ")[1];

    try {
      // Verify token
      const decoded = jwt.verify(token, JWT_SECRET);

      // Get user from database
      const user = await prisma.user.findUnique({
        where: { id: decoded.user_id },
        include: { tenant: true },
      });

      if (!user) {
        throw new UnauthorizedError("User not found");
      }

      // Attach user and tenant to request
      req.user = {
        id: user.id,
        email: user.email,
        tenantId: user.tenantId,
        role: user.role,
      };

      // Set tenant context
      if (user.tenant) {
        req.tenant = {
          id: user.tenant.id,
          schemaName: user.tenant.schemaName,
          name: user.tenant.name,
        };
      }

      next();
    } catch (error) {
      if (error.name === "JsonWebTokenError") {
        throw new UnauthorizedError("Invalid token");
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

  res.status(status).json({
    success: false,
    error: {
      message,
      ...(process.env.NODE_ENV === "development" && { stack: err.stack }),
    },
  });
};

// Socket.IO middleware for authentication
export const socketAuth = (socket, next) => {
  try {
    const token =
      socket.handshake.auth.token ||
      socket.handshake.headers.authorization?.split(" ")[1];

    if (!token) {
      return next(new Error("Authentication error: No token provided"));
    }

    const decoded = jwt.verify(token, JWT_SECRET);
    socket.user = {
      id: decoded.user_id,
      tenantId: decoded.tenant_id,
    };

    next();
  } catch (error) {
    next(new Error("Authentication error: Invalid token"));
  }
};
