from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlencode

from .base import YepBase


class YepSearch(YepBase):
    def run(self, *args, **kwargs) -> List[Dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "all")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        max_results = args[3] if len(args) > 3 else kwargs.get("max_results")

        safe_search_map = {
            "on": "on",
            "moderate": "moderate",
            "off": "off"
        }
        safe_setting = safe_search_map.get(safesearch.lower(), "moderate")

        params = {
            "client": "web",
            "gl": region,
            "limit": str(max_results) if max_results else "10",
            "no_correct": "false",
            "q": keywords,
            "safeSearch": safe_setting,
            "type": "web"
        }

        url = f"{self.base_url}?{urlencode(params)}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            raw_results = response.json()

            formatted_results = self.format_results(raw_results)

            if max_results:
                return formatted_results[:max_results]
            return formatted_results
        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                 raise Exception(f"Yep search failed with status {e.response.status_code}: {str(e)}")
            else:
                 raise Exception(f"Yep search failed: {str(e)}")

    def format_results(self, raw_results: dict) -> List[Dict]:
        formatted_results = []

        if not raw_results or len(raw_results) < 2:
            return formatted_results

        results = raw_results[1].get('results', [])

        for result in results:
            formatted_result = {
                "title": self._remove_html_tags(result.get("title", "")),
                "href": result.get("url", ""),
                "body": self._remove_html_tags(result.get("snippet", "")),
                "source": result.get("visual_url", ""),
                "position": len(formatted_results) + 1,
                "type": result.get("type", "organic"),
                "first_seen": result.get("first_seen", None)
            }

            if "sitelinks" in result:
                sitelinks = []
                if "full" in result["sitelinks"]:
                    sitelinks.extend(result["sitelinks"]["full"])
                if "short" in result["sitelinks"]:
                    sitelinks.extend(result["sitelinks"]["short"])

                if sitelinks:
                    formatted_result["sitelinks"] = [
                        {
                            "title": self._remove_html_tags(link.get("title", "")),
                            "href": link.get("url", "")
                        }
                        for link in sitelinks
                    ]

            formatted_results.append(formatted_result)

        return formatted_results

    def _remove_html_tags(self, text: str) -> str:
        result = ""
        in_tag = False

        for char in text:
            if char == '<':
                in_tag = True
            elif char == '>':
                in_tag = False
            elif not in_tag:
                result += char

        replacements = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
        }

        for entity, replacement in replacements.items():
            result = result.replace(entity, replacement)

        return result.strip()

