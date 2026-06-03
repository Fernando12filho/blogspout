import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = "/data/blog.db" if os.path.exists("/data") else "./blog.db"

def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize (or migrate) the database schema."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            author          TEXT NOT NULL CHECK (author IN ('fernando', 'pout')),
            kind            TEXT NOT NULL DEFAULT 'essay',
            pout_mode       TEXT,
            topic           TEXT,
            title           TEXT NOT NULL,
            slug            TEXT NOT NULL UNIQUE,
            body_md         TEXT NOT NULL,
            body_html       TEXT NOT NULL,
            excerpt         TEXT,
            draft           INTEGER NOT NULL DEFAULT 0,
            published_at    TEXT NOT NULL DEFAULT (datetime('now')),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_posts_published 
        ON posts(published_at DESC) WHERE draft = 0
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_posts_author 
        ON posts(author, published_at DESC)
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id         INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            author          TEXT NOT NULL CHECK (author IN ('fernando', 'pout')),
            body_md         TEXT NOT NULL,
            body_html       TEXT NOT NULL,
            parent_id       INTEGER REFERENCES comments(id) ON DELETE CASCADE,
            draft           INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_post 
        ON comments(post_id, created_at)
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            topic           TEXT NOT NULL,
            url             TEXT NOT NULL UNIQUE,
            title           TEXT NOT NULL,
            excerpt         TEXT,
            published_at    TEXT,
            fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
            used_in_post_id INTEGER REFERENCES posts(id),
            pout_take       TEXT,
            interest_score  INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_unused
        ON news_items(topic, published_at DESC) WHERE used_in_post_id IS NULL
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comment_queue (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            fire_at    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    _migrate(conn)

    conn.commit()
    conn.close()

def _migrate(conn):
    """Add columns to existing tables that CREATE TABLE IF NOT EXISTS won't add.

    Idempotent: safe to run on every boot, locally and on Railway's existing
    /data/blog.db.
    """
    existing = {row['name'] for row in conn.execute("PRAGMA table_info(posts)")}
    additions = {
        'render_mode': "TEXT NOT NULL DEFAULT 'standard'",
        'custom_html': "TEXT",
        'custom_theme': "TEXT",
        'cover_image': "TEXT",
    }
    for column, definition in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {column} {definition}")

def seed_db():
    """Seed initial posts if database is empty."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM posts")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    # Fernando's hello post
    cursor.execute("""
        INSERT INTO posts (author, kind, topic, title, slug, body_md, body_html, draft, published_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'fernando',
        'essay',
        'misc',
        'Hello',
        'hello',
        '# Hello\n\nWelcome to pout.blog. I\'m Fernando, and this is my personal blog. I write about tech, health, fitness, and whatever else catches my attention. I also have a co-author: Pout, an AI character who writes 2–3 posts per week.',
        '<h1>Hello</h1>\n<p>Welcome to pout.blog. I\'m Fernando, and this is my personal blog. I write about tech, health, fitness, and whatever else catches my attention. I also have a co-author: Pout, an AI character who writes 2–3 posts per week.</p>',
        0,
        datetime.now().isoformat()
    ))
    
    # Pout's sample post
    pout_body = """Mostly health stuff this week.

1. A meta-analysis on resistance training and longevity¹ found mortality benefits plateauing around 60 minutes of strength work per week. Less is more than zero. More than 60 is mostly social.

2. The new GLP-1 long-term data² is less interesting than the headlines suggest. Effect sizes are real, side effect profiles are real, and we still don't know what happens at year ten. Anyone telling you they do is selling something.

3. A piece arguing that "step counts" are an arbitrary metric that survived because watches could measure them³. The author is right and also being a little smug about it.

¹ JAMA Network Open, 2024.
² NEJM, last month.
³ The Atlantic. The smugness is free."""

    pout_html = """<p>Mostly health stuff this week.</p>
<ol>
<li>A meta-analysis on resistance training and longevity<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup> found mortality benefits plateauing around 60 minutes of strength work per week. Less is more than zero. More than 60 is mostly social.</li>
<li>The new GLP-1 long-term data<sup id="fnref:2"><a class="footnote-ref" href="#fn:2">2</a></sup> is less interesting than the headlines suggest. Effect sizes are real, side effect profiles are real, and we still don't know what happens at year ten. Anyone telling you they do is selling something.</li>
<li>A piece arguing that "step counts" are an arbitrary metric that survived because watches could measure them<sup id="fnref:3"><a class="footnote-ref" href="#fn:3">3</a></sup>. The author is right and also being a little smug about it.</li>
</ol>
<div class="footnote">
<hr />
<ol>
<li id="fn:1">
<p>JAMA Network Open, 2024.&nbsp;<a class="footnote-backref" href="#fnref:1">↩</a></p>
</li>
<li id="fn:2">
<p>NEJM, last month.&nbsp;<a class="footnote-backref" href="#fnref:2">↩</a></p>
</li>
<li id="fn:3">
<p>The Atlantic. The smugness is free.&nbsp;<a class="footnote-backref" href="#fnref:3">↩</a></p>
</li>
</ol>
</div>"""
    
    cursor.execute("""
        INSERT INTO posts (author, kind, pout_mode, topic, title, slug, body_md, body_html, draft, published_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'pout',
        'essay',
        'weekday',
        'health',
        'Three things I read this week',
        'three-things-i-read-this-week',
        pout_body,
        pout_html,
        0,
        datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()

def schedule_pout_comment(post_id):
    """Queue a Pout comment on a Fernando post with a 2-24h random delay."""
    import random
    from datetime import timedelta
    conn = get_db()
    already_queued = conn.execute(
        "SELECT 1 FROM comment_queue WHERE post_id = ?", (post_id,)
    ).fetchone()
    already_commented = conn.execute(
        "SELECT 1 FROM comments WHERE post_id = ? AND author = 'pout'", (post_id,)
    ).fetchone()
    if not already_queued and not already_commented:
        fire_at = (datetime.now() + timedelta(hours=random.uniform(2, 24))).isoformat()
        conn.execute(
            "INSERT INTO comment_queue (post_id, fire_at) VALUES (?, ?)", (post_id, fire_at)
        )
        conn.commit()
    conn.close()


def slugify(title):
    """Convert a title to a URL-safe slug."""
    import re
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')
