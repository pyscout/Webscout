"""Yandex search engine."""

from __future__ import annotations

from collections.abc import Mapping
from random import SystemRandom
from typing import Any

from ..base import BaseSearchEngine
from ..results import TextResult

random = SystemRandom()


class Yandex(BaseSearchEngine[TextResult]):
    """Yandex search engine."""

    name = "yandex"
    category = "text"
    provider = "yandex"

    search_url = "https://yandex.com/search/"
    search_method = "GET"

    items_xpath = "//li[contains(@class, 'serp-item')]"
    elements_xpath: Mapping[str, str] = {
        "title": ".//h2//text()",
        "href": ".//h2/a/@href",
        "body": ".//div[contains(@class, 'text-container')]//text()",
    }

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the search request."""
        safesearch_base = {"on": "1", "moderate": "0", "off": "0"}
        payload = {
            "text": query,
            "family": safesearch_base[safesearch.lower()],
        }
        if page > 1:
            payload["p"] = str(page - 1)
        return payload
