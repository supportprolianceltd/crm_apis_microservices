"""
FastAPI server for OR-Tools optimization service
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from models import OptimizationRequest, OptimizationResponse
from optimizer import optimize_roster
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="OR-Tools Roster Optimizer",
    description="Constraint programming solver for staff rostering optimization",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ortools-optimizer",
        "timestamp": time.time()
    }

@app.post("/solve", response_model=OptimizationResponse)
async def solve(request: OptimizationRequest):
    """
    Solve roster optimization problem
    
    - **visits**: List of visits to schedule
    - **carers**: List of available carers
    - **constraints**: Working time and travel constraints
    - **weights**: Objective function weights
    - **travelMatrix**: Travel times between locations
    - **timeoutSeconds**: Maximum solve time (10-600 seconds)
    """
    try:
        logger.info(f"Received optimization request: {len(request.visits)} visits, {len(request.carers)} carers")
        
        # Validate input
        if not request.visits:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No visits provided"
            )
        
        if not request.carers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No carers provided"
            )
        
        # Optimize
        result = optimize_roster(request)
        
        logger.info(f"Optimization completed: {result.status}, {len(result.assignments)} assignments")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization failed: {str(e)}"
        )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OR-Tools Roster Optimizer",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "solve": "/solve (POST)",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")