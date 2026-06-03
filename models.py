from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Post:
    id: int
    author: str  # 'fernando' or 'pout'
    kind: str  # 'essay', etc.
    pout_mode: Optional[str]  # 'weekday', 'weekend', or None
    topic: Optional[str]  # 'tech', 'health', 'fitness', 'misc'
    title: str
    slug: str
    body_md: str
    body_html: str
    excerpt: Optional[str]
    draft: int  # 0 or 1
    published_at: str  # ISO8601
    created_at: str  # ISO8601
    render_mode: str = 'standard'  # 'standard' (Notion template) or 'custom'
    custom_html: Optional[str] = None  # body-only HTML used when render_mode == 'custom'
    custom_theme: Optional[str] = None  # JSON theme (fonts + CSS vars) from the Designer agent
    cover_image: Optional[str] = None  # optional cover image URL

    @classmethod
    def from_row(cls, row):
        """Create a Post from a sqlite3.Row."""
        keys = row.keys()
        return cls(
            id=row['id'],
            author=row['author'],
            kind=row['kind'],
            pout_mode=row['pout_mode'],
            topic=row['topic'],
            title=row['title'],
            slug=row['slug'],
            body_md=row['body_md'],
            body_html=row['body_html'],
            excerpt=row['excerpt'],
            draft=row['draft'],
            published_at=row['published_at'],
            created_at=row['created_at'],
            render_mode=(row['render_mode'] if 'render_mode' in keys else None) or 'standard',
            custom_html=row['custom_html'] if 'custom_html' in keys else None,
            custom_theme=row['custom_theme'] if 'custom_theme' in keys else None,
            cover_image=row['cover_image'] if 'cover_image' in keys else None,
        )

@dataclass
class Comment:
    id: int
    post_id: int
    author: str  # 'fernando' or 'pout'
    body_md: str
    body_html: str
    parent_id: Optional[int]
    draft: int  # 0 or 1
    created_at: str  # ISO8601
    
    @classmethod
    def from_row(cls, row):
        """Create a Comment from a sqlite3.Row."""
        return cls(
            id=row['id'],
            post_id=row['post_id'],
            author=row['author'],
            body_md=row['body_md'],
            body_html=row['body_html'],
            parent_id=row['parent_id'],
            draft=row['draft'],
            created_at=row['created_at']
        )

@dataclass
class NewsItem:
    id: int
    source: str
    topic: str
    url: str
    title: str
    excerpt: Optional[str]
    published_at: Optional[str]
    fetched_at: str
    used_in_post_id: Optional[int]
    pout_take: Optional[str]
    interest_score: Optional[int]
    
    @classmethod
    def from_row(cls, row):
        """Create a NewsItem from a sqlite3.Row."""
        return cls(
            id=row['id'],
            source=row['source'],
            topic=row['topic'],
            url=row['url'],
            title=row['title'],
            excerpt=row['excerpt'],
            published_at=row['published_at'],
            fetched_at=row['fetched_at'],
            used_in_post_id=row['used_in_post_id'],
            pout_take=row['pout_take'],
            interest_score=row['interest_score']
        )
