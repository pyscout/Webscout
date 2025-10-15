# Webscout Search Documentation

## Overview

Webscout provides comprehensive access to multiple search engines through a unified, easy-to-use API. The search module supports various search engines including DuckDuckGo, Yep, and individual engines like Bing, Brave, Yahoo, Yandex, Wikipedia, and more.

## Quick Start

```python
from webscout import DuckDuckGoSearch, YepSearch

# DuckDuckGo Search
ddg = DuckDuckGoSearch()
results = ddg.text("python programming", max_results=5)

# Yep Search
yep = YepSearch()
results = yep.text("web development", max_results=5)
```

## Search Engines

### DuckDuckGo Search (DuckDuckGoSearch)

DuckDuckGo offers privacy-focused search with comprehensive features across multiple categories.

#### Features
- **Privacy-focused**: No tracking or personalized results
- **Comprehensive search types**: Text, images, videos, news, maps, translations, suggestions, weather
- **Advanced filtering**: Region, SafeSearch, time limits
- **Context manager support**: Proper resource management

#### Basic Usage

```python
from webscout import DuckDuckGoSearch

# Initialize DuckDuckGo search
ddg = DuckDuckGoSearch()

# Simple text search
results = ddg.text("python programming", max_results=5)
for result in results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['href']}")
    print(f"Description: {result['body']}")
```

#### Available Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `text()` | General web search | `keywords`, `region`, `safesearch`, `timelimit`, `max_results` |
| `answers()` | Instant answers | `keywords` |
| `images()` | Image search | `keywords`, `region`, `safesearch`, `timelimit`, `max_results` |
| `videos()` | Video search | `keywords`, `region`, `safesearch`, `timelimit`, `max_results` |
| `news()` | News articles | `keywords`, `region`, `safesearch`, `timelimit`, `max_results` |
| `maps()` | Location search | `keywords`, `place`, `street`, `city`, `county`, `state`, `country`, `postalcode`, `latitude`, `longitude`, `radius`, `max_results` |
| `translate()` | Text translation | `keywords`, `from_lang`, `to_lang` |
| `suggestions()` | Search suggestions | `keywords`, `region` |
| `weather()` | Weather information | `location`, `language` |

#### Advanced Examples

##### Text Search with Filters

```python
results = ddg.text(
    keywords="artificial intelligence",
    region="wt-wt",           # Region code
    safesearch="moderate",    # "on", "moderate", "off"
    timelimit="y",            # "d"=day, "w"=week, "m"=month, "y"=year
    max_results=10
)
```

##### News Search

```python
news_results = ddg.news(
    keywords="technology trends",
    region="wt-wt",
    safesearch="moderate",
    timelimit="w",  # Last week
    max_results=20
)

for item in news_results:
    print(f"Title: {item['title']}")
    print(f"Date: {item['date']}")
    print(f"Source: {item['url']}")
    print(f"Summary: {item['body']}")
```

##### Weather Information

```python
weather = ddg.weather("New York")
if weather:
    print(f"Location: {weather['location']}")
    print(f"Temperature: {weather['current']['temperature_c']}°C")
    print(f"Condition: {weather['current']['condition']}")
```

##### Maps Search

```python
maps_results = ddg.maps(
    keywords="restaurants",
    place="new york",
    max_results=30
)
```

### Yep Search (YepSearch)

Yep.com provides fast, privacy-focused search results with a clean interface and multiple content types.

#### Features
- **Privacy-focused**: Alternative to mainstream search engines
- **Fast responses**: Optimized for speed
- **Multiple content types**: Text and images
- **Search suggestions**: Autocomplete functionality

#### Basic Usage

```python
from webscout import YepSearch

# Initialize YepSearch
yep = YepSearch()

# Text Search
text_results = yep.text(
    keywords="artificial intelligence",
    region="all",           # Optional: Region for results
    safesearch="moderate",  # Optional: "on", "moderate", "off"
    max_results=10          # Optional: Limit number of results
)

for result in text_results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['href']}")
    print(f"Description: {result['body']}")
```

#### Available Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `text()` | Text search | `keywords`, `region`, `safesearch`, `max_results` |
| `images()` | Image search | `keywords`, `region`, `safesearch`, `max_results` |
| `suggestions()` | Search suggestions | `query`, `region` |

#### Image Search Example

```python
image_results = yep.images(
    keywords="nature photography",
    region="all",
    safesearch="moderate",
    max_results=10
)

for image in image_results:
    print(f"Title: {image['title']}")
    print(f"URL: {image['image']}")
    print(f"Thumbnail: {image['thumbnail']}")
```

## Individual Search Engines

Webscout also provides direct access to individual search engines for specialized use cases.

### Available Engines

| Engine | Description | Features |
|--------|-------------|----------|
| `Bing` | Microsoft's search engine | Text search |
| `BingNews` | Bing news search | News articles |
| `Brave` | Privacy-focused search | Text search |
| `Mojeek` | Independent search engine | Text search |
| `Yahoo` | Yahoo search | Text search |
| `YahooNews` | Yahoo news | News articles |
| `Yandex` | Russian search engine | Text search |
| `Wikipedia` | Encyclopedia search | Articles |

### Usage Examples

```python
from webscout.search import Bing, Brave, Yahoo, Yandex, Wikipedia, BingNews, YahooNews, Mojeek

# Bing Search
bing = Bing()
results = bing.search("python programming", max_results=10)

# Brave Search
brave = Brave()
results = brave.search("artificial intelligence", max_results=10)

# Yahoo Search
yahoo = Yahoo()
results = yahoo.search("web development", max_results=10)

# Yandex Search
yandex = Yandex()
results = yandex.search("machine learning", max_results=10)

# Wikipedia Search
wiki = Wikipedia()
results = wiki.search("quantum computing", max_results=5)

# News-specific engines
bing_news = BingNews()
news_results = bing_news.search("technology news", max_results=15)

yahoo_news = YahooNews()
news_results = yahoo_news.search("AI breakthroughs", max_results=15)

# Mojeek Search (privacy-focused)
mojeek = Mojeek()
results = mojeek.search("open source", max_results=10)
```

## Command Line Interface

Webscout provides comprehensive CLI commands for all search engines.

### DuckDuckGo Commands

```bash
# Text search
webscout text -k "python programming" -r "wt-wt" -s "moderate" -t "y" -m 25

# Answers
webscout answers -k "population of france"

# Images
webscout images -k "nature photography" -m 90

# Videos
webscout videos -k "python tutorials" -m 50

# News
webscout news -k "technology trends" -m 25

# Maps
webscout maps -k "restaurants" -p "new york" -m 50

# Translate
webscout translate -k "hello world" -t "es"

# Suggestions
webscout suggestions -k "how to" -r "wt-wt"

# Weather
webscout weather -l "New York"
```

### Yep Commands

```bash
# Text search
webscout yep_text -k "web development" -r "all" -s "moderate" -m 10

# Image search
webscout yep_images -k "landscapes" -r "all" -s "moderate" -m 10

# Suggestions
webscout yep_suggestions -q "javascript"
```

## Advanced Usage

### Asynchronous Search

```python
import asyncio
from webscout import DuckDuckGoSearch

async def search_multiple_terms(search_terms):
    async with DuckDuckGoSearch() as ddg:
        # Create tasks for each search term
        tasks = [ddg.text(term, max_results=5) for term in search_terms]
        # Run all searches concurrently
        results = await asyncio.gather(*tasks)
        return results

async def main():
    terms = ["python", "javascript", "machine learning"]
    all_results = await search_multiple_terms(terms)

    # Process results
    for i, term_results in enumerate(all_results):
        print(f"Results for '{terms[i]}':")
        for result in term_results:
            print(f"- {result['title']}")
        print()

# Run the async function
asyncio.run(main())
```

### Custom Configuration

```python
from webscout import DuckDuckGoSearch

# Note: DuckDuckGoSearch() doesn't accept constructor arguments
# Proxy and timeout configuration is handled internally
ddg = DuckDuckGoSearch()

results = ddg.text("search query", max_results=10)
```

### Error Handling

```python
from webscout import DuckDuckGoSearch
from webscout.exceptions import WebscoutE

try:
    ddg = DuckDuckGoSearch()
    results = ddg.text("python programming", max_results=5)
    print(f"Found {len(results)} results")
except WebscoutE as e:
    print(f"Search failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Result Processing

```python
from webscout import DuckDuckGoSearch
import json

ddg = DuckDuckGoSearch()

# Get results
results = ddg.text("artificial intelligence", max_results=10)

# Convert to different formats
# As JSON
json_results = json.dumps(results, indent=2)

# Extract URLs only
urls = [result['href'] for result in results]

# Filter results
filtered_results = [
    result for result in results
    if 'python' in result['title'].lower()
]

# Save to file
with open('search_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

## API Reference

### DuckDuckGoSearch Class

#### Constructor

```python
DuckDuckGoSearch()
```

**Note:** The DuckDuckGoSearch class does not accept constructor parameters. Configuration like timeout, proxies, and SSL verification are handled internally by the underlying search engine implementations.

#### Methods

##### text(keywords, region="wt-wt", safesearch="moderate", timelimit=None, max_results=25)

Performs a general web search.

**Parameters:**
- `keywords` (str): Search query
- `region` (str): Region code (default: "wt-wt")
- `safesearch` (str): SafeSearch level ("on", "moderate", "off")
- `timelimit` (str): Time limit ("d", "w", "m", "y")
- `max_results` (int): Maximum results to return

**Returns:** List of result dictionaries

##### answers(keywords)

Gets instant answers for a query.

**Parameters:**
- `keywords` (str): Search query

**Returns:** List of answer dictionaries

##### images(keywords, region="wt-wt", safesearch="moderate", timelimit=None, max_results=90)

Searches for images.

**Parameters:**
- `keywords` (str): Search query
- `region` (str): Region code
- `safesearch` (str): SafeSearch level
- `timelimit` (str): Time limit
- `max_results` (int): Maximum results

**Returns:** List of image result dictionaries

##### videos(keywords, region="wt-wt", safesearch="moderate", timelimit=None, max_results=50)

Searches for videos.

**Parameters:**
- Similar to images()

**Returns:** List of video result dictionaries

##### news(keywords, region="wt-wt", safesearch="moderate", timelimit=None, max_results=25)

Searches for news articles.

**Parameters:**
- Similar to text()

**Returns:** List of news result dictionaries

##### maps(keywords, place=None, street=None, city=None, county=None, state=None, country=None, postalcode=None, latitude=None, longitude=None, radius=0, max_results=50)

Searches for locations and places.

**Parameters:**
- `keywords` (str): Search query
- `place` (str): Place name
- `street` (str): Street address
- `city` (str): City name
- `county` (str): County name
- `state` (str): State name
- `country` (str): Country name
- `postalcode` (str): Postal code
- `latitude` (float): Latitude coordinate
- `longitude` (float): Longitude coordinate
- `radius` (int): Search radius in kilometers
- `max_results` (int): Maximum results

**Returns:** List of map result dictionaries

##### translate(keywords, from_lang=None, to_lang="en")

Translates text between languages.

**Parameters:**
- `keywords` (str): Text to translate
- `from_lang` (str): Source language (auto-detected if None)
- `to_lang` (str): Target language (default: "en")

**Returns:** List of translation result dictionaries

##### suggestions(keywords, region="wt-wt")

Gets search suggestions.

**Parameters:**
- `keywords` (str): Partial search query
- `region` (str): Region code

**Returns:** List of suggestion strings

##### weather(location, language="en")

Gets weather information for a location.

**Parameters:**
- `location` (str): Location name
- `language` (str): Language code

**Returns:** Weather data dictionary

### YepSearch Class

#### Constructor

```python
YepSearch()
```

**Note:** The YepSearch class does not accept constructor parameters. Configuration like timeout, proxies, and SSL verification are handled internally by the underlying search engine implementations.

#### Methods

##### text(keywords, region="all", safesearch="moderate", max_results=None)

##### images(keywords, region="all", safesearch="moderate", max_results=None)

##### suggestions(query, region="all")

## Troubleshooting

### Common Issues

1. **Timeout Errors**
   ```python
   # Timeout is handled internally by the search engine implementation
   # If experiencing timeout issues, try reducing max_results
   ddg = DuckDuckGoSearch()
   results = ddg.text("query", max_results=5)
   ```

2. **Rate Limiting**
   ```python
   # Add delays between requests
   import time
   results = ddg.text("query", max_results=5)
   time.sleep(1)  # Wait 1 second between requests
   ```

3. **Network Issues**
   ```python
   # Handle network-related exceptions
   from webscout.exceptions import WebscoutE
   try:
       results = ddg.text("query", max_results=5)
   except WebscoutE as e:
       print(f"Search failed: {e}")
   ```

### Error Types

- `WebscoutE`: Base Webscout exception
- `RatelimitE`: Rate limit exceeded
- `TimeoutE`: Request timeout
- Standard Python exceptions for network/connectivity issues

## Best Practices

1. **Handle Errors Gracefully**: Always implement proper error handling for production use
2. **Set Reasonable Limits**: Don't request excessive results; most engines limit responses
3. **Respect Rate Limits**: Add delays between multiple requests
4. **Cache Results**: Cache search results when possible to reduce API calls
5. **Use Appropriate Result Limits**: Start with smaller `max_results` values and increase as needed

## Scout Integration

Webscout's search engines now use **Scout**, a powerful, zero-dependency HTML parsing library, instead of BeautifulSoup4. Scout provides all the parsing capabilities you need with better performance and more features.

### Why Scout?

- **Zero Dependencies**: No need to install BeautifulSoup4 or lxml separately
- **Full BS4 Compatibility**: Drop-in replacement for BeautifulSoup with the same API
- **Enhanced Features**: Advanced CSS selectors, text analysis, web crawling, and more
- **Better Performance**: Optimized parsing and traversal

### Scout Features Used in Search

The search engines leverage Scout's powerful CSS selector capabilities:

```python
from webscout.scout import Scout

# Parse HTML response
html = response.text
soup = Scout(html)

# CSS selectors (just like BeautifulSoup)
results = soup.select('ol#b_results > li.b_algo')  # Child combinator
title = result.select_one('h2 a')                   # Descendant selector
paragraphs = result.select('p.description')         # Class selector

# Extract data
href = title.get('href')
text = title.get_text(strip=True)
```

### Supported CSS Selectors

Scout's CSS selector engine supports:

- **Tag selectors**: `p`, `div`, `a`
- **Class selectors**: `.class`, `p.class`, `.class1.class2`
- **ID selectors**: `#id`, `div#id`
- **Attribute selectors**: `[attr]`, `[attr="value"]`
- **Descendant selectors**: `div p`, `div span a`
- **Child selectors**: `div > p`, `ol > li.item`
- **Combined selectors**: `p.class#id[attr]`

### Additional Scout Methods

Beyond CSS selectors, Scout provides many other useful methods:

```python
from webscout.scout import Scout

soup = Scout(html)

# Find methods (BeautifulSoup-compatible)
soup.find('div', attrs={'class': 'content'})
soup.find_all('p', limit=10)

# Text extraction
soup.get_text(separator='\n', strip=True)

# Tree traversal
tag.find_parent('div')
tag.find_next_sibling('p')

# Export to different formats
soup.to_json(indent=2)
soup.to_markdown()
soup.prettify()
```

### Learn More About Scout

For complete Scout documentation, see:
- [Scout README](../webscout/scout/README.md)
- [Scout API Reference](../webscout/scout/README.md#api-reference)

## Contributing

To add support for new search engines:

1. Create a new engine class in `webscout/search/engines/`
2. Implement the required interface methods
3. Add the engine to `webscout/search/__init__.py`
4. Update this documentation
5. Add CLI commands if appropriate

## License

This search functionality is part of Webscout and follows the same license terms.</content>
<parameter name="filePath">c:\Users\koula\Desktop\Webscout\docs\search.md