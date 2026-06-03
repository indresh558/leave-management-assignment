import time
import logging
import uuid
import sys
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.consul import register_service
from app.db.database import (
    engine,
    Base
)
from app.api.leave import router as leave_router

sys.path.insert(0, "/app")
from shared.tracing import init_tracing, instrument_app

app = FastAPI(
    title="Leave Service",
    description="Leave management service for applying and approving leave requests"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Fix #11: Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_tracing("leave-service")
instrument_app(app)


# Fix #13: Add comprehensive request logging middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all incoming requests with trace ID and performance metrics."""
    start_time = datetime.now()
    trace_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    request.state.logger = logging.getLogger("leave-service")
    
    # Log incoming request
    request.state.logger.info(
        f"→ {request.method} {request.url.path} [trace_id={trace_id}] (Client: {request.client.host if request.client else 'unknown'})"
    )

    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        request.state.logger.info(
            f"← {request.method} {request.url.path} [trace_id={trace_id}] - Status: {response.status_code} ({process_time:.3f}s)"
        )
        response.headers["X-Request-ID"] = trace_id
        return response
    except Exception as exc:
        process_time = (datetime.now() - start_time).total_seconds()
        request.state.logger.error(
            f"✗ {request.method} {request.url.path} [trace_id={trace_id}] - Error: {str(exc)} ({process_time:.3f}s)",
            exc_info=True
        )
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception during request %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logging.warning("HTTP exception %s during request %s: %s", exc.status_code, request.url.path, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.on_event("startup")
def startup_event():

    register_service()

    connected = False

    while not connected:

        try:

            Base.metadata.create_all(bind=engine)

            connected = True

            print("Leave DB connected")

        except OperationalError:

            print("Waiting for PostgreSQL...")

            time.sleep(2)


app.include_router(
    leave_router,
    prefix="/leaves",
    tags=["Leaves"]
)


@app.get("/")
def root():

    return {
        "message": "Leave Service Running"
    }


@app.get("/health")
def health():
    """Health check endpoint for load balancers and orchestration systems."""
    return {
        "status": "healthy",
        "service": "leave-service"
    }
