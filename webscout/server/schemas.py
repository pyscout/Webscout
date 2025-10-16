# webscout/server/schemas.py

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }