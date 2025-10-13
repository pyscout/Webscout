"""Mojeek search engine implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..base import BaseSearchEngine
from ..results import TextResult


class Mojeek(BaseSearchEngine[TextResult]):
    """Mojeek search engine."""

    name = "mojeek"
    category = "text"
    provider = "mojeek"

    search_url = "https://www.mojeek.com/search"
    search_method = "GET"

    items_xpath = "//ul[contains(@class, 'results')]/li"
    elements_xpath: Mapping[str, str] = {
        "title": ".//h2//text()",
        "href": ".//h2/a/@href",
        "body": ".//p[@class='s']//text()",
    }

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the search request."""
        safesearch_base = {"on": "1", "moderate": "0", "off": "0"}
        payload = {"q": query, "safe": safesearch_base[safesearch.lower()]}
        if page > 1:
            payload["s"] = f"{(page - 1) * 10 + 1}"
        return payload
