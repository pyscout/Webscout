import sys
from .swiftcli import CLI, option
from .webscout_search import DuckDuckGoSearch  # Import the WEBS class from webscout_search
from .DWEBS import GoogleSearch  # Import GoogleSearch from DWEBS
from .yep_search import YepSearch  # Import YepSearch from yep_search
from .version import __version__


def _print_data(data):
    """Prints data in a simple formatted way."""
    if data:
        for i, e in enumerate(data, start=1):
            print(f"\nResult {i}:")
            print("-" * 50)
            for k, v in e.items():
                if v:
                    k = "language" if k == "detected_language" else k
                    print(f"{k:15}: {v}")
            print("-" * 50)

def _print_weather(data):
    """Prints weather data in a clean format."""
    current = data["current"]
    
    print(f"\nCurrent Weather in {data['location']}:")
    print("-" * 50)
    print(f"Temperature: {current['temperature_c']}°C")
    print(f"Feels Like: {current['feels_like_c']}°C")
    print(f"Humidity: {current['humidity']}%")
    print(f"Wind: {current['wind_speed_ms']} m/s")
    print(f"Direction: {current['wind_direction']}°")
    print("-" * 50)
    
    print("\n5-Day Forecast:")
    print("-" * 50)
    print(f"{'Date':10} {'Condition':15} {'High':8} {'Low':8}")
    print("-" * 50)
    
    for day in data["daily_forecast"][:5]:
        print(f"{day['date']:10} {day['condition']:15} {day['max_temp_c']:8.1f}°C {day['min_temp_c']:8.1f}°C")
    print("-" * 50)

# Initialize CLI app
app = CLI(name="webscout", help="Search the web with a simple UI", version=__version__)

@app.command()
def version():
    """Show the version of webscout."""
    print(f"webscout version: {__version__}")



@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="wt-wt")
@option("--safesearch", "-s", help="SafeSearch setting", default="moderate")
@option("--timelimit", "-t", help="Time limit for results", default=None)
@option("--backend", "-b", help="Search backend to use", default="api")
@option("--max-results", "-m", help="Maximum number of results", type=int, default=25)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def text(keywords: str, region: str, safesearch: str, timelimit: str, backend: str, max_results: int, proxy: str = None, timeout: int = 10):
    """Perform a text search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.text(keywords, region, safesearch, timelimit, backend, max_results)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def answers(keywords: str, proxy: str = None, timeout: int = 10):
    """Perform an answers search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.answers(keywords)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="wt-wt")
@option("--safesearch", "-s", help="SafeSearch setting", default="moderate")
@option("--timelimit", "-t", help="Time limit for results", default=None)
@option("--size", "-size", help="Image size", default=None)
@option("--color", "-c", help="Image color", default=None)
@option("--type", "-type", help="Image type", default=None)
@option("--layout", "-l", help="Image layout", default=None)
@option("--license", "-lic", help="Image license", default=None)
@option("--max-results", "-m", help="Maximum number of results", type=int, default=90)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def images(
    keywords: str,
    region: str,
    safesearch: str,
    timelimit: str,
    size: str,
    color: str,
    type: str,
    layout: str,
    license: str,
    max_results: int,
    proxy: str = None,
    timeout: int = 10,
):
    """Perform an images search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.images(keywords, region, safesearch, timelimit, size, color, type, layout, license, max_results)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="wt-wt")
@option("--safesearch", "-s", help="SafeSearch setting", default="moderate")
@option("--timelimit", "-t", help="Time limit for results", default=None)
@option("--resolution", "-res", help="Video resolution", default=None)
@option("--duration", "-d", help="Video duration", default=None)
@option("--license", "-lic", help="Video license", default=None)
@option("--max-results", "-m", help="Maximum number of results", type=int, default=50)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def videos(
    keywords: str,
    region: str,
    safesearch: str,
    timelimit: str,
    resolution: str,
    duration: str,
    license: str,
    max_results: int,
    proxy: str = None,
    timeout: int = 10,
):
    """Perform a videos search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.videos(keywords, region, safesearch, timelimit, resolution, duration, license, max_results)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="wt-wt")
@option("--safesearch", "-s", help="SafeSearch setting", default="moderate")
@option("--timelimit", "-t", help="Time limit for results", default=None)
@option("--max-results", "-m", help="Maximum number of results", type=int, default=25)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def news(keywords: str, region: str, safesearch: str, timelimit: str, max_results: int, proxy: str = None, timeout: int = 10):
    """Perform a news search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.news(keywords, region, safesearch, timelimit, max_results)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--place", "-p", help="Simplified search - if set, the other parameters are not used")
@option("--street", "-s", help="House number/street")
@option("--city", "-c", help="City of search")
@option("--county", "-county", help="County of search")
@option("--state", "-state", help="State of search")
@option("--country", "-country", help="Country of search")
@option("--postalcode", "-post", help="Postal code of search")
@option("--latitude", "-lat", help="Geographic coordinate (north-south position)")
@option("--longitude", "-lon", help="Geographic coordinate (east-west position); if latitude and longitude are set, the other parameters are not used")
@option("--radius", "-r", help="Expand the search square by the distance in kilometers", type=int, default=0)
@option("--max-results", "-m", help="Number of results", type=int, default=50)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def maps(
    keywords: str,
    place: str,
    street: str,
    city: str,
    county: str,
    state: str,
    country: str,
    postalcode: str,
    latitude: str,
    longitude: str,
    radius: int,
    max_results: int,
    proxy: str = None,
    timeout: int = 10,
):
    """Perform a maps search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.maps(
            keywords,
            place,
            street,
            city,
            county,
            state,
            country,
            postalcode,
            latitude,
            longitude,
            radius,
            max_results,
        )
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Text for translation", required=True)
@option("--from", "-f", help="Language to translate from (defaults automatically)")
@option("--to", "-t", help="Language to translate to (default: 'en')", default="en")
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def translate(keywords: str, from_: str, to: str, proxy: str = None, timeout: int = 10):
    """Perform translation using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.translate(keywords, from_, to)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="wt-wt")
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def suggestions(keywords: str, region: str, proxy: str = None, timeout: int = 10):
    """Perform a suggestions search using DuckDuckGo API."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.suggestions(keywords, region)
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--location", "-l", help="Location to get weather for", required=True)
@option("--language", "-lang", help="Language code (e.g. 'en', 'es')", default="en")
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
def weather(location: str, language: str, proxy: str = None, timeout: int = 10):
    """Get weather information for a location from DuckDuckGo."""
    webs = WEBS(proxy=proxy, timeout=timeout)
    try:
        results = webs.weather(location, language)
        _print_weather(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results (ISO country code)", default="all")
@option("--safesearch", "-s", help="SafeSearch setting (on, moderate, off)", default="moderate")
@option("--max-results", "-m", help="Maximum number of results", type=int, default=10)
@option("--start-num", "-start", help="Starting position for pagination", type=int, default=0)
@option("--unique", "-u", help="Filter duplicate results", type=bool, default=True)
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--impersonate", "-i", help="Browser to impersonate", default="chrome110")
def google_text(
    keywords: str,
    region: str,
    safesearch: str,
    max_results: int,
    start_num: int,
    unique: bool,
    timeout: int = 10,
    proxy: str = None,
    impersonate: str = "chrome110"
):
    """Perform a text search using Google Search."""
    google = GoogleSearch(
        timeout=timeout,
        proxies={"https": proxy, "http": proxy} if proxy else None,
        verify=True,
        lang="en",
        sleep_interval=0.0,
        impersonate=impersonate
    )
    
    try:
        results = google.text(
            keywords=keywords,
            region=region,
            safesearch=safesearch,
            max_results=max_results,
            start_num=start_num,
            unique=unique
        )
        
        # Convert SearchResult objects to dictionaries for printing
        formatted_results = []
        for result in results:
            result_dict = {
                "title": result.title,
                "url": result.url,
                "description": result.description,
            }
            # Add any metadata to the result dictionary
            for k, v in result.metadata.items():
                result_dict[k] = v
                
            formatted_results.append(result_dict)
            
        _print_data(formatted_results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results (ISO country code)", default="all")
@option("--safesearch", "-s", help="SafeSearch setting (on, moderate, off)", default="moderate")
@option("--max-results", "-m", help="Maximum number of results", type=int, default=10)
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--impersonate", "-i", help="Browser to impersonate", default="chrome110")
def google_news(
    keywords: str,
    region: str,
    safesearch: str,
    max_results: int,
    timeout: int = 10,
    proxy: str = None,
    impersonate: str = "chrome110"
):
    """Perform a news search using Google Search."""
    google = GoogleSearch(
        timeout=timeout,
        proxies={"https": proxy, "http": proxy} if proxy else None,
        verify=True,
        lang="en",
        sleep_interval=0.0,
        impersonate=impersonate
    )
    
    try:
        results = google.news(
            keywords=keywords,
            region=region,
            safesearch=safesearch,
            max_results=max_results
        )
        
        # Convert SearchResult objects to dictionaries for printing
        formatted_results = []
        for result in results:
            result_dict = {
                "title": result.title,
                "url": result.url,
                "description": result.description,
            }
            # Add any metadata to the result dictionary
            for k, v in result.metadata.items():
                result_dict[k] = v
                
            formatted_results.append(result_dict)
            
        _print_data(formatted_results)
    except Exception as e:
        raise e

@app.command()
@option("--query", "-q", help="Search query", required=True)
@option("--region", "-r", help="Region for suggestions (ISO country code)", default="all")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=10)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--impersonate", "-i", help="Browser to impersonate", default="chrome110")
def google_suggestions(
    query: str,
    region: str,
    timeout: int = 10,
    proxy: str = None,
    impersonate: str = "chrome110"
):
    """Get search suggestions from Google Search."""
    google = GoogleSearch(
        timeout=timeout,
        proxies={"https": proxy, "http": proxy} if proxy else None,
        verify=True,
        lang="en",
        sleep_interval=0.0,
        impersonate=impersonate
    )
    
    try:
        results = google.suggestions(query=query, region=region)
        
        # Format suggestions for printing
        formatted_results = []
        for i, suggestion in enumerate(results, 1):
            formatted_results.append({"position": i, "suggestion": suggestion})
            
        _print_data(formatted_results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="all")
@option("--safesearch", "-s", help="SafeSearch setting (on, moderate, off)", default="moderate")
@option("--max-results", "-m", help="Maximum number of results", type=int, default=10)
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=20)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--impersonate", "-i", help="Browser to impersonate", default="chrome110")
def yep_text(
    keywords: str,
    region: str,
    safesearch: str,
    max_results: int,
    timeout: int = 20,
    proxy: str = None,
    impersonate: str = "chrome110"
):
    """Perform a text search using Yep Search."""
    yep = YepSearch(
        timeout=timeout,
        proxies={"https": proxy, "http": proxy} if proxy else None,
        verify=True,
        impersonate=impersonate
    )
    
    try:
        results = yep.text(
            keywords=keywords,
            region=region,
            safesearch=safesearch,
            max_results=max_results
        )
        
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--keywords", "-k", help="Search keywords", required=True)
@option("--region", "-r", help="Region for search results", default="all")
@option("--safesearch", "-s", help="SafeSearch setting (on, moderate, off)", default="moderate")
@option("--max-results", "-m", help="Maximum number of results", type=int, default=10)
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=20)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--impersonate", "-i", help="Browser to impersonate", default="chrome110")
def yep_images(
    keywords: str,
    region: str,
    safesearch: str,
    max_results: int,
    timeout: int = 20,
    proxy: str = None,
    impersonate: str = "chrome110"
):
    """Perform an image search using Yep Search."""
    yep = YepSearch(
        timeout=timeout,
        proxies={"https": proxy, "http": proxy} if proxy else None,
        verify=True,
        impersonate=impersonate
    )
    
    try:
        results = yep.images(
            keywords=keywords,
            region=region,
            safesearch=safesearch,
            max_results=max_results
        )
        
        _print_data(results)
    except Exception as e:
        raise e

@app.command()
@option("--query", "-q", help="Search query", required=True)
@option("--region", "-r", help="Region for suggestions", default="all")
@option("--timeout", "-timeout", help="Timeout value for requests", type=int, default=20)
@option("--proxy", "-p", help="Proxy URL to use for requests")
@option("--impersonate", "-i", help="Browser to impersonate", default="chrome110")
def yep_suggestions(
    query: str,
    region: str,
    timeout: int = 20,
    proxy: str = None,
    impersonate: str = "chrome110"
):
    """Get search suggestions from Yep Search."""
    yep = YepSearch(
        timeout=timeout,
        proxies={"https": proxy, "http": proxy} if proxy else None,
        verify=True,
        impersonate=impersonate
    )
    
    try:
        results = yep.suggestions(query=query, region=region)
        
        # Format suggestions for printing
        formatted_results = []
        for i, suggestion in enumerate(results, 1):
            formatted_results.append({"position": i, "suggestion": suggestion})
            
        _print_data(formatted_results)
    except Exception as e:
        raise e

def main():
    """Main entry point for the CLI."""
    try:
        app.run()
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()