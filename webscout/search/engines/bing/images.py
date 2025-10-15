"""Bing images search."""

from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from time import sleep

from .base import BingBase


class BingImagesSearch(BingBase):
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

        # Bing images URL
        url = f"{self.base_url}/images/async"
        params = {
            'q': keywords,
            'first': '1',
            'count': '35',  # Fetch more to get max_results
            'cw': '1177',
            'ch': '759',
            'tsc': 'ImageHoverTitle',
            'layout': 'RowBased_Landscape',
            't': '0',
            'IG': '',
            'SFX': '0',
            'iid': 'images.1'
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
                html = response.text
            except Exception as e:
                raise Exception(f"Failed to fetch images: {str(e)}")

            soup = BeautifulSoup(html, 'html.parser')
            img_tags = soup.select('a.iusc img')

            for img in img_tags:
                if len(results) >= max_results:
                    break

                title = img.get('alt', '')
                src = img.get('src', '')
                m_attr = img.parent.get('m', '') if img.parent else ''

                # Parse m attribute for full image URL
                image_url = src
                thumbnail = src
                if m_attr:
                    try:
                        import json
                        m_data = json.loads(m_attr)
                        image_url = m_data.get('murl', src)
                        thumbnail = m_data.get('turl', src)
                    except:
                        pass

                source = ''
                if img.parent and img.parent.parent:
                    source_tag = img.parent.parent.select_one('.iusc .lnk')
                    if source_tag:
                        source = source_tag.get_text(strip=True)

                results.append({
                    'title': title,
                    'image': image_url,
                    'thumbnail': thumbnail,
                    'url': image_url,  # For compatibility
                    'source': source
                })

            first += 35
            sfx += 1

            if self.sleep_interval:
                sleep(self.sleep_interval)

        return results[:max_results]