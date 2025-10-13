"""__init__.py for engines package - auto-discovers and registers search engines."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from collections import defaultdict
from typing import Any

from ..base import BaseSearchEngine

logger = logging.getLogger(__name__)

# ENGINES[category][name] = class
ENGINES: dict[str, dict[str, type[BaseSearchEngine[Any]]]] = defaultdict(dict)

package_name = __name__
package = importlib.import_module(package_name)

# Auto-discover all search engine classes
for finder, modname, _ispkg in pkgutil.iter_modules(package.__path__, package_name + "."):
    try:
        module = importlib.import_module(modname)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            # Must subclass BaseSearchEngine (but not the base itself)
            if not issubclass(cls, BaseSearchEngine) or cls is BaseSearchEngine:
                continue

            # Skip any class whose name starts with "Base"
            if cls.__name__.startswith("Base"):
                continue

            # Skip disabled engines
            if getattr(cls, "disabled", False):
                logger.info("Skipping disabled engine: %s", cls.name)
                continue

            # Register the engine
            if hasattr(cls, "name") and hasattr(cls, "category"):
                ENGINES[cls.category][cls.name] = cls
                logger.debug("Registered engine: %s (%s)", cls.name, cls.category)
    except Exception as ex:
        logger.warning("Failed to import module %s: %r", modname, ex)


__all__ = ["ENGINES"]
