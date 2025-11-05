#!/bin/bash

echo "Testing OR-Tools Optimizer Service..."

# 1. Health check
echo -e "\n1. Health Check:"
curl -s http://localhost:5000/health | jq

# 2. Test optimization
echo -e "\n2. Testing Optimization:"
curl -X POST http://localhost:5000/solve \
  -H "Content-Type: application/json" \
  -d '{
    "visits": [
      {
        "id": "visit_1",
        "timeWindowStart": 540,
        "timeWindowEnd": 600,
        "duration": 60,
        "requiredSkills": ["personal-care"],
        "carerPreferences": {"carer_1": 0.9, "carer_2": 0.7},
        "visitType": "single"
      },
      {
        "id": "visit_2",
        "timeWindowStart": 600,
        "timeWindowEnd": 660,
        "duration": 45,
        "requiredSkills": ["personal-care"],
        "carerPreferences": {"carer_1": 0.8, "carer_2": 0.9},
        "visitType": "single"
      }
    ],
    "carers": [
      {
        "id": "carer_1",
        "skills": ["personal-care", "medication"],
        "maxWeeklyHours": 2880
      },
      {
        "id": "carer_2",
        "skills": ["personal-care"],
        "maxWeeklyHours": 2880
      }
    ],
    "constraints": {
      "wtdMaxHoursPerWeek": 2880,
      "travelMaxMinutes": 20,
      "bufferMinutes": 5,
      "restPeriodHours": 11
    },
    "weights": {
      "travel": 33,
      "continuity": 33,
      "workload": 34
    },
    "travelMatrix": {
      "visit_1_visit_2": {"durationMinutes": 10, "distanceMeters": 5000}
    },
    "timeoutSeconds": 60,
    "strategy": "balanced"
  }' | jq

echo -e "\n✅ Test complete!"