"""Bing unified search interface."""

from __future__ import annotations
from typing import Dict, List, Optional
from .base import BaseSearch
from .engines.bing.text import BingTextSearch
from .engines.bing.images import BingImagesSearch
from .engines.bing.news import BingNewsSearch
from .engines.bing.suggestions import BingSuggestionsSearch


class BingSearch(BaseSearch):
    """Unified Bing search interface."""

    def text(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None, unique: bool = True) -> List[Dict[str, str]]:
        search = BingTextSearch()
        return search.run(keywords, region, safesearch, max_results, unique=unique)

    def images(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = BingImagesSearch()
        return search.run(keywords, region, safesearch, max_results)

    def news(self, keywords: str, region: str = "us", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = BingNewsSearch()
        return search.run(keywords, region, safesearch, max_results)

    def suggestions(self, query: str, region: str = "en-US") -> List[Dict[str, str]]:
        search = BingSuggestionsSearch()
        result = search.run(query, region)
        return [{'suggestion': s} for s in result]

    def answers(self, keywords: str) -> List[Dict[str, str]]:
        raise NotImplementedError("Answers not implemented for Bing")

    def maps(self, *args, **kwargs) -> List[Dict[str, str]]:
        raise NotImplementedError("Maps not implemented for Bing")

    def translate(self, keywords: str, from_lang: Optional[str] = None, to_lang: str = "en") -> List[Dict[str, str]]:
        raise NotImplementedError("Translate not implemented for Bing")

    def videos(self, *args, **kwargs) -> List[Dict[str, str]]:
        raise NotImplementedError("Videos not implemented for Bing")