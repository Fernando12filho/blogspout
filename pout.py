import os
import logging
from datetime import datetime
import markdown
from anthropic import Anthropic
from db import get_db, slugify

logger = logging.getLogger(__name__)
client = Anthropic()


def _load(filename):
    path = os.path.join(os.path.dirname(__file__), 'prompts', filename)
    with open(path, 'r') as f:
        return f.read().strip()


SYSTEM   = _load('pout_system.txt')
WEEKDAY  = _load('pout_weekday.txt')
WEEKEND  = _load('pout_weekend.txt')
EXAMPLES = _load('examples.txt')


def _md_to_html(text):
    return markdown.markdown(text or '', extensions=['extra', 'codehilite', 'toc'])


def _current_mode():
    return 'weekend' if datetime.now().weekday() >= 5 else 'weekday'


def _mode_text(mode):
    return WEEKEND if mode == 'weekend' else WEEKDAY


def _infer_topic(text):
    t = text.lower()
    scores = {
        'tech':    sum(t.count(w) for w in ['software', 'code', ' ai ', 'llm', 'startup', 'api', 'infrastructure', 'algorithm', 'model']),
        'health':  sum(t.count(w) for w in ['sleep', 'protein', 'supplement', 'study', 'clinical', 'mortality', 'glp', 'metabol', 'vitamin', 'diet']),
        'fitness': sum(t.count(w) for w in ['training', 'exercise', 'strength', 'muscle', 'cardio', 'vo2', 'lifting', 'running', 'zone 2']),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'misc'


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


def generate_post(mode=None):
    """Generate a Pout post draft. Saves as draft=1. Returns post_id."""
    mode = mode or _current_mode()

    user_message = f"""{_mode_text(mode)}

---

Write a blog post. Pick a topic that genuinely interests you right now: something you read, something that annoyed you, something worth engaging with carefully. Tech, health, fitness, or whatever has your attention.

Length: 300-600 words. Open with one observation. Use markdown footnote syntax [^1] [^2] for sources and caveats. Sign off with "— Pout".

Here is how your voice sounds:

{EXAMPLES}

---

Return your post in this exact format, nothing before or after:
TITLE: [title]
TOPIC: [tech|health|fitness|misc]
---
[post body in Markdown]"""

    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1600,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
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


def generate_comment(post_id, mode=None):
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

    user_message = f"""{_mode_text(mode)}

---

Fernando just published this post. Write a comment from Pout.

Post title: {row['title']}

Post:
{row['body_md']}

---

1-3 short paragraphs. If there's something to push back on, push back with one specific reason. If not, add a related angle or a datapoint that earns its place. Sign off with "— P."

Return only the comment text, nothing else."""

    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=500,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )

    body_md = response.content[0].text.strip()
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
