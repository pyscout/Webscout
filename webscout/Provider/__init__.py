# This file marks the directory as a Python package.

import os
import importlib
from pathlib import Path

# Get current directory
current_dir = Path(__file__).parent

# Auto-import all .py files (except __init__.py)
for file_path in current_dir.glob("*.py"):
    if file_path.name != "__init__.py":
        module_name = file_path.stem
        try:
            module = importlib.import_module(f".{module_name}", package=__name__)
            globals().update(vars(module))
        except ImportError:
            pass  # Skip files that can't be imported
