"""Yahoo weather search using embedded JSON data."""

from __future__ import annotations

import re
import json
from typing import Any

from ...http_client import HttpClient


class YahooWeather:
    """Yahoo weather search using embedded JSON extraction."""

    def __init__(self, proxy: str | None = None, timeout: int | None = None, verify: bool = True):
        """Initialize weather search engine.
        
        Args:
            proxy: Proxy URL.
            timeout: Request timeout in seconds.
            verify: Whether to verify SSL certificates.
        """
        self.http_client = HttpClient(proxy=proxy, timeout=timeout, verify=verify)

    def request(self, method: str, url: str, **kwargs: Any) -> str | None:
        """Make a request to the weather service."""
        try:
            response = self.http_client.request(method, url, **kwargs)
            return response.text
        except Exception:
            return None

    def run(self, *args, **kwargs) -> list[dict[str, Any]]:
        """Get weather data from Yahoo.
        
        Args:
            location: Location to get weather for (e.g., "New York", "London", "Bengaluru")
            
        Returns:
            List of weather data dictionaries
        """
        location = args[0] if args else kwargs.get("location") or kwargs.get("keywords")
        
        if not location:
            raise ValueError("Location is required for weather search")
        
        try:
            # Use the search endpoint which redirects to the correct weather page
            search_url = f"https://weather.yahoo.com/search/?q={location.replace(' ', '+')}"
            
            # Fetch the page
            response = self.request("GET", search_url)
            if not response:
                return [{
                    "location": location,
                    "error": "Failed to fetch weather data from Yahoo"
                }]
            
            # Extract JSON data from the page
            weather_data = self._extract_json_data(response, location)
            
            if weather_data:
                return [weather_data]
            
            # Fallback: try regex parsing
            return self._parse_weather_html(response, location)
            
        except Exception as e:
            return [{
                "location": location,
                "error": f"Failed to fetch weather data: {str(e)}"
            }]
    
    def _extract_json_data(self, html: str, location: str) -> dict[str, Any] | None:
        """Extract weather data from embedded JSON in the page.
        
        Yahoo Weather embeds JSON data in script tags that can be parsed.
        """
        try:
            # Look for the main data script tag
            # Pattern: self.__next_f.push([1,"..JSON data.."])
            json_pattern = r'self\.__next_f\.push\(\[1,"([^"]+)"\]\)'
            matches = re.findall(json_pattern, html)
            
            weather_info = {}
            
            for match in matches:
                # Unescape the JSON string
                try:
                    # The data is escaped, so we need to decode it
                    decoded = match.encode().decode('unicode_escape')
                    
                    # Look for temperature data
                    temp_match = re.search(r'"temperature":(\d+)', decoded)
                    if temp_match and not weather_info.get('temperature'):
                        weather_info['temperature'] = int(temp_match.group(1))
                    
                    # Look for condition
                    condition_match = re.search(r'"iconLabel":"([^"]+)"', decoded)
                    if condition_match and not weather_info.get('condition'):
                        weather_info['condition'] = condition_match.group(1)
                    
                    # Look for high/low
                    high_match = re.search(r'"highTemperature":(\d+)', decoded)
                    if high_match and not weather_info.get('high'):
                        weather_info['high'] = int(high_match.group(1))
                    
                    low_match = re.search(r'"lowTemperature":(\d+)', decoded)
                    if low_match and not weather_info.get('low'):
                        weather_info['low'] = int(low_match.group(1))
                    
                    # Look for humidity
                    humidity_match = re.search(r'"value":"(\d+)%"[^}]*"category":"Humidity"', decoded)
                    if humidity_match and not weather_info.get('humidity'):
                        weather_info['humidity'] = int(humidity_match.group(1))
                    
                    # Look for precipitation probability
                    precip_match = re.search(r'"probabilityOfPrecipitation":"(\d+)%"', decoded)
                    if precip_match and not weather_info.get('precipitation_chance'):
                        weather_info['precipitation_chance'] = int(precip_match.group(1))
                    
                    # Look for location name
                    location_match = re.search(r'"name":"([^"]+)","code":null,"woeid":(\d+)', decoded)
                    if location_match and not weather_info.get('location_name'):
                        weather_info['location_name'] = location_match.group(1)
                        weather_info['woeid'] = int(location_match.group(2))
                    
                except Exception:
                    continue
            
            if weather_info and weather_info.get('temperature'):
                return {
                    "location": weather_info.get('location_name', location),
                    "woeid": weather_info.get('woeid'),
                    "temperature_f": weather_info.get('temperature'),
                    "condition": weather_info.get('condition'),
                    "high_f": weather_info.get('high'),
                    "low_f": weather_info.get('low'),
                    "humidity_percent": weather_info.get('humidity'),
                    "precipitation_chance": weather_info.get('precipitation_chance'),
                    "source": "Yahoo Weather",
                    "units": "Fahrenheit"
                }
            
            return None
            
        except Exception as e:
            return None
    
    def _parse_weather_html(self, html_content: str, location: str) -> list[dict[str, Any]]:
        """Fallback: Parse weather data from HTML content using regex.
        
        Args:
            html_content: HTML content of weather page
            location: Location name
            
        Returns:
            List of weather data dictionaries
        """
        try:
            weather_data = {"location": location}
            
            # Extract current temperature
            temp_patterns = [
                r'<p[^>]*class="[^"]*font-title1[^"]*"[^>]*>(\d+)°</p>',
                r'>(\d+)°<',
                r'"temperature":(\d+)',
            ]
            
            for pattern in temp_patterns:
                match = re.search(pattern, html_content)
                if match:
                    weather_data["temperature_f"] = int(match.group(1))
                    break
            
            # Extract condition
            condition_patterns = [
                r'"iconLabel":"([^"]+)"',
                r'aria-label="([^"]*(?:Cloudy|Sunny|Rain|Clear|Thunder|Shower|Fog)[^"]*)"',
            ]
            
            for pattern in condition_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    weather_data["condition"] = match.group(1)
                    break
            
            # Extract high/low
            high_match = re.search(r'"highTemperature":(\d+)', html_content)
            if high_match:
                weather_data["high_f"] = int(high_match.group(1))
            
            low_match = re.search(r'"lowTemperature":(\d+)', html_content)
            if low_match:
                weather_data["low_f"] = int(low_match.group(1))
            
            # Extract humidity
            humidity_match = re.search(r'Humidity[^>]*>(\d+)%|"value":"(\d+)%"[^}]*"Humidity"', html_content, re.IGNORECASE)
            if humidity_match:
                weather_data["humidity_percent"] = int(humidity_match.group(1) or humidity_match.group(2))
            
            weather_data["source"] = "Yahoo Weather"
            weather_data["units"] = "Fahrenheit"
            
            # Remove None values
            weather_data = {k: v for k, v in weather_data.items() if v is not None}
            
            if len(weather_data) > 3:  # Has more than just location, source, and units
                return [weather_data]
            
            return [{
                "location": location,
                "error": "Could not extract weather data from page"
            }]
            
        except Exception as e:
            return [{
                "location": location,
                "error": f"Failed to parse weather data: {str(e)}"
            }]
