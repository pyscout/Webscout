from __future__ import annotations

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoTranslate(DuckDuckGoBase):
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        from_ = args[1] if len(args) > 1 else kwargs.get("from_")
        to = args[2] if len(args) > 2 else kwargs.get("to", "en")

        assert keywords, "keywords is mandatory"

        vqd = self._get_vqd("translate")

        payload = {
            "vqd": vqd,
            "query": "translate",
            "to": to,
        }
        if from_:
            payload["from"] = from_

        def _translate_keyword(keyword: str) -> dict[str, str]:
            resp_content = self._get_url(
                "POST",
                "https://duckduckgo.com/translation.js",
                params=payload,
                content=keyword.encode(),
            ).content
            page_data: dict[str, str] = self.json_loads(resp_content)
            page_data["original"] = keyword
            return page_data

        if isinstance(keywords, str):
            keywords = [keywords]

        results = []
        try:
            for r in self._executor.map(_translate_keyword, keywords):
                results.append(r)
        except Exception as e:
            raise e

        return results

