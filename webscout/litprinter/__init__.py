try:
    import litprinter
    # If standalone package is found, re-export all its components
    from litprinter import litprint, lit, log, ic, install, uninstall
    from litprinter import LITPrintDebugger, argumentToString
    from litprinter import JARVIS, RICH, MODERN, NEON, CYBERPUNK, create_custom_style
    from litprinter import traceback   
    # For compatibility with icecream
    enable = litprinter.enable
    disable = litprinter.disable
    
except ImportError:
    # Raise a more informative error when litprinter is not installed
    raise ImportError(
        "The 'litprinter' package is required but not installed. "
        "Please install it using: pip install litprinter"
    ) from None