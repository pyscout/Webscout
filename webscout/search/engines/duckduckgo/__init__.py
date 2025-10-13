"""DuckDuckGo search engines package."""

from .answers import DuckDuckGoAnswers
from .base import DuckDuckGoBase
from .images import DuckDuckGoImages
from .maps import DuckDuckGoMaps
from .news import DuckDuckGoNews
from .suggestions import DuckDuckGoSuggestions
from .text import DuckDuckGoTextSearch
from .translate import DuckDuckGoTranslate
from .videos import DuckDuckGoVideos
from .weather import DuckDuckGoWeather

__all__ = [
    "DuckDuckGoBase",
    "DuckDuckGoTextSearch",
    "DuckDuckGoImages",
    "DuckDuckGoVideos",
    "DuckDuckGoNews",
    "DuckDuckGoAnswers",
    "DuckDuckGoSuggestions",
    "DuckDuckGoMaps",
    "DuckDuckGoTranslate",
    "DuckDuckGoWeather",
]
