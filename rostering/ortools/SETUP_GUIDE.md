# OR-Tools Python Service - Complete Setup Guide

## 📋 Prerequisites

- Docker Desktop installed
- Docker Compose installed
- Git
- (Optional) Python 3.11+ for local development

---

## 🚀 Quick Start (Docker - Recommended)

### Step 1: Project Structure Setup

From your rostering project root:

```bash
cd rostering

# Create ortools directory structure
mkdir -p ortools/app
mkdir -p ortools/tests

# Navigate to ortools directory
cd ortools
```

### Step 2: Create Files

Copy all the files from the artifacts above into the correct locations:

```
rostering/ortools/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── optimizer.py
│   ├── models.py
├── tests/
│   └── test_optimizer.py
├── Dockerfile
├── requirements.txt
├── .dockerignore
└── README.md
```

### Step 3: Build and Run

From `rostering/` directory:

```bash
# Build the optimizer service
docker-compose build optimizer

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f optimizer
```

### Step 4: Test the Service

```bash
# Make test script executable
chmod +x ortools/test-optimizer.sh

# Run tests
./ortools/test-optimizer.sh
```

Expected output:
```
🧪 Testing OR-Tools Optimizer Service
======================================

1️⃣ Testing health endpoint...
{
  "status": "healthy",
  "version": "1.0.0",
  "ortools_version": "9.8.3296",
  "uptime_seconds": 12.34
}
✅ Health check passed

2️⃣ Testing optimization endpoint...
{
  "assignments": [...],
  "status": "OPTIMAL",
  "solution_time": 2.15
}
✅ Optimization successful: OPTIMAL

📊 Results:
   - Status: OPTIMAL
   - Assignments: 3
   - Solve time: 2.15s

✅ All tests passed!
```

---

## 🔧 Alternative Setup (Local Python Development)

### Step 1: Create Virtual Environment

```bash
cd rostering/ortools

# Create virtual environment
python3.11 -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run Locally

```bash
# Run server
uvicorn app.main:app --reload --port 5000

# In another terminal, run tests
pytest tests/ -v
```

---

## 🔗 Integration with Node.js Service

### Update Node.js Environment Variables

In your `rostering/.env` file:

```bash
# OR-Tools Python Service
PYTHON_OPTIMIZER_URL=http://optimizer:5000  # For Docker
# OR
# PYTHON_OPTIMIZER_URL=http://localhost:5000  # For local development

USE_PYTHON_OPTIMIZER=true
```

### Test Integration

From your Node.js service:

```bash
# Start Node.js service
cd rostering
npm run dev

# Test roster generation with OR-Tools
curl -X POST http://localhost:3005/api/rostering/roster/generate \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-12-05",
    "endDate": "2024-12-06",
    "strategy": "balanced",
    "generateScenarios": true
  }'
```

---

## 🐛 Troubleshooting

### Problem: Port 5000 already in use

**Solution 1:** Stop other services using port 5000
```bash
# Find process
lsof -i :5000

# Kill it
kill -9 <PID>
```

**Solution 2:** Change port in docker-compose.yml
```yaml
optimizer:
  ports:
    - "5001:5000"  # External:Internal
```

Then update `PYTHON_OPTIMIZER_URL`:
```
PYTHON_OPTIMIZER_URL=http://optimizer:5001
```

### Problem: Docker build fails

```bash
# Clear Docker cache
docker-compose down
docker system prune -a

# Rebuild
docker-compose build --no-cache optimizer
```

### Problem: Optimizer returns INFEASIBLE

Check logs:
```bash
docker-compose logs optimizer
```

Common causes:
- Travel matrix missing entries
- Skills don't match
- Time windows too narrow
- Too many visits, not enough carers

### Problem: Can't connect from Node.js service

```bash
# Test network connectivity
docker exec rostering_service ping optimizer

# Check if optimizer is running
docker ps | grep optimizer

# Check optimizer health
docker exec rostering_optimizer curl http://localhost:5000/health
```

---

## 📊 Monitoring and Logs

### View Real-time Logs

```bash
# All services
docker-compose logs -f

# Only optimizer
docker-compose logs -f optimizer

# Last 100 lines
docker-compose logs --tail=100 optimizer
```

### Health Monitoring

```bash
# Check container health
docker ps

# Manual health check
curl http://localhost:5000/health | jq
```

### Performance Monitoring

Add to your Python code for metrics:

```python
import time
import logging

logger = logging.getLogger(__name__)

@app.post("/solve")
async def optimize_roster(request: OptimizationRequest):
    start = time.time()
    
    # ... optimization logic ...
    
    logger.info(f"Optimization metrics: "
               f"visits={len(request.visits)}, "
               f"carers={len(request.carers)}, "
               f"time={time.time()-start:.2f}s")
```

---

## 🚀 Production Deployment

### Docker Production Build

Create `Dockerfile.prod`:

```dockerfile
FROM python:3.11-slim

# Production optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

# Run with gunicorn for production
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:5000"]
```

Update requirements.txt:
```
gunicorn==21.2.0
```

### Kubernetes Deployment

Create `k8s/optimizer-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: optimizer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: optimizer
  template:
    metadata:
      labels:
        app: optimizer
    spec:
      containers:
      - name: optimizer
        image: your-registry/rostering-optimizer:latest
        ports:
        - containerPort: 5000
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: optimizer-service
spec:
  selector:
    app: optimizer
  ports:
  - protocol: TCP
    port: 5000
    targetPort: 5000
```

---

## 🔒 Security Best Practices

### 1. Add Authentication

Update `app/main.py`:

```python
from fastapi import Header, HTTPException

async def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Add your token verification logic
    return True

@app.post("/solve", dependencies=[Depends(verify_token)])
async def optimize_roster(request: OptimizationRequest):
    # ... existing code
```

### 2. Rate Limiting

Add to `requirements.txt`:
```
slowapi==0.1.9
```

Update `app/main.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

@app.post("/solve")
@limiter.limit("10/minute")
async def optimize_roster(request: Request, data: OptimizationRequest):
    # ... existing code
```

### 3. Input Validation

Already implemented with Pydantic models, but add extra checks:

```python
@app.post("/solve")
async def optimize_roster(request: OptimizationRequest):
    # Validate input sizes
    if len(request.visits) > 200:
        raise HTTPException(status_code=400, 
                          detail="Too many visits (max 200)")
    
    if len(request.carers) > 50:
        raise HTTPException(status_code=400, 
                          detail="Too many carers (max 50)")
    
    # ... existing code
```

---

## 📈 Performance Tuning

### 1. Adjust Solver Parameters

In `optimizer.py`:

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = timeout
solver.parameters.num_search_workers = 8  # Adjust based on CPU
solver.parameters.log_search_progress = True
solver.parameters.cp_model_presolve = True  # Enable preprocessing
solver.parameters.linearization_level = 2  # Max linearization
```

### 2. Docker Resource Limits

In `docker-compose.yml`:

```yaml
optimizer:
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 4G
      reservations:
        cpus: '2'
        memory: 2G
```

### 3. Caching

Add Redis for caching optimization results:

```python
import redis
import hashlib
import json

redis_client = redis.Redis(host='redis', port=6379, db=0)

@app.post("/solve")
async def optimize_roster(request: OptimizationRequest):
    # Create cache key
    cache_key = hashlib.md5(
        json.dumps(request.dict(), sort_keys=True).encode()
    ).hexdigest()
    
    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Optimize
    result = optimizer.optimize()
    
    # Cache result (1 hour TTL)
    redis_client.setex(cache_key, 3600, json.dumps(result.dict()))
    
    return result
```

---

## ✅ Final Checklist

- [ ] All Python files created in correct structure
- [ ] Docker container builds successfully
- [ ] Health check endpoint responds
- [ ] Test script passes all tests
- [ ] Node.js service can connect to optimizer
- [ ] Logs show successful optimizations
- [ ] Environment variables configured
- [ ] Production considerations reviewed

---

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs optimizer`
2. Verify health: `curl http://localhost:5000/health`
3. Test manually: `./test-optimizer.sh`
4. Check network: `docker network inspect rostering_rostering_network`

Need help? Share your logs and error messages!