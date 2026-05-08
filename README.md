# pout.blog

A personal Flask blog with an AI co-author named Pout. Fernando writes some posts; Pout writes 2–3 posts per week about tech, health, fitness, and whatever else.

## Quick Start (Local Development)

### Prerequisites

- Python 3.12+
- pip or venv

### Setup

1. **Clone or download the repo** and navigate to the directory:
   ```bash
   cd pout-blog
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a .env file** from the example:
   ```bash
   cp .env.example .env
   ```

5. **Edit .env** with your own values:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ADMIN_PASSWORD=choose_a_strong_password
   SECRET_KEY=choose_a_random_secret_key
   TZ=America/New_York
   ```

6. **Run the Flask development server:**
   ```bash
   flask run
   ```

7. **Open your browser** and navigate to `http://localhost:5000`

### First Login

- Go to `/admin`
- Login with the password you set in `ADMIN_PASSWORD`
- Write your first post or review generated content

## Deployment to Railway

### Prerequisites

- A Railway account (free tier available)
- GitHub account and repo for this project
- Anthropic API key

### Steps

1. **Push your repo to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/your-username/pout-blog.git
   git push -u origin main
   ```

2. **Create a Railway project:**
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Authorize and select your `pout-blog` repo

3. **Set environment variables** in Railway dashboard:
   - Go to your project settings
   - Click "Environment Variables"
   - Add:
     - `ANTHROPIC_API_KEY` (your Anthropic key)
     - `ADMIN_PASSWORD` (strong password)
     - `SECRET_KEY` (random secret)
     - `TZ=America/New_York`

4. **Add a persistent volume** for the SQLite database:
   - In Railway dashboard, go to your project
   - Click "Volumes"
   - Add volume mounted at `/data`
   - Database will automatically use `/data/blog.db`

5. **Configure custom domain** (optional):
   - In Railway, go to "Settings" → "Custom Domain"
   - Add `pout.blog` (or your domain)
   - Copy the CNAME target
   - In your registrar (Porkbun, Namecheap, etc.), set DNS:
     - Type: CNAME, Name: @, Value: <railway-cname-target>
   - SSL certificate will be issued automatically

6. **Deploy:**
   - Railway will auto-deploy when you push to GitHub
   - Check the deployment logs in Railway dashboard

### Database Backups

SQLite is a single file (`/data/blog.db` on Railway). To back it up:

```bash
# Copy from Railway volume to local machine
scp -r railway:/data/blog.db ./backup-$(date +%Y%m%d).db
```

Or use Railway's built-in snapshot feature in the dashboard.

## Project Structure

```
pout-blog/
├── app.py                 # Flask app with all routes
├── db.py                  # SQLite setup and helpers
├── models.py              # Post, Comment, NewsItem dataclasses
├── requirements.txt       # Python dependencies
├── .env.example           # Template for environment variables
├── .gitignore             # Git exclusions
├── Procfile               # Railway deployment config
├── runtime.txt            # Python version for Railway
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── post.html
│   ├── posts_list.html
│   ├── pout.html
│   ├── about.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── admin_new.html
│   ├── admin_edit.html
│   └── admin_review.html
└── static/                # CSS and static assets
    └── style.css
```

## Phase 1 Complete

This is **Phase 1** of the build spec. The following are **not yet implemented:**

- `pout.py`: LLM-powered post/comment generation
- `news.py`: RSS feed fetching and curation
- `scheduler.py`: Automated post scheduling with APScheduler
- LLM calls and Pout character prompts
- Weekend mode posts and comment automation

These will be added in Phases 2–4. For now, you can:

1. Write and publish posts manually as Fernando
2. Manually create Pout posts in the admin (write text, save as Pout)
3. Read the character bible in `POUT_CHARACTER_BIBLE.md` to understand Pout's voice

## Next Steps

Once you've verified Phase 1 locally and deployed:

1. Seed a few posts to get the feel of the site
2. Verify the design and layout match your vision
3. Proceed to Phase 2 (LLM integration for Pout's post generation)

## Support

For issues or questions, refer to `BUILD_SPEC.md` and `POUT_CHARACTER_BIBLE.md` for the full architecture and character guidelines.
