"""Webscout search module - unified search interfaces."""

from .base import BaseSearch, BaseSearchEngine
from .duckduckgo_main import DuckDuckGoSearch
from .yep_main import YepSearch
from .bing_main import BingSearch
from .yahoo_main import YahooSearch

# Import new search engines
from .engines.brave import Brave
from .engines.mojeek import Mojeek

from .engines.yandex import Yandex
from .engines.wikipedia import Wikipedia

# Import result models
from .results import (
    TextResult,
    ImagesResult,
    VideosResult,
    NewsResult,
    BooksResult,
)

__all__ = [
    # Base classes
    "BaseSearch",
    "BaseSearchEngine",
    
    # Main search interfaces
    "DuckDuckGoSearch",
    "YepSearch",
    "BingSearch",
    "YahooSearch",
    
    # Individual engines
    "Brave",
    "Mojeek",
    "Yandex",
    "Wikipedia",
    
    # Result models
    "TextResult",
    "ImagesResult",
    "VideosResult",
    "NewsResult",
    "BooksResult",
]
