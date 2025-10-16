"""Yahoo search suggestions engine."""

from __future__ import annotations

import json
from typing import Any

from .base import YahooSearchEngine


class YahooSuggestions(YahooSearchEngine[str]):
    """Yahoo search suggestions engine.
    
    Provides autocomplete suggestions as you type.
    """

    name = "yahoo"
    category = "suggestions"

    search_url = "https://search.yahoo.com/sugg/gossip/gossip-us-ura"
    search_method = "GET"

    def build_payload(
        self,
        query: str,
        region: str,
        safesearch: str,
        timelimit: str | None,
        page: int = 1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build suggestions payload.
        
        Args:
            query: Partial search query
            region: Region code
            safesearch: Safe search level (unused)
            timelimit: Time limit (unused)
            page: Page number (unused)
            **kwargs: Additional parameters
            
        Returns:
            Query parameters
        """
        payload = {
            "command": query,
            "output": "sd1",
            "nresults": kwargs.get("max_suggestions", 10),
        }
        
        return payload

    def extract_results(self, html_text: str) -> list[str]:
        """Extract suggestions from JSON response.
        
        Args:
            html_text: JSON response text
            
        Returns:
            List of suggestion strings
        """
        try:
            data = json.loads(html_text)
            
            # Yahoo returns suggestions in 'r' key
            if "r" in data and isinstance(data["r"], list):
                suggestions = []
                for item in data["r"]:
                    if isinstance(item, dict) and "k" in item:
                        suggestions.append(item["k"])
                    elif isinstance(item, str):
                        suggestions.append(item)
                return suggestions
            
            return []
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def search(
        self,
        query: str,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        page: int = 1,
        max_results: int | None = None,
        **kwargs: Any,
    ) -> list[str] | None:
        """Get search suggestions for a query.
        
        Args:
            query: Partial search query
            region: Region code
            safesearch: Safe search level
            timelimit: Time limit
            page: Page number
            max_results: Maximum suggestions
            **kwargs: Additional parameters
            
        Returns:
            List of suggestion strings
        """
        if max_results:
            kwargs["max_suggestions"] = max_results
        
        payload = self.build_payload(
            query=query,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            page=page,
            **kwargs
        )
        
        response = self.request(self.search_method, self.search_url, params=payload)
        if not response:
            return None
        
        suggestions = self.extract_results(response)
        
        if max_results:
            suggestions = suggestions[:max_results]
        
        return suggestions if suggestions else None

    def run(self, keywords: str, region: str = "us-en") -> list[str]:
        """Run suggestions search and return results.
        
        Args:
            keywords: Search query.
            region: Region code.
            
        Returns:
            List of suggestion strings.
        """
        results = self.search(
            query=keywords,
            region=region,
        )
        return results if results else []
