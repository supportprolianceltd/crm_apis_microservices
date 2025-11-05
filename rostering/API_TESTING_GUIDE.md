# 🔬 Complete API Testing Guide - Rostering Service

## Overview
This comprehensive testing guide provides practical examples for testing all Rostering Service endpoints using cURL, Postman, and frontend integration. All examples assume the service is running on `http://localhost:3005` with proper authentication.

## 🛠️ Setup & Prerequisites

### Environment Setup
```bash
# Ensure services are running
docker-compose ps

# Get authentication token (replace with actual credentials)
AUTH_TOKEN="your-jwt-token-here"
TENANT_ID="your-tenant-id"
```

### Postman Collection Setup
```json
{
  "info": {
    "name": "Rostering Service API",
    "description": "Complete API testing collection for Rostering Service",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:3005"
    },
    {
      "key": "auth_token",
      "value": "{{auth_token}}"
    },
    "key": "tenant_id",
      "value": "{{tenant_id}}"
    }
  ]
}
```

### Frontend Setup (React)
```javascript
// api/client.js
const API_BASE = 'http://localhost:3005/api/rostering';

class RosteringAPI {
  constructor() {
    this.baseURL = API_BASE;
    this.token = localStorage.getItem('auth_token');
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`,
        ...options.headers
      },
      ...options
    };

    const response = await fetch(url, config);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  }
}

export const api = new RosteringAPI();
```

---

## 🔐 Authentication & Authorization

### Login (Get JWT Token)
```bash
# cURL
curl -X POST http://localhost:9090/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "support@prolianceltd.com",
    "password": "qwerty"
  }'
```

**Postman:**
- Method: POST
- URL: `{{base_url}}/api/token/`
- Body (raw JSON):
```json
{
  "email": "support@prolianceltd.com",
  "password": "qwerty"
}
```

**Frontend (React):**
```javascript
// Login function
const login = async (email, password, tenantId) => {
  try {
    const response = await fetch('http://localhost:9090/api/token/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, tenantId })
    });

    const data = await response.json();
    if (data.success) {
      localStorage.setItem('auth_token', data.data.token);
      localStorage.setItem('tenant_id', tenantId);
      return data.data;
    }
  } catch (error) {
    console.error('Login failed:', error);
  }
};
```

---

## 🎯 Roster Generation & Optimization

### Generate Optimized Roster Scenarios
```bash
# cURL - Generate 3 scenarios with OR-Tools optimization
curl -X POST http://localhost:3005/api/rostering/roster/generate \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-12-05T00:00:00Z",
    "endDate": "2024-12-11T23:59:59Z",
    "strategy": "balanced",
    "generateScenarios": true,
    "clusterId": "cluster-123"
  }'
```

**Postman:**
- Method: POST
- URL: `{{base_url}}/api/rostering/roster/generate`
- Headers:
  - Authorization: Bearer {{auth_token}}
  - Content-Type: application/json
- Body:
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "balanced",
  "generateScenarios": true,
  "clusterId": "cluster-123"
}
```

**Frontend (React):**
```javascript
// Generate roster scenarios
const generateRoster = async (params) => {
  try {
    const data = await api.request('/roster/generate', {
      method: 'POST',
      body: JSON.stringify(params)
    });

    console.log('Generated scenarios:', data.data);
    return data.data; // Array of 3 optimized scenarios
  } catch (error) {
    console.error('Roster generation failed:', error);
  }
};

// Usage
const scenarios = await generateRoster({
  startDate: '2024-12-05T00:00:00Z',
  endDate: '2024-12-11T23:59:59Z',
  strategy: 'balanced',
  generateScenarios: true
});
```

### Get Specific Roster
```bash
# cURL
curl -X GET http://localhost:3005/api/rostering/roster/roster-123 \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**Postman:**
- Method: GET
- URL: `{{base_url}}/api/rostering/roster/roster-123`
- Headers: Authorization: Bearer {{auth_token}}

**Frontend:**
```javascript
const getRoster = async (rosterId) => {
  return await api.request(`/roster/${rosterId}`);
};
```

### Compare Scenarios
```bash
# cURL
curl -X POST http://localhost:3005/api/rostering/roster/compare \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scenarioA": {"id": "scenario_1", "assignments": [...]},
    "scenarioB": {"id": "scenario_2", "assignments": [...]}
  }'
```

**Frontend:**
```javascript
const compareScenarios = async (scenarioA, scenarioB) => {
  return await api.request('/roster/compare', {
    method: 'POST',
    body: JSON.stringify({ scenarioA, scenarioB })
  });
};
```

---

## 📍 Live Operations

### Update Carer Location
```bash
# cURL - Real-time location tracking
curl -X POST http://localhost:3005/api/rostering/live/location/carer-123 \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 51.5074,
    "longitude": -0.1278,
    "accuracy": 10,
    "speed": 25,
    "heading": 90
  }'
```

**Postman:**
- Method: POST
- URL: `{{base_url}}/api/rostering/live/location/carer-123`
- Body:
```json
{
  "latitude": 51.5074,
  "longitude": -0.1278,
  "accuracy": 10,
  "speed": 25,
  "heading": 90,
  "timestamp": "2024-12-05T10:30:00Z"
}
```

**Frontend (React) - GPS Tracking:**
```javascript
// Real-time GPS tracking component
const LocationTracker = ({ carerId }) => {
  const [location, setLocation] = useState(null);
  const [watchId, setWatchId] = useState(null);

  useEffect(() => {
    if (navigator.geolocation) {
      const id = navigator.geolocation.watchPosition(
        async (position) => {
          const locationData = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            speed: position.coords.speed,
            heading: position.coords.heading,
            timestamp: new Date().toISOString()
          };

          setLocation(locationData);

          // Send to server
          try {
            await api.request(`/live/location/${carerId}`, {
              method: 'POST',
              body: JSON.stringify(locationData)
            });
          } catch (error) {
            console.error('Location update failed:', error);
          }
        },
        (error) => console.error('GPS error:', error),
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 30000
        }
      );

      setWatchId(id);
    }

    return () => {
      if (watchId) {
        navigator.geolocation.clearWatch(watchId);
      }
    };
  }, [carerId]);

  return (
    <div className="location-tracker">
      <h3>Live Location Tracking</h3>
      {location && (
        <div>
          <p>Lat: {location.latitude.toFixed(6)}</p>
          <p>Lng: {location.longitude.toFixed(6)}</p>
          <p>Accuracy: {location.accuracy}m</p>
          {location.speed && <p>Speed: {location.speed} m/s</p>}
        </div>
      )}
    </div>
  );
};
```

### Visit Check-in
```bash
# cURL
curl -X POST http://localhost:3005/api/rostering/live/visits/visit-123/check-in \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "carerId": "carer-123",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "notes": "Arrived on time, client ready",
    "withinGeofence": true,
    "distanceFromVisit": 45
  }'
```

**Frontend:**
```javascript
const checkInToVisit = async (visitId, carerId, location) => {
  return await api.request(`/live/visits/${visitId}/check-in`, {
    method: 'POST',
    body: JSON.stringify({
      carerId,
      latitude: location.latitude,
      longitude: location.longitude,
      notes: 'Arrived at client location',
      withinGeofence: true,
      distanceFromVisit: 45
    })
  });
};
```

### Visit Check-out
```bash
# cURL
curl -X POST http://localhost:3005/api/rostering/live/visits/visit-123/check-out \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "carerId": "carer-123",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "actualDuration": 65,
    "tasksCompleted": ["Personal care", "Medication", "Light housekeeping"],
    "incidentReported": false,
    "notes": "Visit completed successfully"
  }'
```

**Frontend:**
```javascript
const checkOutFromVisit = async (visitId, carerId, visitData) => {
  return await api.request(`/live/visits/${visitId}/check-out`, {
    method: 'POST',
    body: JSON.stringify({
      carerId,
      ...visitData
    })
  });
};
```

### Get Live Dashboard
```bash
# cURL
curl -X GET http://localhost:3005/api/rostering/live/dashboard \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "activeVisits": 23,
    "completedToday": 145,
    "onTimePercentage": 0.87,
    "latenessAlerts": {
      "total": 12,
      "resolved": 10,
      "averageDelay": 8.5
    },
    "activeCarers": 18,
    "upcomingVisits": 45
  }
}
```

**Frontend Dashboard Component:**
```javascript
const LiveDashboard = () => {
  const [dashboard, setDashboard] = useState(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const data = await api.request('/live/dashboard');
        setDashboard(data.data);
      } catch (error) {
        console.error('Failed to fetch dashboard:', error);
      }
    };

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 30000); // Update every 30s

    return () => clearInterval(interval);
  }, []);

  if (!dashboard) return <div>Loading...</div>;

  return (
    <div className="live-dashboard">
      <h2>Live Operations Dashboard</h2>
      <div className="metrics-grid">
        <div className="metric">
          <h3>Active Visits</h3>
          <span className="value">{dashboard.activeVisits}</span>
        </div>
        <div className="metric">
          <h3>On-Time Rate</h3>
          <span className="value">{(dashboard.onTimePercentage * 100).toFixed(1)}%</span>
        </div>
        <div className="metric">
          <h3>Lateness Alerts</h3>
          <span className="value">{dashboard.latenessAlerts.total}</span>
        </div>
      </div>
    </div>
  );
};
```

---

## 🚨 Disruption Management

### Report Disruption
```bash
# cURL - Report carer sick
curl -X POST http://localhost:3005/api/rostering/disruptions \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "carer_sick",
    "severity": "high",
    "title": "Carer called in sick",
    "description": "Carer reported sick with flu symptoms",
    "affectedCarers": ["carer-123"],
    "affectedVisits": ["visit-123", "visit-124", "visit-125"],
    "impactData": {
      "visitsAffected": 3,
      "clientsAffected": 2,
      "estimatedDelay": 120
    },
    "location": {
      "latitude": 51.5074,
      "longitude": -0.1278
    }
  }'
```

**Postman Collection for Disruptions:**
```json
{
  "name": "Report Carer Unavailable",
  "request": {
    "method": "POST",
    "header": [
      {
        "key": "Authorization",
        "value": "Bearer {{auth_token}}"
      }
    ],
    "body": {
      "mode": "raw",
      "raw": "{\n  \"type\": \"carer_unavailable\",\n  \"severity\": \"medium\",\n  \"title\": \"Carer unavailable\",\n  \"description\": \"Carer has personal emergency\",\n  \"affectedCarers\": [\"carer-456\"],\n  \"affectedVisits\": [\"visit-456\"],\n  \"immediateActionRequired\": true\n}"
    },
    "url": {
      "raw": "{{base_url}}/api/rostering/disruptions",
      "host": ["{{base_url}}"],
      "path": ["api", "rostering", "disruptions"]
    }
  }
}
```

**Frontend Disruption Reporting:**
```javascript
const DisruptionReporter = () => {
  const [disruption, setDisruption] = useState({
    type: 'carer_sick',
    severity: 'medium',
    title: '',
    description: '',
    affectedCarers: [],
    affectedVisits: []
  });

  const reportDisruption = async () => {
    try {
      const result = await api.request('/disruptions', {
        method: 'POST',
        body: JSON.stringify({
          ...disruption,
          reportedBy: localStorage.getItem('user_id'),
          timestamp: new Date().toISOString()
        })
      });

      alert('Disruption reported successfully');
      // Reset form
      setDisruption({
        type: 'carer_sick',
        severity: 'medium',
        title: '',
        description: '',
        affectedCarers: [],
        affectedVisits: []
      });
    } catch (error) {
      alert('Failed to report disruption: ' + error.message);
    }
  };

  return (
    <div className="disruption-reporter">
      <h3>Report Disruption</h3>
      <select
        value={disruption.type}
        onChange={(e) => setDisruption({...disruption, type: e.target.value})}
      >
        <option value="carer_sick">Carer Sick</option>
        <option value="carer_unavailable">Carer Unavailable</option>
        <option value="visit_cancelled">Visit Cancelled</option>
        <option value="emergency">Emergency</option>
      </select>

      <select
        value={disruption.severity}
        onChange={(e) => setDisruption({...disruption, severity: e.target.value})}
      >
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
        <option value="critical">Critical</option>
      </select>

      <input
        type="text"
        placeholder="Title"
        value={disruption.title}
        onChange={(e) => setDisruption({...disruption, title: e.target.value})}
      />

      <textarea
        placeholder="Description"
        value={disruption.description}
        onChange={(e) => setDisruption({...disruption, description: e.target.value})}
      />

      <button onClick={reportDisruption}>Report Disruption</button>
    </div>
  );
};
```

### Get Active Disruptions
```bash
# cURL
curl -X GET http://localhost:3005/api/rostering/disruptions/active \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

### Resolve Disruption
```bash
# cURL
curl -X POST http://localhost:3005/api/rostering/disruptions/disruption-123/resolve \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resolutionId": "res_redistribute_123",
    "notes": "Visits reassigned to available carers"
  }'
```

---

## 📊 Analytics & Reporting

### Get Travel Analytics
```bash
# cURL
curl -X GET http://localhost:3005/api/rostering/analytics/travel \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "totalTravelTime": 12450,
    "averageTravelPerVisit": 18.5,
    "travelDistribution": {
      "0-10min": 234,
      "10-20min": 456,
      "20-30min": 123,
      "30min+": 45
    },
    "optimizationImpact": {
      "beforeORTools": 22.3,
      "afterORTools": 18.5,
      "improvement": 17.0
    },
    "costSavings": {
      "fuelSavings": 1250,
      "timeSavings": 890
    }
  }
}
```

**Frontend Analytics Dashboard:**
```javascript
const AnalyticsDashboard = () => {
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const [travel, compliance, disruptions] = await Promise.all([
          api.request('/analytics/travel'),
          api.request('/compliance/wtd'),
          api.request('/analytics/disruptions')
        ]);

        setAnalytics({
          travel: travel.data,
          compliance: compliance.data,
          disruptions: disruptions.data
        });
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      }
    };

    fetchAnalytics();
  }, []);

  if (!analytics) return <div>Loading analytics...</div>;

  return (
    <div className="analytics-dashboard">
      <h2>Rostering Analytics</h2>

      <div className="metric-cards">
        <div className="card">
          <h3>Travel Optimization</h3>
          <p>Average travel: {analytics.travel.averageTravelPerVisit}min</p>
          <p>Improvement: {analytics.travel.optimizationImpact.improvement}%</p>
          <p>Cost savings: £{analytics.travel.costSavings.fuelSavings}/week</p>
        </div>

        <div className="card">
          <h3>WTD Compliance</h3>
          <p>Compliance rate: {(analytics.compliance.complianceRate * 100).toFixed(1)}%</p>
          <p>Violations: {analytics.compliance.violations.length}</p>
        </div>

        <div className="card">
          <h3>Disruption Management</h3>
          <p>Total disruptions: {analytics.disruptions.totalDisruptions}</p>
          <p>Auto-resolved: {analytics.disruptions.resolutionStats.autoResolved}</p>
        </div>
      </div>

      {/* Travel Distribution Chart */}
      <div className="chart-container">
        <h3>Travel Time Distribution</h3>
        <div className="travel-chart">
          {Object.entries(analytics.travel.travelDistribution).map(([range, count]) => (
            <div key={range} className="bar">
              <span className="label">{range}</span>
              <div
                className="bar-fill"
                style={{ width: `${(count / Math.max(...Object.values(analytics.travel.travelDistribution))) * 100}%` }}
              >
                {count}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

### Compliance Reports
```bash
# cURL - WTD Compliance Report
curl -X GET "http://localhost:3005/api/rostering/compliance/wtd?period=current_week" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

---

## 🔧 System Health & Monitoring

### Health Check
```bash
# cURL
curl -X GET http://localhost:3005/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "rostering",
  "timestamp": "2024-12-05T10:30:00Z",
  "uptime": 86400,
  "memory": {
    "rss": 156000000,
    "heapTotal": 128000000,
    "heapUsed": 89000000,
    "external": 2000000
  },
  "environment": "development"
}
```

### Service Status
```bash
# cURL
curl -X GET http://localhost:3005/api/rostering/status \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "service": "rostering",
    "status": "operational",
    "version": "2.1.0",
    "features": {
      "dataValidation": true,
      "travelMatrix": true,
      "eligibilityPrecomputation": true,
      "clusterMetrics": true,
      "advancedOptimization": true,
      "publicationWorkflow": true,
      "liveOperations": true,
      "realTimeWebsockets": true,
      "disruptionManagement": true
    },
    "database": "connected",
    "websockets": {
      "available": true,
      "totalConnections": 15,
      "activeTenants": 3
    },
    "uptime": 86400
  }
}
```

### WebSocket Status
```bash
# cURL
curl -X GET http://localhost:3005/api/rostering/ws/status \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

---

## 🌐 WebSocket Integration Testing

### Frontend WebSocket Client
```javascript
// WebSocket client for real-time updates
class RosteringWebSocket {
  constructor() {
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.eventHandlers = new Map();
  }

  connect(token, tenantId, userId) {
    const wsUrl = `ws://localhost:3005`;

    this.socket = io(wsUrl, {
      auth: {
        userId,
        tenantId,
        token
      },
      transports: ['websocket', 'polling'],
      timeout: 30000
    });

    this.socket.on('connect', () => {
      console.log('Connected to rostering service');
      this.reconnectAttempts = 0;

      // Subscribe to relevant rooms
      this.subscribeToRooms(tenantId, userId);
    });

    this.socket.on('disconnect', (reason) => {
      console.log('Disconnected:', reason);
      this.handleReconnect();
    });

    this.socket.on('connect_error', (error) => {
      console.error('Connection error:', error);
      this.handleReconnect();
    });

    // Set up event listeners
    this.setupEventListeners();
  }

  subscribeToRooms(tenantId, userId) {
    this.socket.emit('subscribe', {
      rooms: [
        `tenant:${tenantId}`,
        `carer:${userId}`,
        'broadcast:disruptions'
      ]
    });
  }

  setupEventListeners() {
    // Roster events
    this.socket.on('roster:published', (data) => {
      this.emit('rosterPublished', data);
    });

    // Live operations events
    this.socket.on('visit:checkedin', (data) => {
      this.emit('visitCheckedIn', data);
    });

    this.socket.on('visit:checkedout', (data) => {
      this.emit('visitCheckedOut', data);
    });

    // Location events
    this.socket.on('location:updated', (data) => {
      this.emit('locationUpdated', data);
    });

    // Disruption events
    this.socket.on('disruption:new', (data) => {
      this.emit('disruptionReported', data);
    });

    this.socket.on('disruption:resolved', (data) => {
      this.emit('disruptionResolved', data);
    });

    // Alert events
    this.socket.on('alert:lateness', (data) => {
      this.emit('latenessAlert', data);
    });
  }

  // Event emitter pattern
  on(event, handler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event).push(handler);
  }

  emit(event, data) {
    const handlers = this.eventHandlers.get(event) || [];
    handlers.forEach(handler => handler(data));
  }

  // Send events to server
  updateLocation(locationData) {
    this.socket.emit('location:update', locationData);
  }

  checkIn(visitData) {
    this.socket.emit('visit:checkin', visitData);
  }

  checkOut(visitData) {
    this.socket.emit('visit:checkout', visitData);
  }

  reportDisruption(disruptionData) {
    this.socket.emit('disruption:report', disruptionData);
  }

  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        console.log(`Reconnection attempt ${this.reconnectAttempts}`);
        this.connect();
      }, 1000 * this.reconnectAttempts);
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
}

// Usage in React component
const RosteringApp = () => {
  const [wsClient, setWsClient] = useState(null);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const tenantId = localStorage.getItem('tenant_id');
    const userId = localStorage.getItem('user_id');

    if (token && tenantId && userId) {
      const client = new RosteringWebSocket();

      // Set up event handlers
      client.on('rosterPublished', (data) => {
        addNotification('New roster published!', 'info');
      });

      client.on('disruptionReported', (data) => {
        addNotification(`Disruption: ${data.title}`, 'warning');
      });

      client.on('latenessAlert', (data) => {
        addNotification(`Lateness alert for visit ${data.visitId}`, 'error');
      });

      client.connect(token, tenantId, userId);
      setWsClient(client);
    }

    return () => {
      if (wsClient) {
        wsClient.disconnect();
      }
    };
  }, []);

  const addNotification = (message, type) => {
    setNotifications(prev => [...prev, { id: Date.now(), message, type }]);
  };

  return (
    <div className="rostering-app">
      {/* Notification system */}
      <div className="notifications">
        {notifications.map(note => (
          <div key={note.id} className={`notification ${note.type}`}>
            {note.message}
          </div>
        ))}
      </div>

      {/* Main app content */}
      <RosterGenerator wsClient={wsClient} />
      <LiveDashboard wsClient={wsClient} />
      <DisruptionReporter wsClient={wsClient} />
    </div>
  );
};
```

---

## 📱 Complete Postman Collection

### Environment Variables
```json
{
  "base_url": "http://localhost:3005",
  "auth_token": "",
  "tenant_id": "tenant-123",
  "carer_id": "carer-456",
  "visit_id": "visit-789",
  "roster_id": "roster-101"
}
```

### Authentication Folder
```json
{
  "name": "Authentication",
  "item": [
    {
      "name": "Login",
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"email\": \"coordinator@hospital.com\",\n  \"password\": \"password123\",\n  \"tenantId\": \"{{tenant_id}}\"\n}"
        },
        "url": {
          "raw": "{{base_url}}/api/auth/login",
          "host": ["{{base_url}}"],
          "path": ["api", "auth", "login"]
        }
      },
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "if (pm.response.code === 200) {",
              "    const response = pm.response.json();",
              "    pm.environment.set('auth_token', response.data.token);",
              "}"
            ]
          }
        }
      ]
    }
  ]
}
```

### Roster Management Folder
```json
{
  "name": "Roster Management",
  "item": [
    {
      "name": "Generate Roster Scenarios",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{auth_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"startDate\": \"2024-12-05T00:00:00Z\",\n  \"endDate\": \"2024-12-11T23:59:59Z\",\n  \"strategy\": \"balanced\",\n  \"generateScenarios\": true\n}"
        },
        "url": {
          "raw": "{{base_url}}/api/rostering/roster/generate",
          "host": ["{{base_url}}"],
          "path": ["api", "rostering", "roster", "generate"]
        }
      }
    },
    {
      "name": "Get Roster Details",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{auth_token}}"
          }
        ],
        "url": {
          "raw": "{{base_url}}/api/rostering/roster/{{roster_id}}",
          "host": ["{{base_url}}"],
          "path": ["api", "rostering", "roster", "{{roster_id}}"]
        }
      }
    }
  ]
}
```

### Live Operations Folder
```json
{
  "name": "Live Operations",
  "item": [
    {
      "name": "Update Carer Location",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{auth_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"latitude\": 51.5074,\n  \"longitude\": -0.1278,\n  \"accuracy\": 10,\n  \"speed\": 25\n}"
        },
        "url": {
          "raw": "{{base_url}}/api/rostering/live/location/{{carer_id}}",
          "host": ["{{base_url}}"],
          "path": ["api", "rostering", "live", "location", "{{carer_id}}"]
        }
      }
    },
    {
      "name": "Visit Check-in",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{auth_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"carerId\": \"{{carer_id}}\",\n  \"latitude\": 51.5074,\n  \"longitude\": -0.1278,\n  \"notes\": \"Arrived on time\"\n}"
        },
        "url": {
          "raw": "{{base_url}}/api/rostering/live/visits/{{visit_id}}/check-in",
          "host": ["{{base_url}}"],
          "path": ["api", "rostering", "live", "visits", "{{visit_id}}", "check-in"]
        }
      }
    }
  ]
}
```

---

## 🧪 Automated Testing Scripts

### Bash Script for End-to-End Testing
```bash
#!/bin/bash
# test-rostering-api.sh

BASE_URL="http://localhost:3005"
TOKEN=""

echo "🧪 Starting Rostering API End-to-End Tests"
echo "==========================================="

# Test 1: Health Check
echo "1️⃣ Testing health endpoint..."
if curl -s -f $BASE_URL/health > /dev/null; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi

# Test 2: Authentication
echo "2️⃣ Testing authentication..."
AUTH_RESPONSE=$(curl -s -X POST $BASE_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@hospital.com","password":"test123","tenantId":"test-tenant"}')

if echo "$AUTH_RESPONSE" | grep -q "success.*true"; then
    TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    echo "✅ Authentication successful"
else
    echo "❌ Authentication failed"
    exit 1
fi

# Test 3: Roster Generation
echo "3️⃣ Testing roster generation..."
ROSTER_RESPONSE=$(curl -s -X POST $BASE_URL/api/rostering/roster/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-12-05T00:00:00Z",
    "endDate": "2024-12-06T23:59:59Z",
    "strategy": "balanced",
    "generateScenarios": true
  }')

if echo "$ROSTER_RESPONSE" | grep -q "success.*true"; then
    echo "✅ Roster generation successful"
else
    echo "❌ Roster generation failed"
    echo "Response: $ROSTER_RESPONSE"
fi

# Test 4: Live Operations
echo "4️⃣ Testing live operations..."
LOCATION_RESPONSE=$(curl -s -X POST $BASE_URL/api/rostering/live/location/test-carer \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 51.5074,
    "longitude": -0.1278,
    "accuracy": 10
  }')

if echo "$LOCATION_RESPONSE" | grep -q "success.*true"; then
    echo "✅ Location update successful"
else
    echo "❌ Location update failed"
fi

echo ""
echo "🎉 All tests completed!"
```

### Node.js Testing Script
```javascript
// test-api.js
const axios = require('axios');

const BASE_URL = 'http://localhost:3005';
let authToken = '';

async function runTests() {
  console.log('🧪 Running Rostering API Tests\n');

  try {
    // Health check
    console.log('1️⃣ Health Check...');
    const health = await axios.get(`${BASE_URL}/health`);
    console.log('✅ Health:', health.data.status);

    // Authentication
    console.log('2️⃣ Authentication...');
    const auth = await axios.post(`${BASE_URL}/api/auth/login`, {
      email: 'coordinator@hospital.com',
      password: 'password123',
      tenantId: 'tenant-123'
    });
    authToken = auth.data.data.token;
    console.log('✅ Authenticated');

    // Roster generation
    console.log('3️⃣ Roster Generation...');
    const roster = await axios.post(`${BASE_URL}/api/rostering/roster/generate`, {
      startDate: '2024-12-05T00:00:00Z',
      endDate: '2024-12-11T23:59:59Z',
      strategy: 'balanced',
      generateScenarios: true
    }, {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    console.log(`✅ Generated ${roster.data.data.length} scenarios`);

    // Live operations
    console.log('4️⃣ Live Operations...');
    const location = await axios.post(`${BASE_URL}/api/rostering/live/location/carer-123`, {
      latitude: 51.5074,
      longitude: -0.1278,
      accuracy: 10
    }, {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    console.log('✅ Location updated');

    // Disruption reporting
    console.log('5️⃣ Disruption Management...');
    const disruption = await axios.post(`${BASE_URL}/api/rostering/disruptions`, {
      type: 'carer_sick',
      severity: 'high',
      title: 'Carer sick',
      description: 'Carer called in sick',
      affectedCarers: ['carer-123']
    }, {
      headers: { Authorization: `Bearer ${authToken}` }
    });
    console.log('✅ Disruption reported');

    console.log('\n🎉 All tests passed!');

  } catch (error) {
    console.error('❌ Test failed:', error.response?.data || error.message);
    process.exit(1);
  }
}

runTests();
```

---

## 📋 Testing Checklist

### Pre-Flight Checks
- [ ] Docker services running (`docker-compose ps`)
- [ ] Database migrations applied
- [ ] OR-Tools optimizer healthy (`curl http://localhost:5000/health`)
- [ ] Authentication service available
- [ ] Test data seeded

### API Endpoint Testing
- [ ] Authentication (login, refresh token)
- [ ] Roster generation (single scenario, multiple scenarios)
- [ ] Roster retrieval and comparison
- [ ] Assignment management (create, validate, update)
- [ ] Live operations (location updates, check-in/out)
- [ ] Disruption reporting and resolution
- [ ] Publication workflow
- [ ] Analytics and reporting
- [ ] System health and monitoring

### WebSocket Testing
- [ ] Connection establishment
- [ ] Room subscription
- [ ] Real-time events (location, visits, disruptions)
- [ ] Message broadcasting
- [ ] Error handling and reconnection

### Frontend Integration Testing
- [ ] Component rendering
- [ ] API calls and error handling
- [ ] WebSocket event handling
- [ ] State management
- [ ] User authentication flow

### Performance Testing
- [ ] Response times (< 100ms API, < 50ms WebSocket)
- [ ] Concurrent users (50+ simultaneous connections)
- [ ] Large roster optimization (200+ visits)
- [ ] Memory usage and garbage collection
- [ ] Database query performance

This comprehensive testing guide ensures all Rostering Service functionality works correctly across different integration methods and use cases.