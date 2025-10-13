from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import quote

from ....exceptions import WebscoutE
from .base import DuckDuckGoBase


class DuckDuckGoWeather(DuckDuckGoBase):
    def run(self, *args, **kwargs) -> dict[str, any]:
        location = args[0] if args else kwargs.get("location")
        language = args[1] if len(args) > 1 else kwargs.get("language", "en")

        assert location, "location is mandatory"
        lang = language.split('-')[0]
        url = f"https://duckduckgo.com/js/spice/forecast/{quote(location)}/{lang}"

        resp = self._get_url("GET", url).content
        resp_text = resp.decode('utf-8')

        if "ddg_spice_forecast(" not in resp_text:
            raise WebscoutE(f"No weather data found for {location}")

        json_text = resp_text[resp_text.find('(') + 1:resp_text.rfind(')')]
        try:
            result = json.loads(json_text)
        except Exception as e:
            raise WebscoutE(f"Error parsing weather JSON: {e}")

        if not result or 'currentWeather' not in result or 'forecastDaily' not in result:
            raise WebscoutE(f"Invalid weather data format for {location}")

        formatted_data = {
            "location": result["currentWeather"]["metadata"].get("ddg-location", "Unknown"),
            "current": {
                "condition": result["currentWeather"].get("conditionCode"),
                "temperature_c": result["currentWeather"].get("temperature"),
                "feels_like_c": result["currentWeather"].get("temperatureApparent"),
                "humidity": result["currentWeather"].get("humidity"),
                "wind_speed_ms": result["currentWeather"].get("windSpeed"),
                "wind_direction": result["currentWeather"].get("windDirection"),
                "visibility_m": result["currentWeather"].get("visibility"),
            },
            "daily_forecast": [],
            "hourly_forecast": []
        }

        for day in result["forecastDaily"]["days"]:
            formatted_data["daily_forecast"].append({
                "date": datetime.fromisoformat(day["forecastStart"].replace("Z", "+00:00")).strftime("%Y-%m-%d"),
                "condition": day["daytimeForecast"].get("conditionCode"),
                "max_temp_c": day["temperatureMax"],
                "min_temp_c": day["temperatureMin"],
                "sunrise": datetime.fromisoformat(day["sunrise"].replace("Z", "+00:00")).strftime("%H:%M"),
                "sunset": datetime.fromisoformat(day["sunset"].replace("Z", "+00:00")).strftime("%H:%M"),
            })

        if 'forecastHourly' in result and 'hours' in result['forecastHourly']:
            for hour in result['forecastHourly']['hours']:
                formatted_data["hourly_forecast"].append({
                    "time": datetime.fromisoformat(hour["forecastStart"].replace("Z", "+00:00")).strftime("%H:%M"),
                    "condition": hour.get("conditionCode"),
                    "temperature_c": hour.get("temperature"),
                    "feels_like_c": hour.get("temperatureApparent"),
                    "humidity": hour.get("humidity"),
                    "wind_speed_ms": hour.get("windSpeed"),
                    "wind_direction": hour.get("windDirection"),
                    "visibility_m": hour.get("visibility"),
                })

        return formatted_data

