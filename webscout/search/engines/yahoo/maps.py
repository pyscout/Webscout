"""Yahoo maps search."""

from __future__ import annotations

from .base import YahooSearchEngine


class YahooMaps(YahooSearchEngine):
    """Yahoo maps search."""

    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        """Get maps results from Yahoo.

        Not supported.
        """
        raise NotImplementedError("Yahoo does not support maps search")