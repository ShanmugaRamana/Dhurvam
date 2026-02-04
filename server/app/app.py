from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.routes import auth, detect, logs
from app.core.security import get_api_key
from app.core.database import connect_db, close_db
from app.core.logger import add_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    add_log("Starting Dhurvam AI API server...")
    try:
        await connect_db()
    except Exception as e:
        add_log(f"FATAL: Could not connect to MongoDB. Exiting. Error: {str(e)}")
        raise
    
    # Start background task for auto-timeout
    import asyncio
    from app.core.background_tasks import check_inactive_sessions
    timeout_task = asyncio.create_task(check_inactive_sessions())
    add_log("Background task: Auto-timeout checker started")
    
    yield
    
    # Shutdown
    timeout_task.cancel()
    add_log("Background task: Auto-timeout checker stopped")
    await close_db()
    add_log("Server shutdown complete.")


app = FastAPI(title="Dhurvam AI API", lifespan=lifespan)

# CORS logic
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler for debugging
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    from app.core.logger import add_log
    add_log(f"[VALIDATION_ERROR] Request validation failed: {exc}")
    add_log(f"[VALIDATION_ERROR] Request body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

app.include_router(auth.router, prefix="/api/honeypot", tags=["auth"], dependencies=[Depends(get_api_key)])
app.include_router(detect.router, prefix="/api/honeypot", tags=["detect"], dependencies=[Depends(get_api_key)])
app.include_router(logs.router, prefix="/api/honeypot", tags=["logs"], dependencies=[Depends(get_api_key)])

# Also expose /detect directly for hackathon compatibility
app.include_router(detect.router, prefix="", tags=["hackathon"], dependencies=[Depends(get_api_key)])


@app.get("/", dependencies=[Depends(get_api_key)])
def read_root():
    return {"message": "Server is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring (no auth required)."""
    from datetime import datetime, timezone, timedelta
    from app.core.database import get_database
    
    # Indian Standard Time
    IST = timezone(timedelta(hours=5, minutes=30))
    
    # Check database connection
    db_status = "healthy"
    try:
        db = get_database()
        if db is None:
            db_status = "disconnected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "dhurvam-honeypot-api",
        "database": db_status,
        "timestamp": datetime.now(IST).isoformat(),
        "timezone": "IST (UTC+5:30)"
    }
