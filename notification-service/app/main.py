import asyncio
import logging
import sys
from datetime import datetime

from fastapi import FastAPI, Request

from app.core.consumer import NotificationConsumer

sys.path.insert(0, "/app")
from shared.tracing import init_tracing, instrument_app

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Notification Service"
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

init_tracing("notification-service")
instrument_app(app)

consumer = NotificationConsumer()


@app.on_event("startup")
async def startup_event():
    app.state.consumer_task = asyncio.create_task(consumer.start())


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "consumer_task"):
        app.state.consumer_task.cancel()
    await consumer.close()


@app.get("/")
def root():
    return {"message": "Notification Service Running"}


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint for load balancers and orchestration systems.
    
    **Response:** Service status and timestamp
    """
    return {
        "status": "healthy",
        "service": "notification-service",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/notifications", tags=["Notifications"], summary="Get Notification History")
def get_notifications(skip: int = 0, limit: int = 20):
    """
    Get notification history.
    
    **Query Parameters:**
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 20)
    
    **Response:** List of notification records
    
    **Note:** This endpoint returns in-memory history. In production,
    this should be persisted in a database and queryable by user.
    """
    history = consumer.notification_history
    total = len(history)
    paginated = history[skip:skip + limit]
    
    return {
        "items": paginated,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@app.get("/notifications/{recipient}", tags=["Notifications"], summary="Get Notifications for Recipient")
def get_user_notifications(recipient: str, skip: int = 0, limit: int = 20):
    """
    Get notifications for a specific recipient (employee or manager).
    
    **Path Parameters:**
    - **recipient**: Username of the recipient
    
    **Query Parameters:**
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 20)
    
    **Response:** List of notifications for the recipient
    """
    history = consumer.notification_history
    user_notifications = [
        notif for notif in history 
        if notif.get("recipient") == recipient
    ]
    total = len(user_notifications)
    paginated = user_notifications[skip:skip + limit]
    
    return {
        "recipient": recipient,
        "items": paginated,
        "total": total,
        "skip": skip,
        "limit": limit
    }
