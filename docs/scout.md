# Scout: Advanced HTML Parser & Web Crawler

**🚀 The Most Advanced HTML Parser & Web Crawler for AI/LLM Data Collection**

**🌟 Built for the Future • Powered by Intelligence • Trusted by Developers**

## 📋 Overview

Scout is an ultra-powerful, enterprise-grade HTML parsing and web crawling library designed for the AI era. Built with LLM data collection in mind, Scout provides unparalleled capabilities for extracting, analyzing, and processing web content at scale. With its BeautifulSoup-compatible API enhanced with modern features, Scout is the go-to solution for serious web scraping projects.

<details open>
<summary><b>🌟 Why Scout is the Ultimate Choice</b></summary>

- **🧠 LLM-Optimized Crawling**: Purpose-built for collecting high-quality training data for Large Language Models
- **🌐 Subdomain Intelligence**: Automatically discovers and crawls subdomains (e.g., blog.example.com, docs.example.com)
- **⚡ Lightning-Fast Performance**: Multi-threaded concurrent crawling with intelligent rate limiting
- **🎯 Surgical Precision**: Advanced content extraction that preserves structure while removing noise
- **🔍 Deep Analysis**: Built-in NLP capabilities for entity extraction, text analysis, and semantic understanding
- **🛡️ Enterprise-Ready**: Robust error handling, retry mechanisms, and respect for robots.txt
- **📊 Rich Data Extraction**: Captures metadata, structured data, semantic content, and more
- **🔄 Format Flexibility**: Export to JSON, Markdown, CSV, or custom formats
- **🎨 BeautifulSoup++ API**: Familiar interface with 10x more features

</details>

## 📑 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Features](#-features)
- [Advanced Usage](#-advanced-usage)
- [Webscout Integration](#-webscout-integration)
- [API Reference](#-api-reference)
- [Dependencies](#-dependencies)
- [Supported Python Versions](#-supported-python-versions)
- [Contributing](#-contributing)
- [License](#-license)

## 📦 Installation

Scout is included with Webscout:

```bash
pip install webscout
```

Or install the latest version from GitHub:

```bash
pip install git+https://github.com/pyscout/Webscout.git
```

## 🚀 Quick Start

### Basic Parsing

```python
from webscout.scout import Scout

# Parse HTML content
html_content = """
<html>
    <body>
        <h1>Hello, Scout!</h1>
        <div class="content">
            <p>Web parsing made easy.</p>
            <a href="https://example.com">Link</a>
        </div>
    </body>
</html>
"""

scout = Scout(html_content)

# Find elements
title = scout.find('h1')
links = scout.find_all('a')

# Extract text
print(title[0].get_text())  # Output: Hello, Scout!
print(links.attrs('href'))  # Output: ['https://example.com']
```

### Web Crawling

```python
from webscout.scout import ScoutCrawler

# Crawl a website with default settings
crawler = ScoutCrawler('https://example.com')  # Default: max_pages=50

# Or customize the crawler
crawler = ScoutCrawler(
    'https://example.com',                      # base_url
    max_pages=100,                              # maximum pages to crawl
    tags_to_remove=['script', 'style', 'nav']   # tags to remove from content
)

# Start crawling
crawled_pages = crawler.crawl()

for page in crawled_pages:
    print(f"URL: {page['url']}")
    print(f"Title: {page['title']}")
    print(f"Links found: {len(page['links'])}")
    print(f"Crawl depth: {page['depth']}")
```

### Text Analysis

```python
from webscout.scout import Scout

# Parse a webpage
html = """<div><h1>Climate Change</h1><p>Email us at info@example.com or call 555-123-4567.</p>
<p>Visit https://climate-action.org for more information.</p></div>"""
scout = Scout(html)

# Analyze text and extract entities
analysis = scout.analyze_text()
print(f"Word frequencies: {analysis['word_count']}")
print(f"Entities found: {analysis['entities']}")
```

## ✨ Features

### 🔍 Multiple Parser Support

Scout supports multiple HTML/XML parsers, allowing you to choose the best tool for your specific needs:

| Parser | Description | Best For |
|--------|-------------|----------|
| `html.parser` | Python's built-in parser | General-purpose parsing, no dependencies |
| `lxml` | Fast C-based parser | Performance-critical applications |
| `html5lib` | Highly compliant HTML5 parser | Handling malformed HTML |
| `lxml-xml` | XML parser | XML document parsing |

```python
# Choose your parser
scout = Scout(html_content, features='lxml')  # For speed
scout = Scout(html_content, features='html5lib')  # For compliance
```

### 🌐 Advanced Parsing Capabilities

Scout provides powerful tools for navigating and manipulating HTML/XML documents:

- **Element Selection**: Find elements by tag name, attributes, CSS selectors, and more
- **Tree Traversal**: Navigate parent-child relationships and sibling elements
- **Content Extraction**: Extract text, attributes, and structured data
- **Document Manipulation**: Modify, replace, or remove elements
- **Dynamic Building**: Easily append or insert new nodes

#### CSS Selector Support

Scout includes a comprehensive CSS selector engine that supports all common selector types:

```python
# Tag selectors
paragraphs = scout.select('p')
divs = scout.select('div')

# Class selectors
items = scout.select('.item')              # Single class
cards = scout.select('div.card')           # Tag + class
special = scout.select('.card.special')    # Multiple classes

# ID selectors
header = scout.select_one('#header')       # Single element by ID
menu = scout.select('nav#main-menu')       # Tag + ID

# Attribute selectors
links = scout.select('a[href]')                    # Has attribute
external = scout.select('a[rel="nofollow"]')       # Attribute value
images = scout.select('img[alt]')                  # Has alt attribute

# Descendant selectors (space)
nested = scout.select('div p')                     # Any p inside div
deep = scout.select('article section p')           # Deeply nested

# Child selectors (>)
direct = scout.select('ul > li')                   # Direct children only
menu_items = scout.select('nav#menu > ul > li')    # Multiple levels

# Combined selectors
complex = scout.select('div.container > p.text[lang="en"]')
links = scout.select('ol#results > li.item a[href]')

# Get first match only
first = scout.select_one('p.intro')
```

**Supported Selector Types:**
- **Tag**: `p`, `div`, `a`
- **Class**: `.class`, `div.class`, `.class1.class2`
- **ID**: `#id`, `div#id`
- **Attribute**: `[attr]`, `[attr="value"]`
- **Descendant**: `div p`, `article section p`
- **Child**: `div > p`, `ul > li`
- **Combined**: `p.class#id[attr="value"]`

#### Element Navigation

```python
# Advanced find with attribute matching
results = scout.find_all('a', attrs={'class': 'external', 'rel': 'nofollow'})

# Tree traversal
parent = element.find_parent('div')
siblings = element.find_next_siblings('p')
prev_sibling = element.find_previous_sibling('p')
```

### 🧠 Intelligent Analysis

Scout includes built-in analysis tools for extracting insights from web content:

#### Text Analysis

```python
# Extract and analyze text
text = scout.get_text()
word_counts = scout.text_analyzer.count_words(text)
entities = scout.text_analyzer.extract_entities(text)
```

#### Web Structure Analysis

```python
# Analyze page structure
structure = scout.analyze_page_structure()
print(f"Most common tags: {structure['tag_distribution']}")
print(f"Page depth: {max(structure['depth_analysis'].keys())}")
```

#### Semantic Information Extraction

```python
# Extract semantic information
semantics = scout.extract_semantic_info()
print(f"Headings: {semantics['headings']}")
print(f"Lists: {len(semantics['lists']['ul']) + len(semantics['lists']['ol'])}")
print(f"Tables: {semantics['tables']['count']}")
```

### 🕸️ Web Crawling

Scout includes a powerful concurrent web crawler for fetching and analyzing multiple pages:

```python
from webscout.scout import ScoutCrawler

# Create a crawler with default settings
crawler = ScoutCrawler('https://example.com')  # Default: max_pages=50

# Or customize the crawler with specific options
crawler = ScoutCrawler(
    'https://example.com',                      # base_url
    max_pages=100,                              # maximum pages to crawl
    tags_to_remove=['script', 'style', 'nav']   # tags to remove from content
)

# Start crawling
pages = crawler.crawl()

# Process results
for page in pages:
    print(f"URL: {page['url']}")
    print(f"Title: {page['title']}")
    print(f"Links: {len(page['links'])}")
    print(f"Depth: {page['depth']}")
```

The crawler automatically:
- Stays within the same domain as the base URL
- Uses concurrent requests for faster crawling
- Removes unwanted tags (like scripts and styles) for cleaner text extraction
- Tracks crawl depth for each page

### 📄 Format Conversion

Scout can convert HTML to various formats:

```python
# Convert to JSON
json_data = scout.to_json(indent=2)

# Convert to Markdown
markdown = scout.to_markdown(heading_style='ATX')

# Pretty-print HTML
pretty_html = scout.prettify()
```

## 🔬 Advanced Usage

### Working with Search Results

Scout's search methods return a `ScoutSearchResult` object with powerful methods for processing results:

```python
from webscout.scout import Scout

scout = Scout(html_content)

# Find all paragraphs
paragraphs = scout.find_all('p')

# Extract all text from results
all_text = paragraphs.texts(separator='\n')

# Extract specific attributes
hrefs = paragraphs.attrs('href')

# Filter results with a predicate function
important = paragraphs.filter(lambda p: 'important' in p.get('class', []))

# Transform results
word_counts = paragraphs.map(lambda p: len(p.get_text().split()))

# Analyze text in results
analysis = paragraphs.analyze_text()
```

### URL Handling and Analysis

```python
from webscout.scout import Scout

scout = Scout(html_content)

# Parse and analyze URLs
links = scout.extract_links(base_url='https://example.com')
for link in links:
    url_components = scout.url_parse(link['href'])
    print(f"Domain: {url_components['netloc']}")
    print(f"Path: {url_components['path']}")
```

### Metadata Extraction

```python
from webscout.scout import Scout

scout = Scout(html_content)

# Extract metadata
metadata = scout.extract_metadata()
print(f"Title: {metadata['title']}")
print(f"Description: {metadata['description']}")
print(f"Open Graph: {metadata['og_metadata']}")
print(f"Twitter Card: {metadata['twitter_metadata']}")
```

### Content Hashing and Caching

```python
from webscout.scout import Scout

scout = Scout(html_content)

# Generate content hash
content_hash = scout.hash_content(method='sha256')

# Use caching for expensive operations
if not scout.cache('parsed_data'):
    data = scout.extract_semantic_info()
    scout.cache('parsed_data', data)

cached_data = scout.cache('parsed_data')
```

## 🔗 Webscout Integration

Scout is deeply integrated into Webscout's search engines, providing powerful HTML parsing capabilities without external dependencies.

### Why Scout in Webscout?

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

### Supported CSS Selectors in Search

Scout's CSS selector engine supports:

- **Tag selectors**: `p`, `div`, `a`
- **Class selectors**: `.class`, `p.class`, `.class1.class2`
- **ID selectors**: `#id`, `div#id`
- **Attribute selectors**: `[attr]`, `[attr="value"]`
- **Descendant selectors**: `div p`, `div span a`
- **Child selectors**: `div > p`, `ol > li.item`
- **Combined selectors**: `p.class#id[attr]`

### Additional Scout Methods in Search

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

## 📚 API Reference

### Core Classes

| Class | Description |
|-------|-------------|
| `Scout` | Main class for HTML parsing and traversal |
| `ScoutCrawler` | Web crawler for fetching and parsing multiple pages |
| `ScoutTextAnalyzer` | Text analysis utilities |
| `ScoutWebAnalyzer` | Web page analysis utilities |
| `ScoutSearchResult` | Enhanced search results with filtering and analysis |
| `Tag` | Represents an HTML/XML tag |
| `NavigableString` | Represents text within an HTML/XML document |

### Key Methods

#### Scout Class

- `__init__(markup, features='html.parser', from_encoding=None)`: Initialize with HTML content
- `find(name, attrs={}, recursive=True, text=None)`: Find first matching element
- `find_all(name, attrs={}, recursive=True, text=None, limit=None)`: Find all matching elements
- `find_next(name, attrs={}, text=None)`: Find next element in document order
- `find_all_next(name, attrs={}, text=None, limit=None)`: Find all next elements in document order
- `find_previous(name, attrs={}, text=None)`: Find previous element in document order
- `find_all_previous(name, attrs={}, text=None, limit=None)`: Find all previous elements in document order
- `select(selector)`: Find elements using CSS selector
- `get_text(separator=' ', strip=False)`: Extract text from document
- `analyze_text()`: Perform text analysis
- `analyze_page_structure()`: Analyze document structure
- `extract_semantic_info()`: Extract semantic information
- `extract_links(base_url=None)`: Extract all links
- `extract_metadata()`: Extract metadata from document
- `to_json(indent=2)`: Convert to JSON
- `to_markdown(heading_style='ATX')`: Convert to Markdown
- `prettify(formatter='minimal')`: Pretty-print HTML

#### ScoutCrawler Class

- `__init__(base_url, max_pages=50, tags_to_remove=None)`: Initialize the crawler
- `crawl()`: Start crawling from the base URL
- `_crawl_page(url, depth=0)`: Crawl a single page (internal method)
- `_is_valid_url(url)`: Check if a URL is valid (internal method)

For detailed API documentation, please refer to the [documentation](https://github.com/pyscout/Webscout/wiki).

## 🔧 Dependencies

- `curl_cffi`: HTTP library used for web requests
- `lxml`: XML and HTML processing library (optional, recommended)
- `html5lib`: Standards-compliant HTML parser (optional)
- `markdownify`: HTML to Markdown conversion
- `concurrent.futures`: Asynchronous execution (standard library)

## 🌈 Supported Python Versions

- Python 3.8+

## 🤝 Contributing

Contributions are welcome! Here's how you can contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please make sure to update tests as appropriate.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<div align="center">
  <p>Made with ❤️ by the Webscout team</p>
  <p>
    <a href="https://github.com/pyscout/Webscout">GitHub</a> •
    <a href="https://github.com/pyscout/Webscout/wiki">Documentation</a> •
    <a href="https://github.com/pyscout/Webscout/issues">Report Bug</a> •
    <a href="https://github.com/pyscout/Webscout/issues">Request Feature</a>
  </p>
</div>