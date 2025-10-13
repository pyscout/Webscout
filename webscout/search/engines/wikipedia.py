"""Wikipedia text search engine."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from ..base import BaseSearchEngine
from ..results import TextResult
from ...utils import json_loads

logger = logging.getLogger(__name__)


class Wikipedia(BaseSearchEngine[TextResult]):
    """Wikipedia text search engine."""

    name = "wikipedia"
    category = "text"
    provider = "wikipedia"
    priority = 2

    search_url = "https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={query}"
    search_method = "GET"

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the search request."""
        _country, lang = region.lower().split("-")
        encoded_query = quote(query)
        self.search_url = (
            f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&profile=fuzzy&limit=1&search={encoded_query}"
        )
        payload: dict[str, Any] = {}
        self.lang = lang  # used in extract_results
        return payload

    def extract_results(self, html_text: str) -> list[TextResult]:
        """Extract search results from html text."""
        json_data = json_loads(html_text)
        if not json_data or len(json_data) < 4:
            return []
        
        results = []
        titles, descriptions, urls = json_data[1], json_data[2], json_data[3]
        
        for title, description, url in zip(titles, descriptions, urls):
            result = TextResult()
            result.title = title
            result.body = description
            result.href = url
            results.append(result)
        
        return results
