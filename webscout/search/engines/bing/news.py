"""Bing news search."""

from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from time import sleep

from .base import BingBase


class BingNewsSearch(BingBase):
    def run(self, *args, **kwargs) -> List[Dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "us")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        max_results = args[3] if len(args) > 3 else kwargs.get("max_results", 10)

        if not keywords:
            raise ValueError("Keywords are mandatory")

        safe_map = {
            "on": "Strict",
            "moderate": "Moderate",
            "off": "Off"
        }
        safe = safe_map.get(safesearch.lower(), "Moderate")

        # Bing news URL
        url = f"{self.base_url}/news/infinitescrollajax"
        params = {
            'q': keywords,
            'InfiniteScroll': '1',
            'first': '1',
            'SFX': '0',
            'cc': region.lower(),
            'setlang': self.lang.split('-')[0]
        }

        results = []
        first = 1
        sfx = 0

        while len(results) < max_results:
            params['first'] = str(first)
            params['SFX'] = str(sfx)
            full_url = f"{url}?{urlencode(params)}"

            try:
                response = self.session.get(full_url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                raise Exception(f"Failed to fetch news: {str(e)}")

            html = data.get('html', '')
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')
            news_items = soup.select('div.newsitem')

            for item in news_items:
                if len(results) >= max_results:
                    break

                title = item.select_one('a.title')
                snippet = item.select_one('div.snippet')
                source = item.select_one('div.source')
                date = item.select_one('span.date')

                if title:
                    news_result = {
                        'title': title.get_text(strip=True),
                        'url': title.get('href', ''),
                        'body': snippet.get_text(strip=True) if snippet else '',
                        'source': source.get_text(strip=True) if source else '',
                        'date': date.get_text(strip=True) if date else ''
                    }
                    results.append(news_result)

            first += 10
            sfx += 1

            if self.sleep_interval:
                sleep(self.sleep_interval)

        return results[:max_results]