<div align="center">
  <a href="https://github.com/pyscout/Webscout">
    <img src="https://img.shields.io/badge/YTToolkit-YouTube%20Toolkit-red?style=for-the-badge&logo=youtube&logoColor=white" alt="YTToolkit Logo">
  </a>
  <h1>YTToolkit</h1>
  <p><strong>Comprehensive YouTube Toolkit for Downloading, Transcription, and Data Extraction</strong></p>

  <!-- Badges -->
  <p>
    <a href="https://pypi.org/project/webscout/"><img src="https://img.shields.io/pypi/v/webscout.svg?style=flat-square&logo=pypi&label=PyPI" alt="PyPI Version"></a>
    <a href="#"><img src="https://img.shields.io/badge/No%20API%20Key-Required-success?style=flat-square" alt="No API Key Required"></a>
    <a href="#"><img src="https://img.shields.io/badge/Python-3.7%2B-blue?style=flat-square&logo=python" alt="Python Version"></a>
  </p>
</div>

> [!NOTE]
> YTToolkit provides a complete suite of YouTube tools including video downloading, transcript extraction, and comprehensive data retrieval - all without requiring an official API key.

## ✨ Features

### Video Management

* **Advanced Video Downloading**
  * Multiple format support (MP4, MP3)
  * Customizable quality selection (up to 4K)
  * Progress tracking and auto-save functionality
  * Batch downloading with search capabilities

* **Transcript Extraction**
  * Multi-language transcript support
  * Automatic and manual transcript fetching
  * Real-time translation capabilities
  * Flexible parsing options

### Data Extraction

* **Channel Information**
  * Comprehensive channel metadata
  * Subscriber count, views, and engagement metrics
  * Avatar and banner image URLs
  * Social media links and about information

* **Video Intelligence**
  * Detailed video metadata retrieval
  * Thumbnail extraction in multiple resolutions
  * Stream and upload history tracking
  * Embed code generation

* **Search & Discovery**
  * Advanced search capabilities
  * Trending videos across categories
  * Playlist content extraction
  * No official API dependency

## 🚀 Installation

```bash
pip install -U webscout
```

## 💻 Quick Start Guide

### Video Downloading

```python
from webscout import Handler

# Basic video download
downloader = Handler('https://youtube.com/watch?v=dQw4w9WgXcQ')
downloader.save()

# Advanced download with custom settings
downloader = Handler(
    query='python tutorial',  # Search query
    format='mp4',            # Format (mp4, mp3)
    quality='720p',          # Quality (144p to 4K)
    limit=5                  # Number of videos to download
)
downloader.auto_save(dir='./downloads')
```

### Transcript Extraction

```python
from webscout import YTTranscriber

# Get video transcript
transcript = YTTranscriber.get_transcript('https://youtube.com/watch?v=dQw4w9WgXcQ')
print(transcript)

# Get transcript in a specific language
spanish_transcript = YTTranscriber.get_transcript(
    'dQw4w9WgXcQ',  # Video ID or URL
    languages='es'   # Language code
)

# Translate transcript
translated = YTTranscriber.translate_transcript(
    'dQw4w9WgXcQ',  # Video ID or URL
    source_lang='en',
    target_lang='fr'
)
```

### Channel Information

```python
from webscout import Channel

# Create a channel instance
channel = Channel('@PewDiePie')  # Handle, ID, or URL

# Access channel metadata
print(f"Channel: {channel.name}")
print(f"Subscribers: {channel.subscribers}")
print(f"Total Views: {channel.views}")
print(f"Country: {channel.country}")

# Get media URLs
print(f"Avatar: {channel.avatar}")
print(f"Banner: {channel.banner}")

# Get recent uploads
recent_videos = channel.uploads(10)  # 10 most recent videos
```

### Video Metadata

```python
from webscout import Video

# Get video information
video = Video('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
metadata = video.metadata

print(f"Title: {metadata['title']}")
print(f"Views: {metadata['views']}")
print(f"Duration: {metadata['duration']} seconds")
print(f"Upload Date: {metadata['upload_date']}")

# Get thumbnails
thumbnails = video.thumbnail_urls
print(f"Default thumbnail: {thumbnails['default']}")
print(f"High quality: {thumbnails['high']}")
```

### Search & Trending

```python
from webscout import Search, Extras

# Search for videos
video_results = Search.videos("Python tutorial", limit=5)

# Search for channels
channel_results = Search.channels("coding", limit=3)

# Get trending videos
trending = Extras.trending_videos(limit=10)

# Get category-specific videos
music_videos = Extras.music_videos(limit=5)
gaming_videos = Extras.gaming_videos(limit=5)
```

## 📓 Detailed Documentation

<details>
<summary><strong>Video Downloader (Handler)</strong></summary>

The `Handler` class provides powerful video downloading capabilities:

```python
from webscout import Handler

# Initialize with video URL or search query
downloader = Handler('https://youtube.com/watch?v=dQw4w9WgXcQ')

# Basic download with default settings
downloader.save()  # Saves to current directory

# Download with custom settings
downloader.save(
    filename='custom_name',  # Custom filename
    format='mp3',           # Format (mp4, mp3)
    quality='highest',      # Quality setting
    output_path='./videos'  # Output directory
)

# Batch download from search
batch_downloader = Handler(
    query='python tutorials',
    limit=5,                # Number of videos
    format='mp4',
    quality='720p'
)
batch_downloader.auto_save()

# Get download progress
progress = downloader.progress
print(f"Download progress: {progress}%")

# Get download history
history = downloader.history
print(f"Downloaded files: {history}")
```
</details>

<details>
<summary><strong>Transcript Retriever (YTTranscriber)</strong></summary>

The `YTTranscriber` class extracts and processes video transcripts:

```python
from webscout import YTTranscriber

# Get available transcript languages
languages = YTTranscriber.get_available_languages('dQw4w9WgXcQ')
print(f"Available languages: {languages}")

# Get transcript with specific options
transcript = YTTranscriber.get_transcript(
    'dQw4w9WgXcQ',
    languages=['en', 'es', 'fr'],  # Preferred languages in order
    translate=True,                # Auto-translate if needed
    format='text'                  # Format: 'text', 'json', or 'srt'
)

# Get transcript with timestamps
timestamped = YTTranscriber.get_transcript(
    'dQw4w9WgXcQ',
    include_timestamps=True
)
for entry in timestamped:
    print(f"[{entry['start']:.2f}s] {entry['text']}")

# Save transcript to file
YTTranscriber.save_transcript(
    'dQw4w9WgXcQ',
    output_file='transcript.txt',
    format='text'
)
```
</details>

<details>
<summary><strong>Channel Class</strong></summary>

The `Channel` class provides comprehensive access to YouTube channel data:

```python
from webscout import Channel

# Initialize with channel handle, ID, or URL
channel = Channel('@PewDiePie')

# Basic information
print(f"Name: {channel.name}")
print(f"ID: {channel.id}")
print(f"Subscribers: {channel.subscribers}")
print(f"Total Views: {channel.views}")
print(f"Country: {channel.country}")

# Media URLs
print(f"Avatar: {channel.avatar}")
print(f"Banner: {channel.banner}")
print(f"URL: {channel.url}")

# Content
print(f"Description: {channel.description}")
print(f"Social Links: {channel.socials}")

# Live status
if channel.live:
    print(f"Currently streaming: {channel.streaming_now}")

# Get videos
recent_uploads = channel.uploads(20)  # Get 20 most recent videos
```
</details>

<details>
<summary><strong>Video Class</strong></summary>

The `Video` class extracts detailed information about YouTube videos:

```python
from webscout import Video

# Initialize with video ID or URL
video = Video('https://www.youtube.com/watch?v=dQw4w9WgXcQ')

# Get comprehensive metadata
metadata = video.metadata
print(f"Title: {metadata['title']}")
print(f"Views: {metadata['views']}")
print(f"Duration: {metadata['duration']} seconds")
print(f"Upload Date: {metadata['upload_date']}")
print(f"Author ID: {metadata['author_id']}")
print(f"Tags: {metadata['tags']}")

# Get thumbnails in different resolutions
thumbnails = video.thumbnail_urls
print(f"Default thumbnail: {thumbnails['default']}")
print(f"High quality thumbnail: {thumbnails['high']}")
print(f"Maximum resolution thumbnail: {thumbnails['maxres']}")

# Get embed code and URL
print(f"Embed HTML: {video.embed_html}")
print(f"Embed URL: {video.embed_url}")
```
</details>

<details>
<summary><strong>Search & Extras Classes</strong></summary>

The `Search` and `Extras` classes provide discovery capabilities:

```python
from webscout import Search, Extras

# Search for videos with advanced options
video_results = Search.videos(
    "Python tutorial",
    limit=5,           # Number of results
    sort_by="relevance",  # Sort order
    filter_by="video"     # Filter type
)

# Search for channels
channel_results = Search.channels("coding", limit=3)

# Search for playlists
playlist_results = Search.playlists("music mix", limit=3)

# Get trending videos by region
trending = Extras.trending_videos(
    limit=10,
    region="US"  # Country code
)

# Get category-specific videos
music = Extras.music_videos(limit=5)
gaming = Extras.gaming_videos(limit=5)
```
</details>

## 📚 Module Structure

| Module | File | Description |
|--------|------|-------------|
| **Video Downloader** | [`YTdownloader.py`](YTdownloader.py) | YouTube video downloading with format and quality options |
| **Transcript Retriever** | [`transcriber.py`](transcriber.py) | Multi-language transcript extraction and translation |
| **Channel Data** | [`ytapi/channel.py`](ytapi/channel.py) | Channel metadata and interaction |
| **Video Information** | [`ytapi/video.py`](ytapi/video.py) | Video information extraction |
| **Search** | [`ytapi/query.py`](ytapi/query.py) | Advanced search capabilities |
| **Trending** | [`ytapi/extras.py`](ytapi/extras.py) | Trending and category-based video retrieval |
| **Playlists** | [`ytapi/playlist.py`](ytapi/playlist.py) | Playlist metadata extraction |

## ⚠️ Disclaimer

> [!WARNING]
> This toolkit is designed for educational and research purposes only. Please use responsibly and in accordance with YouTube's terms of service. The developers are not responsible for any misuse of this software.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

<div align="center">
  <p>
    <a href="https://t.me/PyscoutAI"><img alt="Telegram Group" src="https://img.shields.io/badge/Telegram%20Group-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white"></a>
    <a href="https://youtube.com/@OEvortex"><img alt="YouTube" src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white"></a>
    <a href="https://buymeacoffee.com/oevortex"><img alt="Buy Me A Coffee" src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black"></a>
  </p>
</div>
