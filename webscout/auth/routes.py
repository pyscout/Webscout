"""
API routes for the Webscout server.
"""

import time
import uuid
import secrets
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Body, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from webscout.Litlogger import Logger, LogLevel, LogFormat, ConsoleHandler
from .config import AppConfig
from .request_models import (
    ChatCompletionRequest, ImageGenerationRequest, ModelListResponse,
    ErrorResponse
)
from .schemas import (
    APIKeyCreateRequest, APIKeyCreateResponse, APIKeyValidationResponse,
    HealthCheckResponse
)
from .exceptions import APIError
from .providers import (
    resolve_provider_and_model, resolve_tti_provider_and_model,
    get_provider_instance, get_tti_provider_instance
)
from .request_processing import (
    process_messages, prepare_provider_params,
    handle_streaming_response, handle_non_streaming_response
)
from .auth_system import get_auth_components
from .simple_logger import request_logger
from ..search import DuckDuckGoSearch, YepSearch
from ..DWEBS import GoogleSearch
from webscout.Bing_search import BingSearch

# Setup logger
logger = Logger(
    name="webscout.api",
    level=LogLevel.INFO,
    handlers=[ConsoleHandler(stream=sys.stdout)],
    fmt=LogFormat.DEFAULT
)


class Api:
    """API route handler class."""
    
    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self.get_api_key = APIKeyHeader(name="authorization", auto_error=False)

    def register_authorization(self):
        """Register legacy authorization middleware."""
        @self.app.middleware("http")
        async def authorization(request: Request, call_next):
            if AppConfig.api_key is not None:
                auth_header = await self.get_api_key(request)
                path = request.url.path
                if path.startswith("/v1"):  # Only protect /v1 routes
                    if auth_header is None:
                        return JSONResponse(
                            status_code=HTTP_401_UNAUTHORIZED,
                            content={"error": {"message": "API key required", "type": "authentication_error"}}
                        )
                    if auth_header.startswith("Bearer "):
                        auth_header = auth_header[7:]
                    if not secrets.compare_digest(AppConfig.api_key, auth_header):
                        return JSONResponse(
                            status_code=HTTP_403_FORBIDDEN,
                            content={"error": {"message": "Invalid API key", "type": "authentication_error"}}
                        )
            return await call_next(request)

    def register_validation_exception_handler(self):
        """Register comprehensive exception handlers."""
        from fastapi.exceptions import RequestValidationError
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
        from .exceptions import APIError
        
        github_footer = "If you believe this is a bug, please pull an issue at https://github.com/OEvortex/Webscout."

        @self.app.exception_handler(APIError)
        async def api_error_handler(request, exc: APIError):
            logger.error(f"API Error: {exc.message} (Status: {exc.status_code})")
            # Patch: add footer to error content before creating JSONResponse
            error_response = exc.to_response()
            # If the response is a JSONResponse, patch its content dict before returning
            if hasattr(error_response, 'body') and hasattr(error_response, 'media_type'):
                # Try to decode the body to dict and add footer if possible
                try:
                    import json
                    content_dict = json.loads(error_response.body.decode())
                    if "error" in content_dict:
                        content_dict["error"]["footer"] = github_footer
                        return JSONResponse(status_code=error_response.status_code, content=content_dict)
                except Exception:
                    pass
            return error_response

        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request, exc: RequestValidationError):
            errors = exc.errors()
            error_messages = []
            body = await request.body()
            is_empty_body = not body or body.strip() in (b"", b"null", b"{}")
            for error in errors:
                loc = error.get("loc", [])
                loc_str = " -> ".join(str(item) for item in loc)
                msg = error.get("msg", "Validation error")
                error_messages.append({
                    "loc": loc,
                    "message": f"{msg} at {loc_str}",
                    "type": error.get("type", "validation_error")
                })
            content = {
                "error": {
                    "message": "Request validation error.",
                    "details": error_messages,
                    "type": "validation_error",
                    "footer": github_footer
                }
            }
            return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=content)

        @self.app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc: StarletteHTTPException):
            content = {
                "error": {
                    "message": exc.detail or "HTTP error occurred.",
                    "type": "http_error",
                    "footer": github_footer
                }
            }
            return JSONResponse(status_code=exc.status_code, content=content)

        @self.app.exception_handler(Exception)
        async def general_exception_handler(request, exc: Exception):
            logger.error(f"Unhandled server error: {exc}")
            content = {
                "error": {
                    "message": f"Internal server error: {str(exc)}",
                    "type": "server_error",
                    "footer": github_footer
                }
            }
            return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content=content)

    def register_routes(self):
        """Register all API routes."""
        self._register_model_routes()
        self._register_chat_routes()
        self._register_auth_routes()
        self._register_websearch_routes()
        self._register_monitoring_routes()

    def _register_model_routes(self):
        """Register model listing routes."""        
        @self.app.get(
            "/v1/models",
            response_model=ModelListResponse,
            tags=["Chat Completions"],
            description="List all available chat completion models."
        )
        async def list_models():
            models = []
            for model_name, provider_class in AppConfig.provider_map.items():
                if "/" not in model_name:
                    continue  # Skip provider names
                if any(m["id"] == model_name for m in models):
                    continue
                models.append({
                    "id": model_name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": 'webscout'  # Set owned_by to webscout
                })
            # Sort models alphabetically by the part after the first '/'
            models = sorted(models, key=lambda m: m["id"].split("/", 1)[1].lower())
            return {
                "object": "list",
                "data": models
            }        
        @self.app.get(
            "/v1/TTI/models",
            response_model=ModelListResponse,
            tags=["Image Generation"],
            description="List all available text-to-image (TTI) models."
        )
        async def list_tti_models():
            models = []
            for model_name, provider_class in AppConfig.tti_provider_map.items():
                if "/" not in model_name:
                    continue  # Skip provider names
                if any(m["id"] == model_name for m in models):
                    continue
                models.append({
                    "id": model_name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": 'webscout'  # Set owned_by to webscout
                })
            # Sort models alphabetically by the part after the first '/'
            models = sorted(models, key=lambda m: m["id"].split("/", 1)[1].lower())
            return {
                "object": "list",
                "data": models
            }

    def _register_chat_routes(self):
        """Register chat completion routes."""
        @self.app.post(
            "/v1/chat/completions",
            response_model_exclude_none=True,
            response_model_exclude_unset=True,
            tags=["Chat Completions"],
            description="Generate chat completions using the specified model.",
            openapi_extra={
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ChatCompletionRequest"
                            },
                            "example": ChatCompletionRequest.Config.schema_extra["example"]
                        }
                    }
                }
            }
        )
        async def chat_completions(
            request: Request,
            chat_request: ChatCompletionRequest = Body(...)
        ):
            """Handle chat completion requests with comprehensive error handling."""
            start_time = time.time()
            request_id = f"chatcmpl-{uuid.uuid4()}"

            try:
                logger.info(f"Processing chat completion request {request_id} for model: {chat_request.model}")

                # Resolve provider and model
                provider_class, model_name = resolve_provider_and_model(chat_request.model)

                # Initialize provider with caching and error handling
                try:
                    provider = get_provider_instance(provider_class)
                    logger.debug(f"Using provider instance: {provider_class.__name__}")
                except Exception as e:
                    logger.error(f"Failed to initialize provider {provider_class.__name__}: {e}")
                    raise APIError(
                        f"Failed to initialize provider {provider_class.__name__}: {e}",
                        HTTP_500_INTERNAL_SERVER_ERROR,
                        "provider_error"
                    )

                # Process and validate messages
                processed_messages = process_messages(chat_request.messages)

                # Prepare parameters for provider
                params = prepare_provider_params(chat_request, model_name, processed_messages)

                # Extract client IP address
                client_ip = request.client.host if request.client else "unknown"
                if "x-forwarded-for" in request.headers:
                    client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
                elif "x-real-ip" in request.headers:
                    client_ip = request.headers["x-real-ip"]

                # Extract question from messages (last user message)
                question = ""
                for msg in reversed(processed_messages):
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            question = content
                        elif isinstance(content, list) and content:
                            # Handle content with multiple parts (text, images, etc.)
                            for part in content:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    question = part.get("text", "")
                                    break
                        break

                # Handle streaming vs non-streaming
                if chat_request.stream:
                    return await handle_streaming_response(
                        provider, params, request_id, client_ip, question, model_name, start_time,
                        provider_class.__name__, request
                    )
                else:
                    return await handle_non_streaming_response(
                        provider, params, request_id, start_time, client_ip, question, model_name,
                        provider_class.__name__, request
                    )

            except APIError:
                # Re-raise API errors as-is
                raise
            except Exception as e:
                logger.error(f"Unexpected error in chat completion {request_id}: {e}")
                raise APIError(
                    f"Internal server error: {str(e)}",
                    HTTP_500_INTERNAL_SERVER_ERROR,
                    "internal_error"
                )


        @self.app.post(
            "/v1/images/generations",
            tags=["Image Generation"],
            description="Generate images from text prompts using the specified TTI model."
        )
        async def image_generations(
            image_request: ImageGenerationRequest = Body(...)
        ):
            """Handle image generation requests."""
            start_time = time.time()
            request_id = f"img-{uuid.uuid4()}"

            try:
                logger.info(f"Processing image generation request {request_id} for model: {image_request.model}")

                # Resolve TTI provider and model
                provider_class, model_name = resolve_tti_provider_and_model(image_request.model)

                # Initialize TTI provider
                try:
                    provider = get_tti_provider_instance(provider_class)
                    logger.debug(f"Using TTI provider instance: {provider_class.__name__}")
                except APIError as e:
                    # Add helpful footer for provider errors
                    return JSONResponse(
                        status_code=e.status_code,
                        content={
                            "error": {
                                "message": e.message,
                                "type": e.error_type,
                                "footer": "If you believe this is a bug, please pull an issue at https://github.com/OEvortex/Webscout."
                            }
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize TTI provider {provider_class.__name__}: {e}")
                    raise APIError(
                        f"Failed to initialize TTI provider {provider_class.__name__}: {e}",
                        HTTP_500_INTERNAL_SERVER_ERROR,
                        "provider_error"
                    )

                # Prepare parameters for TTI provider
                params = {
                    "prompt": image_request.prompt,
                    "model": model_name,
                    "n": image_request.n,
                    "size": image_request.size,
                    "response_format": image_request.response_format,
                }

                # Add optional parameters
                optional_params = ["user", "style", "aspect_ratio", "timeout", "image_format", "seed"]
                for param in optional_params:
                    value = getattr(image_request, param, None)
                    if value is not None:
                        params[param] = value

                # Generate images
                response = provider.images.create(**params)

                # Standardize response format
                if hasattr(response, "model_dump"):
                    response_data = response.model_dump(exclude_none=True)
                elif hasattr(response, "dict"):
                    response_data = response.dict(exclude_none=True)
                elif isinstance(response, dict):
                    response_data = response
                else:
                    raise APIError(
                        "Invalid response format from TTI provider",
                        HTTP_500_INTERNAL_SERVER_ERROR,
                        "provider_error"
                    )

                elapsed = time.time() - start_time
                logger.info(f"Completed image generation request {request_id} in {elapsed:.2f}s")

                return response_data
            except APIError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in image generation {request_id}: {e}")
                raise APIError(
                    f"Internal server error: {str(e)}",
                    HTTP_500_INTERNAL_SERVER_ERROR,
                    "internal_error"
                )

    def _register_auth_routes(self):
        """Register authentication routes."""
        # Only register auth endpoints if authentication is required
        if not AppConfig.auth_required:
            logger.info("Auth endpoints are disabled (no-auth mode)")
            return
        auth_components = get_auth_components()
        api_key_manager = auth_components.get("api_key_manager")

        @self.app.post(
            "/v1/auth/generate-key",
            response_model=APIKeyCreateResponse,
            tags=["Authentication"],
            description="Generate a new API key for a user."
        )
        async def generate_api_key(request: APIKeyCreateRequest = Body(...)):
            """Generate a new API key."""
            if not api_key_manager:
                raise APIError("Authentication system not initialized", HTTP_500_INTERNAL_SERVER_ERROR)

            try:
                api_key, user = await api_key_manager.create_api_key(
                    username=request.username,
                    telegram_id=request.telegram_id,
                    name=request.name,
                    rate_limit=request.rate_limit or 10,
                    expires_in_days=request.expires_in_days
                )

                return APIKeyCreateResponse(
                    api_key=api_key.key,
                    key_id=api_key.id,
                    user_id=user.id,
                    name=api_key.name,
                    created_at=api_key.created_at,
                    expires_at=api_key.expires_at,
                    rate_limit=api_key.rate_limit
                )
            except Exception as e:
                logger.error(f"Error generating API key: {e}")
                raise APIError(f"Failed to generate API key: {str(e)}", HTTP_500_INTERNAL_SERVER_ERROR)

        @self.app.get(
            "/v1/auth/validate",
            response_model=APIKeyValidationResponse,
            tags=["Authentication"],
            description="Validate an API key and return its status."
        )
        async def validate_api_key(request: Request):
            """Validate an API key."""
            if not api_key_manager:
                raise APIError("Authentication system not initialized", HTTP_500_INTERNAL_SERVER_ERROR)

            auth_header = request.headers.get("authorization")
            if not auth_header:
                return APIKeyValidationResponse(valid=False, error="No authorization header provided")

            # Extract API key
            api_key = auth_header
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

            try:
                is_valid, api_key_obj, error_msg = await api_key_manager.validate_api_key(api_key)

                if is_valid and api_key_obj:
                    return APIKeyValidationResponse(
                        valid=True,
                        user_id=api_key_obj.user_id,
                        key_id=api_key_obj.id,
                        rate_limit=api_key_obj.rate_limit,
                        usage_count=api_key_obj.usage_count,
                        last_used_at=api_key_obj.last_used_at
                    )
                else:
                    return APIKeyValidationResponse(valid=False, error=error_msg)
            except Exception as e:
                logger.error(f"Error validating API key: {e}")
                return APIKeyValidationResponse(valid=False, error="Internal validation error")

        @self.app.get(
            "/health",
            response_model=HealthCheckResponse,
            tags=["Health"],
            description="Health check endpoint for the API and database."
        )
        async def health_check():
            """Health check endpoint."""
            db_status = "unknown"
            db_manager = auth_components.get("db_manager")
            if db_manager:
                status_info = db_manager.get_status()
                db_status = f"{status_info['type']} - {status_info['status']}"

            return HealthCheckResponse(
                status="healthy",
                database=db_status,
                timestamp=datetime.now(timezone.utc)
            )

    def _register_websearch_routes(self):
        """Register web search endpoint."""

        @self.app.get(
            "/search",
            tags=["Web search"],
            description="Unified web search endpoint supporting Google, Yep, DuckDuckGo, and Bing with text, news, images, and suggestions search types."
        )
        async def websearch(
            q: str = Query(..., description="Search query"),
            engine: str = Query("google", description="Search engine: google, yep, duckduckgo, bing"),
            max_results: int = Query(10, description="Maximum number of results"),
            region: str = Query("all", description="Region code (optional)"),
            safesearch: str = Query("moderate", description="Safe search: on, moderate, off"),
            type: str = Query("text", description="Search type: text, news, images, suggestions"),
        ):
            """Unified web search endpoint."""
            github_footer = "If you believe this is a bug, please pull an issue at https://github.com/OEvortex/Webscout."
            try:
                if engine == "google":
                    gs = GoogleSearch()
                    if type == "text":
                        results = gs.text(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "google", "type": "text", "results": [r.__dict__ for r in results]}
                    elif type == "news":
                        results = gs.news(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "google", "type": "news", "results": [r.__dict__ for r in results]}
                    elif type == "suggestions":
                        results = gs.suggestions(q, region=region)
                        return {"engine": "google", "type": "suggestions", "results": results}
                    else:
                        return {"error": "Google only supports text, news, and suggestions in this API.", "footer": github_footer}
                elif engine == "yep":
                    ys = YepSearch()
                    if type == "text":
                        results = ys.text(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "yep", "type": "text", "results": results}
                    elif type == "images":
                        results = ys.images(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "yep", "type": "images", "results": results}
                    elif type == "suggestions":
                        results = ys.suggestions(q, region=region)
                        return {"engine": "yep", "type": "suggestions", "results": results}
                    else:
                        return {"error": "Yep only supports text, images, and suggestions in this API.", "footer": github_footer}
                elif engine == "duckduckgo":
                    ws = WEBS()
                    if type == "text":
                        results = ws.text(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "duckduckgo", "type": "text", "results": results}
                    elif type == "suggestions":
                        results = ws.suggestions(keywords=q, region=region)
                        return {"engine": "duckduckgo", "type": "suggestions", "results": results}
                    else:
                        return {"error": "DuckDuckGo only supports text and suggestions in this API.", "footer": github_footer}
                elif engine == "bing":
                    bs = BingSearch()
                    if type == "text":
                        results = bs.text(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "bing", "type": "text", "results": [r.__dict__ for r in results]}
                    elif type == "news":
                        results = bs.news(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "bing", "type": "news", "results": [r.__dict__ for r in results]}
                    elif type == "images":
                        results = bs.images(keywords=q, region=region, safesearch=safesearch, max_results=max_results)
                        return {"engine": "bing", "type": "images", "results": [r.__dict__ for r in results]}
                    elif type == "suggestions":
                        results = bs.suggestions(q, region=region)
                        return {"engine": "bing", "type": "suggestions", "results": results}
                    else:
                        return {"error": "Bing only supports text, news, images, and suggestions in this API.", "footer": github_footer}
                else:
                    return {"error": "Unknown engine. Use one of: google, yep, duckduckgo, bing.", "footer": github_footer}
            except Exception as e:
                # Special handling for rate limit errors
                msg = str(e)
                if "429" in msg or "rate limit" in msg.lower():
                    return {
                        "error": "You have hit the search rate limit. Please try again later.",
                        "details": msg,
                        "code": 429,
                        "footer": github_footer
                    }
                return {
                    "error": f"Search request failed: {msg}",
                    "footer": github_footer
                }

    def _register_monitoring_routes(self):
        """Register monitoring and analytics routes for no-auth mode."""

        @self.app.get(
            "/monitor/requests",
            tags=["Monitoring"],
            description="Get recent API requests (no-auth mode only)"
        )
        async def get_recent_requests(limit: int = Query(10, description="Number of recent requests to fetch")):
            """Get recent API requests for monitoring."""
            if AppConfig.auth_required:
                return {"error": "Monitoring is only available in no-auth mode"}
            
            try:
                return await request_logger.get_recent_requests(limit)
            except Exception as e:
                return {"error": f"Failed to fetch requests: {str(e)}"}

        @self.app.get(
            "/monitor/stats",
            tags=["Monitoring"], 
            description="Get API usage statistics (no-auth mode only)"
        )
        async def get_api_stats():
            """Get API usage statistics."""
            if AppConfig.auth_required:
                return {"error": "Monitoring is only available in no-auth mode"}
            
            try:
                return await request_logger.get_stats()
            except Exception as e:
                return {"error": f"Failed to fetch stats: {str(e)}"}

        @self.app.get(
            "/monitor/health",
            tags=["Monitoring"],
            description="Health check with database status"
        )
        async def enhanced_health_check():
            """Enhanced health check including database connectivity."""
            try:
                # Check database connectivity
                db_status = "disconnected"
                if request_logger.supabase_client:
                    try:
                        # Try a simple query to check connectivity
                        result = request_logger.supabase_client.table("api_requests").select("id").limit(1).execute()
                        db_status = "connected"
                    except Exception as e:
                        db_status = f"error: {str(e)[:100]}"
                
                return {
                    "status": "healthy",
                    "database": db_status,
                    "auth_required": AppConfig.auth_required,
                    "rate_limit_enabled": AppConfig.rate_limit_enabled,
                    "request_logging_enabled": AppConfig.request_logging_enabled,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
