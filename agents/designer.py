"""The Designer agent.

Given a post, it designs a one-off visual treatment driven by the post's topic
and content: a colour palette, a typeface pairing, and a bespoke body layout.

The output is intentionally constrained so it can never break the site shell:

  * Colours are emitted as CSS custom-property overrides on a fixed, validated
    allowlist of tokens. Because the header, footer, nav, and logo are already
    built on those same tokens, they restyle automatically while keeping their
    structure. The logo text never changes.
  * Fonts are chosen from a curated allowlist of Google Fonts. The agent only
    names a font; this module builds the trusted <link>, so no arbitrary remote
    URL can be injected.
  * The body fragment is scoped to `.custom-post` and sanitized (no scripts, no
    external resources) before it is stored.
"""
import re
import json
import logging

from db import get_db
from .base import Agent, load_prompt

logger = logging.getLogger(__name__)

# Curated Google Fonts the Designer may choose from.
# name -> (css2 family query, CSS font stack)
ALLOWED_FONTS = {
    # Serif / display
    'Fraunces':         ("Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700", "'Fraunces', Georgia, serif"),
    'Spectral':         ("Spectral:wght@400;500;600;700", "'Spectral', Georgia, serif"),
    'Newsreader':       ("Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600", "'Newsreader', Georgia, serif"),
    'Lora':             ("Lora:wght@400;500;600;700", "'Lora', Georgia, serif"),
    'DM Serif Display': ("DM+Serif+Display:ital@0;1", "'DM Serif Display', Georgia, serif"),
    # Sans / geometric
    'Space Grotesk':    ("Space+Grotesk:wght@400;500;600;700", "'Space Grotesk', system-ui, sans-serif"),
    'Inter':            ("Inter:wght@400;500;600;700", "'Inter', system-ui, sans-serif"),
    'Archivo':          ("Archivo:wght@400;500;600;700", "'Archivo', system-ui, sans-serif"),
    'Syne':             ("Syne:wght@400;500;600;700;800", "'Syne', system-ui, sans-serif"),
    'IBM Plex Sans':    ("IBM+Plex+Sans:wght@400;500;600", "'IBM Plex Sans', system-ui, sans-serif"),
    # Monospace
    'JetBrains Mono':   ("JetBrains+Mono:wght@400;500;600;700", "'JetBrains Mono', ui-monospace, monospace"),
    'Space Mono':       ("Space+Mono:wght@400;700", "'Space Mono', ui-monospace, monospace"),
    'IBM Plex Mono':    ("IBM+Plex+Mono:wght@400;500;600;700", "'IBM Plex Mono', ui-monospace, monospace"),
}

# CSS variables the Designer may override. Anything else is dropped.
ALLOWED_VARS = {
    '--bg', '--bg-elev', '--panel', '--fg', '--muted', '--faint',
    '--line', '--accent', '--accent-hover', '--glow-1', '--glow-2',
}

# A safe colour value: hex, or rgb/rgba/hsl/hsla. Nothing else gets through.
_COLOR_RE = re.compile(
    r'^(#[0-9a-fA-F]{3,8}|(?:rgb|rgba|hsl|hsla)\([0-9.,%\s]+\))$'
)

# Body-fragment sanitization: strip anything that loads code or remote resources.
_SCRIPT_RE = re.compile(r'<\s*script\b.*?<\s*/\s*script\s*>', re.IGNORECASE | re.DOTALL)
_DANGER_TAG_RE = re.compile(r'<\s*(link|iframe|object|embed|meta|base)\b[^>]*>', re.IGNORECASE)
_IMPORT_RE = re.compile(r'@import[^;]*;?', re.IGNORECASE)
_ON_ATTR_RE = re.compile(r'\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', re.IGNORECASE)
_JS_URL_RE = re.compile(r'javascript:', re.IGNORECASE)


def _sanitize_fragment(html):
    html = _SCRIPT_RE.sub('', html)
    html = _DANGER_TAG_RE.sub('', html)
    html = _IMPORT_RE.sub('', html)
    html = _ON_ATTR_RE.sub('', html)
    html = _JS_URL_RE.sub('#', html)
    return html.strip()


def _strip_fences(text):
    t = text.strip()
    if t.startswith('```'):
        t = t.split('\n', 1)[1] if '\n' in t else ''
        if t.rstrip().endswith('```'):
            t = t.rstrip()[:-3]
    return t.strip()


def _parse_theme(raw):
    """Parse the Designer's delimiter format into a validated theme dict + body.

    Expected format:
        RATIONALE: one line
        FONTS: display=Fraunces; body=Spectral; mono=JetBrains Mono
        VARS:
        --bg: #110a1e
        --accent: #ff7ab6
        ---HTML---
        <style>.custom-post ...</style>
        ...body...
    """
    raw = _strip_fences(raw)
    meta, _, body = raw.partition('---HTML---')

    rationale = ''
    fonts = {}
    variables = {}
    in_vars = False

    for line in meta.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith('RATIONALE:'):
            rationale = stripped[10:].strip()
        elif stripped.upper().startswith('FONTS:'):
            for pair in stripped[6:].split(';'):
                if '=' in pair:
                    role, name = pair.split('=', 1)
                    role, name = role.strip().lower(), name.strip()
                    if role in ('display', 'body', 'mono') and name in ALLOWED_FONTS:
                        fonts[role] = name
        elif stripped.upper().startswith('VARS:'):
            in_vars = True
        elif in_vars and stripped.startswith('--') and ':' in stripped:
            key, value = stripped.split(':', 1)
            key, value = key.strip(), value.strip().rstrip(';').strip()
            if key in ALLOWED_VARS and _COLOR_RE.match(value):
                variables[key] = value

    theme = {'rationale': rationale, 'fonts': fonts, 'vars': variables}
    return theme, _sanitize_fragment(body)


class DesignerAgent(Agent):
    name = 'designer'
    model = 'claude-sonnet-4-6'

    def __init__(self):
        super().__init__()
        self.system = load_prompt('designer.txt')

    def generate_theme(self, post_id):
        """Design a bespoke theme + body layout for a post. Stores both in
        posts.custom_theme / posts.custom_html. Leaves render_mode unchanged so
        the admin approves it. Returns post_id, or None if the post is missing."""
        conn = get_db()
        row = conn.execute(
            "SELECT title, topic, body_md FROM posts WHERE id = ?", (post_id,)
        ).fetchone()
        conn.close()

        if not row:
            logger.error("Post %d not found for theme generation", post_id)
            return None

        fonts_list = ', '.join(ALLOWED_FONTS.keys())
        vars_list = ', '.join(sorted(ALLOWED_VARS))
        user_message = f"""AVAILABLE FONTS (choose only from these names): {fonts_list}
OVERRIDABLE VARS (choose only from these): {vars_list}

TITLE: {row['title']}
TOPIC: {row['topic'] or 'misc'}
---
{row['body_md']}"""

        raw = self.complete(self.system, user_message, max_tokens=4000)
        theme, body_html = _parse_theme(raw)

        conn = get_db()
        conn.execute(
            "UPDATE posts SET custom_theme = ?, custom_html = ? WHERE id = ?",
            (json.dumps(theme), body_html, post_id),
        )
        conn.commit()
        conn.close()

        logger.info(
            "Designed theme for post %d (%d vars, fonts=%s, %d chars body)",
            post_id, len(theme['vars']), theme['fonts'], len(body_html),
        )
        return post_id


# Shared instance + module-level helpers
designer = DesignerAgent()


def generate_theme(post_id):
    return designer.generate_theme(post_id)


def build_theme_head(theme):
    """Build the trusted <head> markup (font links + :root overrides) for a theme.

    ``theme`` is the parsed dict (or its JSON string). Returns a plain string;
    callers wrap it in Markup. Returns '' when there is nothing to apply.
    """
    if not theme:
        return ''
    if isinstance(theme, str):
        try:
            theme = json.loads(theme)
        except (ValueError, TypeError):
            return ''

    fonts = theme.get('fonts') or {}
    variables = theme.get('vars') or {}

    # Trusted font <link> built from the allowlist only.
    families = []
    seen = set()
    for role in ('display', 'body', 'mono'):
        name = fonts.get(role)
        if name in ALLOWED_FONTS and name not in seen:
            families.append(ALLOWED_FONTS[name][0])
            seen.add(name)

    parts = []
    if families:
        query = '&'.join(f'family={f}' for f in families)
        parts.append(
            f'<link href="https://fonts.googleapis.com/css2?{query}&display=swap" rel="stylesheet">'
        )

    decls = []
    for key, value in variables.items():
        if key in ALLOWED_VARS and _COLOR_RE.match(value):
            decls.append(f'{key}:{value}')
    if 'body' in fonts:
        decls.append(f'--sans:{ALLOWED_FONTS[fonts["body"]][1]}')
    if 'mono' in fonts:
        decls.append(f'--mono:{ALLOWED_FONTS[fonts["mono"]][1]}')
    if 'display' in fonts:
        decls.append(f'--display:{ALLOWED_FONTS[fonts["display"]][1]}')

    if decls:
        parts.append('<style id="custom-theme">:root{' + ';'.join(decls) + '}</style>')

    return '\n'.join(parts)


def theme_head(post):
    """Jinja helper: render the theme head for a post when it is in custom mode."""
    if not post or getattr(post, 'render_mode', 'standard') != 'custom':
        return ''
    return build_theme_head(getattr(post, 'custom_theme', None))
