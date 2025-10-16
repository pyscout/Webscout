"""Yahoo text search engine with pagination support."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote_plus, urljoin

from .base import YahooSearchEngine
from ...results import TextResult


def extract_url(u: str) -> str:
    """Extract and sanitize URL from Yahoo redirect.
    
    Yahoo uses /RU= redirect URLs that need to be decoded.
    Example: /url?sa=t&url=https%3A%2F%2Fexample.com
    """
    if not u:
        return u
    
    # Handle /RU= redirect format
    if "/RU=" in u:
        start = u.find("/RU=") + 4
        end = u.find("/RK=", start)
        if end == -1:
            end = len(u)
        return unquote_plus(u[start:end])
    
    return u


class YahooText(YahooSearchEngine[TextResult]):
    """Yahoo text search engine with full pagination support.
    
    Features:
    - Multi-page navigation like a human
    - Automatic next page detection
    - Clean result extraction
    - Time filter support
    - Region support
    """

    name = "yahoo"
    category = "text"

    search_url = "https://search.yahoo.com/search"
    search_method = "GET"

    # XPath selectors for result extraction
    items_xpath = "//div[contains(@class, 'compTitle')]"
    elements_xpath: Mapping[str, str] = {
        "title": ".//h3//span//text()",
        "href": ".//a/@href",
        "body": "./following-sibling::div[contains(@class, 'compText')]//text()",
    }

    def build_payload(
        self, 
        query: str, 
        region: str, 
        safesearch: str, 
        timelimit: str | None, 
        page: int = 1, 
        **kwargs: Any
    ) -> dict[str, Any]:
        """Build search payload for Yahoo.
        
        Args:
            query: Search query string
            region: Region code (e.g., 'us-en')
            safesearch: Safe search level
            timelimit: Time limit filter (d=day, w=week, m=month)
            page: Page number (1-indexed)
            **kwargs: Additional parameters
            
        Returns:
            Dictionary of query parameters
        """
        payload = {
            "p": query,
            "ei": "UTF-8",
        }
        
        # Pagination: Yahoo uses 'b' parameter for offset
        # Page 1: no b parameter or b=1
        # Page 2: b=8 (shows results 8-14)
        # Page 3: b=15, etc.
        if page > 1:
            payload["b"] = f"{(page - 1) * 7 + 1}"
        
        # Time filter
        if timelimit:
            payload["btf"] = timelimit
            
        return payload

    def post_extract_results(self, results: list[TextResult]) -> list[TextResult]:
        """Post-process and clean extracted results.
        
        Args:
            results: Raw extracted results
            
        Returns:
            Cleaned and filtered results
        """
        cleaned_results = []
        
        for result in results:
            # Extract real URL from redirect
            if result.href:
                result.href = extract_url(result.href)
            
            # Filter out empty results
            if result.title and result.href:
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
    ) -> list[TextResult] | None:
        """Search Yahoo with automatic pagination like a human browser.
        
        This method automatically follows pagination links to gather results
        across multiple pages, similar to how a human would browse search results.
        
        Args:
            query: Search query string
            region: Region code
            safesearch: Safe search level
            timelimit: Time filter (d=day, w=week, m=month, y=year)
            page: Starting page number
            max_results: Maximum number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of TextResult objects, or None if search fails
        """
        results = []
        current_page = page
        max_pages = kwargs.get("max_pages", 10)  # Limit to prevent infinite loops
        
        while current_page <= max_pages:
            # Build payload for current page
            payload = self.build_payload(
                query=query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                page=current_page,
                **kwargs
            )
            
            # Make request
            html_text = self.request(self.search_method, self.search_url, params=payload)
            if not html_text:
                break
            
            # Pre-process HTML
            html_text = self.pre_process_html(html_text)
            
            # Extract results from current page
            page_results = self.extract_results(html_text)
            if not page_results:
                break
            
            results.extend(page_results)
            
            # Check if we have enough results
            if max_results and len(results) >= max_results:
                break
            
            # Look for next page link
            tree = self.extract_tree(html_text)
            next_links = tree.xpath("//a[contains(text(), 'Next') or contains(@class, 'next')]/@href")
            
            if not next_links:
                # Try to find numbered page links
                page_links = tree.xpath(f"//a[contains(text(), '{current_page + 1}')]/@href")
                if not page_links:
                    break
            
            current_page += 1
        
        # Post-process all results
        results = self.post_extract_results(results)
        
        # Trim to max_results if specified
        if max_results:
            results = results[:max_results]
        
        return results if results else None

    def search_page(
        self,
        query: str,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        page: int = 1,
        **kwargs: Any,
    ) -> list[TextResult] | None:
        """Search a single page (for compatibility).
        
        Args:
            query: Search query
            region: Region code
            safesearch: Safe search level
            timelimit: Time filter
            page: Page number
            **kwargs: Additional parameters
            
        Returns:
            List of results from the specified page
        """
        payload = self.build_payload(
            query=query,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            page=page,
            **kwargs
        )
        
        html_text = self.request(self.search_method, self.search_url, params=payload)
        if not html_text:
            return None
        
        html_text = self.pre_process_html(html_text)
        results = self.extract_results(html_text)
        
        return self.post_extract_results(results) if results else None

    def run(
        self,
        keywords: str,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        backend: str = "auto",
        max_results: int | None = None,
    ) -> list[dict[str, str]]:
        """Run text search and return results as dictionaries.
        
        Args:
            keywords: Search query.
            region: Region code.
            safesearch: Safe search level.
            timelimit: Time filter.
            backend: Backend type (ignored for Yahoo).
            max_results: Maximum number of results.
            
        Returns:
            List of search result dictionaries.
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
