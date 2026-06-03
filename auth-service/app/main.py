import time
from sqlalchemy.exc import OperationalError
import logging
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.core.consul import register_service

from app.db.database import engine, SessionLocal
from app.db.init_db import seed_users

from app.models.user import User
from app.db.database import Base

import sys
sys.path.insert(0, "/app")
from shared.tracing import init_tracing, instrument_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    description="Authentication service for user login and token generation"
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
    
    # Log request
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

init_tracing("auth-service")
instrument_app(app)


@app.on_event("startup")
def startup_event():

    register_service()

    connected = False

    while not connected:

        try:

            print("Trying to connect to PostgreSQL...")

            # Create tables
            Base.metadata.create_all(bind=engine)

            # Create DB session
            db = SessionLocal()

            # Seed users
            seed_users(db)

            db.close()

            connected = True

            print("PostgreSQL connected successfully")

        except OperationalError as ex:

            print("PostgreSQL not ready yet...")
            print(str(ex))

            time.sleep(2)


app.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)


@app.get("/")
def root():

    return {
        "message": "Auth Service Running"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }