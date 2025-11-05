# OR-Tools Roster Optimizer Service

Python-based constraint programming service using Google OR-Tools for complex roster optimization.

## 🚀 Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run server locally
uvicorn app.main:app --reload --port 5000
```

### Docker

```bash
# Build image
docker build -t rostering-optimizer .

# Run container
docker run -p 5000:5000 rostering-optimizer

# Or use docker-compose (from parent directory)
docker-compose up optimizer
```

## 📡 API Endpoints

### Health Check
```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "ortools_version": "9.8.3296",
  "uptime_seconds": 123.45
}
```

### Optimize Roster
```bash
POST /solve
Content-Type: application/json
```

Request body example:
```json
{
  "visits": [
    {
      "id": "visit_1",
      "time_window_start": 540,
      "time_window_end": 720,
      "duration": 60,
      "required_skills": ["personal-care"],
      "carer_preferences": {"carer_1": 1.0}
    }
  ],
  "carers": [
    {
      "id": "carer_1",
      "skills": ["personal-care"],
      "max_weekly_hours": 48.0
    }
  ],
  "constraints": {
    "wtd_max_hours_per_week": 48.0,
    "travel_max_minutes": 20,
    "buffer_minutes": 5,
    "rest_period_hours": 11
  },
  "weights": {
    "travel": 33,
    "continuity": 33,
    "workload": 34
  },
  "travel_matrix": {
    "visit_1_visit_2": {
      "duration_minutes": 10,
      "distance_meters": 2000
    }
  },
  "timeout_seconds": 300,
  "strategy": "balanced"
}
```

Response:
```json
{
  "assignments": [
    {
      "visit_id": "visit_1",
      "carer_id": "carer_1",
      "start_time": 540,
      "end_time": 600,
      "travel_time": 0,
      "score": 100.0
    }
  ],
  "objective": 1250.5,
  "solution_time": 2.34,
  "status": "OPTIMAL",
  "violations": {
    "wtd": 0,
    "rest_period": 0,
    "travel": 0,
    "skills": 0
  },
  "message": "Found optimal solution"
}
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_optimizer.py::test_optimizer_solves_simple_problem -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## 🏗️ Architecture

### Constraint Programming Model

The optimizer uses Google OR-Tools CP-SAT solver with the following constraints:

1. **Assignment Constraints**
   - Each visit assigned to exactly one carer
   - Skills matching required

2. **Temporal Constraints**
   - No overlapping visits for same carer
   - Time windows respected
   - Buffer time between visits

3. **Legal Constraints**
   - Working Time Directive (max hours)
   - Minimum rest periods
   - Maximum travel time

4. **Optimization Objectives**
   - Minimize travel time
   - Balance workload across carers
   - Maximize continuity of care

### Decision Variables

- `x[v][c]`: Boolean - visit `v` assigned to carer `c`
- `start_times[v]`: Integer - start time for visit `v` (minutes from midnight)

### Performance

- Typical solve time: 1-5 seconds for 50 visits, 10 carers
- Complex scenarios: up to 300 seconds (configurable timeout)
- Multi-threaded solving (8 workers by default)

## 🔧 Configuration

Environment variables:

- `UVICORN_PORT`: Server port (default: 5000)
- `UVICORN_WORKERS`: Number of worker processes (default: 4)
- `LOG_LEVEL`: Logging level (default: INFO)

## 📊 Monitoring

### Health Checks

Docker health check runs every 30 seconds:
```bash
curl http://localhost:5000/health
```

### Logs

View logs:
```bash
docker logs rostering_optimizer -f
```

## 🐛 Troubleshooting

### Optimizer returns INFEASIBLE

**Possible causes:**
- Constraints too strict (e.g., travel limits too low)
- Not enough carers with required skills
- Time windows too narrow
- WTD hours exceeded

**Solutions:**
- Relax travel limits
- Add more carers
- Widen time windows
- Check skill requirements

### Slow optimization

**Causes:**
- Large problem size (>100 visits)
- Complex constraints
- Tight time windows

**Solutions:**
- Increase timeout
- Split into smaller problems
- Simplify constraints

## 📚 References

- [OR-Tools Documentation](https://developers.google.com/optimization)
- [CP-SAT Solver Guide](https://developers.google.com/optimization/cp/cp_solver)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)