"""DuckDuckGo answers search."""

from __future__ import annotations

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoAnswers(DuckDuckGoBase):
    """DuckDuckGo instant answers."""
    
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        """Get instant answers from DuckDuckGo.
        
        Args:
            keywords: Search query.
            
        Returns:
            List of answer dictionaries.
        """
        keywords = args[0] if args else kwargs.get("keywords")

        assert keywords, "keywords is mandatory"

        payload = {
            "q": f"what is {keywords}",
            "format": "json",
        }
        resp_content = self._get_url("GET", "https://api.duckduckgo.com/", params=payload).content
        page_data = self.json_loads(resp_content)

        results = []
        answer = page_data.get("AbstractText")
        url = page_data.get("AbstractURL")
        if answer:
            results.append(
                {
                    "icon": None,
                    "text": answer,
                    "topic": None,
                    "url": url,
                }
            )

        # related
        payload = {
            "q": f"{keywords}",
            "format": "json",
        }
        resp_content = self._get_url("GET", "https://api.duckduckgo.com/", params=payload).content
        resp_json = self.json_loads(resp_content)
        page_data = resp_json.get("RelatedTopics", [])

        for row in page_data:
            topic = row.get("Name")
            if not topic:
                icon = row["Icon"].get("URL")
                results.append(
                    {
                        "icon": f"https://duckduckgo.com{icon}" if icon else "",
                        "text": row["Text"],
                        "topic": None,
                        "url": row["FirstURL"],
                    }
                )
            else:
                for subrow in row["Topics"]:
                    icon = subrow["Icon"].get("URL")
                    results.append(
                        {
                            "icon": f"https://duckduckgo.com{icon}" if icon else "",
                            "text": subrow["Text"],
                            "topic": topic,
                            "url": subrow["FirstURL"],
                        }
                    )

        return results
