"""Bing text search."""

from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from time import sleep

from .base import BingBase


class BingTextSearch(BingBase):
    def run(self, *args, **kwargs) -> List[Dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        region = args[1] if len(args) > 1 else kwargs.get("region", "us")
        safesearch = args[2] if len(args) > 2 else kwargs.get("safesearch", "moderate")
        max_results = args[3] if len(args) > 3 else kwargs.get("max_results", 10)
        unique = kwargs.get("unique", True)

        if not keywords:
            raise ValueError("Keywords are mandatory")

        safe_map = {
            "on": "Strict",
            "moderate": "Moderate",
            "off": "Off"
        }
        safe = safe_map.get(safesearch.lower(), "Moderate")

        fetched_results = []
        fetched_links = set()

        def fetch_page(url):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except Exception as e:
                raise Exception(f"Failed to fetch page: {str(e)}")

        # Get first page URL
        url = f'{self.base_url}/search?q={keywords}&search=&form=QBLH'
        urls_to_fetch = [url]

        while len(fetched_results) < max_results and urls_to_fetch:
            current_url = urls_to_fetch.pop(0)
            html = fetch_page(current_url)
            soup = BeautifulSoup(html, 'html.parser')

            links = soup.select('ol#b_results > li.b_algo')
            for link in links:
                if len(fetched_results) >= max_results:
                    break
                title_tag = link.select_one('h2')
                url_tag = link.select_one('h2 a')
                text_tag = link.select_one('p')

                if title_tag and url_tag and text_tag:
                    title = title_tag.get_text(strip=True)
                    href = url_tag.get('href', '')
                    body = text_tag.get_text(strip=True)

                    # Decode Bing URL if needed
                    if href.startswith('/ck/a?'):
                        # Simple unwrap, similar to bing.py
                        from urllib.parse import parse_qs, urlparse
                        try:
                            parsed = urlparse(href)
                            query_params = parse_qs(parsed.query)
                            if 'u' in query_params:
                                encoded_url = query_params['u'][0]
                                if encoded_url.startswith('a1'):
                                    encoded_url = encoded_url[2:]
                                padding = len(encoded_url) % 4
                                if padding:
                                    encoded_url += '=' * (4 - padding)
                                import base64
                                decoded = base64.urlsafe_b64decode(encoded_url).decode()
                                href = decoded
                        except:
                            pass

                    if unique and href in fetched_links:
                        continue
                    fetched_links.add(href)

                    fetched_results.append({
                        'title': title,
                        'href': href,
                        'body': body
                    })

            # Get next page
            next_page_tag = soup.select_one('div#b_content nav[role="navigation"] a.sb_pagN')
            if next_page_tag and next_page_tag.get('href'):
                next_url = self.base_url + next_page_tag['href']
                urls_to_fetch.append(next_url)

            if self.sleep_interval:
                sleep(self.sleep_interval)

        return fetched_results[:max_results]