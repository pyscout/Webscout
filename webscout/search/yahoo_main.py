"""Yahoo unified search interface."""

from __future__ import annotations
from typing import Dict, List, Optional
from .base import BaseSearch
from .engines.yahoo.text import YahooText
from .engines.yahoo.images import YahooImages
from .engines.yahoo.videos import YahooVideos
from .engines.yahoo.news import YahooNews
from .engines.yahoo.suggestions import YahooSuggestions
from .engines.yahoo.answers import YahooAnswers
from .engines.yahoo.maps import YahooMaps
from .engines.yahoo.translate import YahooTranslate
from .engines.yahoo.weather import YahooWeather


class YahooSearch(BaseSearch):
    """Unified Yahoo search interface."""

    def text(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YahooText()
        return search.run(keywords, region, safesearch, max_results)

    def images(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YahooImages()
        return search.run(keywords, region, safesearch, max_results)

    def videos(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YahooVideos()
        return search.run(keywords, region, safesearch, max_results)

    def news(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YahooNews()
        return search.run(keywords, region, safesearch, max_results)

    def suggestions(self, keywords: str, region: str = "us") -> List[str]:
        search = YahooSuggestions()
        return search.run(keywords, region)

    def answers(self, keywords: str) -> List[Dict[str, str]]:
        search = YahooAnswers()
        return search.run(keywords)

    def maps(self, keywords: str, place: Optional[str] = None, street: Optional[str] = None, city: Optional[str] = None, county: Optional[str] = None, state: Optional[str] = None, country: Optional[str] = None, postalcode: Optional[str] = None, latitude: Optional[str] = None, longitude: Optional[str] = None, radius: int = 0, max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YahooMaps()
        return search.run(keywords, place, street, city, county, state, country, postalcode, latitude, longitude, radius, max_results)

    def translate(self, keywords: str, from_lang: Optional[str] = None, to_lang: str = "en") -> List[Dict[str, str]]:
        search = YahooTranslate()
        return search.run(keywords, from_lang, to_lang)

    def weather(self, keywords: str) -> List[Dict[str, str]]:
        search = YahooWeather()
        return search.run(keywords)