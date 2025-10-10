# Rostering Service

A comprehensive microservice for email-based rostering, geocoding, and carer matching with multi-tenant support.

## Features

- **Email Processing**: Automated IMAP email parsing and request extraction
- **Geocoding**: Address to coordinate conversion with caching using Nominatim API
- **Geospatial Matching**: PostGIS-powered distance-based carer matching
- **Multi-tenant Support**: Isolated data and email configurations per tenant
- **Authentication**: JWT-based authentication with RS256/HS256 hybrid support
- **Real-time Processing**: Background workers for email polling and auto-matching
- **RESTful API**: Comprehensive CRUD operations for requests and carers
- **Production Ready**: Docker containerization, logging, monitoring, and error handling

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Email IMAP    │    │   Nominatim     │    │   Auth Service  │
│   Servers       │    │   Geocoding     │    │   (External)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
┌─────────────────────────────────────────────────────────────────┐
│                    Rostering Service                            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Email       │  │ Geocoding   │  │ Matching    │              │
│  │ Service     │  │ Service     │  │ Service     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Request     │  │ Carer       │  │ Auth        │              │
│  │ Controller  │  │ Controller  │  │ Middleware  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │ Email       │  │ Express     │                               │
│  │ Worker      │  │ Server      │                               │
│  └─────────────┘  └─────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
         │                       │
         │                       │
┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │
│   + PostGIS     │    │   (Caching)     │
└─────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Node.js 18+ 
- Docker and Docker Compose
- PostgreSQL with PostGIS (or use Docker)
- Access to auth_service for authentication

### Environment Setup

1. Clone and navigate to the service directory:
   ```bash
   cd rostering
   ```

2. Copy environment file:
   ```bash
   cp .env.example .env
   ```

3. Configure environment variables in `.env`:
   ```env
   # Database
   DATABASE_URL="postgresql://postgres:password@localhost:5434/rostering_dev"
   
   # Auth Service
   AUTH_SERVICE_URL=http://localhost:8001
   JWT_SECRET=your-hs256-secret-key
   
   # Email Configuration (per tenant)
   TENANT_1_EMAIL_HOST=imap.gmail.com
   TENANT_1_EMAIL_PORT=993
   TENANT_1_EMAIL_USER=your-email@gmail.com
   TENANT_1_EMAIL_PASS=your-app-password
   TENANT_1_EMAIL_SECURE=true
   ```

### Using Docker Compose (Recommended)

1. Start all services:
   ```bash
   docker-compose up -d
   ```

2. Run database migrations:
   ```bash
   docker-compose exec rostering-service npx prisma migrate dev
   ```

3. Generate Prisma client:
   ```bash
   docker-compose exec rostering-service npx prisma generate
   ```

4. Service will be available at: `http://localhost:3005`

### Manual Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Set up PostgreSQL with PostGIS
3. Run database migrations:
   ```bash
   npm run migrate
   ```

4. Start development server:
   ```bash
   npm run dev
   ```

## API Documentation

### Base URL
- Development: `http://localhost:3005/api/v1`
- Authentication: Required for all endpoints except health checks

### Authentication
Include JWT token in Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

### Endpoints

#### Health & Status
```http
GET /api/v1/health           # Public health check
GET /api/v1/status           # Authenticated status check
```

#### Requests
```http
GET    /api/v1/requests/search        # Search requests with pagination
POST   /api/v1/requests               # Create new request
GET    /api/v1/requests/:id           # Get specific request
PUT    /api/v1/requests/:id           # Update request
DELETE /api/v1/requests/:id           # Delete request
POST   /api/v1/requests/:id/match     # Trigger manual matching
```

#### Carers
```http
GET    /api/v1/carers/search          # Search carers with pagination
POST   /api/v1/carers                 # Create new carer
GET    /api/v1/carers/:id             # Get specific carer
PUT    /api/v1/carers/:id             # Update carer
DELETE /api/v1/carers/:id             # Delete carer
PATCH  /api/v1/carers/:id/toggle-status    # Toggle active/inactive
GET    /api/v1/carers/:id/availability     # Get carer availability
```

### Request Payload Examples

#### Create Request
```json
{
  "subject": "Care needed for elderly client",
  "content": "Need assistance with personal care for 2 hours...",
  "requestorEmail": "family@example.com",
  "requestorName": "John Smith",
  "requestorPhone": "+44 7700 900123",
  "address": "123 Main Street, London",
  "postcode": "SW1A 1AA",
  "urgency": "HIGH",
  "estimatedDuration": 120,
  "requirements": "Experience with dementia care required"
}
```

#### Create Carer
```json
{
  "email": "carer@example.com",
  "firstName": "Sarah",
  "lastName": "Johnson",
  "phone": "+44 7700 900456",
  "address": "456 Care Street, London",
  "postcode": "SW1A 2BB",
  "skills": ["personal-care", "dementia-care", "medication"],
  "languages": ["English", "Spanish"],
  "maxTravelDistance": 8000,
  "hourlyRate": 25.50,
  "experience": 5
}
```

#### Search Parameters
```http
# Requests
GET /api/v1/requests/search?status=PENDING&urgency=HIGH&postcode=SW1A&page=1&limit=20

# Carers  
GET /api/v1/carers/search?skills=dementia-care&isActive=true&maxDistance=5000&page=1&limit=20
```

## Email Processing

### Supported Email Formats
The service automatically extracts request information from emails:

- **Subject**: Used as request title
- **Content**: Parsed for address, urgency, duration, contact details
- **Urgency Detection**: Keywords like "urgent", "emergency", "asap"
- **Address Extraction**: Looks for UK postcodes and addresses
- **Contact Info**: Phone numbers and names

### Email Configuration
Configure per tenant in environment variables:
```env
TENANT_1_EMAIL_HOST=imap.gmail.com
TENANT_1_EMAIL_PORT=993
TENANT_1_EMAIL_USER=your-email@domain.com
TENANT_1_EMAIL_PASS=app-specific-password
TENANT_1_EMAIL_SECURE=true
```

### Email Processing Flow
1. **Polling**: Background worker checks for new emails every 5 minutes
2. **Parsing**: Extracts request details from email content
3. **Geocoding**: Converts addresses to coordinates
4. **Creation**: Creates request in database
5. **Matching**: Automatically finds and creates carer matches
6. **Logging**: Records processing results

## Geocoding & Matching

### Geocoding Service
- **Provider**: OpenStreetMap Nominatim API
- **Caching**: Database-backed cache for performance
- **Fallback**: Haversine distance calculation if PostGIS fails
- **Rate Limiting**: Respects Nominatim usage policies

### Matching Algorithm
1. **Distance Filtering**: PostGIS spatial queries within travel radius
2. **Skills Matching**: Required skills intersection
3. **Language Preferences**: Preferred language matching
4. **Experience Weighting**: Years of experience bonus
5. **Urgency Bonus**: Higher scores for urgent requests
6. **Score Calculation**: Weighted algorithm (0-100 scale)

### Match Score Components
- Distance: 40% weight (closer = higher score)
- Skills: 30% weight (required skills match percentage)
- Languages: 10% weight (preferred language bonus)
- Experience: 10% weight (experience years bonus)
- Urgency: 10% weight (urgent/high priority bonus)

## Database Schema

### Core Tables
- **external_requests**: Care requests with geospatial location
- **carers**: Carer profiles with skills and availability
- **request_carer_matches**: Match results with scores and status
- **geocoding_cache**: Address geocoding cache
- **email_processing_logs**: Email processing audit trail

### PostGIS Features
- Geography columns for precise location storage
- Spatial indexing for fast distance queries
- Distance functions in meters
- Support for complex geospatial operations

## Development

### Project Structure
```
src/
├── controllers/          # Express route controllers
├── middleware/          # Authentication and validation
├── services/           # Business logic services
├── workers/            # Background job processors
├── routes/             # API route definitions
├── types/              # TypeScript type definitions
└── utils/              # Utility functions and helpers
```

### Scripts
```bash
npm run dev          # Start development server with hot reload
npm run build        # Build for production
npm run start        # Start production server
npm run migrate      # Run database migrations
npm run generate     # Generate Prisma client
npm run studio       # Open Prisma Studio
npm test             # Run tests
npm run lint         # Run ESLint
```

### Database Operations
```bash
# Reset database
npx prisma migrate reset

# Deploy migrations
npx prisma migrate deploy

# View data
npx prisma studio
```

## Deployment

### Docker Production Build
```bash
# Build production image
docker build -t rostering-service .

# Run with environment
docker run -d --name rostering \
  -p 3005:3005 \
  -e DATABASE_URL="your-production-db-url" \
  -e AUTH_SERVICE_URL="your-auth-service-url" \
  rostering-service
```

### Fly.io Deployment
1. Install Fly CLI and login
2. Create app: `fly apps create rostering-service`
3. Set secrets:
   ```bash
   fly secrets set DATABASE_URL="postgresql://..."
   fly secrets set JWT_SECRET="your-secret"
   fly secrets set AUTH_SERVICE_URL="https://your-auth-service.fly.dev"
   ```
4. Deploy: `fly deploy`

### Environment Variables
Required for production:
- `DATABASE_URL`: PostgreSQL connection string with PostGIS
- `AUTH_SERVICE_URL`: URL of authentication service
- `JWT_SECRET`: Secret for HS256 JWT verification
- `REDIS_URL`: Redis connection for caching
- `TENANT_X_EMAIL_*`: Email configuration per tenant

## Monitoring & Logging

### Logging
- **Winston**: Structured logging with multiple transports
- **Log Levels**: error, warn, info, http, debug
- **Log Files**: Automatic rotation and cleanup
- **Request Logging**: HTTP request/response logging

### Health Checks
- **Docker**: Built-in health check endpoint
- **Database**: Connection monitoring
- **Redis**: Cache availability
- **External Services**: Auth service and Nominatim API

### Metrics
Monitor these key metrics:
- Request processing time
- Email processing success rate
- Geocoding cache hit rate
- Match generation speed
- Database query performance

## Troubleshooting

### Common Issues

1. **Email Connection Fails**
   - Check IMAP credentials and server settings
   - Verify app-specific passwords for Gmail
   - Ensure firewall allows outbound IMAP connections

2. **Geocoding Errors**
   - Check Nominatim API availability
   - Verify address format and postcode validity
   - Monitor rate limiting

3. **Database Connection Issues**
   - Verify DATABASE_URL format
   - Check PostGIS extension installation
   - Ensure proper permissions

4. **Authentication Failures**
   - Verify AUTH_SERVICE_URL accessibility
   - Check JWT_SECRET matches auth service
   - Validate RS256 public key retrieval

### Debug Mode
Enable debug logging:
```env
LOG_LEVEL=debug
NODE_ENV=development
```

### Performance Optimization
- Enable database connection pooling
- Implement Redis caching for frequently accessed data
- Use PostGIS spatial indexes
- Optimize email polling frequency
- Batch geocoding requests

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Follow TypeScript and ESLint conventions
4. Add tests for new functionality
5. Update documentation
6. Submit pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check troubleshooting section
- Review logs in `/app/logs`
- Monitor health endpoints
- Contact development team