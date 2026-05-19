import os
import hmac
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import markdown
from db import get_db, init_db, seed_db, slugify
from models import Post, Comment

load_dotenv()

IS_PRODUCTION = bool(os.getenv('RAILWAY_ENVIRONMENT'))

_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if IS_PRODUCTION:
        raise RuntimeError('SECRET_KEY environment variable is required in production')
    _secret_key = 'dev-insecure-local-only'

_admin_password = os.getenv('ADMIN_PASSWORD', '')
if not _admin_password and IS_PRODUCTION:
    raise RuntimeError('ADMIN_PASSWORD environment variable is required in production')

app = Flask(__name__)
app.secret_key = _secret_key
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # trust Railway's X-Forwarded-For

app.config.update(
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    WTF_CSRF_TIME_LIMIT=3600,
)

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri='memory://',
)

# Initialize database on startup
with app.app_context():
    init_db()
    seed_db()

def md_to_html(text):
    """Convert Markdown to HTML with footnote extension."""
    return markdown.markdown(text, extensions=['extra', 'codehilite', 'toc'])

def is_admin():
    """Check if user is authenticated as admin."""
    return session.get('admin') is True

@app.route('/')
def index():
    """Homepage: latest 20 published posts, mixed authors."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM posts
        WHERE draft = 0
        ORDER BY published_at DESC
        LIMIT 20
    """)
    posts = [Post.from_row(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('index.html', posts=posts)

@app.route('/posts')
def posts_list():
    """All posts, filterable by author and topic."""
    author = request.args.get('author')
    topic = request.args.get('topic')
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM posts WHERE draft = 0"
    params = []
    
    if author:
        query += " AND author = ?"
        params.append(author)
    if topic:
        query += " AND topic = ?"
        params.append(topic)
    
    query += " ORDER BY published_at DESC"
    
    cursor.execute(query, params)
    posts = [Post.from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('posts_list.html', posts=posts, filter_author=author, filter_topic=topic)

@app.route('/posts/<slug>')
def post_detail(slug):
    """Single post + comments thread."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM posts WHERE slug = ?", (slug,))
    post_row = cursor.fetchone()
    
    if not post_row:
        conn.close()
        return "Post not found", 404
    
    post = Post.from_row(post_row)
    
    # Get published comments
    cursor.execute("""
        SELECT * FROM comments
        WHERE post_id = ? AND draft = 0
        ORDER BY created_at ASC
    """, (post.id,))
    comments = [Comment.from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('post.html', post=post, comments=comments)

@app.route('/pout')
def pout_profile():
    """Pout's profile and archive."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM posts
        WHERE author = 'pout' AND draft = 0
        ORDER BY published_at DESC
    """)
    posts = [Post.from_row(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('pout.html', posts=posts)

@app.route('/about')
def about():
    """About page with disclosure."""
    return render_template('about.html')

@app.route('/feed.xml')
def feed():
    """RSS feed of published posts."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM posts
        WHERE draft = 0
        ORDER BY published_at DESC
        LIMIT 50
    """)
    posts = [Post.from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    # Simple RSS generation
    rss_items = []
    for post in posts:
        author_name = "Fernando" if post.author == "fernando" else "Pout"
        rss_items.append(f"""
    <item>
        <title>{post.title}</title>
        <link>https://pout.blog/posts/{post.slug}</link>
        <author>{author_name}</author>
        <description>{post.excerpt or post.body_md[:200]}</description>
        <pubDate>{post.published_at}</pubDate>
        <guid>https://pout.blog/posts/{post.slug}</guid>
    </item>
        """)
    
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>pout.blog</title>
        <link>https://pout.blog</link>
        <description>A personal blog by Fernando and Pout</description>
        <language>en-us</language>
        {''.join(rss_items)}
    </channel>
</rss>"""
    
    return rss, 200, {'Content-Type': 'application/rss+xml'}

# Admin routes

@app.route('/admin')
def admin_home():
    """Admin home: login or dashboard."""
    if is_admin():
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def admin_login():
    """Admin login."""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if _admin_password and hmac.compare_digest(password.encode('utf-8'), _admin_password.encode('utf-8')):
            session.permanent = True
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid password')
    return render_template('admin_login.html')


@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template('admin_login.html', error='Too many attempts. Please wait a minute.'), 429

@app.route('/admin/logout')
def admin_logout():
    """Admin logout."""
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard: list drafts and published posts."""
    if not is_admin():
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM posts
        ORDER BY created_at DESC
    """)
    posts = [Post.from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    drafts = [p for p in posts if p.draft == 1]
    published = [p for p in posts if p.draft == 0]
    
    return render_template('admin_dashboard.html', drafts=drafts, published=published)

@app.route('/admin/new', methods=['GET', 'POST'])
def admin_new():
    """Admin: write a new post (Fernando only for Phase 1)."""
    if not is_admin():
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        body_md = request.form.get('body')
        topic = request.form.get('topic')
        publish = request.form.get('publish') == 'on'
        
        slug = slugify(title)
        body_html = md_to_html(body_md)
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posts (author, kind, topic, title, slug, body_md, body_html, draft, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'fernando',
            'essay',
            topic,
            title,
            slug,
            body_md,
            body_html,
            0 if publish else 1,
            datetime.now().isoformat()
        ))
        conn.commit()
        post_id = cursor.lastrowid
        conn.close()
        
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_new.html')

@app.route('/admin/edit/<int:post_id>', methods=['GET', 'POST'])
def admin_edit(post_id):
    """Admin: edit a post."""
    if not is_admin():
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        body_md = request.form.get('body')
        topic = request.form.get('topic')
        publish = request.form.get('publish') == 'on'
        
        body_html = md_to_html(body_md)
        
        cursor.execute("""
            UPDATE posts
            SET title = ?, body_md = ?, body_html = ?, topic = ?, draft = ?
            WHERE id = ?
        """, (title, body_md, body_html, topic, 0 if publish else 1, post_id))
        conn.commit()
        conn.close()
        
        return redirect(url_for('admin_dashboard'))
    
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    post_row = cursor.fetchone()
    conn.close()
    
    if not post_row:
        return "Post not found", 404
    
    post = Post.from_row(post_row)
    return render_template('admin_edit.html', post=post)

@app.route('/admin/preview', methods=['POST'])
def admin_preview():
    if not is_admin():
        return '', 403
    return md_to_html(request.form.get('body', ''))


@app.route('/admin/review/<int:post_id>', methods=['GET', 'POST'])
def admin_review(post_id):
    """Admin: review a Pout draft post."""
    if not is_admin():
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'publish':
            title = request.form.get('title')
            body_md = request.form.get('body')
            body_html = md_to_html(body_md)
            
            cursor.execute("""
                UPDATE posts
                SET title = ?, body_md = ?, body_html = ?, draft = 0
                WHERE id = ?
            """, (title, body_md, body_html, post_id))
        elif action == 'delete':
            cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    post_row = cursor.fetchone()
    conn.close()
    
    if not post_row:
        return "Post not found", 404
    
    post = Post.from_row(post_row)
    return render_template('admin_review.html', post=post)

if __name__ == '__main__':
    app.run(debug=True)
