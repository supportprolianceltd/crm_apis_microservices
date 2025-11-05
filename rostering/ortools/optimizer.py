"""
FIXED OR-Tools Optimizer - Reduces constraint complexity
"""

import time
from typing import Dict, List, Tuple, Set
from ortools.sat.python import cp_model
from models import OptimizationRequest, Assignment, Violations, OptimizationResponse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RosterOptimizer:
    def __init__(self, request: OptimizationRequest):
        self.request = request
        self.model = cp_model.CpModel()
        self.visits = request.visits
        self.carers = request.carers
        self.constraints = request.constraints
        self.weights = request.weights
        self.travel_matrix = request.travelMatrix
        
        self.num_visits = len(self.visits)
        self.num_carers = len(self.carers)
        
        # Decision variables
        self.x = {}
        self.start_times = {}
        self.end_times = {}
        
        # ✅ FIX: Pre-filter eligible carers per visit
        self.eligible_carers = self._precompute_eligibility()
        
    def _precompute_eligibility(self) -> Dict[int, Set[int]]:
        """Pre-filter carers who can do each visit (reduces search space)"""
        eligible = {}
        
        for v in range(self.num_visits):
            visit = self.visits[v]
            required_skills = set(visit.requiredSkills)
            eligible[v] = set()
            
            for c in range(self.num_carers):
                carer = self.carers[c]
                carer_skills = set(carer.skills)
                
                # Must have required skills
                if required_skills and not required_skills.issubset(carer_skills):
                    continue
                
                eligible[v].add(c)
        
        logger.info(f"Eligibility computed: avg {sum(len(e) for e in eligible.values()) / len(eligible):.1f} carers per visit")
        return eligible
        
    def build_model(self):
        """Build constraint model with optimizations"""
        logger.info(f"Building model: {self.num_visits} visits, {self.num_carers} carers")
        
        # 1. Create variables (only for eligible carers)
        self._create_variables()
        
        # 2. Add constraints
        self._add_assignment_constraints()
        self._add_wtd_constraints()
        self._add_time_window_constraints()
        self._add_no_overlap_constraints()
        
        # ✅ FIX: Only add travel constraints for nearby visits
        self._add_optimized_travel_constraints()
        
        # 3. Define objective
        self._define_objective()
        
    def _create_variables(self):
        """Create decision variables only for eligible assignments"""
        # Assignment variables (only for eligible carers)
        for v in range(self.num_visits):
            for c in self.eligible_carers[v]:
                self.x[(v, c)] = self.model.NewBoolVar(f'x_v{v}_c{c}')
        
        # Start and end time variables
        for v in range(self.num_visits):
            visit = self.visits[v]
            self.start_times[v] = self.model.NewIntVar(
                visit.timeWindowStart,
                visit.timeWindowEnd,
                f'start_v{v}'
            )
            self.end_times[v] = self.model.NewIntVar(
                visit.timeWindowStart,
                visit.timeWindowEnd + visit.duration,
                f'end_v{v}'
            )
            self.model.Add(self.end_times[v] == self.start_times[v] + visit.duration)
    
    def _add_assignment_constraints(self):
        """Each visit assigned to exactly one eligible carer"""
        for v in range(self.num_visits):
            eligible = list(self.eligible_carers[v])
            if not eligible:
                logger.error(f"Visit {v} has no eligible carers!")
                continue
            self.model.Add(sum(self.x.get((v, c), 0) for c in eligible) == 1)
    
    def _add_wtd_constraints(self):
        """Working Time Directive constraints"""
        max_minutes = self.constraints.wtdMaxHoursPerWeek
        
        for c in range(self.num_carers):
            total_minutes = sum(
                self.x.get((v, c), 0) * self.visits[v].duration 
                for v in range(self.num_visits)
                if c in self.eligible_carers[v]
            )
            self.model.Add(total_minutes <= max_minutes)
    
    def _add_time_window_constraints(self):
        """Visits must start within time windows"""
        for v in range(self.num_visits):
            visit = self.visits[v]
            self.model.Add(self.start_times[v] >= visit.timeWindowStart)
            self.model.Add(self.start_times[v] <= visit.timeWindowEnd)
    
    def _add_no_overlap_constraints(self):
        """Same carer cannot do overlapping visits"""
        for c in range(self.num_carers):
            intervals = []
            for v in range(self.num_visits):
                if c not in self.eligible_carers[v]:
                    continue
                    
                interval = self.model.NewOptionalIntervalVar(
                    self.start_times[v],
                    self.visits[v].duration,
                    self.end_times[v],
                    self.x[(v, c)],
                    f'interval_v{v}_c{c}'
                )
                intervals.append(interval)
            
            if intervals:
                self.model.AddNoOverlap(intervals)
    
    def _add_optimized_travel_constraints(self):
        """✅ FIX: Only add constraints for visits that could be sequential"""
        buffer = self.constraints.bufferMinutes
        max_travel = self.constraints.travelMaxMinutes
        
        # ✅ Group visits by time bucket (30min buckets)
        time_buckets = {}
        for v in range(self.num_visits):
            bucket = self.visits[v].timeWindowStart // 30
            if bucket not in time_buckets:
                time_buckets[bucket] = []
            time_buckets[bucket].append(v)
        
        constraint_count = 0
        
        for c in range(self.num_carers):
            # ✅ Only check visits in adjacent time buckets
            sorted_buckets = sorted(time_buckets.keys())
            
            for i, bucket in enumerate(sorted_buckets):
                current_visits = time_buckets[bucket]
                
                # Check next 2 buckets only (within ~1 hour)
                for next_bucket in sorted_buckets[i+1:i+3]:
                    if next_bucket not in time_buckets:
                        continue
                        
                    next_visits = time_buckets[next_bucket]
                    
                    for v1 in current_visits:
                        if c not in self.eligible_carers[v1]:
                            continue
                            
                        for v2 in next_visits:
                            if c not in self.eligible_carers[v2]:
                                continue
                            
                            # Get travel time
                            travel_key = f"{self.visits[v1].id}_{self.visits[v2].id}"
                            travel = self.travel_matrix.get(travel_key)
                            
                            if not travel or travel.durationMinutes > max_travel:
                                continue
                            
                            # Create constraint
                            both = self.model.NewBoolVar(f'seq_c{c}_v{v1}_v{v2}')
                            self.model.Add(self.x[(v1, c)] + self.x[(v2, c)] == 2).OnlyEnforceIf(both)
                            
                            gap = travel.durationMinutes + buffer
                            self.model.Add(
                                self.end_times[v1] + gap <= self.start_times[v2]
                            ).OnlyEnforceIf(both)
                            
                            constraint_count += 1
        
        logger.info(f"Added {constraint_count} travel constraints (optimized)")
    
    def _define_objective(self):
        """Define optimization objective"""
        objective_terms = []

        # 1. Minimize travel
        travel_sum = 0
        for c in range(self.num_carers):
            for v1 in range(self.num_visits):
                if c not in self.eligible_carers[v1]:
                    continue
                    
                for v2 in range(v1 + 1, self.num_visits):
                    if c not in self.eligible_carers[v2]:
                        continue
                    
                    travel_key = f"{self.visits[v1].id}_{self.visits[v2].id}"
                    travel = self.travel_matrix.get(travel_key)
                    
                    if travel:
                        both = self.model.NewBoolVar(f'both_c{c}_v{v1}_v{v2}')
                        self.model.Add(both == 1).OnlyEnforceIf([self.x[(v1, c)], self.x[(v2, c)]])
                        travel_sum += both * travel.durationMinutes

        objective_terms.append(self.weights.travel * travel_sum)

        # 2. Maximize continuity
        continuity_bonus = 0
        for v in range(self.num_visits):
            visit = self.visits[v]
            for c in self.eligible_carers[v]:
                carer = self.carers[c]
                preference = visit.carerPreferences.get(carer.id, 0.3)
                continuity_bonus += self.x[(v, c)] * int(preference * 100)

        objective_terms.append(-self.weights.continuity * continuity_bonus)

        # 3. Balance workload
        carer_loads = []
        for c in range(self.num_carers):
            load = self.model.NewIntVar(0, 3000, f'load_c{c}')
            self.model.Add(
                load == sum(
                    self.x.get((v, c), 0) * self.visits[v].duration 
                    for v in range(self.num_visits)
                    if c in self.eligible_carers[v]
                )
            )
            carer_loads.append(load)

        max_load = self.model.NewIntVar(0, 3000, 'max_load')
        for load in carer_loads:
            self.model.Add(max_load >= load)

        objective_terms.append(self.weights.workload * max_load)

        self.model.Minimize(sum(objective_terms))
    
    def solve(self) -> OptimizationResponse:
        """Solve with timeout"""
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = min(self.request.timeoutSeconds, 25)
        solver.parameters.num_search_workers = 4
        solver.parameters.log_search_progress = False

        logger.info(f"Starting solve (timeout: {solver.parameters.max_time_in_seconds}s)")
        start_time = time.time()

        status = solver.Solve(self.model)
        solve_time = time.time() - start_time

        logger.info(f"Solved in {solve_time:.2f}s with status: {status}")

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return self._extract_solution(solver, status, solve_time)
        else:
            return self._handle_infeasible(status, solve_time)
    
    def _extract_solution(self, solver, status, solve_time):
        """Extract solution"""
        assignments = []
        
        for v in range(self.num_visits):
            for c in self.eligible_carers[v]:
                if solver.Value(self.x[(v, c)]) == 1:
                    visit = self.visits[v]
                    carer = self.carers[c]
                    start = solver.Value(self.start_times[v])
                    end = solver.Value(self.end_times[v])
                    
                    travel_time = 0
                    for v2 in range(self.num_visits):
                        if v2 != v and c in self.eligible_carers[v2]:
                            if solver.Value(self.x.get((v2, c), 0)) == 1:
                                if solver.Value(self.start_times[v2]) < start:
                                    travel_key = f"{self.visits[v2].id}_{visit.id}"
                                    travel = self.travel_matrix.get(travel_key)
                                    if travel:
                                        travel_time = travel.durationMinutes
                    
                    assignments.append(Assignment(
                        visitId=visit.id,
                        carerId=carer.id,
                        startTime=start,
                        endTime=end,
                        travelTime=travel_time,
                        score=100.0
                    ))
        
        return OptimizationResponse(
            assignments=assignments,
            objective=solver.ObjectiveValue(),
            solutionTime=solve_time,
            status='OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE',
            violations=Violations(wtd=0, restPeriod=0, travel=0, skills=0),
            message=f"Found {len(assignments)} assignments"
        )
    
    def _handle_infeasible(self, status, solve_time):
        """Handle infeasible"""
        return OptimizationResponse(
            assignments=[],
            objective=0.0,
            solutionTime=solve_time,
            status="INFEASIBLE",
            violations=Violations(wtd=0, restPeriod=0, travel=0, skills=0),
            message="No feasible solution"
        )

def optimize_roster(request: OptimizationRequest) -> OptimizationResponse:
    """Main entry point"""
    try:
        optimizer = RosterOptimizer(request)
        optimizer.build_model()
        return optimizer.solve()
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return OptimizationResponse(
            assignments=[],
            objective=0.0,
            solutionTime=0.0,
            status="ERROR",
            violations=Violations(wtd=0, restPeriod=0, travel=0, skills=0),
            message=f"Failed: {str(e)}"
        )