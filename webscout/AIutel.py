from .sanitize import * # noqa: E402,F401
from .conversation import Conversation  # noqa: E402,F401
from .Extra.autocoder import AutoCoder  # noqa: E402,F401
from .optimizers import Optimizers  # noqa: E402,F401
from .prompt_manager import AwesomePrompts  # noqa: E402,F401

# --- Utility Decorators ---
from typing import Callable
import time
import functools

def timeIt(func: Callable):
    """
    Decorator to measure execution time of a function (sync or async).
    Prints: - Execution time for '{func.__name__}' : {elapsed:.6f} Seconds.  
    """
    import asyncio
    GREEN_BOLD = "\033[1;92m"
    RESET = "\033[0m"
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print()
        print(f"{GREEN_BOLD}- Execution time for '{func.__name__}' : {end_time - start_time:.6f} Seconds.  {RESET}\n")
        return result

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        print()
        print(f"{GREEN_BOLD}- Execution time for '{func.__name__}' : {end_time - start_time:.6f} Seconds.  {RESET}\n")
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def retry(retries: int = 3, delay: float = 1) -> Callable:
    """
    Decorator to retry a function on exception.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    print(f"Attempt {attempt + 1} failed: {exc}. Retrying in {delay} seconds...")
                    time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
