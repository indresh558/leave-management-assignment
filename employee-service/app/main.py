import time
import sys
import logging
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.exc import OperationalError

from app.core.consul import register_service

from app.db.database import (
    engine,
    Base,
    SessionLocal
)

from app.db.init_db import seed_data

from app.api.employee import router as employee_router

sys.path.insert(0, "/app")
from shared.tracing import init_tracing, instrument_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Employee Service",
    description="Employee information and leave balance management service"
)

# Fix #11: Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix #13: Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses."""
    start_time = datetime.now()
    
    logger.info(f"→ {request.method} {request.url.path} (Client: {request.client.host if request.client else 'unknown'})")
    
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"← {request.method} {request.url.path} - Status: {response.status_code} ({process_time:.3f}s)")
        return response
    except Exception as exc:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"✗ {request.method} {request.url.path} - Error: {str(exc)} ({process_time:.3f}s)", exc_info=True)
        raise

init_tracing("employee-service")
instrument_app(app)


@app.on_event("startup")
def startup_event():

    register_service()

    connected = False

    while not connected:

        try:

            Base.metadata.create_all(bind=engine)

            db = SessionLocal()

            seed_data(db)

            db.close()

            connected = True

            print("Employee DB connected")

        except OperationalError:

            print("Waiting for PostgreSQL...")

            time.sleep(2)


app.include_router(
    employee_router,
    prefix="/employees",
    tags=["Employees"]
)


@app.get("/")
def root():

    return {
        "message": "Employee Service Running"
    }


@app.get("/health")
def health():
    """Health check endpoint for load balancers and orchestration systems."""
    return {
        "status": "healthy",
        "service": "employee-service"
    }