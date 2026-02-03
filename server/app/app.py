import os
from dotenv import load_dotenv
from fastapi import FastAPI, Security, HTTPException, status
from fastapi.security import APIKeyHeader
import uvicorn

load_dotenv()

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials",
    )

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from .routers import honeypot

app = FastAPI(
    title="Dhurvam AI",
    description="AI aimed at detecting scammer messages and engaging them in safe conversations.",
    dependencies=[Security(get_api_key)]
)

from .middleware.input_validation import validation_exception_handler

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return await validation_exception_handler(request, exc)

from .middleware.time_log import log_process_time

app.middleware("http")(log_process_time)

app.include_router(honeypot.router, prefix="/api/honeypot")

@app.get("/")
def read_root():
    return {"system": "Dhurvam AI", "status": "Operational", "message": "Advanced Scam Detection and Countermeasures System Online"}


