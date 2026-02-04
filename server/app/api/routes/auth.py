from fastapi import APIRouter, Header, HTTPException, Body
from pydantic import BaseModel
from app.core.config import API_KEY, PASSWORD, ADMIN_EMAIL

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(
    login_request: LoginRequest
):
    # API Key is checked by global dependency
    
    if login_request.email != ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if login_request.password != PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {"success": True, "message": "Login successful"}
