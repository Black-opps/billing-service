"""
Billing Service - Main application entry point.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import httpx  # Added for JWKS endpoint
import sentry_sdk
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

# Add this import at the top
# Import routers
from .api import test_sdk  # Add this line
from .api import invoices, plans, subscriptions, usage
from .api.internal import router as internal_router  # Moved here
from .core.config import settings
from .core.database import Base, SessionLocal, engine

# Add before routers
from .core.dependencies import get_current_tenant, get_current_user
from .core.exceptions import BillingError
from .services.billing_cycle import BillingCycleService
from .services.invoicing import InvoicingService
from .services.pricing import PricingService

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Sentry if configured
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,
    )

# Prometheus metrics
request_count = Counter(
    "billing_service_requests_total", "Total requests", ["method", "endpoint", "status"]
)
request_duration = Histogram(
    "billing_service_request_duration_seconds",
    "Request duration",
    ["method", "endpoint"],
)

# Background tasks
consumer_task = None
scheduled_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting Billing Service...")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    # Initialize default plans
    try:
        db = SessionLocal()
        pricing = PricingService(db)
        pricing.seed_default_plans()
        db.close()
        logger.info("Plans seeded successfully")
    except Exception as e:
        logger.warning(f"Could not seed plans: {e}")

    # Start Kafka consumer (commented out for now)
    global consumer_task, scheduled_task
    # consumer = UsageEventConsumer()
    # consumer_task = asyncio.create_task(consumer.start())
    logger.info("Kafka consumer started (placeholder)")

    # Schedule daily billing tasks
    scheduled_task = asyncio.create_task(schedule_billing_tasks())
    logger.info("🔄 Scheduled billing tasks started")

    yield

    # Shutdown
    logger.info("Shutting down Billing Service...")

    # Stop consumer
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Kafka consumer stopped")

    # Stop scheduled tasks
    if scheduled_task:
        scheduled_task.cancel()
        try:
            await scheduled_task
        except asyncio.CancelledError:
            logger.info("🔄 Scheduled billing tasks cancelled")

    logger.info("Billing Service shutdown complete")


async def schedule_billing_tasks():
    """Schedule recurring billing tasks."""
    logger.info("🔄 Scheduled billing tasks started")

    while True:
        try:
            now = datetime.utcnow()

            # Run monthly billing on 1st of month
            if now.day == 1 and now.hour == 0 and now.minute == 0:
                logger.info("📆 Running monthly billing...")
                db = SessionLocal()
                try:
                    billing = BillingCycleService(db)
                    # await billing.process_monthly_billing()
                    logger.info("✅ Monthly billing completed (placeholder)")
                except Exception as e:
                    logger.error(f"❌ Error in monthly billing: {e}")
                finally:
                    db.close()

            # Check for overdue invoices daily
            if now.hour == 1 and now.minute == 0:
                logger.info("📋 Checking overdue invoices...")
                db = SessionLocal()
                try:
                    invoicing = InvoicingService(db)
                    # await invoicing.check_overdue_invoices()
                    logger.info("✅ Overdue invoice check completed (placeholder)")
                except Exception as e:
                    logger.error(f"❌ Error in overdue invoice check: {e}")
                finally:
                    db.close()

            # Process grace periods daily
            if now.hour == 2 and now.minute == 0:
                logger.info("⏳ Processing grace periods...")
                db = SessionLocal()
                try:
                    billing = BillingCycleService(db)
                    # await billing.process_grace_periods()
                    logger.info("✅ Grace period processing completed (placeholder)")
                except Exception as e:
                    logger.error(f"❌ Error in grace period processing: {e}")
                finally:
                    db.close()

            # Sleep for 1 hour
            await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("🔄 Scheduled billing tasks cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in scheduled tasks: {e}")
            await asyncio.sleep(60)


# ==================== CREATE FASTAPI APP ====================
app = FastAPI(
    title="Billing Service",
    description="Subscription and usage-based billing service for M-PESA SaaS platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and track metrics."""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Update metrics
    request_count.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    request_duration.labels(method=request.method, endpoint=request.url.path).observe(
        duration
    )

    # Log request
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - "
        f"{duration:.3f}s"
    )

    return response


# Exception handlers
@app.exception_handler(BillingError)
async def billing_exception_handler(request: Request, exc: BillingError):
    """Handle custom billing exceptions."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.ENVIRONMENT == "development":
        content = {"detail": str(exc)}
    else:
        content = {"detail": "An internal server error occurred"}

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content
    )


# ==================== JWKS ENDPOINT ====================
@app.get("/.well-known/jwks.json")
async def get_jwks():
    """
    Proxy JWKS from Auth Service.

    This endpoint allows the billing service to serve JWKS for JWT validation.
    It proxies requests to the auth service's JWKS endpoint.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/.well-known/jwks.json"
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error("Timeout connecting to auth service for JWKS")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Auth service unavailable"},
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Auth service returned error: {e}")
        return JSONResponse(
            status_code=e.response.status_code,
            content={"detail": "Error fetching JWKS"},
        )
    except Exception as e:
        logger.error(f"Error fetching JWKS: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


# ==================== HEALTH CHECK ENDPOINT ====================
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "billing-service",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "consumer_running": (
            consumer_task is not None and not consumer_task.done()
            if consumer_task
            else False
        ),
        "scheduled_tasks_running": (
            scheduled_task is not None and not scheduled_task.done()
            if scheduled_task
            else False
        ),
    }


# ==================== ROOT ENDPOINT ====================
@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "name": "Billing Service",
        "version": "1.0.0",
        "description": "Subscription and usage-based billing for M-PESA SaaS",
        "docs": "/api/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


# ==================== DIRECT TEST ENDPOINTS ====================
@app.get("/api/v1/test/tenant")
async def test_tenant_direct(
    tenant_id: str = Depends(get_current_tenant), user: dict = Depends(get_current_user)
):
    """
    Direct test endpoint for tenant extraction.
    This bypasses the test_sdk router to debug tenant extraction.
    """
    return {
        "success": True,
        "tenant_id": tenant_id,
        "user_email": user.get("email"),
        "user_role": user.get("role"),
    }


@app.get("/api/v1/test/user")
async def test_user_direct(user: dict = Depends(get_current_user)):
    """
    Direct test endpoint for user extraction.
    This bypasses the test_sdk router to debug user extraction.
    """
    return {
        "success": True,
        "user": {
            "id": user.get("sub"),
            "email": user.get("email"),
            "role": user.get("role"),
            "tenant_id": user.get("tenant_id"),
        },
    }


# ==================== INCLUDE ROUTERS ====================
# Register all routers AFTER app is created
# After app creation, add the router
app.include_router(test_sdk.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")  # Internal router moved here


# Add this right before the main block
@app.on_event("startup")
async def startup_event():
    """Log all registered routes on startup."""
    import logging

    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("REGISTERED ROUTES:")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            logger.info(f"  {route.path} -> {route.methods}")
    logger.info("=" * 50)


# ==================== MAIN ENTRY POINT ====================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app", host="0.0.0.0", port=settings.API_PORT, reload=settings.DEBUG
    )
