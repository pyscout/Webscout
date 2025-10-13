from __future__ import annotations

from datetime import datetime, timezone

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoNews(DuckDuckGoBase):
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "wt-wt")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        timelimit = args[3] if len(args) > 3 else kwargs.get("timelimit")
        max_results = args[4] if len(args) > 4 else kwargs.get("max_results")

        assert keywords, "keywords is mandatory"

        vqd = self._get_vqd(keywords)

        safesearch_base = {"on": "1", "moderate": "-1", "off": "-2"}
        payload = {
            "l": region,
            "o": "json",
            "noamp": "1",
            "q": keywords,
            "vqd": vqd,
            "p": safesearch_base[safesearch.lower()],
        }
        if timelimit:
            payload["df"] = timelimit

        cache = set()
        results: list[dict[str, str]] = []

        def _news_page(s: int) -> list[dict[str, str]]:
            payload["s"] = f"{s}"
            resp_content = self._get_url("GET", "https://duckduckgo.com/news.js", params=payload).content
            resp_json = self.json_loads(resp_content)
            page_data = resp_json.get("results", [])
            page_results = []
            for row in page_data:
                if row["url"] not in cache:
                    cache.add(row["url"])
                    image_url = row.get("image", None)
                    result = {
                        "date": datetime.fromtimestamp(row["date"], timezone.utc).isoformat(),
                        "title": row["title"],
                        "body": self._normalize(row["excerpt"]),
                        "url": self._normalize_url(row["url"]),
                        "image": self._normalize_url(image_url),
                        "source": row["source"],
                    }
                    page_results.append(result)
            return page_results

        slist = [0]
        if max_results:
            max_results = min(max_results, 120)
            slist.extend(range(30, max_results, 30))
        try:
            for r in self._executor.map(_news_page, slist):
                results.extend(r)
        except Exception as e:
            raise e

        return list(self.islice(results, max_results))

