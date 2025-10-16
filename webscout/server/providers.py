"""
Provider management and initialization for the Webscout API.
"""

import sys
import inspect
from typing import Any, Dict, Tuple
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from webscout.Litlogger import Logger, LogLevel, LogFormat, ConsoleHandler
from .config import AppConfig
from .exceptions import APIError

# Setup logger
logger = Logger(
    name="webscout.api",
    level=LogLevel.INFO,
    handlers=[ConsoleHandler(stream=sys.stdout)],
    fmt=LogFormat.DEFAULT
)

# Cache for provider instances to avoid reinitialization on every request
provider_instances: Dict[str, Any] = {}
tti_provider_instances: Dict[str, Any] = {}


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
                provider_count += 1

                # Register available models for this provider
                if hasattr(obj, "AVAILABLE_MODELS") and isinstance(
                    obj.AVAILABLE_MODELS, (list, tuple, set)
                ):
                    for model in obj.AVAILABLE_MODELS:
                        if model and isinstance(model, str):
                            model_key = f"{provider_name}/{model}"
                            AppConfig.provider_map[model_key] = obj
                            model_count += 1

        # Fallback to ChatGPT if no providers found
        if not AppConfig.provider_map:
            logger.warning("No providers found, using ChatGPT fallback")
            try:
                from webscout.Provider.OPENAI.chatgpt import ChatGPT
                fallback_models = ["gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

                AppConfig.provider_map["ChatGPT"] = ChatGPT

                for model in fallback_models:
                    model_key = f"ChatGPT/{model}"
                    AppConfig.provider_map[model_key] = ChatGPT

                AppConfig.default_provider = "ChatGPT"
                provider_count = 1
                model_count = len(fallback_models)
            except ImportError as e:
                logger.error(f"Failed to import ChatGPT fallback: {e}")
                raise APIError("No providers available", HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(f"Initialized {provider_count} providers with {model_count} models")

    except Exception as e:
        logger.error(f"Failed to initialize provider map: {e}")
        raise APIError(f"Provider initialization failed: {e}", HTTP_500_INTERNAL_SERVER_ERROR)


def initialize_tti_provider_map() -> None:
    """Initialize the TTI provider map by discovering available TTI providers."""
    logger.info("Initializing TTI provider map...")

    try:
        from webscout.Provider.TTI.base import TTICompatibleProvider
        module = sys.modules["webscout.Provider.TTI"]

        provider_count = 0
        model_count = 0

        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, TTICompatibleProvider)
                and obj.__name__ != "TTICompatibleProvider"
                and obj.__name__ != "BaseImages"
            ):
                provider_name = obj.__name__
                AppConfig.tti_provider_map[provider_name] = obj
                provider_count += 1

                # Register available models for this TTI provider
                if hasattr(obj, "AVAILABLE_MODELS") and isinstance(
                    obj.AVAILABLE_MODELS, (list, tuple, set)
                ):
                    for model in obj.AVAILABLE_MODELS:
                        if model and isinstance(model, str):
                            model_key = f"{provider_name}/{model}"
                            AppConfig.tti_provider_map[model_key] = obj
                            model_count += 1

        # Fallback to PollinationsAI if no TTI providers found
        if not AppConfig.tti_provider_map:
            logger.warning("No TTI providers found, using PollinationsAI fallback")
            try:
                from webscout.Provider.TTI.pollinations import PollinationsAI
                fallback_models = ["flux", "turbo", "gptimage"]

                AppConfig.tti_provider_map["PollinationsAI"] = PollinationsAI

                for model in fallback_models:
                    model_key = f"PollinationsAI/{model}"
                    AppConfig.tti_provider_map[model_key] = PollinationsAI

                AppConfig.default_tti_provider = "PollinationsAI"
                provider_count = 1
                model_count = len(fallback_models)
            except ImportError as e:
                logger.error(f"Failed to import PollinationsAI fallback: {e}")
                raise APIError("No TTI providers available", HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(f"Initialized {provider_count} TTI providers with {model_count} models")

    except Exception as e:
        logger.error(f"Failed to initialize TTI provider map: {e}")
        raise APIError(f"TTI Provider initialization failed: {e}", HTTP_500_INTERNAL_SERVER_ERROR)


def resolve_provider_and_model(model_identifier: str) -> Tuple[Any, str]:
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
        available = getattr(provider_class, "AVAILABLE_MODELS", None)
        # If it's a property, get from instance
        if isinstance(available, property):
            try:
                available = getattr(provider_class(), "AVAILABLE_MODELS", [])
            except Exception:
                available = []
        # If still not iterable, fallback to empty list
        if not isinstance(available, (list, tuple, set)):
            available = list(available) if hasattr(available, "__iter__") and not isinstance(available, str) else []
        if available and model_name not in available:
            raise APIError(
                f"Model '{model_name}' not supported by provider '{provider_class.__name__}'. Available models: {available}",
                HTTP_404_NOT_FOUND,
                "model_not_found",
                param="model"
            )

    return provider_class, model_name


def resolve_tti_provider_and_model(model_identifier: str) -> Tuple[Any, str]:
    """Resolve TTI provider class and model name from model identifier."""
    provider_class = None
    model_name = None

    # Check for explicit provider/model syntax
    if model_identifier in AppConfig.tti_provider_map and "/" in model_identifier:
        provider_class = AppConfig.tti_provider_map[model_identifier]
        _, model_name = model_identifier.split("/", 1)
    elif "/" in model_identifier:
        provider_name, model_name = model_identifier.split("/", 1)
        provider_class = AppConfig.tti_provider_map.get(provider_name)
    else:
        provider_class = AppConfig.tti_provider_map.get(AppConfig.default_tti_provider)
        model_name = model_identifier

    if not provider_class:
        available_providers = list(set(v.__name__ for v in AppConfig.tti_provider_map.values()))
        raise APIError(
            f"TTI Provider for model '{model_identifier}' not found. Available TTI providers: {available_providers}",
            HTTP_404_NOT_FOUND,
            "model_not_found",
            param="model"
        )

    # Validate model availability
    if hasattr(provider_class, "AVAILABLE_MODELS") and model_name is not None:
        available = getattr(provider_class, "AVAILABLE_MODELS", None)
        # If it's a property, get from instance
        if isinstance(available, property):
            try:
                available = getattr(provider_class(), "AVAILABLE_MODELS", [])
            except Exception:
                available = []
        # If still not iterable, fallback to empty list
        if not isinstance(available, (list, tuple, set)):
            available = list(available) if hasattr(available, "__iter__") and not isinstance(available, str) else []
        if available and model_name not in available:
            raise APIError(
                f"Model '{model_name}' not supported by TTI provider '{provider_class.__name__}'. Available models: {available}",
                HTTP_404_NOT_FOUND,
                "model_not_found",
                param="model"
            )

    return provider_class, model_name


def get_provider_instance(provider_class: Any):
    """Return a cached instance of the provider, creating it if necessary."""
    key = provider_class.__name__
    instance = provider_instances.get(key)
    if instance is None:
        try:
            instance = provider_class()
        except TypeError as e:
            # Handle abstract class instantiation error
            if "abstract class" in str(e):
                from .exceptions import APIError
                raise APIError(
                    f"Provider misconfiguration: Cannot instantiate abstract class '{provider_class.__name__}'. Please check the provider implementation.",
                    HTTP_500_INTERNAL_SERVER_ERROR,
                    "provider_error"
                )
            raise
        provider_instances[key] = instance
    return instance


def get_tti_provider_instance(provider_class: Any):
    """Return a cached instance of the TTI provider, creating it if needed."""
    key = provider_class.__name__
    instance = tti_provider_instances.get(key)
    if instance is None:
        try:
            instance = provider_class()
        except TypeError as e:
            # Handle abstract class instantiation error
            if "abstract class" in str(e):
                from .exceptions import APIError
                raise APIError(
                    f"Provider misconfiguration: Cannot instantiate abstract class '{provider_class.__name__}'. Please check the provider implementation.",
                    HTTP_500_INTERNAL_SERVER_ERROR,
                    "provider_error",
                )
            raise
        tti_provider_instances[key] = instance
    return instance
