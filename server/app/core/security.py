from fastapi import Header, HTTPException
from app.core.config import API_KEY

async def get_api_key(x_api_key: str = Header(None)):
    if x_api_key is None or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return x_api_key
