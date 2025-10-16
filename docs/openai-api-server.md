# OpenAI-Compatible API Server (`webscout.server`)

Webscout's [`webscout.server`](../webscout/server/__init__.py:1) module provides a comprehensive OpenAI-compatible API server with provider management capabilities. This server allows you to use any supported provider with tools and applications designed for OpenAI's API.

## Table of Contents

1. [Core Components](#core-components)
2. [Server Configuration](#server-configuration)
3. [Provider Management](#provider-management)
4. [API Endpoints](#api-endpoints)
5. [Starting the Server](#starting-the-server)
6. [Usage Examples](#usage-examples)
7. [Environment Variables](#environment-variables)
8. [Error Handling](#error-handling)
9. [Troubleshooting](#troubleshooting)

## Core Components

### [`server.py`](../webscout/server/server.py:1)

The main server module that creates and configures the FastAPI application with OpenAI-compatible endpoints.

```python
from webscout.server.server import create_app, run_api, start_server

# Create FastAPI app
app = create_app()

# Start server programmatically
start_server(port=8000, host="0.0.0.0")
```

**Key Features:**
- OpenAI-compatible API endpoints
- Automatic provider discovery and registration
- Comprehensive error handling and logging
- Interactive API documentation with custom UI

## Server Configuration

### [`ServerConfig`](../webscout/server/config.py:22)

Centralized configuration management for the API server.

```python
from webscout.server.config import ServerConfig

config = ServerConfig()
config.update(
    port=8080,
    host="localhost",
)
```

**Configuration Options:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"0.0.0.0"` | Server host address |
| `port` | `int` | `8000` | Server port number |
| `debug` | `bool` | `False` | Enable debug mode |
| `cors_origins` | `List[str]` | `["*"` | CORS allowed origins |
| `max_request_size` | `int` | `10MB` | Maximum request size |
| `request_timeout` | `int` | `300` | Request timeout in seconds |

## Provider Management

### [`providers.py`](../webscout/server/providers.py:1)

Automatic provider discovery and management system with intelligent model resolution.

```python
from webscout.server.providers import (
    initialize_provider_map,
    resolve_provider_and_model,
    get_provider_instance
)

# Initialize providers
initialize_provider_map()

# Resolve provider and model
provider_class, model_name = resolve_provider_and_model("ChatGPT/gpt-4")

# Get cached provider instance
provider = get_provider_instance(provider_class)
```

**Provider Features:**
- Automatic discovery of OpenAI-compatible providers
- Model validation and availability checking
- Provider instance caching for performance
- Support for both chat and image generation providers
- Fallback provider configuration

## API Endpoints

### Chat Completions

**Endpoint:** `POST /v1/chat/completions`

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    headers={
        "Content-Type": "application/json"
    },
    json={
        "model": "ChatGPT/gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 150,
        "stream": False
    }
)
```

### Image Generation

**Endpoint:** `POST /v1/images/generations`

```python
response = requests.post(
    "http://localhost:8000/v1/images/generations",
    headers={
        "Content-Type": "application/json"
    },
    json={
        "prompt": "A futuristic cityscape at sunset",
        "model": "PollinationsAI/flux",
        "n": 1,
        "size": "1024x1024",
        "response_format": "url"
    }
)
```

### Model Listing

**Endpoint:** `GET /v1/models`

```python
response = requests.get(
    "http://localhost:8000/v1/models"
)
```

## Starting the Server

### Command Line Interface

The server provides a comprehensive CLI with environment variable support:

```bash
# Basic startup
webscout-server

# Custom configuration
webscout-server --port 8080 --host localhost --debug

# Production settings
webscout-server --workers 4 --log-level info
```

### Programmatic Startup

```python
from webscout.server import start_server, run_api

# Simple startup
start_server()

# Advanced configuration
start_server(
    port=8080,
    host="0.0.0.0",
    debug=False,
)

# Full control with run_api
run_api(
    host="0.0.0.0",
    port=8000,
    workers=4,
    log_level="info",
    debug=False
)
```

### Alternative Methods

```bash
# Using UV (no installation required)
uv run --extra api webscout-server

# Using Python module
python -m webscout.server.server

# Direct module execution
python -m webscout.server.server --port 8080
```

## Usage Examples

### OpenAI Python Client

```python
from openai import OpenAI

# Initialize client
client = OpenAI(
    api_key="dummy-key", # API key is not required, but the client may expect a value
    base_url="http://localhost:8000/v1"
)

# Chat completion
response = client.chat.completions.create(
    model="ChatGPT/gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing"}
    ],
    temperature=0.7,
    max_tokens=500
)

print(response.choices[0].message.content)
```

### Streaming Responses

```python
# Streaming chat completion
stream = client.chat.completions.create(
    model="ChatGPT/gpt-4",
    messages=[{"role": "user", "content": "Write a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

### cURL Examples

```bash
# Chat completion
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ChatGPT/gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'

# List models
curl http://localhost:8000/v1/models
```

## Environment Variables

The server supports comprehensive environment variable configuration:

### Server Configuration

```bash
# Server settings
export WEBSCOUT_HOST="0.0.0.0"
export WEBSCOUT_PORT="8000"
export WEBSCOUT_WORKERS="4"
export WEBSCOUT_LOG_LEVEL="info"
export WEBSCOUT_DEBUG="false"

# Optional API configuration
export WEBSCOUT_DEFAULT_PROVIDER="ChatGPT"
export WEBSCOUT_BASE_URL="/api/v1"
```

### Docker Environment

```bash
# Docker-specific variables
export WEBSCOUT_API_TITLE="My AI API"
export WEBSCOUT_API_DESCRIPTION="Custom AI API Server"
export WEBSCOUT_API_VERSION="1.0.0"
export WEBSCOUT_API_DOCS_URL="/docs"
```

For a complete list of supported environment variables and Docker deployment options, see [DOCKER.md](../DOCKER.md).

## Error Handling

### [`APIError`](../webscout/server/exceptions.py:26)

Comprehensive error handling with OpenAI-compatible error responses.

```python
from webscout.server.exceptions import APIError
from starlette.status import HTTP_400_BAD_REQUEST

# Raise API error
raise APIError(
    message="Invalid model specified",
    status_code=HTTP_400_BAD_REQUEST,
    error_type="invalid_request_error",
    param="model",
    code="model_not_found"
)
```

**Error Response Format:**
```json
{
  "error": {
    "message": "Invalid model specified",
    "type": "invalid_request_error",
    "param": "model",
    "code": "model_not_found",
    "footer": "If you believe this is a bug, please pull an issue at https://github.com/OEvortex/Webscout."
  }
}
```

### Exception Handling

The server provides comprehensive exception handling with detailed error responses:

```python
# Validation errors
{
  "error": {
    "message": "Request validation error.",
    "details": [
      {
        "loc": ["body", "messages"],
        "message": "field required at body -> messages",
        "type": "value_error.missing"
      }
    ],
    "type": "validation_error"
  }
}
```

## Troubleshooting

If you encounter issues, check the server logs for detailed error messages. You can increase the log level to `debug` for more verbose output:

```bash
webscout-server --log-level debug
```

Common issues include:
- Incorrect provider or model names.
- Network connectivity issues to the provider's API.
- Invalid request format.

*This documentation covers the comprehensive functionality of the [`webscout.server`](../webscout/server/__init__.py:1) module. For the most up-to-date information, refer to the source code and inline documentation.*
