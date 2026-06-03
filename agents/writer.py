"""The Writer agent: Pout.

Generates Pout's blog posts and his comments on Fernando's posts. The voice
lives in prompts/pout_system.txt plus the weekday/weekend modifiers.
"""
import logging
from datetime import datetime
import markdown

from db import get_db, slugify
from .base import Agent, load_prompt

logger = logging.getLogger(__name__)


def _md_to_html(text):
    return markdown.markdown(text or '', extensions=['extra', 'codehilite', 'toc'])


def _current_mode():
    return 'weekend' if datetime.now().weekday() >= 5 else 'weekday'


def _unique_slug(cursor, base):
    slug, n = base, 1
    while cursor.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _parse_post(raw):
    """Parse TITLE / TOPIC / --- / body from model output."""
    lines = raw.splitlines()
    title, topic, sep = 'Untitled', 'misc', -1

    for i, line in enumerate(lines):
        if line.startswith('TITLE:'):
            title = line[6:].strip()
        elif line.startswith('TOPIC:'):
            t = line[6:].strip().lower()
            if t in ('tech', 'health', 'fitness', 'misc'):
                topic = t
        elif line.strip() == '---':
            sep = i
            break

    body_md = '\n'.join(lines[sep + 1:]).strip() if sep >= 0 else raw
    return title, topic, body_md


class WriterAgent(Agent):
    name = 'pout'
    model = 'claude-sonnet-4-6'

    def __init__(self):
        super().__init__()
        self.system = load_prompt('pout_system.txt')
        self.weekday = load_prompt('pout_weekday.txt')
        self.weekend = load_prompt('pout_weekend.txt')
        self.examples = load_prompt('examples.txt')

    def _mode_text(self, mode):
        return self.weekend if mode == 'weekend' else self.weekday

    def _avoid_block(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT title, topic FROM posts WHERE author = 'pout' "
            "ORDER BY created_at DESC LIMIT 12"
        ).fetchall()
        conn.close()
        if not rows:
            return ''
        lines = '\n'.join(f"- {r['title']} ({r['topic']})" for r in rows)
        return (
            "\nYou have recently written the posts below. Do not repeat these topics, "
            "angles, or titles. Pick something genuinely different this time, and vary "
            "the subject across tech, health, and fitness rather than circling one theme.\n"
            f"{lines}\n"
        )

    def generate_post(self, mode=None):
        """Generate a Pout post draft. Saves as draft=1. Returns post_id."""
        mode = mode or _current_mode()

        user_message = f"""{self._mode_text(mode)}

---

Write a blog post. Pick a topic that genuinely interests you right now: something you read, something that annoyed you, something worth engaging with carefully. Tech, health, fitness, or whatever has your attention.
{self._avoid_block()}

Length: 300-600 words. Open with one observation. Use markdown footnote syntax [^1] [^2] for sources and caveats. Sign off with "— Pout".

Here is how your voice sounds:

{self.examples}

---

Return your post in this exact format, nothing before or after:
TITLE: [title]
TOPIC: [tech|health|fitness|misc]
---
[post body in Markdown]"""

        raw = self.complete(self.system, user_message, max_tokens=1600)
        title, topic, body_md = _parse_post(raw)
        body_html = _md_to_html(body_md)
        now = datetime.now().isoformat()

        conn = get_db()
        cur = conn.cursor()
        slug = _unique_slug(cur, slugify(title))
        cur.execute("""
            INSERT INTO posts
                (author, kind, pout_mode, topic, title, slug, body_md, body_html, draft, published_at, created_at)
            VALUES ('pout', 'essay', ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (mode, topic, title, slug, body_md, body_html, now, now))
        conn.commit()
        post_id = cur.lastrowid
        conn.close()

        logger.info("Pout draft post: '%s' (id=%d mode=%s)", title, post_id, mode)
        return post_id

    def generate_comment(self, post_id, mode=None):
        """Generate a Pout comment draft on a Fernando post. Returns comment_id or None."""
        mode = mode or _current_mode()

        conn = get_db()
        row = conn.execute(
            "SELECT title, body_md FROM posts WHERE id = ?", (post_id,)
        ).fetchone()
        conn.close()

        if not row:
            logger.error("Post %d not found for comment generation", post_id)
            return None

        user_message = f"""{self._mode_text(mode)}

---

Fernando just published this post. Write a comment from Pout.

Post title: {row['title']}

Post:
{row['body_md']}

---

1-3 short paragraphs. If there's something to push back on, push back with one specific reason. If not, add a related angle or a datapoint that earns its place. Sign off with "— P."

Return only the comment text, nothing else."""

        body_md = self.complete(self.system, user_message, max_tokens=500)
        body_html = _md_to_html(body_md)
        now = datetime.now().isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO comments (post_id, author, body_md, body_html, draft, created_at)
            VALUES (?, 'pout', ?, ?, 1, ?)
        """, (post_id, body_md, body_html, now))
        conn.commit()
        comment_id = cur.lastrowid
        conn.close()

        logger.info("Pout draft comment on post %d (id=%d mode=%s)", post_id, comment_id, mode)
        return comment_id


# Shared instance + module-level helpers (back-compat with `from pout import ...`)
writer = WriterAgent()


def generate_post(mode=None):
    return writer.generate_post(mode)


def generate_comment(post_id, mode=None):
    return writer.generate_comment(post_id, mode)
