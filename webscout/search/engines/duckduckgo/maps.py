from __future__ import annotations

from decimal import Decimal

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoMaps(DuckDuckGoBase):
    def run(self, *args, **kwargs) -> list[dict[str, str]]:
        keywords = args[0] if args else kwargs.get("keywords")
        place = args[1] if len(args) > 1 else kwargs.get("place")
        street = args[2] if len(args) > 2 else kwargs.get("street")
        city = args[3] if len(args) > 3 else kwargs.get("city")
        county = args[4] if len(args) > 4 else kwargs.get("county")
        state = args[5] if len(args) > 5 else kwargs.get("state")
        country = args[6] if len(args) > 6 else kwargs.get("country")
        postalcode = args[7] if len(args) > 7 else kwargs.get("postalcode")
        latitude = args[8] if len(args) > 8 else kwargs.get("latitude")
        longitude = args[9] if len(args) > 9 else kwargs.get("longitude")
        radius = args[10] if len(args) > 10 else kwargs.get("radius", 0)
        max_results = args[11] if len(args) > 11 else kwargs.get("max_results")

        assert keywords, "keywords is mandatory"

        vqd = self._get_vqd(keywords)

        # if longitude and latitude are specified, skip the request about bbox to the nominatim api
        if latitude and longitude:
            lat_t = Decimal(latitude.replace(",", "."))
            lat_b = Decimal(latitude.replace(",", "."))
            lon_l = Decimal(longitude.replace(",", "."))
            lon_r = Decimal(longitude.replace(",", "."))
            if radius == 0:
                radius = 1
        # otherwise request about bbox to nominatim api
        else:
            if place:
                params = {
                    "q": place,
                    "polygon_geojson": "0",
                    "format": "jsonv2",
                }
            else:
                params = {
                    "polygon_geojson": "0",
                    "format": "jsonv2",
                }
                if street:
                    params["street"] = street
                if city:
                    params["city"] = city
                if county:
                    params["county"] = county
                if state:
                    params["state"] = state
                if country:
                    params["country"] = country
                if postalcode:
                    params["postalcode"] = postalcode
            # request nominatim api to get coordinates box
            resp_content = self._get_url(
                "GET",
                "https://nominatim.openstreetmap.org/search.php",
                params=params,
            ).content
            if resp_content == b"[]":
                raise WebscoutE("maps() Coordinates are not found, check function parameters.")
            resp_json = self.json_loads(resp_content)
            coordinates = resp_json[0]["boundingbox"]
            lat_t, lon_l = Decimal(coordinates[1]), Decimal(coordinates[2])
            lat_b, lon_r = Decimal(coordinates[0]), Decimal(coordinates[3])

        # if a radius is specified, expand the search square
        lat_t += Decimal(radius) * Decimal(0.008983)
        lat_b -= Decimal(radius) * Decimal(0.008983)
        lon_l -= Decimal(radius) * Decimal(0.008983)
        lon_r += Decimal(radius) * Decimal(0.008983)

        cache = set()
        results: list[dict[str, str]] = []

        def _maps_page(
            bbox: tuple[Decimal, Decimal, Decimal, Decimal],
        ) -> list[dict[str, str]] | None:
            if max_results and len(results) >= max_results:
                return None
            lat_t, lon_l, lat_b, lon_r = bbox
            params = {
                "q": keywords,
                "vqd": vqd,
                "tg": "maps_places",
                "rt": "D",
                "mkexp": "b",
                "wiki_info": "1",
                "is_requery": "1",
                "bbox_tl": f"{lat_t},{lon_l}",
                "bbox_br": f"{lat_b},{lon_r}",
                "strict_bbox": "1",
            }
            resp_content = self._get_url("GET", "https://duckduckgo.com/local.js", params=params).content
            resp_json = self.json_loads(resp_content)
            page_data = resp_json.get("results", [])

            page_results = []
            for res in page_data:
                r_name = f'{res["name"]} {res["address"]}'
                if r_name in cache:
                    continue
                else:
                    cache.add(r_name)
                    result = {
                        "title": res["name"],
                        "address": res["address"],
                        "country_code": res["country_code"],
                        "url": self._normalize_url(res["website"]),
                        "phone": res["phone"] or "",
                        "latitude": res["coordinates"]["latitude"],
                        "longitude": res["coordinates"]["longitude"],
                        "source": self._normalize_url(res["url"]),
                        "image": x.get("image", "") if (x := res["embed"]) else "",
                        "desc": x.get("description", "") if (x := res["embed"]) else "",
                        "hours": res["hours"] or "",
                        "category": res["ddg_category"] or "",
                        "facebook": f"www.facebook.com/profile.php?id={x}" if (x := res["facebook_id"]) else "",
                        "instagram": f"https://www.instagram.com/{x}" if (x := res["instagram_id"]) else "",
                        "twitter": f"https://twitter.com/{x}" if (x := res["twitter_id"]) else "",
                    }
                    page_results.append(result)
            return page_results

        start_bbox = (lat_t, lon_l, lat_b, lon_r)
        work_bboxes = [start_bbox]
        while work_bboxes:
            queue_bboxes = []
            tasks = []
            for bbox in work_bboxes:
                tasks.append(bbox)
                if self._calculate_distance(lat_t, lon_l, lat_b, lon_r) > 1:
                    lat_t, lon_l, lat_b, lon_r = bbox
                    lat_middle = (lat_t + lat_b) / 2
                    lon_middle = (lon_l + lon_r) / 2
                    bbox1 = (lat_t, lon_l, lat_middle, lon_middle)
                    bbox2 = (lat_t, lon_middle, lat_middle, lon_r)
                    bbox3 = (lat_middle, lon_l, lat_b, lon_middle)
                    bbox4 = (lat_middle, lon_middle, lat_b, lon_r)
                    queue_bboxes.extend([bbox1, bbox2, bbox3, bbox4])

            work_bboxes_results = []
            try:
                for r in self._executor.map(_maps_page, tasks):
                    if r:
                        work_bboxes_results.extend(r)
            except Exception as e:
                raise e

            for x in work_bboxes_results:
                if isinstance(x, list):
                    results.extend(x)
                elif isinstance(x, dict):
                    results.append(x)

            work_bboxes = queue_bboxes
            if not max_results or len(results) >= max_results or len(work_bboxes_results) == 0:
                break

        return list(self.islice(results, max_results))

