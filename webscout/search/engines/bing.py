"""Bing search engine implementation."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from time import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..base import BaseSearchEngine
from ..results import TextResult


def unwrap_bing_url(raw_url: str) -> str | None:
    """Decode the Bing-wrapped raw_url to extract the original url."""
    try:
        parsed = urlparse(raw_url)
        if parsed.netloc == "www.bing.com" and parsed.path == "/ck/a":
            query_params = parse_qs(parsed.query)
            if "u" in query_params:
                encoded_url = query_params["u"][0]
                # Decode the base64-like encoding
                if encoded_url.startswith("a1"):
                    encoded_url = encoded_url[2:]
                # Add padding if needed
                padding = len(encoded_url) % 4
                if padding:
                    encoded_url += "=" * (4 - padding)
                try:
                    decoded = base64.urlsafe_b64decode(encoded_url).decode()
                    return decoded
                except Exception:
                    pass
        return raw_url
    except Exception:
        return raw_url


class Bing(BaseSearchEngine[TextResult]):
    """Bing search engine."""

    name = "bing"
    category = "text"
    provider = "bing"

    search_url = "https://www.bing.com/search"
    search_method = "GET"

    items_xpath = "//li[contains(@class, 'b_algo')]"
    elements_xpath: Mapping[str, str] = {
        "title": ".//h2/a//text()",
        "href": ".//h2/a/@href",
        "body": ".//p//text()",
    }

    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int = 1, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the Bing search request."""
        country, lang = region.lower().split("-")
        payload = {"q": query, "pq": query, "cc": lang}
        cookies = {
            "_EDGE_CD": f"m={lang}-{country}&u={lang}-{country}",
            "_EDGE_S": f"mkt={lang}-{country}&ui={lang}-{country}",
        }
        self.http_client.set_cookies("https://www.bing.com", cookies)
        if timelimit:
            d = int(time() // 86400)
            payload["filters"] = {
                "d": f"ex1:\"ez1_{d - 1}_{d}\"",
                "w": f"ex1:\"ez1_{d - 7}_{d}\"",
                "m": f"ex1:\"ez1_{d - 30}_{d}\"",
                "y": f"ex1:\"ez1_{d - 365}_{d}\"",
            }[timelimit]
        if page > 1:
            payload["first"] = f"{(page - 1) * 10 + 1}"
        return payload

    def post_extract_results(self, results: list[TextResult]) -> list[TextResult]:
        """Post-process search results."""
        for result in results:
            result.href = unwrap_bing_url(result.href)
        return results
