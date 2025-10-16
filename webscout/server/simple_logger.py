"""
Simple logger for no-auth mode.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import sys
from webscout.Litlogger import Logger, LogLevel, LogFormat, ConsoleHandler

# Setup logger
logger = Logger(
    name="webscout.api.simple_db",
    level=LogLevel.INFO,
    handlers=[ConsoleHandler(stream=sys.stdout)],
    fmt=LogFormat.DEFAULT
)

class SimpleRequestLogger:
    """Simple request logger for no-auth mode."""

    def __init__(self):
        logger.info("Simple request logger initialized (no database).")

    async def log_request(
        self,
        request_id: str,
        ip_address: str,
        model: str,
        question: str,
        answer: str,
        **kwargs
    ) -> bool:
        """Logs request details to the console."""
        logger.info(f"Request {request_id}: model={model}, ip={ip_address}")
        return True

    async def get_recent_requests(self, limit: int = 10) -> Dict[str, Any]:
        """Returns empty list of recent requests."""
        logger.info("get_recent_requests called, but no database is configured.")
        return {"requests": [], "count": 0}

    async def get_stats(self) -> Dict[str, Any]:
        """Returns empty stats."""
        logger.info("get_stats called, but no database is configured.")
        return {"error": "No database configured.", "available": False}

# Global instance
request_logger = SimpleRequestLogger()

async def log_api_request(
    request_id: str,
    ip_address: str,
    model: str,
    question: str,
    answer: str,
    **kwargs
) -> bool:
    """Convenience function to log API requests."""
    return await request_logger.log_request(
        request_id=request_id,
        ip_address=ip_address,
        model=model,
        question=question,
        answer=answer,
        **kwargs
    )

def get_client_ip(request) -> str:
    """Extract client IP address from request."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    return getattr(request.client, "host", "unknown")

def generate_request_id() -> str:
    """Generate a unique request ID."""
    import uuid
    return str(uuid.uuid4())