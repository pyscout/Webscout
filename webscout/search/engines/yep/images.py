from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlencode

from .base import YepBase


class YepImages(YepBase):
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
            "type": "images"
        }

        url = f"{self.base_url}?{urlencode(params)}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            raw_results = response.json()

            if not raw_results or len(raw_results) < 2:
                return []

            formatted_results = []
            results = raw_results[1].get('results', [])

            for result in results:
                if result.get("type") != "Image":
                    continue

                formatted_result = {
                    "title": self._remove_html_tags(result.get("title", "")),
                    "image": result.get("image_id", ""),
                    "thumbnail": result.get("src", ""),
                    "url": result.get("host_page", ""),
                    "height": result.get("height", 0),
                    "width": result.get("width", 0),
                    "source": result.get("visual_url", "")
                }

                if "srcset" in result:
                    formatted_result["thumbnail_hd"] = result["srcset"].split(",")[1].strip().split(" ")[0]

                formatted_results.append(formatted_result)

            if max_results:
                return formatted_results[:max_results]
            return formatted_results

        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                 raise Exception(f"Yep image search failed with status {e.response.status_code}: {str(e)}")
            else:
                 raise Exception(f"Yep image search failed: {str(e)}")

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

