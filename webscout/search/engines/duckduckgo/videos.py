from __future__ import annotations

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoVideos(DuckDuckGoBase):
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "wt-wt")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        timelimit = args[3] if len(args) > 3 else kwargs.get("timelimit")
        resolution = args[4] if len(args) > 4 else kwargs.get("resolution")
        duration = args[5] if len(args) > 5 else kwargs.get("duration")
        license_videos = args[6] if len(args) > 6 else kwargs.get("license_videos")
        max_results = args[7] if len(args) > 7 else kwargs.get("max_results")

        assert keywords, "keywords is mandatory"

        vqd = self._get_vqd(keywords)

        safesearch_base = {"on": "1", "moderate": "-1", "off": "-2"}
        timelimit = f"publishedAfter:{timelimit}" if timelimit else ""
        resolution = f"videoDefinition:{resolution}" if resolution else ""
        duration = f"videoDuration:{duration}" if duration else ""
        license_videos = f"videoLicense:{license_videos}" if license_videos else ""
        payload = {
            "l": region,
            "o": "json",
            "q": keywords,
            "vqd": vqd,
            "f": f"{timelimit},{resolution},{duration},{license_videos}",
            "p": safesearch_base[safesearch.lower()],
        }

        cache = set()
        results: list[dict[str, str]] = []

        def _videos_page(s: int) -> list[dict[str, str]]:
            payload["s"] = f"{s}"
            resp_content = self._get_url("GET", "https://duckduckgo.com/v.js", params=payload).content
            resp_json = self.json_loads(resp_content)

            page_data = resp_json.get("results", [])
            page_results = []
            for row in page_data:
                if row["content"] not in cache:
                    cache.add(row["content"])
                    page_results.append(row)
            return page_results

        slist = [0]
        if max_results:
            max_results = min(max_results, 400)
            slist.extend(range(60, max_results, 60))
        try:
            for r in self._executor.map(_videos_page, slist):
                results.extend(r)
        except Exception as e:
            raise e

        return list(self.islice(results, max_results))

