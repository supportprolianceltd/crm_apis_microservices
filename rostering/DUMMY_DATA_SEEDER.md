# 📊 Dummy Data Seeder for Roster Generation Testing

## Overview
This guide provides scripts and data to seed your database with realistic test data for roster generation testing. The seeder creates approved visits, active carers, travel matrices, and historical matches to test the OR-Tools optimization engine.

## 🚀 Quick Setup

### 1. Start Docker Services
```bash
cd rostering
docker-compose up -d rostering-db rostering-redis ortools-optimizer
```

### 2. Run Database Migrations
```bash
docker-compose exec rostering npx prisma migrate dev
docker-compose exec rostering npx prisma generate
```

### 3. Run the Seeder Script
```bash
# Execute seeder inside the rostering container
docker-compose exec rostering npm run seed:dummy
```

### 4. Start the Rostering Service
```bash
docker-compose up -d rostering
```

### 5. Verify Data (Optional)
```bash
# Access database via Adminer at http://localhost:8083
# Or use Prisma Studio
docker-compose exec rostering npx prisma studio --port 5556
```

### 6. Test Roster Generation
```bash
# Test balanced scenario
curl -X POST http://localhost:3005/api/rostering/roster/generate \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-12-05T00:00:00Z",
    "endDate": "2024-12-11T23:59:59Z",
    "strategy": "balanced",
    "generateScenarios": true
  }'
```

---

## 📋 Seeded Data Overview

### Tenants
- **tenant-123**: Main test tenant with complete dataset

### Carers (25 Active)
- **Skills**: Personal care, medication, mobility, dementia, complex care
- **Locations**: Distributed across London postcodes
- **Availability**: Standard working hours (8 AM - 6 PM)
- **Max Travel Distance**: 10km

### Visits (150 Approved)
- **Date Range**: Next 7 days (2024-12-05 to 2024-12-11)
- **Duration**: 30-120 minutes
- **Requirements**: Various skill combinations
- **Locations**: London postcodes with coordinates
- **Status**: All approved and ready for rostering

### Travel Matrix
- **Coverage**: All visit-to-visit and carer-to-visit combinations
- **Realistic Times**: 5-60 minutes based on distance
- **Traffic Factor**: Includes rush hour adjustments

### Historical Matches
- **Continuity Data**: Previous successful carer-client assignments
- **Success Rates**: 85% acceptance rate for historical matches

---

## 🔧 Manual Seeding Scripts

### Create Test Carers
```sql
-- Insert test carers
INSERT INTO carers (id, tenant_id, email, first_name, last_name, phone, address, postcode, location, latitude, longitude, is_active, max_travel_distance, availability_hours, skills, languages, hourly_rate, auth_user_id, created_at, updated_at) VALUES
('carer-001', 'tenant-123', 'sarah.johnson@test.com', 'Sarah', 'Johnson', '+447700000001', '123 Main St, London', 'SW1A 1AA', ST_GeomFromText('POINT(-0.1278 51.5074)', 4326), 51.5074, -0.1278, true, 10000, '{"monday": ["08:00", "18:00"], "tuesday": ["08:00", "18:00"], "wednesday": ["08:00", "18:00"], "thursday": ["08:00", "18:00"], "friday": ["08:00", "18:00"]}', ARRAY['personal-care', 'medication', 'mobility'], ARRAY['english'], 25.00, null, NOW(), NOW()),
('carer-002', 'tenant-123', 'mike.davis@test.com', 'Mike', 'Davis', '+447700000002', '456 Oak Ave, London', 'E1 6AN', ST_GeomFromText('POINT(-0.0798 51.5174)', 4326), 51.5174, -0.0798, true, 10000, '{"monday": ["09:00", "17:00"], "tuesday": ["09:00", "17:00"], "wednesday": ["09:00", "17:00"], "thursday": ["09:00", "17:00"], "friday": ["09:00", "17:00"]}', ARRAY['personal-care', 'complex-care', 'hoist'], ARRAY['english'], 28.00, null, NOW(), NOW()),
-- ... more carers
```

### Create Test Visits
```sql
-- Insert test visits
INSERT INTO external_requests (id, tenant_id, subject, content, requestor_email, requestor_name, requestor_phone, address, postcode, location, latitude, longitude, urgency, status, requirements, estimated_duration, scheduled_start_time, scheduled_end_time, notes, email_message_id, email_thread_id, approved_by, approved_at, send_to_rostering, created_at, updated_at, processed_at) VALUES
('visit-001', 'tenant-123', 'Personal Care Visit', 'Regular personal care assistance needed', 'client1@test.com', 'Mary Smith', '+447700000101', '789 Pine Rd, London', 'N1 9AL', ST_GeomFromText('POINT(-0.1078 51.5374)', 4326), 51.5374, -0.1078, 'MEDIUM', 'APPROVED', 'personal-care, medication', 60, '2024-12-05T10:00:00Z', '2024-12-05T11:00:00Z', 'Regular weekly visit', null, null, 'coordinator@test.com', NOW(), true, NOW(), NOW(), NOW()),
('visit-002', 'tenant-123', 'Complex Care Visit', 'Hoist transfer and complex care required', 'client2@test.com', 'John Brown', '+447700000102', '321 Elm St, London', 'SE1 2AB', ST_GeomFromText('POINT(-0.0978 51.4974)', 4326), 51.4974, -0.0978, 'HIGH', 'APPROVED', 'complex-care, hoist, mobility', 90, '2024-12-05T14:00:00Z', '2024-12-05T15:30:00Z', 'Requires two carers', null, null, 'coordinator@test.com', NOW(), true, NOW(), NOW(), NOW()),
-- ... more visits
```

### Create Travel Matrix
```sql
-- Insert travel times
INSERT INTO travel_matrix (from_postcode, to_postcode, duration_minutes, distance_meters, last_updated, expires_at) VALUES
('SW1A 1AA', 'N1 9AL', 25, 4500, NOW(), NOW() + INTERVAL '24 hours'),
('SW1A 1AA', 'SE1 2AB', 15, 2800, NOW(), NOW() + INTERVAL '24 hours'),
('E1 6AN', 'N1 9AL', 20, 3800, NOW(), NOW() + INTERVAL '24 hours'),
-- ... more travel combinations
```

### Create Historical Matches
```sql
-- Insert historical carer-client matches
INSERT INTO request_carer_matches (id, tenant_id, request_id, carer_id, distance, match_score, status, responded_at, response, response_notes, notification_sent, created_at, updated_at) VALUES
('match-001', 'tenant-123', 'visit-001', 'carer-001', 2.3, 0.95, 'ACCEPTED', NOW(), 'ACCEPTED', 'Happy to help regular client', true, NOW() - INTERVAL '30 days', NOW()),
('match-002', 'tenant-123', 'visit-002', 'carer-002', 1.8, 0.88, 'ACCEPTED', NOW(), 'ACCEPTED', 'Experienced with complex care', true, NOW() - INTERVAL '15 days', NOW()),
-- ... more historical matches
```

---

## 🧪 Testing Scenarios

### Scenario 1: Balanced Optimization
**Input:**
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "balanced",
  "generateScenarios": true
}
```
**Expected Output:** 3 scenarios with balanced travel/continuity/workload scores

### Scenario 2: Continuity Priority
**Input:**
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "continuity",
  "generateScenarios": false
}
```
**Expected Output:** Single scenario prioritizing carer-client continuity

### Scenario 3: Travel Minimization
**Input:**
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "travel",
  "generateScenarios": false
}
```
**Expected Output:** Single scenario minimizing total travel time

---

## 📈 Expected Results

### Balanced Scenario Metrics
- **Total Travel:** 800-1200 minutes
- **Continuity Score:** 75-85%
- **Violations:** 0-2 soft constraints
- **Average Workload:** 40-50 minutes per carer

### Continuity Scenario Metrics
- **Total Travel:** 1000-1400 minutes (higher due to continuity priority)
- **Continuity Score:** 90-95%
- **Violations:** 0-1 soft constraints
- **Average Workload:** 45-55 minutes per carer

### Travel Scenario Metrics
- **Total Travel:** 600-900 minutes (optimized for minimal travel)
- **Continuity Score:** 60-75%
- **Violations:** 1-3 soft constraints
- **Average Workload:** 35-45 minutes per carer

---

## 🔍 Verification Queries

### Check Seeded Data
```bash
# Access database via Adminer at http://localhost:8083
# Or run queries inside the container:

docker-compose exec rostering-db psql -U postgres -d rostering_dev -c "
-- Count carers
SELECT COUNT(*) FROM carers WHERE tenant_id = 'tenant-123' AND is_active = true;

-- Count visits
SELECT COUNT(*) FROM external_requests
WHERE tenant_id = 'tenant-123' AND status = 'APPROVED'
AND scheduled_start_time >= '2024-12-05T00:00:00Z'
AND scheduled_start_time <= '2024-12-11T23:59:59Z';

-- Check travel matrix
SELECT COUNT(*) FROM travel_matrix;

-- Check historical matches
SELECT COUNT(*) FROM request_carer_matches
WHERE tenant_id = 'tenant-123' AND status = 'ACCEPTED';
"
```

### Verify Roster Results
```bash
# Check generated rosters
docker-compose exec rostering-db psql -U postgres -d rostering_dev -c "
SELECT id, name, strategy, total_travel_minutes, continuity_score, quality_score
FROM rosters WHERE tenant_id = 'tenant-123' ORDER BY created_at DESC LIMIT 5;
"

# Check assignments for a specific roster
docker-compose exec rostering-db psql -U postgres -d rostering_dev -c "
SELECT COUNT(*) FROM assignments WHERE roster_id = 'your-roster-id-here';
"
```

---

## 🐛 Troubleshooting

### Issue: No visits found
**Solution:** Check date range and approval status
```bash
docker-compose exec rostering-db psql -U postgres -d rostering_dev -c "
SELECT status, scheduled_start_time FROM external_requests
WHERE tenant_id = 'tenant-123' ORDER BY scheduled_start_time LIMIT 10;
"
```

### Issue: No carers available
**Solution:** Verify active status and tenant
```bash
docker-compose exec rostering-db psql -U postgres -d rostering_dev -c "
SELECT id, is_active, tenant_id FROM carers WHERE tenant_id = 'tenant-123' LIMIT 10;
"
```

### Issue: OR-Tools fails
**Solution:** Check Python service and data format
```bash
# Test OR-Tools service
curl http://localhost:5000/health

# Check container logs
docker-compose logs ortools-optimizer

# Check rostering service logs
docker-compose logs rostering
```

### Issue: Travel matrix empty
**Solution:** Re-run travel matrix seeding
```bash
docker-compose exec rostering npm run seed:dummy
```

### Issue: Database connection fails
**Solution:** Ensure services are running
```bash
docker-compose ps
docker-compose up -d rostering-db rostering-redis
```

---

## 📝 Custom Data Generation

### Generate More Visits
```bash
# Run additional seeding inside container
docker-compose exec rostering node -e "
const { PrismaClient } = require('@prisma/client');
const { faker } = require('@faker-js/faker');

async function addMoreVisits() {
  const prisma = new PrismaClient();
  const tenantId = 'tenant-123';

  const visits = [];
  for (let i = 150; i < 200; i++) {
    visits.push({
      id: \`visit-\${String(i + 1).padStart(3, '0')}\`,
      tenantId,
      subject: \`Additional Test Visit \${i + 1}\`,
      content: faker.lorem.sentences(2),
      requestorEmail: \`client\${i + 1}@test.com\`,
      requestorName: faker.person.fullName(),
      address: faker.location.streetAddress(),
      postcode: 'SW1A 1AA', // Fixed postcode for simplicity
      latitude: 51.5074,
      longitude: -0.1278,
      status: 'APPROVED',
      requirements: 'personal-care, medication',
      estimatedDuration: 60,
      scheduledStartTime: new Date(Date.now() + (i-149) * 24 * 60 * 60 * 1000), // Next days
      sendToRostering: true
    });
  }

  await prisma.externalRequest.createMany({ data: visits });
  console.log('Added 50 more visits');
  await prisma.\$disconnect();
}

addMoreVisits();
"
```

### Generate Custom Travel Matrix
```javascript
const generateTravelMatrix = async (prisma, postcodes) => {
  const matrix = [];
  for (const from of postcodes) {
    for (const to of postcodes) {
      if (from !== to) {
        const distance = calculateDistance(from, to);
        const duration = Math.ceil(distance / 500) + 5; // 500m per minute + 5min base
        matrix.push({
          fromPostcode: from,
          toPostcode: to,
          durationMinutes: duration,
          distanceMeters: distance,
          expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
        });
      }
    }
  }
  await prisma.travelMatrix.createMany({ data: matrix });
};
```

This dummy data seeder provides everything needed to test roster generation with realistic data that matches your database schema and OR-Tools optimization requirements.