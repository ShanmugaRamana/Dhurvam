from pydantic import BaseModel, field_validator
from typing import List, Optional

class Message(BaseModel):
    sender: str
    text: str
    timestamp: int

    @field_validator('text')
    def text_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Message text cannot be empty')
        return v

class Metadata(BaseModel):
    channel: str
    language: str
    locale: str

class DetectRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[dict]
    metadata: Metadata

    @field_validator('sessionId')
    def session_id_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Session ID cannot be empty')
        return v

class DetectResponse(BaseModel):
    classification: str
