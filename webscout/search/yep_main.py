"""Yep unified search interface."""

from __future__ import annotations
from typing import Dict, List, Optional
from .base import BaseSearch
from .engines.yep.text import YepSearch as YepTextSearch
from .engines.yep.images import YepImages
from .engines.yep.suggestions import YepSuggestions


class YepSearch(BaseSearch):
    """Unified Yep search interface."""

    def text(self, keywords: str, region: str = "all", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YepTextSearch()
        return search.run(keywords, region, safesearch, max_results)

    def images(self, keywords: str, region: str = "all", safesearch: str = "moderate", max_results: Optional[int] = None) -> List[Dict[str, str]]:
        search = YepImages()
        return search.run(keywords, region, safesearch, max_results)

    def suggestions(self, keywords: str, region: str = "all") -> List[str]:
        search = YepSuggestions()
        return search.run(keywords, region)

    def videos(self, *args, **kwargs) -> List[Dict[str, str]]:
        """Videos search not supported by Yep."""
        raise NotImplementedError("Yep does not support video search")

    def news(self, *args, **kwargs) -> List[Dict[str, str]]:
        """News search not supported by Yep."""
        raise NotImplementedError("Yep does not support news search")

    def answers(self, *args, **kwargs) -> List[Dict[str, str]]:
        """Instant answers not supported by Yep."""
        raise NotImplementedError("Yep does not support instant answers")

    def maps(self, *args, **kwargs) -> List[Dict[str, str]]:
        """Maps search not supported by Yep."""
        raise NotImplementedError("Yep does not support maps search")

    def translate(self, *args, **kwargs) -> List[Dict[str, str]]:
        """Translation not supported by Yep."""
        raise NotImplementedError("Yep does not support translation")
