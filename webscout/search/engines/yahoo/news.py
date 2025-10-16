"""Yahoo news search engine with comprehensive features."""

from __future__ import annotations

from collections.abc import Mapping
from secrets import token_urlsafe
from typing import Any

from .base import YahooSearchEngine
from ...results import NewsResult


def extract_image(u: str) -> str:
    """Sanitize image URL.
    
    Args:
        u: Image URL
        
    Returns:
        Cleaned URL or empty string
    """
    if not u:
        return ""
    
    # Skip data URIs
    if u.startswith("data:image"):
        return ""
    
    return u


def extract_source(s: str) -> str:
    """Remove ' via Yahoo' from source string.
    
    Args:
        s: Source string
        
    Returns:
        Cleaned source name
    """
    if not s:
        return s
    
    return s.replace(" via Yahoo", "").replace(" - Yahoo", "").strip()


class YahooNews(YahooSearchEngine[NewsResult]):
    """Yahoo news search engine with advanced filtering.
    
    Features:
    - Time-based filtering
    - Category filtering
    - Source filtering
    - Pagination support
    - Rich metadata extraction
    """

    name = "yahoo"
    category = "news"

    search_url = "https://news.search.yahoo.com/search"
    search_method = "GET"

    # XPath selectors for news articles
    items_xpath = "//div[contains(@class, 'NewsArticle') or contains(@class, 'dd') and contains(@class, 'algo')]"
    elements_xpath: Mapping[str, str] = {
        "date": ".//span[contains(@class, 'fc-2nd') or contains(@class, 'age') or contains(@class, 's-time')]//text()",
        "title": ".//h4//a//text() | .//h3//a//text()",
        "url": ".//h4//a/@href | .//h3//a/@href",
        "body": ".//p//text() | .//div[contains(@class, 'compText')]//text()",
        "image": ".//img/@src",
        "source": ".//span[contains(@class, 's-source') or contains(@class, 'source')]//text()",
    }

    def build_payload(
        self,
        query: str,
        region: str,
        safesearch: str,
        timelimit: str | None,
        page: int = 1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build news search payload.
        
        Args:
            query: Search query
            region: Region code
            safesearch: Safe search level
            timelimit: Time filter (d, w, m)
            page: Page number
            **kwargs: Additional parameters
            
        Returns:
            Query parameters dictionary
        """
        # Generate dynamic URL tokens for tracking
        self.search_url = (
            f"https://news.search.yahoo.com/search"
            f";_ylt={token_urlsafe(24 * 3 // 4)}"
            f";_ylu={token_urlsafe(47 * 3 // 4)}"
        )
        
        payload = {
            "p": query,
            "ei": "UTF-8",
        }
        
        # Pagination - Yahoo news uses 'b' parameter
        if page > 1:
            # Each page shows approximately 10 articles
            payload["b"] = f"{(page - 1) * 10 + 1}"
        
        # Time filter
        if timelimit:
            time_map = {
                "d": "1d",   # Past 24 hours
                "w": "1w",   # Past week
                "m": "1m",   # Past month
            }
            if timelimit in time_map:
                payload["btf"] = time_map[timelimit]
        
        # Additional filters
        if "category" in kwargs:
            payload["category"] = kwargs["category"]
        
        if "sort" in kwargs:
            # Sort by relevance or date
            payload["sort"] = kwargs["sort"]
        
        return payload

    def post_extract_results(self, results: list[NewsResult]) -> list[NewsResult]:
        """Post-process news results.
        
        Args:
            results: Raw extracted results
            
        Returns:
            Cleaned news results
        """
        cleaned_results = []
        
        for result in results:
            # Clean image URL
            result.image = extract_image(result.image)
            
            # Clean source name
            result.source = extract_source(result.source)
            
            # Extract URL from redirect
            if result.url and "/RU=" in result.url:
                from urllib.parse import unquote
                start = result.url.find("/RU=") + 4
                end = result.url.find("/RK=", start)
                if end == -1:
                    end = len(result.url)
                result.url = unquote(result.url[start:end])
            
            # Filter out results without essential fields
            if result.title and result.url:
                cleaned_results.append(result)
        
        return cleaned_results

    def search(
        self,
        query: str,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        page: int = 1,
        max_results: int | None = None,
        **kwargs: Any,
    ) -> list[NewsResult] | None:
        """Search Yahoo News with pagination.
        
        Args:
            query: News search query
            region: Region code
            safesearch: Safe search level
            timelimit: Time filter (d, w, m)
            page: Starting page
            max_results: Maximum results to return
            **kwargs: Additional parameters (category, sort)
            
        Returns:
            List of NewsResult objects
        """
        results = []
        current_page = page
        max_pages = kwargs.get("max_pages", 10)
        
        while current_page <= max_pages:
            payload = self.build_payload(
                query=query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                page=current_page,
                **kwargs
            )
            
            html_text = self.request(self.search_method, self.search_url, params=payload)
            if not html_text:
                break
            
            html_text = self.pre_process_html(html_text)
            page_results = self.extract_results(html_text)
            
            if not page_results:
                break
            
            results.extend(page_results)
            
            if max_results and len(results) >= max_results:
                break
            
            current_page += 1
        
        results = self.post_extract_results(results)
        
        if max_results:
            results = results[:max_results]
        
        return results if results else None

    def run(
        self,
        keywords: str,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, str]]:
        """Run news search and return results as dictionaries.
        
        Args:
            keywords: Search query.
            region: Region code.
            safesearch: Safe search level.
            timelimit: Time filter.
            max_results: Maximum number of results.
            
        Returns:
            List of news result dictionaries.
        """
        results = self.search(
            query=keywords,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            max_results=max_results,
        )
        if results is None:
            return []
        return [result.to_dict() for result in results]
