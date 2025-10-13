"""Yahoo news search engine."""

from __future__ import annotations

from collections.abc import Mapping
from secrets import token_urlsafe
from typing import Any

from ..base import BaseSearchEngine
from ..results import NewsResult


def extract_image(u: str) -> str:
    """Sanitize image url."""
    if u and u.startswith("data:image"):
        return ""
    return u


def extract_source(s: str) -> str:
    """Remove ' via Yahoo' from string."""
    return s.replace(" via Yahoo", "") if s else s


class YahooNews(BaseSearchEngine[NewsResult]):
    """Yahoo news search engine."""

    name = "yahoo"
    category = "news"
    provider = "bing"

    search_url = "https://news.search.yahoo.com/search"
    search_method = "GET"

    items_xpath = "//div[contains(@class, 'NewsArticle')]"
    elements_xpath: Mapping[str, str] = {
        "date": ".//span[contains(@class, 'fc-2nd')]//text()",
        "title": ".//h4//a//text()",
        "url": ".//h4//a/@href",
        "body": ".//p//text()",
        "image": ".//img/@src",
        "source": ".//span[contains(@class, 's-source')]//text()",
    }

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the search request."""
        self.search_url = (
            f"https://news.search.yahoo.com/search;_ylt={token_urlsafe(24 * 3 // 4)};_ylu={token_urlsafe(47 * 3 // 4)}"
        )
        payload = {"p": query}
        if page > 1:
            payload["b"] = f"{(page - 1) * 10 + 1}"
        if timelimit:
            payload["btf"] = timelimit
        return payload

    def post_extract_results(self, results: list[NewsResult]) -> list[NewsResult]:
        """Post-process search results."""
        for result in results:
            result.image = extract_image(result.image)
            result.source = extract_source(result.source)
        return results
