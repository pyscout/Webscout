"""Bing news search engine implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..base import BaseSearchEngine
from ..results import NewsResult


class BingNews(BaseSearchEngine[NewsResult]):
    """Bing news engine."""

    name = "bing"
    category = "news"
    provider = "bing"

    search_url = "https://www.bing.com/news/infinitescrollajax"
    search_method = "GET"

    items_xpath = "//div[contains(@class, 'newsitem')]"
    elements_xpath: Mapping[str, str] = {
        "date": ".//span[@aria-label]//@aria-label",
        "title": "@data-title",
        "body": ".//div[@class='snippet']//text()",
        "url": "@url",
        "image": ".//a[contains(@class, 'image')]//@src",
        "source": "@data-author",
    }

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the Bing search request."""
        country, lang = region.lower().split("-")
        payload = {
            "q": query,
            "InfiniteScroll": "1",
            "first": f"{page * 10 + 1}",
            "SFX": f"{page}",
            "cc": country,
            "setlang": lang,
        }
        if timelimit:
            payload["qft"] = {
                "d": 'interval="4"',  # doesn't exist so it's the same as one hour
                "w": 'interval="7"',
                "m": 'interval="9"',
                "y": 'interval="9"',  # doesn't exist so it's the same as month
            }[timelimit]
        return payload
