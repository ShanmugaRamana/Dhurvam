from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import time

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


# Middleware to log raw requests BEFORE FastAPI parses them
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class RawRequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        # Log ALL requests, not just /detect
        try:
            # Log request details
            add_log(f"[RAW_REQUEST] Method: {request.method}")
            add_log(f"[RAW_REQUEST] Path: {request.url.path}")
            add_log(f"[RAW_REQUEST] Query: {request.url.query}")
            add_log(f"[RAW_REQUEST] Client: {request.client.host if request.client else 'unknown'}")
            
            # Log all headers
            headers_dict = dict(request.headers)
            add_log(f"[RAW_REQUEST_HEADERS] {json.dumps(headers_dict, indent=2)}")
            
            # Log body
            body = await request.body()
            body_str = body.decode('utf-8') if body else "empty"
            add_log(f"[RAW_REQUEST_BODY] {body_str}")
            
            # Try to parse as JSON
            try:
                body_json = json.loads(body_str)
                add_log(f"[RAW_REQUEST_BODY_JSON] {json.dumps(body_json, indent=2)}")
            except json.JSONDecodeError:
                add_log(f"[RAW_REQUEST_BODY_NOT_JSON] Body is not valid JSON")
                
        except Exception as e:
            add_log(f"[RAW_REQUEST_ERROR] {str(e)}")
            import traceback
            add_log(f"[RAW_REQUEST_TRACEBACK] {traceback.format_exc()}")
        
        response = await call_next(request)
        
        # Log response
        add_log(f"[RAW_RESPONSE] Status: {response.status_code}")
        
        return response

app.add_middleware(RawRequestLoggingMiddleware)


# CORS logic
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://hackathon.guvi.in",
    "*"  # Allow all origins for hackathon
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for hackathon
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


# Diagnostic endpoint - echoes request back (NO AUTH for debugging)
from fastapi import Request

@app.post("/echo")
async def echo_request(request: Request):
    """Echo back the request for debugging hackathon integration (no auth required)."""
    body = await request.body()
    try:
        import json
        body_json = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        body_json = body.decode('utf-8')
    
    add_log(f"[ECHO] Received request: {body_json}")
    
    return {
        "status": "success",
        "echo": body_json,
        "headers": dict(request.headers)
    }

# Public debug endpoint for hackathon testing
@app.post("/debug")
async def debug_request(request: Request):
    """Debug endpoint that shows full request details (no auth required)."""
    body = await request.body()
    body_str = body.decode('utf-8') if body else "empty"
    
    try:
        body_json = json.loads(body_str)
    except json.JSONDecodeError:
        body_json = None
    
    headers_dict = dict(request.headers)
    
    add_log(f"[DEBUG] Method: {request.method}")
    add_log(f"[DEBUG] Path: {request.url.path}")
    add_log(f"[DEBUG] Headers: {json.dumps(headers_dict, indent=2)}")
    add_log(f"[DEBUG] Body: {body_str}")
    
    return {
        "status": "success",
        "request": {
            "method": request.method,
            "path": request.url.path,
            "query": request.url.query,
            "headers": headers_dict,
            "body_raw": body_str,
            "body_json": body_json
        }
    }


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
