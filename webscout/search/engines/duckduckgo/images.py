"""DuckDuckGo image search."""

from __future__ import annotations

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoImages(DuckDuckGoBase):
    """DuckDuckGo image search."""
    
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        """Perform image search on DuckDuckGo.
        
        Args:
            keywords: Search query.
            region: Region code.
            safesearch: on, moderate, or off.
            timelimit: d, w, m, or y.
            size: Small, Medium, Large, Wallpaper.
            color: color name or Monochrome.
            type_image: photo, clipart, gif, transparent, line.
            layout: Square, Tall, Wide.
            license_image: any, Public, Share, etc.
            max_results: Maximum number of results.
            
        Returns:
            List of image result dictionaries.
        """
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "wt-wt")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        timelimit = args[3] if len(args) > 3 else kwargs.get("timelimit")
        size = args[4] if len(args) > 4 else kwargs.get("size")
        color = args[5] if len(args) > 5 else kwargs.get("color")
        type_image = args[6] if len(args) > 6 else kwargs.get("type_image")
        layout = args[7] if len(args) > 7 else kwargs.get("layout")
        license_image = args[8] if len(args) > 8 else kwargs.get("license_image")
        max_results = args[9] if len(args) > 9 else kwargs.get("max_results")

        assert keywords, "keywords is mandatory"

        vqd = self._get_vqd(keywords)

        safesearch_base = {"on": "1", "moderate": "1", "off": "-1"}
        timelimit = f"time:{timelimit}" if timelimit else ""
        size = f"size:{size}" if size else ""
        color = f"color:{color}" if color else ""
        type_image = f"type:{type_image}" if type_image else ""
        layout = f"layout:{layout}" if layout else ""
        license_image = f"license:{license_image}" if license_image else ""
        payload = {
            "l": region,
            "o": "json",
            "q": keywords,
            "vqd": vqd,
            "f": f"{timelimit},{size},{color},{type_image},{layout},{license_image}",
            "p": safesearch_base[safesearch.lower()],
        }

        cache = set()
        results: list[dict[str, str]] = []

        def _images_page(s: int) -> list[dict[str, str]]:
            payload["s"] = f"{s}"
            resp_content = self._get_url("GET", "https://duckduckgo.com/i.js", params=payload).content
            resp_json = self.json_loads(resp_content)

            page_data = resp_json.get("results", [])
            page_results = []
            for row in page_data:
                image_url = row.get("image")
                if image_url and image_url not in cache:
                    cache.add(image_url)
                    result = {
                        "title": row["title"],
                        "image": self._normalize_url(image_url),
                        "thumbnail": self._normalize_url(row["thumbnail"]),
                        "url": self._normalize_url(row["url"]),
                        "height": row["height"],
                        "width": row["width"],
                        "source": row["source"],
                    }
                    page_results.append(result)
            return page_results

        slist = [0]
        if max_results:
            max_results = min(max_results, 500)
            slist.extend(range(100, max_results, 100))
        try:
            for r in self._executor.map(_images_page, slist):
                results.extend(r)
        except Exception as e:
            raise e

        return list(self.islice(results, max_results))
