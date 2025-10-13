"""DuckDuckGo text search."""

from __future__ import annotations

import warnings
from random import shuffle

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoTextSearch(DuckDuckGoBase):
    """DuckDuckGo text/web search."""
    
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        """Perform text search on DuckDuckGo.
        
        Args:
            keywords: Search query.
            region: Region code (e.g., wt-wt, us-en).
            safesearch: on, moderate, or off.
            timelimit: d, w, m, or y.
            backend: html, lite, or auto.
            max_results: Maximum number of results.
            
        Returns:
            List of search result dictionaries.
        """
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "wt-wt")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        timelimit = args[3] if len(args) > 3 else kwargs.get("timelimit")
        backend = args[4] if len(args) > 4 else kwargs.get("backend", "auto")
        max_results = args[5] if len(args) > 5 else kwargs.get("max_results")

        if backend in ("api", "ecosia"):
            warnings.warn(f"{backend=} is deprecated, using backend='auto'", stacklevel=2)
            backend = "auto"
        backends = ["html", "lite"] if backend == "auto" else [backend]
        shuffle(backends)

        results, err = [], None
        for b in backends:
            try:
                if b == "html":
                    results = self._text_html(keywords, region, timelimit, max_results)
                elif b == "lite":
                    results = self._text_lite(keywords, region, timelimit, max_results)
                return results
            except Exception as ex:
                err = ex

        raise WebscoutE(err)

    def _text_html(
        self,
        keywords: str,
        region: str = "wt-wt",
        timelimit: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, str]]:
        """Text search using HTML backend."""
        assert keywords, "keywords is mandatory"

        payload = {
            "q": keywords,
            "s": "0",
            "o": "json",
            "api": "d.js",
            "vqd": "",
            "kl": region,
            "bing_market": region,
        }
        if timelimit:
            payload["df"] = timelimit
        if max_results and max_results > 20:
            vqd = self._get_vqd(keywords)
            payload["vqd"] = vqd

        cache = set()
        results: list[dict[str, str]] = []

        def _text_html_page(s: int) -> list[dict[str, str]]:
            payload["s"] = f"{s}"
            resp_content = self._get_url("POST", "https://html.duckduckgo.com/html", data=payload).content
            if b"No  results." in resp_content:
                return []

            page_results = []
            tree = self.parser.fromstring(resp_content)
            elements = tree.xpath("//div[h2]")
            if not isinstance(elements, list):
                return []
            for e in elements:
                if isinstance(e, self.parser.etree.Element):
                    hrefxpath = e.xpath("./a/@href")
                    href = str(hrefxpath[0]) if hrefxpath and isinstance(hrefxpath, list) else None
                    if (
                        href
                        and href not in cache
                        and not href.startswith(
                            ("http://www.google.com/search?q=", "https://duckduckgo.com/y.js?ad_domain")
                        )
                    ):
                        cache.add(href)
                        titlexpath = e.xpath("./h2/a/text()")
                        title = str(titlexpath[0]) if titlexpath and isinstance(titlexpath, list) else ""
                        bodyxpath = e.xpath("./a//text()")
                        body = "".join(str(x) for x in bodyxpath) if bodyxpath and isinstance(bodyxpath, list) else ""
                        result = {
                            "title": self._normalize(title),
                            "href": self._normalize_url(href),
                            "body": self._normalize(body),
                        }
                        page_results.append(result)
            return page_results

        slist = [0]
        if max_results:
            max_results = min(max_results, 2023)
            slist.extend(range(23, max_results, 50))
        try:
            for r in self._executor.map(_text_html_page, slist):
                results.extend(r)
        except Exception as e:
            raise e

        return list(self.islice(results, max_results))

    def _text_lite(
        self,
        keywords: str,
        region: str = "wt-wt",
        timelimit: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, str]]:
        """Text search using lite backend."""
        assert keywords, "keywords is mandatory"

        payload = {
            "q": keywords,
            "s": "0",
            "o": "json",
            "api": "d.js",
            "vqd": "",
            "kl": region,
            "bing_market": region,
        }
        if timelimit:
            payload["df"] = timelimit

        cache = set()
        results: list[dict[str, str]] = []

        def _text_lite_page(s: int) -> list[dict[str, str]]:
            payload["s"] = f"{s}"
            resp_content = self._get_url("POST", "https://lite.duckduckgo.com/lite/", data=payload).content
            if b"No more results." in resp_content:
                return []

            page_results = []
            tree = self.parser.fromstring(resp_content)
            elements = tree.xpath("//table[last()]//tr")
            if not isinstance(elements, list):
                return []

            data = zip(self.cycle(range(1, 5)), elements)
            for i, e in data:
                if isinstance(e, self.parser.etree.Element):
                    if i == 1:
                        hrefxpath = e.xpath(".//a//@href")
                        href = str(hrefxpath[0]) if hrefxpath and isinstance(hrefxpath, list) else None
                        if (
                            href is None
                            or href in cache
                            or href.startswith(
                                ("http://www.google.com/search?q=", "https://duckduckgo.com/y.js?ad_domain")
                            )
                        ):
                            [next(data, None) for _ in range(3)]  # skip block(i=1,2,3,4)
                        else:
                            cache.add(href)
                            titlexpath = e.xpath(".//a//text()")
                            title = str(titlexpath[0]) if titlexpath and isinstance(titlexpath, list) else ""
                    elif i == 2:
                        bodyxpath = e.xpath(".//td[@class='result-snippet']//text()")
                        body = (
                            "".join(str(x) for x in bodyxpath).strip()
                            if bodyxpath and isinstance(bodyxpath, list)
                            else ""
                        )
                        if href:
                            result = {
                                "title": self._normalize(title),
                                "href": self._normalize_url(href),
                                "body": self._normalize(body),
                            }
                            page_results.append(result)
            return page_results

        slist = [0]
        if max_results:
            max_results = min(max_results, 2023)
            slist.extend(range(23, max_results, 50))
        try:
            for r in self._executor.map(_text_lite_page, slist):
                results.extend(r)
        except Exception as e:
            raise e

        return list(self.islice(results, max_results))
