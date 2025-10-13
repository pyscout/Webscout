"""Result models for search engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextResult:
    """Text search result."""
    
    title: str = ""
    href: str = ""
    body: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "href": self.href,
            "body": self.body,
        }


@dataclass
class ImagesResult:
    """Images search result."""
    
    title: str = ""
    image: str = ""
    thumbnail: str = ""
    url: str = ""
    height: int = 0
    width: int = 0
    source: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "image": self.image,
            "thumbnail": self.thumbnail,
            "url": self.url,
            "height": self.height,
            "width": self.width,
            "source": self.source,
        }


@dataclass
class VideosResult:
    """Videos search result."""
    
    content: str = ""
    description: str = ""
    duration: str = ""
    embed_html: str = ""
    embed_url: str = ""
    image_token: str = ""
    images: dict[str, str] = field(default_factory=dict)
    provider: str = ""
    published: str = ""
    publisher: str = ""
    statistics: dict[str, int] = field(default_factory=dict)
    title: str = ""
    uploader: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "description": self.description,
            "duration": self.duration,
            "embed_html": self.embed_html,
            "embed_url": self.embed_url,
            "image_token": self.image_token,
            "images": self.images,
            "provider": self.provider,
            "published": self.published,
            "publisher": self.publisher,
            "statistics": self.statistics,
            "title": self.title,
            "uploader": self.uploader,
        }


@dataclass
class NewsResult:
    """News search result."""
    
    date: str = ""
    title: str = ""
    body: str = ""
    url: str = ""
    image: str = ""
    source: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "image": self.image,
            "source": self.source,
        }


@dataclass
class BooksResult:
    """Books search result."""
    
    title: str = ""
    author: str = ""
    href: str = ""
    thumbnail: str = ""
    year: str = ""
    publisher: str = ""
    language: str = ""
    filesize: str = ""
    extension: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "href": self.href,
            "thumbnail": self.thumbnail,
            "year": self.year,
            "publisher": self.publisher,
            "language": self.language,
            "filesize": self.filesize,
            "extension": self.extension,
        }
