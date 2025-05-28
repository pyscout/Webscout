"""
Webscout OpenAI-Compatible API Server

A FastAPI-based server that provides OpenAI-compatible endpoints for various LLM providers.
Supports streaming and non-streaming chat completions with comprehensive error handling,
authentication, and provider management.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
import time
import uuid
import inspect
import re
import codecs
from typing import List, Dict, Optional, Union, Any, Generator, Callable
import types

import uvicorn
from fastapi import FastAPI, Response, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException as StarletteHTTPException

def clean_text(text):
    """Clean text by removing null bytes and control characters except newlines and tabs."""
    if not isinstance(text, str):
        return text
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Keep newlines, tabs, and other printable characters, remove other control chars
    # This regex matches control characters except \n, \r, \t
    return re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
from starlette.status import (
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_404_NOT_FOUND,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from webscout.Provider.OPENAI.pydantic_imports import BaseModel, Field
from typing import Literal

# Import provider classes from the OPENAI directory
from webscout.Provider.OPENAI import *
from webscout.Provider.OPENAI.utils import (
    ChatCompletion, Choice, ChatCompletionMessage, CompletionUsage
)


# Configuration constants
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"
API_VERSION = "v1"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("webscout.api")


class ServerConfig:
    """Centralized configuration management for the API server."""

    def __init__(self):
        self.api_key: Optional[str] = None
        self.provider_map: Dict[str, Any] = {}
        self.default_provider: str = "ChatGPT"
        self.base_url: Optional[str] = None
        self.host: str = DEFAULT_HOST
        self.port: int = DEFAULT_PORT
        self.debug: bool = False
        self.cors_origins: List[str] = ["*"]
        self.max_request_size: int = 10 * 1024 * 1024  # 10MB
        self.request_timeout: int = 300  # 5 minutes

    def update(self, **kwargs) -> None:
        """Update configuration with provided values."""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
                logger.info(f"Config updated: {key} = {value}")

    def validate(self) -> None:
        """Validate configuration settings."""
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")

        if self.default_provider not in self.provider_map and self.provider_map:
            available_providers = list(set(v.__name__ for v in self.provider_map.values()))
            logger.warning(f"Default provider '{self.default_provider}' not found. Available: {available_providers}")


# Global configuration instance
config = ServerConfig()


# Define Pydantic models for multimodal content parts, aligning with OpenAI's API
class TextPart(BaseModel):
    """Text content part for multimodal messages."""
    type: Literal["text"]
    text: str


class ImageURL(BaseModel):
    """Image URL configuration for multimodal messages."""
    url: str  # Can be http(s) or data URI
    detail: Optional[Literal["auto", "low", "high"]] = Field(
        "auto",
        description="Specifies the detail level of the image."
    )


class ImagePart(BaseModel):
    """Image content part for multimodal messages."""
    type: Literal["image_url"]
    image_url: ImageURL


MessageContentParts = Union[TextPart, ImagePart]


class Message(BaseModel):
    """Chat message model compatible with OpenAI API."""
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: Optional[Union[str, List[MessageContentParts]]] = Field(
        None,
        description="The content of the message. Can be a string, a list of content parts (for multimodal), or null."
    )
    name: Optional[str] = None
    # Future: Add tool_calls and tool_call_id for function calling support
    # tool_calls: Optional[List[ToolCall]] = None
    # tool_call_id: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="ID of the model to use. See the model endpoint for the available models.")
    messages: List[Message] = Field(..., description="A list of messages comprising the conversation so far.")
    temperature: Optional[float] = Field(None, description="What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic.")
    top_p: Optional[float] = Field(None, description="An alternative to sampling with temperature, called nucleus sampling, where the model considers the results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability mass are considered.")
    n: Optional[int] = Field(1, description="How many chat completion choices to generate for each input message.")
    stream: Optional[bool] = Field(False, description="If set, partial message deltas will be sent, like in ChatGPT. Tokens will be sent as data-only server-sent events as they become available, with the stream terminated by a data: [DONE] message.")
    max_tokens: Optional[int] = Field(None, description="The maximum number of tokens to generate in the chat completion.")
    presence_penalty: Optional[float] = Field(None, description="Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far, increasing the model's likelihood to talk about new topics.")
    frequency_penalty: Optional[float] = Field(None, description="Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.")
    logit_bias: Optional[Dict[str, float]] = Field(None, description="Modify the likelihood of specified tokens appearing in the completion.")
    user: Optional[str] = Field(None, description="A unique identifier representing your end-user, which can help the API to monitor and detect abuse.")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Up to 4 sequences where the API will stop generating further tokens.")

    class Config:
        extra = "ignore"  # Ignore extra fields that aren't in the model
        schema_extra = {
            "example": {
                "model": "ChatGPT/gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello, how are you?"}
                ],
                "temperature": 0.7,
                "max_tokens": 150,
                "stream": False
            }
        }

class ModelInfo(BaseModel):
    """Model information for the models endpoint."""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelListResponse(BaseModel):
    """Response model for the models list endpoint."""
    object: str = "list"
    data: List[ModelInfo]


class ErrorDetail(BaseModel):
    """Error detail structure compatible with OpenAI API."""
    message: str
    type: str = "server_error"
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response structure compatible with OpenAI API."""
    error: ErrorDetail


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


class AppConfig:
    """Legacy configuration class for backward compatibility."""
    api_key: Optional[str] = None
    provider_map = {}
    default_provider = "ChatGPT"
    base_url: Optional[str] = None

    @classmethod
    def set_config(cls, **data):
        """Set configuration values."""
        for key, value in data.items():
            setattr(cls, key, value)
        # Sync with new config system
        config.update(**data)

# Custom route class to handle dynamic base URLs
# Note: The /docs 404 issue is likely related to server execution (Werkzeug logs vs. Uvicorn script).
# This DynamicBaseRoute, when AppConfig.base_url is None, should act as a passthrough and not break /docs.
# If AppConfig.base_url is set, this route class has limitations in correctly handling prefixed routes
# without more complex path manipulation or using FastAPI's APIRouter prefixing/mounting features.
class DynamicBaseRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()
        async def custom_route_handler(request: Request) -> Response:
            if AppConfig.base_url:
                if not request.url.path.startswith(AppConfig.base_url):
                    # This logic might need refinement if base_url is used.
                    # For API routes not matching the prefix, a 404 might be appropriate.
                    # Docs routes (/docs, /openapi.json) are usually at the root.
                    # The current 'pass' allows root docs even if base_url is set for APIs.
                    pass
            return await original_route_handler(request)
        return custom_route_handler

def create_app():
    app = FastAPI(
        title="Webscout OpenAI API",
        description="OpenAI API compatible interface for various LLM providers",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.router.route_class = DynamicBaseRoute
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api = Api(app)
    api.register_authorization()
    api.register_validation_exception_handler()
    api.register_routes()
    initialize_provider_map()

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        if "components" not in openapi_schema: openapi_schema["components"] = {}
        if "schemas" not in openapi_schema["components"]: openapi_schema["components"]["schemas"] = {}

        # Use Pydantic's schema generation for accuracy
        # Assuming Pydantic v1 .schema() or v2 .model_json_schema() based on pydantic_imports
        # For broader compatibility, trying .schema() first.
        # If using Pydantic v2 primarily, .model_json_schema() is preferred.
        schema_method_name = "model_json_schema" if hasattr(BaseModel, "model_json_schema") else "schema"

        # Add/update schemas derived from Pydantic models to ensure they are correctly defined
        pydantic_models_to_register = {
            "TextPart": TextPart,
            "ImageURL": ImageURL,
            "ImagePart": ImagePart,
            "Message": Message,
            "ChatCompletionRequest": ChatCompletionRequest,
        }

        for name, model_cls in pydantic_models_to_register.items():
            if schema_method_name == "model_json_schema":
                schema_data = model_cls.model_json_schema(ref_template="#/components/schemas/{model}")
            else:
                schema_data = model_cls.schema()
            # Pydantic might add a "title" to the schema, which is often not desired for component schemas
            if "title" in schema_data:
                del schema_data["title"]
            openapi_schema["components"]["schemas"][name] = schema_data

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
    return app

def create_app_debug():
    return create_app()

def initialize_provider_map() -> None:
    """Initialize the provider map by discovering available providers."""
    logger.info("Initializing provider map...")

    try:
        from webscout.Provider.OPENAI.base import OpenAICompatibleProvider
        module = sys.modules["webscout.Provider.OPENAI"]

        provider_count = 0
        model_count = 0

        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, OpenAICompatibleProvider)
                and obj.__name__ != "OpenAICompatibleProvider"
            ):
                provider_name = obj.__name__
                AppConfig.provider_map[provider_name] = obj
                config.provider_map[provider_name] = obj
                provider_count += 1

                # Register available models for this provider
                if hasattr(obj, "AVAILABLE_MODELS") and isinstance(
                    obj.AVAILABLE_MODELS, (list, tuple, set)
                ):
                    for model in obj.AVAILABLE_MODELS:
                        if model and isinstance(model, str):
                            model_key = f"{provider_name}/{model}"
                            AppConfig.provider_map[model_key] = obj
                            config.provider_map[model_key] = obj
                            model_count += 1

        # Fallback to ChatGPT if no providers found
        if not AppConfig.provider_map:
            logger.warning("No providers found, using ChatGPT fallback")
            try:
                from webscout.Provider.OPENAI.chatgpt import ChatGPT
                fallback_models = ["gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

                AppConfig.provider_map["ChatGPT"] = ChatGPT
                config.provider_map["ChatGPT"] = ChatGPT

                for model in fallback_models:
                    model_key = f"ChatGPT/{model}"
                    AppConfig.provider_map[model_key] = ChatGPT
                    config.provider_map[model_key] = ChatGPT

                AppConfig.default_provider = "ChatGPT"
                config.default_provider = "ChatGPT"
                provider_count = 1
                model_count = len(fallback_models)
            except ImportError as e:
                logger.error(f"Failed to import ChatGPT fallback: {e}")
                raise APIError("No providers available", HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(f"Initialized {provider_count} providers with {model_count} models")

    except Exception as e:
        logger.error(f"Failed to initialize provider map: {e}")
        raise APIError(f"Provider initialization failed: {e}", HTTP_500_INTERNAL_SERVER_ERROR)

class Api:
    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self.get_api_key = APIKeyHeader(name="authorization", auto_error=False)

    def register_authorization(self):
        @self.app.middleware("http")
        async def authorization(request: Request, call_next):
            if AppConfig.api_key is not None:
                auth_header = await self.get_api_key(request)
                path = request.url.path
                if path.startswith("/v1"): # Only protect /v1 routes
                    # Also allow access to /docs, /openapi.json etc. if AppConfig.base_url is not set or path is not under it
                    # This logic should be fine as it only protects /v1 paths
                    if auth_header is None:
                        return ErrorResponse.from_message("API key required", HTTP_401_UNAUTHORIZED)
                    if auth_header.startswith("Bearer "):
                        auth_header = auth_header[7:]
                    if AppConfig.api_key is None or not secrets.compare_digest(AppConfig.api_key, auth_header): # AppConfig.api_key check is redundant after outer if
                        return ErrorResponse.from_message("Invalid API key", HTTP_403_FORBIDDEN)
            return await call_next(request)

    def register_validation_exception_handler(self):
        """Register comprehensive exception handlers."""

        @self.app.exception_handler(APIError)
        async def api_error_handler(request: Request, exc: APIError):
            """Handle custom API errors."""
            logger.error(f"API Error: {exc.message} (Status: {exc.status_code})")
            return exc.to_response()

        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            errors = exc.errors()
            error_messages = []
            body = await request.body()
            is_empty_body = not body or body.strip() in (b"", b"null", b"{}")
            for error in errors:
                loc = error.get("loc", [])
                # Ensure loc_str is user-friendly
                loc_str_parts = []
                for item in loc:
                    if item == "body": # Skip "body" part if it's the first element of a longer path
                        if len(loc) > 1: continue
                    loc_str_parts.append(str(item))
                loc_str = " -> ".join(loc_str_parts)

                msg = error.get("msg", "Validation error")

                # Check if this error is for the 'content' field specifically due to multimodal input
                if len(loc) >=3 and loc[0] == 'body' and loc[1] == 'messages' and loc[-1] == 'content':
                     # Check if the error type suggests a string was expected but a list (or vice-versa) was given for content
                    if "Input should be a valid string" in msg and error.get("input_type") == "list":
                         error_messages.append({
                            "loc": loc,
                            "message": f"Invalid message content: {msg}. Ensure content matches the expected format (string or list of content parts). Path: {loc_str}",
                            "type": error.get("type", "validation_error")
                        })
                         continue # Skip default message formatting for this specific case
                    elif "Input should be a valid list" in msg and error.get("input_type") == "string":
                         error_messages.append({
                            "loc": loc,
                            "message": f"Invalid message content: {msg}. Ensure content matches the expected format (string or list of content parts). Path: {loc_str}",
                            "type": error.get("type", "validation_error")
                        })
                         continue

                if "body" in loc:
                    if len(loc) > 1 and loc[1] == "messages":
                        error_messages.append({
                            "loc": loc,
                            "message": "The 'messages' field is required and must be a non-empty array of message objects. " + f"Error: {msg} at {loc_str}",
                            "type": error.get("type", "validation_error")
                        })
                    elif len(loc) > 1 and loc[1] == "model":
                        error_messages.append({
                            "loc": loc,
                            "message": "The 'model' field is required and must be a string. " + f"Error: {msg} at {loc_str}",
                            "type": error.get("type", "validation_error")
                        })
                    else:
                        error_messages.append({
                            "loc": loc,
                            "message": f"{msg} at {loc_str}",
                            "type": error.get("type", "validation_error")
                        })
                else:
                    error_messages.append({
                        "loc": loc,
                        "message": f"{msg} at {loc_str}",
                        "type": error.get("type", "validation_error")
                    })
            if request.url.path == "/v1/chat/completions":
                example = ChatCompletionRequest.Config.schema_extra["example"]
                if is_empty_body:
                    return JSONResponse(
                        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                        content={
                            "error": {
                                "message": "Request body is required and must include 'model' and 'messages'.",
                                "type": "invalid_request_error",
                                "param": None,
                                "code": "body_missing"
                            },
                            "example": example
                        }
                    )
                return JSONResponse(
                    status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": error_messages, "example": example}
                )
            return JSONResponse(
                status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": error_messages}
            )
        @self.app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request: Request, exc: StarletteHTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail}
            )
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            return JSONResponse(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": f"Internal server error: {str(exc)}"}
            )

    def register_routes(self):
        @self.app.get("/", include_in_schema=False)
        async def root():
            # Note: If /docs is 404ing, check if server is Uvicorn (expected) or Werkzeug (from logs).
            # Werkzeug logs suggest possible execution of a Flask app or WSGI misconfiguration.
            # This api.py file is intended for Uvicorn.
            return RedirectResponse(url="/docs")

        @self.app.get("/v1/models", response_model=ModelListResponse)
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
                    "owned_by": provider_class.__name__
                })
            return {
                "object": "list",
                "data": models
            }

        @self.app.post(
            "/v1/chat/completions",
            response_model_exclude_none=True,
            response_model_exclude_unset=True,
            openapi_extra={ # This ensures the example is shown in docs
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ChatCompletionRequest" # Relies on custom_openapi
                            },
                            "example": ChatCompletionRequest.Config.schema_extra["example"]
                        }
                    }
                }
            }
        )
        async def chat_completions(
            chat_request: ChatCompletionRequest = Body(...)
        ):
            """Handle chat completion requests with comprehensive error handling."""
            start_time = time.time()
            request_id = f"chatcmpl-{uuid.uuid4()}"

            try:
                logger.info(f"Processing chat completion request {request_id} for model: {chat_request.model}")

                # Resolve provider and model
                provider_class, model_name = resolve_provider_and_model(chat_request.model)

                # Initialize provider with error handling
                try:
                    provider = provider_class()
                    logger.debug(f"Initialized provider: {provider_class.__name__}")
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

                # Handle streaming vs non-streaming
                if chat_request.stream:
                    return await handle_streaming_response(provider, params, request_id)
                else:
                    return await handle_non_streaming_response(provider, params, request_id, start_time)

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


def resolve_provider_and_model(model_identifier: str) -> tuple[Any, str]:
    """Resolve provider class and model name from model identifier."""
    provider_class = None
    model_name = None

    # Check for explicit provider/model syntax
    if model_identifier in AppConfig.provider_map and "/" in model_identifier:
        provider_class = AppConfig.provider_map[model_identifier]
        _, model_name = model_identifier.split("/", 1)
    elif "/" in model_identifier:
        provider_name, model_name = model_identifier.split("/", 1)
        provider_class = AppConfig.provider_map.get(provider_name)
    else:
        provider_class = AppConfig.provider_map.get(AppConfig.default_provider)
        model_name = model_identifier

    if not provider_class:
        available_providers = list(set(v.__name__ for v in AppConfig.provider_map.values()))
        raise APIError(
            f"Provider for model '{model_identifier}' not found. Available providers: {available_providers}",
            HTTP_404_NOT_FOUND,
            "model_not_found",
            param="model"
        )

    # Validate model availability
    if hasattr(provider_class, "AVAILABLE_MODELS") and model_name is not None:
        available = getattr(provider_class, "AVAILABLE_MODELS", [])
        if available and model_name not in available:
            raise APIError(
                f"Model '{model_name}' not supported by provider '{provider_class.__name__}'. Available models: {available}",
                HTTP_404_NOT_FOUND,
                "model_not_found",
                param="model"
            )

    return provider_class, model_name


def process_messages(messages: List[Message]) -> List[Dict[str, Any]]:
    """Process and validate chat messages."""
    processed_messages = []

    for i, msg_in in enumerate(messages):
        try:
            message_dict_out = {"role": msg_in.role}

            if msg_in.content is None:
                message_dict_out["content"] = None
            elif isinstance(msg_in.content, str):
                message_dict_out["content"] = msg_in.content
            else:  # List[MessageContentParts]
                message_dict_out["content"] = [
                    part.model_dump(exclude_none=True) for part in msg_in.content
                ]

            if msg_in.name:
                message_dict_out["name"] = msg_in.name

            processed_messages.append(message_dict_out)

        except Exception as e:
            raise APIError(
                f"Invalid message at index {i}: {str(e)}",
                HTTP_422_UNPROCESSABLE_ENTITY,
                "invalid_request_error",
                param=f"messages[{i}]"
            )

    return processed_messages


def prepare_provider_params(chat_request: ChatCompletionRequest, model_name: str,
                          processed_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepare parameters for the provider."""
    params = {
        "model": model_name,
        "messages": processed_messages,
        "stream": chat_request.stream,
    }

    # Add optional parameters if present
    optional_params = [
        "temperature", "max_tokens", "top_p", "presence_penalty",
        "frequency_penalty", "stop", "user"
    ]

    for param in optional_params:
        value = getattr(chat_request, param, None)
        if value is not None:
            params[param] = value

    return params


async def handle_streaming_response(provider: Any, params: Dict[str, Any], request_id: str) -> StreamingResponse:
    """Handle streaming chat completion response."""
    async def streaming():
        try:
            logger.debug(f"Starting streaming response for request {request_id}")
            completion_stream = provider.chat.completions.create(**params)

            # Check if it's iterable (generator, iterator, or other iterable types)
            if hasattr(completion_stream, '__iter__') and not isinstance(completion_stream, (str, bytes, dict)):
                try:
                    for chunk in completion_stream:
                        # Check if the chunk indicates a provider-side error (as per BLACKBOXAI.py update)
                        # Assumes chunk is a ChatCompletionChunk object
                        if hasattr(chunk, 'choices') and chunk.choices and \
                           hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason == "error":
                            
                            error_message = "Unknown streaming error from provider."
                            if hasattr(chunk.choices[0], 'delta') and \
                               chunk.choices[0].delta and \
                               hasattr(chunk.choices[0].delta, 'content') and \
                               chunk.choices[0].delta.content:
                                error_message = chunk.choices[0].delta.content
                            
                            error_message = clean_text(error_message) # Ensure error message is clean
                            
                            logger.error(f"Provider error received in stream for request {request_id}: {error_message}")
                            error_data = {
                                "error": {
                                    "message": error_message,
                                    "type": "provider_error", 
                                    "code": "streaming_provider_error"
                                }
                            }
                            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                            return # Stop further processing for this stream; [DONE] will be sent by finally

                        # Standardize chunk format before sending if not an error chunk
                        if hasattr(chunk, 'model_dump'):  # Pydantic v2
                            chunk_data = chunk.model_dump(exclude_none=True)
                        elif hasattr(chunk, 'dict'):  # Pydantic v1
                            chunk_data = chunk.dict(exclude_none=True)
                        elif isinstance(chunk, dict):
                            chunk_data = chunk
                        else:  # Fallback for unknown chunk types
                            chunk_data = chunk
                        
                        # Clean text content in the chunk to remove control characters
                        # This part remains, as it can also handle non-error chunks from other providers
                        # or if BLACKBOXAI.py's error chunk somehow bypasses the check above.
                        if isinstance(chunk_data, dict) and 'choices' in chunk_data:
                            for choice_item in chunk_data.get('choices', []): # Renamed 'choice' to 'choice_item' to avoid conflict
                                if isinstance(choice_item, dict):
                                    # Handle delta for streaming
                                    if 'delta' in choice_item and isinstance(choice_item['delta'], dict) and 'content' in choice_item['delta']:
                                        choice_item['delta']['content'] = clean_text(choice_item['delta']['content'])
                                    # Handle message for non-streaming (less relevant here but good for consistency)
                                    elif 'message' in choice_item and isinstance(choice_item['message'], dict) and 'content' in choice_item['message']:
                                        choice_item['message']['content'] = clean_text(choice_item['message']['content'])
                        
                        yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                except TypeError as te:
                    logger.error(f"Error iterating over completion_stream: {te}. Request ID: {request_id}")
                    # Fall back to treating as non-generator response
                    # This block handles the case where completion_stream is not an iterator (e.g., a single object)
                    # or if TypeError occurred during iteration.
                    if hasattr(completion_stream, 'model_dump'): # Pydantic v2
                        response_data_fallback = completion_stream.model_dump(exclude_none=True)
                    elif hasattr(completion_stream, 'dict'): # Pydantic v1
                        response_data_fallback = completion_stream.dict(exclude_none=True)
                    else:
                        response_data_fallback = completion_stream # Fallback
                    
                    # Clean text content in the fallback response
                    if isinstance(response_data_fallback, dict) and 'choices' in response_data_fallback:
                        for choice_item_fallback in response_data_fallback.get('choices', []): # Renamed for clarity
                            if isinstance(choice_item_fallback, dict):
                                if 'delta' in choice_item_fallback and isinstance(choice_item_fallback['delta'], dict) and 'content' in choice_item_fallback['delta']:
                                    choice_item_fallback['delta']['content'] = clean_text(choice_item_fallback['delta']['content'])
                                elif 'message' in choice_item_fallback and isinstance(choice_item_fallback['message'], dict) and 'content' in choice_item_fallback['message']:
                                    choice_item_fallback['message']['content'] = clean_text(choice_item_fallback['message']['content'])
                    
                    yield f"data: {json.dumps(response_data_fallback, ensure_ascii=False)}\n\n"

            # This else block handles cases where completion_stream is not directly iterable (e.g., already a single response object)
            # but the initial check `hasattr(completion_stream, '__iter__')` passed.
            # This logic might be redundant if the TypeError above catches most non-iterable scenarios.
            else:  # Non-generator response (or if initial iter check was misleading)
                if hasattr(completion_stream, 'model_dump'):
                    response_data_single = completion_stream.model_dump(exclude_none=True)
                elif hasattr(completion_stream, 'dict'):
                    response_data_single = completion_stream.dict(exclude_none=True)
                else:
                    response_data_single = completion_stream
                
                # Clean text content
                if isinstance(response_data_single, dict) and 'choices' in response_data_single:
                    for choice_item_single in response_data_single.get('choices', []): # Renamed for clarity
                        if isinstance(choice_item_single, dict):
                            if 'delta' in choice_item_single and isinstance(choice_item_single['delta'], dict) and 'content' in choice_item_single['delta']:
                                choice_item_single['delta']['content'] = clean_text(choice_item_single['delta']['content'])
                            elif 'message' in choice_item_single and isinstance(choice_item_single['message'], dict) and 'content' in choice_item_single['message']:
                                choice_item_single['message']['content'] = clean_text(choice_item_single['message']['content'])
                
                yield f"data: {json.dumps(response_data_single, ensure_ascii=False)}\n\n"

        except Exception as e: # Catches errors within api.py's streaming logic
            logger.error(f"Error in API streaming logic for request {request_id}: {e}")
            error_message = clean_text(str(e)) # Ensure error message is clean
            error_data = {
                "error": {
                    "message": error_message,
                    "type": "server_error",
                    "code": "streaming_error"
                }
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    return StreamingResponse(streaming(), media_type="text/event-stream")


async def handle_non_streaming_response(provider: Any, params: Dict[str, Any],
                                      request_id: str, start_time: float) -> Dict[str, Any]:
    """Handle non-streaming chat completion response."""
    try:
        logger.debug(f"Starting non-streaming response for request {request_id}")
        completion = provider.chat.completions.create(**params)

        if completion is None:
            # Return a valid OpenAI-compatible error response
            return ChatCompletion(
                id=request_id,
                created=int(time.time()),
                model=params.get("model", "unknown"),
                choices=[Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content="No response generated."),
                    finish_reason="error"
                )],
                usage=CompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            ).model_dump(exclude_none=True)

        # Standardize response format
        if hasattr(completion, "model_dump"):  # Pydantic v2
            response_data = completion.model_dump(exclude_none=True)
        elif hasattr(completion, "dict"):  # Pydantic v1
            response_data = completion.dict(exclude_none=True)
        elif isinstance(completion, dict):
            response_data = completion
        else:
            raise APIError(
                "Invalid response format from provider",
                HTTP_500_INTERNAL_SERVER_ERROR,
                "provider_error"
            )
        
        # Clean text content in the response to remove control characters
        if isinstance(response_data, dict) and 'choices' in response_data:
            for choice in response_data.get('choices', []):
                if isinstance(choice, dict) and 'message' in choice:
                    if isinstance(choice['message'], dict) and 'content' in choice['message']:
                        choice['message']['content'] = clean_text(choice['message']['content'])

        elapsed = time.time() - start_time
        logger.info(f"Completed non-streaming request {request_id} in {elapsed:.2f}s")

        return response_data

    except Exception as e:
        logger.error(f"Error in non-streaming response for request {request_id}: {e}")
        error_message = clean_text(str(e))
        raise APIError(
            f"Provider error: {error_message}",
            HTTP_500_INTERNAL_SERVER_ERROR,
            "provider_error"
        )

def format_exception(e: Union[Exception, str]) -> str:
    if isinstance(e, str):
        message = e
    else:
        message = f"{e.__class__.__name__}: {str(e)}" # Keep it concise
    return json.dumps({
        "error": {
            "message": message,
            "type": "server_error", # Or more specific if possible
            "param": None,
            "code": "internal_server_error" # Or more specific
        }
    })

def start_server(
    port: int = DEFAULT_PORT,
    host: str = DEFAULT_HOST,
    api_key: str = None,
    default_provider: str = None,
    base_url: str = None,
    workers: int = 1,
    log_level: str = 'info',
    debug: bool = False
):
    """Start the API server with the given configuration."""
    run_api(
        host=host,
        port=port,
        api_key=api_key,
        default_provider=default_provider,
        base_url=base_url,
        workers=workers,
        log_level=log_level,
        debug=debug,
    )

def run_api(
    host: str = '0.0.0.0',
    port: int = None,
    api_key: str = None,
    default_provider: str = None,
    base_url: str = None,
    debug: bool = False,
    workers: int = 1,
    log_level: str = 'info',
    show_available_providers: bool = True,
) -> None:
    print("Starting Webscout OpenAI API server...")
    if port is None:
        port = DEFAULT_PORT
    AppConfig.set_config(
        api_key=api_key,
        default_provider=default_provider or AppConfig.default_provider,
        base_url=base_url
    )
    # initialize_provider_map() # This is called inside create_app now.
                              # Call here if create_app doesn't exist yet or for early info.
                              # For showing providers, it needs to be called before printing.
    if show_available_providers: # Initialize map if needed for display before app creation
        if not AppConfig.provider_map: # Avoid re-initializing if already done by app creation logic path
            initialize_provider_map()

        print("\n=== Webscout OpenAI API Server ===")
        print(f"Server URL: http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        if AppConfig.base_url:
            print(f"Base Path: {AppConfig.base_url}")
            api_endpoint_base = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}{AppConfig.base_url}"
        else:
            api_endpoint_base = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"

        print(f"API Endpoint: {api_endpoint_base}/v1/chat/completions")
        print(f"Docs URL: {api_endpoint_base}/docs") # Adjusted for potential base_url in display
        print(f"API Authentication: {'Enabled' if api_key else 'Disabled'}")
        print(f"Default Provider: {AppConfig.default_provider}")
        print(f"Workers: {workers}")
        print(f"Log Level: {log_level}")
        print(f"Debug Mode: {'Enabled' if debug else 'Disabled'}")

        providers = list(set(v.__name__ for v in AppConfig.provider_map.values()))
        print(f"\n--- Available Providers ({len(providers)}) ---")
        for i, provider_name in enumerate(sorted(providers), 1):
            print(f"{i}. {provider_name}")

        provider_class_names = set(v.__name__ for v in AppConfig.provider_map.values())
        models = sorted([model for model in AppConfig.provider_map.keys() if model not in provider_class_names])
        if models:
            print(f"\n--- Available Models ({len(models)}) ---")
            for i, model_name in enumerate(models, 1):
                print(f"{i}. {model_name} (via {AppConfig.provider_map[model_name].__name__})")
        else:
            print("\nNo specific models registered. Use provider names as models.")

        print("\nUse Ctrl+C to stop the server.")
        print("=" * 40 + "\n")

    uvicorn_app_str = "webscout.Provider.OPENAI.api:create_app_debug" if debug else "webscout.Provider.OPENAI.api:create_app"

    # Configure uvicorn settings
    uvicorn_config = {
        "app": uvicorn_app_str,
        "host": host,
        "port": int(port),
        "factory": True,
        "reload": debug,  # Enable reload only in debug mode for stability
        "log_level": log_level.lower() if log_level else ("debug" if debug else "info"),
    }

    # Add workers only if not in debug mode (reload and workers are incompatible)
    if not debug and workers > 1:
        uvicorn_config["workers"] = workers
        print(f"Starting with {workers} workers...")
    elif debug:
        print("Debug mode enabled - using single worker with reload...")

    # Note: Logs show "werkzeug". If /docs 404s persist, ensure Uvicorn is the actual server running.
    # The script uses uvicorn.run, so "werkzeug" logs are unexpected for this file.
    uvicorn.run(**uvicorn_config)

if __name__ == "__main__":
    import argparse

    # Read environment variables with fallbacks
    default_port = int(os.getenv('WEBSCOUT_PORT', os.getenv('PORT', DEFAULT_PORT)))
    default_host = os.getenv('WEBSCOUT_HOST', DEFAULT_HOST)
    default_workers = int(os.getenv('WEBSCOUT_WORKERS', '1'))
    default_log_level = os.getenv('WEBSCOUT_LOG_LEVEL', 'info')
    default_api_key = os.getenv('WEBSCOUT_API_KEY', os.getenv('API_KEY'))
    default_provider = os.getenv('WEBSCOUT_DEFAULT_PROVIDER', os.getenv('DEFAULT_PROVIDER'))
    default_base_url = os.getenv('WEBSCOUT_BASE_URL', os.getenv('BASE_URL'))
    default_debug = os.getenv('WEBSCOUT_DEBUG', os.getenv('DEBUG', 'false')).lower() == 'true'

    parser = argparse.ArgumentParser(description='Start Webscout OpenAI-compatible API server')
    parser.add_argument('--port', type=int, default=default_port, help=f'Port to run the server on (default: {default_port})')
    parser.add_argument('--host', type=str, default=default_host, help=f'Host to bind the server to (default: {default_host})')
    parser.add_argument('--workers', type=int, default=default_workers, help=f'Number of worker processes (default: {default_workers})')
    parser.add_argument('--log-level', type=str, default=default_log_level, choices=['debug', 'info', 'warning', 'error', 'critical'], help=f'Log level (default: {default_log_level})')
    parser.add_argument('--api-key', type=str, default=default_api_key, help='API key for authentication (optional)')
    parser.add_argument('--default-provider', type=str, default=default_provider, help='Default provider to use (optional)')
    parser.add_argument('--base-url', type=str, default=default_base_url, help='Base URL for the API (optional, e.g., /api/v1)')
    parser.add_argument('--debug', action='store_true', default=default_debug, help='Run in debug mode')
    args = parser.parse_args()

    # Print configuration summary
    print(f"Configuration:")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Workers: {args.workers}")
    print(f"  Log Level: {args.log_level}")
    print(f"  Debug Mode: {args.debug}")
    print(f"  API Key: {'Set' if args.api_key else 'Not set'}")
    print(f"  Default Provider: {args.default_provider or 'Not set'}")
    print(f"  Base URL: {args.base_url or 'Not set'}")
    print()

    run_api(
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level=args.log_level,
        api_key=args.api_key,
        default_provider=args.default_provider,
        base_url=args.base_url,
        debug=args.debug
    )
