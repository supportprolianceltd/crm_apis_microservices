# Rostering Service API Testing Guide

## Overview

The Rostering Service provides comprehensive AI-powered care visit scheduling and real-time operations management. This guide focuses on testing the key endpoints, with special emphasis on the new **Client Auto-Assignment to Clusters** functionality.

## Prerequisites

### Environment Setup
1. **Start the services**:
   ```bash
   cd rostering && docker-compose up -d
   ```

2. **Verify services are running**:
   ```bash
   docker-compose ps
   ```

3. **Check health**:
   ```bash
   curl http://localhost:3005/health
   ```

### Authentication
All endpoints require JWT authentication via Bearer token:
```
Authorization: Bearer <jwt_token>
```

### Google Maps API Key
The auto-assignment endpoint uses Google Maps API for distance calculations. Ensure `GOOGLE_MAPS_API_KEY` is configured in the `.env` file.

---

## 🚀 Auto-Assignment to Clusters

### Overview
The rostering service provides intelligent auto-assignment endpoints for both clients and carers to clusters. These endpoints use a multi-step assignment algorithm that prioritizes location-based clustering for optimal care visit scheduling.

---

## 1. Client Auto-Assignment

### Endpoint: `POST /api/rostering/clusters/auto-assign-client`

### Algorithm Logic

The endpoint follows this hierarchical assignment logic:

1. **Postcode Direct Match**: Check if any existing cluster has the exact same postcode
2. **Related Postcode Match**: Check if any existing clients/carers with the same postcode are assigned to clusters
3. **Distance-Based Match**: Use Google Maps API to calculate driving distance to existing clusters (≤1km threshold)
4. **New Cluster Creation**: Create a new cluster if no suitable existing cluster is found

### Endpoint Details

**Method**: `POST`  
**URL**: `http://localhost:3005/api/rostering/clusters/auto-assign-client`  
**Headers**:
```
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN
```

### Request Body

```json
{
  "name": "John Smith",
  "postcode": "SW1A 1AA",
  "address": "123 Buckingham Palace Road, London",
  "town": "London",
  "city": "London",
  "latitude": 51.5074,    // Optional
  "longitude": -0.1278,   // Optional
  "clientId": "existing-client-id"  // Optional - if client already exists
}
```

### Required Fields
- `postcode`: Client's postcode (used for matching)
- `address`: Client's full address (used for cluster naming and Google Maps geocoding)

### Optional Fields
- `name`: Client's name (used in cluster description)
- `town`, `city`: Additional location details
- `latitude`, `longitude`: GPS coordinates (if available, improves precision)
- `clientId`: If the client already exists in the system

---

## Response Formats

### Success Responses

#### 1. Assigned to Existing Cluster (Postcode Match)
```json
{
  "success": true,
  "action": "assigned_to_existing_cluster",
  "clusterId": "cluster_123",
  "clusterName": "Central London Hub",
  "reason": "postcode_match",
  "message": "Client assigned to cluster \"Central London Hub\" due to matching postcode"
}
```

#### 2. Assigned to Existing Cluster (Related Postcode Match)
```json
{
  "success": true,
  "action": "assigned_to_existing_cluster",
  "clusterId": "cluster_456",
  "clusterName": "Westminster District",
  "reason": "related_postcode_match",
  "message": "Client assigned to cluster \"Westminster District\" due to related postcode match"
}
```

#### 3. Assigned to Existing Cluster (Distance Match)
```json
{
  "success": true,
  "action": "assigned_to_existing_cluster",
  "clusterId": "cluster_789",
  "clusterName": "South Bank Area",
  "reason": "distance_match",
  "distanceKm": "0.85",
  "durationMinutes": 12,
  "message": "Client assigned to cluster \"South Bank Area\" due to proximity (0.85km, 12min drive)"
}
```

#### 4. New Cluster Created
```json
{
  "success": true,
  "action": "new_cluster_created",
  "clusterId": "cluster_new_123",
  "clusterName": "123 Buckingham Palace Road, London",
  "clientId": "request_auto_456",
  "reason": "no_match_found",
  "message": "New cluster \"123 Buckingham Palace Road, London\" created and client assigned"
}
```

### Error Responses

#### Missing Required Fields
```json
{
  "success": false,
  "error": "postcode is required"
}
```

#### Authentication Error
```json
{
  "success": false,
  "error": "User not authenticated"
}
```

#### Google Maps API Error
```json
{
  "success": false,
  "error": "Failed to auto-assign client to cluster",
  "details": "Google Maps API error: REQUEST_DENIED - Invalid API key"
}
```

---

## Testing Scenarios

### Test Case 1: Postcode Direct Match
**Scenario**: Client postcode matches an existing cluster postcode

**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Margaret Smith",
    "postcode": "SW1A 1AA",
    "address": "10 Downing Street, London"
  }'
```

**Expected Response**: Assignment to existing cluster with matching postcode

### Test Case 2: Distance-Based Assignment
**Scenario**: No postcode match, but client is within 1km of existing cluster

**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "David Johnson",
    "postcode": "SW1A 2AA",
    "address": "Westminster Abbey, London"
  }'
```

**Expected Response**: Assignment to nearest cluster within 1km with distance/duration details

### Test Case 3: New Cluster Creation
**Scenario**: No suitable existing cluster found

**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Sarah Wilson",
    "postcode": "E1 6AA",
    "address": "Brick Lane, London"
  }'
```

**Expected Response**: New cluster created with address as cluster name

### Test Case 4: Existing Client Assignment
**Scenario**: Assign existing client to cluster

**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Robert Brown",
    "postcode": "N1 9AL",
    "address": "Upper Street, London",
    "clientId": "existing_client_123"
  }'
```

**Expected Response**: Existing client assigned to appropriate cluster

### Test Case 5: Error Handling - Missing Postcode
**Scenario**: Required field missing

**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Test Client",
    "address": "123 Test Street"
  }'
```

**Expected Response**: Error about missing postcode

---

## Technical Implementation Details

### Google Maps Integration
- Uses Google Distance Matrix API for accurate driving distances
- Supports address, postcode, and coordinate inputs
- Automatic geocoding when coordinates not provided
- Intelligent caching (1 hour for address precision, 24 hours for postcode precision)

### Database Operations
- Creates `ExternalRequest` records for new clients
- Creates `ClusterClient` links for assignments
- Updates cluster statistics automatically
- Supports tenant isolation

### Performance Considerations
- Distance calculations are cached to reduce API calls
- Batch processing for multiple cluster distance checks
- Graceful degradation when Google Maps API is unavailable

### Security Features
- JWT-based authentication required
- Tenant-based data isolation
- Input validation and sanitization

---

## Integration Testing

### Setup Test Data
First, create some test clusters:

```bash
# Create test cluster in Central London
curl -X POST http://localhost:3005/api/rostering/clusters \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Central London",
    "postcode": "SW1A 1AA",
    "latitude": 51.5074,
    "longitude": -0.1278
  }'

# Create test cluster in North London
curl -X POST http://localhost:3005/api/rostering/clusters \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "North London",
    "postcode": "N1 9AL",
    "latitude": 51.5308,
    "longitude": -0.0973
  }'
```

### Run Auto-Assignment Tests
```bash
# Test postcode match
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"name":"Test Client","postcode":"SW1A 1AA","address":"Test Address"}'

# Test distance match
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"name":"Nearby Client","postcode":"SW1A 2AA","address":"Nearby Address"}'

# Test new cluster creation
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-client \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"name":"Remote Client","postcode":"E1 6AA","address":"Remote Address"}'
```

### Verify Results
Check cluster assignments:
```bash
# List all clusters with client counts
curl -X GET http://localhost:3005/api/rostering/clusters \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Check specific cluster details
curl -X GET http://localhost:3005/api/rostering/clusters/{clusterId} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Troubleshooting

### Common Issues

#### Google Maps API Errors
**Symptom**: Distance calculations fail
**Solution**:
1. Verify `GOOGLE_MAPS_API_KEY` is set in `.env`
2. Check API key has Distance Matrix API enabled
3. Ensure API key has sufficient quota

#### No Cluster Assignment
**Symptom**: Client not assigned to any cluster
**Debug Steps**:
1. Check if postcode normalization is working
2. Verify existing clusters have location data
3. Check Google Maps API responses in logs

#### Database Connection Issues
**Symptom**: 500 errors on database operations
**Solution**:
1. Verify PostgreSQL container is running
2. Check database connection string
3. Ensure PostGIS extensions are enabled

### Debug Logging
Enable debug logging to see detailed operation flow:
```bash
# Set log level to debug in environment
LOG_LEVEL=debug
```

### Performance Monitoring
Monitor Google Maps API usage:
```bash
# Check cache statistics
curl -X GET http://localhost:3005/api/rostering/travel-matrix/cache/stats \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## API Reference

### Related Endpoints

- `GET /api/rostering/clusters` - List all clusters
- `GET /api/rostering/clusters/{clusterId}` - Get cluster details
- `GET /api/rostering/clusters/{clusterId}/clients` - List cluster clients
- `POST /api/rostering/travel-matrix/calculate` - Manual distance calculation
- `GET /api/rostering/travel-matrix/cache/stats` - Cache statistics

### Data Models

#### Cluster
```typescript
{
  id: string;
  tenantId: string;
  name: string;
  postcode: string;
  latitude?: number;
  longitude?: number;
  activeRequestCount: number;
  activeCarerCount: number;
}
```

#### ExternalRequest (Client)
```typescript
{
  id: string;
  tenantId: string;
  subject: string;
  requestorName: string;
  address: string;
  postcode: string;
  status: 'APPROVED' | 'PENDING' | 'DECLINED';
}
```

#### ClusterClient (Assignment Link)
```typescript
{
  id: string;
  tenantId: string;
  clusterId: string;
  clientId: string;
}
```

#### ClusterAssignment (Carer Assignment Link)
```typescript
{
  id: string;
  tenantId: string;
  clusterId: string;
  carerId: string;
  assignedAt: DateTime;
}
```

---

## 2. Carer Auto-Assignment

### Endpoint: `POST /api/rostering/clusters/auto-assign-carer`

### Overview
The carer auto-assignment endpoint automatically assigns existing carers to appropriate clusters using the same intelligent matching logic as client assignment. This ensures carers are grouped with clients in their geographic area for efficient visit scheduling.

### Algorithm Logic
The endpoint follows the same hierarchical assignment logic as client assignment:

1. **Postcode Direct Match**: Check if any existing cluster has the exact same postcode
2. **Related Postcode Match**: Check if any existing clients/carers with the same postcode are assigned to clusters
3. **Distance-Based Match**: Use Google Maps API to calculate driving distance to existing clusters (≤1km threshold)
4. **New Cluster Creation**: Create a new cluster if no suitable existing cluster is found

### Request Body

```json
{
  "carerId": "carer_123",
  "postcode": "SW1A 1AA",
  "address": "123 Buckingham Palace Road, London",
  "town": "London",
  "city": "London",
  "latitude": 51.5074,    // Optional
  "longitude": -0.1278    // Optional
}
```

### Required Fields
- `carerId`: ID of the carer (must exist in auth service)
- `postcode`: Carer's postcode (used for matching)
- `address`: Carer's full address (used for cluster naming and Google Maps geocoding)

### Optional Fields
- `town`, `city`: Additional location details
- `latitude`, `longitude`: GPS coordinates (if available, improves precision)

### Success Responses

#### 1. Assigned to Existing Cluster (Postcode Match)
```json
{
  "success": true,
  "action": "assigned_to_existing_cluster",
  "clusterId": "cluster_123",
  "clusterName": "Central London Hub",
  "carerId": "carer_456",
  "reason": "postcode_match",
  "message": "Carer assigned to cluster \"Central London Hub\" due to matching postcode"
}
```

#### 2. Assigned to Existing Cluster (Distance Match)
```json
{
  "success": true,
  "action": "assigned_to_existing_cluster",
  "clusterId": "cluster_789",
  "clusterName": "South Bank Area",
  "carerId": "carer_456",
  "reason": "distance_match",
  "distanceKm": "0.85",
  "durationMinutes": 12,
  "message": "Carer assigned to cluster \"South Bank Area\" due to proximity (0.85km, 12min drive)"
}
```

#### 3. New Cluster Created
```json
{
  "success": true,
  "action": "new_cluster_created",
  "clusterId": "cluster_new_123",
  "clusterName": "123 Buckingham Palace Road, London",
  "carerId": "carer_456",
  "reason": "no_match_found",
  "message": "New cluster \"123 Buckingham Palace Road, London\" created and carer assigned"
}
```

### Testing Scenarios

#### Test Case 1: Postcode Direct Match
**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-carer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "carerId": "carer_123",
    "postcode": "SW1A 1AA",
    "address": "10 Downing Street, London"
  }'
```

#### Test Case 2: Distance-Based Assignment
**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-carer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "carerId": "carer_456",
    "postcode": "SW1A 2AA",
    "address": "Westminster Abbey, London"
  }'
```

#### Test Case 3: New Cluster Creation
**Request**:
```bash
curl -X POST http://localhost:3005/api/rostering/clusters/auto-assign-carer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "carerId": "carer_789",
    "postcode": "E1 6AA",
    "address": "Brick Lane, London"
  }'
```

### Key Differences from Client Assignment
- **Carer Validation**: Validates carer exists in auth service before assignment
- **Database Records**: Creates `ClusterAssignment` records instead of `ClusterClient` records
- **No Carer Creation**: Carers must already exist; no auto-creation like clients
- **Assignment Logic**: Same postcode and distance matching logic

---

## Conclusion

The Auto-Assignment endpoints provide intelligent, automated cluster assignment for both clients and carers based on real-world driving distances and postcode relationships. The Google Maps integration ensures accurate distance calculations, while the hierarchical matching algorithm provides flexible assignment logic suitable for various care scheduling scenarios.

**Available Endpoints**:
- `POST /api/rostering/clusters/auto-assign-client` - Auto-assign clients to clusters
- `POST /api/rostering/clusters/auto-assign-carer` - Auto-assign carers to clusters

For additional support or questions, refer to the main documentation in `documentations.md` or contact the development team.