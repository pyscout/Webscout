# This file marks the directory as a Python package.

import os
import importlib
from pathlib import Path

# Get current directory
current_dir = Path(__file__).parent

# List to store all exported names
__all__ = []

# Auto-import all .py files (except __init__.py)
for file_path in current_dir.glob("*.py"):
    if file_path.name != "__init__.py":
        module_name = file_path.stem
        try:
            module = importlib.import_module(f".{module_name}", package=__name__)
            
            # Import the main class (assumes class name matches filename)
            class_name = module_name
            if hasattr(module, class_name):
                globals()[class_name] = getattr(module, class_name)
                __all__.append(class_name)
            else:
                # If no matching class, import all public attributes
                for attr_name in dir(module):
                    if not attr_name.startswith('_'):
                        globals()[attr_name] = getattr(module, attr_name)
                        if attr_name not in __all__:
                            __all__.append(attr_name)
        except ImportError:
            pass  # Skip files that can't be imported
