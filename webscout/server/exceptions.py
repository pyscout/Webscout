"""
Custom exceptions for the Webscout API.
"""

import json
import re
from typing import Optional
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from .request_models import ErrorDetail, ErrorResponse


def clean_text(text):
    """Clean text by removing null bytes and control characters except newlines and tabs."""
    if not isinstance(text, str):
        return text
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Keep newlines, tabs, and other printable characters, remove other control chars
    # This regex matches control characters except \n, \r, \t
    return re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: int = HTTP_500_INTERNAL_SERVER_ERROR,
                 error_type: str = "server_error", param: Optional[str] = None,
                 code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.param = param
        self.code = code
        super().__init__(message)

    def to_response(self) -> JSONResponse:
        """Convert to FastAPI JSONResponse."""
        error_detail = ErrorDetail(
            message=self.message,
            type=self.error_type,
            param=self.param,
            code=self.code
        )
        error_response = ErrorResponse(error=error_detail)
        return JSONResponse(
            status_code=self.status_code,
            content=error_response.model_dump(exclude_none=True)
        )


def format_exception(e) -> str:
    """Format exception for JSON response."""
    if isinstance(e, str):
        message = e
    else:
        message = f"{e.__class__.__name__}: {str(e)}"
    return json.dumps({
        "error": {
            "message": message,
            "type": "server_error",
            "param": None,
            "code": "internal_server_error"
        }
    })
