# Database Seeding for Rostering Service

This document explains how to seed the database with test data for the rostering service.

## Overview

The seeding script creates a comprehensive test dataset including:
- Rostering constraints
- 8 realistic carers with different skills and experience levels
- 6 visits with time windows and various requirements
- Travel matrix calculations
- Historical matches for continuity testing
- Optimization scenario testing

## Running the Seed Script

### Option 1: Using Docker Compose (Recommended)

1. Ensure your main docker-compose.yml is running with the database service
2. Run the seeding service:

```bash
docker-compose -f docker-compose.seed.yml up rostering-seed
```

This will:
- Build the rostering container
- Run the seed script
- Exit after completion

### Option 2: Running Directly in Container

If you have an existing rostering container running:

```bash
# Enter the running container
docker exec -it <rostering-container-name> /seed.sh
```

### Option 3: Local Development

For local development (not in Docker):

```bash
# Install dependencies
npm install

# Generate Prisma client
npx prisma generate

# Run the seed script
npm run seed
```

## Seed Data Details

### Carers (8 total)
- **High-skilled**: Robert Johnson, Christine Williams
- **Medium-skilled**: Hasan Ahmed, Olivia Martinez
- **Specialized**: Janet Thompson, Daniel Brown
- **Backup**: Sarah Davis, Michael Wilson

Each carer has realistic skills, experience levels, and travel distance limits.

### Visits (6 total)
- Morning visits in NW4 cluster
- Mid-day visits in HA2 cluster
- Afternoon visits with mixed requirements
- Includes double-handed visit requirements

### Tenant Configuration
- Default tenant: `test-tenant-1`
- Can be overridden with `TENANT_ID` environment variable

## Environment Variables

- `DATABASE_URL`: Database connection string (required)
- `TENANT_ID`: Tenant identifier (optional, defaults to 'test-tenant-1')

## Troubleshooting

### Common Issues

1. **Database not ready**: The script waits up to 60 seconds for the database to be available
2. **Prisma client not generated**: Ensure `npx prisma generate` has been run
3. **Build failures**: Make sure the application is properly built (`npm run build`)

### Logs

The seeding script provides detailed console output with emojis for easy tracking:
- 🚀 Starting
- 📋 Seeding constraints
- 👥 Seeding carers
- 🏠 Seeding visits
- 🗺️ Generating travel matrix
- 📊 Creating historical matches
- 🎯 Testing scenarios
- ✅ Success

## Cleanup

The seed script automatically cleans up existing data for the specified tenant before seeding new data. This ensures a clean state for testing.