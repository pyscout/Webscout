"""Brave search engine implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..base import BaseSearchEngine
from ..results import TextResult


class Brave(BaseSearchEngine[TextResult]):
    """Brave search engine."""

    name = "brave"
    category = "text"
    provider = "brave"

    search_url = "https://search.brave.com/search"
    search_method = "GET"

    items_xpath = "//div[@data-type='web']"
    elements_xpath: Mapping[str, str] = {
        "title": ".//div[(contains(@class,'title') or contains(@class,'sitename-container')) and position()=last()]//text()",
        "href": "./a/@href",
        "body": ".//div[contains(@class, 'description')]//text()",
    }

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the search request."""
        safesearch_base = {"on": "strict", "moderate": "moderate", "off": "off"}
        payload = {
            "q": query,
            "source": "web",
            "safesearch": safesearch_base[safesearch.lower()],
        }
        if timelimit:
            payload["tf"] = timelimit
        if page > 1:
            payload["offset"] = f"{(page - 1) * 10}"
        return payload
