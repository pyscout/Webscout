"""Webscout search module - unified search interfaces."""

from .base import BaseSearch, BaseSearchEngine
from .duckduckgo_main import DuckDuckGoSearch
from .yep_main import YepSearch

# Import new search engines
from .engines.bing import Bing
from .engines.brave import Brave
from .engines.mojeek import Mojeek
from .engines.yahoo import Yahoo
from .engines.yandex import Yandex
from .engines.wikipedia import Wikipedia
from .engines.bing_news import BingNews
from .engines.yahoo_news import YahooNews

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
    
    # Individual engines
    "Bing",
    "Brave",
    "Mojeek",
    "Yahoo",
    "Yandex",
    "Wikipedia",
    "BingNews",
    "YahooNews",
    
    # Result models
    "TextResult",
    "ImagesResult",
    "VideosResult",
    "NewsResult",
    "BooksResult",
]
