"""
Unified client import for OpenAI-compatible providers and server utilities.

This module provides a unified import interface for all OpenAI-compatible providers and exposes
helper functions to start the OpenAI-compatible API server programmatically.

Usage:
    from webscout.client import FreeAIChat, AI4Chat, ExaChat, MultiChatAI, TwoAI, SciraChat, ChatSandbox, C4AI, Groq, TypeGPT, LLMChat, Cleeai, DeepInfra, BlackboxAI, Cloudflare, Netwrck, OIVSCode, Venice, Writecream, Wisecat, Yep, X0GPT, Sonus, Toolbaz, TextPollinations, StandardInput, Opkfc, Flowith, ExaAI, FreeGemini, GeminiAPI, Gemini, GithubChat, GizAI, Glider, HeckAI, HuggingFaceChat, Hunyuan, Jadve, Julius, Koala, LearnFast, LearnFastAI, NEMOTRON, MCPCore, PydanticImports, TeachAnything, UncovrAI, API, Base
    client = FreeAIChat()
    response = client.chat.completions.create(...)

    # To start the server programmatically:
    from webscout.client import start_server
    start_server()

    # For advanced server control:
    from webscout.client import run_api
    run_api(host="0.0.0.0", port=8000, debug=True)

    # Instantly start the API server from the command line:
    #   python -m webscout.client
    # or, if installed as a script:
    #   webscout-api

Exports:
    - All OpenAI-compatible provider classes
    - start_server (function): Start the OpenAI-compatible API server with default or custom settings.
    - run_api (function): Advanced server startup with full control over host, port, and other options.
"""

from webscout.Provider.OPENAI import *

# Import server utilities from the FastAPI-compatible backend
try:
    # Use lazy import to avoid module execution issues
    def run_api(*args, **kwargs):
        from webscout.server.server import run_api as _run_api
        return _run_api(*args, **kwargs)
    
    def start_server(**kwargs):
        """Start the Webscout OpenAI-compatible API server (FastAPI backend)."""
        from webscout.server.server import run_api as _run_api
        return _run_api(**kwargs)
except ImportError:
    # Fallback for environments where the backend is not available
    def run_api(*args, **kwargs):
        raise ImportError("webscout.server.server.run_api is not available in this environment.")
    def start_server(*args, **kwargs):
        raise ImportError("webscout.server.server.start_server is not available in this environment.")

# ---
# API Documentation
#
# start_server
# -------------
# def start_server(
#     port: int = 8000,
#     host: str = "0.0.0.0",
#     api_key: str = None,
#     default_provider: str = None,
#     base_url: str = None,
#     workers: int = 1,
#     log_level: str = 'info',
#     debug: bool = False,
#     no_auth: bool = False,
#     no_rate_limit: bool = False
# ):
#     """
#     Start the OpenAI-compatible API server with optional configuration.
#
#     Parameters:
#         port (int, optional): The port to run the server on. Defaults to 8000.
#         host (str, optional): Host address to bind the server. Defaults to '0.0.0.0'.
#         api_key (str, optional): API key for authentication. If None, authentication is disabled.
#         default_provider (str, optional): The default provider to use. If None, uses the package default.
#         base_url (str, optional): Base URL prefix for the API (e.g., '/api/v1'). If None, no prefix is used.
#         workers (int, optional): Number of worker processes. Defaults to 1.
#         log_level (str, optional): Log level for the server ('debug', 'info', etc.). Defaults to 'info'.
#         debug (bool, optional): Run the server in debug mode with auto-reload. Defaults to False.
#         no_auth (bool, optional): Disable authentication (no API keys required). Defaults to False.
#         no_rate_limit (bool, optional): Disable rate limiting (unlimited requests). Defaults to False.
#
#     Returns:
#         None
#     """
#
# run_api
# -------
# def run_api(
#     host: str = '0.0.0.0',
#     port: int = None,
#     api_key: str = None,
#     default_provider: str = None,
#     base_url: str = None,
#     debug: bool = False,
#     workers: int = 1,
#     log_level: str = 'info',
#     show_available_providers: bool = True,
#     no_auth: bool = False,
#     no_rate_limit: bool = False,
# ) -> None:
#     """
#     Advanced server startup for the OpenAI-compatible API server.
#
#     Parameters:
#         host (str, optional): Host address to bind the server. Defaults to '0.0.0.0'.
#         port (int, optional): Port to run the server on. Defaults to 8000 if not specified.
#         api_key (str, optional): API key for authentication. If None, authentication is disabled.
#         default_provider (str, optional): The default provider to use. If None, uses the package default.
#         base_url (str, optional): Base URL prefix for the API (e.g., '/api/v1'). If None, no prefix is used.
#         debug (bool, optional): Run the server in debug mode with auto-reload. Defaults to False.
#         workers (int, optional): Number of worker processes. Defaults to 1.
#         log_level (str, optional): Log level for the server ('debug', 'info', etc.). Defaults to 'info'.
#         show_available_providers (bool, optional): Print available providers on startup. Defaults to True.
#         no_auth (bool, optional): Disable authentication (no API keys required). Defaults to False.
#         no_rate_limit (bool, optional): Disable rate limiting (unlimited requests). Defaults to False.
#
#     Returns:
#         None
#     """
