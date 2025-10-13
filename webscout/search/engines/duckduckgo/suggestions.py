from __future__ import annotations

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoSuggestions(DuckDuckGoBase):
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "wt-wt")

        assert keywords, "keywords is mandatory"

        payload = {
            "q": keywords,
            "kl": region,
        }
        resp_content = self._get_url("GET", "https://duckduckgo.com/ac/", params=payload).content
        page_data = self.json_loads(resp_content)
        return [r for r in page_data]

