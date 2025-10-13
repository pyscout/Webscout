from __future__ import annotations

from typing import List
from urllib.parse import urlencode

from .base import YepBase


class YepSuggestions(YepBase):
    def run(self, *args, **kwargs) -> List[str]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "all")

        params = {
            "query": keywords,
            "type": "web",
            "gl": region
        }

        url = f"https://api.yep.com/ac/?{urlencode(params)}"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                return data[1]
            return []

        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                 raise Exception(f"Yep suggestions failed with status {e.response.status_code}: {str(e)}")
            else:
                 raise Exception(f"Yep suggestions failed: {str(e)}")

