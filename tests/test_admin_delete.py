import uuid
import pytest
from db import get_db


def seed_post(app, draft=0, author='fernando'):
    slug = str(uuid.uuid4())[:12]
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO posts (author, kind, topic, title, slug, body_md, body_html, draft) "
            "VALUES (?, 'essay', 'misc', 'Test Post', ?, 'body', '<p>body</p>', ?)",
            (author, slug, draft),
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_delete_requires_auth(client):
    r = client.post('/admin/delete/1', follow_redirects=False)
    assert r.status_code == 302
    assert '/dashboard' not in r.headers['Location']


def test_delete_published_post(app, auth_client):
    post_id = seed_post(app, draft=0)
    r = auth_client.post(f'/admin/delete/{post_id}', follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
        assert row is None


def test_delete_draft_post(app, auth_client):
    post_id = seed_post(app, draft=1, author='pout')
    r = auth_client.post(f'/admin/delete/{post_id}', follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
        assert row is None


def test_delete_nonexistent_post(auth_client):
    r = auth_client.post('/admin/delete/99999', follow_redirects=False)
    assert r.status_code == 302  # graceful, no crash


def test_delete_cascades_comments(app, auth_client):
    post_id = seed_post(app, draft=0)
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO comments (post_id, author, body_md, body_html) "
            "VALUES (?, 'pout', 'hi', '<p>hi</p>')",
            (post_id,),
        )
        db.commit()
    auth_client.post(f'/admin/delete/{post_id}')
    with app.app_context():
        row = get_db().execute(
            "SELECT id FROM comments WHERE post_id = ?", (post_id,)
        ).fetchone()
        assert row is None
