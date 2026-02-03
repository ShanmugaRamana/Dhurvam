from fastapi import APIRouter, HTTPException
from ..models.schemas import DetectRequest, DetectResponse
from ..services import llm

router = APIRouter()

@router.post("/detect", response_model=DetectResponse)
async def detect_scam(request: DetectRequest):
    classification = llm.analyze_message(request.message.text)
    return DetectResponse(classification=classification)
