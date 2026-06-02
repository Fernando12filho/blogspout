import logging
from datetime import datetime
import feedparser
from db import get_db
from rss_sources import SOURCES

logger = logging.getLogger(__name__)


def fetch_rss():
    """Fetch all RSS sources, dedupe by URL, insert new items. Returns count of new items."""
    conn = get_db()
    inserted = 0

    for topic, sources in SOURCES.items():
        for source_name, url in sources:
            try:
                feed = feedparser.parse(url, request_headers={'User-Agent': 'pout.blog/1.0'})
                for entry in feed.entries[:20]:
                    item_url = (entry.get('link') or '').strip()
                    if not item_url:
                        continue
                    if conn.execute("SELECT 1 FROM news_items WHERE url = ?", (item_url,)).fetchone():
                        continue

                    title     = (entry.get('title') or '')[:500]
                    excerpt   = (entry.get('summary') or entry.get('description') or '')[:1000]
                    published_at = None
                    if getattr(entry, 'published_parsed', None):
                        try:
                            published_at = datetime(*entry.published_parsed[:6]).isoformat()
                        except Exception:
                            pass

                    conn.execute(
                        "INSERT INTO news_items (source, topic, url, title, excerpt, published_at) VALUES (?,?,?,?,?,?)",
                        (source_name, topic, item_url, title, excerpt, published_at),
                    )
                    inserted += 1
            except Exception:
                logger.exception("RSS fetch failed: %s (%s)", source_name, url)

    conn.commit()
    conn.close()
    logger.info("RSS fetch complete: %d new items", inserted)
    return inserted


def triage_items():
    """Score unscored news items with Haiku (1-5). Phase 4."""
    pass


def generate_news_roundup():
    """Write a weekly news roundup post with Sonnet. Phase 4."""
    pass
