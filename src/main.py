"""
Billing Service - Main application entry point.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
import asyncio
from prometheus_client import make_asgi_app, Counter, Histogram
import sentry_sdk

from .api import plans, subscriptions, usage, invoices, payments
from .core.config import settings
from .core.database import engine, Base
from .core.exceptions import BillingError
from .consumers.usage_consumer import UsageEventConsumer
from .services.billing_cycle import BillingCycleService
from .services.pricing import PricingService

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Sentry if configured
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1
    )

# Prometheus metrics
request_count = Counter(
    'billing_service_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)
request_duration = Histogram(
    'billing_service_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

# Background tasks
consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting Billing Service...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    # Initialize default plans
    async with SessionLocal() as db:
        pricing = PricingService(db)
        await pricing.initialize_plans()
    
    # Start Kafka consumer
    global consumer_task
    consumer = UsageEventConsumer()
    consumer_task = asyncio.create_task(consumer.start())
    logger.info("Kafka consumer started")
    
    # Schedule daily billing tasks
    asyncio.create_task(schedule_billing_tasks())
    
    yield
    
    # Shutdown
    logger.info("Shutting down Billing Service...")
    
    # Stop consumer
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


async def schedule_billing_tasks():
    """Schedule recurring billing tasks."""
    while True:
        try:
            now = datetime.utcnow()
            
            # Run monthly billing on 1st of month
            if now.day == 1 and now.hour == 0 and now.minute == 0:
                async with SessionLocal() as db:
                    billing = BillingCycleService(db)
                    await billing.process_monthly_billing()
                    logger.info("Monthly billing completed")
            
            # Check for overdue invoices daily
            if now.hour == 1 and now.minute == 0:
                async with SessionLocal() as db:
                    invoicing = InvoicingService(db)
                    await invoicing.check_overdue_invoices()
                    logger.info("Overdue invoice check completed")
            
            # Process grace periods daily
            if now.hour == 2 and now.minute == 0:
                async with SessionLocal() as db:
                    billing = BillingCycleService(db)
                    await billing.process_grace_periods()
                    logger.info("Grace period processing completed")
            
            # Sleep for 1 hour
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in scheduled tasks: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute


# Create FastAPI app
app = FastAPI(
    title="Billing Service",
    description="Subscription and usage-based billing service for M-PESA SaaS platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
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
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
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
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.ENVIRONMENT == "development":
        content = {"detail": str(exc)}
    else:
        content = {"detail": "An internal server error occurred"}
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "billing-service",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "consumer_running": consumer_task is not None and not consumer_task.done()
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "name": "Billing Service",
        "version": "1.0.0",
        "description": "Subscription and usage-based billing for M-PESA SaaS",
        "docs": "/api/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


# Include routers
app.include_router(plans.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.API_PORT,
        reload=settings.DEBUG
    )