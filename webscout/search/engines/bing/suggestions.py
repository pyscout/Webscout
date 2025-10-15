"""Bing suggestions search."""

from __future__ import annotations

from typing import List
from urllib.parse import urlencode

from .base import BingBase


class BingSuggestionsSearch(BingBase):
    def run(self, *args, **kwargs) -> List[str]:
        query = args[0] if args else kwargs.get("query")
        region = args[1] if len(args) > 1 else kwargs.get("region", "en-US")

        if not query:
            raise ValueError("Query is mandatory")

        params = {
            "query": query,
            "mkt": region
        }
        url = f"https://api.bing.com/osjson.aspx?{urlencode(params)}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            # Bing suggestions API returns [query, [suggestions]]
            if len(data) > 1 and isinstance(data[1], list):
                return data[1]
            return []
        except Exception as e:
            raise Exception(f"Failed to fetch suggestions: {str(e)}")