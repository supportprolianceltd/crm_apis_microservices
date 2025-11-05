from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum

class VisitType(str, Enum):
    SINGLE = "single"
    DOUBLE = "double"

class Visit(BaseModel):
    id: str
    timeWindowStart: int  # Minutes from midnight
    timeWindowEnd: int
    duration: int  # Minutes
    requiredSkills: List[str]
    carerPreferences: Dict[str, float]  # carerId -> preference score
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    visitType: VisitType = VisitType.SINGLE

class Carer(BaseModel):
    id: str
    skills: List[str]
    maxWeeklyHours: int  # Minutes
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class Constraints(BaseModel):
    wtdMaxHoursPerWeek: int  # Minutes
    travelMaxMinutes: int
    bufferMinutes: int
    restPeriodHours: int

class Weights(BaseModel):
    travel: int
    continuity: int
    workload: int

class TravelTime(BaseModel):
    durationMinutes: int
    distanceMeters: int

class OptimizationRequest(BaseModel):
    visits: List[Visit]
    carers: List[Carer]
    constraints: Constraints
    weights: Weights
    travelMatrix: Dict[str, TravelTime]
    timeoutSeconds: int = Field(default=300, ge=10, le=600)
    strategy: str = "balanced"

class Assignment(BaseModel):
    visitId: str
    carerId: str
    startTime: int
    endTime: int
    travelTime: int
    score: float

class Violations(BaseModel):
    wtd: int
    restPeriod: int
    travel: int
    skills: int

class OptimizationResponse(BaseModel):
    assignments: List[Assignment]
    objective: float
    solutionTime: float
    status: str  # OPTIMAL, FEASIBLE, INFEASIBLE, ERROR
    violations: Violations
    message: str = ""



