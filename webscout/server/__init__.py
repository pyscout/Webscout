# webscout/server/__init__.py

from .schemas import (
    HealthCheckResponse
)
# Import server functions lazily to avoid module execution issues
def create_app():
    from .server import create_app as _create_app
    return _create_app()

def run_api(*args, **kwargs):
    from .server import run_api as _run_api
    return _run_api(*args, **kwargs)

def start_server(*args, **kwargs):
    from .server import start_server as _start_server
    return _start_server(*args, **kwargs)
from .routes import Api
from .exceptions import APIError

# Lazy imports for config classes to avoid initialization issues
def get_server_config():
    from .config import ServerConfig
    return ServerConfig

def get_app_config():
    from .config import AppConfig
    return AppConfig

def initialize_provider_map():
    from .providers import initialize_provider_map as _init_provider_map
    return _init_provider_map()

def initialize_tti_provider_map():
    from .providers import initialize_tti_provider_map as _init_tti_provider_map
    return _init_tti_provider_map()

__all__ = [
    "HealthCheckResponse",
    "create_app",
    "run_api",
    "start_server",
    "Api",
    "get_server_config",
    "get_app_config",
    "APIError",
    "initialize_provider_map",
    "initialize_tti_provider_map"
]