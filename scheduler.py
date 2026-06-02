import logging
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
ET = ZoneInfo('America/New_York')
scheduler = BackgroundScheduler(timezone=ET)


# ── job functions ──────────────────────────────────────────────────────────────

def _safe(label, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("%s failed", label)


def tuesday_post_job():
    from pout import generate_post
    _safe('tuesday_post', generate_post, 'weekday')


def friday_post_job():
    from pout import generate_post
    _safe('friday_post', generate_post, 'weekday')


def saturday_post_job():
    if random.random() < 0.5:
        logger.info("Pout skipped Saturday post (50%% chance)")
        return
    from pout import generate_post
    _safe('saturday_post', generate_post, 'weekend')


def sunday_bomb_job():
    if random.random() > 0.3:
        logger.info("Pout skipped Sunday comment bomb (70%% chance)")
        return
    from db import get_db
    from pout import generate_comment
    conn = get_db()
    posts = conn.execute("""
        SELECT p.id FROM posts p
        WHERE p.author = 'fernando' AND p.draft = 0
          AND NOT EXISTS (
              SELECT 1 FROM comments c
              WHERE c.post_id = p.id AND c.author = 'pout'
          )
        ORDER BY p.published_at DESC
        LIMIT 2
    """).fetchall()
    conn.close()
    for row in posts[:random.randint(1, max(1, len(posts)))]:
        _safe('sunday_bomb_comment', generate_comment, row['id'], 'weekend')


def daily_rss_job():
    from news import fetch_rss
    _safe('daily_rss', fetch_rss)


def weekly_triage_job():
    from news import triage_items, generate_news_roundup
    _safe('weekly_triage', triage_items)
    _safe('weekly_roundup', generate_news_roundup)


def process_comment_queue_job():
    """Fire any queued Pout comments whose delay has elapsed."""
    from db import get_db
    from pout import generate_comment
    conn = get_db()
    due = conn.execute(
        "SELECT post_id FROM comment_queue WHERE fire_at <= ?",
        (datetime.now().isoformat(),),
    ).fetchall()
    conn.close()

    for row in due:
        post_id = row['post_id']
        comment_id = _safe('comment_queue', generate_comment, post_id)
        if comment_id is not None:
            conn = get_db()
            conn.execute("DELETE FROM comment_queue WHERE post_id = ?", (post_id,))
            conn.commit()
            conn.close()


# ── setup ──────────────────────────────────────────────────────────────────────

def setup_scheduler():
    # In Flask dev mode the reloader forks twice; only start in the child process.
    if os.getenv('FLASK_DEBUG') and os.getenv('WERKZEUG_RUN_MAIN') != 'true':
        return

    scheduler.add_job(tuesday_post_job,        'cron', day_of_week='tue', hour=9,  id='tuesday_post',   replace_existing=True)
    scheduler.add_job(friday_post_job,         'cron', day_of_week='fri', hour=9,  id='friday_post',    replace_existing=True)
    scheduler.add_job(saturday_post_job,       'cron', day_of_week='sat', hour=11, id='saturday_post',  replace_existing=True)
    scheduler.add_job(sunday_bomb_job,         'cron', day_of_week='sun', hour=18, id='sunday_bomb',    replace_existing=True)
    scheduler.add_job(daily_rss_job,           'cron', hour=7,            id='daily_rss',      replace_existing=True)
    scheduler.add_job(weekly_triage_job,       'cron', day_of_week='sun', hour=20, id='weekly_triage',  replace_existing=True)
    scheduler.add_job(process_comment_queue_job, 'interval', minutes=30,  id='comment_queue',  replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started (%d jobs)", len(scheduler.get_jobs()))
