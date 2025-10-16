"""Yahoo video search engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

from .base import YahooSearchEngine
from ...results import VideosResult


class YahooVideos(YahooSearchEngine[VideosResult]):
    """Yahoo video search engine with filters.
    
    Features:
    - Length filters (short, medium, long)
    - Resolution filters (SD, HD, 4K)
    - Source filters
    - Time filters
    - Pagination support
    """

    name = "yahoo"
    category = "videos"

    search_url = "https://video.search.yahoo.com/search/video"
    search_method = "GET"

    # XPath selectors for video results
    items_xpath = "//div[@id='results']//div[contains(@class, 'dd') or contains(@class, 'vr')]"
    elements_xpath: Mapping[str, str] = {
        "title": ".//h3//a/text() | .//a/@title",
        "url": ".//h3//a/@href | .//a/@href",
        "thumbnail": ".//img/@src",
        "duration": ".//span[contains(@class, 'time') or contains(@class, 'duration')]//text()",
        "views": ".//span[contains(@class, 'views')]//text()",
        "published": ".//span[contains(@class, 'date') or contains(@class, 'age')]//text()",
        "source": ".//span[contains(@class, 'source')]//text()",
    }

    # Filter mappings
    LENGTH_FILTERS = {
        "short": "short",    # < 4 minutes
        "medium": "medium",  # 4-20 minutes
        "long": "long",      # > 20 minutes
        "all": "",
    }

    RESOLUTION_FILTERS = {
        "sd": "sd",
        "hd": "hd",
        "4k": "4k",
        "all": "",
    }

    SOURCE_FILTERS = {
        "youtube": "youtube",
        "dailymotion": "dailymotion",
        "vimeo": "vimeo",
        "metacafe": "metacafe",
        "all": "",
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
        """Build video search payload.
        
        Args:
            query: Search query
            region: Region code
            safesearch: Safe search level
            timelimit: Time filter (d, w, m)
            page: Page number
            **kwargs: Additional filters:
                - length: Video length filter
                - resolution: Video resolution filter
                - source: Video source filter
                
        Returns:
            Query parameters dictionary
        """
        payload = {
            "p": query,
            "fr": "sfp",
            "fr2": "p:s,v:v,m:sb,rgn:top",
            "ei": "UTF-8",
        }

        # Pagination
        if page > 1:
            # Each page shows ~15-20 videos
            payload["b"] = f"{(page - 1) * 15 + 1}"

        # Safe search
        if safesearch == "on":
            payload["safe"] = "active"
        elif safesearch == "off":
            payload["safe"] = "off"

        # Time filter
        if timelimit:
            time_map = {
                "d": "1d",
                "w": "1w",
                "m": "1m",
                "y": "1y",
            }
            if timelimit in time_map:
                payload["age"] = time_map[timelimit]

        # Length filter
        if "length" in kwargs and kwargs["length"] in self.LENGTH_FILTERS:
            length_val = self.LENGTH_FILTERS[kwargs["length"]]
            if length_val:
                payload["vidlen"] = length_val

        # Resolution filter
        if "resolution" in kwargs and kwargs["resolution"] in self.RESOLUTION_FILTERS:
            res_val = self.RESOLUTION_FILTERS[kwargs["resolution"]]
            if res_val:
                payload["vidqual"] = res_val

        # Source filter
        if "source" in kwargs and kwargs["source"] in self.SOURCE_FILTERS:
            source_val = self.SOURCE_FILTERS[kwargs["source"]]
            if source_val:
                payload["site"] = source_val

        return payload

    def extract_video_url(self, href: str) -> str:
        """Extract actual video URL from Yahoo redirect.
        
        Args:
            href: Yahoo redirect URL
            
        Returns:
            Actual video URL
        """
        if not href:
            return href
            
        try:
            # Parse the URL
            parsed = urlparse(href)
            
            # Check if it's a Yahoo redirect
            if "r.search.yahoo.com" in parsed.netloc or "/RU=" in href:
                # Extract the RU parameter
                if "/RU=" in href:
                    start = href.find("/RU=") + 4
                    end = href.find("/RK=", start)
                    if end == -1:
                        end = len(href)
                    from urllib.parse import unquote
                    return unquote(href[start:end])
                else:
                    query_params = parse_qs(parsed.query)
                    if "url" in query_params:
                        return query_params["url"][0]
            
            return href
        except Exception:
            return href

    def post_extract_results(self, results: list[VideosResult]) -> list[VideosResult]:
        """Post-process video results.
        
        Args:
            results: Raw extracted results
            
        Returns:
            Cleaned results
        """
        cleaned_results = []
        
        for result in results:
            # Extract real URL
            if result.url:
                result.url = self.extract_video_url(result.url)
            
            # Skip invalid results
            if not result.url or not result.title:
                continue
            
            # Clean thumbnail URL
            if result.thumbnail and result.thumbnail.startswith("data:"):
                result.thumbnail = ""
            
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
    ) -> list[VideosResult] | None:
        """Search Yahoo Videos with pagination.
        
        Args:
            query: Video search query
            region: Region code
            safesearch: Safe search level
            timelimit: Time filter
            page: Starting page
            max_results: Maximum results
            **kwargs: Additional filters (length, resolution, source)
            
        Returns:
            List of VideoResult objects
        """
        results = []
        current_page = page
        max_pages = kwargs.get("max_pages", 5)
        
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
        resolution: str | None = None,
        duration: str | None = None,
        license_videos: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, str]]:
        """Run video search and return results as dictionaries.
        
        Args:
            keywords: Search query.
            region: Region code.
            safesearch: Safe search level.
            timelimit: Time filter.
            resolution: Video resolution filter.
            duration: Video duration filter.
            license_videos: License filter.
            max_results: Maximum number of results.
            
        Returns:
            List of video result dictionaries.
        """
        results = self.search(
            query=keywords,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            resolution=resolution,
            duration=duration,
            license_videos=license_videos,
            max_results=max_results,
        )
        if results is None:
            return []
        return [result.to_dict() for result in results]
