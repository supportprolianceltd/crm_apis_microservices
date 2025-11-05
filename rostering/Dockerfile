# ---------- Builder stage ----------
FROM node:18-alpine AS builder

# Install system dependencies and OpenSSL for Prisma
RUN apk add --no-cache bash postgresql-client su-exec openssl libc6-compat

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev for build)
RUN npm install

# Copy source code
COPY . .

# Generate Prisma client
RUN npx prisma generate

# Build the application
RUN npm run build


# ---------- Runtime stage ----------
FROM node:18-alpine AS runtime

# Install system dependencies and OpenSSL for Prisma
RUN apk add --no-cache bash postgresql-client su-exec openssl libc6-compat

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install only production dependencies with Prisma-friendly settings
ENV PRISMA_CLI_BINARY_TARGETS=linux-musl-openssl-3.0.x
RUN npm install --omit=dev && npm cache clean --force

# Copy built files and prisma artifacts from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma

# Generate Prisma client in runtime stage
RUN npx prisma generate

# Copy entrypoint and seed script
COPY entrypoint.sh /entrypoint.sh
COPY seed.sh /seed.sh
RUN chmod +x /entrypoint.sh /seed.sh

# Create directories
RUN mkdir -p /app/logs && addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 rostering \
  && chown rostering:nodejs /app/logs

EXPOSE 3005

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "const http = require('http'); \
    const options = { hostname: 'localhost', port: 3005, path: '/health', timeout: 2000 }; \
    const req = http.request(options, (res) => { \
      process.exit(res.statusCode === 200 ? 0 : 1); \
    }); \
    req.on('error', () => process.exit(1)); \
    req.end();"

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "dist/server.js"]



