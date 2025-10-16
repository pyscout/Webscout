"""Yahoo search engines package.

This package provides comprehensive Yahoo search functionality including:
- Text search with multi-page pagination
- Image search with advanced filters
- Video search with quality and length filters
- News search with time filtering
- Search suggestions/autocomplete

All engines support:
- Human-like browsing through multiple pages
- Rich metadata extraction
- Filter support
- Clean result formatting

Example:
    >>> from webscout.search.engines.yahoo import YahooText
    >>> 
    >>> # Search with automatic pagination
    >>> searcher = YahooText()
    >>> results = searcher.search("python programming", max_results=50)
    >>> 
    >>> for result in results:
    ...     print(f"{result.title}: {result.url}")
"""

from .base import YahooSearchEngine
from .images import YahooImages
from .news import YahooNews
from .suggestions import YahooSuggestions
from .text import YahooText
from .videos import YahooVideos

__all__ = [
    "YahooSearchEngine",
    "YahooText",
    "YahooImages",
    "YahooVideos",
    "YahooNews",
    "YahooSuggestions",
]
