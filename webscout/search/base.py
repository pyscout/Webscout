"""Base class for search engines."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from functools import cached_property
from typing import Any, Generic, Literal, TypeVar

try:
    from lxml import html
    from lxml.etree import HTMLParser as LHTMLParser
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False
    html = None  # type: ignore
    LHTMLParser = None  # type: ignore

from .http_client import HttpClient
from .results import BooksResult, ImagesResult, NewsResult, TextResult, VideosResult

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BaseSearchEngine(ABC, Generic[T]):
    """Abstract base class for all search engine backends."""

    name: str  # unique key, e.g. "google"
    category: Literal["text", "images", "videos", "news", "books"]
    provider: str  # source of the search results (e.g. "google", "bing", etc.)
    disabled: bool = False  # if True, the engine is disabled
    priority: float = 1

    search_url: str
    search_method: str  # GET or POST
    search_headers: Mapping[str, str] = {}
    items_xpath: str = ""
    elements_xpath: Mapping[str, str] = {}
    elements_replace: Mapping[str, str] = {}

    def __init__(self, proxy: str | None = None, timeout: int | None = None, verify: bool = True):
        """Initialize search engine.
        
        Args:
            proxy: Proxy URL (supports http/https/socks5).
            timeout: Request timeout in seconds.
            verify: Whether to verify SSL certificates.
        """
        self.http_client = HttpClient(proxy=proxy, timeout=timeout, verify=verify)
        self.results: list[T] = []

    @property
    def result_type(self) -> type[T]:
        """Get result type based on category."""
        categories = {
            "text": TextResult,
            "images": ImagesResult,
            "videos": VideosResult,
            "news": NewsResult,
            "books": BooksResult,
        }
        return categories[self.category]  # type: ignore

    @abstractmethod
    def build_payload(
        self, query: str, region: str, safesearch: str, timelimit: str | None, page: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Build a payload for the search request."""
        raise NotImplementedError

    def request(self, method: str, url: str, **kwargs: Any) -> str | None:
        """Make a request to the search engine."""
        try:
            response = self.http_client.request(method, url, **kwargs)  # type: ignore
            return response.text
        except Exception as ex:
            logger.error("Error in %s request: %r", self.name, ex)
            return None

    @cached_property
    def parser(self) -> Any:
        """Get HTML parser."""
        if not LXML_AVAILABLE:
            logger.warning("lxml not available, HTML parsing disabled")
            return None
        return LHTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True, collect_ids=False)

    def extract_tree(self, html_text: str) -> Any:
        """Extract html tree from html text."""
        if not LXML_AVAILABLE or not self.parser:
            raise ImportError("lxml is required for HTML parsing")
        return html.fromstring(html_text, parser=self.parser)

    def pre_process_html(self, html_text: str) -> str:
        """Pre-process html_text before extracting results."""
        return html_text

    def extract_results(self, html_text: str) -> list[T]:
        """Extract search results from html text."""
        if not LXML_AVAILABLE:
            raise ImportError("lxml is required for result extraction")
        
        html_text = self.pre_process_html(html_text)
        tree = self.extract_tree(html_text)
        
        results = []
        items = tree.xpath(self.items_xpath) if self.items_xpath else []
        
        for item in items:
            result = self.result_type()
            for key, xpath in self.elements_xpath.items():
                try:
                    data = item.xpath(xpath)
                    if data:
                        # Join text nodes or get first attribute
                        value = "".join(data) if isinstance(data, list) else data
                        setattr(result, key, value.strip() if isinstance(value, str) else value)
                except Exception as ex:
                    logger.debug("Error extracting %s: %r", key, ex)
            results.append(result)
        
        return results

    def post_extract_results(self, results: list[T]) -> list[T]:
        """Post-process search results."""
        return results

    def search(
        self,
        query: str,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        page: int = 1,
        **kwargs: Any,
    ) -> list[T] | None:
        """Search the engine."""
        payload = self.build_payload(
            query=query, region=region, safesearch=safesearch, timelimit=timelimit, page=page, **kwargs
        )
        if self.search_method == "GET":
            html_text = self.request(self.search_method, self.search_url, params=payload, headers=self.search_headers)
        else:
            html_text = self.request(self.search_method, self.search_url, data=payload, headers=self.search_headers)
        if not html_text:
            return None
        results = self.extract_results(html_text)
        return self.post_extract_results(results)


# Legacy base class for backwards compatibility
class BaseSearch(ABC):
    """Base class for synchronous search engines (legacy)."""

    @abstractmethod
    def text(self, *args, **kwargs) -> list[dict[str, str]]:
        """Text search."""
        raise NotImplementedError

    @abstractmethod
    def images(self, *args, **kwargs) -> list[dict[str, str]]:
        """Images search."""
        raise NotImplementedError

    @abstractmethod
    def videos(self, *args, **kwargs) -> list[dict[str, str]]:
        """Videos search."""
        raise NotImplementedError

    @abstractmethod
    def news(self, *args, **kwargs) -> list[dict[str, str]]:
        """News search."""
        raise NotImplementedError

    @abstractmethod
    def answers(self, *args, **kwargs) -> list[dict[str, str]]:
        """Instant answers."""
        raise NotImplementedError

    @abstractmethod
    def suggestions(self, *args, **kwargs) -> list[dict[str, str]]:
        """Suggestions."""
        raise NotImplementedError

    @abstractmethod
    def maps(self, *args, **kwargs) -> list[dict[str, str]]:
        """Maps search."""
        raise NotImplementedError

    @abstractmethod
    def translate(self, *args, **kwargs) -> list[dict[str, str]]:
        """Translate."""
        raise NotImplementedError